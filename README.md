# Andy — personal voice AI for your PC

Andy runs as a **native desktop app** on Arch Linux. Say **“Andy”**, wait for **“Yes?”**, then ask your question. Andy answers aloud using Ollama. No browser, API key, or cloud speech service is required for the desktop app.

## Install on Arch Linux

Install the system dependencies and start Ollama:

```bash
sudo pacman -Syu git python python-pip tk portaudio espeak-ng ollama
sudo systemctl enable --now ollama
```

Download the project:

```bash
git clone https://github.com/v-k-19/andy.git
cd andy
```

If you already cloned Andy, open its folder and update it instead:

```bash
git pull --ff-only
```

Install the local voice dependencies and download the English speech model:

```bash
bash install-desktop.sh
ollama pull qwen2.5:14b
```

The installer creates a virtual environment, downloads the official Vosk small English voice model (about 40 MB), and adds **Andy** to your application menu. Model weights and dependencies are downloaded once; internet access is required for installation.

## Talk to Andy

Launch **Andy** from your application menu, or run this inside the project folder:

```bash
.venv/bin/python desktop.py
```

1. Click **Start listening**.
2. Say **“Andy”** and wait for the spoken **“Yes?”**.
3. Ask your question in English, then pause to finish.
4. Andy generates a reply through Ollama, speaks it, and returns to waiting for its name.

Use **Pause / Stop** to close the microphone and stop speech. Starting again begins a fresh conversation. An in-progress Ollama request may take up to three minutes to finish before the Start button becomes available. Closing the app exits it. The app must remain running to hear the wake word; it can be minimized and does not depend on browser focus. It does not automatically start when you log in.

Wake-word detection uses a constrained local Vosk recognizer. This is speech recognition tuned to Andy’s name, not a custom-trained keyword model; accuracy still depends on microphone quality, noise, and pronunciation. Pause between the name and your question. Audio collected during Andy’s speech or model inference is discarded to avoid self-triggering. You can stop playback with **Pause / Stop**; voice interruption during playback is not supported.

## Model and voice

- **AI:** `qwen2.5:14b` by default. Suitable to try with 32 GB RAM, but CPU speed and available memory determine latency. No model can reliably answer every question.
- **Speech recognition:** Vosk small English, running locally. Other languages are not configured.
- **Spoken output:** local eSpeak NG; its voice is basic rather than a natural neural voice.

For faster CPU responses, try a smaller model:

```bash
ollama pull qwen2.5:7b
ANDY_MODEL=qwen2.5:7b .venv/bin/python desktop.py
```

## Troubleshooting

- **Microphone error:** check your input device in the desktop sound settings. List available devices with `.venv/bin/python -m sounddevice`. Select one with `ANDY_INPUT_DEVICE=DEVICE_NUMBER .venv/bin/python desktop.py`.
- **Ollama cannot answer:** run `ollama list` and `systemctl status ollama`. Confirm the configured model is installed.
- **No speech:** test `espeak-ng "Hello from Andy"` and check your sound output.
- **Andy misses its name:** try a quiet room, move closer to the microphone, and say “Hey Andy” distinctly. Wait for “Yes?” before the question.
- **No display:** the native window needs an active graphical desktop session. Run as your normal desktop user, not with sudo.
- **App menu shortcut stops working:** rerun `bash install-desktop.sh` after moving the project directory.

## Configuration and privacy

Set variables before launching; `.env` files are not loaded automatically. Optional names are documented in `.env.example`:

- `ANDY_MODEL`: Ollama model name.
- `OLLAMA_URL`: defaults to `http://127.0.0.1:11434`. If changed to a remote server, your questions and conversation context go to that server.
- `ANDY_VOICE_MODEL`: absolute path to a compatible Vosk English voice model directory.
- `ANDY_INPUT_DEVICE`: input device index or name.

Andy keeps conversation context and temporary audio buffers in memory. It does not save recordings or transcripts. With default local Ollama, speech and questions stay on your computer after installation. It cannot browse, access your files/apps, schedule reminders, or perform background actions outside the running assistant.

## Legacy browser version

The earlier browser app remains available with `python3 server.py`, then http://127.0.0.1:8000. It uses browser speech recognition, which may use an online service. Use `desktop.py` for native local voice operation.

## Checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile desktop.py download_voice_model.py server.py
bash -n install-desktop.sh
node --check static/app.js
```

Automated tests mock the microphone and Ollama. Physical microphone recognition, desktop audio, and live model speed need testing on your computer.
