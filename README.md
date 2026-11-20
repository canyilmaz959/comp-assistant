# Comp Assistant

Comp Assistant is a Windows desktop assistant in active development.

## Current features

- System-tray shell with settings, enabled/paused state, and full shutdown.
- Configurable command wait interval and a user-managed HTTP/HTTPS site list.
- Dynamic Windows application discovery from Start Menu shortcuts and registered App Paths.
- App search and explicit launch from the tray picker.

## Run

Install Python 3.10 or newer and the desktop dependencies:

```powershell
py -m pip install -r requirements-tray.txt
py -m comp_assistant
```

## Development roadmap

- Connect a local/offline wake-word and speech pipeline to the shared runtime.
- Add command/session state and connect spoken app requests to the guarded app catalog.
- Add dictation, system monitoring, and actions for managed websites.
- Package and validate the Windows application.

The current shell does not access the microphone.
