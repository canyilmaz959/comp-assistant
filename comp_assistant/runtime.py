"""Thread-safe assistant lifecycle shared by the tray and audio services."""
from __future__ import annotations

from threading import Lock

from .lifecycle import RuntimeState
from .voice import AudioService, MockAudioService


class AssistantRuntime:
    def __init__(
        self,
        command_wait_seconds: int,
        audio_service: AudioService | None = None,
        microphone_manager=None,
    ) -> None:
        self._lock = Lock()
        self._lifecycle_lock = Lock()
        self._command_wait_seconds = command_wait_seconds
        self._state = RuntimeState.STANDBY
        self.microphone_manager = microphone_manager
        self._microphone_error: str | None = None
        self._audio_service = audio_service or MockAudioService(
            on_state_change=self._set_audio_state
        )
        self._audio_service.on_state_change = self._set_audio_state
        self._audio_service.start()

    @property
    def state(self) -> RuntimeState:
        with self._lock:
            return self._state

    @property
    def is_enabled(self) -> bool:
        return self.state in {RuntimeState.STANDBY, RuntimeState.ACTIVE}

    @property
    def is_shutdown(self) -> bool:
        return self.state is RuntimeState.STOPPED

    @property
    def microphone_error(self) -> str | None:
        with self._lock:
            return self._microphone_error

    @property
    def command_wait_seconds(self) -> int:
        with self._lock:
            return self._command_wait_seconds

    def _set_audio_state(self, state: RuntimeState) -> None:
        with self._lock:
            if self._state in {RuntimeState.PAUSED, RuntimeState.STOPPED}:
                return
        if state in {RuntimeState.STANDBY, RuntimeState.STOPPED}:
            self._manage_microphone("stop" if state is RuntimeState.STANDBY else "close")
        with self._lock:
            if self._state not in {RuntimeState.PAUSED, RuntimeState.STOPPED}:
                self._state = state
            else:
                return
        if self.microphone_manager is None:
            return
        if state is RuntimeState.ACTIVE:
            self._manage_microphone("start")

    def _manage_microphone(self, operation: str) -> None:
        try:
            getattr(self.microphone_manager, operation)()
        except Exception as error:
            with self._lock:
                self._microphone_error = str(error)
        else:
            with self._lock:
                self._microphone_error = None

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self.resume()
        else:
            self.pause()

    def pause(self) -> None:
        with self._lifecycle_lock:
            with self._lock:
                if self._state in {RuntimeState.PAUSED, RuntimeState.STOPPED}:
                    return
            try:
                self._audio_service.pause()
            finally:
                if self.microphone_manager is not None:
                    self._manage_microphone("stop")
                with self._lock:
                    if self._state is not RuntimeState.STOPPED:
                        self._state = RuntimeState.PAUSED

    def resume(self) -> None:
        with self._lifecycle_lock:
            with self._lock:
                if self._state is RuntimeState.STOPPED:
                    return
                if self._state is not RuntimeState.PAUSED:
                    return
                self._state = RuntimeState.STANDBY
            self._audio_service.start()

    def update_command_wait_seconds(self, seconds: int) -> None:
        with self._lock:
            self._command_wait_seconds = seconds

    def shutdown(self) -> None:
        with self._lifecycle_lock:
            with self._lock:
                if self._state is RuntimeState.STOPPED:
                    return
            try:
                self._audio_service.shutdown()
            finally:
                if self.microphone_manager is not None:
                    self._manage_microphone("close")
                with self._lock:
                    self._state = RuntimeState.STOPPED

    def wait_for_next_command_window(self) -> bool:
        """Retain the prior wait API for callers during migration."""
        import time

        deadline = time.monotonic() + self.command_wait_seconds
        while time.monotonic() < deadline:
            if self.state in {RuntimeState.PAUSED, RuntimeState.STOPPED}:
                return False
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        return self.state not in {RuntimeState.PAUSED, RuntimeState.STOPPED}
