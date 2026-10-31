"""Download the official Vosk small English model for local speech recognition."""
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import ZipFile
import shutil

ROOT = Path(__file__).resolve().parent
NAME = 'vosk-model-small-en-us-0.15'
URL = f'https://alphacephei.com/vosk/models/{NAME}.zip'


def install():
    models = ROOT / 'models'
    target = models / NAME
    if target.is_dir():
        print('Voice model already installed.')
        return
    models.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=models) as temporary:
        temporary = Path(temporary)
        archive = temporary / 'voice.zip'
        print('Downloading the official English voice model (about 40 MB)…', flush=True)
        with urlopen(URL, timeout=120) as response, archive.open('wb') as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 100 * 1024 * 1024:
                    raise RuntimeError('Voice model download exceeded the expected size limit.')
                output.write(chunk)
        with ZipFile(archive) as source:
            if sum(info.file_size for info in source.infolist()) > 400 * 1024 * 1024:
                raise RuntimeError('Voice model archive is unexpectedly large.')
            for info in source.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != NAME:
                    raise RuntimeError('Unsafe path in voice model archive.')
            source.extractall(temporary)
        extracted = temporary / NAME
        if not (extracted / 'am' / 'final.mdl').is_file():
            raise RuntimeError('Downloaded archive does not contain the expected voice model.')
        shutil.move(str(extracted), str(target))
    print('Offline voice model installed.')


if __name__ == '__main__':
    install()
