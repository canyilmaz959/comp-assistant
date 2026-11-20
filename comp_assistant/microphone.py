"""Single-owner, callback-driven microphone capture backed by sounddevice."""
from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, Lock, RLock
from typing import Any

from .config import (
    DEFAULT_BLOCK_SIZE,
    DEFAULT_CHANNELS,
    DEFAULT_DTYPE,
    DEFAULT_SAMPLE_RATE,
)


class MicrophoneCaptureError(RuntimeError):
    """Raised when a microphone stream cannot be created or controlled."""


@dataclass(frozen=True)
class AudioChunk:
    data: Any
    frame_count: int
    status: str = ""


class MicrophoneManager:
    """Own one sounddevice InputStream and queue callback-delivered chunks.

    The callback only copies a block and performs a non-blocking queue insert.
    A full queue drops the newest block and increments ``dropped_frames``;
    consumers should drain it promptly. No capture thread is created here:
    sounddevice owns its callback thread and ``stop``/``close`` join it through
    the stream API.
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        block_size: int = DEFAULT_BLOCK_SIZE,
        input_device: int | str | None = None,
        dtype: str = DEFAULT_DTYPE,
        queue_capacity: int = 32,
        sounddevice_module: Any | None = None,
    ) -> None:
        if sample_rate <= 0 or channels <= 0 or block_size <= 0 or queue_capacity <= 0:
            raise ValueError("sample_rate, channels, block_size and queue_capacity must be positive")
        if isinstance(input_device, bool):
            raise ValueError("input_device must be a non-negative ID, a name, or None")
        if isinstance(input_device, int) and input_device < 0:
            raise ValueError("input_device must be a non-negative ID, a name, or None")
        if input_device is not None and not isinstance(input_device, (int, str)):
            raise ValueError("input_device must be a non-negative ID, a name, or None")

        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = block_size
        self.input_device = input_device
        self.dtype = dtype
        self._sounddevice_module = sounddevice_module
        self._frames: Queue[AudioChunk] = Queue(maxsize=queue_capacity)
        self._capture_enabled = Event()
        self._operation_lock = RLock()
        self._state_lock = Lock()
        self._stream: Any | None = None
        self._closed = False
        self._dropped_frames = 0
        self._last_error: str | None = None

    @property
    def is_capturing(self) -> bool:
        return self._capture_enabled.is_set()

    @property
    def has_open_stream(self) -> bool:
        with self._state_lock:
            return self._stream is not None

    @property
    def dropped_frames(self) -> int:
        with self._state_lock:
            return self._dropped_frames

    @property
    def last_error(self) -> str | None:
        with self._state_lock:
            return self._last_error

    @property
    def queued_frames(self) -> int:
        return self._frames.qsize()

    def read_frame(self, timeout: float | None = None) -> AudioChunk:
        """Return the oldest captured chunk, optionally waiting for a consumer."""
        try:
            if timeout is None:
                return self._frames.get_nowait()
            return self._frames.get(timeout=timeout)
        except Empty as error:
            raise TimeoutError("No microphone audio frame is available") from error

    def start(self) -> None:
        with self._operation_lock:
            with self._state_lock:
                if self._closed:
                    raise MicrophoneCaptureError("Microphone manager is closed")
                if self._stream is not None:
                    return
            module = self._get_sounddevice()
            stream = None
            try:
                stream = module.InputStream(
                    device=self.input_device,
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    blocksize=self.block_size,
                    dtype=self.dtype,
                    callback=self._on_audio,
                )
                self._capture_enabled.set()
                stream.start()
            except Exception as error:
                self._capture_enabled.clear()
                if stream is not None:
                    try:
                        stream.stop()
                    except Exception:
                        pass
                    try:
                        stream.close()
                    except Exception:
                        pass
                message = self._format_error(error)
                with self._state_lock:
                    self._last_error = message
                raise MicrophoneCaptureError(message) from error
            with self._state_lock:
                self._stream = stream
                self._last_error = None

    def _get_sounddevice(self) -> Any:
        if self._sounddevice_module is not None:
            return self._sounddevice_module
        try:
            import sounddevice
        except ImportError as error:
            message = "Microphone capture requires the 'sounddevice' package."
            with self._state_lock:
                self._last_error = message
            raise MicrophoneCaptureError(message) from error
        self._sounddevice_module = sounddevice
        return sounddevice

    def _format_error(self, error: Exception) -> str:
        selected = "system default input device" if self.input_device is None else repr(self.input_device)
        return (
            f"Could not open microphone input {selected} "
            f"({self.sample_rate} Hz, {self.channels} channel(s)): {error}"
        )

    def _on_audio(self, indata: Any, frames: int, _time_info: Any, status: Any) -> None:
        if not self._capture_enabled.is_set():
            return
        try:
            data = indata.copy()
            chunk = AudioChunk(data=data, frame_count=frames, status=str(status) if status else "")
            self._frames.put_nowait(chunk)
        except Full:
            with self._state_lock:
                self._dropped_frames += frames
        except Exception:
            # Audio callbacks must not propagate exceptions into the PortAudio thread.
            with self._state_lock:
                self._dropped_frames += frames

    def stop(self) -> None:
        with self._operation_lock:
            with self._state_lock:
                stream = self._stream
                self._stream = None
            self._capture_enabled.clear()
            if stream is None:
                self._discard_queued_frames()
                return

            first_error: Exception | None = None
            try:
                stream.stop()
            except Exception as error:
                first_error = error
            try:
                stream.close()
            except Exception as error:
                if first_error is None:
                    first_error = error
            self._discard_queued_frames()
            if first_error is not None:
                message = self._format_error(first_error)
                with self._state_lock:
                    self._last_error = message
                raise MicrophoneCaptureError(message) from first_error

    def _discard_queued_frames(self) -> None:
        while True:
            try:
                self._frames.get_nowait()
            except Empty:
                return

    def close(self) -> None:
        with self._operation_lock:
            with self._state_lock:
                if self._closed:
                    return
            error: Exception | None = None
            try:
                self.stop()
            except Exception as caught:
                error = caught
            with self._state_lock:
                self._closed = True
            if error is not None:
                raise error
