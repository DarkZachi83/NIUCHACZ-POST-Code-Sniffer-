"""Kolejność cyfr karty (DIG1 = prawa cyfra) i mapa segmentów z pomiaru dE24."""
import unittest

from niuchacz.decoding.code_assembler import CardProfile, CodeAssembler
from niuchacz.decoding.seven_segment import SegmentMap, SevenSegmentDecoder
from niuchacz.domain.models import FrameEvent


def raw(lit_channels):
    """Kanały 1..7, które świecą -> bajt surowy (aktywne stanem niskim)."""
    b = 0xFF
    for ch in lit_channels:
        b &= ~(1 << (ch - 1))
    return b & 0xFF


class CardOrderTest(unittest.TestCase):
    def test_de24_measurement(self):
        # pomiar 18.10.2026: DIG1..DIG4 -> świecące kanały
        frame = FrameEvent(digits_raw=(raw({2, 3, 6, 7}), raw({1, 2, 4, 5, 7}),
                                       raw({1, 4, 5, 6, 7}), raw({2, 3, 4, 5, 7})), ts_ms=0)
        smap = SegmentMap(active_low=True)
        prof = CardProfile(digits=4, display_order=(3, 2, 1, 0), code_digits=(2, 3))
        asm = CodeAssembler(SevenSegmentDecoder(smap), prof, clock=lambda: 0.0)
        ch = asm.feed(frame)
        self.assertEqual(ch.display, "DE24")
        self.assertEqual(ch.code.value, "24")

    def test_mock_roundtrip_with_reversed_order(self):
        from tests.fake_esp32 import MockTransport
        smap = SegmentMap(active_low=True)
        prof = CardProfile(digits=4, display_order=(3, 2, 1, 0), code_digits=(2, 3))
        m = MockTransport(segment_map=smap, profile=prof)
        fr = m._frame("C1")
        asm = CodeAssembler(SevenSegmentDecoder(smap), prof, clock=lambda: 0.0)
        ch = asm.feed(FrameEvent(digits_raw=tuple(fr["d"]), ts_ms=0))
        self.assertEqual(ch.code.value, "C1")
        self.assertEqual(ch.display, "--C1")


if __name__ == "__main__":
    unittest.main()
