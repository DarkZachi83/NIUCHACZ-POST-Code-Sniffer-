"""Transport Wi-Fi: TCP do ESP32 (domyślnie AP 192.168.4.1:7080)."""
from __future__ import annotations

import socket
from typing import Optional

from niuchacz.i18n import t
from niuchacz.transport.base import Transport, TransportError


class TcpTransport(Transport):
    name = "Wi-Fi"

    def __init__(self, host: str = "192.168.4.1", port: int = 7080, connect_timeout: float = 5.0):
        self.host, self.port, self.connect_timeout = host, port, connect_timeout
        self._sock: Optional[socket.socket] = None
        self._buf = b""

    def open(self) -> None:
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        except OSError as exc:
            raise TransportError(t("tcp.connect_failed", host=self.host, port=self.port, error=exc)) from exc
        self._buf = b""

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            finally:
                self._sock = None

    @property
    def is_open(self) -> bool:
        return self._sock is not None

    def read_line(self, timeout: float = 0.5) -> Optional[str]:
        if not self._sock:
            raise TransportError(t("tcp.closed"))
        while b"\n" not in self._buf:
            self._sock.settimeout(timeout)
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                return None
            except OSError as exc:
                raise TransportError(t("tcp.read_error", error=exc)) from exc
            if not chunk:
                raise TransportError(t("tcp.esp_closed"))
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line.decode("utf-8", errors="replace").rstrip("\r")

    def write_line(self, line: str) -> None:
        if not self._sock:
            raise TransportError(t("tcp.closed"))
        self._sock.sendall(line.encode("utf-8") + b"\n")
