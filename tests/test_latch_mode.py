"""Tryb zatrzasku 74LCX374: kod przychodzi jako bajt ("t":"code")."""
import unittest

from niuchacz.decoding.code_assembler import CardProfile, CodeAssembler
from niuchacz.decoding.seven_segment import SegmentMap, SevenSegmentDecoder
from niuchacz.domain.models import CodeEvent
from niuchacz.protocol.parser import parse_line


class LatchModeTest(unittest.TestCase):
    def setUp(self):
        self.t = [0.0]
        self.asm = CodeAssembler(SevenSegmentDecoder(SegmentMap()), CardProfile(), clock=lambda: self.t[0])

    def test_parser_code(self):
        self.assertEqual(parse_line('{"t":"code","c":135,"ts":42}'), CodeEvent(code=0x87, ts_ms=42))

    def test_sequence(self):
        out = [c for v in (0x19, 0x2A, 0x87) for c in self.asm.feed_code(v, 0)]
        self.assertEqual([c.code.value for c in out], ["19", "2A", "87"])
        self.assertTrue(all(c.is_new for c in out))
        self.assertEqual(self.asm.feed_code(0x87, 1), [])
        self.assertEqual(out[-1].display, "872A")

    def test_flap_suppressed(self):
        news = [c.is_new for v in (0x85, 0x86, 0x85, 0x86, 0x85) for c in self.asm.feed_code(v, 0)]
        self.assertEqual(news, [True, True, True, False, False])

    def test_hang(self):
        self.asm.feed_code(0x2A, 0)
        self.t[0] = 20.0
        hang = self.asm.check_hang(15)
        self.assertEqual(hang.code.value, "2A")


if __name__ == "__main__":
    unittest.main()
