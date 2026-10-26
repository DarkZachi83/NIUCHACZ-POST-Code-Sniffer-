"""Rejestr przebiegu POST jednej sesji (od RESET do RESET)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from niuchacz.domain.models import CodeChange, SequenceItem
from niuchacz.i18n import localized, t

LIVE = "live"


def source_label(source: str, lang: Optional[str] = None) -> str:
    """Źródło sesji dla człowieka: "live" -> "na żywo"/"live", "esp32:7" -> "ESP32 #7"."""
    if source == LIVE:
        return t("session.source_live", lang)
    if source.startswith("esp32:"):
        return t("session.source_esp32", lang, id=source.split(":", 1)[1])
    return source


@dataclass
class Session:
    session_id: int
    started_at: datetime = field(default_factory=datetime.now)
    items: list[SequenceItem] = field(default_factory=list)
    hung_on: Optional[str] = None
    source: str = LIVE        # albo "esp32:7" dla sesji pobranej z urządzenia
    ended: bool = False
    # wynik i porównanie ze wzorcem jako KLUCZ + pola – tekst powstaje przy wyświetleniu,
    # więc raport po zmianie języka jest w nowym języku
    result_key: str = ""
    result_fields: dict = field(default_factory=dict)
    golden_key: str = ""
    golden_fields: dict = field(default_factory=dict)
    gap_max_us: int = 0       # najdłuższa ślepa przerwa ESP32 w czasie tej sesji (z heartbeat)

    def set_result(self, key: str = "", **fields) -> None:
        self.result_key, self.result_fields = key, fields

    def set_golden(self, key: str = "", **fields) -> None:
        self.golden_key, self.golden_fields = key, fields

    @staticmethod
    def _render(key: str, fields: dict, lang: Optional[str]) -> str:
        if not key:
            return ""
        return t(key, lang, **{k: localized(v, lang) if isinstance(v, (dict, str)) else v
                               for k, v in fields.items()})

    def result_text(self, lang: Optional[str] = None) -> str:
        return self._render(self.result_key, self.result_fields, lang)

    def golden_text(self, lang: Optional[str] = None) -> str:
        return self._render(self.golden_key, self.golden_fields, lang)

    @property
    def result(self) -> str:
        """Wynik w bieżącym języku (pusty, gdy brak)."""
        return self.result_text()

    @property
    def codes(self) -> list[str]:
        return [i.code for i in self.items]

    @property
    def last_code(self) -> Optional[str]:
        return self.items[-1].code if self.items else None


class SessionRecorder:
    def __init__(self) -> None:
        self.sessions: list[Session] = []
        self._next_local_id = 1
        self.current: Session = self.start()

    def start(self, session_id: Optional[int] = None, source: str = LIVE) -> Session:
        sid = session_id if session_id is not None else self._next_local_id
        self._next_local_id = max(self._next_local_id, sid) + 1
        self.current = Session(session_id=sid, source=source)
        self.sessions.append(self.current)
        return self.current

    def record(self, change: CodeChange) -> Optional[SequenceItem]:
        if change.code is None or not change.is_new:
            return None
        item = SequenceItem(code=change.code.value, ts_ms=change.ts_ms, recovered=change.recovered,
                            gap_us=change.gap_us)
        self.current.items.append(item)
        return item

    def mark_hang(self, code: Optional[str]) -> None:
        self.current.hung_on = code

    def relative_ms(self, item: SequenceItem) -> int:
        first = self.current.items[0].ts_ms if self.current.items else item.ts_ms
        return item.ts_ms - first
