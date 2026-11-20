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

## Current boundary

This milestone adds manual app discovery and launch. Voice, wake-word detection, dictation, system monitoring, and offline speech services are not wired in yet. The runtime and catalog are separate modules so later voice commands can use the same guarded launcher.
