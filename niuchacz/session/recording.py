"""Nagrywanie przebiegów (przycisk REC).

Bez REC aplikacja tylko pokazuje kody na żywo – nic nie zapisuje i nie otwiera raportów.
Po REC czeka na reset płyty (albo włączenie zasilania); nagranie zaczyna się od pierwszego
startu i kończy dopiero na prawdziwym końcu przebiegu: zakończony POST, BIOS czeka na
użytkownika, postój albo ręczny STOP.

Reset w trakcie nagrania NIE kończy go – otwiera kolejny „start” w tym samym nagraniu.
Wiele płyt robi przy każdym uruchomieniu jeden zaplanowany reset (np. ASRock 775V88 po
ustawieniu pamięci), więc pełny przebieg to często dwa starty. Gdy płyta wpadnie w pętlę
restartów, nagranie kończy się po `max_starts` startach z podsumowaniem, na jakim kodzie
płyta padała przed każdym resetem.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from niuchacz.i18n import t
from niuchacz.session.recorder import Session

IDLE = "idle"            # nic nie nagrywa (podgląd na żywo działa zawsze)
ARMED = "armed"          # REC wciśnięty – czeka na reset / włączenie płyty
RECORDING = "recording"  # nagrywa
DONE = "done"            # nagranie zakończone i zapisane


@dataclass
class Recording:
    rec_id: int
    starts: list[Session] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    end_key: str = ""
    end_fields: dict = field(default_factory=dict)
    saved: list[Path] = field(default_factory=list)

    # --- zgodność z miejscami, które pokazują sesję (okno raportu, nazwa pliku) ---
    @property
    def session_id(self) -> int:
        return self.rec_id

    def result_text(self, lang: Optional[str] = None) -> str:
        return t(self.end_key, lang, **self.end_fields) if self.end_key else ""

    @property
    def result(self) -> str:
        return self.result_text()

    @property
    def last_code(self) -> Optional[str]:
        for s in reversed(self.starts):
            if s.items:
                return s.last_code
        return None

    @property
    def code_count(self) -> int:
        return sum(len(s.items) for s in self.starts)


class RecordingManager:
    def __init__(self, max_starts: int = 4):
        self.max_starts = max(1, int(max_starts))
        self.state = IDLE
        self.current: Optional[Recording] = None
        self.last: Optional[Recording] = None
        self._next_id = 1

    def _new(self) -> Recording:
        rec = Recording(rec_id=self._next_id)
        self._next_id += 1
        return rec

    # ---------- sterowanie ----------

    def arm(self) -> bool:
        """REC: czekaj na start płyty. Zwraca False, jeśli już nagrywa."""
        if self.state in (IDLE, DONE):
            self.state = ARMED
            self.current = None
            return True
        return False

    def cancel(self) -> bool:
        """Anulowanie oczekiwania (przed startem płyty)."""
        if self.state == ARMED:
            self.state = IDLE
            return True
        return False

    def on_new_start(self, session: Session) -> Optional[str]:
        """Płyta zaczyna nowy start (koniec resetu albo kod bloku startowego).

        Zwraca: "started" – nagranie ruszyło, "next" – kolejny start w nagraniu,
        "loop" – przekroczony limit startów (nagranie trzeba zakończyć), None – nie nagrywamy.
        """
        if self.state == ARMED:
            self.current = self._new()
            self.current.starts.append(session)
            self.state = RECORDING
            return "started"
        if self.state == RECORDING and self.current is not None:
            if len(self.current.starts) >= self.max_starts:
                return "loop"
            self.current.starts.append(session)
            return "next"
        return None

    def finish(self, key: str, **fields) -> Optional[Recording]:
        """Kończy nagranie z powodem (klucz tłumaczenia + pola)."""
        if self.state != RECORDING or self.current is None:
            return None
        rec = self.current
        rec.end_key, rec.end_fields = key, fields
        self.state = DONE
        self.last = rec
        return rec

    def snapshot(self, session: Session) -> Recording:
        """„Zapisz ostatni przebieg” – nagranie z sesji, która nie była uzbrojona."""
        rec = self._new()
        rec.starts.append(session)
        rec.started_at = session.started_at
        rec.end_key, rec.end_fields = "rec.end_snapshot", {"code": session.last_code or "?"}
        self.last = rec
        return rec

    @property
    def start_count(self) -> int:
        return len(self.current.starts) if self.current and self.state == RECORDING else 0
