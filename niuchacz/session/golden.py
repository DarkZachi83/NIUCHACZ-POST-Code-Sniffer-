"""Złote przebiegi: wzorcowe sekwencje POST ze sprawnych płyt i porównanie z nimi."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from niuchacz.domain.models import Divergence
from niuchacz.session.recorder import Session


@dataclass
class GoldenRun:
    board: str
    bios_vendor: str
    codes: list[str]
    bios_version: str = ""
    chipset: str = ""
    cpu: str = ""
    ram: str = ""
    video: str = ""
    induced_fault: str = ""      # "" = przebieg sprawny, np. "brak RAM"
    notes: str = ""
    author: str = ""
    recorded_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    timings_ms: list[int] = field(default_factory=list)

    @classmethod
    def from_session(cls, session: Session, **meta) -> "GoldenRun":
        first = session.items[0].ts_ms if session.items else 0
        return cls(codes=session.codes,
                   timings_ms=[i.ts_ms - first for i in session.items], **meta)

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "GoldenRun":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


def collapse(codes: list[str]) -> list[str]:
    """Usuwa powtórzenia pod rząd (np. migotanie tego samego kodu)."""
    out: list[str] = []
    for c in codes:
        if not out or out[-1] != c:
            out.append(c)
    return out


def compare(actual: list[str], golden: list[str]) -> Divergence:
    """Szuka pierwszego miejsca, w którym przebieg odbiega od wzorca."""
    a, g = collapse(actual), collapse(golden)
    for i in range(min(len(a), len(g))):
        if a[i] != g[i]:
            return Divergence(index=i, expected=g[i], actual=a[i], matched=i)
    if len(a) < len(g):
        # przebieg urwał się wcześniej - typowe zawieszenie
        return Divergence(index=len(a), expected=g[len(a)], actual=None, matched=len(a))
    if len(a) > len(g):
        return Divergence(index=len(g), expected=None, actual=a[len(g)], matched=len(g))
    return Divergence(index=-1, expected=None, actual=None, matched=len(a))


def describe(div: Divergence, golden: GoldenRun) -> str:
    if div.identical:
        return f"Przebieg zgodny ze wzorcem ({div.matched} kodów)."
    if div.actual is None:
        return (f"Start zatrzymał się po {div.matched} zgodnych kodach. "
                f"Wzorzec przechodzi dalej do {div.expected} – usterka między tymi etapami.")
    if div.expected is None:
        return f"Przebieg dłuższy niż wzorzec, nadmiarowy kod: {div.actual}."
    return (f"Rozbieżność na pozycji {div.index + 1}: oczekiwano {div.expected}, "
            f"jest {div.actual} (zgodnych {div.matched}).")
