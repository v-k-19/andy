from array import array
import os
from pathlib import Path
import queue
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import Mock, MagicMock, patch
from device_preferences import DevicePreferences
from microphone_input import audio_levels, input_device
from speech_input import Transcript
import desktop


class MicrophoneTests(unittest.TestCase):
    def test_silence_and_signal_levels(self):
        self.assertEqual(audio_levels(b''),(0.,0.))
        self.assertEqual(audio_levels(b'\0\0'*100),(0.,0.))
        pcm=array('h',[16384,-16384]).tobytes()
        peak,rms=audio_levels(pcm)
        self.assertEqual(peak,.5);self.assertEqual(rms,.5)

    def test_device_number_name_and_default(self):
        self.assertEqual(input_device('2'),2)
        self.assertEqual(input_device('Pixy microphone'),'Pixy microphone')
        self.assertIsNone(input_device(''))

    def test_device_preferences_survive_restart_without_camera_consent(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'devices.json'
            first=DevicePreferences(path)
            first.save(microphone='Pixy microphone',camera='/dev/video2')
            loaded=DevicePreferences(path)
            with patch.dict(os.environ,{},clear=True):
                loaded.apply()
                self.assertEqual(os.environ['ANDY_INPUT_DEVICE'],'Pixy microphone')
                self.assertEqual(os.environ['ANDY_CAMERA_DEVICE'],'/dev/video2')
            self.assertEqual(set(loaded.state),{'microphone','camera'})
            self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_environment_override_wins_over_saved_device(self):
        with TemporaryDirectory() as directory:
            preferences=DevicePreferences(Path(directory)/'devices.json')
            preferences.save(microphone='Pixy')
            with patch.dict(os.environ,{'ANDY_INPUT_DEVICE':'4'}):
                preferences.apply()
                self.assertEqual(os.environ['ANDY_INPUT_DEVICE'],'4')

    def test_manual_talk_dispatches_without_wake_or_ollama_for_time(self):
        worker=desktop.VoiceWorker(queue.Queue(),1,threading.Event())
        worker.talk_requested.set()
        worker.clear_audio=Mock()
        worker.audio.get=Mock(return_value=b'\0\0'*16000)
        spoken=[]
        def say(text):
            spoken.append(text);worker.stop.set()
        worker.say=say
        sd,vosk=Mock(),Mock()
        sd.query_devices.return_value={'default_samplerate':16000,'name':'Pixy microphone'}
        sd.RawInputStream.return_value=MagicMock()
        wake,command=Mock(),Mock()
        vosk.KaldiRecognizer.side_effect=[wake,command]
        command.AcceptWaveform.return_value=True
        with patch.dict('sys.modules',{'sounddevice':sd,'vosk':vosk}),patch.object(desktop.shutil,'which',return_value='/usr/bin/espeak-ng'),patch.object(desktop,'VOICE_MODEL') as path,patch.object(desktop,'SpeechInput') as speech,patch.object(desktop,'build_opener') as network:
            path.is_dir.return_value=True
            speech.return_value.transcribe.return_value=Transcript('what time is it','en',True)
            worker.run()
            wake.AcceptWaveform.assert_not_called()
            network.assert_not_called()
        self.assertEqual(len(spoken),1)
        self.assertTrue(spoken[0].startswith("It's "))
        events=[]
        while not worker.events.empty():events.append(worker.events.get())
        self.assertTrue(any('Wake word bypassed' in event[2] for event in events))


if __name__=='__main__':unittest.main()
