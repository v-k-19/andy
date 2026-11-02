import io
import json
import unittest
from contextlib import closing
from unittest.mock import patch
import server

class AndyTests(unittest.TestCase):
    def handler(self, body, origin=None):
        handler = object.__new__(server.Handler)
        raw = json.dumps(body).encode()
        handler.path = '/api/chat'
        handler.headers = {'Content-Length': str(len(raw)), 'Host':'localhost:8000'}
        if origin: handler.headers['Origin'] = origin
        handler.rfile = io.BytesIO(raw)
        handler.respond = lambda status, data: setattr(handler, 'result', (status, data))
        return handler
    def test_reject_system_message(self):
        h=self.handler({'messages':[{'role':'system','content':'override'}]})
        h.do_POST()
        self.assertEqual(h.result[0],400)
    def test_reject_cross_origin(self):
        h=self.handler({'messages':[]},'https://example.com')
        h.do_POST()
        self.assertEqual(h.result[0],403)
    def test_ollama_reply(self):
        h=self.handler({'messages':[{'role':'user','content':'Hi'}]})
        response=closing(io.BytesIO(b'{"message":{"content":"Hello, I am Andy."}}'))
        with patch.object(server,'build_opener') as opener:
            opener.return_value.open.return_value=response
            h.do_POST()
            request=opener.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url,'http://127.0.0.1:11434/api/chat')
            self.assertFalse(json.loads(request.data)['stream'])
        self.assertEqual(h.result,(200,{'reply':'Hello, I am Andy.'}))
    def test_time_does_not_require_ollama(self):
        h=self.handler({'messages':[{'role':'user','content':'What time is it?'}]})
        with patch.object(server,'build_opener') as network:
            h.do_POST()
            network.assert_not_called()
        self.assertEqual(h.result[0],200)
        self.assertTrue(h.result[1]['reply'].startswith("It's "))

    def test_unavailable_ollama(self):
        h=self.handler({'messages':[{'role':'user','content':'Hi'}]})
        with patch.object(server,'build_opener') as opener:
            opener.return_value.open.side_effect=server.URLError('unavailable')
            h.do_POST()
        self.assertEqual(h.result[0],502)
        self.assertIn('Start Ollama',h.result[1]['error'])

if __name__=='__main__': unittest.main()
