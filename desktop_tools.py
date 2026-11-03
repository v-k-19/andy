"""Explicit, bounded desktop requests. Never executes generated shell commands."""
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
import webbrowser
from web_tools import public_url


APPS={
    'terminal':('konsole','gnome-terminal','kitty','alacritty','xterm'),
    'calculator':('kcalc','gnome-calculator','galculator'),
    'text editor':('kate','gnome-text-editor','gedit','mousepad'),
    'settings':('systemsettings','gnome-control-center','xfce4-settings-manager'),
    'firefox':('firefox',),'chromium':('chromium',),'vlc':('vlc',),
}
SITES={'youtube':'https://www.youtube.com','google':'https://www.google.com',
       'github':'https://github.com','wikipedia':'https://en.wikipedia.org',
       'spotify':'https://open.spotify.com','youtube music':'https://music.youtube.com'}


class DesktopTools:
    def __init__(self):
        self.process=None;self.queue=[];self.index=0
        self.ipc=TemporaryDirectory(prefix='andy-music-')
        self.socket_path=str(Path(self.ipc.name)/'player.sock')

    def launch(self,arguments):
        try:
            subprocess.Popen(arguments,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return True
        except OSError:
            return False

    def stop_music(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=2)
        self.process=None

    def close(self):self.stop_music();self.ipc.cleanup()

    def playback(self,target):
        if not shutil.which('mpv'):return 'Install mpv to play music.'
        self.stop_music()
        try:
            Path(self.socket_path).unlink(missing_ok=True)
            self.process=subprocess.Popen(['mpv','--no-video','--really-quiet','--no-terminal',
                '--input-ipc-server='+self.socket_path,'--ytdl-format=bestaudio/best','--volume=45','--',target],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return None
        except OSError:return 'I could not start the music player. Check that mpv is installed.'

    def pause_music(self,pause):
        if not self.process or self.process.poll() is not None:return 'No music is currently running in Andy’s player.'
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
                channel.settimeout(1);channel.connect(self.socket_path)
                channel.sendall((json.dumps({'command':['set_property','pause',pause]})+'\n').encode())
            return 'Music paused.' if pause else 'Music resumed.'
        except OSError:return 'The player is still starting or is unavailable. Please try again.'

    def play_local(self,query):
        root=Path(os.getenv('ANDY_MUSIC_DIR',str(Path.home()/'Music'))).expanduser().resolve()
        if not root.is_dir():return 'Your Music folder was not found. Set ANDY_MUSIC_DIR to your music folder.'
        tokens=re.findall(r'\w+',query.lower())
        found=[]
        for count,path in enumerate(root.rglob('*')):
            if count>=10000:break
            if path.suffix.lower() not in {'.mp3','.flac','.wav','.ogg','.m4a','.opus','.aac','.aiff'}:continue
            real=path.resolve()
            if not real.is_relative_to(root) or not real.is_file():continue
            label=str(path.relative_to(root)).lower()
            if all(token in label for token in tokens):found.append(real)
        self.queue=sorted(found)
        self.index=0
        if not self.queue:return 'I could not find matching audio in your Music folder. Try a song or artist name.'
        error=self.playback(str(self.queue[0]))
        return error or 'Starting local track: '+self.queue[0].stem+'.'

    def handle(self,text):
        command=re.sub(r'^(?:hey\s+)?andy[,.]?\s+|^please\s+','',text.strip(),flags=re.I).strip(' .!?')
        lower=command.lower()
        if lower in ('pause music','pause the music','pause song'):return self.pause_music(True)
        if lower in ('resume music','resume the music','continue music'):return self.pause_music(False)
        if lower in ('stop music','stop the music','stop song'):
            self.stop_music();return 'Andy’s music player is stopped.'
        if lower in ('next song','next track','skip song'):
            if self.index+1>=len(self.queue):return 'There is no next local track. Ask me to play another song.'
            self.index+=1
            error=self.playback(str(self.queue[self.index]))
            return error or 'Starting local track: '+self.queue[self.index].stem+'.'
        local=re.match(r'(?:play local(?: music)?|play (?:music|songs|files) from (?:my )?(?:pc|computer|music folder))(?:\s+(.+))?$',command,re.I)
        if local:return self.play_local(re.sub(r'^(?:songs?|files?)\s+','',local[1] or '',flags=re.I))
        play=re.match(r'play(?: me)?(?: online)?\s+(.+)',command,re.I)
        if play:
            query=play[1]
            if query.lower() in ('music','some music','a song'):query='relaxing music'
            if not shutil.which('yt-dlp'):return 'Install yt-dlp and mpv for online music playback.'
            self.queue=[]
            error=self.playback('ytdl://ytsearch1:'+query[:250])
            return error or 'Starting an online music search for '+query+'. Playback depends on the source being available.'
        opening=re.fullmatch(r'(?:open|launch|start)\s+(.+)',command,re.I)
        if not opening:return None
        target=opening[1].lower().strip()
        if target in ('browser','web browser'):
            return 'Opening your browser.' if webbrowser.open('https://www.google.com') else 'I could not open the browser.'
        if target in ('file manager','files','downloads','music folder'):
            folder=Path.home()/('Downloads' if target=='downloads' else 'Music') if target in ('downloads','music folder') else Path.home()
            if not shutil.which('xdg-open'):return 'Install xdg-utils to open folders.'
            if not folder.is_dir():return 'That folder does not exist on your PC.'
            return 'Opening '+target+'.' if self.launch(['xdg-open',str(folder)]) else 'I could not open that folder.'
        if target in APPS:
            executable=next((shutil.which(app) for app in APPS[target] if shutil.which(app)),None)
            if not executable:return 'A supported '+target+' app is not installed.'
            return 'Opening '+target+'.' if self.launch([executable]) else 'I could not launch '+target+'.'
        url=SITES.get(target)
        if not url and re.fullmatch(r'(?:https?://)?[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s]*)?',target):
            url=target if '://' in target else 'https://'+target
            try:public_url(url)
            except ValueError:return 'Please name a public website.'
        if url:return 'Opening '+target+'.' if webbrowser.open(url) else 'I could not open the browser.'
        return 'Name a website or a supported app, such as the browser, terminal, calculator, text editor, settings, Firefox, Chromium, or VLC.'
