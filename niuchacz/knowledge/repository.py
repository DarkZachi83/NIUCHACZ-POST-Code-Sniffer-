"""Repozytorium bazy kodów POST.

Lokalnie SQLite. Źródłem prawdy są pliki JSON w data/post_codes/
(to je wymienia społeczność przez GitHub). Przy starcie baza jest
odświeżana z plików JSON, więc nowe pliki wystarczy wrzucić do katalogu.

Pola opisowe (stage, fault, check) mogą być napisem albo słownikiem języków
{"en": ..., "pl": ...}. W SQLite słownik leży jako tekst JSON, a język wybiera
dopiero i18n.localized() przy wyświetleniu.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, fields
from pathlib import Path

from niuchacz.domain.models import CodeEntry

_COLUMNS = [f.name for f in fields(CodeEntry)]
# nazwy kolumn w cudzysłowach: "check" to słowo kluczowe SQL
_QCOLS = ", ".join(f'"{c}"' for c in _COLUMNS)
_COLDEFS = ", ".join('"%s" TEXT NOT NULL DEFAULT \'\'' % c for c in _COLUMNS)

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS post_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    {_COLDEFS},
    origin_file TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_code_vendor ON post_codes(code, vendor);
"""


def _as_text(value) -> str:
    """Słownik języków -> tekst JSON (do SQLite); reszta -> str."""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


class CodeRepository:
    def __init__(self, db_path: Path | str = ":memory:"):
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Dopisuje kolumny dodane w nowszych wersjach (np. kind) do starej bazy."""
        have = {row[1] for row in self._db.execute("PRAGMA table_info(post_codes)")}
        with self._db:
            for col in _COLUMNS:
                if col not in have:
                    self._db.execute(f'ALTER TABLE post_codes ADD COLUMN "{col}" TEXT NOT NULL DEFAULT \'\'')

    def close(self) -> None:
        self._db.close()

    # ---- import / eksport JSON ----

    def import_directory(self, directory: Path) -> int:
        """Przeładowuje wpisy pochodzące z plików *.json w katalogu."""
        count = 0
        for path in sorted(Path(directory).glob("*.json")):
            count += self.import_file(path)
        return count

    def import_file(self, path: Path) -> int:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        vendor = payload.get("vendor", "")
        entries = payload.get("entries", [])
        with self._db:
            self._db.execute("DELETE FROM post_codes WHERE origin_file = ?", (str(path.name),))
            for raw in entries:
                raw = {"vendor": vendor, "stage": "", **raw}
                entry = CodeEntry(**{k: _as_text(raw[k]) for k in _COLUMNS if k in raw})
                entry.code = entry.code.strip().upper()
                self._insert(entry, origin=path.name)
        return len(entries)

    def export_vendor(self, vendor: str, path: Path) -> None:
        rows = [asdict(e) for e in self.all_for_vendor(vendor)]
        for r in rows:
            r.pop("vendor", None)
        Path(path).write_text(
            json.dumps({"vendor": vendor, "entries": rows}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- zapytania ----

    def add(self, entry: CodeEntry, origin: str = "lokalne") -> None:
        with self._db:
            self._insert(entry, origin)

    def find(self, code: str, vendor: str) -> list[CodeEntry]:
        cur = self._db.execute(
            f"SELECT {_QCOLS} FROM post_codes WHERE code = ? AND vendor = ? ORDER BY id",
            (code.upper(), vendor),
        )
        return [CodeEntry(*row) for row in cur.fetchall()]

    def all_for_vendor(self, vendor: str) -> list[CodeEntry]:
        cur = self._db.execute(
            f"SELECT {_QCOLS} FROM post_codes WHERE vendor = ? ORDER BY code, id",
            (vendor,),
        )
        return [CodeEntry(*row) for row in cur.fetchall()]

    def count(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM post_codes").fetchone()[0]

    def _insert(self, entry: CodeEntry, origin: str) -> None:
        values = [getattr(entry, c) for c in _COLUMNS]
        self._db.execute(
            f"INSERT INTO post_codes ({_QCOLS}, origin_file) VALUES ({', '.join('?' * (len(_COLUMNS) + 1))})",
            (*values, origin),
        )
