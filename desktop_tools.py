"""Explicit, bounded desktop requests. Never executes generated shell commands."""
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time
from tempfile import TemporaryDirectory,TemporaryFile
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


def player_error_text(log):
    log=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', log)
    log=re.sub(r'https?://[^\s]+','<media URL>',log)
    return '\n'.join(line.strip() for line in log.splitlines() if line.strip())[-1800:]


class DesktopTools:
    def __init__(self):
        self.process=None;self.queue=[];self.index=0
        self.player_log=None;self.download_log=None;self.downloader=None
        self.last_error=None;self.closed=False;self.browser_music=False
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
        if self.downloader:
            if self.downloader.poll() is None:
                self.downloader.terminate()
                try:self.downloader.wait(timeout=2)
                except subprocess.TimeoutExpired:self.downloader.kill();self.downloader.wait(timeout=2)
            if self.downloader.stdout:self.downloader.stdout.close()
            self.downloader=None
        if self.download_log:
            self.download_log.close();self.download_log=None
        if self.player_log:
            self.player_log.close();self.player_log=None

    def close(self):
        self.closed=True;self.stop_music();self.ipc.cleanup()

    def player_request(self,command,timeout=.4):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
            channel.settimeout(timeout);channel.connect(self.socket_path)
            channel.sendall((json.dumps({'command':command,'request_id':1})+'\n').encode())
            data=b''
            while len(data)<65536:
                chunk=channel.recv(4096)
                if not chunk:break
                data+=chunk
                while b'\n' in data:
                    line,data=data.split(b'\n',1)
                    result=json.loads(line)
                    if result.get('request_id')==1:
                        return result.get('data') if result.get('error')=='success' else None
        return None

    def playback(self,target,stop=None,media_command=None):
        if self.closed or (stop and stop.is_set()):return 'Music request cancelled.'
        if not shutil.which('mpv'):return 'Install mpv to play music.'
        self.stop_music()
        self.browser_music=False
        self.last_error=None
        try:
            Path(self.socket_path).unlink(missing_ok=True)
            self.player_log=TemporaryFile()
            source=subprocess.DEVNULL
            if media_command:
                self.download_log=TemporaryFile()
                self.downloader=subprocess.Popen(media_command,stdout=subprocess.PIPE,stderr=self.download_log)
                source=self.downloader.stdout
            self.process=subprocess.Popen(['mpv','--no-config','--no-video','--terminal=yes','--input-terminal=no','--msg-level=all=warn',
                '--input-ipc-server='+self.socket_path,'--ytdl-format=bestaudio/best','--ytdl-raw-options=ignore-config=','--volume=45','--',target],
                stdin=source,stdout=self.player_log,stderr=subprocess.STDOUT)
            if self.downloader and self.downloader.stdout:self.downloader.stdout.close()
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                if self.closed or (stop and stop.is_set()):
                    self.stop_music();return 'Music request cancelled.'
                if self.process.poll() is not None:
                    exit_code=self.process.returncode
                    self.player_log.seek(0,os.SEEK_END)
                    end=self.player_log.tell()
                    self.player_log.seek(max(0,end-6000))
                    details=player_error_text(self.player_log.read().decode(errors='replace'))
                    if self.download_log:
                        self.download_log.seek(0,os.SEEK_END)
                        end=self.download_log.tell();self.download_log.seek(max(0,end-6000))
                        details+='\nyt-dlp: '+player_error_text(self.download_log.read().decode(errors='replace'))
                    self.last_error=f'Player exited before audio started (exit code {exit_code}). '+(details or 'mpv did not provide an error message.')
                    self.stop_music()
                    return 'The music player could not start audio from that source. Try another song or open YouTube in your browser. Run check_music.py for details.'
                try:
                    if self.player_request(['get_property','audio-params']):return None
                except (OSError,ValueError):pass
                time.sleep(.15)
            self.last_error='No audio decoder became ready within 20 seconds.'
            self.stop_music()
            return 'The music source did not start within twenty seconds. Please try again or choose another song.'
        except OSError:
            self.stop_music()
            self.last_error='Could not start mpv.'
            return 'I could not start the music player. Check that mpv is installed.'

    def play_online(self,query,stop=None):
        if not shutil.which('yt-dlp') or not shutil.which('mpv'):
            return 'Install yt-dlp and mpv for online music playback.'
        self.last_error=None
        try:
            search=subprocess.run(['yt-dlp','--ignore-config','--dump-single-json','--flat-playlist','--skip-download',
                                   '--no-warnings','--playlist-end','1','--','ytsearch1:'+query[:250]],
                                  capture_output=True,text=True,timeout=20,check=True)
            result=json.loads(search.stdout)
            if not isinstance(result,dict):raise ValueError('Invalid music search response')
            entries=result.get('entries') or []
            if not isinstance(entries,list):raise ValueError('Invalid music results')
            if not entries:return 'I could not find an online track for that request. Try the song and artist together.'
            entry=entries[0]
            if not isinstance(entry,dict):raise ValueError('Invalid music result')
            video=entry.get('id','')
            if not isinstance(video,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',video):
                raise ValueError('No usable YouTube video ID')
            title=' '.join(str(entry.get('title') or query).split())[:140]
            if self.closed or (stop and stop.is_set()):return 'Music request cancelled.'
            self.queue=[]
            watch='https://www.youtube.com/watch?v='+video
            media=['yt-dlp','--ignore-config','--no-playlist','--no-progress','--format','bestaudio/best','--output','-','--',watch]
            error=self.playback('-',stop=stop,media_command=media)
            if error and not self.closed and not (stop and stop.is_set()):
                refused=re.search(r'403|forbidden|sign.?in|not available|not a bot',self.last_error or '',re.I)
                if refused:
                    try:opened=webbrowser.open(watch+'&autoplay=1')
                    except Exception:opened=False
                    if opened:
                        self.browser_music=True
                        return 'YouTube refused direct audio playback. I opened the selected song in your browser. Press Play there if it does not start. Browser playback uses its own controls.'
            return error or 'The audio player has started '+title+'.'
        except subprocess.CalledProcessError as error:
            self.last_error='Online search failed: '+str(error.stderr or '')[-1000:]
        except (OSError,ValueError,subprocess.TimeoutExpired) as error:
            self.last_error='Online search failed: '+type(error).__name__
        return 'I could not complete the online music search. The source may be blocked or yt-dlp may need updating. Run check_music.py to check it.'

    def pause_music(self,pause):
        if self.browser_music:return 'That song was opened in your browser. Please use the playback controls on its YouTube page.'
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

    def handle(self,text,stop=None):
        if self.closed or (stop and stop.is_set()):return 'Request cancelled.'
        command=re.sub(r"^(?:(?:hey\s+)?andy[,.]?\s+|please\s+|(?:can|could|would|will) you\s+|(?:i would|id|i'd) like (?:you )?to\s+|i want (?:you )?to\s+)+",'',text.strip(),flags=re.I).strip(' .!?')
        command=re.sub(r'^(?:put on|find and play|listen to)\s+','play ',command,flags=re.I)
        lower=command.lower()
        if lower in ('pause music','pause the music','pause song'):return self.pause_music(True)
        if lower in ('resume music','resume the music','continue music'):return self.pause_music(False)
        if lower in ('stop music','stop the music','stop song'):
            if self.browser_music:return 'That song was opened in your browser. Please use the playback controls on its YouTube page.'
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
            query=re.sub(r'^(?:the )?(?:song|track)(?: called| named)?\s+','',play[1],flags=re.I)
            query=re.sub(r'\s+(?:on|from) (?:youtube|youtube music|the internet|online)(?: please)?$','',query,flags=re.I)
            query=re.sub(r'\s+please$','',query,flags=re.I).strip()
            if query.lower() in ('music','some music','a song'):query='relaxing music'
            return self.play_online(query,stop=stop)
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
