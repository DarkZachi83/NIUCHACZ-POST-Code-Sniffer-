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
