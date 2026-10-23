"""Udawane ESP32 dla testów (dawny symulator aplikacji – usunięty z programu 18.10.2026).

Generuje dokładnie te same linie JSON co prawdziwy firmware, a cyfry koduje
przez tę samą mapę segmentów, więc ćwiczy całą ścieżkę dekodowania.
Scenariusze opisują sekwencje kodów; to dane przykładowe, nie pomiar.
"""
from __future__ import annotations

import json
import queue
import random
import threading
import time
from typing import Optional

from niuchacz.decoding.seven_segment import SegmentMap, SevenSegmentDecoder
from niuchacz.transport.base import Transport, TransportError

# (kod, czas trwania w sekundach); ostatni element bez wyjścia = zawieszenie
SCENARIOS: dict[str, dict] = {
    "normal": {
        "label": "Sprawna płyta",
        "steps": [("CF", .4), ("C0", .4), ("C1", .9), ("C3", .5), ("C5", .4), ("01", .3),
                  ("03", .3), ("05", .3), ("07", .4), ("0E", .3), ("13", .3), ("2B", .6),
                  ("41", .5), ("52", .4), ("FF", 0)],
        "hang": False,
    },
    "no_ram": {
        "label": "Brak / uszkodzony RAM",
        "steps": [("CF", .4), ("C0", .4), ("C1", 0)],
        "hang": True,
    },
    "no_vga": {
        "label": "Brak karty graficznej",
        "steps": [("CF", .4), ("C0", .4), ("C1", .9), ("C3", .5), ("C5", .4), ("01", .3),
                  ("03", .3), ("05", .3), ("07", .4), ("0E", .3), ("13", .3), ("2B", 0)],
        "hang": True,
    },
    "dead": {
        "label": "Martwa płyta (brak startu BIOS)",
        "steps": [("FF", 0)],
        "hang": True,
    },
}


class MockTransport(Transport):
    name = "Symulator"

    def __init__(self, segment_map: Optional[SegmentMap] = None, scenario: str = "normal",
                 digits: int = 4, speed: float = 1.0, loop: bool = True, profile=None):
        from niuchacz.decoding.code_assembler import CardProfile
        self.segment_map = segment_map or SegmentMap()
        self.profile = profile or CardProfile(digits=digits)
        self.scenario = scenario if scenario in SCENARIOS else "normal"
        self.digits = digits
        self.speed = speed
        self.loop = loop
        self._out: "queue.Queue[str]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._t0 = 0.0
        self._session_id = 0

    # ---- Transport ----

    def open(self) -> None:
        self._stop.clear()
        self._t0 = time.monotonic()
        self._thread = threading.Thread(target=self._run, name="niuchacz-mock", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    @property
    def is_open(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def read_line(self, timeout: float = 0.5) -> Optional[str]:
        if not self.is_open and self._out.empty():
            raise TransportError("Symulator zatrzymany")
        try:
            return self._out.get(timeout=timeout)
        except queue.Empty:
            return None

    def write_line(self, line: str) -> None:
        try:
            cmd = json.loads(line).get("cmd")
        except (ValueError, AttributeError):
            return
        if cmd == "ping":
            self._emit({"re": "ping", "ok": True})
        elif cmd == "list_sessions":
            self._emit({"re": "list_sessions", "ids": list(range(1, self._session_id + 1))})
        else:
            self._emit({"re": cmd, "ok": True, "note": "symulator"})

    # ---- generator ----

    def _ts(self) -> int:
        return int((time.monotonic() - self._t0) * 1000)

    def _emit(self, obj: dict) -> None:
        self._out.put(json.dumps(obj, separators=(",", ":")))

    def _frame(self, code: str) -> dict:
        # napis tak, jak na karcie: kod na pozycjach code_digits, reszta "-"
        visual = ["-"] * self.digits
        for pos, ch in zip(self.profile.code_digits, code):
            if pos < self.digits:
                visual[pos] = ch
        by_line = self.profile.to_lines(visual)
        raw = [self.segment_map.canonical_to_raw(SevenSegmentDecoder.encode_char(c)) for c in by_line]
        return {"t": "frame", "d": raw, "ts": self._ts()}

    def _sleep(self, seconds: float) -> bool:
        """Śpi, wysyłając heartbeat i stan diod. Zwraca False, gdy trzeba kończyć."""
        end = time.monotonic() + seconds / self.speed
        while time.monotonic() < end:
            if self._stop.wait(min(0.25, max(0.0, end - time.monotonic()))):
                return False
        return True

    def _leds(self, rst: bool, bus_active: bool) -> None:
        self._emit({"t": "led", "clk": 1, "irdy": int(bus_active), "frame": int(bus_active),
                    "rst": int(rst), "ts": self._ts()})

    def _run(self) -> None:
        self._emit({"t": "hello", "fw": "symulator-0.1", "ch": 16})
        scen = SCENARIOS[self.scenario]
        while not self._stop.is_set():
            # impuls RESET = nowa sesja
            self._leds(rst=True, bus_active=False)
            if not self._sleep(0.3):
                return
            self._session_id += 1
            self._leds(rst=False, bus_active=True)
            self._emit({"t": "session", "id": self._session_id, "ts": self._ts()})
            for code, dur in scen["steps"]:
                self._emit(self._frame(code))
                if dur == 0:
                    break
                jitter = dur * random.uniform(0.9, 1.1)
                if not self._sleep(jitter):
                    return
            # stan końcowy: zawieszenie albo FF (start systemu)
            last_hb = time.monotonic()
            hold = 12.0 if scen["hang"] else 8.0
            end = time.monotonic() + hold / self.speed
            self._leds(rst=False, bus_active=not scen["hang"])
            while time.monotonic() < end:
                if self._stop.wait(0.25):
                    return
                if time.monotonic() - last_hb >= 1.0:
                    self._emit({"t": "hb", "ts": self._ts()})
                    last_hb = time.monotonic()
            if not self.loop:
                return
