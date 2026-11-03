"""Explicit local/hybrid/cloud routing. No desktop actions are executed by a model."""
import json
import os
import re
from http.client import HTTPException
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

TECHNICAL = re.compile(r'\b(?:debug|debugging|code|coding|programming|python|javascript|typescript|rust|java|c\+\+|sql|linux|arch linux|git|docker|algorithm|equation|calculus|physics|engineering|compiler|traceback|stack trace|api|software|kernel|server|database|technical|cpu|gpu|processor|networking|ram|memory)\b', re.I)
FOLLOW_UP = re.compile(r'^(?:why|how so|explain (?:that|more)|give me an example|make (?:it|that) simpler|what about|and what|continue|go on)\b', re.I)


class CloudFailure(RuntimeError):
    def __init__(self, message, partial=False):
        super().__init__(message)
        self.partial = partial


class BrainRouter:
    def __init__(self):
        mode = os.getenv('ANDY_AI_MODE', 'hybrid')
        self.mode = mode if mode in ('local', 'hybrid', 'cloud') else 'local'
        self.reset()

    def reset(self):
        self.cloud_history = []
        self.last_provider = 'local'

    def choose(self, text):
        # Explicit spoken requests override mode for this question only.
        match = re.match(r'^(?:ask|use) (?:the )?(cloud|local)(?: ai| model)?(?: to)?[,:]?\s+(.+)$', text.strip(), re.I)
        if match:
            return match[1].lower(), match[2]
        if self.mode == 'local':
            return 'local', text
        if self.mode == 'cloud':
            return 'cloud', text
        if os.getenv('OPENAI_API_KEY') and (TECHNICAL.search(text) or (self.last_provider == 'cloud' and FOLLOW_UP.search(text))):
            return 'cloud', text
        return 'local', text

    def cloud_answer(self, text, system, on_sentence=None, stop=None):
        key = os.getenv('OPENAI_API_KEY', '').strip()
        if not key:
            raise CloudFailure('Cloud AI is not configured. Add your API key in Andy’s Cloud AI settings.')
        if stop and stop.is_set():
            return ''
        # Separate history prevents local notes, to-dos and personal commands
        # from being uploaded with later technical questions.
        history = self.cloud_history[-10:] + [{'role':'user', 'content':text}]
        payload = {'model':os.getenv('ANDY_CLOUD_MODEL','gpt-4.1-mini'),
                   'instructions':system, 'input':history, 'stream':True,
                   'store':False, 'max_output_tokens':900}
        request = Request('https://api.openai.com/v1/responses', data=json.dumps(payload).encode(),
                          headers={'Authorization':'Bearer ' + key, 'Content-Type':'application/json',
                                   'Accept':'text/event-stream'})
        answer, pending, completed = '', '', False
        try:
            with urlopen(request, timeout=60) as response:
                for line in response:
                    if stop and stop.is_set():
                        return ''
                    if not line.startswith(b'data:'):
                        continue
                    data = line[5:].strip()
                    if data == b'[DONE]':
                        break
                    event = json.loads(data)
                    kind = event.get('type')
                    if kind in ('error','response.failed','response.incomplete'):
                        raise ValueError('Cloud response incomplete')
                    if kind in ('response.output_text.delta','response.refusal.delta'):
                        chunk = event.get('delta','')
                        if not isinstance(chunk,str):
                            raise ValueError('Invalid text delta')
                        answer += chunk
                        pending += chunk
                        if on_sentence:
                            while True:
                                boundary = re.search(r'(?<=[.!?])\s+', pending)
                                if boundary:
                                    sentence, pending = pending[:boundary.start()], pending[boundary.end():]
                                elif len(pending) > 220:
                                    index = pending.rfind(' ',0,220)
                                    if index <= 0:
                                        break
                                    sentence, pending = pending[:index], pending[index+1:]
                                else:
                                    break
                                if stop and stop.is_set():
                                    return ''
                                if sentence.strip():
                                    on_sentence(sentence.strip())
                    if kind == 'response.completed':
                        completed = True
                        break
            if not completed or not answer.strip():
                raise ValueError('Incomplete response')
            if on_sentence and pending.strip() and not (stop and stop.is_set()):
                on_sentence(pending.strip())
        except HTTPError as exc:
            message = 'Cloud AI could not authenticate or access this model. Check your API key, model access, and API billing.' if exc.code in (400,401,403,404,429) else 'Cloud AI is temporarily unavailable.'
            raise CloudFailure(message, partial=bool(answer)) from exc
        except (OSError,HTTPException,ValueError,TypeError,KeyError) as exc:
            raise CloudFailure('Cloud AI could not complete the reply. Check your internet connection.', partial=bool(answer)) from exc
        if not (stop and stop.is_set()):
            self.cloud_history = (history + [{'role':'assistant','content':answer}])[-12:]
            self.last_provider = 'cloud'
        return answer
