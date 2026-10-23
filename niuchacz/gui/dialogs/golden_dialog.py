"""Okno zapisu złotego przebiegu: metadane płyty i rodzaj przebiegu."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from niuchacz.i18n import t

# klucze – tekst w bieżącym języku trafia do pliku wzorca jako opis usterki
FAULTS = ("", "golden.fault_ram", "golden.fault_video", "golden.fault_keyboard", "golden.fault_cmos",
          "golden.fault_other")


class GoldenDialog(tk.Toplevel):
    def __init__(self, master, controller, golden_dir: Path):
        super().__init__(master)
        self.title(t("golden.title"))
        self.resizable(False, False)
        self.transient(master)
        self.controller = controller
        self.golden_dir = golden_dir
        fields = (("board", t("golden.board")), ("bios_version", t("golden.bios_version")),
                  ("chipset", t("golden.chipset")), ("cpu", t("golden.cpu")), ("ram", t("golden.ram")),
                  ("video", t("golden.video")), ("author", t("golden.author")), ("notes", t("golden.notes")))
        self.vars = {k: tk.StringVar(value=controller.settings.get("board", "") if k == "board" else "")
                     for k, _ in fields}
        frm = ttk.Frame(self, padding=12)
        frm.pack()
        for r, (key, label) in enumerate(fields):
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=2)
            ttk.Entry(frm, textvariable=self.vars[key], width=36).grid(row=r, column=1, padx=(8, 0), pady=2)
        ttk.Label(frm, text=t("golden.induced")).grid(row=len(fields), column=0, sticky="w", pady=2)
        self.fault = ttk.Combobox(frm, values=[t(k) if k else "" for k in FAULTS], width=34)
        self.fault.set("")
        self.fault.grid(row=len(fields), column=1, padx=(8, 0), pady=2)
        ttk.Label(frm, text=t("golden.empty_hint"),
                  foreground="#7a7a7a").grid(row=len(fields) + 1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        btns = ttk.Frame(frm)
        btns.grid(row=len(fields) + 2, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text=t("btn.cancel"), command=self.destroy).pack(side="right")
        ttk.Button(btns, text=t("btn.save"), command=self._save).pack(side="right", padx=6)
        self.grab_set()

    def _save(self) -> None:
        meta = {k: v.get().strip() for k, v in self.vars.items()}
        if not meta["board"]:
            messagebox.showwarning(t("dlg.golden_title"), t("golden.err_board"), parent=self)
            return
        if not self.controller.recorder.current.items:
            messagebox.showwarning(t("dlg.golden_title"), t("golden.err_empty"), parent=self)
            return
        meta["induced_fault"] = self.fault.get().strip()
        self.golden_dir.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in meta["board"])[:40]
        suffix = "_" + "".join(c if c.isalnum() else "_" for c in meta["induced_fault"]) if meta["induced_fault"] else ""
        path = filedialog.asksaveasfilename(parent=self, initialdir=self.golden_dir,
                                            initialfile=f"{safe}{suffix}.json",
                                            defaultextension=".json", filetypes=[(t("file.golden_type"), "*.json")])
        if path:
            self.controller.save_golden(Path(path), **meta)
            self.destroy()
