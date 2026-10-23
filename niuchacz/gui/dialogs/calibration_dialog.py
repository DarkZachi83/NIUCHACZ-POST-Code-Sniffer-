"""Kreator kalibracji wyświetlacza: odczyt z karty + napis wpisany przez użytkownika."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from niuchacz.decoding.calibration import Sample, auto_rank, solve, summarize
from niuchacz.protocol import commands


class CalibrationDialog(tk.Toplevel):
    def __init__(self, master, controller):
        super().__init__(master)
        self.title("Kalibracja wyświetlacza")
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
        ttk.Label(frm, justify="left", wraplength=420, text=(
            "1. Połącz się z NIUCHACZEM i poczekaj, aż karta pokaże stały napis "
            "(np. płyta czeka na F1 albo jest w Setup).\n"
            "2. Wpisz dokładnie to, co widzisz na karcie (4 znaki, od lewej) i kliknij „Dodaj odczyt”.\n"
            "3. Zwykle wystarczą 2–3 różne napisy. Gdy wynik będzie jednoznaczny, kliknij „Zastosuj”.\n\n"
            "Kody migają za szybko? Wpisz jeden stały napis (np. z menu BIOS), uruchom płytę 2–3 razy "
            "od nowa i kliknij „Automatycznie” – program dobierze resztę z zapisanych ramek.")
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(frm, text="Linie DIG1–DIG4 teraz:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.raw_var = tk.StringVar(value="–")
        ttk.Label(frm, textvariable=self.raw_var, font=("TkFixedFont", 11)).grid(row=1, column=1, columnspan=2,
                                                                                 sticky="w", pady=(10, 0))
        ttk.Label(frm, text="Na karcie widzę:").grid(row=2, column=0, sticky="w", pady=6)
        self.text_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.text_var, width=10).grid(row=2, column=1, sticky="w", pady=6)
        ttk.Button(frm, text="Dodaj odczyt", command=self._add).grid(row=2, column=2, sticky="w", pady=6)

        self.listbox = tk.Listbox(frm, height=5, width=52)
        self.listbox.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.listbox.bind("<Double-Button-1>", self._remove_selected)
        ttk.Label(frm, text="(podwójne kliknięcie usuwa błędny odczyt)", foreground="#777").grid(
            row=6, column=0, columnspan=3, sticky="w")
        self.result_var = tk.StringVar(value="Brak odczytów.")
        ttk.Label(frm, textvariable=self.result_var, wraplength=420, justify="left").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=8)
        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=3, sticky="e")
        self.frames_var = tk.StringVar(value="")
        ttk.Label(btns, textvariable=self.frames_var).pack(side="left", padx=8)
        ttk.Button(btns, text="Automatycznie", command=self._auto).pack(side="left", padx=4)
        ttk.Button(btns, text="Wyczyść", command=self._clear).pack(side="left", padx=4)
        self.apply_btn = ttk.Button(btns, text="Zastosuj", command=self._apply, state="disabled")
        self.apply_btn.pack(side="left", padx=4)
        ttk.Button(btns, text="Zamknij", command=self.destroy).pack(side="left", padx=4)
        self._tick()

    def _on_destroy(self, event) -> None:
        if event.widget is self:
            self.controller.calibrating = False

    def _tick(self) -> None:
        if self._ticks % 7 == 0:
            # ESP32 wysyła ramkę tylko przy zmianie – co ~2 s prosimy o bieżący stan
            self.controller.send(commands.ping())
        self._ticks += 1
        self.frames_var.set(f"ramek: {len(self.controller.raw_history)}")
        raw = self.controller.last_raw
        if raw:
            lit = [bin(~b & 0x7F).count("1") for b in raw]
            self.raw_var.set(" ".join(f"{b:08b}" for b in raw) + "   świeci: " + "/".join(map(str, lit)))
        else:
            self.raw_var.set("– (brak danych z urządzenia)")
        self.after(300, self._tick)

    def _add(self) -> None:
        raw = self.controller.last_raw
        text = self.text_var.get().upper()
        if not raw:
            messagebox.showwarning("Kalibracja", "Brak danych z NIUCHACZA – połącz się najpierw.", parent=self)
            return
        if len(text) != len(raw):
            messagebox.showwarning("Kalibracja", f"Wpisz dokładnie {len(raw)} znaki (spacja = pusta cyfra).",
                                   parent=self)
            return
        for old in self.samples:
            if old.raw == tuple(raw) and old.text != text:
                messagebox.showwarning("Kalibracja", (
                    f"Ten sam stan linii był już zapisany jako „{old.text}”. Karta jeszcze się nie zmieniła "
                    "albo odczyt jest nieaktualny – poczekaj, aż napis na karcie będzie stały, i spróbuj ponownie."),
                    parent=self)
                return
            if old.raw == tuple(raw):
                return
        self.samples.append(Sample(tuple(raw), text))
        self.listbox.insert("end", f"„{text}”  ←  " + " ".join(f"{b:02X}" for b in raw))
        self._solve()

    def _solve(self) -> None:
        try:
            self.solutions = solve(self.samples, digits=len(self.samples[0].raw))
        except ValueError as exc:
            self.samples.pop()
            self.listbox.delete("end")
            messagebox.showwarning("Kalibracja", str(exc), parent=self)
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
            messagebox.showinfo("Kalibracja", f"Za mało danych ({len(frames)} ramek). Uruchom płytę od nowa "
                                "2–3 razy przy połączonym NIUCHACZU i spróbuj ponownie.", parent=self)
            return
        samples = self.samples if self.samples and solve(self.samples, len(frames[0])) else None
        ranked = auto_rank(frames, samples, digits=len(frames[0]))
        if not ranked:
            self.result_var.set("Brak wyniku – wpisane odczyty się wykluczają; kliknij Wyczyść.")
            return
        best, sol = ranked[0]
        second = ranked[1][0] if len(ranked) > 1 else 0.0
        pairs = ", ".join(f"{i + 1}={seg}" for i, seg in enumerate(sol.channel_to_segment[:7]))
        note = "" if samples else " (bez wpisanego napisu – kolejność cyfr bez zmian)"
        if best - second >= 0.02:
            self.solutions = [sol]
            self.result_var.set(f"Automatycznie: {best:.0%} cyfr czytelnych (następny wariant {second:.0%}). "
                                f"Kanały {pairs}{note}. Kliknij „Zastosuj”.")
            self.apply_btn.config(state="normal")
        else:
            self.result_var.set(f"Za mała różnica między wariantami ({best:.0%} vs {second:.0%}) – "
                                "zbierz więcej ramek (kolejne starty płyty) albo dodaj stały napis.")
            self.apply_btn.config(state="disabled")

    def _clear(self) -> None:
        self.samples.clear()
        self.solutions = []
        self.listbox.delete(0, "end")
        self.result_var.set("Brak odczytów.")
        self.apply_btn.config(state="disabled")

    def _apply(self) -> None:
        self.controller.apply_calibration(self.solutions[0])
        messagebox.showinfo("Kalibracja", "Zapisano. Kody są już dekodowane według nowej mapy.", parent=self)
        self.destroy()
