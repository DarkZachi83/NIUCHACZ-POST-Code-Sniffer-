"""Parser protokołu JSON lines: jedna linia od ESP32 -> zdarzenie domenowe."""
from __future__ import annotations

import json
from typing import Optional

from niuchacz.domain.models import (
    CodeEvent, CommandReply, DeviceError, DeviceHello, FrameEvent, Heartbeat,
    LedState, ReplayEvent, SessionStart,
)


class ProtocolError(ValueError):
    pass


def parse_line(line: str) -> Optional[object]:
    """Zwraca zdarzenie albo None dla pustej linii. Rzuca ProtocolError dla śmieci."""
    line = (line or "").strip()
    if not line:
        return None
    if not line.startswith("{"):
        # np. komunikaty REPL MicroPythona na USB - ignorujemy
        return None
    try:
        msg = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Niepoprawny JSON: {line[:60]}") from exc
    if not isinstance(msg, dict):
        raise ProtocolError("Komunikat nie jest obiektem JSON")
    return parse_message(msg)


def parse_message(msg: dict) -> Optional[object]:
    if "re" in msg:
        data = {k: v for k, v in msg.items() if k != "re"}
        return CommandReply(command=str(msg["re"]), data=data)

    kind = msg.get("t")
    ts = int(msg.get("ts", 0))
    if kind == "hello":
        return DeviceHello(firmware=str(msg.get("fw", "?")), channels=int(msg.get("ch", 0)))
    if kind == "frame":
        digits = msg.get("d")
        if not isinstance(digits, list) or not all(isinstance(x, int) for x in digits):
            raise ProtocolError("Ramka bez listy cyfr 'd'")
        return FrameEvent(digits_raw=tuple(x & 0xFF for x in digits), ts_ms=ts)
    if kind == "code":
        c = msg.get("c")
        if not isinstance(c, int):
            raise ProtocolError("Kod bez pola 'c'")
        return CodeEvent(code=c & 0xFF, ts_ms=ts)
    if kind == "led":
        return LedState(
            clk=bool(msg.get("clk", 0)), irdy=bool(msg.get("irdy", 0)),
            frame=bool(msg.get("frame", 0)), rst=bool(msg.get("rst", 0)), ts_ms=ts,
        )
    if kind == "session":
        return SessionStart(session_id=int(msg.get("id", 0)), ts_ms=ts)
    if kind == "hb":
        return Heartbeat(ts_ms=ts)
    if kind == "err":
        return DeviceError(message=str(msg.get("msg", "")))
    if kind == "replay":
        inner = msg.get("ev")
        if not isinstance(inner, dict):
            raise ProtocolError("Replay bez pola 'ev'")
        return ReplayEvent(session_id=int(msg.get("id", 0)), event=parse_message(inner))
    raise ProtocolError(f"Nieznany typ komunikatu: {kind!r}")
