"""Okno ustawień: adres ESP32, port COM, płyta, progi czasowe."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from niuchacz.transport.serial_transport import available_ports


class SettingsDialog(tk.Toplevel):
    def __init__(self, master, controller):
        super().__init__(master)
        self.title("Ustawienia NIUCHACZA")
        self.resizable(False, False)
        self.transient(master)
        self.controller = controller
        s = controller.settings

        self.vars = {
            "host": tk.StringVar(value=s["tcp"]["host"]),
            "port": tk.StringVar(value=str(s["tcp"]["port"])),
            "com": tk.StringVar(value=s["serial"]["port"]),
            "board": tk.StringVar(value=s.get("board", "")),
            "hang": tk.StringVar(value=str(s.get("hang_seconds", 15))),
            "debounce": tk.StringVar(value=str(s.get("debounce_ms", 16))),
        }
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both")
        rows = (("Adres ESP32 (Wi-Fi)", "host"), ("Port TCP", "port"), ("Port COM (USB)", "com"),
                ("Badana płyta", "board"), ("Postój po [s]", "hang"), ("Filtr stabilności [ms]", "debounce"))
        for r, (label, key) in enumerate(rows):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=3)
            if key == "com":
                w = ttk.Combobox(frm, textvariable=self.vars[key], values=available_ports(), width=28)
            else:
                w = ttk.Entry(frm, textvariable=self.vars[key], width=30)
            w.grid(row=r, column=1, sticky="ew", padx=(8, 0), pady=3)
        self.auto_report = tk.BooleanVar(value=bool(s.get("report_auto_open", True)))
        ttk.Checkbutton(frm, text="Otwieraj okno raportu po zakończeniu sesji",
                        variable=self.auto_report).grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=(8, 0))
        btns = ttk.Frame(frm)
        btns.grid(row=len(rows) + 1, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Anuluj", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Zapisz", command=self._save).pack(side="right", padx=6)
        self.grab_set()

    def _save(self) -> None:
        v = {k: var.get().strip() for k, var in self.vars.items()}
        try:
            changes = {
                "tcp": {"host": v["host"], "port": int(v["port"])},
                "serial": {**self.controller.settings["serial"], "port": v["com"]},
                "board": v["board"],
                "hang_seconds": float(v["hang"]),
                "debounce_ms": int(v["debounce"]),
                "report_auto_open": bool(self.auto_report.get()),
            }
        except ValueError:
            messagebox.showerror("Ustawienia", "Port, czas i filtr muszą być liczbami.", parent=self)
            return
        self.controller.update_settings(changes)
        self.destroy()
