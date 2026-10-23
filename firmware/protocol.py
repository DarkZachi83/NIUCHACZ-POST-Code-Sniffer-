# NIUCHACZ firmware – protokół JSON lines (wspólny dla Wi-Fi i USB)

import json

import config


def line(obj):
    return json.dumps(obj)


def hello():
    return line({"t": "hello", "fw": config.FW_VERSION, "ch": config.CHANNELS})


def frame(digits, ts):
    return line({"t": "frame", "d": [digits[0], digits[1], digits[2], digits[3]], "ts": ts})


def code(value, ts):
    return line({"t": "code", "c": value, "ts": ts})


def leds(state, ts):
    msg = {"t": "led", "ts": ts}
    msg.update(state)
    return line(msg)


def session(sid, ts):
    return line({"t": "session", "id": sid, "ts": ts})


def heartbeat(ts):
    return line({"t": "hb", "ts": ts})


def error(msg):
    return line({"t": "err", "msg": msg})


def reply(cmd, **data):
    msg = {"re": cmd}
    msg.update(data)
    return line(msg)


def parse_command(text):
    try:
        msg = json.loads(text)
    except ValueError:
        return None
    if isinstance(msg, dict) and "cmd" in msg:
        return msg
    return None
