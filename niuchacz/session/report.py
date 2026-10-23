"""Raport tekstowy z sesji POST – do zapisu w .txt i wydruku.

Czysta funkcja: dostaje dane, zwraca tekst. Ten sam tekst widać w oknie
podglądu, trafia do pliku i na drukarkę. Szerokość 72 znaki mieści się na
kartce A4 drukowanej z Notatnika.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from niuchacz import __version__
from niuchacz.session.recorder import Session

WIDTH = 72
LINE = "=" * WIDTH
SEP = "-" * WIDTH


@dataclass
class ReportMeta:
    """Pola wpisywane przez serwisanta w oknie raportu."""
    repair_no: str = ""
    board: str = ""
    owner: str = ""
    technician: str = ""
    notes: str = ""


def _field(label: str, value: str) -> str:
    return f" {label:<11}: {value or '-'}"


def _wrap(text: str, indent: str = " ") -> list[str]:
    out: list[str] = []
    for raw in text.splitlines() or [""]:
        lead = len(raw) - len(raw.lstrip(" "))
        pre = indent + " " * lead
        out += textwrap.wrap(raw.strip(), WIDTH, initial_indent=pre,
                             subsequent_indent=pre + "  ") or [""]
    return out


def _cut(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def build_report(session: Session, vendor: str, meta: ReportMeta,
                 stage_for: Callable[[str], str], diagnosis_text: str,
                 generated_at: Optional[datetime] = None) -> str:
    generated_at = generated_at or datetime.now()
    first = session.items[0].ts_ms if session.items else 0

    lines = [LINE, " NIUCHACZ – RAPORT DIAGNOSTYKI POST", LINE,
             _field("Nr naprawy", meta.repair_no),
             _field("Płyta", meta.board),
             _field("Właściciel", meta.owner),
             _field("Serwisant", meta.technician),
             _field("Data", f"{session.started_at:%Y-%m-%d %H:%M}"),
             _field("BIOS", vendor),
             _field("Sesja", f"{session.session_id} ({session.source})"),
             SEP]

    result = session.result or (f"Ostatni kod: {session.last_code}" if session.last_code else "Brak kodów")
    lines += _wrap(f"WYNIK: {result}") + [SEP]

    lines.append(f" PRZEBIEG POST ({len(session.items)} kodów)")
    if session.items:
        lines.append("   #  Kod   Czas      Etap")
        for i, item in enumerate(session.items, 1):
            t = f"+{(item.ts_ms - first) / 1000:.2f} s"
            mark = " <" if session.hung_on and i == len(session.items) else ""
            code = item.code + ("*" if getattr(item, "recovered", False) else "")
            head = f" {i:3d}  {code:<4}  {t:<9} "
            stage = (stage_for(item.code) or "(brak w bazie)") + mark
            # pełny opis, zawijany pod kolumną "Etap" (bez ucinania)
            parts = textwrap.wrap(stage, WIDTH - len(head)) or [""]
            lines.append(head + parts[0])
            lines += [" " * len(head) + p for p in parts[1:]]
        if any(getattr(it, "recovered", False) for it in session.items):
            lines.append("   * kod mignął za szybko – odczytany z historii karty (lewa para cyfr)")
    else:
        lines.append("   (brak zarejestrowanych kodów)")
    lines.append(SEP)

    lines.append(" DIAGNOZA OSTATNIEGO KODU")
    lines += _wrap(diagnosis_text or "(brak)")
    lines.append(SEP)

    if session.golden_text:
        lines.append(" PORÓWNANIE ZE WZORCEM")
        lines += _wrap(session.golden_text)
        lines.append(SEP)

    lines.append(" UWAGI SERWISANTA")
    lines += _wrap(meta.notes or "")
    lines += [SEP, f" Wygenerowano: NIUCHACZ {__version__} · {generated_at:%Y-%m-%d %H:%M:%S}", LINE]
    return "\n".join(lines) + "\n"


def default_filename(session: Session, meta: ReportMeta) -> str:
    parts = [p for p in (meta.repair_no, meta.board) if p]
    stem = "_".join(parts) or f"sesja{session.session_id}"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)[:50]
    return f"NIUCHACZ_{safe}_{session.started_at:%Y%m%d_%H%M}.txt"
