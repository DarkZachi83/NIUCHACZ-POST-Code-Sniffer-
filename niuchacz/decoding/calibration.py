"""Kreator kalibracji: z odczytów "surowy stan linii + co widać na karcie" ustala
mapę kanałów na segmenty, kolejność cyfr i polaryzację segmentów.

Każda karta POST może mieć inny wyświetlacz i inaczej poprowadzone przewody, więc
zamiast mierzyć wszystko ręcznie użytkownik podaje 1–3 napisy z karty (np. "8584",
"dE24"), a program sprawdza wszystkie możliwe przyporządkowania (7! × 4! × 2 ≈ 240 tys.)
i zostawia te, które pasują do każdego odczytu.

Kanały 0..6 to segmenty (przewody 1–7), kanał 7 (przewód 8) – kropka / nieużywany.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations

from niuchacz.i18n import t
from niuchacz.decoding.seven_segment import PATTERN_TO_CHAR, SEGMENTS, _CHAR_TO_PATTERN

SEG7 = SEGMENTS[:7]


def _patterns_for(ch: str) -> set[int]:
    """Wszystkie wzorce, które dany znak może mieć na karcie (np. 6 z belką i bez)."""
    ch = ch.upper()
    out = {p for p, c in PATTERN_TO_CHAR.items() if c == ch}
    if ch in _CHAR_TO_PATTERN:
        out.add(_CHAR_TO_PATTERN[ch])
    return out


@dataclass(frozen=True)
class Sample:
    raw: tuple[int, ...]   # bajt na linię DIG1..DIG4 (bity = kanały 1..8)
    text: str              # co widać na karcie, od lewej, np. "8584"


@dataclass(frozen=True)
class Solution:
    channel_to_segment: tuple[str, ...]   # 8 pozycji, ostatnia "dp"
    display_order: tuple[int, ...]        # linia DIG na kolejnych pozycjach od lewej
    active_low: bool


def solve(samples: list[Sample], digits: int = 4) -> list[Solution]:
    if not samples:
        return []
    for s in samples:
        if len(s.text) != digits or len(s.raw) != digits:
            raise ValueError(t("calib.err_digits", n=digits))
    wanted = [[_patterns_for(c) for c in s.text] for s in samples]
    if any(not w for row in wanted for w in row):
        raise ValueError(t("calib.err_chars"))

    solutions: list[Solution] = []
    perms = list(permutations(range(7)))
    for active_low in (True, False):
        lit = [[((~r) if active_low else r) & 0x7F for r in s.raw] for s in samples]
        for order in permutations(range(digits)):
            # dla tej kolejności: (świecące kanały, dopuszczalne wzorce) dla każdej cyfry
            checks = [(lit[i][order[pos]], wanted[i][pos]) for i in range(len(samples)) for pos in range(digits)]
            # szybkie odrzucenie: liczba świecących segmentów musi się zgadzać
            if any(bin(l).count("1") not in {bin(p).count("1") for p in w} for l, w in checks):
                continue
            for perm in perms:
                ok = True
                for l, w in checks:
                    out = 0
                    for ch in range(7):
                        if l & (1 << ch):
                            out |= 1 << perm[ch]
                    if out not in w:
                        ok = False
                        break
                if ok:
                    solutions.append(Solution(tuple(SEG7[perm[ch]] for ch in range(7)) + ("dp",),
                                              tuple(order), active_low))
    return solutions


def summarize(solutions: list[Solution]) -> str:
    if not solutions:
        return t("calib.none")
    if len(solutions) == 1:
        s = solutions[0]
        pairs = ", ".join(f"{i + 1}={seg}" for i, seg in enumerate(s.channel_to_segment[:7]))
        return t("calib.unique", pairs=pairs, lines=", ".join("DIG%d" % (d + 1) for d in s.display_order),
                 level=t("calib.level_low" if s.active_low else "calib.level_high"))
    return t("calib.many", n=len(solutions))


def auto_rank(frames: list[tuple[int, ...]], samples: list[Sample] | None = None,
              digits: int = 4, top: int = 5) -> list[tuple[float, Solution]]:
    """Kalibracja bez przepisywania napisów: z wielu zapisanych ramek (np. z całego POST)
    wybiera przyporządkowanie, przy którym najwięcej cyfr daje sensowny znak (0-9, A-F, -, spacja).

    Kody migają za szybko, żeby je przepisać, ale każda ramka i tak jest "prawdziwym" wzorem
    cyfry – przy złym przyporządkowaniu duża część wzorów nie układa się w żaden znak.
    Odczyty wpisane ręcznie (samples) zawężają wybór (np. kolejność cyfr z "8785").
    Zwraca listę (wynik 0..1, rozwiązanie) od najlepszego.
    """
    valid = set(PATTERN_TO_CHAR)
    if samples:
        candidates = solve(samples, digits)
    else:
        candidates = [Solution(tuple(SEG7[perm[ch]] for ch in range(7)) + ("dp",), tuple(range(digits)), al)
                      for al in (True, False) for perm in permutations(range(7))]
    # licznik wzorów (polaryzacja uwzględniana przy liczeniu)
    counts: dict[int, int] = {}
    for fr in frames:
        for b in fr:
            counts[b & 0x7F] = counts.get(b & 0x7F, 0) + 1
    total = sum(counts.values()) or 1
    ranked: list[tuple[float, Solution]] = []
    seen = set()
    for sol in candidates:
        key = (sol.channel_to_segment, sol.active_low)
        if key in seen:
            continue
        seen.add(key)
        seg_idx = [SEG7.index(x) for x in sol.channel_to_segment[:7]]
        good = 0
        for raw, n in counts.items():
            lit = ((~raw) if sol.active_low else raw) & 0x7F
            out = 0
            for ch in range(7):
                if lit & (1 << ch):
                    out |= 1 << seg_idx[ch]
            if out in valid:
                good += n
        ranked.append((good / total, sol))
    ranked.sort(key=lambda t: -t[0])
    return ranked[:top]
