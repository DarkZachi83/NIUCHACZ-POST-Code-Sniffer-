"""Historia sekwencji POST: każda sesja (od RESET) jako grupa wierszy."""
from __future__ import annotations

from tkinter import ttk

from niuchacz.app import event_bus as ev
from niuchacz.i18n import t
from niuchacz.session.recorder import LIVE, source_label

# rodzaj postoju -> klucz krótkiego słowa przy nazwie sesji
_HANG_WORD = {"wait": "history.word_wait", "done": "history.word_done", "stop": "history.word_stop"}
# klucz wyniku sesji -> rodzaj (do odtworzenia drzewa po zmianie języka)
_RESULT_KIND = {"result.wait": "wait", "result.done": "done", "result.stop": "stop"}


class HistoryView(ttk.LabelFrame):
    def __init__(self, master, bus):
        super().__init__(master, text=t("panel.history"), padding=6)
        cols = ("lp", "kod", "czas", "etap")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings", height=14)
        for col, title, width in (("lp", "#", 40), ("kod", t("history.col_code"), 60),
                                  ("czas", t("history.col_time"), 80), ("etap", t("history.col_stage"), 320)):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w" if col == "etap" else "center", stretch=col == "etap")
        self.tree.column("#0", width=250, stretch=False)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.tag_configure("hang", foreground="#c25e00")
        self.tree.tag_configure("recovered", foreground="#6a6a6a")
        self._session_node = ""
        self._last_row = ""
        self._count = 0
        self._session_label = t("history.session")

        bus.subscribe(ev.SESSION, self._on_session)
        bus.subscribe(ev.SEQUENCE, self._on_item)
        bus.subscribe(ev.DIAGNOSIS, self._on_diagnosis)
        bus.subscribe(ev.HANG, self._on_hang)

    def _ensure_session(self) -> None:
        if not self._session_node:
            self._session_label = t("history.session")
            self._session_node = self.tree.insert("", "end", text=self._session_label, open=True)

    def _on_session(self, session) -> None:
        if self._session_node:
            self.tree.item(self._session_node, open=False)
        label = t("history.session_label", id=session.session_id, time=f"{session.started_at:%H:%M:%S}")
        if session.source != LIVE:
            label += f" · {source_label(session.source)}"
        self._session_node = self.tree.insert("", "end", text=label, open=True)
        self._session_label = label
        self._count = 0
        self._last_row = ""

    def _add_row(self, code: str, rel_ms: int, recovered: bool, stage: str = "") -> None:
        self._ensure_session()
        self._count += 1
        self._last_row = self.tree.insert(self._session_node, "end", text="",
                                          values=(self._count, code + ("*" if recovered else ""),
                                                  f"+{rel_ms / 1000:.2f} s", stage),
                                          tags=("recovered",) if recovered else ())
        self.tree.see(self._last_row)

    def _on_item(self, payload) -> None:
        item, rel_ms = payload
        self._add_row(item.code, rel_ms, getattr(item, "recovered", False))

    def _stage_text(self, stage: str, recovered: bool) -> str:
        text = stage or t("report.not_in_db")
        if recovered:
            text += "  " + t("history.recovered_mark")
        return text

    def _on_diagnosis(self, payload) -> None:
        diag, _text = payload
        if not self._last_row:
            return
        values = list(self.tree.item(self._last_row, "values"))
        if values and values[1].rstrip("*") == diag.code.value:
            from niuchacz.knowledge.diagnosis_service import DiagnosisService
            stage = DiagnosisService.stage(diag.entries[0]) if diag.known else ""
            values[3] = self._stage_text(stage, values[1].endswith("*"))
            self.tree.item(self._last_row, values=values)

    def _mark(self, kind: str, code) -> None:
        if self._last_row and kind == "stop":
            self.tree.item(self._last_row, tags=("hang",))
        if self._session_node:
            word = t(_HANG_WORD.get(kind, "history.word_stop"))
            self.tree.item(self._session_node, text=f"{self._session_label} · {word} {code or '?'}")

    def _on_hang(self, hang) -> None:
        self._mark(getattr(hang, "kind", "stop"), hang.code)

    def replay(self, sessions, stage_for) -> None:
        """Odtwarza drzewo z zapisanych sesji – po przebudowie okna w innym języku."""
        for session in sessions:
            if not session.items:
                continue
            self._on_session(session)
            first = session.items[0].ts_ms
            for item in session.items:
                recovered = getattr(item, "recovered", False)
                self._add_row(item.code, item.ts_ms - first, recovered,
                              self._stage_text(stage_for(item.code), recovered))
            kind = _RESULT_KIND.get(session.result_key)
            if kind:
                self._mark(kind, session.result_fields.get("code"))
