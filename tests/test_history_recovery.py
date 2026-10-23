"""Odtwarzanie kodów, które mignęły za szybko – z lewej pary cyfr karty (historia).

Dane z prawdziwego przebiegu 18.10.2026: aplikacja złapała 52, 75, 84, a karta
pokazała 7875 i 8584 – czyli 78 i 85 mignęły między odczytami.
"""
import unittest

from niuchacz.decoding.code_assembler import CardProfile, CodeAssembler
from niuchacz.decoding.seven_segment import SegmentMap, SevenSegmentDecoder
from niuchacz.domain.models import FrameEvent
from niuchacz.session.recorder import SessionRecorder

PROF = CardProfile(digits=4, display_order=(3, 2, 1, 0), code_digits=(2, 3), prev_code_digits=(0, 1))
SMAP = SegmentMap(active_low=True)


def frame(visual, ts):
    by_line = PROF.to_lines(list(visual))
    raw = tuple(SMAP.canonical_to_raw(SevenSegmentDecoder.encode_char(c)) for c in by_line)
    return FrameEvent(digits_raw=raw, ts_ms=ts)


class HistoryRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.asm = CodeAssembler(SevenSegmentDecoder(SMAP), PROF, clock=lambda: 0.0)
        self.rec = SessionRecorder()

    def run_frames(self, frames):
        for i, vis in enumerate(frames):
            for ch in self.asm.feed_all(frame(vis, i * 10)):
                self.rec.record(ch)
        return [(it.code, it.recovered) for it in self.rec.current.items]

    def test_real_run(self):
        got = self.run_frames(["3752", "7875", "8584", "848C"])
        self.assertEqual(got, [("52", False), ("78", True), ("75", False),
                               ("85", True), ("84", False), ("8C", False)])

    def test_no_recovery_when_nothing_missed(self):
        got = self.run_frames(["C0C1", "C1C3", "C3C5"])
        self.assertEqual(got, [("C1", False), ("C3", False), ("C5", False)])

    def test_first_frame_does_not_invent_previous(self):
        # pierwszy odczyt sesji: lewa para to resztka poprzedniego startu – pomijamy
        got = self.run_frames(["0061"])
        self.assertEqual(got, [("61", False)])

    def test_glitch_does_not_duplicate(self):
        # zakłócenie (nie-kod) między dwoma identycznymi stanami nie tworzy drugiego wpisu
        got = self.run_frames(["3752", "37 2", "3752", "5275"])
        self.assertEqual(got, [("52", False), ("75", False)])

    def test_left_pair_flicker_is_not_a_new_code(self):
        # pomiar 18.10.2026: przy stałym kodzie 84 lewa para miga 85/86 co ok. 0,5 s
        prof = CardProfile(digits=4, display_order=(3, 2, 1, 0), code_digits=(2, 3))
        asm = CodeAssembler(SevenSegmentDecoder(SMAP), prof, clock=lambda: 0.0)
        rec = SessionRecorder()
        changes = []
        for i, vis in enumerate(["7584", "8584", "8684", "8584", "8684", "848C"]):
            for ch in asm.feed_all(frame(vis, i * 500)):
                changes.append(ch)
                rec.record(ch)
        self.assertEqual([it.code for it in rec.current.items], ["84", "8C"])
        self.assertEqual([c.display for c in changes if not c.is_new], ["8584", "8684", "8584", "8684"])

    def test_flapping_pair_recorded_once(self):
        # BIOS czeka w pętli i miga 85/86 – zapis: 84, 85, 86, 85, potem cisza; nowy kod przerywa
        prof = CardProfile(digits=4, display_order=(3, 2, 1, 0), code_digits=(0, 1))
        clock = [0.0]
        asm = CodeAssembler(SevenSegmentDecoder(SMAP), prof, clock=lambda: clock[0])
        rec = SessionRecorder()
        seq = ["8478", "8584", "8684", "8584", "8684", "8584", "8684"]
        for i, vis in enumerate(seq):
            clock[0] = i * 0.5
            for ch in asm.feed_all(frame(vis, i * 500)):
                rec.record(ch)
        self.assertEqual([it.code for it in rec.current.items], ["84", "85", "86", "85"])
        clock[0] = 9.0
        self.assertIsNotNone(asm.check_hang(5))   # miganie nie blokuje wykrycia postoju
        for ch in asm.feed_all(frame("0086", 9000)):
            rec.record(ch)
        self.assertEqual(rec.current.items[-1].code, "00")

    def test_left_current_right_previous(self):
        # karta: lewa para = bieżący, prawa = poprzedni (AMI: ekran 0085 przy 8584)
        prof = CardProfile(digits=4, display_order=(3, 2, 1, 0), code_digits=(0, 1), prev_code_digits=(2, 3))
        asm = CodeAssembler(SevenSegmentDecoder(SMAP), prof, clock=lambda: 0.0)
        rec = SessionRecorder()
        # 75 mignął (nie złapany na lewej), widać go potem po prawej: 7875
        for i, vis in enumerate(["5237", "7875", "8478", "8584", "8684", "8584", "8684"]):
            for ch in asm.feed_all(frame(vis, i * 100)):
                rec.record(ch)
        self.assertEqual([(it.code, it.recovered) for it in rec.current.items],
                         [("52", False), ("75", True), ("78", False), ("84", False), ("85", False),
                          ("86", False), ("85", False)])

    def test_profile_without_history(self):
        prof = CardProfile(digits=4, display_order=(3, 2, 1, 0), code_digits=(2, 3))
        asm = CodeAssembler(SevenSegmentDecoder(SMAP), prof, clock=lambda: 0.0)
        asm.feed_all(frame("3752", 0))
        self.assertEqual([c.code.value for c in asm.feed_all(frame("7875", 10))], ["75"])


if __name__ == "__main__":
    unittest.main()
