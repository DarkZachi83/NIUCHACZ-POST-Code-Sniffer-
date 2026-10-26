# NIUCHACZ firmware – protokół JSON lines (wspólny dla Wi-Fi i USB)

import json

import config


def line(obj):
    return json.dumps(obj)


def hello():
    return line({"t": "hello", "fw": config.FW_VERSION, "ch": config.CHANNELS})


def frame(digits, ts):
    return line({"t": "frame", "d": [digits[0], digits[1], digits[2], digits[3]], "ts": ts})


def code(value, ts, gap_us=0, single=0):
    msg = {"t": "code", "c": value, "ts": ts}
    if gap_us:
        msg["g"] = gap_us      # kod zmienił się w ślepej przerwie tylu µs – przed nim mogły zginąć kody
    if single:
        msg["s"] = 1           # widziany w jednym odczycie (ok. 1 µs) – krótki kod, mniej pewny
    return line(msg)


def leds(state, ts):
    msg = {"t": "led", "ts": ts}
    msg.update(state)
    return line(msg)


def session(sid, ts):
    return line({"t": "session", "id": sid, "ts": ts})


def heartbeat(ts, gap_max_us=0, blind_permille=0):
    # gm = najdłuższa ślepa przerwa w ostatniej sekundzie [µs], bl = część czasu bez odczytu [‰]
    return line({"t": "hb", "ts": ts, "gm": gap_max_us, "bl": blind_permille})


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
