"""English female neural speech, with a local female-style backup voice."""
import asyncio
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

_ACKNOWLEDGEMENT = None


async def save_neural(text,path,stop):
    import edge_tts
    speech=edge_tts.Communicate(text,voice=os.getenv('ANDY_TTS_VOICE','en-IN-NeerjaNeural'),
                               rate=os.getenv('ANDY_TTS_RATE','-8%'),volume='-5%',
                               proxy=os.getenv('HTTPS_PROXY') or os.getenv('https_proxy'))
    task=asyncio.create_task(speech.save(str(path)))
    try:
        while not task.done():
            if stop.is_set():return False
            await asyncio.wait([task],timeout=.1)
        await task
        return True
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)


@contextmanager
def speech_command(text,stop,notice=None):
    """Yield playback argv and optional stdin. Temporary speech files are deleted."""
    global _ACKNOWLEDGEMENT
    if stop.is_set():
        yield None,None
        return
    if os.getenv('ANDY_TTS_ENGINE','edge')=='edge' and shutil.which('mpv'):
        with TemporaryDirectory(prefix='andy-speech-') as folder:
            path=Path(folder)/'speech.mp3'
            try:
                if text == 'Yes?' and _ACKNOWLEDGEMENT:
                    path.write_bytes(_ACKNOWLEDGEMENT)
                    ready=True
                else:
                    ready=asyncio.run(asyncio.wait_for(save_neural(text,path,stop),timeout=25))
                if not ready or stop.is_set():
                    yield None,None
                    return
                if not path.is_file() or not path.stat().st_size:raise RuntimeError('Empty speech audio')
                if text == 'Yes?':_ACKNOWLEDGEMENT=path.read_bytes()
            except Exception:
                if notice:notice('Neural voice unavailable','Using the offline backup voice for this reply.')
            else:
                yield ['mpv','--no-video','--really-quiet','--no-terminal',str(path)],None
                return
    elif os.getenv('ANDY_TTS_ENGINE','edge')=='edge' and notice:
        notice('Neural voice needs mpv','Install mpv to hear the softer female neural voice. Using offline backup.')
    if stop.is_set():yield None,None
    else:yield ['espeak-ng','-v','en-us+f3','-s','155','-a','90','--stdin'],text.encode()
