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

## Current boundary

The offline recognition backend and shared microphone lifecycle are in place,
but wake-word detection and speech output are not implemented. The tray app's
wake detector is intentionally inert, so voice activation is not yet available;
this phase does not execute recognized text as a shell command.
