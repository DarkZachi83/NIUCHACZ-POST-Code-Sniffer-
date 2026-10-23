"""Okno raportu po zakończeniu sesji: pola serwisanta + podgląd pliku .txt.

Podgląd to dokładnie ten tekst, który trafi do pliku i na drukarkę.
Okno jest jedno: gdy w trakcie jego otwarcia zakończy się kolejna sesja,
nie nadpisujemy wpisanych uwag, tylko pokazujemy pasek „Pokaż nowszą”.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from niuchacz.app.printing import PrintError
from niuchacz.gui import theme
from niuchacz.session.report import ReportMeta, default_filename


class ReportWindow(tk.Toplevel):
    def __init__(self, master, controller, reports_dir: Path, session):
        super().__init__(master)
        self.controller = controller
        self.reports_dir = Path(reports_dir)
        self.session = session
        self.saved_path: Path | None = None
        self.geometry("900x720")
        self.minsize(760, 560)

        meta = controller.default_report_meta()
        self.vars = {
            "repair_no": tk.StringVar(value=meta.repair_no),
            "board": tk.StringVar(value=meta.board),
            "owner": tk.StringVar(value=meta.owner),
            "technician": tk.StringVar(value=meta.technician),
        }

        # --- pasek „nowsza sesja” (ukryty) ---
        self.newer = tk.Frame(self, bg="#fff3cd")
        self.newer_label = tk.Label(self.newer, bg="#fff3cd", font=theme.FONT_UI)
        self.newer_label.pack(side="left", padx=8, pady=4)
        self._newer_session = None
        ttk.Button(self.newer, text="Pokaż nowszą", command=self._show_newer).pack(side="right", padx=8, pady=4)

        # --- pola serwisanta ---
        form = ttk.LabelFrame(self, text="Dane naprawy", padding=8)
        form.pack(fill="x", padx=10, pady=(10, 6))
        labels = (("repair_no", "Nr naprawy"), ("board", "Płyta"), ("owner", "Właściciel / opis"),
                  ("technician", "Serwisant"))
        for i, (key, label) in enumerate(labels):
            r, c = divmod(i, 2)
            ttk.Label(form, text=label).grid(row=r, column=c * 2, sticky="w", padx=(0 if c == 0 else 16, 6), pady=3)
            e = ttk.Entry(form, textvariable=self.vars[key], width=34)
            e.grid(row=r, column=c * 2 + 1, sticky="ew", pady=3)
            self.vars[key].trace_add("write", lambda *_: self._refresh())
        ttk.Label(form, text="Uwagi").grid(row=2, column=0, sticky="nw", pady=3)
        self.notes = tk.Text(form, height=3, wrap="word", font=theme.FONT_UI)
        self.notes.grid(row=2, column=1, columnspan=3, sticky="ew", pady=3)
        self.notes.bind("<KeyRelease>", lambda _e: self._refresh())
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        # --- podgląd ---
        prev = ttk.LabelFrame(self, text="Podgląd pliku .txt", padding=6)
        prev.pack(fill="both", expand=True, padx=10, pady=6)
        self.preview = tk.Text(prev, wrap="none", font=theme.FONT_MONO, state="disabled",
                               bg="#fbfbf8", relief="flat", padx=8, pady=6)
        ys = ttk.Scrollbar(prev, orient="vertical", command=self.preview.yview)
        self.preview.configure(yscrollcommand=ys.set)
        self.preview.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")

        # --- przyciski ---
        bar = ttk.Frame(self, padding=(10, 4, 10, 10))
        bar.pack(fill="x")
        self.saved_label = ttk.Label(bar, text="Nie zapisano", foreground=theme.MUTED)
        self.saved_label.pack(side="left")
        ttk.Button(bar, text="Zamknij", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Kopiuj", command=self._copy).pack(side="right", padx=6)
        ttk.Button(bar, text="Drukuj", command=self._print).pack(side="right")
        ttk.Button(bar, text="Zapisz TXT…", command=self._save_as).pack(side="right", padx=6)

        self.bind("<Control-s>", lambda _e: self._save_as())
        self.bind("<Control-p>", lambda _e: self._print())
        self._load_session(session)

    # ---------- dane ----------

    def _meta(self) -> ReportMeta:
        v = {k: var.get().strip() for k, var in self.vars.items()}
        return ReportMeta(notes=self.notes.get("1.0", "end").strip(), **v)

    def text(self) -> str:
        return self.controller.report_text(self.session, self._meta())

    def _load_session(self, session) -> None:
        self.session = session
        self.saved_path = None
        self.title(f"Raport – sesja {session.session_id} · {session.result or ''}")
        self.saved_label.config(text="Nie zapisano", foreground=theme.MUTED)
        self.newer.pack_forget()
        self._refresh()

    def _refresh(self) -> None:
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", self.text())
        self.preview.config(state="disabled")
        if self.saved_path is not None:
            self.saved_label.config(text=f"Zmiany od zapisu {self.saved_path.name} – zapisz ponownie lub drukuj",
                                    foreground=theme.HANG)

    def offer_newer(self, session) -> None:
        """Kolejna sesja zakończona, a to okno jest otwarte."""
        self._newer_session = session
        self.newer_label.config(text=f"Zakończono nowszą sesję {session.session_id}: {session.result}")
        self.newer.pack(fill="x", before=self.winfo_children()[1])

    def _show_newer(self) -> None:
        if self._newer_session is not None:
            self._load_session(self._newer_session)
            self._newer_session = None

    # ---------- akcje ----------

    def _remember_technician(self) -> None:
        tech = self.vars["technician"].get().strip()
        if tech != self.controller.settings.get("technician", ""):
            self.controller.update_settings({"technician": tech})

    def _ask_path(self) -> Path | None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        name = default_filename(self.session, self._meta())
        path = filedialog.asksaveasfilename(parent=self, initialdir=self.reports_dir, initialfile=name,
                                            defaultextension=".txt", filetypes=[("Raport tekstowy", "*.txt")])
        return Path(path) if path else None

    def _save_as(self) -> None:
        path = self._ask_path()
        if not path:
            return
        self.controller.save_report(path, self.text())
        self._mark_saved(path)

    def _print(self) -> None:
        # drukujemy zapisany plik; jeśli go jeszcze nie ma – najpierw pytamy, gdzie zapisać
        path = self.saved_path or self._ask_path()
        if not path:
            return
        try:
            self.controller.print_report(path, self.text())
        except PrintError as exc:
            messagebox.showerror("Drukowanie", f"{exc}\n\nPlik zapisano: {path}", parent=self)
        self._mark_saved(path)

    def _mark_saved(self, path: Path) -> None:
        self.saved_path = path
        self._remember_technician()
        self.saved_label.config(text=f"Zapisano: {path}", foreground=theme.OK)

    def _copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.text())
        self.saved_label.config(text="Skopiowano do schowka", foreground=theme.OK)
