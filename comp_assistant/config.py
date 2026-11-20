"""Persistent user settings for the Comp Assistant desktop shell."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_WAIT_SECONDS = 8
MIN_WAIT_SECONDS = 1
MAX_WAIT_SECONDS = 120
DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_CHANNELS = 1
DEFAULT_BLOCK_SIZE = 1_024
DEFAULT_DTYPE = "int16"
SUPPORTED_AUDIO_DTYPES = {"int16", "int32", "float32"}
DEFAULT_VOSK_MODEL_NAME = "vosk-model-small-tr-0.3"


def settings_path() -> Path:
    app_data = os.environ.get("APPDATA")
    root = Path(app_data) if app_data else Path.home() / ".config"
    return root / "CompAssistant" / "settings.json"


def default_vosk_model_directory() -> str:
    return str(settings_path().parent / "models" / DEFAULT_VOSK_MODEL_NAME)


def validate_site(value: str) -> str:
    site = value.strip()
    parsed = urlparse(site)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Geçerli bir http/https adresi girin: {site}")
    return site


@dataclass
class Settings:
    command_wait_seconds: int = DEFAULT_WAIT_SECONDS
    websites: list[str] = field(default_factory=list)
    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS
    block_size: int = DEFAULT_BLOCK_SIZE
    input_device: int | str | None = None
    dtype: str = DEFAULT_DTYPE
    vosk_model_directory: str = field(default_factory=default_vosk_model_directory)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        target = path or settings_path()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            wait_seconds = int(data.get("command_wait_seconds", DEFAULT_WAIT_SECONDS))
            wait_seconds = max(MIN_WAIT_SECONDS, min(MAX_WAIT_SECONDS, wait_seconds))
            websites = []
            for entry in data.get("websites", []):
                try:
                    site = validate_site(str(entry))
                except ValueError:
                    continue
                if site not in websites:
                    websites.append(site)
            sample_rate = _positive_int(data.get("sample_rate"), DEFAULT_SAMPLE_RATE)
            channels = _positive_int(data.get("channels"), DEFAULT_CHANNELS)
            block_size = _positive_int(data.get("block_size"), DEFAULT_BLOCK_SIZE)
            dtype = str(data.get("dtype", DEFAULT_DTYPE)).casefold()
            if dtype not in SUPPORTED_AUDIO_DTYPES:
                dtype = DEFAULT_DTYPE
            input_device = data.get("input_device")
            if isinstance(input_device, bool) or not isinstance(input_device, (int, str, type(None))):
                input_device = None
            elif isinstance(input_device, int) and input_device < 0:
                input_device = None
            elif isinstance(input_device, str) and not input_device.strip():
                input_device = None
            model_directory = data.get("vosk_model_directory")
            if not isinstance(model_directory, str) or not model_directory.strip():
                model_directory = default_vosk_model_directory()
            return cls(
                command_wait_seconds=wait_seconds,
                websites=websites,
                sample_rate=sample_rate,
                channels=channels,
                block_size=block_size,
                input_device=input_device,
                dtype=dtype,
                vosk_model_directory=model_directory,
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        target = path or settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "command_wait_seconds": max(
                MIN_WAIT_SECONDS, min(MAX_WAIT_SECONDS, int(self.command_wait_seconds))
            ),
            "websites": list(dict.fromkeys(validate_site(site) for site in self.websites)),
            "sample_rate": _positive_int(self.sample_rate, DEFAULT_SAMPLE_RATE),
            "channels": _positive_int(self.channels, DEFAULT_CHANNELS),
            "block_size": _positive_int(self.block_size, DEFAULT_BLOCK_SIZE),
            "input_device": self.input_device,
            "dtype": self.dtype if self.dtype in SUPPORTED_AUDIO_DTYPES else DEFAULT_DTYPE,
            "vosk_model_directory": (
                self.vosk_model_directory.strip()
                if self.vosk_model_directory.strip()
                else default_vosk_model_directory()
            ),
        }
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)


def _positive_int(value: object, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return fallback
    return value
