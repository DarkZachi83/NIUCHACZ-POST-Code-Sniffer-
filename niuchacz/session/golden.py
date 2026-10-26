"""Złote przebiegi: wzorcowe sekwencje POST ze sprawnych płyt i porównanie z nimi."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

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
    # pozycje kodów niepewnych (~ = złapany jednym odczytem, ok. 1 µs) – mogą nie złapać się w innym
    # przebiegu tej samej płyty, więc ich brak nie jest rozbieżnością
    optional: list[int] = field(default_factory=list)

    @classmethod
    def from_session(cls, session: Session, **meta) -> "GoldenRun":
        first = session.items[0].ts_ms if session.items else 0
        return cls(codes=session.codes,
                   timings_ms=[i.ts_ms - first for i in session.items],
                   optional=[k for k, i in enumerate(session.items) if getattr(i, "single", False)], **meta)

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "GoldenRun":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})


LOOKAHEAD = 4   # tyle kodów naprzód szukamy, żeby po brakującym/nadmiarowym kodzie złapać wspólny rytm


def collapse(codes: list[str], flags: Optional[Sequence[bool]] = None) -> tuple[list[str], list[bool]]:
    """Usuwa powtórzenia pod rząd (np. migotanie tego samego kodu); flagi idą razem z kodami."""
    flags = list(flags) if flags is not None else [False] * len(codes)
    out: list[str] = []
    out_f: list[bool] = []
    for c, f in zip(codes, flags):
        if not out or out[-1] != c:
            out.append(c)
            out_f.append(f)
    return out, out_f


def _resync(src: list[str], start: int, other: list[str], j: int) -> int:
    """Czy pominięcie src[start:k] daje zgodność od src[k] z other[j] (i następnym kodem)? Zwraca k albo -1."""
    for k in range(start + 1, min(len(src), start + 1 + LOOKAHEAD)):
        if src[k] != other[j]:
            continue
        if k + 1 < len(src) and j + 1 < len(other) and src[k + 1] != other[j + 1]:
            continue
        return k
    return -1


def compare(actual: list[str], golden: list[str], golden_optional: Sequence[int] = (),
            actual_uncertain: Optional[Sequence[bool]] = None) -> Divergence:
    """Porównanie z wzorcem odporne na pojedyncze brakujące lub nadmiarowe kody.

    Odczyt nie jest idealny: bardzo krótkie kody (~) raz się łapią, raz nie. Jeśli po brakującym
    (albo nadmiarowym) kodzie dalsza sekwencja znów się zgadza, to nie jest rozbieżność, tylko
    pominięcie – zapisane w wyniku. Rozbieżność = płyta naprawdę poszła inną drogą albo stanęła.
    """
    g_flags = [k in set(golden_optional) for k in range(len(golden))]
    a, a_opt = collapse(actual, actual_uncertain)
    g, g_opt = collapse(golden, g_flags)
    i = j = matched = 0
    skipped: list[str] = []
    extra: list[str] = []
    only_uncertain = True
    while i < len(a) and j < len(g):
        if a[i] == g[j]:
            i, j, matched = i + 1, j + 1, matched + 1
            continue
        k = _resync(g, j, a, i)          # brakuje kodów wzorca g[j:k]
        if k >= 0:
            skipped += g[j:k]
            only_uncertain &= all(g_opt[j:k])
            j = k
            continue
        k = _resync(a, i, g, j)          # nadmiarowe kody przebiegu a[i:k]
        if k >= 0:
            extra += a[i:k]
            only_uncertain &= all(a_opt[i:k])
            i = k
            continue
        return Divergence(index=j, expected=g[j], actual=a[i], matched=matched,
                          skipped=tuple(skipped), extra=tuple(extra), only_uncertain=only_uncertain)
    rest = dict(skipped=tuple(skipped), extra=tuple(extra), only_uncertain=only_uncertain)
    while j < len(g) and g_opt[j]:       # na końcu wzorca same niepewne kody – nie szkodzi
        skipped.append(g[j])
        j += 1
        rest["skipped"] = tuple(skipped)
    if j < len(g):
        # przebieg urwał się wcześniej - typowe zawieszenie
        return Divergence(index=j, expected=g[j], actual=None, matched=matched, **rest)
    if i < len(a):
        return Divergence(index=j, expected=None, actual=a[i], matched=matched, **rest)
    return Divergence(index=-1, expected=None, actual=None, matched=matched, **rest)


def describe(div: Divergence, golden: GoldenRun) -> tuple[str, dict]:
    """Opis porównania jako (klucz tłumaczenia, pola) – tekst powstaje przy wyświetleniu.

    Klucze golden.stopped i golden.diverged oznaczają problem (panel pokazuje je na pomarańczowo)."""
    base = {"board": golden.board}
    if div.identical and (div.skipped or div.extra):
        key = "golden.identical_uncertain" if div.only_uncertain else "golden.identical_missing"
        return key, {**base, "n": div.matched, "skipped": ", ".join(div.skipped) or "-",
                     "extra": ", ".join(div.extra) or "-"}
    if div.identical:
        return "golden.identical", {**base, "n": div.matched}
    if div.actual is None:
        return "golden.stopped", {**base, "n": div.matched, "expected": div.expected}
    if div.expected is None:
        return "golden.longer", {**base, "actual": div.actual}
    return "golden.diverged", {**base, "pos": div.index + 1, "expected": div.expected,
                               "actual": div.actual, "n": div.matched}


PROBLEM_KEYS = ("golden.stopped", "golden.diverged")
