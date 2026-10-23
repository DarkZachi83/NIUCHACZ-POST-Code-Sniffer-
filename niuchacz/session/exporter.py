"""Eksport sesji do CSV (dalsza analiza). Raport TXT buduje session/report.py."""
from __future__ import annotations

import csv
from pathlib import Path

from niuchacz.session.recorder import Session


def export_csv(session: Session, path: Path) -> None:
    first = session.items[0].ts_ms if session.items else 0
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["lp", "kod", "czas_ms_od_startu", "ts_ms_urzadzenia", "z_historii_karty"])
        for i, item in enumerate(session.items, 1):
            w.writerow([i, item.code, item.ts_ms - first, item.ts_ms, "tak" if item.recovered else ""])
