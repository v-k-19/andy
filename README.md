# Andy — personal voice AI for your PC

Andy runs as a **native desktop app** on Arch Linux. Say **“Andy”**, wait for **“Yes?”**, then ask your question. Andy answers aloud using Ollama. No browser, API key, or cloud speech service is required for the desktop app.

## Install on Arch Linux

Install the system dependencies and start Ollama:

```bash
sudo pacman -Syu git python python-pip portaudio espeak-ng ollama
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
ollama pull gemma3:4b
```

The installer creates a virtual environment, downloads the official Vosk English wake-word model (about 40 MB) and multilingual Whisper small model (roughly 500 MB), and adds **Andy** to your application menu. Model weights and dependencies are downloaded once; internet access is required for installation.

## Transparent particle orb

Andy appears as a frameless, transparent native window: a blue-white particle cloud slowly folds and rotates over your desktop. There is no painted background or browser. The particles pulse differently during listening, thinking, and speaking; this indicates the current state, rather than measured audio amplitude.

- **Click the orb / press Space:** start or pause listening.
- **Drag:** move Andy around your desktop.
- **Right-click:** Start listening, Pause / Stop speech, or Quit Andy.
- **Escape:** close Andy when the window has keyboard focus.
- **Hover:** show the current status. Setup and error messages also appear while idle.

Window transparency needs a desktop compositor. Most current Wayland desktops provide one; X11 window managers may need compositing enabled. Rendering pauses when minimized while wake-word recognition continues. Animation runs at up to 25 frames per second to limit CPU use alongside Ollama.

## Talk to Andy

Launch **Andy** from your application menu, or run this inside the project folder:

```bash
.venv/bin/python desktop.py
```

1. Click the orb, or right-click it and choose **Start listening**.
2. Say **“Andy”** and wait for the spoken **“Yes?”**.
3. Ask your question in English or Telugu, then pause to finish.
4. Andy generates a reply through Ollama, speaks it, and returns to waiting for its name.

Click the active orb or use **Pause / Stop speech** in its right-click menu to close the microphone and stop speech. Starting again begins a fresh conversation. An in-progress Ollama request may take up to three minutes to finish before listening can restart. Closing the app exits it. The app must remain running to hear the wake word; it can be minimized and does not depend on browser focus. It does not automatically start when you log in.

Wake-word detection uses a constrained local Vosk recognizer. This is speech recognition tuned to Andy’s name, not a custom-trained keyword model; accuracy still depends on microphone quality, noise, and pronunciation. Pause between the name and your question. Audio collected during Andy’s speech or model inference is discarded to avoid self-triggering. You can stop playback with **Pause / Stop speech**; voice interruption during playback is not supported.

## Model and voice

- **AI:** `gemma3:4b` by default, a compact multilingual Ollama model. Ollama 0.6 or later is required. Larger models can give better technical answers but are slower. No model can reliably answer every question.
- **Speech recognition:** Vosk hears the English name “Andy”; multilingual Whisper small transcribes questions locally using CPU int8. English and Telugu are accepted, with automatic language detection by default. Other detected languages and weak recognition prompt a repeat. Language detection can be unreliable for very short utterances or mixed speech.
- **Spoken output:** local eSpeak NG selects English (`en-us`) or Telugu (`te`) based on the reply’s script. It remains a basic synthetic voice, not a humanlike neural voice; words from the other language in a mixed sentence may sound imperfect.

For more detailed technical answers, you can explicitly select the slower, larger model:

```bash
ollama pull qwen2.5:14b
ANDY_MODEL=qwen2.5:14b .venv/bin/python desktop.py
```

## Natural English and Telugu conversation

Whisper replaces the English-only word transcription used in earlier versions. It consumes in-memory audio and is configured for local CPU int8 inference. Speech models are downloaded during installation; the running app does not download them or send audio to a cloud service. Vosk is used for the wake word and for detecting the end of the utterance, not for the final question text.

Andy supplies recent conversation turns to the model, so you can ask a question and follow with “give me an example” or “explain that more simply.” It is instructed to reply in your language and clarify ambiguous meaning. These are model behaviors, not guarantees: Whisper may still mishear accents, and model replies can be wrong. The “unclear speech” check uses recognition confidence heuristics, not a verified understanding of what you intended.

Automatic language detection is the default. For more reliable single-language recognition, run:

```bash
ANDY_SPEECH_LANGUAGE=te .venv/bin/python desktop.py
# Or use ANDY_SPEECH_LANGUAGE=en for English.
```

To try faster recognition with lower potential accuracy, download the multilingual base model and launch it explicitly:

```bash
ANDY_SPEECH_MODEL=base .venv/bin/python download_speech_model.py
ANDY_SPEECH_MODEL=base .venv/bin/python desktop.py
```

Small multilingual recognition adds CPU work, so it may take longer than the earlier English-only recognizer. No live accent-accuracy or speed measurements have been made on your computer. Text is kept in memory only. Telugu-script output is sent to eSpeak’s Telugu voice; verify it with `espeak-ng --voices=te`.

Sources: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Gemma 3 on Ollama](https://ollama.com/library/gemma3), [eSpeak languages](https://github.com/espeak-ng/espeak-ng/blob/master/docs/languages.md).

## Fast everyday answers

Ask “What time is it?”, “What is today’s date?”, or “What day is it?”. Andy answers directly from your computer’s local clock without loading or calling Ollama. Common Telugu variants such as “ఇప్పుడు టైమ్ ఎంత?” also use the local clock. These answers work even if Ollama is unavailable; local voice dependencies must still be installed. For correct local time, verify your PC’s clock and timezone with `timedatectl`.

For other questions the desktop app streams Ollama’s reply and speaks sentences as they arrive, rather than waiting for the whole answer. Context is limited to the latest 12 messages, model context to 2,048 tokens, and output to 180 tokens to reduce CPU latency. Answers are brief by default. Ollama is asked to keep the model loaded for 30 minutes after use; the first question after a cold start may still take longer. Model failures return Andy to wake-word listening instead of ending the voice session.

To update from the earlier slow configuration, close Andy, open your project folder, and run:

```bash
git pull --ff-only
bash install-desktop.sh
ollama stop qwen2.5:14b
ollama pull gemma3:4b
ANDY_MODEL=gemma3:4b .venv/bin/python desktop.py
```

Stopping the old model frees its memory without deleting it. If it is not running, skip the stop command. Actual response speed still depends on your CPU, memory pressure, question, and initial model loading.

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
- `ANDY_SPEECH_MODEL`: multilingual Whisper model size; defaults to `small`. Download it with `download_speech_model.py` before changing sizes.
- `ANDY_SPEECH_LANGUAGE`: `auto`, `en`, or `te`; defaults to `auto`.

Andy keeps conversation context and temporary audio buffers in memory. It does not save recordings or transcripts. With default local Ollama, speech and questions stay on your computer after installation. It cannot browse, access your files/apps, schedule reminders, or perform background actions outside the running assistant.

## Legacy browser version

The earlier browser app remains available with `python3 server.py`, then http://127.0.0.1:8000. It uses browser speech recognition, which may use an online service. Use `desktop.py` for native local voice operation.

## Checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile desktop.py particle_orb.py local_answers.py download_voice_model.py speech_input.py download_speech_model.py server.py
bash -n install-desktop.sh
node --check static/app.js
```

Automated tests mock the microphone and Ollama. Physical microphone recognition, desktop audio, and live model speed need testing on your computer.
