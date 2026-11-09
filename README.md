# Andy — personal voice AI for your PC

Andy is a native Arch Linux desktop assistant with a transparent blue-white particle orb. Speak in **English**, hear a **female English neural voice**, ask general questions through local Ollama, and get live weather or recent news from online sources.

## Install on Arch Linux

```bash
sudo pacman -Syu git python python-pip portaudio espeak-ng mpv yt-dlp deno xdg-utils libnotify ollama
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
sudo pacman -S mpv yt-dlp deno xdg-utils libnotify
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

## Pixy webcam and microphone

Andy can answer questions about **one camera snapshot at a time**. It does not watch continuously or record video. No camera photo is saved to disk.

1. Update Andy and run `bash install-desktop.sh` to install the new OpenCV camera dependency.
2. Right-click the orb → **Choose microphone…** or **Choose camera…**, or press **Ctrl+,** while Andy has focus.
3. Select your **Pixy** camera and its microphone, then save. Listing devices reads names only; it does not open the lens or microphone. If the microphone changes, click the orb to restart listening.
4. Wake Andy and say **“What do you see?”**, **“What am I holding?”**, or **“Look at this and describe it.”**
5. A native dialog asks **“Allow Andy to use your camera once?”** Choose **Allow once** or **Deny**. **Deny is the default**, including Escape or closing the dialog. Requests expire after one minute.

**Andy does not open the camera until you approve that particular request.** Approval is consumed by one snapshot and cannot be reused. Each new camera question requires a new dialog. Pausing, closing Andy, disabling camera requests, or changing devices cancels pending permission. Startup frames may be discarded while the webcam initializes; only one resulting JPEG is used for the answer. The camera is released before model analysis, including on read/encode failure.

Photos are sent only to a loopback Ollama endpoint on your PC, using the configured vision model (`gemma3:4b` by default). This path stays local even in **Cloud** or **Hybrid** AI mode. Remote `OLLAMA_URL` values are refused for camera questions. Images are not stored in conversation history or sent to OpenAI. **Spoken descriptions still follow your speech settings**: the default online neural voice receives the reply text. Use `ANDY_TTS_ENGINE=espeak` to keep spoken descriptions offline too.

To prevent all camera prompts, uncheck **Camera → Allow permission requests (ask every time)**. This switch enables requests only; checking it does not open the camera or pre-authorize a photo. Camera and microphone selections are session-only. To choose a camera on startup, set `ANDY_CAMERA_DEVICE=/dev/video0` (use the path shown for Pixy in the picker). Microphone selection also supports `ANDY_INPUT_DEVICE`, as before.

If the selector is missing, quit every old Andy window and launch the updated app directly into device settings:

```bash
cd ~/andy-app
git pull --ff-only
bash install-desktop.sh
.venv/bin/python desktop.py --devices
```

Updating files does not update an already-running Python process. `--devices` opens the native device picker immediately, without starting the microphone or camera. Settings can also be opened from the main right-click menu or **Ctrl+,**.

You can open either selector directly, without navigating the orb menu:

```bash
.venv/bin/python desktop.py --microphone
.venv/bin/python desktop.py --camera
```

Each picker has **Refresh devices** and shows how many devices Linux exposes. The microphone picker also accepts an input name or number. **Open system input settings** opens an installed sound settings app. If Linux exposes Pixy's microphone only through the default input, choose Pixy in that sound settings app, then leave Andy on **System default microphone**. Install `pavucontrol` with `sudo pacman -S pavucontrol` if you do not have a sound settings app. Camera selection still does not activate it or grant capture permission.

A webcam may expose multiple `/dev/video*` nodes. Select a node that provides video frames if the first entry cannot capture. Close other apps using that camera. Camera analysis can be slower than text questions on a CPU, and small text or fine details may be misread. Ask a fresh camera question for a new image; visual follow-ups do not reuse a stored photo. The actual Pixy hardware has not been tested in this cloud workspace.

## Local + cloud technical help

Andy supports three **AI inference** modes from the orb’s right-click menu:

- **Local:** general model replies use Ollama on your configured server.
- **Hybrid (default):** technical questions containing terms such as Python, code, CPU, Linux, debugging, or databases use OpenAI when an API key is configured. Their short follow-ups also use the cloud. Other general questions use Ollama. Without a key, hybrid remains local.
- **Cloud:** general model replies use OpenAI; deterministic personal commands, desktop tools, and live-information handlers still run first.

Routing is a keyword heuristic, not a semantic classifier. You can override it for a single question: **“Ask cloud explain Python decorators”** or **“Ask local explain Python decorators.”** Cloud replies have a separate conversation history, so local notes, tasks, and personal command history are not bundled into a later technical request. If you explicitly include private information in a cloud-routed question, that question is sent.

### Configure cloud on your PC

1. Start Andy, right-click the orb, and choose **Cloud AI settings…**.
2. Choose **Hybrid** and enter your own OpenAI API key in the password field.
3. The default cloud model is `gpt-4.1-mini`; choose another Responses API-compatible text model you have access to if desired.
4. Save, wake Andy, and ask a technical question. The orb status identifies cloud use.

The key and menu settings are kept only in the running process, not in the repository or a settings file. Alternatively, supply `OPENAI_API_KEY`, `ANDY_CLOUD_MODEL`, and `ANDY_AI_MODE` through your PC’s runtime environment. Do not paste API keys into this chat. Cloud API usage may be billed and depends on your account’s model access and internet connectivity. Cloud inference has not been tested against a live account here because no API key is configured.

OpenAI receives the cloud question and recent cloud conversation (and retrieved evidence for that question when applicable), with API response storage disabled through `store: false`. This does not override the provider’s account-level retention policies. If cloud access fails before a reply, Andy announces fallback to Ollama; an interrupted partial cloud reply is reported rather than silently retried. Local mode affects **model inference only**: the existing online voice, search, weather, news, and music services still make network requests when used.

Cloud implementation reference: [OpenAI streaming responses](https://developers.openai.com/api/docs/guides/streaming-responses).

## Personal assistant commands

These requests use local deterministic code rather than either AI model:

- **“Set a timer for five minutes.”** / **“Set a ten minute timer.”**
- **“Remind me to drink water in twenty minutes.”**
- **“Remind me to study at nine PM today.”** Use `tomorrow` after the time to schedule the next day.
- **“List my timers.”** / **“List my reminders.”** / **“Cancel reminder 1.”**
- **“Remember that I prefer Python.”** / **“Read my notes.”** / **“Delete note 1.”**
- **“Add buy milk to my to do list.”** / **“List my tasks.”** / **“Complete task 1.”**

Durations accept seconds, minutes, and hours, with digits or common English number words. Absolute reminders use the PC’s timezone. An explicit time already passed *today* is rejected, not silently moved to another day; without a day qualifier, the next occurrence is selected. Confirm the PC’s clock with `timedatectl`.

Notes, to-dos, and timer/reminder deadlines are saved in `$XDG_DATA_HOME/andy/personal.json` (normally `~/.local/share/andy/personal.json`). The data file is replaced atomically with owner-only permissions. It is **not encrypted**. These records persist across restarts; microphone recordings and conversation transcripts are still not saved.

**Keep Andy running and the PC awake for on-time alerts.** There is no OS background scheduling service. Overdue pending reminders are delivered when Andy is next running. While active, the orb shows alerts and, with `libnotify` and your desktop notification service available, posts notifications. Voice alerts are queued until the listener is waiting for its wake word, so an answer or question is not interrupted. While paused, notifications still work but no voice alert is queued. A fully closed app cannot notify you. Pause/restart does not delete saved records.

Personal commands and stored records are excluded from automatic cloud-AI requests. However, the existing default neural **speech service receives spoken reply text**, including notes you ask Andy to read. Set `ANDY_TTS_ENGINE=espeak` to keep spoken personal replies offline too. App launching and music behavior remain as described below; model-generated instructions are never executed as shell commands.

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

General questions use Ollama's learned knowledge and recent conversation. Say **“Search the web for …”** to explicitly look something up. Queries containing “latest,” “current,” stock prices or exchange rates also attempt a web search. Results are search snippets unless you ask Andy to read a result. Search providers may block or rate-limit automated access; a snippet alone does not establish that a fact is current or correct.

## Web search and page reading

Examples:

- “Search the web for the latest Python release.”
- “Look up how solar panels work.”
- “Read the first result.”
- “Summarize the second result.”
- “Read https://example.com.”

DDGS 9 searches DuckDuckGo/Brave without an API key. Queries go to the search providers. Up to three results, with source links, are supplied to the local model. Page reading fetches public HTML/text, excludes scripts and navigation, and limits the extracted text. Private-network URLs, login credentials in URLs, non-web protocols, nonstandard ports, unsupported content types and oversized pages are rejected. Pages requiring login, JavaScript or automated-access challenges may not be readable. The reader does not execute page scripts or follow instructions found on a page.

Right-click **Sources for latest live answer** to inspect links. Web sources are treated as evidence, not commands, and are never passed to desktop action handlers. Ollama summarizes retrieved text; it can still make mistakes, so check important details against the linked sources. Search and page summaries need the local model to be running. “Read the first result” uses the last search in the current native listening session.

## Websites, desktop apps, and music

These commands are handled directly from your speech in the **native desktop app**:

- “Open YouTube,” “Open GitHub,” or “Open example.com.”
- “Open browser,” “Open terminal,” “Open calculator,” “Open text editor,” “Open settings,” “Open Firefox,” “Open Chromium,” or “Open VLC.” The requested app must be installed.
- “Open file manager,” “Open downloads,” or “Open music folder.”
- “Play online relaxing music” or “Play [song/artist].”
- “Play local [song/artist]” or “Play local music.”
- “Pause music,” “Resume music,” “Stop music,” or “Next track.”

Website commands open the PC's normal browser. App launch requests use a small set of known executables and fixed argument lists; they do not run model-generated commands or arbitrary shell strings. Unknown apps are reported as unsupported. Opening a terminal does not run commands inside it. These desktop actions are not exposed by the browser API.

Online music first uses yt-dlp to find a concrete YouTube video, then lets yt-dlp retrieve the audio and pipe it directly into mpv. This avoids passing an extracted media URL to a different downloader. It announces startup only after mpv exposes an active audio decoder. That confirms player readiness, not that your speakers are audible. It requires internet access, yt-dlp (with a supported JavaScript runtime such as Deno for sources that require it), and depends on source availability; source failures are reported instead of announcing that the song is playing. No login, DRM bypass, or downloading a permanent music library is implemented. Andy does not extract browser cookies or change accounts automatically. On Arch, update the extractor/runtime with `sudo pacman -Syu mpv yt-dlp deno`; the current Arch yt-dlp package depends on its EJS support package. If YouTube still refuses direct playback with a 403, sign-in, or availability error, Andy opens the selected YouTube watch page in your normal browser and says so. The browser may require you to press Play; its music is controlled from that page, not Andy’s native pause/stop controls. Other playback errors remain explicit. Updating yt-dlp may resolve extractor compatibility problems, but an update cannot guarantee access to a refused stream. Polite phrases such as “Can you play…”, “Please put on…”, and “I want to listen to…” route directly to music tools.

To diagnose search without playing anything:

```bash
.venv/bin/python check_music.py "song name and artist"
```

To test search and playback together:

```bash
.venv/bin/python check_music.py --play "song name and artist"
```

The test shows dependency paths and versions, the player exit code, and combined player/provider error output. Media URLs are redacted from player errors. The player explicitly enables warning/error output even without a terminal, so failures are not silently discarded; press Enter to stop test playback. Source searches and player startup each have a 20-second timeout. Provider sign-in requirements or blocks are reported rather than bypassed.

Local music searches `~/Music` (up to 10,000 directory entries), matches song/artist text against file paths, and plays supported audio files without uploading them. Matching tracks form a local queue for “Next track.” Online search selects one track; “Next track” does not create an online playlist. To use a different local folder:

```bash
ANDY_MUSIC_DIR='/path/to/Music' .venv/bin/python desktop.py
```

Music has a separate player from the spoken voice. Pausing Andy's microphone does not pause music; use the music commands or quit the app to stop its player. When music is loud, wake-word accuracy can fall; reduce playback/output volume. Music playback and desktop interaction need testing on your actual PC.

## Transparent orb controls

- **Click / Space:** start or pause listening.
- **Drag:** move the orb.
- **Right-click:** listening controls, AI mode, Cloud AI settings, latest live sources, and Quit.
- **Escape:** close Andy when it has keyboard focus.
- **Hover:** show status and errors.

There is no painted background panel. Transparency requires desktop compositing; most Wayland desktops provide it, while an X11 window manager may need compositing enabled. Rendering stops while minimized but listening continues. The orb must remain running to hear its wake word; it does not automatically start at login.

Pause closes the microphone and stops Andy’s spoken reply; music is controlled separately. An active network or Ollama request may need to finish before listening can restart; model requests have a three-minute timeout. Neural synthesis has a 25-second timeout and checks for cancellation. Voice interruption during playback is not supported; click to pause instead. Restarting listening clears conversation context.

## Speech understanding and response speed

Vosk recognizes the name “Andy” and detects the end of speech; Whisper small transcribes questions locally with CPU int8. Recognition is set to English by default, and the model is instructed to reply in English. Unclear speech prompts another attempt instead of using a low-confidence transcription. This is a heuristic: accuracy still depends on accent, noise and microphone quality.

Gemma 3 4B is the default conversational model. Replies are streamed and spoken sentence by sentence. It retains the latest 12 messages, uses a 2,048-token model context and up to 180 output tokens, and asks Ollama to keep the model loaded for 30 minutes. The first request after a cold start can take longer. No local model reliably answers every question, and CPU latency still needs testing on your machine.

For faster recognition with potentially lower accuracy:

```bash
ANDY_SPEECH_MODEL=base .venv/bin/python download_speech_model.py
ANDY_SPEECH_MODEL=base .venv/bin/python desktop.py
```

## Capability answers and connection checks

“What can you do?” and questions about internet tools are answered directly from Andy's supported features, without asking Ollama to describe itself. This does not claim that a provider is currently reachable; an actual weather/news request makes the online call.

To test those connections without the microphone, voice, or Ollama, run this in your project folder:

```bash
.venv/bin/python check_online.py
```

It prints the project folder, Git version, separate Weather/News/Web search results, and a short error type when a provider fails. A failure may mean connectivity, rate limiting, unavailable or malformed data; it is not automatically evidence that your whole PC is offline. The browser API also routes weather/news questions through the live handlers.

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

Microphone audio and conversation context stay in memory, with no saved recordings or transcripts. After initial model downloads, recognition runs offline. General conversation uses the selected local/hybrid/cloud routing. Ollama defaults to the local PC; configured cloud AI sends cloud-routed questions and recent cloud history to OpenAI. Saved personal records are excluded from automatic cloud AI context. Female neural speech sends reply text to Microsoft. Weather sends city/coordinates to Open-Meteo; news sends search topics to Google News. Temporary synthesized audio is removed after playback. Web search sends query text to search providers; page reading requests public pages and supplies extracted text to the configured Ollama server. Desktop tools can launch supported apps and inspect/play audio in your configured Music folder. They do not send messages. Local timers and reminders are checked by the running app, as described above.

The earlier browser interface remains available with `python3 server.py` and http://127.0.0.1:8000. It uses browser speech features; the native soft voice and live-source menu described here belong to `desktop.py`; weather/news routing also works through the browser API.

## Checks and sources

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile desktop.py voice_output.py live_information.py speech_input.py web_tools.py desktop_tools.py ai_router.py personal_assistant.py
bash -n install-desktop.sh
```

Automated tests cover source parsing, stale data, offline failures, temporary audio, cancellation, and conversation flow. Live network providers, neural voice sound, and physical microphone playback need verification on your PC; the cloud workspace does not permit these provider endpoints.

Sources: [edge-tts](https://github.com/rany2/edge-tts), [Microsoft voice support](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support), [Open-Meteo](https://open-meteo.com/en/docs), [Geocoding API](https://open-meteo.com/en/docs/geocoding-api), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Gemma 3](https://ollama.com/library/gemma3), [DDGS](https://github.com/deedy5/ddgs), [mpv](https://mpv.io/manual/master/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [yt-dlp playback FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ), [Arch yt-dlp package](https://archlinux.org/packages/extra/any/yt-dlp/).
