"""Interfejs transportu: skąd płyną linie protokołu."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class TransportError(IOError):
    pass


class Transport(ABC):
    """Wszystkie transporty (Wi-Fi, USB) mówią tym samym protokołem."""

    name: str = "transport"

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def read_line(self, timeout: float = 0.5) -> Optional[str]:
        """Zwraca jedną linię bez \\n albo None po upływie timeoutu."""

    @abstractmethod
    def write_line(self, line: str) -> None: ...

    @property
    @abstractmethod
    def is_open(self) -> bool: ...
