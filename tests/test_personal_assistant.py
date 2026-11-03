from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch,Mock
from personal_assistant import PersonalAssistant,duration_seconds
import desktop
from ai_router import BrainRouter


class PersonalTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.path=Path(self.temp.name)/'personal.json'
        self.personal=PersonalAssistant(self.path)
        self.now=datetime(2026,11,3,12,0,tzinfo=timezone.utc)
    def tearDown(self):self.temp.cleanup()

    def test_notes_and_tasks_persist(self):
        self.personal.handle('Remember that I prefer Python')
        self.personal.handle('Add buy milk to my to do list')
        loaded=PersonalAssistant(self.path)
        self.assertIn('prefer Python',loaded.handle('Read my notes'))
        self.assertIn('buy milk',loaded.handle('List my tasks'))
        self.assertIn('completed',loaded.handle('Complete task 1'))
        self.assertIn('empty',loaded.handle('List my tasks'))
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

    def test_timer_duration_and_delivery_happen_once(self):
        self.assertEqual(duration_seconds('one hour and thirty minutes'),5400)
        self.assertEqual(duration_seconds('half an hour'),1800)
        self.assertIsNone(duration_seconds('five minutes and execute a command'))
        self.assertIn('set',self.personal.handle('Set a timer for five minutes',self.now))
        self.assertEqual(self.personal.due(self.now.timestamp()+299),[])
        self.assertEqual(self.personal.due(self.now.timestamp()+300),['Your timer is finished.'])
        self.assertEqual(PersonalAssistant(self.path).due(self.now.timestamp()+301),[])

    def test_relative_reminder_and_cancel(self):
        self.assertIn('set',self.personal.handle('Remind me to drink water in twenty minutes',self.now))
        self.assertIn('drink water',self.personal.handle('List my reminders'))
        self.assertIn('cancelled',self.personal.handle('Cancel reminder 1'))
        self.assertEqual(self.personal.due(self.now.timestamp()+2000),[])

    def test_explicit_today_past_time_is_not_moved_to_tomorrow(self):
        self.assertIn('passed',self.personal.handle('Remind me to study at 9 AM today',self.now))
        self.assertEqual(self.personal.state['alerts'],[])
        self.assertIn('set',self.personal.handle('Remind me to study at nine PM today',self.now))
        self.assertEqual(datetime.fromtimestamp(self.personal.state['alerts'][0]['due'],timezone.utc).hour,21)

    def test_write_failure_rolls_back_unacknowledged_action(self):
        with patch.object(self.personal,'save',side_effect=OSError('no access')):
            self.assertIn('could not save',self.personal.handle('Remember that private note'))
        self.assertEqual(self.personal.state['notes'],[])

    def test_personal_commands_bypass_both_model_providers(self):
        router=BrainRouter();router.mode='cloud'
        with patch.object(router,'cloud_answer') as cloud,patch.object(desktop,'build_opener') as local:
            answer,_=desktop.ask_ollama([],'Remember that I like tea',personal=self.personal,router=router)
            cloud.assert_not_called();local.assert_not_called()
        self.assertIn('Saved note',answer)
        self.assertEqual(router.last_provider,'personal')

    def test_bad_data_is_not_overwritten(self):
        self.path.write_text('{"notes":[{}],"todos":[],"alerts":[]}')
        with self.assertRaises(RuntimeError):PersonalAssistant(self.path)
        self.assertIn('{}',self.path.read_text())


if __name__=='__main__':unittest.main()
