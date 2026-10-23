"""Dekodowanie wzorców 7-segmentowych na znaki.

Kanoniczny układ bitów: bit0=a, bit1=b, ... bit6=g, bit7=dp.
Mapa kalibracji (segment_map.json) mówi, który kanał ESP32 to który segment
oraz czy segment świeci przy stanie niskim (wspólna anoda).
"""
from __future__ import annotations

from dataclasses import dataclass, field

SEGMENTS = ("a", "b", "c", "d", "e", "f", "g", "dp")

# znak -> kanoniczny wzorzec (bez kropki)
_CHAR_TO_PATTERN = {
    "0": 0x3F, "1": 0x06, "2": 0x5B, "3": 0x4F, "4": 0x66, "5": 0x6D,
    "6": 0x7D, "7": 0x07, "8": 0x7F, "9": 0x6F, "A": 0x77, "B": 0x7C,
    "C": 0x39, "D": 0x5E, "E": 0x79, "F": 0x71, "-": 0x40, " ": 0x00,
}
# warianty spotykane na różnych kartach
_ALTERNATES = {
    0x7C: "B",   # małe b
    0x7D: "6",   # 6 z górną belką
    0x27: "7",   # 7 z segmentem f
    0x67: "9",   # 9 bez segmentu d
    0x58: "C",   # małe c
    0x5E: "D",   # małe d
}

PATTERN_TO_CHAR = {v: k for k, v in _CHAR_TO_PATTERN.items()}
for _p, _c in _ALTERNATES.items():
    PATTERN_TO_CHAR.setdefault(_p, _c)

UNKNOWN_CHAR = "?"


@dataclass
class SegmentMap:
    """Wynik kalibracji: channel_to_segment[i] = nazwa segmentu dla kanału i (0..7)."""
    channel_to_segment: list[str] = field(default_factory=lambda: list(SEGMENTS))
    active_low: bool = False

    def __post_init__(self) -> None:
        if sorted(self.channel_to_segment) != sorted(SEGMENTS):
            raise ValueError("Mapa segmentów musi zawierać dokładnie a..g i dp")

    @classmethod
    def from_dict(cls, data: dict) -> "SegmentMap":
        return cls(
            channel_to_segment=list(data.get("channel_to_segment", SEGMENTS)),
            active_low=bool(data.get("active_low", False)),
        )

    def to_dict(self) -> dict:
        return {"channel_to_segment": self.channel_to_segment, "active_low": self.active_low}

    def raw_to_canonical(self, raw: int) -> int:
        if self.active_low:
            raw = (~raw) & 0xFF
        out = 0
        for ch, seg in enumerate(self.channel_to_segment):
            if raw & (1 << ch):
                out |= 1 << SEGMENTS.index(seg)
        return out

    def canonical_to_raw(self, canonical: int) -> int:
        """Operacja odwrotna - używa jej symulator, żeby ćwiczyć pełną ścieżkę."""
        raw = 0
        for ch, seg in enumerate(self.channel_to_segment):
            if canonical & (1 << SEGMENTS.index(seg)):
                raw |= 1 << ch
        if self.active_low:
            raw = (~raw) & 0xFF
        return raw


class SevenSegmentDecoder:
    def __init__(self, segment_map: SegmentMap):
        self.segment_map = segment_map

    def decode_digit(self, raw: int) -> str:
        canonical = self.segment_map.raw_to_canonical(raw) & 0x7F  # kropkę pomijamy
        return PATTERN_TO_CHAR.get(canonical, UNKNOWN_CHAR)

    def decode(self, digits_raw: tuple[int, ...]) -> str:
        return "".join(self.decode_digit(r) for r in digits_raw)

    @staticmethod
    def encode_char(ch: str) -> int:
        return _CHAR_TO_PATTERN.get(ch.upper(), 0)
