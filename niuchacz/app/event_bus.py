"""Prosta szyna zdarzeń publish/subscribe między kontrolerem a widokami."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger(__name__)

# nazwy tematów w jednym miejscu
CONNECTION = "connection"          # (ConnectionState, opis)
DEVICE = "device"                  # DeviceHello
CODE = "code"                      # CodeChange
LEDS = "leds"                      # LedState
DIAGNOSIS = "diagnosis"            # (Diagnosis, tekst)
SEQUENCE = "sequence"              # (SequenceItem, czas względny ms)
SESSION = "session"                # Session (nowa sesja)
SESSION_END = "session_end"        # Session (zakończona, z wynikiem) – otwiera okno raportu
HANG = "hang"                      # HangDetected
GOLDEN = "golden"                  # tekst porównania ze wzorcem
STATUS = "status"                  # str – pasek stanu
REPLY = "reply"                    # CommandReply


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Callable[[Any], None]) -> None:
        self._subs[topic].append(handler)

    def publish(self, topic: str, payload: Any = None) -> None:
        for handler in list(self._subs.get(topic, ())):
            try:
                handler(payload)
            except Exception:  # widok nie może wywrócić całej aplikacji
                log.exception("Błąd obsługi zdarzenia %s", topic)
