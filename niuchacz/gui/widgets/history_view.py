"""Historia sekwencji POST: każda sesja (od RESET) jako grupa wierszy."""
from __future__ import annotations

from tkinter import ttk

from niuchacz.app import event_bus as ev


class HistoryView(ttk.LabelFrame):
    def __init__(self, master, bus: ev.EventBus):
        super().__init__(master, text="Przebieg POST", padding=6)
        cols = ("lp", "kod", "czas", "etap")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings", height=14)
        for col, title, width in (("lp", "#", 40), ("kod", "Kod", 60), ("czas", "Czas", 80), ("etap", "Etap", 320)):
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
        self._session_label = "Sesja"

        bus.subscribe(ev.SESSION, self._on_session)
        bus.subscribe(ev.SEQUENCE, self._on_item)
        bus.subscribe(ev.DIAGNOSIS, self._on_diagnosis)
        bus.subscribe(ev.HANG, self._on_hang)

    def _ensure_session(self) -> None:
        if not self._session_node:
            self._session_node = self.tree.insert("", "end", text="Sesja", open=True)
            self._session_label = "Sesja"

    def _on_session(self, session) -> None:
        if self._session_node:
            self.tree.item(self._session_node, open=False)
        label = f"Sesja {session.session_id} · {session.started_at:%H:%M:%S}"
        if session.source != "na żywo":
            label += f" · {session.source}"
        self._session_node = self.tree.insert("", "end", text=label, open=True)
        self._session_label = label
        self._count = 0
        self._last_row = ""

    def _on_item(self, payload) -> None:
        item, rel_ms = payload
        self._ensure_session()
        self._count += 1
        recovered = getattr(item, "recovered", False)
        self._last_row = self.tree.insert(self._session_node, "end", text="",
                                          values=(self._count, item.code + ("*" if recovered else ""),
                                                  f"+{rel_ms / 1000:.2f} s", ""),
                                          tags=("recovered",) if recovered else ())
        self.tree.see(self._last_row)

    def _on_diagnosis(self, payload) -> None:
        diag, _text = payload
        if not self._last_row:
            return
        values = list(self.tree.item(self._last_row, "values"))
        if values and values[1].rstrip("*") == diag.code.value:
            values[3] = diag.entries[0].stage if diag.known else "(brak w bazie)"
            if values[1].endswith("*"):
                values[3] += "  [* mignął – odczytany z historii karty]"
            self.tree.item(self._last_row, values=values)

    def _on_hang(self, hang) -> None:
        if self._last_row and getattr(hang, "kind", "stop") == "stop":
            self.tree.item(self._last_row, tags=("hang",))
        if self._session_node:
            word = {"wait": "CZEKA", "done": "KONIEC"}.get(getattr(hang, "kind", "stop"), "POSTÓJ")
            self.tree.item(self._session_node, text=f"{self._session_label} · {word} {hang.code or '?'}")
