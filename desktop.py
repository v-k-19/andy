"""Native, offline-voice Andy. Launch with .venv/bin/python desktop.py."""
import json
from datetime import datetime
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
from local_answers import local_reply
from speech_input import SpeechInput, speech_voice
from urllib.error import HTTPError, URLError
from urllib.request import Request, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent
MODEL_NAME = os.getenv('ANDY_MODEL', 'gemma3:4b')
VOICE_MODEL = Path(os.getenv('ANDY_VOICE_MODEL', str(ROOT / 'models' / 'vosk-model-small-en-us-0.15')))
PROMPT = ('You are Andy, a practical personal AI voice assistant. Understand natural English, '
          'Telugu, and mixed English/Telugu speech. Reply in the language the user is using; '
          'use Telugu script for Telugu replies. Follow the recent conversation to resolve '
          'follow-up questions. If the meaning is unclear, ask one short clarifying question '
          'instead of inventing what the user meant. Be conversational and concise, usually '
          'one to three short sentences unless more detail is requested. Use natural spoken language with no markdown. '
          'Be honest about uncertainty and corrections. You can answer time and date from '
          'the computer clock, but cannot browse, access apps or files, or perform actions '
          'outside this conversation.')


def is_wake_word(text):
    return bool(re.search(r'\b(?:andy|andi|andie)\b', text, re.IGNORECASE))


def ask_ollama(history, text, on_sentence=None, stop=None):
    if stop and stop.is_set():
        return '', history
    messages = (history + [{'role': 'user', 'content': text}])[-12:]
    immediate = local_reply(text)
    if immediate:
        if on_sentence and not (stop and stop.is_set()):
            on_sentence(immediate)
        return immediate, messages + [{'role': 'assistant', 'content': immediate}]
    payload = {'model': MODEL_NAME, 'stream': True, 'keep_alive': '30m',
               'messages': [{'role': 'system', 'content': PROMPT + '\nCurrent computer local time and date: ' + datetime.now().astimezone().isoformat(timespec='minutes')}] + messages,
               'options': {'num_predict': 180, 'num_ctx': 2048}}
    req = Request(os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/') + '/api/chat',
                  data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
    answer, pending, completed = '', '', False
    try:
        with build_opener(ProxyHandler({})).open(req, timeout=180) as response:
            for line in response:
                if stop and stop.is_set():
                    return '', history
                if not line.strip():
                    continue
                part = json.loads(line)
                if part.get('error'):
                    raise ValueError('Ollama could not finish the answer')
                chunk = part.get('message', {}).get('content', '')
                if not isinstance(chunk, str):
                    raise ValueError('Invalid response')
                answer += chunk
                pending += chunk
                if on_sentence:
                    while True:
                        boundary = re.search(r'(?<=[.!?])\s+', pending)
                        if boundary:
                            sentence, pending = pending[:boundary.start()], pending[boundary.end():]
                        elif len(pending) > 220 and ' ' in pending:
                            boundary_index = pending.rfind(' ', 0, 220)
                            if boundary_index <= 0:
                                break
                            sentence, pending = pending[:boundary_index], pending[boundary_index + 1:]
                        else:
                            break
                        if stop and stop.is_set():
                            return '', history
                        if sentence.strip():
                            on_sentence(sentence.strip())
                if part.get('done'):
                    completed = True
                    break
        if not completed or not answer.strip():
            raise ValueError('Incomplete reply')
        if on_sentence and pending.strip() and not (stop and stop.is_set()):
            on_sentence(pending.strip())
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
            self.speaker = subprocess.Popen(['espeak-ng', '-v', speech_voice(text), '-s', '165', '--stdin'],
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
            self.emit('Loading multilingual speech…', 'Preparing local English and Telugu recognition.')
            speech = SpeechInput()
            device = os.getenv('ANDY_INPUT_DEVICE')
            if device and device.isdecimal():
                device = int(device)
            rate = int(sd.query_devices(device, 'input')['default_samplerate'])
            # A small grammar recognizes the name locally before enabling free-form dictation.
            wake = KaldiRecognizer(model, rate, json.dumps(['andy', 'hey andy', '[unk]']))
            command = KaldiRecognizer(model, rate)
            waiting = True
            deadline = 0
            recorded = bytearray()
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
                        recorded.clear()
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
                            recorded.clear()
                            waiting = False
                            deadline = time.monotonic() + 30
                            self.emit('Listening to your question…', 'Speak in English or Telugu; pause when finished.')
                    else:
                        recorded.extend(data)
                        # Vosk supplies only the speech endpoint here, not the words.
                        if command.AcceptWaveform(data):
                            command.Result()
                            self.emit('Understanding your words…', 'Transcribing English or Telugu locally.')
                            transcript = speech.transcribe(bytes(recorded), rate)
                            recorded.clear()
                            if self.stop.is_set():
                                break
                            if not transcript.clear:
                                self.emit('Please say that again', 'The speech was unclear. Listening for another attempt.')
                                self.say('I did not catch that clearly. Please say it again.')
                                self.clear_audio()
                                command.Reset()
                                deadline = time.monotonic() + 30
                                continue
                            text = transcript.text
                            self.emit('Thinking…', 'Preparing a reply. Time and date use your computer clock.')
                            def speak_sentence(sentence):
                                self.emit('Andy is speaking', 'The microphone is ignored during playback.')
                                self.say(sentence)
                            try:
                                answer, updated_history = ask_ollama(
                                    self.history, text, on_sentence=speak_sentence, stop=self.stop)
                                if self.stop.is_set():
                                    break
                                self.history = updated_history
                            except RuntimeError as exc:
                                self.emit('Ollama unavailable', str(exc))
                                self.say('I could not reach the model. Please check Ollama. You can still ask me the time or date.')
                            self.clear_audio()
                            recorded.clear()
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
    import sys
    try:
        from PySide6.QtCore import Qt, QTimer, QPointF
        from PySide6.QtGui import QColor, QPainter, QPen, QFont, QAction
        from PySide6.QtWidgets import QApplication, QWidget, QMenu
    except ImportError:
        raise SystemExit('Desktop dependencies are missing. Run bash install-desktop.sh first.')
    from particle_orb import ParticleCloud

    class AndyWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle('Andy — Personal AI')
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAccessibleName('Andy voice assistant')
            self.setAccessibleDescription('Transparent particle orb. Click or press Space to start or pause. Right-click for controls. Escape closes Andy.')
            self.resize(420, 460)
            self.setMinimumSize(260, 300)
            self.setMouseTracking(True)
            self.cloud = ParticleCloud()
            self.started_at = time.monotonic()
            self.mode = 'idle'
            self.heading = 'Click to start Andy'
            self.detail = 'Drag to move · Right-click for controls'
            self.events = queue.Queue()
            self.worker = None
            self.thread = None
            self.token = 0
            self.hovered = False
            self.drag_origin = None
            self.drag_position = None
            self.dragged = False
            self.menu_open = False
            self.animation = QTimer(self)
            self.animation.timeout.connect(self.update)
            self.animation.start(40)
            self.event_timer = QTimer(self)
            self.event_timer.timeout.connect(self.poll)
            self.event_timer.start(100)
            self.setToolTip(self.heading + '\n' + self.detail)

        def start(self):
            if self.thread and self.thread.is_alive():
                return
            self.token += 1
            self.worker = VoiceWorker(self.events, self.token, threading.Event())
            self.thread = threading.Thread(target=self.worker.run, daemon=True)
            self.mode = 'thinking'
            self.heading = 'Loading Andy…'
            self.detail = 'Local voice recognition is starting.'
            self.thread.start()
            self.update()

        def pause(self):
            self.token += 1
            if self.worker:
                self.worker.cancel()
            self.mode = 'paused'
            self.heading = 'Paused · microphone off'
            self.detail = 'Click to restart. An active Ollama request must finish first.'
            self.setToolTip(self.heading + '\n' + self.detail)
            self.update()

        def toggle(self):
            if self.mode in ('idle', 'paused'):
                if self.thread and self.thread.is_alive():
                    self.heading = 'Finishing the previous request…'
                    self.detail = 'Ollama may take up to three minutes. Then click again.'
                    self.update()
                else:
                    self.start()
            else:
                self.pause()

        def poll(self):
            while True:
                try:
                    token, heading, detail = self.events.get_nowait()
                except queue.Empty:
                    break
                if token != self.token:
                    continue
                if heading == '__finished__':
                    self.mode = 'idle'
                    continue
                self.heading, self.detail = heading, detail
                if heading.startswith('Say'):
                    self.mode = 'waiting'
                elif heading.startswith('Listening'):
                    self.mode = 'listening'
                elif heading in ('Andy is speaking', 'I heard you'):
                    self.mode = 'speaking'
                elif heading.startswith(('Thinking', 'Loading', 'Understanding')):
                    self.mode = 'thinking'
                else:
                    self.mode = 'idle'
                self.setToolTip(self.heading + '\n' + self.detail)
            # Animation state describes the voice phase, not measured microphone volume.

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # No background is painted; the desktop remains visible between particles.
            width, height = self.width(), self.height()
            radius = min(width * .32, (height - 90) * .34)
            center = QPointF(width / 2, (height - 45) / 2)
            elapsed = time.monotonic() - self.started_at
            pen = QPen()
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            for x, y, size, rgba in self.cloud.frame(elapsed, self.mode):
                pen.setColor(QColor(*rgba))
                pen.setWidthF(size * max(.7, radius / 125))
                painter.setPen(pen)
                painter.drawPoint(QPointF(center.x() + x * radius, center.y() + y * radius))
            if self.hovered or self.menu_open or self.mode in ('idle', 'paused'):
                painter.setPen(QColor(188, 205, 242, 230))
                painter.setFont(QFont('Sans', 10))
                painter.drawText(12, height - 65, width - 24, 26,
                                 Qt.AlignmentFlag.AlignHCenter, self.heading)
                painter.setPen(QColor(144, 161, 198, 210))
                painter.setFont(QFont('Sans', 8))
                painter.drawText(16, height - 38, width - 32, 34,
                                 Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap,
                                 self.detail)
            painter.end()

        def enterEvent(self, event):
            self.hovered = True
            self.update()
            super().enterEvent(event)

        def leaveEvent(self, event):
            self.hovered = False
            self.update()
            super().leaveEvent(event)

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_origin = event.globalPosition().toPoint()
                self.drag_position = self.pos()
                self.dragged = False

        def mouseMoveEvent(self, event):
            if self.drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
                delta = event.globalPosition().toPoint() - self.drag_origin
                if delta.manhattanLength() > QApplication.startDragDistance():
                    self.dragged = True
                if self.dragged:
                    handle = self.windowHandle()
                    if handle and handle.startSystemMove():
                        self.drag_origin = None
                    else:
                        self.move(self.drag_position + delta)

        def mouseReleaseEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                if self.drag_origin is not None and not self.dragged:
                    self.toggle()
                self.drag_origin = None

        def contextMenuEvent(self, event):
            self.menu_open = True
            menu = QMenu(self)
            running = bool(self.thread and self.thread.is_alive())
            start_action = QAction('Start listening', self)
            start_action.setEnabled(not running)
            start_action.triggered.connect(self.start)
            menu.addAction(start_action)
            pause_action = QAction('Pause / Stop speech', self)
            pause_action.setEnabled(running and self.mode != 'paused')
            pause_action.triggered.connect(self.pause)
            menu.addAction(pause_action)
            menu.addSeparator()
            menu.addAction('Quit Andy', self.close)
            menu.exec(event.globalPos())
            self.menu_open = False
            menu.deleteLater()
            start_action.deleteLater()
            pause_action.deleteLater()
            self.update()

        def keyPressEvent(self, event):
            if event.key() == Qt.Key.Key_Space:
                self.toggle()
            elif event.key() == Qt.Key.Key_Escape:
                self.close()
            else:
                super().keyPressEvent(event)

        def changeEvent(self, event):
            # Keep wake-word recognition running while minimized, but stop rendering.
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.Type.WindowStateChange:
                if self.isMinimized():
                    self.animation.stop()
                else:
                    self.animation.start(40)
            super().changeEvent(event)

        def closeEvent(self, event):
            self.animation.stop()
            self.event_timer.stop()
            if self.worker:
                self.worker.cancel()
            event.accept()

    app = QApplication(sys.argv)
    app.setApplicationName('Andy')
    window = AndyWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
