"""Pasek nagrywania: przycisk REC (F9), stan nagrania i decyzja „Nagrać kolejny?”.

Stan musi być czytelny z daleka – serwisant stoi przy płycie, nie przy ekranie:
szary REC = nic nie nagrywa, migający czerwony = czeka na reset płyty,
czerwony NAGRYWA = nagrywa, zielony pasek = zapisano.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from niuchacz.app import event_bus as ev
from niuchacz.gui import theme
from niuchacz.i18n import t
from niuchacz.session import recording as rec_mod

REC_RED = "#d62828"
REC_GREY = "#7a7a7a"
DONE_BG = "#e3f4e6"
WARN_BG = "#fff3cd"


class RecPanel(ttk.Frame):
    def __init__(self, master, bus, controller, on_show_report):
        super().__init__(master, padding=(8, 0, 8, 4))
        self.controller = controller
        self.on_show_report = on_show_report
        self._blink_job = None
        self._blink_on = False
        self._last_rec = None

        row = ttk.Frame(self)
        row.pack(fill="x")
        self.button = tk.Button(row, width=16, font=theme.FONT_BOLD, relief="raised", bd=2,
                                command=self.toggle, cursor="hand2")
        self.button.pack(side="left")
        self.state_label = tk.Label(row, font=theme.FONT_BOLD, anchor="w")
        self.state_label.pack(side="left", padx=10)
        ttk.Button(row, text=t("rec.save_last"), command=controller.save_last_run).pack(side="right")

        # pasek decyzji po zakończonym nagraniu (ukryty)
        self.bar = tk.Frame(self, bg=DONE_BG, padx=8, pady=6)
        self.bar_label = tk.Label(self.bar, bg=DONE_BG, font=theme.FONT_UI, justify="left", anchor="w",
                                  wraplength=640)
        self.bar_label.pack(side="left", fill="x", expand=True)
        self.btn_close = ttk.Button(self.bar, text=t("rec.finish"), command=self._close_bar)
        self.btn_close.pack(side="right", padx=(4, 0))
        self.btn_next = ttk.Button(self.bar, text=t("rec.next"), command=self._next)
        self.btn_next.pack(side="right", padx=4)
        self.btn_report = ttk.Button(self.bar, text=t("rec.show_report"), command=self._show)
        self.btn_report.pack(side="right", padx=4)

        bus.subscribe(ev.REC, self._on_rec)
        rec = controller.rec
        self._on_rec((rec.state, rec.current if rec.state == rec_mod.RECORDING else rec.last), restore=True)

    # ---------- akcje ----------

    def toggle(self) -> None:
        """F9 / przycisk: REC -> czekaj na reset; w trakcie: STOP; przy czekaniu: anuluj."""
        state = self.controller.rec.state
        if state in (rec_mod.IDLE, rec_mod.DONE):
            self._close_bar()
            self.controller.arm_recording()
        else:
            self.controller.stop_recording()

    def _next(self) -> None:
        self._close_bar()
        self.controller.arm_recording()

    def _show(self) -> None:
        if self._last_rec is not None:
            self.on_show_report(self._last_rec)

    def _close_bar(self) -> None:
        self.bar.pack_forget()

    # ---------- wygląd ----------

    def _stop_blink(self) -> None:
        if self._blink_job is not None:
            self.after_cancel(self._blink_job)
            self._blink_job = None

    def _blink(self) -> None:
        self._blink_on = not self._blink_on
        self.button.config(bg=REC_RED if self._blink_on else "#f2c4c4")
        self._blink_job = self.after(500, self._blink)

    def _on_rec(self, payload, restore: bool = False) -> None:
        state, rec = payload
        self._stop_blink()
        if state == rec_mod.ARMED:
            self.button.config(text=t("rec.btn_cancel"), fg="white", activebackground=REC_RED)
            self.state_label.config(text=t("rec.label_armed"), fg=REC_RED)
            self._blink()
        elif state == rec_mod.RECORDING:
            self.button.config(text=t("rec.btn_stop"), bg=REC_RED, fg="white", activebackground=REC_RED)
            n = len(rec.starts) if rec else 1
            self.state_label.config(text=t("rec.label_recording", n=n), fg=REC_RED)
        else:
            self.button.config(text=t("rec.btn_rec"), bg="#e6e6e6", fg=REC_GREY, activebackground="#d6d6d6")
            self.state_label.config(text="", fg=REC_GREY)
            if state in (rec_mod.DONE, "saved") and rec is not None and not restore:
                self._show_bar(rec, ask_next=(state == rec_mod.DONE))

    def _show_bar(self, rec, ask_next: bool) -> None:
        self._last_rec = rec
        warn = rec.end_key in ("rec.end_loop", "rec.end_stop")
        bg = WARN_BG if warn else DONE_BG
        name = rec.saved[0].name if rec.saved else "-"
        text = t("rec.bar_saved", result=rec.result, name=name)
        if ask_next:
            text += "\n" + t("rec.bar_ask_next")
        for w in (self.bar, self.bar_label):
            w.config(bg=bg)
        self.bar_label.config(text=text)
        if ask_next:
            self.btn_next.pack(side="right", padx=4, before=self.btn_report)
        else:
            self.btn_next.pack_forget()
        self.bar.pack(fill="x", pady=(4, 0))
