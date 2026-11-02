"""Pre-download Whisper for offline English/Telugu recognition."""
from pathlib import Path
from speech_input import MODEL_PATH, SPEECH_MODEL


def install():
    from faster_whisper.utils import download_model
    if SPEECH_MODEL not in ('tiny', 'base', 'small', 'medium'):
        raise RuntimeError('Use a multilingual Whisper model: tiny, base, small, or medium.')
    MODEL_PATH.parent.mkdir(exist_ok=True)
    print(f'Downloading/checking multilingual Whisper {SPEECH_MODEL}; this can take a while.', flush=True)
    download_model(SPEECH_MODEL, output_dir=str(MODEL_PATH))
    print('Multilingual speech model ready for offline use.')


if __name__ == '__main__':
    install()
