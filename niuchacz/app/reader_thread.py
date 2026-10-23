"""Wątek czytający transport. Nie dotyka GUI – wszystko trafia do kolejki."""
from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

from niuchacz.domain.models import DeviceError
from niuchacz.protocol.parser import ProtocolError, parse_line
from niuchacz.transport.base import Transport, TransportError

log = logging.getLogger(__name__)


class TransportClosed:
    """Znacznik w kolejce: transport się zamknął (opcjonalnie z powodem)."""
    def __init__(self, reason: str = ""):
        self.reason = reason


class ReaderThread(threading.Thread):
    def __init__(self, transport: Transport, out: "queue.Queue[object]"):
        super().__init__(name="niuchacz-reader", daemon=True)
        self.transport = transport
        self.out = out
        self._stop_evt = threading.Event()

    def stop(self) -> None:
        self._stop_evt.set()

    def run(self) -> None:
        reason = ""
        try:
            while not self._stop_evt.is_set():
                line: Optional[str] = self.transport.read_line(timeout=0.3)
                if line is None:
                    continue
                try:
                    event = parse_line(line)
                except ProtocolError as exc:
                    log.warning("%s", exc)
                    self.out.put(DeviceError(message=str(exc)))
                    continue
                if event is not None:
                    self.out.put(event)
        except TransportError as exc:
            reason = str(exc)
        except Exception as exc:  # nieoczekiwany błąd – raportujemy, nie zabijamy GUI
            log.exception("Wątek czytający przerwany")
            reason = f"Nieoczekiwany błąd: {exc}"
        finally:
            self.out.put(TransportClosed(reason if not self._stop_evt.is_set() else ""))
