"""Tworzenie transportu na podstawie ustawień – jedyne miejsce wyboru implementacji."""
from __future__ import annotations

from niuchacz.decoding.seven_segment import SegmentMap
from niuchacz.domain.enums import TransportKind
from niuchacz.transport.base import Transport
from niuchacz.transport.serial_transport import SerialTransport
from niuchacz.transport.tcp_transport import TcpTransport


def create_transport(kind: TransportKind, settings: dict, segment_map: SegmentMap,
                     digits: int = 4, profile=None) -> Transport:
    if kind is TransportKind.TCP:
        tcp = settings.get("tcp", {})
        return TcpTransport(tcp.get("host", "192.168.4.1"), int(tcp.get("port", 7080)))
    ser = settings.get("serial", {})
    return SerialTransport(ser.get("port", "COM3"), int(ser.get("baud", 115200)))
