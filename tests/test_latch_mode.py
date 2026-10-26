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

    def test_parser_gap_and_heartbeat(self):
        from niuchacz.domain.models import Heartbeat
        self.assertEqual(parse_line('{"t":"code","c":177,"ts":42,"g":12000}'), CodeEvent(0xB1, 42, 12000))
        self.assertEqual(parse_line('{"t":"hb","ts":5,"gm":3100,"bl":40}'), Heartbeat(5, 3100, 40))
        self.assertEqual(parse_line('{"t":"hb","ts":5}'), Heartbeat(5))      # stary firmware

    def test_gap_marked_in_report(self):
        from datetime import datetime
        from niuchacz.domain.models import SequenceItem
        from niuchacz.session.recorder import Session
        from niuchacz.session.report import ReportMeta, build_report
        s = Session(session_id=1)
        s.items = [SequenceItem("78", 0), SequenceItem("B1", 3900, gap_us=12000)]
        s.gap_max_us = 12000
        text = build_report(s, "AMI", ReportMeta(), lambda c: "", "", datetime(2026, 1, 1), lang="en")
        self.assertIn("B1!", text)
        self.assertIn("longest gap 12.0 ms, codes caught after a gap: 1", text)
        old = Session(session_id=2)
        old.items = [SequenceItem("78", 0)]
        self.assertNotIn("ESP32 reading", build_report(old, "AMI", ReportMeta(), lambda c: "", "", lang="en"))

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
