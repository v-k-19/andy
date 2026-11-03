"""Local multilingual transcription of microphone PCM; audio stays in memory."""
from dataclasses import dataclass
import io
import os
from pathlib import Path
import wave

ROOT = Path(__file__).resolve().parent
SPEECH_MODEL = os.getenv('ANDY_SPEECH_MODEL', 'small')
MODEL_PATH = ROOT / 'models' / ('whisper-' + SPEECH_MODEL)


@dataclass
class Transcript:
    text: str
    language: str
    clear: bool


class SpeechInput:
    def __init__(self):
        from faster_whisper import WhisperModel
        if not (MODEL_PATH / 'model.bin').is_file():
            raise RuntimeError('Multilingual speech model is missing. Run bash install-desktop.sh first.')
        self.language = os.getenv('ANDY_SPEECH_LANGUAGE', 'en')
        if self.language not in ('auto', 'en', 'te'):
            raise RuntimeError('ANDY_SPEECH_LANGUAGE must be auto, en, or te.')
        self.model = WhisperModel(str(MODEL_PATH), device='cpu', compute_type='int8',
                                  cpu_threads=min(4, os.cpu_count() or 1), local_files_only=True)

    def transcribe(self, pcm, sample_rate):
        if len(pcm) < int(sample_rate * 2 * .35):
            return Transcript('', '', False)
        audio = io.BytesIO()
        with wave.open(audio, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(pcm)
        audio.seek(0)
        segments, info = self.model.transcribe(
            audio, language=None if self.language == 'auto' else self.language,
            beam_size=3, vad_filter=True, condition_on_previous_text=False,
            vad_parameters={'min_silence_duration_ms': 500})
        heard = list(segments)
        text = ' '.join(s.text.strip() for s in heard if s.text.strip())
        # Weak or unsupported recognition asks for repetition, not a guessed answer.
        clear = bool(text and info.language in ('en', 'te') and heard
                     and sum(s.avg_logprob for s in heard) / len(heard) >= -1.0)
        return Transcript(text, info.language, clear)


def speech_voice(text):
    return 'te' if any('\u0c00' <= char <= '\u0c7f' for char in text) else 'en-us'
