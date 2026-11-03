"""Diagnose online music search; add --play to also test playback."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from desktop_tools import DesktopTools


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query',nargs='?',default='relaxing instrumental music')
    parser.add_argument('--play',action='store_true')
    args=parser.parse_args()
    print('Andy project:',Path(__file__).resolve().parent)
    ready=True
    for program in ('mpv','yt-dlp','deno'):
        path=shutil.which(program)
        print(program+': '+(path or 'NOT FOUND'))
        if not path and program in ('mpv','yt-dlp'):ready=False
    if not ready:
        print('Install missing programs with: sudo pacman -S mpv yt-dlp deno')
        return
    if args.play:
        tools=DesktopTools()
        try:
            print(tools.play_online(args.query))
            if tools.last_error:print('Details:',tools.last_error)
            if tools.process and tools.process.poll() is None:
                input('Press Enter to stop the test music. ')
        except (EOFError,KeyboardInterrupt):pass
        finally:tools.close()
        return
    try:
        result=subprocess.run(['yt-dlp','--ignore-config','--dump-single-json','--flat-playlist','--skip-download',
                               '--no-warnings','--playlist-end','1','--','ytsearch1:'+args.query],
                              capture_output=True,text=True,timeout=20,check=True)
        entries=json.loads(result.stdout).get('entries') or []
        if entries:print('Search OK. First result:',entries[0].get('title','Untitled'))
        else:print('Search returned no results.')
        print('No music was played. Add --play to test audio playback.')
    except subprocess.CalledProcessError as error:
        print('Search FAILED. Provider details:',str(error.stderr or '')[-1200:])
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        print('Search FAILED:',type(error).__name__)


if __name__=='__main__':main()
