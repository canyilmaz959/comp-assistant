# Comp Assistant

This package provides the Windows system-tray shell, settings, and a dynamic application catalog.

## Start on Windows

1. Install Python 3.10 or newer.
2. From the repository root, install dependencies:

   `py -m pip install -r requirements-tray.txt`

3. Start the assistant:

   `py -m comp_assistant`

Use **Uygulama bul ve aç** from the tray menu to search apps exposed by the current user's and all users' Windows Start Menu shortcuts, plus executable paths registered under Windows App Paths. The launcher only starts entries discovered from those sources; it does not execute arbitrary text as a shell command. When names match multiple apps, the picker lets the user choose.

Settings are stored in `%APPDATA%\CompAssistant\settings.json`. They include a 1–120 second command wait interval and a list of HTTP/HTTPS sites.

## Offline Turkish speech recognition (manual model setup)

Vosk is installed with `requirements-tray.txt`, but the speech model is not
bundled and Comp never downloads it automatically. Download the official
[`vosk-model-small-tr-0.3` Turkish model (about 35 MB)](https://alphacephei.com/vosk/models)
from the Vosk model list, then extract the model folder to:

`%APPDATA%\CompAssistant\models\vosk-model-small-tr-0.3`

The extracted folder itself must contain Vosk model files (avoid an extra
nested `vosk-model-small-tr-0.3\vosk-model-small-tr-0.3` directory). Comp uses
this path by default. To choose another location, set `vosk_model_directory`
in `%APPDATA%\CompAssistant\settings.json`. If the directory is missing or
invalid when recognition is requested, Comp reports a model setup error; normal
startup does not load or download the model. The configured microphone sample
rate is passed to Vosk; the default is 16 kHz, mono, signed 16-bit PCM.

## Offline speech output (Windows OneCore)

Comp uses the native `Windows.Media.SpeechSynthesis` API through PyWinRT and
plays its generated stream with Windows `MediaPlayer`. It enumerates OneCore's
`SpeechSynthesizer.AllVoices`, matches the BCP-47 `Language` value to `tr-*`,
prefers the installed Tolga voice, then uses another installed Turkish voice.
It never falls back to English or German. Synthesis is local and does not
download voice data or models at startup.

The tray dependency file installs the PyWinRT projections for SpeechSynthesis,
Media.Core and Media.Playback on Windows. Keep the Turkish speech voice
installed and enabled in Windows; no separate model directory is required.
`tts_voice_id` can pin an installed voice by ID or display name, but the
configured voice must still report a Turkish BCP-47 language. `tts_enabled`
toggles output, `tts_rate` accepts 80–350 (180 is normal speed), and
`tts_volume` accepts 0.0–1.0. The legacy settings remain readable.

List the OneCore voices visible to Comp (DisplayName, Language and Id) with:

```powershell
python -m comp_assistant.onecore_diagnostic
```

Optionally synthesize and play a Turkish test phrase:

```powershell
python -m comp_assistant.onecore_diagnostic --speak "Merhaba, bu bir ses testidir."
```

If OneCore is unavailable in the current Windows session, Comp logs a clear
diagnostic and does not switch back to legacy SAPI5 or another language.

## Current boundary

Offline recognition and Windows speech output are wired behind the audio
service, but wake-word detection is not implemented. The tray app's wake
detector remains intentionally inert, so saying “hey comp” does not activate
the microphone or command pipeline yet. This phase does not execute recognized
text as a shell command.
