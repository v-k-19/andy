# Andy — voice-only personal AI with Ollama

Talk to Andy through your microphone and hear spoken replies. No typed chat or transcript. Conversations live only in server-request/browser memory and disappear on reload or New conversation. No API key is needed.

## Start on your computer

On **Arch Linux**, install the tools and start Ollama:

```bash
sudo pacman -Syu git python ollama
sudo systemctl enable --now ollama
```

Download Andy and the model:

```bash
git clone https://github.com/v-k-19/andy.git
cd andy
ollama pull qwen2.5:14b
python3 server.py
```

Open http://127.0.0.1:8000 in Chrome or Edge, allow microphone access, and click **Enable “Andy” wake word**. Keep the terminal open while using Andy.

### Other operating systems

Install Python 3.10+ and [Ollama](https://ollama.com), then:

```bash
ollama pull qwen2.5:14b
ollama serve
```

If Ollama is already running, skip `ollama serve`. In a separate terminal:

```bash
git clone https://github.com/v-k-19/andy.git
cd andy
python3 server.py
```

Open http://127.0.0.1:8000 in Chrome or Edge. Allow microphone access. Tap the orb, speak, then tap again to finish. Andy responds aloud. Tap the orb to interrupt and speak again, or use Stop speaking. New conversation clears context.

## Wake word

Click **Enable “Andy” wake word**, allow microphone access, then say “Andy, help me plan my day.” Pause after your question to send it. Andy speaks the reply and resumes wake-word listening. Say “Andy” alone, then ask your question within eight seconds. Disable wake word to end continuous listening. Recognition pauses during Andy’s spoken response to prevent self-triggering.

This is browser speech recognition matching the word Andy, not an offline keyword detector. While enabled, microphone audio may be processed by the browser vendor even before the wake word. It works only while this page remains open and the browser permits microphone use; it is not a system-wide or guaranteed background assistant.

## Configuration

`ANDY_MODEL` defaults to `qwen2.5:14b`. `OLLAMA_URL` defaults to `http://127.0.0.1:11434`; set it server-side if Ollama runs elsewhere. `PORT` defaults to `8000`. Set environment variables before starting; `.env` is not loaded automatically. Python 3.10+ and Node for JavaScript syntax checks; no application dependencies.

Ollama must be reachable from the machine running Python. Run Andy alongside Ollama on your computer, or configure a reachable Ollama server.

## Voice and privacy

AI inference runs on your configured Ollama server. Browser speech recognition may send microphone audio to the browser vendor and may require internet access. Browser speech synthesis uses the device's available voices; some may be remote. This is not a fully offline speech pipeline. Microphone access requires localhost or HTTPS and browser support. No recordings, transcript files, or conversations are persisted by Andy. The app does not browse, access files, or run background actions.

The Python server is for local single-user use and binds to loopback. No authentication is included; do not expose it publicly.

## Checks

```bash
python3 -m unittest discover -s tests -v
node --check static/app.js
```
