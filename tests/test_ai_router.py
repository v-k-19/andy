import io
import json
import os
from contextlib import closing
from unittest.mock import patch, Mock
import unittest
from ai_router import BrainRouter,CloudFailure
import desktop


def response(*events):
    data=b''.join(b'data: '+json.dumps(event).encode()+b'\n\n' for event in events)
    return closing(io.BytesIO(data))


class RouterTests(unittest.TestCase):
    def test_hybrid_technical_and_local_override(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','ANDY_AI_MODE':'hybrid'}):
            router=BrainRouter()
            self.assertEqual(router.choose('Help me debug Python')[0],'cloud')
            self.assertEqual(router.choose('Tell me a joke')[0],'local')
            self.assertEqual(router.choose('ask local explain Python'),('local','explain Python'))
            router.last_provider='cloud'
            self.assertEqual(router.choose('give me an example')[0],'cloud')

    def test_missing_key_leaves_hybrid_local(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'','ANDY_AI_MODE':'hybrid'}):
            router=BrainRouter()
            self.assertEqual(router.choose('Explain Linux')[0],'local')
            with patch('ai_router.urlopen') as network:
                with self.assertRaises(CloudFailure):router.cloud_answer('Hello','system')
                network.assert_not_called()

    def test_separate_cloud_context_and_streaming(self):
        spoken=[]
        def stream():
            yield b'data: {"type":"response.output_text.delta","delta":"A CPU runs instructions. "}\n'
            self.assertEqual(spoken,['A CPU runs instructions.'])
            yield b'data: {"type":"response.output_text.delta","delta":"Here is an example."}\n'
            yield b'data: {"type":"response.completed"}\n'
        class Stream:
            def __enter__(self):return stream()
            def __exit__(self,*args):pass
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),patch('ai_router.urlopen',return_value=Stream()) as network:
            router=BrainRouter()
            answer=router.cloud_answer('Explain CPU','test system',spoken.append)
            request=network.call_args.args[0]
            sent=json.loads(request.data)
            self.assertFalse(sent['store'])
            self.assertEqual(request.full_url,'https://api.openai.com/v1/responses')
            self.assertEqual(sent['input'],[{'role':'user','content':'Explain CPU'}])
        self.assertEqual(spoken,['A CPU runs instructions.','Here is an example.'])
        self.assertEqual(router.cloud_history[-1]['content'],answer)

    def test_refusal_is_returned_without_local_retry(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),patch('ai_router.urlopen',return_value=response({'type':'response.refusal.delta','delta':'I cannot help with that request.'},{'type':'response.completed'})):
            router=BrainRouter()
            self.assertEqual(router.cloud_answer('A request','system'),'I cannot help with that request.')

    def test_personal_history_is_not_sent_to_cloud(self):
        private=[{'role':'user','content':'My private note is confidential'},{'role':'assistant','content':'Saved'}]
        information=Mock();information.answer.return_value=None;information.evidence=[]
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','ANDY_AI_MODE':'hybrid'}),patch('ai_router.urlopen',return_value=response({'type':'response.output_text.delta','delta':'A CPU processes instructions.'},{'type':'response.completed'})) as network:
            desktop.ask_ollama(private,'Explain a CPU',information=information,router=BrainRouter())
            self.assertNotIn('confidential',network.call_args.args[0].data.decode())

    def test_cloud_failure_falls_back_locally_without_repeating_actions(self):
        router=BrainRouter();router.mode='cloud'
        info=Mock();info.answer.return_value=None;info.evidence=[]
        tools=Mock();tools.handle.return_value=None
        notices=[]
        with patch.object(router,'cloud_answer',side_effect=CloudFailure('offline')),patch.object(desktop,'build_opener') as local:
            local.return_value.open.return_value=closing(io.BytesIO(b'{"message":{"content":"Local answer"},"done":true}\n'))
            answer,_=desktop.ask_ollama([],'Explain a CPU',information=info,tools=tools,router=router,notice=lambda *x:notices.append(x))
        self.assertEqual(answer,'Local answer')
        tools.handle.assert_called_once()
        self.assertEqual(router.last_provider,'local')
        self.assertTrue(any('local' in x[0] for x in notices))

    def test_partial_cloud_answer_is_not_silently_retried(self):
        router=BrainRouter();router.mode='cloud'
        info=Mock();info.answer.return_value=None;info.evidence=[]
        with patch.object(router,'cloud_answer',side_effect=CloudFailure('interrupted',partial=True)),patch.object(desktop,'build_opener') as local:
            with self.assertRaisesRegex(RuntimeError,'interrupted'):
                desktop.ask_ollama([],'Explain a CPU',information=info,router=router)
            local.assert_not_called()


if __name__=='__main__':unittest.main()
