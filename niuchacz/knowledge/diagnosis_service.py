"""Usługa diagnostyczna: (kod POST, producent BIOS) -> opis i wskazówki."""
from __future__ import annotations

from niuchacz.domain.models import Diagnosis, PostCode
from niuchacz.knowledge.repository import CodeRepository


class DiagnosisService:
    def __init__(self, repository: CodeRepository):
        self.repository = repository

    def diagnose(self, code: PostCode, vendor: str, board: str = "") -> Diagnosis:
        entries = self.repository.find(code.value, vendor)
        if board:
            # wpisy dla konkretnej płyty na górę listy
            entries.sort(key=lambda e: 0 if e.board and e.board.lower() in board.lower() else 1)
        return Diagnosis(code=code, vendor=vendor, entries=entries)

    @staticmethod
    def format(diagnosis: Diagnosis) -> str:
        if not diagnosis.known:
            return (f"Kod {diagnosis.code} ({diagnosis.vendor}): brak w bazie.\n"
                    "Zapisz przebieg i dodaj wpis, gdy ustalisz przyczynę.")
        lines = []
        for i, e in enumerate(diagnosis.entries, 1):
            head = f"[{i}] Kod {e.code} – {e.stage}"
            if e.board:
                head += f"  (płyta: {e.board})"
            lines.append(head)
            if e.fault:
                lines.append(f"    Prawdopodobna usterka: {e.fault}")
            if e.check:
                lines.append(f"    Co sprawdzić: {e.check}")
            meta = ", ".join(x for x in (e.bios_version and f"BIOS {e.bios_version}",
                                         e.author and f"autor: {e.author}",
                                         e.confidence and f"pewność: {e.confidence}") if x)
            if meta:
                lines.append(f"    ({meta})")
        return "\n".join(lines)
