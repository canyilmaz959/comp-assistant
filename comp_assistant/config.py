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


def settings_path() -> Path:
    app_data = os.environ.get("APPDATA")
    root = Path(app_data) if app_data else Path.home() / ".config"
    return root / "CompAssistant" / "settings.json"


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
            return cls(command_wait_seconds=wait_seconds, websites=websites)
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
        }
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
