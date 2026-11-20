"""Engine-independent audio contracts and a deterministic mock pipeline.

Implementations must make blocking operations observe the supplied stop event;
``close`` must release any microphone/device resources owned by the engine.
"""
from __future__ import annotations

from collections.abc import Callable
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Protocol
import logging

from .lifecycle import RuntimeState

logger = logging.getLogger(__name__)


class WakeWordDetector(Protocol):
    def open(self) -> None: ...
    def wait_for_wake_word(self, stop_event: Event) -> bool: ...
    def close(self) -> None: ...


class SpeechRecognizer(Protocol):
    def open(self) -> None: ...
    def recognize(self, stop_event: Event) -> str | None: ...
    def close(self) -> None: ...


class SpeechSynthesizer(Protocol):
    def open(self) -> None: ...
    def speak(self, text: str, stop_event: Event) -> None: ...
    def close(self) -> None: ...


StateCallback = Callable[[RuntimeState], None]
CommandHandler = Callable[[str], str | None]


class AudioService:
    """Owns one cooperative worker and the wake/STT/TTS service resources."""

    def __init__(
        self,
        wake_word_detector: WakeWordDetector,
        speech_recognizer: SpeechRecognizer,
        speech_synthesizer: SpeechSynthesizer,
        command_handler: CommandHandler | None = None,
        on_state_change: StateCallback | None = None,
    ) -> None:
        self.wake_word_detector = wake_word_detector
        self.speech_recognizer = speech_recognizer
        self.speech_synthesizer = speech_synthesizer
        self.command_handler = command_handler or (lambda _text: None)
        self.on_state_change = on_state_change or (lambda _state: None)
        self._lock = Lock()
        self._stop_event: Event | None = None
        self._worker: Thread | None = None
        self._shutdown = False

    @property
    def worker_alive(self) -> bool:
        with self._lock:
            return self._worker is not None and self._worker.is_alive()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._worker is not None and self._worker.is_alive()

    def start(self) -> None:
        with self._lock:
            if self._shutdown or (self._worker and self._worker.is_alive()):
                return
            stop_event = Event()
            opened = []
            try:
                for service in (
                    self.wake_word_detector,
                    self.speech_recognizer,
                    self.speech_synthesizer,
                ):
                    service.open()
                    opened.append(service)
            except Exception:
                for service in reversed(opened):
                    service.close()
                raise
            worker = Thread(
                target=self._run,
                args=(stop_event,),
                name="CompAssistantAudio",
                daemon=False,
            )
            self._stop_event = stop_event
            self._worker = worker
            try:
                worker.start()
            except Exception:
                self._worker = None
                self._stop_event = None
                self._close_services()
                raise
        self.on_state_change(RuntimeState.STANDBY)

    def _run(self, stop_event: Event) -> None:
        try:
            while not stop_event.is_set():
                if not self.wake_word_detector.wait_for_wake_word(stop_event):
                    continue
                if stop_event.is_set():
                    break
                self.on_state_change(RuntimeState.ACTIVE)
                command = self.speech_recognizer.recognize(stop_event)
                if command and not stop_event.is_set():
                    response = self.command_handler(command)
                    if response and not stop_event.is_set():
                        self.speech_synthesizer.speak(response, stop_event)
                if not stop_event.is_set():
                    self.on_state_change(RuntimeState.STANDBY)
        except Exception:
            # A failed audio backend must not leave the runtime claiming to listen.
            logger.exception("Audio service worker failed")
            self.on_state_change(RuntimeState.STOPPED)

    def pause(self) -> None:
        with self._lock:
            worker = self._worker
            stop_event = self._stop_event
            if worker is None:
                return
            if stop_event is not None:
                stop_event.set()
        worker.join()
        with self._lock:
            if self._worker is worker:
                self._worker = None
                self._stop_event = None
                self._close_services()

    def _close_services(self) -> None:
        first_error: Exception | None = None
        for service in (
            self.speech_synthesizer,
            self.speech_recognizer,
            self.wake_word_detector,
        ):
            try:
                service.close()
            except Exception as error:
                if first_error is None:
                    first_error = error
        if first_error is not None:
            raise first_error

    def shutdown(self) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
        self.pause()
        self.on_state_change(RuntimeState.STOPPED)


class MockWakeWordDetector:
    """Queue-driven wake detector; it never opens a real microphone."""

    def __init__(self) -> None:
        self._wakes: Queue[bool] = Queue()
        self.open_count = 0
        self.close_count = 0
        self.is_open = False

    def trigger(self) -> None:
        self._wakes.put(True)

    def open(self) -> None:
        self.open_count += 1
        self.is_open = True

    def wait_for_wake_word(self, stop_event: Event) -> bool:
        while not stop_event.is_set():
            try:
                self._wakes.get(timeout=0.05)
                return not stop_event.is_set()
            except Empty:
                continue
        return False

    def close(self) -> None:
        self.close_count += 1
        self.is_open = False


class MockSpeechRecognizer:
    def __init__(self) -> None:
        self._commands: Queue[str | None] = Queue()
        self.open_count = 0
        self.close_count = 0
        self.is_open = False

    def submit(self, command: str | None) -> None:
        self._commands.put(command)

    def open(self) -> None:
        self.open_count += 1
        self.is_open = True

    def recognize(self, stop_event: Event) -> str | None:
        while not stop_event.is_set():
            try:
                return self._commands.get(timeout=0.05)
            except Empty:
                continue
        return None

    def close(self) -> None:
        self.close_count += 1
        self.is_open = False


class MockSpeechSynthesizer:
    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.open_count = 0
        self.close_count = 0
        self.is_open = False

    def open(self) -> None:
        self.open_count += 1
        self.is_open = True

    def speak(self, text: str, stop_event: Event) -> None:
        if not stop_event.is_set():
            self.spoken.append(text)

    def close(self) -> None:
        self.close_count += 1
        self.is_open = False


class MockAudioService(AudioService):
    """Convenience mock bundle used by the desktop shell until engines exist."""

    def __init__(
        self,
        command_handler: CommandHandler | None = None,
        on_state_change: StateCallback | None = None,
    ) -> None:
        self.detector = MockWakeWordDetector()
        self.recognizer = MockSpeechRecognizer()
        self.synthesizer = MockSpeechSynthesizer()
        super().__init__(
            self.detector,
            self.recognizer,
            self.synthesizer,
            command_handler=command_handler,
            on_state_change=on_state_change,
        )
