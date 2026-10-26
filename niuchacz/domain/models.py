"""Modele domenowe. Czysta logika: bez importów z innych warstw NIUCHACZA."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------- zdarzenia z urządzenia (po sparsowaniu protokołu) ----------

@dataclass(frozen=True)
class DeviceHello:
    firmware: str
    channels: int


@dataclass(frozen=True)
class CodeEvent:
    """Bajt kodu POST odczytany wprost z zatrzasku karty (tryb 74LCX374)."""
    code: int
    ts_ms: int
    gap_us: int = 0      # bajt zmienił się w ślepej przerwie ESP32 – przed nim mogły zginąć kody
    single: bool = False  # widziany w jednym odczycie (kod trwał ok. 1 µs)


@dataclass(frozen=True)
class FrameEvent:
    """Surowe bajty segmentów dla każdej cyfry wyświetlacza karty."""
    digits_raw: tuple[int, ...]
    ts_ms: int


@dataclass(frozen=True)
class LedState:
    clk: bool
    irdy: bool
    frame: bool
    rst: bool
    ts_ms: int


@dataclass(frozen=True)
class SessionStart:
    session_id: int
    ts_ms: int


@dataclass(frozen=True)
class Heartbeat:
    ts_ms: int
    gap_max_us: int = 0       # najdłuższa przerwa w odczycie w ostatniej sekundzie
    blind_permille: int = 0   # część czasu bez odczytu [‰]


@dataclass(frozen=True)
class DeviceError:
    message: str


@dataclass(frozen=True)
class CommandReply:
    command: str
    data: dict


@dataclass(frozen=True)
class ReplayEvent:
    """Zdarzenie odtworzone z sesji zapisanej na ESP32."""
    session_id: int
    event: object


# ---------- pojęcia diagnostyczne ----------

@dataclass(frozen=True)
class PostCode:
    value: str  # zawsze 2 znaki hex, wielkie litery, np. "C1"

    @staticmethod
    def parse(text: str) -> Optional["PostCode"]:
        t = (text or "").strip().upper()
        if len(t) == 2 and all(c in "0123456789ABCDEF" for c in t):
            return PostCode(t)
        return None

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class CodeChange:
    """Kod POST pojawił się na wyświetlaczu karty."""
    code: Optional[PostCode]   # None, gdy wyświetlacz pokazuje coś nie-hex
    display: str               # pełny tekst wszystkich cyfr, np. "C1--"
    ts_ms: int
    recovered: bool = False    # kod odtworzony z historii karty (lewa para cyfr) – był za krótki
    is_new: bool = True        # False: zmieniła się tylko reszta wyświetlacza, kod POST ten sam
    gap_us: int = 0            # tryb zatrzasku: kod złapany po ślepej przerwie (patrz CodeEvent)
    single: bool = False       # tryb zatrzasku: jeden odczyt (patrz CodeEvent)


@dataclass(frozen=True)
class HangDetected:
    code: Optional[PostCode]
    seconds: float
    kind: str = "stop"         # "stop" = postój, "wait" = czeka na użytkownika, "done" = koniec POST


@dataclass
class CodeEntry:
    """Jeden wpis bazy kodów (może być wiele wpisów dla jednego kodu)."""
    code: str
    vendor: str
    stage: str
    fault: str = ""
    check: str = ""
    bios_version: str = ""
    board: str = ""
    author: str = ""
    source: str = ""
    confidence: str = "unverified"
    kind: str = ""             # "wait" = BIOS czeka na użytkownika (F1, Setup) – nie awaria


@dataclass
class Diagnosis:
    code: PostCode
    vendor: str
    entries: list[CodeEntry] = field(default_factory=list)

    @property
    def known(self) -> bool:
        return bool(self.entries)


@dataclass
class SequenceItem:
    code: str
    ts_ms: int
    recovered: bool = False    # odtworzony z historii karty, nie widziany bezpośrednio
    gap_us: int = 0            # złapany po ślepej przerwie ESP32 – wcześniejsze kody mogły zginąć
    single: bool = False       # widziany w jednym odczycie ESP32 (ok. 1 µs) – mniej pewny


@dataclass
class Divergence:
    """Wynik porównania z wzorcem."""
    index: int                 # pozycja pierwszej różnicy, -1 gdy zgodne
    expected: Optional[str]
    actual: Optional[str]
    matched: int

    @property
    def identical(self) -> bool:
        return self.index == -1
