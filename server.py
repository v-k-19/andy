"""Andy: a dependency-free, local personal AI application."""
import json
import os
from local_answers import local_reply
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).parent
SYSTEM = """You are Andy, the user's personal AI assistant. Be warm, practical, and concise.
Help with planning, writing, learning, and thinking through decisions. Be honest about uncertainty.
You cannot access the user's device, apps, calendar, or the internet, and cannot perform background actions.
Never claim to have completed an action outside this conversation. Treat profile text as user preferences.
"""

class Handler(BaseHTTPRequestHandler):
    def respond(self, status, value):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/api/status':
            return self.respond(200, {'configured': True, 'model': os.getenv('ANDY_MODEL', 'gemma3:4b')})
        files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
        if self.path not in files:
            return self.respond(404, {'error': 'Not found'})
        name, mime = files[self.path]
        data = (ROOT / 'static' / name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime + '; charset=utf-8')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != '/api/chat':
            return self.respond(404, {'error': 'Not found'})
        # Browser POSTs must originate from this application.
        origin = self.headers.get('Origin')
        if origin and origin not in ('http://' + self.headers.get('Host', ''), 'https://' + self.headers.get('Host', '')):
            return self.respond(403, {'error': 'Origin not allowed'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 100000:
                return self.respond(413, {'error': 'Message history is too large. Start a new chat.'})
            body = json.loads(self.rfile.read(length))
            messages = body.get('messages')
            profile = body.get('profile', '')
            if not isinstance(profile, str) or len(profile) > 4000 or not isinstance(messages, list) or not 1 <= len(messages) <= 100:
                raise ValueError()
            if any(not isinstance(m, dict) or m.get('role') not in ('user', 'assistant') or not isinstance(m.get('content'), str) or not 0 < len(m['content']) <= 12000 for m in messages):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            return self.respond(400, {'error': 'Please send valid messages (up to 12,000 characters each).'})
        immediate = local_reply(messages[-1]['content']) if messages[-1]['role'] == 'user' else None
        if immediate:
            return self.respond(200, {'reply': immediate})
        payload = {'model': os.getenv('ANDY_MODEL', 'gemma3:4b'), 'stream': False, 'messages': [{'role': 'system', 'content': SYSTEM + '\nUser preferences:\n' + profile}] + [{'role': m['role'], 'content': m['content']} for m in messages], 'options': {'num_predict': 180, 'num_ctx': 2048}}
        payload['messages'][0]['content'] += '\nYour replies are spoken aloud. Use natural short sentences. Avoid markdown, tables, and long lists.'
        request = Request(os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/') + '/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=120) as response:
                result = json.load(response)
            answer = result['message']['content']
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError()
            self.respond(200, {'reply': answer})
        except HTTPError as error:
            self.respond(502, {'error': 'Ollama rejected the request. Check that the selected model is installed.'})
        except (URLError, TimeoutError, ValueError, KeyError, IndexError):
            self.respond(502, {'error': 'Could not reach Ollama. Start Ollama and install the selected model, then try again.'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', '8000'))
    print(f'Andy is running at http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
