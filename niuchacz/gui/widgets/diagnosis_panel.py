"""Panel diagnozy: opis bieżącego kodu i wynik porównania ze wzorcem."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from niuchacz.app import event_bus as ev
from niuchacz.gui import theme


class DiagnosisPanel(ttk.LabelFrame):
    def __init__(self, master, bus: ev.EventBus):
        super().__init__(master, text="Diagnoza", padding=8)
        self.text = tk.Text(self, height=9, wrap="word", font=theme.FONT_UI, relief="flat",
                            padx=6, pady=6, state="disabled")
        self.text.pack(fill="both", expand=True)
        self.golden = ttk.Label(self, text="Wzorzec: nie wczytano", foreground=theme.MUTED,
                                wraplength=520, justify="left")
        self.golden.pack(fill="x", pady=(6, 0))
        bus.subscribe(ev.DIAGNOSIS, self._on_diagnosis)
        bus.subscribe(ev.GOLDEN, lambda text: self.golden.config(text=f"Wzorzec: {text}",
                                                                 foreground=theme.HANG if "zatrzymał" in text or "Rozbieżność" in text else theme.OK))

    def _on_diagnosis(self, payload) -> None:
        _diag, text = payload
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.config(state="disabled")
