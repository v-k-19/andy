from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock,patch
from desktop_tools import DesktopTools
import desktop


class ToolTests(unittest.TestCase):
    def setUp(self):self.tools=DesktopTools()
    def tearDown(self):self.tools.close()

    def test_app_launch_uses_allowlisted_executable(self):
        with patch('desktop_tools.shutil.which',return_value='/usr/bin/kcalc'),patch('desktop_tools.subprocess.Popen') as run:
            answer=self.tools.handle('Open calculator')
        self.assertIn('Opening',answer)
        self.assertEqual(run.call_args.args[0],['/usr/bin/kcalc'])
        self.assertNotIn('shell',run.call_args.kwargs)

    def test_arbitrary_arguments_are_not_executed(self):
        with patch('desktop_tools.subprocess.Popen') as run:
            self.tools.handle('Open calculator --some-argument')
            run.assert_not_called()

    def test_website_launch_is_explicit(self):
        with patch('desktop_tools.webbrowser.open',return_value=True) as browser:
            self.assertIsNone(self.tools.handle('What is YouTube?'))
            browser.assert_not_called()
            self.tools.handle('Open YouTube')
            browser.assert_called_once_with('https://www.youtube.com')

    def test_online_music_query_is_data_not_a_shell_command(self):
        with patch('desktop_tools.shutil.which',return_value='/usr/bin/program'),patch('desktop_tools.subprocess.Popen') as run:
            run.return_value.poll.return_value=None
            answer=self.tools.handle('Play online relaxing music')
            self.assertEqual(run.call_args.args[0][-1],'ytdl://ytsearch1:relaxing music')
            self.assertNotIn('shell',run.call_args.kwargs)
            self.assertIn('Starting',answer)

    def test_local_music_stays_in_configured_folder(self):
        with TemporaryDirectory() as folder:
            song=Path(folder)/'Quiet Song.mp3';song.write_bytes(b'audio')
            with patch.dict('os.environ',{'ANDY_MUSIC_DIR':folder}),patch.object(self.tools,'playback',return_value=None) as play:
                answer=self.tools.handle('Play local quiet')
            play.assert_called_once_with(str(song))
            self.assertIn('Quiet Song',answer)

    def test_app_action_bypasses_language_model(self):
        tools=Mock();tools.handle.return_value='Opening calculator.'
        with patch.object(desktop,'build_opener') as model:
            answer,_=desktop.ask_ollama([], 'Open calculator',tools=tools)
            model.assert_not_called()
        self.assertEqual(answer,'Opening calculator.')


if __name__=='__main__':unittest.main()
