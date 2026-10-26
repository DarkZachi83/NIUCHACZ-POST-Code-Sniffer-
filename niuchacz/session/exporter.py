"""Eksport sesji do CSV (dalsza analiza). Raport TXT buduje session/report.py."""
from __future__ import annotations

import csv
from pathlib import Path

from niuchacz.i18n import t
from niuchacz.session.recorder import Session


def export_csv(session: Session, path: Path) -> None:
    first = session.items[0].ts_ms if session.items else 0
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([t("csv.no"), t("csv.code"), t("csv.ms_from_start"), t("csv.device_ts"), t("csv.recovered")])
        for i, item in enumerate(session.items, 1):
            w.writerow([i, item.code, item.ts_ms - first, item.ts_ms, t("csv.yes") if item.recovered else ""])


def export_recording_csv(rec, path: Path) -> None:
    """CSV nagrania: każdy kod z numerem startu i czasem od początku nagrania."""
    starts = [s for s in rec.starts if s.items]
    first = starts[0].items[0].ts_ms if starts else 0
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([t("csv.start"), t("csv.no"), t("csv.code"), t("csv.ms_from_start"), t("csv.device_ts"),
                    t("csv.recovered")])
        n = 0
        for si, start in enumerate(rec.starts, 1):
            for item in start.items:
                n += 1
                w.writerow([si, n, item.code, item.ts_ms - first, item.ts_ms,
                            t("csv.yes") if item.recovered else ""])
