"""Firmware: ślepe przerwy między oknami, kolejka USB, flaga "g" (CPython z podstawionymi modułami)."""
import contextlib
import importlib
import io
import json
import sys
import time
import types
import unittest
from pathlib import Path

FW = Path(__file__).resolve().parents[1] / "firmware"


class Clock:
    def __init__(self):
        self.us = 1_000_000

    def ticks_us(self):
        return self.us

    def ticks_ms(self):
        return self.us // 1000


def stub(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


class FirmwareGapTest(unittest.TestCase):
    def setUp(self):
        self.clock = clk = Clock()
        self.saved_time = {k: getattr(time, k, None) for k in ("ticks_us", "ticks_ms", "ticks_diff", "sleep_ms")}
        time.ticks_us, time.ticks_ms = clk.ticks_us, clk.ticks_ms
        time.ticks_diff = lambda a, b: a - b
        time.sleep_ms = lambda ms: None
        self.saved_mods = {k: sys.modules.get(k) for k in
                           ("machine", "config", "sampler", "demo", "net_server", "session_store",
                            "usb_link", "protocol", "main")}
        stub("machine", Pin=type("Pin", (), {"IN": 0, "PULL_UP": 0, "__init__": lambda s, *a: None,
                                             "value": lambda s: 0}))
        stub("config", INPUT_MODE="latch", LEDS_CONNECTED=False, RST_ACTIVE_HIGH=False, DEBOUNCE_MS=16,
             USB_ENABLED=True, HEARTBEAT_MS=1000, FW_VERSION="t", CHANNELS=16)
        self.windows = []          # kolejne okna: lista (idx, surowy bajt)
        self.usb_out = []

        def latch_window(n, quiet, maxn, last, vals, idx, maxcnt, act):
            changes = self.windows.pop(0) if self.windows else []
            for k, (i, b) in enumerate(changes):
                idx[k], vals[k] = i, b
            clk.us += 50_000                       # okno trwa 50 ms
            return len(changes)

        stub("sampler", LATCH_BUF=256, LATCH_SAMPLES=1, LATCH_QUIET=1, LATCH_MAX=1, IMPL="python", SINGLE=0x20000000, is_mix=None,
             setup_pins=lambda: None, build_remap=lambda: bytes(range(256)), latch_window=latch_window)
        stub("demo")
        stub("net_server", NetServer=lambda cb: types.SimpleNamespace(broadcast=lambda t: None))
        store = lambda: types.SimpleNamespace(append=lambda t: None, flush=lambda: None, start=lambda: 1)
        stub("session_store", SessionStore=store, NullStore=store)

        def send(text):
            clk.us += 3000                         # UART 115200: ok. 3 ms na linię
            self.usb_out.append(text)
        stub("usb_link", UsbLink=lambda cb, en: types.SimpleNamespace(enabled=en, send=send, poll=lambda: None))
        sys.path.insert(0, str(FW))
        sys.modules.pop("protocol", None)
        sys.modules.pop("main", None)
        with contextlib.redirect_stdout(io.StringIO()):
            self.main = importlib.import_module("main")    # _safe_start(): BOOT "wciśnięty" -> REPL
        self.fw = self.main.Niuchacz()

    def tearDown(self):
        for k, v in self.saved_time.items():
            if v is None:
                delattr(time, k)
            else:
                setattr(time, k, v)
        for k, v in self.saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.path.remove(str(FW))

    def codes(self):
        return [json.loads(x) for x in self.usb_out if '"code"' in x]

    def test_change_during_gap_is_flagged(self):
        fw = self.fw
        self.windows = [[(500, 0x78)], [], [(1, 0xB1), (900, 0x00)]]
        fw.process_latch(self.clock.ticks_ms())            # pierwsze okno: brak przerwy do zmierzenia
        fw.drain_codes()
        fw.process_latch(self.clock.ticks_ms())
        self.clock.us += 12_000                            # np. zapis flash / USB – ESP32 nie patrzy
        fw.process_latch(self.clock.ticks_ms())
        self.assertEqual(2, len(fw.code_q))                # obróbka dopiero między oknami
        fw.drain_codes(10)
        fw.usb_pump(10**9)
        c = self.codes()
        self.assertEqual([0x78, 0xB1, 0x00], [x["c"] for x in c])
        self.assertNotIn("g", c[0])
        self.assertEqual(12_000, c[1]["g"])                # B1 pojawił się w przerwie
        self.assertNotIn("g", c[2])                        # 00 widziany w trakcie okna
        self.assertEqual(12_000, fw.gap_max_us)

    def test_usb_is_sent_in_small_portions(self):
        fw = self.fw
        for v in range(10):
            fw.emit('{"t":"code","c":%d,"ts":0}' % v)
        self.assertEqual([], self.usb_out)                 # emit nie blokuje na USB
        fw.usb_pump()
        self.assertEqual(2, len(self.usb_out))             # najwyżej ok. 5 ms na przerwę
        for _ in range(4):
            fw.usb_pump()
        self.assertEqual(10, len(self.usb_out))


if __name__ == "__main__":
    unittest.main()


class SessionStoreTest(unittest.TestCase):
    """Sesje na flashu: nic nie dotyka systemu plików przed flush()."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {k: sys.modules.get(k) for k in ("config", "session_store")}
        stub("config", SESSION_DIR=self.tmp.name + "/s", MAX_SESSIONS=2)
        sys.path.insert(0, str(FW))
        sys.modules.pop("session_store", None)
        self.mod = importlib.import_module("session_store")

    def tearDown(self):
        sys.path.remove(str(FW))
        for k, v in self.saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        self.tmp.cleanup()

    def test_no_flash_until_flush(self):
        import os
        st = self.mod.SessionStore()
        d = self.tmp.name + "/s"
        self.assertEqual(1, st.start())
        st.append("a")
        self.assertEqual(2, st.start())
        st.append("b")
        st.append("c")
        self.assertEqual([], os.listdir(d))              # nic jeszcze nie zapisane
        self.assertEqual([1, 2], st.list_ids())
        st.flush()
        self.assertEqual(["a"], list(st.read_lines(1)))
        self.assertEqual(["b", "c"], list(st.read_lines(2)))
        st.start(); st.append("d"); st.flush()            # 3 sesje, limit 2 -> najstarsza znika
        self.assertEqual([2, 3], st.list_ids())
        st.clear()
        self.assertEqual([], st.list_ids())

    def test_full_buffer_drops_oldest_instead_of_writing(self):
        import os
        st = self.mod.SessionStore()
        st.start()
        for i in range(self.mod.BUF_MAX + 5):
            st.append(str(i))
        self.assertEqual([], os.listdir(self.tmp.name + "/s"))   # żadnego zapisu w trakcie
        st.flush()
        lines = list(st.read_lines(1))
        self.assertEqual(self.mod.BUF_MAX, len(lines))
        self.assertEqual("5", lines[0])
