"""Search and launch discovered Windows applications from the tray."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .app_catalog import AppCatalog, Application


def show_apps() -> None:
    catalog = AppCatalog()
    catalog.refresh()

    root = tk.Tk()
    root.title("Uygulama bul ve aç")
    root.geometry("460x460")
    root.minsize(380, 340)
    root.configure(padx=16, pady=14)

    ttk.Label(root, text="Uygulama adı").pack(anchor="w")
    query = tk.StringVar()
    search = ttk.Entry(root, textvariable=query)
    search.pack(fill="x", pady=(5, 10))

    results = tk.Listbox(root, height=16, activestyle="dotbox")
    results.pack(fill="both", expand=True)
    status = ttk.Label(root, text=f"{len(catalog.applications)} uygulama bulundu")
    status.pack(anchor="w", pady=(8, 8))

    current: list[Application] = []

    def update_results(*_args) -> None:
        nonlocal current
        current = catalog.search(query.get())
        results.delete(0, "end")
        for app in current:
            results.insert("end", app.name)
        if not catalog.applications:
            status.config(text="Uygulama bulunamadı. Windows Başlat menüsünü kontrol edin.")
        elif current:
            status.config(text=f"{len(current)} eşleşme")
        else:
            status.config(text="Eşleşme bulunamadı")

    def launch_selected(_event=None) -> None:
        selection = results.curselection()
        if not selection:
            status.config(text="Önce listeden bir uygulama seçin")
            return
        app = current[selection[0]]
        try:
            app.launch()
        except (OSError, ValueError) as error:
            messagebox.showerror("Uygulama açılamadı", f"{app.name}: {error}", parent=root)
            return
        status.config(text=f"{app.name} başlatıldı")

    query.trace_add("write", update_results)
    results.bind("<Double-Button-1>", launch_selected)
    buttons = ttk.Frame(root)
    buttons.pack(fill="x")
    ttk.Button(buttons, text="Yenile", command=lambda: (catalog.refresh(), update_results())).pack(side="left")
    ttk.Button(buttons, text="Başlat", command=launch_selected).pack(side="right")
    ttk.Button(buttons, text="Kapat", command=root.destroy).pack(side="right", padx=(0, 8))

    update_results()
    search.focus_set()
    root.mainloop()
