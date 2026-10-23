"""Budowanie komend PC -> ESP32 (jedna linia JSON)."""
import json


def _line(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"))


def ping() -> str:
    return _line({"cmd": "ping"})


def set_debounce(ms: int) -> str:
    return _line({"cmd": "set", "debounce_ms": int(ms)})


def raw_dump(on: bool) -> str:
    return _line({"cmd": "raw_dump", "on": bool(on)})


def list_sessions() -> str:
    return _line({"cmd": "list_sessions"})


def get_session(session_id: int) -> str:
    return _line({"cmd": "get_session", "id": int(session_id)})


def clear_sessions() -> str:
    return _line({"cmd": "clear_sessions"})
