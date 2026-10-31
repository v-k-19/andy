import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile
import download_voice_model as downloader


def archive_bytes(entries):
    data = io.BytesIO()
    with ZipFile(data, 'w') as archive:
        for name, value in entries.items():
            archive.writestr(name, value)
    data.seek(0)
    return data


class VoiceDownloadTests(unittest.TestCase):
    def test_installs_expected_model_and_skips_repeat_download(self):
        with TemporaryDirectory() as temporary, patch.object(downloader, 'ROOT', Path(temporary)), patch.object(downloader, 'urlopen') as fetch:
            fetch.return_value = archive_bytes({downloader.NAME + '/am/final.mdl': b'model'})
            downloader.install()
            self.assertTrue((Path(temporary) / 'models' / downloader.NAME / 'am/final.mdl').exists())
            downloader.install()
            fetch.assert_called_once()

    def test_rejects_archive_path_traversal(self):
        with TemporaryDirectory() as temporary, patch.object(downloader, 'ROOT', Path(temporary)), patch.object(downloader, 'urlopen') as fetch:
            fetch.return_value = archive_bytes({downloader.NAME + '/../outside.txt': b'bad'})
            with self.assertRaisesRegex(RuntimeError, 'Unsafe path'):
                downloader.install()
            self.assertFalse((Path(temporary) / 'models' / 'outside.txt').exists())
            self.assertFalse((Path(temporary) / 'models' / downloader.NAME).exists())


if __name__ == '__main__':
    unittest.main()
