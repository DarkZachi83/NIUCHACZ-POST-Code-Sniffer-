"""Główne okno NIUCHACZA – składa widżety i menu, logikę deleguje do kontrolera."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from niuchacz import __version__
from niuchacz.app import event_bus as ev
from niuchacz.gui import theme
from niuchacz.gui.dialogs.golden_dialog import GoldenDialog
from niuchacz.gui.dialogs.report_window import ReportWindow
from niuchacz.gui.dialogs.settings_dialog import SettingsDialog
from niuchacz.gui.dialogs.calibration_dialog import CalibrationDialog
from niuchacz.gui.assets import Assets
from niuchacz.gui.gui_adapter import GuiAdapter
from niuchacz.gui.widgets.banner import Banner
from niuchacz.gui.widgets.code_display import CodeDisplay
from niuchacz.gui.widgets.diagnosis_panel import DiagnosisPanel
from niuchacz.gui.widgets.history_view import HistoryView
from niuchacz.gui.widgets.led_panel import LedPanel
from niuchacz.gui.widgets.toolbar import Toolbar
from niuchacz.protocol import commands


class MainWindow:
    def __init__(self, root: tk.Tk, controller, bus: ev.EventBus, paths: dict[str, Path]):
        self.root = root
        self.controller = controller
        self.paths = paths
        root.title(f"NIUCHACZ {__version__} – diagnostyka karty POST")
        self.assets = Assets(paths["assets"])
        self.assets.apply_icon(root)
        root.minsize(980, 640)
        root.protocol("WM_DELETE_WINDOW", self.close)

        self._build_menu()
        Toolbar(root, bus, controller, on_report=self._report_now).pack(fill="x")
        ttk.Separator(root).pack(fill="x")

        body = ttk.Frame(root, padding=8)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        # lewa kolumna: wyświetlacz, tuż pod nim diody (jak na karcie), niżej baner
        profile = controller.profile
        left = ttk.Frame(body)
        left.grid(row=0, column=0, rowspan=2, sticky="nsw")
        CodeDisplay(left, bus, profile.digits, profile.code_digits).pack(fill="x")
        LedPanel(left, bus).pack(fill="x")
        # expand=True bez fill: baner stoi na środku wolnego miejsca pod diodami
        Banner(left, self.assets.banner()).pack(expand=True)

        DiagnosisPanel(body, bus).grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        HistoryView(body, bus).grid(row=1, column=1, sticky="nsew", padx=(10, 0), pady=(10, 0))

        self.status = ttk.Label(root, text="Gotowy. Wybierz połączenie i kliknij Połącz.",
                                padding=(8, 3), foreground=theme.MUTED)
        self.status.pack(fill="x", side="bottom", before=body)   # przed body: nie zostanie ucięty
        bus.subscribe(ev.STATUS, lambda text: self.status.config(text=text))
        bus.subscribe(ev.REPLY, self._on_reply)
        bus.subscribe(ev.SESSION_END, self._on_session_end)
        root.bind_all("<Control-r>", lambda _e: self._report_now())
        self.report_window: ReportWindow | None = None
        self._manual_report = False

        self.adapter = GuiAdapter(root, controller)
        self.adapter.start()

    # ---------- menu ----------

    def _build_menu(self) -> None:
        bar = tk.Menu(self.root)
        m_file = tk.Menu(bar, tearoff=False)
        m_file.add_command(label="Zakończ sesję i pokaż raport", accelerator="Ctrl+R",
                           command=self._report_now)
        m_file.add_command(label="Eksportuj sekwencję CSV…", command=self._export_csv)
        m_file.add_separator()
        m_file.add_command(label="Wyjście", command=self.close)
        bar.add_cascade(label="Plik", menu=m_file)

        m_gold = tk.Menu(bar, tearoff=False)
        m_gold.add_command(label="Nagraj wzorzec z bieżącej sesji…",
                           command=lambda: GoldenDialog(self.root, self.controller, self.paths["golden"]))
        m_gold.add_command(label="Porównuj ze wzorcem…", command=self._load_golden)
        bar.add_cascade(label="Wzorce", menu=m_gold)

        m_dev = tk.Menu(bar, tearoff=False)
        m_dev.add_command(label="Ping", command=lambda: self.controller.send(commands.ping()))
        m_dev.add_command(label="Lista sesji na ESP32", command=self.controller.request_session_list)
        m_dev.add_command(label="Pobierz sesję z ESP32…", command=self._get_session)
        m_dev.add_command(label="Usuń sesje z ESP32", command=self._clear_sessions)
        bar.add_cascade(label="Urządzenie", menu=m_dev)

        m_tools = tk.Menu(bar, tearoff=False)
        m_tools.add_command(label="Ustawienia…", command=lambda: SettingsDialog(self.root, self.controller))
        m_tools.add_command(label="Kalibracja wyświetlacza…",
                            command=lambda: CalibrationDialog(self.root, self.controller))
        m_tools.add_command(label="Przeładuj bazę kodów",
                            command=lambda: self.controller.reload_codes(self.paths["codes"]))
        bar.add_cascade(label="Narzędzia", menu=m_tools)
        self.root.config(menu=bar)

    # ---------- akcje ----------

    def _report_now(self) -> None:
        self._manual_report = True
        self.controller.finish_session_now()

    def _on_session_end(self, session) -> None:
        manual, self._manual_report = self._manual_report, False
        if not manual and getattr(self.controller, "calibrating", False):
            return   # w trakcie kalibracji raporty nie wyskakują
        if not manual and not self.controller.settings.get("report_auto_open", True):
            self.status.config(text=f"Sesja {session.session_id} zakończona: {session.result} "
                                    "(raport: Plik → Zakończ sesję i pokaż raport)")
            return
        win = self.report_window
        if win is not None and win.winfo_exists():
            if win.session is session:
                win.lift()
            else:
                win.offer_newer(session)
                win.lift()
            return
        self.report_window = ReportWindow(self.root, self.controller, self.paths["reports"], session)

    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialdir=self.paths["reports"], initialfile="sekwencja_post.csv")
        if path:
            self.controller.export_csv(Path(path))

    def _load_golden(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Wzorzec", "*.json")], initialdir=self.paths["golden"])
        if path:
            try:
                self.controller.load_golden(Path(path))
            except (ValueError, TypeError, KeyError) as exc:
                messagebox.showerror("Wzorzec", f"Nie można wczytać wzorca:\n{exc}")

    def _get_session(self) -> None:
        sid = simpledialog.askinteger("Pobierz sesję", "Numer sesji na ESP32:", parent=self.root, minvalue=1)
        if sid:
            self.controller.request_session(sid)

    def _clear_sessions(self) -> None:
        if messagebox.askyesno("ESP32", "Usunąć wszystkie sesje zapisane na ESP32?"):
            self.controller.send(commands.clear_sessions())

    def _on_reply(self, reply) -> None:
        if reply.command == "list_sessions":
            ids = reply.data.get("ids", [])
            messagebox.showinfo("Sesje na ESP32", "Zapisane sesje: " + (", ".join(map(str, ids)) or "brak"))
        else:
            self.status.config(text=f"Odpowiedź ESP32 na '{reply.command}': {reply.data}")

    def close(self) -> None:
        self.adapter.stop()
        self.controller.disconnect()
        self.root.destroy()
