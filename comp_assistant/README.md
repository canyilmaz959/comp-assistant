# Comp Assistant desktop shell

This package adds a separate system-tray shell while preserving the existing Jarvis prototypes.

## Start on Windows

1. Install Python 3.10 or newer.
2. From the repository root, install the tray dependencies:

   `py -m pip install -r requirements-tray.txt`

3. Start the shell:

   `py -m comp_assistant`

The tray menu provides a settings window, an enabled/paused state, and a full shutdown action. Settings are stored in the current Windows user's `%APPDATA%\CompAssistant\settings.json` folder. The wait interval is limited to 1–120 seconds, and managed sites accept only valid HTTP or HTTPS addresses.

## Current boundary

This is the lifecycle and settings foundation. It does not yet start a microphone, wake-word detector, speech recognizer, or speech output service. The runtime exposes shared enabled, pause, shutdown, and wait-interval state for those services to attach in a later milestone. Selecting full shutdown stops the tray process; no microphone listener is started by this shell.
