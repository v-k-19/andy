# Andy — personal voice AI for your PC

Andy is a native Arch Linux desktop assistant with a transparent blue-white particle orb. Speak in **English**, hear a **female English neural voice**, ask general questions through local Ollama, and get live weather or recent news from online sources.

## Install on Arch Linux

```bash
sudo pacman -Syu git python python-pip portaudio espeak-ng mpv ollama
sudo systemctl enable --now ollama
git clone https://github.com/v-k-19/andy.git
cd andy
bash install-desktop.sh
ollama pull gemma3:4b
.venv/bin/python desktop.py
```

The installer creates a virtual environment, downloads Vosk's small English wake-word model and multilingual Whisper small for local speech recognition, and adds Andy to your application menu. Downloads require internet access. Ollama 0.6 or later is required for Gemma 3.

### Update an existing installation

Close Andy, then open your existing project folder. If you followed this chat's instructions, that folder is `~/andy-app`:

```bash
cd ~/andy-app
git pull --ff-only
sudo pacman -S mpv
bash install-desktop.sh
.venv/bin/python desktop.py
```

No new Ollama model is needed if you already installed `gemma3:4b`. Environment overrides from previous terminal commands can change the selected model or voice; `.env` files are not automatically loaded.

## Talk to Andy

1. Open **Andy** from the application menu, or run `.venv/bin/python desktop.py` in the project folder.
2. Click the orb to start listening.
3. Say **“Andy”**, wait for **“Yes?”**, then ask a question in English.
4. Pause when finished. Andy speaks the answer and returns to waiting for its name.

Examples:

- “What time is it?” — uses the PC's clock.
- “What is the weather?” — current weather for **Hyderabad, India**.
- “Will it rain tomorrow?” — tomorrow's forecast and maximum precipitation probability.
- “What is the weather in London?” — checks that city instead, and uses it for later weather questions in this session.
- “Read the latest news.” — up to three recent headlines for the India/English news edition.
- “Tell me technology news.” — recent headlines matching that topic.
- “Explain how a processor works.” Then, after waking Andy again: “Give me an example.” — uses recent conversation context.

## Soft female English voice

The default is **Neerja**, an Indian English female neural voice, at a slightly slower rate and reduced volume. It uses Microsoft Edge's online speech service through `edge-tts`; no API key or Edge browser is needed. `mpv` plays the generated audio. The service's available voices and availability may change.

**Reply text is sent to Microsoft's speech service.** Microphone recordings are not sent there. Generated speech is written to a temporary file for playback and deleted afterward.

If online synthesis fails or mpv is missing, Andy reports the problem and uses a local eSpeak female-style backup. This backup is more robotic. To deliberately use only offline speech:

```bash
ANDY_TTS_ENGINE=espeak .venv/bin/python desktop.py
```

To choose a different English neural voice or speaking rate:

```bash
ANDY_TTS_VOICE=en-US-JennyNeural ANDY_TTS_RATE=-12% .venv/bin/python desktop.py
```

List available service voices with `.venv/bin/edge-tts --list-voices`. A softer voice is a selected voice and pacing setting, not a guarantee of humanlike delivery.

## Live weather and news

Weather uses **Open-Meteo**, with city lookup through its geocoding API. The default city is **Hyderabad, India**; no GPS or automatic location lookup is used. Measurements use Celsius. Andy states the selected city, source, and timestamp for current conditions. It checks current conditions or today/tomorrow daily forecasts; hourly, historical, weekend, and extended forecasts are not implemented. Old or missing data is not presented as current.

News uses **Google News RSS**, in English with the India edition. It reads up to three publisher-attributed headlines published in the last 48 hours, rather than inventing a summary or claiming to have read the full articles. Topic searches send the requested topic to Google News.

Right-click the orb and choose **Sources for latest live answer** to open weather attribution or the news articles. Links open only when you select them. There are no paid API keys. These public services can be unavailable or rate-limit requests; Andy reports failure and does not ask the language model to guess a current answer. Open-Meteo's free endpoint is intended for non-commercial use.

For another default city:

```bash
ANDY_WEATHER_CITY='Hyderabad, India' .venv/bin/python desktop.py
```

General questions use Ollama's learned knowledge and recent conversation. Andy does **not** have unrestricted web browsing: live retrieval currently covers weather and news headlines. Other current facts need an additional information source.

## Transparent orb controls

- **Click / Space:** start or pause listening.
- **Drag:** move the orb.
- **Right-click:** listening controls, latest live sources, and Quit.
- **Escape:** close Andy when it has keyboard focus.
- **Hover:** show status and errors.

There is no painted background panel. Transparency requires desktop compositing; most Wayland desktops provide it, while an X11 window manager may need compositing enabled. Rendering stops while minimized but listening continues. The orb must remain running to hear its wake word; it does not automatically start at login.

Pause closes the microphone and stops audio playback. An active network or Ollama request may need to finish before listening can restart; model requests have a three-minute timeout. Neural synthesis has a 25-second timeout and checks for cancellation. Voice interruption during playback is not supported; click to pause instead. Restarting listening clears conversation context.

## Speech understanding and response speed

Vosk recognizes the name “Andy” and detects the end of speech; Whisper small transcribes questions locally with CPU int8. Recognition is set to English by default, and the model is instructed to reply in English. Unclear speech prompts another attempt instead of using a low-confidence transcription. This is a heuristic: accuracy still depends on accent, noise and microphone quality.

Gemma 3 4B is the default conversational model. Replies are streamed and spoken sentence by sentence. It retains the latest 12 messages, uses a 2,048-token model context and up to 180 output tokens, and asks Ollama to keep the model loaded for 30 minutes. The first request after a cold start can take longer. No local model reliably answers every question, and CPU latency still needs testing on your machine.

For faster recognition with potentially lower accuracy:

```bash
ANDY_SPEECH_MODEL=base .venv/bin/python download_speech_model.py
ANDY_SPEECH_MODEL=base .venv/bin/python desktop.py
```

## Troubleshooting

- **Microphone:** check the desktop input device. List devices with `.venv/bin/python -m sounddevice`; select one with `ANDY_INPUT_DEVICE=DEVICE_NUMBER .venv/bin/python desktop.py`.
- **Neural voice unavailable:** verify internet access, install mpv, and list voices with `.venv/bin/edge-tts --list-voices`.
- **No audio:** test `mpv` with a local audio file and `espeak-ng -v en-us+f3 "Hello from Andy"`; check your output device.
- **Weather/news unavailable:** check access to `geocoding-api.open-meteo.com`, `api.open-meteo.com`, and `news.google.com`. Provider failures do not mean Ollama is broken.
- **Ollama unavailable:** run `ollama list` and `systemctl status ollama` and check the selected model is installed.
- **Wrong time:** check your PC's timezone and clock with `timedatectl`.
- **Wake word missed:** move closer to the microphone, reduce background noise and say “Hey Andy.” Wait for “Yes?” before the question.
- **Shortcut broken after moving files:** rerun `bash install-desktop.sh`.

## Data and configuration

Configuration variables are documented in `.env.example`. Set them in the environment before starting the app. Important options include `ANDY_MODEL`, `OLLAMA_URL`, `ANDY_WEATHER_CITY`, `ANDY_TTS_ENGINE`, `ANDY_TTS_VOICE`, `ANDY_TTS_RATE`, `ANDY_INPUT_DEVICE`, `ANDY_SPEECH_MODEL`, and `ANDY_SPEECH_LANGUAGE` (default `en`).

Microphone audio and conversation context stay in memory, with no saved recordings or transcripts. After initial model downloads, recognition runs offline. General conversation is sent to the configured Ollama server; the default is local. Female neural speech sends reply text to Microsoft. Weather sends city/coordinates to Open-Meteo; news sends search topics to Google News. Temporary synthesized audio is removed after playback. Andy cannot access files/apps, send messages, or schedule background actions.

The earlier browser interface remains available with `python3 server.py` and http://127.0.0.1:8000. It uses browser speech features; the native soft voice and live-source menu described here belong to `desktop.py`.

## Checks and sources

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile desktop.py voice_output.py live_information.py speech_input.py
bash -n install-desktop.sh
```

Automated tests cover source parsing, stale data, offline failures, temporary audio, cancellation, and conversation flow. Live network providers, neural voice sound, and physical microphone playback need verification on your PC; the cloud workspace does not permit these provider endpoints.

Sources: [edge-tts](https://github.com/rany2/edge-tts), [Microsoft voice support](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support), [Open-Meteo](https://open-meteo.com/en/docs), [Geocoding API](https://open-meteo.com/en/docs/geocoding-api), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Gemma 3](https://ollama.com/library/gemma3).
