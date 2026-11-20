"""Small thread-safe lifecycle state shared by the tray and future services."""
from __future__ import annotations

from threading import Event, Lock


class AssistantRuntime:
    def __init__(self, command_wait_seconds: int) -> None:
        self._lock = Lock()
        self._command_wait_seconds = command_wait_seconds
        self._enabled = Event()
        self._enabled.set()
        self._shutdown = Event()

    @property
    def is_enabled(self) -> bool:
        return self._enabled.is_set() and not self._shutdown.is_set()

    @property
    def is_shutdown(self) -> bool:
        return self._shutdown.is_set()

    @property
    def command_wait_seconds(self) -> int:
        with self._lock:
            return self._command_wait_seconds

    def set_enabled(self, enabled: bool) -> None:
        if self._shutdown.is_set():
            return
        if enabled:
            self._enabled.set()
        else:
            self._enabled.clear()

    def update_command_wait_seconds(self, seconds: int) -> None:
        with self._lock:
            self._command_wait_seconds = seconds

    def shutdown(self) -> None:
        self._enabled.clear()
        self._shutdown.set()

    def wait_for_next_command_window(self) -> bool:
        """Wait for the configured interval; return false when paused or shut down.

        A future voice service can use this shared gate before opening a command
        capture window. This shell currently does not access the microphone.
        """
        if self._shutdown.wait(self.command_wait_seconds):
            return False
        return self.is_enabled
