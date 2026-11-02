from contextlib import ExitStack
from io import BytesIO
import importlib.util
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave
import desktop
import speech_input


class SpeechInputTests(unittest.TestCase):
    def recognizer(self, text, language='te', confidence=-.2):
        stt=object.__new__(speech_input.SpeechInput)
        stt.language='auto'
        stt.model=Mock()
        stt.model.transcribe.return_value=([SimpleNamespace(text=text,avg_logprob=confidence)],SimpleNamespace(language=language))
        return stt

    def test_sends_original_sample_rate_audio_in_memory(self):
        stt=self.recognizer('నమస్కారం')
        original=b'\x01\x00'*48000
        result=stt.transcribe(original,48000)
        data=stt.model.transcribe.call_args.args[0]
        data.seek(0)
        with wave.open(data,'rb') as audio:
            self.assertEqual(audio.getframerate(),48000)
            self.assertEqual(audio.readframes(48000),original)
        self.assertEqual((result.text,result.language,result.clear),('నమస్కారం','te',True))
        self.assertIsNone(stt.model.transcribe.call_args.kwargs['language'])

    def test_unclear_speech_is_not_accepted_as_a_question(self):
        stt=self.recognizer('guessed words',language='en',confidence=-1.6)
        self.assertFalse(stt.transcribe(b'\0\0'*16000,16000).clear)

    def test_short_audio_is_not_sent_for_transcription(self):
        stt=self.recognizer('fake words')
        self.assertFalse(stt.transcribe(b'\0\0'*100,16000).clear)
        stt.model.transcribe.assert_not_called()

    def test_unsupported_detected_language_is_not_guessed(self):
        stt=self.recognizer('unexpected',language='fr')
        self.assertFalse(stt.transcribe(b'\0\0'*16000,16000).clear)

    def test_voice_follows_telugu_script(self):
        self.assertEqual(speech_input.speech_voice('నమస్కారం'),'te')
        self.assertEqual(speech_input.speech_voice('Hello, how can I help?'),'en-us')

    @unittest.skipUnless(importlib.util.find_spec('faster_whisper'), 'Optional speech dependencies are not installed')
    def test_installed_decoder_and_vad_accept_memory_audio(self):
        from faster_whisper.audio import decode_audio
        from faster_whisper.vad import get_speech_timestamps, VadOptions
        audio=BytesIO()
        with wave.open(audio,'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(48000)
            wav.writeframes(b'\0\0'*48000)
        audio.seek(0)
        decoded=decode_audio(audio,sampling_rate=16000)
        self.assertEqual(decoded.shape,(16000,))
        self.assertEqual(get_speech_timestamps(decoded,VadOptions()),[])

    def test_loading_never_downloads_models_during_conversation(self):
        module=Mock()
        with patch.dict('sys.modules',{'faster_whisper':module}),patch.object(speech_input,'MODEL_PATH') as path:
            path.__truediv__.return_value.is_file.return_value=True
            recognizer=speech_input.SpeechInput()
            self.assertTrue(module.WhisperModel.call_args.kwargs['local_files_only'])
            self.assertEqual(module.WhisperModel.call_args.kwargs['compute_type'],'int8')


if __name__=='__main__':unittest.main()
