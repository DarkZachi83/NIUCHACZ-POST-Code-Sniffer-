"""Test logiki bitowej firmware na CPython: podstawiamy udawany moduł `machine`."""
import sys
import types
import unittest
from pathlib import Path

FW = Path(__file__).resolve().parents[1] / "firmware"

SEG_PINS = (16, 17, 18, 19, 21, 22, 23, 25)
DIG_PINS = (26, 27, 32, 33)
LED_PINS = (34, 35, 36, 39)   # CLK, IRDY, FRAME, RESET


class FakeMem:
    """Odtwarza zadaną listę stanów pinów; każdy stan zajmuje parę odczytów (IN, IN1)."""
    def __init__(self, states):
        self.states = states
        self.i = 0
        self._cur = None

    def __getitem__(self, addr):
        if addr == 0x3FF4403C:
            self._cur = self.states[self.i % len(self.states)]
            self.i += 1
            return self._cur & 0xFFFFFFFF
        return (self._cur >> 32) & 0xFF


def pins_state(seg_byte, digit, leds=(0, 0, 0, 0)):
    v = 0
    for bit, pin in enumerate(SEG_PINS):
        if seg_byte & (1 << bit):
            v |= 1 << pin
    v |= 1 << DIG_PINS[digit]
    for on, pin in zip(leds, LED_PINS):
        if on:
            v |= 1 << pin
    return v


class SamplerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake = types.ModuleType("machine")
        fake.Pin = type("Pin", (), {"IN": 0, "__init__": lambda self, *a: None})
        fake.mem32 = FakeMem([0])
        sys.modules["machine"] = fake
        sys.path.insert(0, str(FW))
        sys.modules.pop("sampler", None)
        import sampler  # noqa: E402
        cls.sampler = sampler
        cls.fake = fake

    def test_python_impl_selected_on_cpython(self):
        self.assertEqual(self.sampler.IMPL, "python")

    def test_four_digits_with_ghosts(self):
        pats = (0x39, 0x06, 0x40, 0x40)   # C 1 - -
        n = self.sampler.MIN_RUN
        states = []
        for d, p in enumerate(pats):
            # prawdziwa cyfra długo, potem duch "8" – też dłuższy niż MIN_RUN (zdarza się na karcie)
            states += [pins_state(p, d, (1, 0, 0, 0))] * (3 * n) + [pins_state(p, d, (0, 1, 0, 0))] * (3 * n)
            states += [pins_state(0x7F, d)] * (2 * n)
            states += [pins_state(0x00, d)] * 10
        self.fake.mem32 = FakeMem(states)
        digits, act = bytearray(4), bytearray(2)
        captured = self.sampler.sample_window(len(states), digits, act, 0)
        self.assertEqual(captured, 4)
        self.assertEqual(list(digits), list(pats))
        leds = self.sampler.leds_from_activity(act[0], act[1], True)
        self.assertEqual(leds, {"clk": 1, "irdy": 1, "frame": 0, "rst": 0})

    def test_short_glimpse_keeps_previous(self):
        # cyfra widziana tylko przez chwilę (krócej niż MIN_RUN) – zostaje poprzednia wartość
        self.fake.mem32 = FakeMem([pins_state(0x7F, 0)] * 5)
        digits, act = bytearray(b"\x01\x02\x03\x04"), bytearray(2)
        self.sampler.sample_window(5, digits, act, 0)
        self.assertEqual(list(digits), [1, 2, 3, 4])

    def test_reset_level(self):
        self.fake.mem32 = FakeMem([pins_state(0, 0, (1, 0, 0, 1))] * 10)
        digits, act = bytearray(4), bytearray(2)
        self.sampler.sample_window(10, digits, act, 0)
        self.assertEqual(self.sampler.leds_from_activity(act[0], act[1], True)["rst"], 1)
        self.assertEqual(self.sampler.leds_from_activity(act[0], act[1], False)["rst"], 0)


def latch_state(byte):
    """Stan pinów, z którego sampler.latch_byte() odczyta `byte`."""
    return ((byte & 0x0F) << 16) | ((byte & 0x70) << 17) | ((byte & 0x80) << 19)


class LatchSingleReadTest(unittest.TestCase):
    """Krótkie kody (ok. 1 µs = jeden odczyt): przyjmować, ale nie stany przejściowe."""

    @classmethod
    def setUpClass(cls):
        SamplerTest.setUpClass.__func__(cls)

    def run_seq(self, seq, last):
        self.fake.mem32 = FakeMem([latch_state(b) for b in seq])
        vals, idx = bytearray(16), [0] * 16
        n = self.sampler._latch_python(len(seq), 1, len(seq), last, vals, idx, 16)
        single = self.sampler.SINGLE
        return [(f"{vals[k]:02X}", bool(idx[k] & single)) for k in range(n)]

    def test_short_code_between_neighbours_is_kept(self):
        # C3 stoi, C4 tylko jeden odczyt, potem C5
        out = self.run_seq([0xC3, 0xC3, 0xC4, 0xC5, 0xC5, 0xC5], last=0xC2)
        self.assertEqual([("C3", False), ("C4", True), ("C5", False)], out)

    def test_transition_glitch_is_dropped(self):
        # C3 -> C5: w trakcie przełączania odczyt C1 (bity wspólne) – to mieszanka, nie kod
        self.assertTrue(self.sampler.is_mix(0xC1, 0xC3, 0xC5))
        out = self.run_seq([0xC3, 0xC3, 0xC1, 0xC5, 0xC5], last=0xC2)
        self.assertEqual([("C3", False), ("C5", False)], out)

    def test_single_spike_back_to_same_code_is_dropped(self):
        out = self.run_seq([0x2A, 0x2A, 0x6A, 0x2A, 0x2A], last=0x2A)
        self.assertEqual([], out)


if __name__ == "__main__":
    unittest.main()
