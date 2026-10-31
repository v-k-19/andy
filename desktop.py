"""Native, offline-voice Andy. Launch with .venv/bin/python desktop.py."""
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent
MODEL_NAME = os.getenv('ANDY_MODEL', 'qwen2.5:14b')
VOICE_MODEL = Path(os.getenv('ANDY_VOICE_MODEL', str(ROOT / 'models' / 'vosk-model-small-en-us-0.15')))
PROMPT = ('You are Andy, a practical personal AI voice assistant. Reply in natural, concise '
          'spoken English without markdown. Be honest about uncertainty. You cannot browse, '
          'access apps or files, or perform actions outside this conversation.')


def is_wake_word(text):
    return bool(re.search(r'\b(?:andy|andi|andie)\b', text, re.IGNORECASE))


def ask_ollama(history, text):
    messages = (history + [{'role': 'user', 'content': text}])[-30:]
    payload = {'model': MODEL_NAME, 'stream': False,
               'messages': [{'role': 'system', 'content': PROMPT}] + messages,
               'options': {'num_predict': 350}}
    req = Request(os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/') + '/api/chat',
                  data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    try:
        with build_opener(ProxyHandler({})).open(req, timeout=180) as response:
            answer = json.load(response)['message']['content']
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError('Empty reply')
    except HTTPError as exc:
        raise RuntimeError('Ollama rejected the request. Check that the selected model is installed.') from exc
    except (URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError('Cannot get a reply from Ollama. Check that it is running and the model is installed.') from exc
    return answer, messages + [{'role': 'assistant', 'content': answer}]


class VoiceWorker:
    def __init__(self, events, token, stop):
        self.events, self.token, self.stop = events, token, stop
        self.audio = queue.Queue(maxsize=80)
        self.history = []
        self.speaker = None
        self.speaker_lock = threading.Lock()
        self.input_problem = threading.Event()
        self.stream = None

    def emit(self, title, detail=''):
        self.events.put((self.token, title, detail))

    def clear_audio(self):
        while True:
            try:
                self.audio.get_nowait()
            except queue.Empty:
                return

    def on_audio(self, data, frames, timing, status):
        if status:
            self.input_problem.set()
        try:
            self.audio.put_nowait(bytes(data))
        except queue.Full:
            self.input_problem.set()

    def cancel(self):
        self.stop.set()
        if self.stream:
            try:
                self.stream.abort()
                self.stream.close()
            except Exception:
                pass
        with self.speaker_lock:
            if self.speaker and self.speaker.poll() is None:
                self.speaker.terminate()

    def say(self, text):
        if self.stop.is_set():
            return
        with self.speaker_lock:
            if self.stop.is_set():
                return
            self.speaker = subprocess.Popen(['espeak-ng', '-v', 'en-us', '-s', '165', '--stdin'],
                                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL)
            process = self.speaker
        try:
            process.communicate(text.encode(), timeout=180)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise RuntimeError('Speech playback timed out. Check your audio output.')
        if not self.stop.is_set() and process.returncode:
            raise RuntimeError('Speech playback failed. Check your audio output.')

    def run(self):
        try:
            import sounddevice as sd
            from vosk import Model, KaldiRecognizer, SetLogLevel
            if not shutil.which('espeak-ng'):
                raise RuntimeError('Install espeak-ng first, then restart Andy.')
            if not VOICE_MODEL.is_dir():
                raise RuntimeError('The offline voice model is missing. Run install-desktop.sh first.')
            SetLogLevel(-1)
            self.emit('Loading local voice recognition…', 'Your microphone is not open yet.')
            model = Model(str(VOICE_MODEL))
            device = os.getenv('ANDY_INPUT_DEVICE')
            if device and device.isdecimal():
                device = int(device)
            rate = int(sd.query_devices(device, 'input')['default_samplerate'])
            # A small grammar recognizes the name locally before enabling free-form dictation.
            wake = KaldiRecognizer(model, rate, json.dumps(['andy', 'hey andy', '[unk]']))
            command = KaldiRecognizer(model, rate)
            waiting = True
            deadline = 0
            if self.stop.is_set():
                return
            self.stream = sd.RawInputStream(samplerate=rate, blocksize=int(rate / 5), device=device,
                                            dtype='int16', channels=1, callback=self.on_audio)
            with self.stream:
                self.emit('Say “Andy”', 'Wait for “Yes?” before asking your question.')
                while not self.stop.is_set():
                    if self.input_problem.is_set():
                        self.input_problem.clear()
                        self.emit('Audio input interrupted', 'Check your microphone or reduce other CPU-heavy work.')
                    if not waiting and time.monotonic() > deadline:
                        command.Reset()
                        waiting = True
                        wake.Reset()
                        self.emit('Say “Andy”', 'No question was heard. Ready when you are.')
                    try:
                        data = self.audio.get(timeout=.2)
                    except queue.Empty:
                        continue
                    if waiting:
                        final = wake.AcceptWaveform(data)
                        result = json.loads(wake.Result() if final else wake.PartialResult())
                        if is_wake_word(result.get('text', result.get('partial', ''))):
                            self.emit('I heard you', 'Wait for “Yes?”, then ask your question.')
                            self.say('Yes?')
                            self.clear_audio()
                            command.Reset()
                            waiting = False
                            deadline = time.monotonic() + 30
                            self.emit('Listening to your question…', 'Pause when you are finished. English speech is supported.')
                    else:
                        if command.AcceptWaveform(data):
                            text = json.loads(command.Result()).get('text', '').strip()
                            if not text:
                                continue
                            self.emit('Thinking…', 'Ollama is answering locally. A larger model can take a while.')
                            answer, updated_history = ask_ollama(self.history, text)
                            if self.stop.is_set():
                                break
                            self.history = updated_history
                            self.emit('Andy is speaking', 'The microphone is ignored during playback.')
                            self.say(answer)
                            self.clear_audio()
                            waiting = True
                            wake.Reset()
                            command.Reset()
                            self.emit('Say “Andy”', 'Ready for your next question.')
        except ImportError:
            self.emit('Setup needed', 'Run install-desktop.sh to install the voice dependencies.')
        except Exception as exc:
            # Do not print speech transcripts or conversation history.
            if not self.stop.is_set():
                self.emit('Andy stopped', str(exc))
        finally:
            self.events.put((self.token, '__finished__', ''))


def main():
    import tkinter as tk
    root = tk.Tk()
    root.title('Andy — Personal AI')
    root.geometry('540x480')
    root.minsize(430, 400)
    root.configure(bg='#f5f7ef')
    events = queue.Queue()
    current = {'worker': None, 'thread': None, 'token': 0}
    title = tk.StringVar(value='Your personal voice AI')
    detail = tk.StringVar(value='Click Start listening, then say “Andy”.')
    tk.Label(root, text='andy', font=('Sans', 48, 'bold'), bg='#f5f7ef', fg='#365c40').pack(pady=(35, 12))
    tk.Label(root, textvariable=title, font=('Sans', 17), bg='#f5f7ef', fg='#365c40').pack(pady=12)
    tk.Label(root, textvariable=detail, wraplength=410, font=('Sans', 11), bg='#f5f7ef', fg='#6b7e61').pack(padx=24, pady=12)
    controls = tk.Frame(root, bg='#f5f7ef')
    controls.pack(pady=20)

    def start():
        if current['thread'] and current['thread'].is_alive():
            return
        current['token'] += 1
        worker = VoiceWorker(events, current['token'], threading.Event())
        current['worker'] = worker
        current['thread'] = threading.Thread(target=worker.run, daemon=True)
        start_button.configure(state='disabled')
        pause_button.configure(state='normal')
        current['thread'].start()

    def pause():
        if current['worker']:
            current['token'] += 1
            current['worker'].cancel()
        title.set('Paused')
        detail.set('Microphone stopped. An in-progress Ollama request may take up to three minutes to finish before restarting.')
        pause_button.configure(state='disabled')

    def poll():
        while True:
            try:
                token, heading, body = events.get_nowait()
            except queue.Empty:
                break
            if token != current['token']:
                continue
            if heading != '__finished__':
                title.set(heading)
                detail.set(body)
        if current['thread'] and not current['thread'].is_alive():
            start_button.configure(state='normal')
            pause_button.configure(state='disabled')
        root.after(100, poll)

    def close():
        if current['worker']:
            current['worker'].cancel()
        root.destroy()

    start_button = tk.Button(controls, text='Start listening', command=start, padx=15, pady=9)
    start_button.pack(side='left', padx=8)
    pause_button = tk.Button(controls, text='Pause / Stop', command=pause, state='disabled', padx=15, pady=9)
    pause_button.pack(side='left', padx=8)
    tk.Label(root, text=f'Ollama · {MODEL_NAME}\nLocal voice recognition · No recordings saved',
             font=('Sans', 10), bg='#f5f7ef', fg='#8b987f').pack(pady=8)
    tk.Label(root, text='English voice · Keep this app running to use the wake word.\nPause and restart listening to begin a fresh conversation.',
             font=('Sans', 9), bg='#f5f7ef', fg='#8b987f').pack(pady=8)
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(100, poll)
    root.mainloop()


if __name__ == '__main__':
    main()
