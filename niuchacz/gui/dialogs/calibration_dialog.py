"""Kreator kalibracji wyświetlacza: odczyt z karty + napis wpisany przez użytkownika."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from niuchacz.i18n import t
from niuchacz.decoding.calibration import Sample, auto_rank, solve, summarize
from niuchacz.protocol import commands


class CalibrationDialog(tk.Toplevel):
    def __init__(self, master, controller):
        super().__init__(master)
        self.title(t("calib.title"))
        self.resizable(False, False)
        self.transient(master)
        self.controller = controller
        self.samples: list[Sample] = []
        self.solutions = []
        self._ticks = 0
        controller.calibrating = True
        self.bind("<Destroy>", self._on_destroy)

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both")
        ttk.Label(frm, justify="left", wraplength=420, text=t("calib.help")).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(frm, text=t("calib.lines_now")).grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.raw_var = tk.StringVar(value="–")
        ttk.Label(frm, textvariable=self.raw_var, font=("TkFixedFont", 11)).grid(row=1, column=1, columnspan=2,
                                                                                 sticky="w", pady=(10, 0))
        ttk.Label(frm, text=t("calib.i_see")).grid(row=2, column=0, sticky="w", pady=6)
        self.text_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.text_var, width=10).grid(row=2, column=1, sticky="w", pady=6)
        ttk.Button(frm, text=t("calib.add"), command=self._add).grid(row=2, column=2, sticky="w", pady=6)

        self.listbox = tk.Listbox(frm, height=5, width=52)
        self.listbox.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.listbox.bind("<Double-Button-1>", self._remove_selected)
        ttk.Label(frm, text=t("calib.dblclick"), foreground="#777").grid(
            row=6, column=0, columnspan=3, sticky="w")
        self.result_var = tk.StringVar(value=t("calib.no_samples"))
        ttk.Label(frm, textvariable=self.result_var, wraplength=420, justify="left").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=8)
        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=3, sticky="e")
        self.frames_var = tk.StringVar(value="")
        ttk.Label(btns, textvariable=self.frames_var).pack(side="left", padx=8)
        ttk.Button(btns, text=t("calib.auto"), command=self._auto).pack(side="left", padx=4)
        ttk.Button(btns, text=t("calib.clear"), command=self._clear).pack(side="left", padx=4)
        self.apply_btn = ttk.Button(btns, text=t("calib.apply"), command=self._apply, state="disabled")
        self.apply_btn.pack(side="left", padx=4)
        ttk.Button(btns, text=t("btn.close"), command=self.destroy).pack(side="left", padx=4)
        self._tick()

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self.controller.calibrating = False

    def _tick(self) -> None:
        if self._ticks % 7 == 0:
            # ESP32 wysyła ramkę tylko przy zmianie – co ~2 s prosimy o bieżący stan
            self.controller.send(commands.ping())
        self._ticks += 1
        self.frames_var.set(t("calib.frames", n=len(self.controller.raw_history)))
        raw = self.controller.last_raw
        if raw:
            lit = [bin(~b & 0x7F).count("1") for b in raw]
            self.raw_var.set(" ".join(f"{b:08b}" for b in raw) + "   " + t("calib.lit", lit="/".join(map(str, lit))))
        else:
            self.raw_var.set(t("calib.no_data"))
        self.after(300, self._tick)

    def _add(self) -> None:
        raw = self.controller.last_raw
        text = self.text_var.get().upper()
        if not raw:
            messagebox.showwarning(t("calib.title"), t("calib.err_no_data"), parent=self)
            return
        if len(text) != len(raw):
            messagebox.showwarning(t("calib.title"), t("calib.err_len", n=len(raw)), parent=self)
            return
        for old in self.samples:
            if old.raw == tuple(raw) and old.text != text:
                messagebox.showwarning(t("calib.title"), t("calib.err_dup", text=old.text), parent=self)
                return
            if old.raw == tuple(raw):
                return
        self.samples.append(Sample(tuple(raw), text))
        self.listbox.insert("end", f"\"{text}\"  <-  " + " ".join(f"{b:02X}" for b in raw))
        self._solve()

    def _solve(self) -> None:
        try:
            self.solutions = solve(self.samples, digits=len(self.samples[0].raw))
        except ValueError as exc:
            self.samples.pop()
            self.listbox.delete("end")
            messagebox.showwarning(t("calib.title"), str(exc), parent=self)
            return
        self.result_var.set(summarize(self.solutions))
        self.apply_btn.config(state="normal" if len(self.solutions) == 1 else "disabled")

    def _remove_selected(self, _event=None) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        i = sel[0]
        self.listbox.delete(i)
        del self.samples[i]
        if self.samples:
            self._solve()
        else:
            self._clear()

    def _auto(self) -> None:
        frames = list(self.controller.raw_history)
        if len(frames) < 40:
            messagebox.showinfo(t("calib.title"), t("calib.err_few", n=len(frames)), parent=self)
            return
        samples = self.samples if self.samples and solve(self.samples, len(frames[0])) else None
        ranked = auto_rank(frames, samples, digits=len(frames[0]))
        if not ranked:
            self.result_var.set(t("calib.conflict"))
            return
        best, sol = ranked[0]
        second = ranked[1][0] if len(ranked) > 1 else 0.0
        pairs = ", ".join(f"{i + 1}={seg}" for i, seg in enumerate(sol.channel_to_segment[:7]))
        note = "" if samples else " " + t("calib.no_text_note")
        if best - second >= 0.02:
            self.solutions = [sol]
            self.result_var.set(t("calib.auto_ok", best=f"{best:.0%}", second=f"{second:.0%}",
                                  pairs=pairs, note=note))
            self.apply_btn.config(state="normal")
        else:
            self.result_var.set(t("calib.auto_close", best=f"{best:.0%}", second=f"{second:.0%}"))
            self.apply_btn.config(state="disabled")

    def _clear(self) -> None:
        self.samples.clear()
        self.solutions = []
        self.listbox.delete(0, "end")
        self.result_var.set(t("calib.no_samples"))
        self.apply_btn.config(state="disabled")

    def _apply(self) -> None:
        self.controller.apply_calibration(self.solutions[0])
        messagebox.showinfo(t("calib.title"), t("calib.applied"), parent=self)
        self.destroy()
