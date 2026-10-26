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
from niuchacz.i18n import t
from niuchacz.session.recorder import Session, source_label

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


def _field(label: str, value: str, width: int = 11) -> str:
    return f" {label:<{width}}: {value or '-'}"


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


def _item_lines(session: Session, stage_for: Callable[[str], str], lang: Optional[str],
                first: Optional[int] = None) -> list[str]:
    """Tabela kodów jednej sesji / jednego startu. `first` = początek czasu (dla nagrania)."""
    lines: list[str] = []
    if not session.items:
        return ["   " + t("report.no_items", lang)]
    first = session.items[0].ts_ms if first is None else first
    lines.append("   " + t("report.columns", lang))
    for i, item in enumerate(session.items, 1):
        tm = f"+{(item.ts_ms - first) / 1000:.2f} s"
        mark = " <" if session.hung_on and i == len(session.items) else ""
        code = item.code + ("*" if getattr(item, "recovered", False) else "")
        head = f" {i:3d}  {code:<4}  {tm:<9} "
        stage = (stage_for(item.code) or t("report.not_in_db", lang)) + mark
        # pełny opis, zawijany pod kolumną "Etap" (bez ucinania)
        parts = textwrap.wrap(stage, WIDTH - len(head)) or [""]
        lines.append(head + parts[0])
        lines += [" " * len(head) + p for p in parts[1:]]
    if any(getattr(it, "recovered", False) for it in session.items):
        lines.append("   " + t("report.recovered_note", lang))
    return lines


def build_report(session: Session, vendor: str, meta: ReportMeta,
                 stage_for: Callable[[str], str], diagnosis_text: str,
                 generated_at: Optional[datetime] = None, lang: Optional[str] = None) -> str:
    """Raport w języku `lang` (domyślnie bieżący język aplikacji)."""
    generated_at = generated_at or datetime.now()
    first = session.items[0].ts_ms if session.items else 0

    labels = [("report.repair_no", meta.repair_no), ("report.board", meta.board),
              ("report.owner", meta.owner), ("report.technician", meta.technician),
              ("report.date", f"{session.started_at:%Y-%m-%d %H:%M}"), ("report.bios", vendor),
              ("report.session", f"{session.session_id} ({source_label(session.source, lang)})")]
    width = max(len(t(k, lang)) for k, _ in labels)
    lines = [LINE, " " + t("report.title", lang), LINE]
    lines += [_field(t(k, lang), v, width) for k, v in labels]
    lines.append(SEP)

    result = session.result_text(lang) or (t("report.last_code", lang, code=session.last_code)
                                           if session.last_code else t("report.no_codes", lang))
    lines += _wrap(t("report.result", lang, result=result)) + [SEP]

    lines.append(" " + t("report.sequence", lang, n=len(session.items)))
    lines += _item_lines(session, stage_for, lang)
    lines.append(SEP)

    lines.append(" " + t("report.diagnosis", lang))
    lines += _wrap(diagnosis_text or t("report.none", lang))
    lines.append(SEP)

    golden_text = session.golden_text(lang)
    if golden_text:
        lines.append(" " + t("report.golden", lang))
        lines += _wrap(golden_text)
        lines.append(SEP)

    lines.append(" " + t("report.notes", lang))
    lines += _wrap(meta.notes or "")
    lines += [SEP, " " + t("report.generated", lang, version=__version__,
                          when=f"{generated_at:%Y-%m-%d %H:%M:%S}"), LINE]
    return "\n".join(lines) + "\n"


def default_filename(session: Session, meta: ReportMeta) -> str:
    parts = [p for p in (meta.repair_no, meta.board) if p]
    stem = "_".join(parts) or t("report.file_session", id=session.session_id)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)[:50]
    return f"NIUCHACZ_{safe}_{session.started_at:%Y%m%d_%H%M}.txt"


def build_recording_report(rec, vendor: str, meta: ReportMeta, stage_for: Callable[[str], str],
                           diagnosis_text: str, generated_at: Optional[datetime] = None,
                           lang: Optional[str] = None) -> str:
    """Raport nagrania (REC): kolejne starty płyty w jednym pliku."""
    generated_at = generated_at or datetime.now()
    labels = [("report.repair_no", meta.repair_no), ("report.board", meta.board),
              ("report.owner", meta.owner), ("report.technician", meta.technician),
              ("report.date", f"{rec.started_at:%Y-%m-%d %H:%M}"), ("report.bios", vendor),
              ("report.recording", t("report.recording_value", lang, id=rec.rec_id, n=len(rec.starts)))]
    width = max(len(t(k, lang)) for k, _ in labels)
    lines = [LINE, " " + t("report.title", lang), LINE]
    lines += [_field(t(k, lang), v, width) for k, v in labels]
    lines.append(SEP)
    result = rec.result_text(lang) or t("report.no_codes", lang)
    lines += _wrap(t("report.result", lang, result=result)) + [SEP]

    with_items = [s for s in rec.starts if s.items]
    first = with_items[0].items[0].ts_ms if with_items else 0
    for i, start in enumerate(rec.starts, 1):
        if i < len(rec.starts):
            end = t("report.start_end_reset", lang, code=start.last_code or "?")
        else:
            end = result
        lines += _wrap(t("report.start", lang, i=i, n=len(start.items), end=end))
        lines += _item_lines(start, stage_for, lang, first if start.items and start.items[0].ts_ms >= first else None)
        lines.append(SEP)

    if len(rec.starts) > 1:
        lines.append(" " + t("report.before_reset", lang))
        lines += _wrap(", ".join(f"{i}: {s.last_code or '?'}" for i, s in enumerate(rec.starts, 1)))
        lines.append(SEP)

    lines.append(" " + t("report.diagnosis", lang))
    lines += _wrap(diagnosis_text or t("report.none", lang))
    lines.append(SEP)
    lines.append(" " + t("report.notes", lang))
    lines += _wrap(meta.notes or "")
    lines += [SEP, " " + t("report.generated", lang, version=__version__,
                          when=f"{generated_at:%Y-%m-%d %H:%M:%S}"), LINE]
    return "\n".join(lines) + "\n"
