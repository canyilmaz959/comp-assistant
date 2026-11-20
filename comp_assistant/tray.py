"""Windows system-tray entry point for the Comp Assistant shell."""
from __future__ import annotations

import threading

from .config import Settings
from .microphone import MicrophoneManager
from .runtime import AssistantRuntime
from .voice import AudioService, MockSpeechSynthesizer, MockWakeWordDetector
from .vosk_recognizer import VoskSpeechRecognizer


class CompAssistantApp:
    def __init__(self) -> None:
        self.settings = Settings.load()
        self.microphone_manager = MicrophoneManager(
            sample_rate=self.settings.sample_rate,
            channels=self.settings.channels,
            block_size=self.settings.block_size,
            input_device=self.settings.input_device,
            dtype=self.settings.dtype,
        )
        self.audio_service = AudioService(
            MockWakeWordDetector(),
            VoskSpeechRecognizer(
                self.microphone_manager,
                self.settings.vosk_model_directory,
                sample_rate=self.settings.sample_rate,
                dtype=self.settings.dtype,
                channels=self.settings.channels,
            ),
            MockSpeechSynthesizer(),
        )
        self.runtime = AssistantRuntime(
            self.settings.command_wait_seconds,
            audio_service=self.audio_service,
            microphone_manager=self.microphone_manager,
        )
        self.icon = None

    def run(self) -> None:
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError as error:
            raise RuntimeError(
                "Tepsi arayüzü için bağımlılıkları yükleyin: "
                "pip install -r requirements-tray.txt"
            ) from error

        menu = pystray.Menu(
            pystray.MenuItem("Uygulama bul ve aç", self._open_apps),
            pystray.MenuItem("Ayarlar", self._open_settings),
            pystray.MenuItem(
                "Asistan etkin",
                self._toggle_enabled,
                checked=lambda item: self.runtime.is_enabled,
            ),
            pystray.MenuItem("Tamamen kapat", self._shutdown),
        )
        self.icon = pystray.Icon(
            "comp-assistant",
            self._make_icon(Image, ImageDraw),
            "Comp Assistant",
            menu,
        )
        self.icon.run()

    @staticmethod
    def _make_icon(image_module, draw_module):
        image = image_module.new("RGB", (64, 64), (18, 28, 42))
        draw = draw_module.Draw(image)
        draw.ellipse((5, 5, 59, 59), fill=(27, 190, 170))
        draw.text((22, 18), "C", fill=(18, 28, 42))
        return image

    def _open_apps(self, icon, item) -> None:
        threading.Thread(target=self._show_apps, daemon=True).start()

    @staticmethod
    def _show_apps() -> None:
        from .apps_window import show_apps

        show_apps()

    def _open_settings(self, icon, item) -> None:
        threading.Thread(target=self._show_settings, daemon=True).start()

    def _show_settings(self) -> None:
        from .settings_window import show_settings

        show_settings(self.settings, self._save_settings)

    def _save_settings(self, settings: Settings) -> None:
        self.settings = settings
        self.runtime.update_command_wait_seconds(settings.command_wait_seconds)

    def _toggle_enabled(self, icon, item) -> None:
        self.runtime.set_enabled(not self.runtime.is_enabled)

    def _shutdown(self, icon, item) -> None:
        self.runtime.shutdown()
        icon.stop()
