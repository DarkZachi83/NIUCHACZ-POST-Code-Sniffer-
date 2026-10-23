"""Transport USB (port COM) – do debugowania ESP32 podłączonego kablem."""
from __future__ import annotations

from typing import Optional

from niuchacz.transport.base import Transport, TransportError

try:
    import serial  # pyserial
    from serial.tools import list_ports
except ImportError:  # aplikacja działa też bez pyserial (Wi-Fi)
    serial = None
    list_ports = None


def available_ports() -> list[str]:
    if list_ports is None:
        return []
    return [p.device for p in list_ports.comports()]


class SerialTransport(Transport):
    name = "USB"

    def __init__(self, port: str = "COM3", baud: int = 115200):
        self.port, self.baud = port, baud
        self._ser = None

    def open(self) -> None:
        if serial is None:
            raise TransportError("Brak pakietu pyserial: pip install pyserial")
        ports = available_ports()
        if self.port not in ports and len(ports) == 1:
            # np. w ustawieniach zostało "COM3", a na Linuksie jest /dev/ttyUSB0
            self.port = ports[0]
        ser = serial.Serial()
        ser.port, ser.baudrate, ser.timeout = self.port, self.baud, 0.5
        # DTR/RTS sterują resetem (EN) i trybem programowania (IO0) ESP32.
        # Ustawione przed otwarciem portu: połączenie nie restartuje urządzenia
        # i nie wprowadza go w tryb wgrywania.
        ser.dtr = False
        ser.rts = False
        try:
            ser.open()
        except serial.SerialException as exc:
            hint = " (zamknij Thonny – port może mieć otwarty tylko jeden program)" if "busy" in str(exc).lower() \
                or "denied" in str(exc).lower() or "odmow" in str(exc).lower() else ""
            if not hint:
                hint = (f" – dostępne porty: {', '.join(ports)}; wybierz właściwy w Ustawieniach" if ports
                        else " – system nie widzi żadnego portu USB: sprawdź kabel (czy nie tylko do ładowania)")
            raise TransportError(f"Nie można otworzyć {self.port}: {exc}{hint}") from exc
        self._ser = ser

    def close(self) -> None:
        if self._ser:
            self._ser.close()
            self._ser = None

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def read_line(self, timeout: float = 0.5) -> Optional[str]:
        if not self._ser:
            raise TransportError("Port zamknięty")
        self._ser.timeout = timeout
        try:
            raw = self._ser.readline()
        except serial.SerialException as exc:
            raise TransportError(f"Błąd portu: {exc}") from exc
        if not raw:
            return None
        return raw.decode("utf-8", errors="replace").rstrip("\r\n")

    def write_line(self, line: str) -> None:
        if not self._ser:
            raise TransportError("Port zamknięty")
        self._ser.write(line.encode("utf-8") + b"\n")
