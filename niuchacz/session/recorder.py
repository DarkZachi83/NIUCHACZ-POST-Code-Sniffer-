"""Rejestr przebiegu POST jednej sesji (od RESET do RESET)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from niuchacz.domain.models import CodeChange, SequenceItem


@dataclass
class Session:
    session_id: int
    started_at: datetime = field(default_factory=datetime.now)
    items: list[SequenceItem] = field(default_factory=list)
    hung_on: Optional[str] = None
    source: str = "na żywo"   # albo "ESP32 #7" dla sesji pobranej z urządzenia
    ended: bool = False
    result: str = ""          # opis wyniku, np. "POSTÓJ na kodzie C1"
    golden_text: str = ""     # wynik porównania ze wzorcem (jeśli był wczytany)

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

    def start(self, session_id: Optional[int] = None, source: str = "na żywo") -> Session:
        sid = session_id if session_id is not None else self._next_local_id
        self._next_local_id = max(self._next_local_id, sid) + 1
        self.current = Session(session_id=sid, source=source)
        self.sessions.append(self.current)
        return self.current

    def record(self, change: CodeChange) -> Optional[SequenceItem]:
        if change.code is None or not change.is_new:
            return None
        item = SequenceItem(code=change.code.value, ts_ms=change.ts_ms, recovered=change.recovered)
        self.current.items.append(item)
        return item

    def mark_hang(self, code: Optional[str]) -> None:
        self.current.hung_on = code

    def relative_ms(self, item: SequenceItem) -> int:
        first = self.current.items[0].ts_ms if self.current.items else item.ts_ms
        return item.ts_ms - first
