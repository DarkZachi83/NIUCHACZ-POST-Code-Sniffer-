"""Składanie kodu POST z cyfr wyświetlacza i wykrywanie zawieszenia."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from niuchacz.domain.models import CodeChange, FrameEvent, HangDetected, PostCode
from niuchacz.decoding.seven_segment import SevenSegmentDecoder


@dataclass
class CardProfile:
    """Opis karty.

    display_order: które linie cyfr (DIG1=0 … DIG4=3) stoją na kolejnych pozycjach
                   wyświetlacza od lewej. Np. (3, 2, 1, 0): DIG1 to skrajna prawa cyfra.
    code_digits:   pozycje na wyświetlaczu (od lewej, 0 = pierwsza), z których składa się kod POST.
    prev_code_digits: pozycje, na których karta pokazuje POPRZEDNI kod (historia), np. (0, 1).
                   Pozwala odtworzyć kod, który mignął za szybko, by go złapać. Puste = brak.
    """
    name: str = "PC Analyzer 4-cyfrowa"
    digits: int = 4
    code_digits: tuple[int, ...] = (0, 1)
    display_order: tuple[int, ...] = ()
    prev_code_digits: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.display_order:
            self.display_order = tuple(range(self.digits))
        if sorted(self.display_order) != list(range(self.digits)):
            raise ValueError("display_order musi zawierać każdą linię cyfry dokładnie raz")

    @classmethod
    def from_dict(cls, data: dict) -> "CardProfile":
        return cls(
            name=str(data.get("name", cls.name)),
            digits=int(data.get("digits", 4)),
            code_digits=tuple(data.get("code_digits", (0, 1))),
            display_order=tuple(data.get("display_order", ())),
            prev_code_digits=tuple(data.get("prev_code_digits", ())),
        )

    def to_visual(self, by_line: str) -> str:
        """Znaki w kolejności linii DIG1..DIG4 -> napis tak, jak widać go na karcie."""
        return "".join(by_line[i] if i < len(by_line) else " " for i in self.display_order)

    def to_lines(self, visual: list) -> list:
        """Odwrotność to_visual: elementy w kolejności wyświetlacza -> kolejność linii DIG."""
        out = [None] * self.digits
        for pos, line in enumerate(self.display_order):
            out[line] = visual[pos]
        return out


class CodeAssembler:
    def __init__(self, decoder: SevenSegmentDecoder, profile: CardProfile,
                 clock: Callable[[], float] = time.monotonic):
        self.decoder = decoder
        self.profile = profile
        self._clock = clock
        self._last_display: Optional[str] = None
        self._last_code: Optional[PostCode] = None
        self._recent: list[str] = []      # ostatnie zapisane kody (do wykrywania migania A-B-A-B)
        self._flap: Optional[frozenset] = None
        self._last_change_at: Optional[float] = None
        self._hang_reported = False

    def reset(self) -> None:
        self._last_display = None
        self._last_code = None
        self._recent = []
        self._flap = None
        self._last_change_at = None
        self._hang_reported = False

    @property
    def current_code(self) -> Optional[PostCode]:
        return self._last_code

    def feed(self, frame: FrameEvent) -> Optional[CodeChange]:
        """Zwraca CodeChange tylko wtedy, gdy wyświetlacz się zmienił (ostatnią zmianę)."""
        changes = self.feed_all(frame)
        return changes[-1] if changes else None

    def _pair(self, display: str, positions: tuple[int, ...]) -> Optional[PostCode]:
        if not positions:
            return None
        return PostCode.parse("".join(display[i] for i in positions if i < len(display)))

    def feed_all(self, frame: FrameEvent) -> list[CodeChange]:
        """Zwraca zmiany wyświetlacza. Nowy kod POST = zmiana pary code_digits.

        Zmiana samej lewej pary (na tej karcie potrafi migać, np. 85/86 co 0,5 s) daje
        CodeChange z is_new=False: odświeża wyświetlacz w aplikacji, ale nie trafia do
        przebiegu i nie przesuwa licznika zawieszenia.

        Jeśli profil ma prev_code_digits (karta pokazuje "poprzedni | bieżący"), kod z lewej
        pary, który nie był zapisany, dopisujemy jako odtworzony (recovered=True).
        """
        display = self.profile.to_visual(self.decoder.decode(frame.digits_raw))
        if display == self._last_display:
            return []
        self._last_display = display
        code = self._pair(display, self.profile.code_digits)
        if code is None or code == self._last_code:
            return [CodeChange(code=code, display=display, ts_ms=frame.ts_ms, is_new=False)]
        if self._flap is not None and code.value in self._flap:
            # miganie dwóch kodów (np. BIOS czeka w pętli 85/86): nie zapisujemy kolejnych
            # przełączeń i nie zerujemy licznika zawieszenia
            self._last_code = code
            return [CodeChange(code=code, display=display, ts_ms=frame.ts_ms, is_new=False)]
        self._flap = None
        r = self._recent
        if len(r) >= 3 and code.value == r[-2] and r[-1] == r[-3]:
            # A B A -> B: to już miganie; B nie zapisujemy, od teraz ignorujemy parę {A, B}
            self._flap = frozenset((r[-1], code.value))
            self._last_code = code
            return [CodeChange(code=code, display=display, ts_ms=frame.ts_ms, is_new=False)]
        out: list[CodeChange] = []
        prev = self._pair(display, self.profile.prev_code_digits)
        if (prev is not None and self._last_code is not None and prev != self._last_code
                and prev != code and prev.value not in self._recent):
            out.append(CodeChange(code=prev, display=display, ts_ms=frame.ts_ms, recovered=True))
        self._last_code = code
        self._recent = (self._recent + [code.value])[-4:]
        self._last_change_at = self._clock()
        self._hang_reported = False
        out.append(CodeChange(code=code, display=display, ts_ms=frame.ts_ms))
        return out

    def feed_code(self, value: int, ts_ms: int) -> list[CodeChange]:
        """Tryb zatrzasku 74LCX374: kod przychodzi wprost jako bajt, bez wyświetlacza.

        Każda zmiana bajtu to prawdziwy zapis BIOS-u do portu 80h, więc nic nie trzeba
        odtwarzać z historii. Zostaje tylko tłumienie migania A-B-A-B (np. 85/86 przy F1).
        """
        code = PostCode(f"{value & 0xFF:02X}")
        prev = self._last_code.value if self._last_code else "--"
        if code == self._last_code:
            return []
        display = code.value + prev
        self._last_display = display
        if self._flap is not None and code.value in self._flap:
            self._last_code = code
            return [CodeChange(code=code, display=display, ts_ms=ts_ms, is_new=False)]
        self._flap = None
        r = self._recent
        if len(r) >= 3 and code.value == r[-2] and r[-1] == r[-3]:
            self._flap = frozenset((r[-1], code.value))
            self._last_code = code
            return [CodeChange(code=code, display=display, ts_ms=ts_ms, is_new=False)]
        self._last_code = code
        self._recent = (self._recent + [code.value])[-4:]
        self._last_change_at = self._clock()
        self._hang_reported = False
        return [CodeChange(code=code, display=display, ts_ms=ts_ms)]

    def idle_seconds(self) -> Optional[float]:
        """Ile sekund od ostatniej zmiany kodu (None – jeszcze nie było kodu)."""
        if self._last_change_at is None:
            return None
        return self._clock() - self._last_change_at

    def check_hang(self, hang_seconds: float) -> Optional[HangDetected]:
        """Wywoływane okresowo. Raportuje zawieszenie raz na każdy kod."""
        if self._last_change_at is None or self._hang_reported:
            return None
        idle = self._clock() - self._last_change_at
        if idle >= hang_seconds:
            self._hang_reported = True
            return HangDetected(code=self._last_code, seconds=idle)
        return None
