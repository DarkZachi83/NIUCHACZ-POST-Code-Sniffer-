"""Wyliczenia domenowe NIUCHACZA."""
from enum import Enum


class BiosVendor(str, Enum):
    AWARD = "award"
    AMI = "ami"
    PHOENIX = "phoenix"

    @property
    def label(self) -> str:
        return {"award": "Award", "ami": "AMI", "phoenix": "Phoenix"}[self.value]


class ConnectionState(str, Enum):
    DISCONNECTED = "rozłączony"
    CONNECTING = "łączenie"
    CONNECTED = "połączony"
    ERROR = "błąd"


class TransportKind(str, Enum):
    TCP = "tcp"
    SERIAL = "serial"

    @property
    def label(self) -> str:
        return {"tcp": "Wi-Fi (TCP)", "serial": "USB (COM)"}[self.value]
