"""Główne okno NIUCHACZA – składa widżety i menu, logikę deleguje do kontrolera.

Zmiana języka przebudowuje całe okno (jak w Nornicy): stare widżety znikają razem
ze swoimi subskrypcjami szyny zdarzeń (BusScope), nowe powstają już w nowym języku.
"""
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
from niuchacz.i18n import LANGUAGES, current_language, set_language, t
from niuchacz.protocol import commands


class MainWindow:
    def __init__(self, root: tk.Tk, controller, bus: ev.EventBus, paths: dict[str, Path]):
        self.root = root
        self.controller = controller
        self.bus = bus
        self.paths = paths
        self.assets = Assets(paths["assets"])
        self.assets.apply_icon(root)
        root.minsize(980, 640)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind_all("<Control-r>", lambda _e: self._report_now())
        self.report_window: ReportWindow | None = None
        self._manual_report = False
        self.lang_var = tk.StringVar(value=current_language())
        self.scope: ev.BusScope | None = None

        self._build_ui()
        self.adapter = GuiAdapter(root, controller)
        self.adapter.start()

    # ---------- budowa i przebudowa ----------

    def _build_ui(self) -> None:
        root, controller = self.root, self.controller
        self.scope = scope = self.bus.scope()
        root.title(t("app.title", version=__version__))
        self._build_menu()
        self.toolbar = Toolbar(root, scope, controller, on_report=self._report_now)
        self.toolbar.pack(fill="x")
        ttk.Separator(root).pack(fill="x")

        body = ttk.Frame(root, padding=8)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        # lewa kolumna: wyświetlacz, tuż pod nim diody (jak na karcie), niżej baner
        profile = controller.profile
        left = ttk.Frame(body)
        left.grid(row=0, column=0, rowspan=2, sticky="nsw")
        CodeDisplay(left, scope, profile.digits, profile.code_digits).pack(fill="x")
        LedPanel(left, scope).pack(fill="x")
        # expand=True bez fill: baner stoi na środku wolnego miejsca pod diodami
        Banner(left, self.assets.banner()).pack(expand=True)

        DiagnosisPanel(body, scope).grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.history = HistoryView(body, scope)
        self.history.grid(row=1, column=1, sticky="nsew", padx=(10, 0), pady=(10, 0))

        self.status = ttk.Label(root, text=t("status.ready"), padding=(8, 3), foreground=theme.MUTED)
        self.status.pack(fill="x", side="bottom", before=body)   # przed body: nie zostanie ucięty
        scope.subscribe(ev.STATUS, lambda text: self.status.config(text=text))
        scope.subscribe(ev.REPLY, self._on_reply)
        scope.subscribe(ev.SESSION_END, self._on_session_end)

    def _rebuild(self) -> None:
        if self.scope is not None:
            self.scope.close()
        for child in self.root.winfo_children():
            child.destroy()          # razem z otwartymi oknami dialogowymi
        self.report_window = None
        self.root.config(menu="")
        self._build_ui()
        self.history.replay(self.controller.recorder.sessions, self.controller._stage_for)
        self.controller.refresh_language()

    def _switch_language(self) -> None:
        lang = set_language(self.lang_var.get())
        self.lang_var.set(lang)
        self.controller.update_settings({"language": lang})
        self._rebuild()

    # ---------- menu ----------

    def _build_menu(self) -> None:
        bar = tk.Menu(self.root)
        m_file = tk.Menu(bar, tearoff=False)
        m_file.add_command(label=t("menu.finish_report"), accelerator="Ctrl+R", command=self._report_now)
        m_file.add_command(label=t("menu.export_csv"), command=self._export_csv)
        m_file.add_separator()
        m_file.add_command(label=t("menu.exit"), command=self.close)
        bar.add_cascade(label=t("menu.file"), menu=m_file)

        m_gold = tk.Menu(bar, tearoff=False)
        m_gold.add_command(label=t("menu.golden_record"),
                           command=lambda: GoldenDialog(self.root, self.controller, self.paths["golden"]))
        m_gold.add_command(label=t("menu.golden_compare"), command=self._load_golden)
        bar.add_cascade(label=t("menu.golden"), menu=m_gold)

        m_dev = tk.Menu(bar, tearoff=False)
        m_dev.add_command(label=t("menu.ping"), command=lambda: self.controller.send(commands.ping()))
        m_dev.add_command(label=t("menu.list_sessions"), command=self.controller.request_session_list)
        m_dev.add_command(label=t("menu.get_session"), command=self._get_session)
        m_dev.add_command(label=t("menu.clear_sessions"), command=self._clear_sessions)
        bar.add_cascade(label=t("menu.device"), menu=m_dev)

        m_tools = tk.Menu(bar, tearoff=False)
        m_tools.add_command(label=t("menu.settings"), command=lambda: SettingsDialog(self.root, self.controller))
        m_tools.add_command(label=t("menu.calibration"),
                            command=lambda: CalibrationDialog(self.root, self.controller))
        m_tools.add_command(label=t("menu.reload_codes"),
                            command=lambda: self.controller.reload_codes(self.paths["codes"]))
        bar.add_cascade(label=t("menu.tools"), menu=m_tools)

        # nazwy języków zawsze we własnym języku – żeby dało się wrócić, nie znając bieżącego
        m_lang = tk.Menu(bar, tearoff=False)
        for code in LANGUAGES:
            m_lang.add_radiobutton(label=t(f"lang.{code}", code), value=code, variable=self.lang_var,
                                   command=self._switch_language)
        bar.add_cascade(label=t("menu.language"), menu=m_lang)
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
            self.status.config(text=t("status.session_ended", id=session.session_id, result=session.result))
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
                                            initialdir=self.paths["reports"],
                                            initialfile=t("file.csv_default"))
        if path:
            self.controller.export_csv(Path(path))

    def _load_golden(self) -> None:
        path = filedialog.askopenfilename(filetypes=[(t("file.golden_type"), "*.json")],
                                          initialdir=self.paths["golden"])
        if path:
            try:
                self.controller.load_golden(Path(path))
            except (ValueError, TypeError, KeyError) as exc:
                messagebox.showerror(t("dlg.golden_title"), t("dlg.golden_load_failed", error=exc))

    def _get_session(self) -> None:
        sid = simpledialog.askinteger(t("dlg.get_session_title"), t("dlg.get_session_prompt"),
                                      parent=self.root, minvalue=1)
        if sid:
            self.controller.request_session(sid)

    def _clear_sessions(self) -> None:
        if messagebox.askyesno("ESP32", t("dlg.clear_sessions_confirm")):
            self.controller.send(commands.clear_sessions())

    def _on_reply(self, reply) -> None:
        if reply.command == "list_sessions":
            ids = reply.data.get("ids", [])
            messagebox.showinfo(t("dlg.sessions_title"),
                                t("dlg.sessions_list", ids=", ".join(map(str, ids)) or t("dlg.none")))
        else:
            self.status.config(text=t("status.reply", command=reply.command, data=reply.data))

    def close(self) -> None:
        self.adapter.stop()
        self.controller.disconnect()
        self.root.destroy()
