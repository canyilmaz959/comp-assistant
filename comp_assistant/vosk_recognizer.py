"""Offline Vosk speech recognition consuming the shared microphone queue."""
from __future__ import annotations

import json
import logging
from pathlib import Path
import struct
from threading import Event, Lock
from typing import Any, Callable

from .config import DEFAULT_DTYPE, DEFAULT_SAMPLE_RATE

logger = logging.getLogger(__name__)


class VoskModelError(RuntimeError):
    """The configured local Vosk model is missing or cannot be loaded."""


class VoskSpeechRecognizer:
    """SpeechRecognizer implementation; never owns or opens a microphone."""

    def __init__(
        self,
        microphone_manager: Any,
        model_directory: str | Path,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        *,
        dtype: str = DEFAULT_DTYPE,
        channels: int = 1,
        vosk_module: Any | None = None,
        on_partial_result: Callable[[str], None] | None = None,
    ) -> None:
        if sample_rate <= 0 or channels <= 0:
            raise ValueError("sample_rate and channels must be positive")
        if sample_rate != microphone_manager.sample_rate:
            raise ValueError("Vosk and microphone sample rates must match")
        self.microphone_manager = microphone_manager
        self.model_directory = Path(model_directory).expanduser()
        self.sample_rate = sample_rate
        self.dtype = dtype
        self.channels = channels
        self._vosk_module = vosk_module
        self.on_partial_result = on_partial_result or (lambda _text: None)
        self._lock = Lock()
        self._model: Any | None = None
        self._recognizer: Any | None = None
        self._opened = False
        self._dropped_frames = 0

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._opened

    def open(self) -> None:
        with self._lock:
            self._recognizer = None
            self._opened = True
            self._dropped_frames = self.microphone_manager.dropped_frames

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not self.model_directory.is_dir():
            raise VoskModelError(
                "Türkçe Vosk modeli bulunamadı. Modeli indirin ve "
                f"'vosk_model_directory' ayarına çıkarılmış klasörün yolunu yazın: {self.model_directory}"
            )
        try:
            module = self._vosk_module
            if module is None:
                import vosk as module
            self._model = module.Model(str(self.model_directory))
        except VoskModelError:
            raise
        except Exception as error:
            raise VoskModelError(
                f"Vosk modeli yüklenemedi: {self.model_directory}. "
                "Klasörün doğru çıkarıldığını ve Vosk model dosyalarını içerdiğini kontrol edin."
            ) from error
        logger.info("Loaded local Vosk model from %s", self.model_directory)
        return self._model

    def _new_recognizer(self) -> Any:
        model = self._load_model()
        module = self._vosk_module
        if module is None:
            import vosk as module
        return module.KaldiRecognizer(model, self.sample_rate)

    def recognize(self, stop_event: Event) -> str | None:
        with self._lock:
            if not self._opened:
                raise RuntimeError("Vosk recognizer is not open")
            self._recognizer = self._new_recognizer()
            recognizer = self._recognizer
            self._dropped_frames = self.microphone_manager.dropped_frames
        try:
            while not stop_event.is_set():
                try:
                    chunk = self.microphone_manager.read_frame(timeout=0.2)
                except TimeoutError:
                    continue
                if chunk.frame_count <= 0:
                    logger.warning("Skipping empty microphone audio block")
                    continue
                try:
                    audio = _pcm16_mono(chunk.data, self.dtype, self.channels)
                except ValueError:
                    logger.warning("Skipping malformed microphone audio block")
                    continue
                if not audio:
                    logger.warning("Skipping invalid or empty microphone audio block")
                    continue
                if chunk.status:
                    logger.warning("Microphone reported an audio status: %s", chunk.status)
                dropped = self.microphone_manager.dropped_frames
                if dropped != self._dropped_frames:
                    logger.warning("Microphone queue dropped audio; resetting Vosk phrase state")
                    with self._lock:
                        if not stop_event.is_set():
                            self._recognizer = self._new_recognizer()
                            recognizer = self._recognizer
                    self._dropped_frames = dropped
                if recognizer.AcceptWaveform(audio):
                    result = _result_text(recognizer.Result(), "text")
                    if result:
                        return result
                else:
                    partial = _result_text(recognizer.PartialResult(), "partial")
                    if partial:
                        self.on_partial_result(partial)
            # Flush internal state, but do not return it after cancellation.
            if recognizer is not None:
                recognizer.FinalResult()
            return None
        except VoskModelError:
            logger.error("Offline speech recognition is unavailable: configured model problem")
            raise
        except Exception:
            logger.exception("Offline speech recognition failed")
            raise
        finally:
            with self._lock:
                if self._recognizer is recognizer:
                    self._recognizer = None

    def close(self) -> None:
        with self._lock:
            self._recognizer = None
            self._model = None
            self._opened = False


def _result_text(payload: str, key: str) -> str:
    try:
        value = json.loads(payload).get(key, "")
    except (TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("Vosk returned an invalid recognition result") from error
    return value.strip() if isinstance(value, str) else ""


def _pcm16_mono(data: Any, dtype: str, channels: int) -> bytes:
    """Convert callback arrays to the PCM16 mono format expected by Vosk."""
    if hasattr(data, "tobytes"):
        raw = data.tobytes()
    elif isinstance(data, (bytes, bytearray, memoryview)):
        raw = bytes(data)
    else:
        raise ValueError("Unsupported microphone audio block")
    widths = {"int16": 2, "int32": 4, "float32": 4}
    if dtype not in widths or not raw or len(raw) % (widths.get(dtype, 1) * channels):
        raise ValueError("Malformed microphone audio block")
    if dtype == "int16" and channels == 1:
        return raw
    width = widths[dtype]
    frame_width = width * channels
    frames = len(raw) // frame_width
    output = bytearray(frames * 2)
    for frame in range(frames):
        samples = []
        for channel in range(channels):
            offset = frame * frame_width + channel * width
            if dtype == "int16":
                sample = struct.unpack_from("<h", raw, offset)[0]
            elif dtype == "int32":
                sample = struct.unpack_from("<i", raw, offset)[0] >> 16
            else:
                value = struct.unpack_from("<f", raw, offset)[0]
                sample = round(max(-1.0, min(1.0, value)) * 32767)
            samples.append(sample)
        mono = max(-32768, min(32767, sum(samples) // channels))
        struct.pack_into("<h", output, frame * 2, mono)
    return bytes(output)
