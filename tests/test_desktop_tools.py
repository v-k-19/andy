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

    def test_online_music_resolves_actual_track_before_playback(self):
        metadata=Mock(stdout='{"entries":[{"id":"abcdefghijk","title":"Relaxing track"}]}')
        with patch('desktop_tools.shutil.which',return_value='/usr/bin/program'),patch('desktop_tools.subprocess.run',return_value=metadata) as search,patch.object(self.tools,'playback',return_value=None) as play:
            answer=self.tools.handle('Can you please play the song relaxing music on YouTube?')
        self.assertEqual(search.call_args.args[0][-1],'ytsearch1:relaxing music')
        self.assertNotIn('shell',search.call_args.kwargs)
        play.assert_called_once_with('ytdl://https://www.youtube.com/watch?v=abcdefghijk',stop=None)
        self.assertIn('audio player has started',answer)

    def test_reported_song_request_routes_to_music_without_llm(self):
        with patch.object(self.tools,'play_online',return_value='Audio ready') as play,patch.object(desktop,'build_opener') as model:
            answer,_=desktop.ask_ollama([], 'play majboor song by zoya wassem',tools=self.tools)
            play.assert_called_once()
            self.assertEqual(play.call_args.args[0],'majboor song by zoya wassem')
            model.assert_not_called()
        self.assertEqual(answer,'Audio ready')

    def test_polite_music_requests_do_not_fall_through_to_model(self):
        for phrase in ['Can you play Imagine?', 'I want to listen to Imagine', 'Please put on Imagine', 'Find and play Imagine', 'Andy, could you play Imagine?']:
            with patch.object(self.tools,'play_online',return_value='Playback ready') as play:
                self.assertEqual(self.tools.handle(phrase),'Playback ready')
                play.assert_called_once_with('Imagine',stop=None)

    def test_search_failure_never_claims_playback(self):
        import subprocess
        error=subprocess.CalledProcessError(1,['yt-dlp'],stderr='Source unavailable')
        with patch('desktop_tools.shutil.which',return_value='/usr/bin/program'),patch('desktop_tools.subprocess.run',side_effect=error),patch.object(self.tools,'playback') as play:
            answer=self.tools.handle('Play Imagine')
            play.assert_not_called()
        self.assertIn('could not complete',answer)
        self.assertNotIn('has started',answer)
        self.assertIn('Source unavailable',self.tools.last_error)

    def test_player_exit_is_reported_instead_of_success(self):
        with patch('desktop_tools.shutil.which',return_value='/usr/bin/mpv'),patch('desktop_tools.subprocess.Popen') as run:
            run.return_value.poll.return_value=1
            answer=self.tools.playback('ytdl://https://www.youtube.com/watch?v=abcdefghijk')
        self.assertIn('could not start audio',answer)
        self.assertIsNone(self.tools.process)

    def test_player_stdout_error_is_captured_and_media_url_redacted(self):
        def fail(arguments,**kwargs):
            kwargs['stdout'].write(b'[ytdl_hook] ERROR: HTTP Error 403: Forbidden https://media.example/path?token=temporary\n')
            process=Mock();process.poll.return_value=2;process.returncode=2
            return process
        with patch('desktop_tools.shutil.which',return_value='/usr/bin/mpv'),patch('desktop_tools.subprocess.Popen',side_effect=fail) as start:
            self.tools.playback('ytdl://https://www.youtube.com/watch?v=abcdefghijk')
        self.assertIn('403: Forbidden',self.tools.last_error)
        self.assertIn('exit code 2',self.tools.last_error)
        self.assertNotIn('token=temporary',self.tools.last_error)
        self.assertIs(start.call_args.kwargs['stderr'],__import__('subprocess').STDOUT)
        self.assertNotIn('--no-terminal',start.call_args.args[0])
        self.assertNotIn('--really-quiet',start.call_args.args[0])

    def test_player_success_requires_audio_params(self):
        with patch('desktop_tools.shutil.which',return_value='/usr/bin/mpv'),patch('desktop_tools.subprocess.Popen') as run,patch.object(self.tools,'player_request',return_value={'samplerate':48000}):
            run.return_value.poll.return_value=None
            self.assertIsNone(self.tools.playback('local-file.mp3'))

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
