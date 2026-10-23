import unittest

from niuchacz.decoding.code_assembler import CardProfile, CodeAssembler
from niuchacz.decoding.seven_segment import SegmentMap, SevenSegmentDecoder
from niuchacz.domain.models import FrameEvent


def frame(decoder_map, text, ts=0):
    raw = tuple(decoder_map.canonical_to_raw(SevenSegmentDecoder.encode_char(c)) for c in text)
    return FrameEvent(digits_raw=raw, ts_ms=ts)


class SevenSegmentTest(unittest.TestCase):
    def test_all_hex_digits_roundtrip(self):
        dec = SevenSegmentDecoder(SegmentMap())
        for ch in "0123456789ABCDEF":
            self.assertEqual(dec.decode_digit(SevenSegmentDecoder.encode_char(ch)), ch)

    def test_protocol_example_ba(self):
        # przykład ze specyfikacji: {"d":[124,119,...]} -> "BA"
        dec = SevenSegmentDecoder(SegmentMap())
        self.assertEqual(dec.decode((124, 119)), "BA")

    def test_active_low_and_shuffled_channels(self):
        smap = SegmentMap(channel_to_segment=["g", "f", "e", "d", "c", "b", "a", "dp"], active_low=True)
        dec = SevenSegmentDecoder(smap)
        for ch in "C1F0":
            raw = smap.canonical_to_raw(SevenSegmentDecoder.encode_char(ch))
            self.assertEqual(dec.decode_digit(raw), ch)

    def test_decimal_point_ignored(self):
        dec = SevenSegmentDecoder(SegmentMap())
        self.assertEqual(dec.decode_digit(0x06 | 0x80), "1")

    def test_invalid_map_rejected(self):
        with self.assertRaises(ValueError):
            SegmentMap(channel_to_segment=["a"] * 8)


class AssemblerTest(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.smap = SegmentMap()
        self.asm = CodeAssembler(SevenSegmentDecoder(self.smap), CardProfile(code_digits=(0, 1)),
                                 clock=lambda: self.now)

    def test_change_reported_once(self):
        c = self.asm.feed(frame(self.smap, "C1--"))
        self.assertEqual(str(c.code), "C1")
        self.assertIsNone(self.asm.feed(frame(self.smap, "C1--")))

    def test_hang_detected_once(self):
        self.asm.feed(frame(self.smap, "C1--"))
        self.now = 4.0
        self.assertIsNone(self.asm.check_hang(5))
        self.now = 6.0
        hang = self.asm.check_hang(5)
        self.assertEqual(str(hang.code), "C1")
        self.assertIsNone(self.asm.check_hang(5))

    def test_non_hex_display(self):
        c = self.asm.feed(frame(self.smap, "----"))
        self.assertIsNone(c.code)
        self.assertEqual(c.display, "----")


if __name__ == "__main__":
    unittest.main()
