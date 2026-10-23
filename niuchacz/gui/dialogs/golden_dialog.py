"""Okno zapisu złotego przebiegu: metadane płyty i rodzaj przebiegu."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

FAULTS = ("", "brak RAM", "brak karty graficznej", "brak klawiatury", "wyjęta bateria / wyczyszczony CMOS", "inna")


class GoldenDialog(tk.Toplevel):
    def __init__(self, master, controller, golden_dir: Path):
        super().__init__(master)
        self.title("Nagraj wzorzec")
        self.resizable(False, False)
        self.transient(master)
        self.controller = controller
        self.golden_dir = golden_dir
        fields = (("board", "Model i rewizja płyty *"), ("bios_version", "Wersja BIOS"),
                  ("chipset", "Chipset"), ("cpu", "Procesor"), ("ram", "Pamięć"),
                  ("video", "Karta graficzna"), ("author", "Autor"), ("notes", "Uwagi"))
        self.vars = {k: tk.StringVar(value=controller.settings.get("board", "") if k == "board" else "")
                     for k, _ in fields}
        frm = ttk.Frame(self, padding=12)
        frm.pack()
        for r, (key, label) in enumerate(fields):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Entry(frm, textvariable=self.vars[key], width=36).grid(row=r, column=1, padx=(8, 0), pady=2)
        ttk.Label(frm, text="Wywołana usterka").grid(row=len(fields), column=0, sticky="w", pady=2)
        self.fault = ttk.Combobox(frm, values=FAULTS, width=34)
        self.fault.set("")
        self.fault.grid(row=len(fields), column=1, padx=(8, 0), pady=2)
        ttk.Label(frm, text="Puste pole usterki = przebieg sprawnej płyty.",
                  foreground="#7a7a7a").grid(row=len(fields) + 1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        btns = ttk.Frame(frm)
        btns.grid(row=len(fields) + 2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Anuluj", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="Zapisz", command=self._save).pack(side="right", padx=6)
        self.grab_set()

    def _save(self) -> None:
        meta = {k: v.get().strip() for k, v in self.vars.items()}
        if not meta["board"]:
            messagebox.showwarning("Wzorzec", "Podaj model płyty.", parent=self)
            return
        if not self.controller.recorder.current.items:
            messagebox.showwarning("Wzorzec", "Bieżąca sesja nie ma żadnych kodów.", parent=self)
            return
        meta["induced_fault"] = self.fault.get().strip()
        self.golden_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in meta["board"])[:40]
        suffix = "_" + "".join(c if c.isalnum() else "_" for c in meta["induced_fault"]) if meta["induced_fault"] else ""
        path = filedialog.asksaveasfilename(parent=self, initialdir=self.golden_dir,
                                            initialfile=f"{safe}{suffix}.json",
                                            defaultextension=".json", filetypes=[("Wzorzec", "*.json")])
        if path:
            self.controller.save_golden(Path(path), **meta)
            self.destroy()
