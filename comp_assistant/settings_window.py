"""Tk settings window opened from the system tray."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from .config import MAX_WAIT_SECONDS, MIN_WAIT_SECONDS, Settings, validate_site


def show_settings(settings: Settings, on_save: Callable[[Settings], None]) -> None:
    root = tk.Tk()
    root.title("Comp Assistant Ayarları")
    root.resizable(False, False)
    root.geometry("440x410")
    root.configure(padx=18, pady=16)

    ttk.Label(root, text="Komut bekleme süresi (saniye)").pack(anchor="w")
    wait_value = tk.StringVar(value=str(settings.command_wait_seconds))
    ttk.Spinbox(
        root,
        from_=MIN_WAIT_SECONDS,
        to=MAX_WAIT_SECONDS,
        textvariable=wait_value,
        width=10,
    ).pack(anchor="w", pady=(6, 14))

    ttk.Label(root, text="Yönetilen siteler (her satıra bir http/https adresi)").pack(anchor="w")
    site_list = tk.Text(root, width=48, height=11, wrap="word")
    site_list.pack(fill="both", expand=True, pady=(6, 12))
    site_list.insert("1.0", "\n".join(settings.websites))

    buttons = ttk.Frame(root)
    buttons.pack(fill="x")

    def save() -> None:
        try:
            seconds = int(wait_value.get())
            if not MIN_WAIT_SECONDS <= seconds <= MAX_WAIT_SECONDS:
                raise ValueError(
                    f"Bekleme süresi {MIN_WAIT_SECONDS} ile {MAX_WAIT_SECONDS} arasında olmalı."
                )
            sites = []
            for raw_site in site_list.get("1.0", "end").splitlines():
                if raw_site.strip():
                    site = validate_site(raw_site)
                    if site not in sites:
                        sites.append(site)
            updated = Settings(
                command_wait_seconds=seconds,
                websites=sites,
                sample_rate=settings.sample_rate,
                channels=settings.channels,
                block_size=settings.block_size,
                input_device=settings.input_device,
                dtype=settings.dtype,
                vosk_model_directory=settings.vosk_model_directory,
                tts_enabled=settings.tts_enabled,
                tts_voice_id=settings.tts_voice_id,
                tts_rate=settings.tts_rate,
                tts_volume=settings.tts_volume,
            )
            updated.save()
            on_save(updated)
        except ValueError as error:
            messagebox.showerror("Ayarlar kaydedilemedi", str(error), parent=root)
            return
        root.destroy()

    ttk.Button(buttons, text="Kaydet", command=save).pack(side="right")
    ttk.Button(buttons, text="Kapat", command=root.destroy).pack(side="right", padx=(0, 8))
    root.mainloop()
