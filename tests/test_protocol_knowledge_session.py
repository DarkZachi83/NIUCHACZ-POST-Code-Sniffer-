import tempfile
import unittest
from pathlib import Path

from niuchacz.domain.models import CodeChange, FrameEvent, LedState, PostCode, ReplayEvent, SessionStart
from niuchacz.knowledge.diagnosis_service import DiagnosisService
from niuchacz.knowledge.repository import CodeRepository
from niuchacz.protocol.parser import ProtocolError, parse_line
from niuchacz.session import golden
from niuchacz.session.recorder import SessionRecorder
from niuchacz.i18n import set_language


def setUpModule():
    set_language("pl")      # te testy sprawdzają polskie teksty raportu


def tearDownModule():
    set_language("en")

ROOT = Path(__file__).resolve().parents[1]


class ParserTest(unittest.TestCase):
    def test_frame(self):
        e = parse_line('{"t":"frame","d":[124,119,0,0],"ts":5}')
        self.assertEqual(e, FrameEvent(digits_raw=(124, 119, 0, 0), ts_ms=5))

    def test_led_and_session(self):
        self.assertIsInstance(parse_line('{"t":"led","clk":1,"irdy":0,"frame":1,"rst":0,"ts":1}'), LedState)
        self.assertEqual(parse_line('{"t":"session","id":7,"ts":9}'), SessionStart(7, 9))

    def test_replay(self):
        e = parse_line('{"t":"replay","id":3,"ev":{"t":"frame","d":[1,2,3,4],"ts":1}}')
        self.assertIsInstance(e, ReplayEvent)
        self.assertIsInstance(e.event, FrameEvent)

    def test_garbage(self):
        self.assertIsNone(parse_line("MicroPython v1.24 on ESP32"))
        with self.assertRaises(ProtocolError):
            parse_line('{"t":"frame"')
        with self.assertRaises(ProtocolError):
            parse_line('{"t":"cos"}')


class KnowledgeTest(unittest.TestCase):
    def test_award_seed_loads(self):
        repo = CodeRepository()
        n = repo.import_directory(ROOT / "data" / "post_codes")
        self.assertGreaterEqual(n, 5)
        diag = DiagnosisService(repo).diagnose(PostCode("C1"), "award")
        self.assertTrue(diag.known)
        self.assertIn("RAM", DiagnosisService.format(diag))

    def test_unknown_code(self):
        repo = CodeRepository()
        diag = DiagnosisService(repo).diagnose(PostCode("AB"), "ami")
        self.assertFalse(diag.known)
        self.assertIn("brak w bazie", DiagnosisService.format(diag))

    def test_reimport_does_not_duplicate(self):
        repo = CodeRepository()
        repo.import_directory(ROOT / "data" / "post_codes")
        first = repo.count()
        repo.import_directory(ROOT / "data" / "post_codes")
        self.assertEqual(repo.count(), first)

    def test_export_roundtrip(self):
        repo = CodeRepository()
        repo.import_directory(ROOT / "data" / "post_codes")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "award.json"
            repo.export_vendor("award", out)
            repo2 = CodeRepository()
            repo2.import_file(out)
            self.assertEqual(len(repo2.all_for_vendor("award")), len(repo.all_for_vendor("award")))


class GoldenTest(unittest.TestCase):
    def test_compare(self):
        g = ["CF", "C0", "C1", "C3", "FF"]
        self.assertTrue(golden.compare(g, g).identical)
        stop = golden.compare(["CF", "C0", "C1"], g)
        self.assertEqual((stop.actual, stop.expected, stop.matched), (None, "C3", 3))
        diff = golden.compare(["CF", "C0", "C5"], g)
        self.assertEqual((diff.expected, diff.actual), ("C1", "C5"))
        self.assertTrue(golden.compare(["CF", "CF", "C0", "C1", "C3", "FF"], g).identical)

    def test_short_code_missing_is_not_a_divergence(self):
        """26.10.2026, ASRock 775V88: wzorzec ma C1~, kolejny przebieg C1 nie złapał."""
        g = ["08", "C0", "C1", "C2", "C3", "C4", "C5", "C6"]
        a = ["08", "C0", "C2", "C3", "C5", "C6"]
        d = golden.compare(a, g, golden_optional=[2, 5])
        self.assertTrue(d.identical)
        self.assertEqual(("C1", "C4"), d.skipped)
        self.assertTrue(d.only_uncertain)
        self.assertEqual("golden.identical_uncertain", golden.describe(d, golden.GoldenRun("B", "ami", g))[0])
        # stary wzorzec bez oznaczeń: też zgodny, ale z listą braków
        d = golden.compare(a, g)
        self.assertTrue(d.identical)
        self.assertFalse(d.only_uncertain)
        # nadmiarowy kod w przebiegu (np. 0E złapany pierwszy raz)
        d = golden.compare(["0C", "0E", "13", "20"], ["0C", "13", "20"])
        self.assertTrue(d.identical)
        self.assertEqual(("0E",), d.extra)

    def test_real_divergence_still_detected(self):
        g = ["D3", "DE", "D4", "D5", "D7", "D8"]
        d = golden.compare(["D3", "DE", "D4", "88", "89", "8A", "8B", "8C"], g)
        self.assertFalse(d.identical)
        self.assertEqual(("D5", "88"), (d.expected, d.actual))
        d = golden.compare(["D3", "DE"], g)     # płyta stanęła na DE (np. brak RAM)
        self.assertEqual((None, "D4", 2), (d.actual, d.expected, d.matched))

    def test_save_load(self):
        rec = SessionRecorder()
        for i, c in enumerate(["CF", "C0", "C1"]):
            rec.record(CodeChange(PostCode(c), c + "--", i * 100))
        run = golden.GoldenRun.from_session(rec.current, board="ASUS P/I-P55T2P4", bios_vendor="award")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "w.json"
            run.save(p)
            back = golden.GoldenRun.load(p)
        self.assertEqual(back.codes, ["CF", "C0", "C1"])
        self.assertEqual(back.timings_ms, [0, 100, 200])


if __name__ == "__main__":
    unittest.main()
