import asyncio
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock,patch,AsyncMock
from voice_output import speech_command,save_neural


class VoiceTests(unittest.TestCase):
    def test_neural_voice_is_english_female_with_slower_rate(self):
        module=Mock()
        module.Communicate.return_value.save=AsyncMock()
        with patch.dict('sys.modules',{'edge_tts':module}),patch.dict('os.environ',{'ANDY_TTS_VOICE':'en-IN-NeerjaNeural','ANDY_TTS_RATE':'-8%'}):
            self.assertTrue(asyncio.run(save_neural('Hello','unused.mp3',threading.Event())))
        self.assertEqual(module.Communicate.call_args.kwargs['voice'],'en-IN-NeerjaNeural')
        self.assertEqual(module.Communicate.call_args.kwargs['rate'],'-8%')

    def test_generated_audio_is_temporary(self):
        async def create(text,path,stop):path.write_bytes(b'audio');return True
        with patch('voice_output.save_neural',side_effect=create),patch('voice_output.shutil.which',return_value='/usr/bin/mpv'):
            with speech_command('Hello',threading.Event()) as (command,data):
                path=Path(command[-1]);self.assertTrue(path.exists());self.assertIsNone(data)
            self.assertFalse(path.exists())

    def test_service_failure_uses_female_style_offline_backup(self):
        notice=Mock()
        with patch('voice_output.save_neural',side_effect=RuntimeError('offline')),patch('voice_output.shutil.which',return_value='/usr/bin/mpv'):
            with speech_command('Hello',threading.Event(),notice) as (command,data):
                self.assertIn('en-us+f3',command);self.assertEqual(data,b'Hello')
        notice.assert_called_once()

    def test_cancellation_stops_in_progress_synthesis(self):
        stop=threading.Event()
        module=Mock()
        async def wait_forever(path):await asyncio.Event().wait()
        module.Communicate.return_value.save=wait_forever
        async def run():
            asyncio.get_running_loop().call_later(.02,stop.set)
            return await save_neural('Hello','unused.mp3',stop)
        with patch.dict('sys.modules',{'edge_tts':module}):
            self.assertFalse(asyncio.run(run()))

    def test_cancelled_speech_never_starts_service(self):
        stop=threading.Event();stop.set()
        with patch('voice_output.save_neural') as network:
            with speech_command('Hello',stop) as result:self.assertEqual(result,(None,None))
            network.assert_not_called()


if __name__=='__main__':unittest.main()
