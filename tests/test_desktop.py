import io
import json
import queue
import threading
import unittest
from contextlib import closing
from unittest.mock import patch, Mock
import desktop


class DesktopTests(unittest.TestCase):
    def test_name_matching(self):
        for text in ['Andy', 'hey andy', 'ANDY', 'andi', 'andie']:
            self.assertTrue(desktop.is_wake_word(text))
        for text in ['candy', 'handyman', 'and', 'hello', 'andyish']:
            self.assertFalse(desktop.is_wake_word(text))

    def test_ollama_reply_and_spoken_context(self):
        reply = closing(io.BytesIO(b'{"message":{"content":"Here is your answer."},"done":true}\n'))
        with patch.object(desktop, 'build_opener') as opener:
            opener.return_value.open.return_value = reply
            answer, history = desktop.ask_ollama([], 'Explain CPUs')
            req = opener.return_value.open.call_args.args[0]
            sent = json.loads(req.data)
            self.assertEqual(sent['messages'][-1]['content'], 'Explain CPUs')
            self.assertIn('spoken', sent['messages'][0]['content'])
        self.assertEqual(answer, 'Here is your answer.')
        self.assertEqual(history[-1]['role'], 'assistant')

    def test_unavailable_ollama(self):
        with patch.object(desktop, 'build_opener') as opener:
            opener.return_value.open.side_effect = desktop.URLError('not running')
            with self.assertRaisesRegex(RuntimeError, 'Check that it is running'):
                desktop.ask_ollama([], 'Hello')

    def test_pause_closes_microphone_and_stops_speech(self):
        worker = desktop.VoiceWorker(queue.Queue(), 1, threading.Event())
        worker.stream = Mock()
        worker.speaker = Mock()
        worker.speaker.poll.return_value = None
        worker.cancel()
        self.assertTrue(worker.stop.is_set())
        worker.stream.abort.assert_called_once()
        worker.stream.close.assert_called_once()
        worker.speaker.terminate.assert_called_once()

    def test_queued_audio_is_bounded_and_playback_audio_is_discarded(self):
        worker = desktop.VoiceWorker(queue.Queue(), 1, threading.Event())
        for _ in range(100):
            worker.on_audio(b'audio', 100, None, None)
        self.assertEqual(worker.audio.qsize(), 80)
        worker.clear_audio()
        self.assertTrue(worker.audio.empty())

    def test_native_wake_to_reply_flow(self):
        worker = desktop.VoiceWorker(queue.Queue(), 1, threading.Event())
        vosk, sd = Mock(), Mock()
        from unittest.mock import MagicMock
        sd.RawInputStream.return_value = MagicMock()
        sd.query_devices.return_value = {'default_samplerate':16000}
        wake, command = Mock(), Mock()
        vosk.KaldiRecognizer.side_effect = [wake, command]
        wake.AcceptWaveform.return_value = False
        wake.PartialResult.return_value = '{"partial":"andy"}'
        command.AcceptWaveform.return_value = True
        command.Result.return_value = '{"text":"what is a processor"}'
        frames = iter([b'wake', b'question'])
        def next_audio(timeout):
            return next(frames)
        worker.audio.get = next_audio
        worker.clear_audio = Mock()
        spoken = []
        def say(text):
            spoken.append(text)
            if len(spoken) == 2:
                worker.stop.set()
        worker.say = say
        def streamed_reply(history, text, on_sentence=None, stop=None, information=None, tools=None):
            on_sentence('A processor runs instructions.')
            return 'A processor runs instructions.', []
        with patch.dict('sys.modules', {'sounddevice':sd,'vosk':vosk}), patch.object(desktop.shutil,'which',return_value='/usr/bin/espeak-ng'), patch.object(desktop,'VOICE_MODEL') as model_path, patch.object(desktop,'SpeechInput') as speech, patch.object(desktop,'ask_ollama',side_effect=streamed_reply) as ask:
            from speech_input import Transcript
            speech.return_value.transcribe.return_value = Transcript('what is a processor', 'en', True)
            model_path.is_dir.return_value = True
            worker.run()
            self.assertEqual(ask.call_args.args, ([], 'what is a processor'))
            self.assertIs(ask.call_args.kwargs['stop'], worker.stop)
        self.assertEqual(spoken, ['Yes?', 'A processor runs instructions.'])
        self.assertGreaterEqual(worker.clear_audio.call_count, 1)


if __name__ == '__main__':
    unittest.main()
