"""Discover and safely launch apps registered in the Windows user environment."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import os
from pathlib import Path
import re
import subprocess
import unicodedata


@dataclass(frozen=True)
class Application:
    name: str
    target: Path
    kind: str

    def launch(self) -> None:
        if self.kind == "shortcut":
            if os.name != "nt":
                raise OSError("Windows kısayolları yalnızca Windows'ta açılabilir.")
            os.startfile(str(self.target))  # type: ignore[attr-defined]
        elif self.kind == "executable":
            subprocess.Popen([str(self.target)], close_fds=True)
        else:
            raise ValueError(f"Desteklenmeyen uygulama türü: {self.kind}")


def _normalize(value: str) -> str:
    value = value.casefold().replace("ı", "i")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", value))


class AppCatalog:
    """Builds a catalog from Start Menu shortcuts and Windows App Paths.

    The catalog never executes a command spoken by the user. A launch target
    must first come from a Windows shortcut or a registered executable path.
    """

    def __init__(self) -> None:
        self._applications: list[Application] = []

    @property
    def applications(self) -> tuple[Application, ...]:
        return tuple(self._applications)

    def refresh(self) -> tuple[Application, ...]:
        discovered: dict[tuple[str, str], Application] = {}
        if os.name == "nt":
            for app in self._start_menu_apps():
                discovered[(app.name.casefold(), os.path.normcase(str(app.target)))] = app
            for app in self._app_paths():
                discovered[(app.name.casefold(), os.path.normcase(str(app.target)))] = app
        self._applications = sorted(discovered.values(), key=lambda app: app.name.casefold())
        return self.applications

    def search(self, query: str) -> list[Application]:
        query_text = _normalize(query)
        if not query_text:
            return list(self.applications)
        query_tokens = set(query_text.split())
        ranked: list[tuple[float, Application]] = []
        for app in self._applications:
            name_text = _normalize(app.name)
            name_tokens = set(name_text.split())
            if query_text == name_text:
                score = 1.0
            elif query_text in name_text:
                score = 0.96
            elif query_tokens and query_tokens.issubset(name_tokens):
                score = 0.9 + 0.09 * (len(query_tokens) / max(len(name_tokens), 1))
            else:
                score = SequenceMatcher(None, query_text, name_text).ratio()
            if score >= 0.48:
                ranked.append((score, app))
        ranked.sort(key=lambda result: (-result[0], result[1].name.casefold()))
        return [app for _, app in ranked]

    def resolve(self, query: str) -> tuple[str, list[Application]]:
        """Return ('not_found', []), ('match', [app]), or ('ambiguous', options)."""
        results = self.search(query)
        if not results:
            return "not_found", []
        query_text = _normalize(query)
        top_score = self._score(query_text, results[0].name)
        if top_score < 0.62:
            return "not_found", []
        close = [app for app in results if top_score - self._score(query_text, app.name) <= 0.06]
        if len(close) > 1:
            return "ambiguous", close
        return "match", [results[0]]

    @staticmethod
    def _score(query_text: str, name: str) -> float:
        name_text = _normalize(name)
        query_tokens = set(query_text.split())
        name_tokens = set(name_text.split())
        if query_text == name_text:
            return 1.0
        if query_text in name_text:
            return 0.96
        if query_tokens and query_tokens.issubset(name_tokens):
            return 0.9 + 0.09 * (len(query_tokens) / max(len(name_tokens), 1))
        return SequenceMatcher(None, query_text, name_text).ratio()

    @staticmethod
    def _start_menu_apps() -> list[Application]:
        roots = []
        for env_name in ("APPDATA", "PROGRAMDATA"):
            base = os.environ.get(env_name)
            if base:
                roots.append(Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
        results = []
        for root in roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.casefold() not in {".lnk", ".exe"}:
                    continue
                kind = "shortcut" if path.suffix.casefold() == ".lnk" else "executable"
                results.append(Application(name=path.stem, target=path, kind=kind))
        return results

    @staticmethod
    def _app_paths() -> list[Application]:
        if os.name != "nt":
            return []
        import winreg

        root_key = winreg.HKEY_CURRENT_USER
        machine_key = winreg.HKEY_LOCAL_MACHINE
        base_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        views = (
            getattr(winreg, "KEY_WOW64_64KEY", 0),
            getattr(winreg, "KEY_WOW64_32KEY", 0),
        )
        results = []
        seen = set()
        for hive in (root_key, machine_key):
            for view in views:
                try:
                    with winreg.OpenKey(hive, base_path, 0, winreg.KEY_READ | view) as key:
                        count = winreg.QueryInfoKey(key)[0]
                        subkeys = [winreg.EnumKey(key, index) for index in range(count)]
                except OSError:
                    continue
                for subkey in subkeys:
                    try:
                        with winreg.OpenKey(hive, base_path + "\\" + subkey, 0, winreg.KEY_READ | view) as key:
                            raw_path, _ = winreg.QueryValueEx(key, None)
                    except OSError:
                        continue
                    executable = Path(os.path.expandvars(str(raw_path).strip().strip('"')))
                    identity = os.path.normcase(str(executable))
                    if identity in seen or executable.suffix.casefold() != ".exe" or not executable.is_file():
                        continue
                    seen.add(identity)
                    results.append(
                        Application(name=Path(subkey).stem.replace(".", " "), target=executable, kind="executable")
                    )
        return results
