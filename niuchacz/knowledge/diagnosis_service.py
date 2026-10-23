"""Usługa diagnostyczna: (kod POST, producent BIOS) -> opis i wskazówki."""
from __future__ import annotations

from typing import Optional

from niuchacz.domain.models import CodeEntry, Diagnosis, PostCode
from niuchacz.i18n import has_key, localized, t
from niuchacz.knowledge.repository import CodeRepository


def _confidence(value: str, lang: Optional[str]) -> str:
    key = f"confidence.{value}"
    return t(key, lang) if has_key(key) else value


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
    def stage(entry: CodeEntry, lang: Optional[str] = None) -> str:
        """Etap w danym języku; kody oczekiwania na użytkownika dostają przedrostek."""
        text = localized(entry.stage, lang)
        if entry.kind == "wait":
            return f"{t('stage.wait_prefix', lang)}: {text}"
        return text

    @staticmethod
    def format(diagnosis: Diagnosis, lang: Optional[str] = None) -> str:
        if not diagnosis.known:
            return t("diag.unknown", lang, code=diagnosis.code, vendor=diagnosis.vendor)
        lines = []
        for i, e in enumerate(diagnosis.entries, 1):
            head = t("diag.head", lang, i=i, code=e.code, stage=DiagnosisService.stage(e, lang))
            if e.board:
                head += "  " + t("diag.board", lang, board=e.board)
            lines.append(head)
            if e.fault:
                lines.append("    " + t("diag.fault", lang, text=localized(e.fault, lang)))
            if e.check:
                lines.append("    " + t("diag.check", lang, text=localized(e.check, lang)))
            meta = ", ".join(x for x in (e.bios_version and f"BIOS {localized(e.bios_version, lang)}",
                                         e.author and t("diag.author", lang, author=e.author),
                                         e.confidence and t("diag.confidence", lang,
                                                            value=_confidence(e.confidence, lang)))
                             if x)
            if meta:
                lines.append(f"    ({meta})")
        return "\n".join(lines)
