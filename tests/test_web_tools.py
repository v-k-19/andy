import io
import json
from email.message import Message
import unittest
from unittest.mock import Mock,patch
from contextlib import closing
import desktop
from live_information import LiveInformation
from web_tools import WebTools,PageText,public_url,PublicRedirect,read_page


class WebTests(unittest.TestCase):
    def test_private_urls_and_credentials_are_rejected(self):
        for url in ['file:///etc/hosts','http://localhost/','http://127.0.0.1/','http://192.168.1.1/','http://[::1]/','https://user:password@example.com','https://example.com:11434/']:
            with self.assertRaises(ValueError):public_url(url)

    def test_dns_private_address_is_rejected(self):
        with patch('web_tools.socket.getaddrinfo',return_value=[(None,None,None,None,('10.0.0.1',443))]):
            with self.assertRaises(ValueError):public_url('https://example.com',resolve=True)

    def test_page_parser_removes_scripts_and_navigation(self):
        parser=PageText();parser.feed('<nav>Navigation</nav><script>hidden()</script><article><h1>Title</h1><p>Useful paragraph.</p></article>')
        result=' '.join(parser.parts)
        self.assertIn('Useful paragraph.',result)
        self.assertNotIn('hidden()',result)
        self.assertNotIn('Navigation',result)

    def test_search_returns_evidence_and_citable_sources(self):
        module=Mock();module.DDGS.return_value.text.return_value=[{'title':'Example','href':'https://example.com','body':'A supported fact.'}]
        web=WebTools()
        with patch.dict('sys.modules',{'ddgs':module}):result=web.handle('Could you search the web for a supported fact?')
        self.assertEqual(result.evidence[0]['text'],'A supported fact.')
        self.assertEqual(web.sources,[('Example','https://example.com')])
        self.assertIsNone(result.answer)

    def test_no_results_does_not_trigger_unverified_answer(self):
        module=Mock();module.DDGS.return_value.text.return_value=[]
        with patch.dict('sys.modules',{'ddgs':module}):result=WebTools().handle('Search for an obscure topic')
        self.assertFalse(result.evidence)
        self.assertIn('could not find',result.answer)

    def test_explicit_web_search_is_not_misrouted_as_weather(self):
        info=LiveInformation()
        module=Mock();module.DDGS.return_value.text.return_value=[{'title':'Weather science','href':'https://example.com','body':'A weather research page.'}]
        with patch.dict('sys.modules',{'ddgs':module}),patch.object(info,'weather') as weather:
            info.answer('Search the web for weather science')
            weather.assert_not_called()
        self.assertTrue(info.evidence)

    def test_read_first_result_uses_previous_search(self):
        web=WebTools();web.results=[{'title':'Example','url':'https://example.com','text':'Snippet'}]
        with patch('web_tools.read_page',return_value='Full readable source passage.'):
            result=web.handle('Read the first result')
        self.assertEqual(result.evidence[0]['text'],'Full readable source passage.')

    def test_model_receives_evidence_as_user_data_not_system_instruction(self):
        info=LiveInformation()
        module=Mock();module.DDGS.return_value.text.return_value=[{'title':'Example','href':'https://example.com','body':'Source passage.'}]
        stream=closing(io.BytesIO(b'{"message":{"content":"According to Example, a fact."},"done":true}\n'))
        with patch.dict('sys.modules',{'ddgs':module}),patch.object(desktop,'build_opener') as model:
            model.return_value.open.return_value=stream
            desktop.ask_ollama([], 'Search the web for a fact',information=info)
            sent=json.loads(model.return_value.open.call_args.args[0].data)
        data=json.loads(sent['messages'][-1]['content'])
        self.assertEqual(data['retrieved_source_data'][0]['text'],'Source passage.')
        self.assertNotIn('Source passage.',sent['messages'][0]['content'])
        self.assertIn('untrusted data',sent['messages'][0]['content'])


if __name__=='__main__':unittest.main()
