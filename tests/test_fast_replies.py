from datetime import datetime, timezone
import io
import json
from contextlib import closing
import threading
import unittest
from unittest.mock import patch
import desktop
from local_answers import local_reply


class FastReplyTests(unittest.TestCase):
    def test_time_formats_clock_at_midnight_and_noon(self):
        self.assertEqual(local_reply('What time is it?', datetime(2026,11,2,0,7,tzinfo=timezone.utc)), "It's 12:07 a.m.")
        self.assertEqual(local_reply('Andy, tell me the time please', datetime(2026,11,2,12,5)), "It's 12:05 p.m.")

    def test_date_and_day_are_from_clock(self):
        now=datetime(2026,11,2,21,0)
        self.assertEqual(local_reply("What's today's date?",now),'Today is Monday, November 2, 2026.')
        self.assertEqual(local_reply('What day is it today?',now),'Today is Monday.')

    def test_telugu_clock_and_day_use_local_facts(self):
        now=datetime(2026,11,2,21,5)
        self.assertEqual(local_reply('ఇప్పుడు టైమ్ ఎంత?',now),'ఇప్పుడు రాత్రి 9:05.')
        self.assertEqual(local_reply('ఈరోజు ఏ రోజు',now),'ఈరోజు సోమవారం.')
        self.assertIsNone(local_reply('సమయం అంటే ఏమిటి?',now))

    def test_followup_keeps_previous_conversation(self):
        history=[{'role':'user','content':'Explain gravity'}, {'role':'assistant','content':'Gravity attracts masses.'}]
        with patch.object(desktop,'build_opener') as network:
            network.return_value.open.return_value=closing(io.BytesIO(b'{"message":{"content":"A falling apple is an example."},"done":true}\n'))
            desktop.ask_ollama(history,'Give me an example')
            sent=json.loads(network.return_value.open.call_args.args[0].data)
        self.assertEqual(sent['messages'][1:3],history)
        self.assertEqual(sent['messages'][-1]['content'],'Give me an example')

    def test_other_time_questions_are_not_misrouted(self):
        for question in ['What is time dilation?', 'What time is it in London?', 'What time did World War Two end?', 'How do I set the time?']:
            self.assertIsNone(local_reply(question))

    def test_clock_answer_never_contacts_ollama(self):
        spoken=[]
        with patch.object(desktop,'build_opener') as network:
            answer,history=desktop.ask_ollama([], 'What time is it?', on_sentence=spoken.append)
            network.assert_not_called()
        self.assertTrue(answer.startswith("It's "))
        self.assertEqual(spoken,[answer])
        self.assertEqual(history[-1]['content'],answer)

    def test_sentence_is_spoken_before_final_response_arrives(self):
        spoken=[]
        def chunks():
            yield b'{"message":{"content":"The CPU runs instructions. "},"done":false}\n'
            self.assertEqual(spoken,['The CPU runs instructions.'])
            yield b'{"message":{"content":"It is the main processor."},"done":true}\n'
        class Stream:
            def __enter__(self): return chunks()
            def __exit__(self,*args): pass
        with patch.object(desktop,'build_opener') as network:
            network.return_value.open.return_value=Stream()
            answer,_=desktop.ask_ollama([], 'Explain CPUs',on_sentence=spoken.append)
            payload=json.loads(network.return_value.open.call_args.args[0].data)
        self.assertEqual(spoken,['The CPU runs instructions.','It is the main processor.'])
        self.assertEqual(answer,'The CPU runs instructions. It is the main processor.')
        self.assertTrue(payload['stream'])
        self.assertEqual(payload['keep_alive'],'30m')

    def test_cancelled_stream_does_not_speak_or_add_history(self):
        stopped=threading.Event();stopped.set()
        with patch.object(desktop,'build_opener') as network:
            network.return_value.open.return_value=closing(io.BytesIO(b'{"message":{"content":"Hello."},"done":true}\n'))
            spoken=[]
            answer,history=desktop.ask_ollama([], 'Hello',on_sentence=spoken.append,stop=stopped)
        self.assertEqual((answer,history,spoken),('',[],[]))

    def test_long_unbroken_output_does_not_loop(self):
        content = 'x' * 250 + ' end'
        data = (json.dumps({'message': {'content':content}, 'done':True}) + '\n').encode()
        spoken=[]
        with patch.object(desktop,'build_opener') as network:
            network.return_value.open.return_value=closing(io.BytesIO(data))
            desktop.ask_ollama([], 'Hello', on_sentence=spoken.append)
        self.assertEqual(spoken,[content])

    def test_incomplete_stream_is_reported(self):
        with patch.object(desktop,'build_opener') as network:
            network.return_value.open.return_value=closing(io.BytesIO(b'{"message":{"content":"partial"},"done":false}\n'))
            with self.assertRaises(RuntimeError):desktop.ask_ollama([], 'Hello')


if __name__=='__main__':unittest.main()
