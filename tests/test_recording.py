"""Nagrywanie REC: starty, pętla restartów, koniec przebiegu, zapis TXT + CSV."""
import tempfile
import unittest
from pathlib import Path

from niuchacz.app import event_bus as ev
from niuchacz.app.config import ConfigStore
from niuchacz.app.controller import AppController
from niuchacz.decoding.code_assembler import CardProfile, CodeAssembler
from niuchacz.decoding.seven_segment import SegmentMap, SevenSegmentDecoder
from niuchacz.domain.models import CodeEvent, SessionStart
from niuchacz.i18n import set_language
from niuchacz.knowledge.diagnosis_service import DiagnosisService
from niuchacz.knowledge.repository import CodeRepository
from niuchacz.session import recording as rec_mod

ROOT = Path(__file__).resolve().parents[1]


class RecordingTest(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.tmp = tempfile.TemporaryDirectory()
        repo = CodeRepository()
        repo.import_directory(ROOT / "data" / "post_codes")
        self.bus = ev.EventBus()
        config = ConfigStore(Path(self.tmp.name))
        config.save_settings({**config.load_settings(), "bios_vendor": "ami"})
        self.c = AppController(self.bus, config, DiagnosisService(repo), None, SegmentMap(), CardProfile())
        self.now = [0.0]
        self.c.assembler = CodeAssembler(SevenSegmentDecoder(SegmentMap()), CardProfile(), clock=lambda: self.now[0])
        self.c.reports_dir = Path(self.tmp.name) / "reports"
        self.rec_events = []
        self.reports = []
        self.bus.subscribe(ev.REC, self.rec_events.append)
        self.bus.subscribe(ev.SESSION_END, self.reports.append)
        self.ts = 0
        self.sid = 0

    def tearDown(self):
        self.tmp.cleanup()

    def reset(self):
        self.sid += 1
        self.c.handle(SessionStart(self.sid, self.ts))

    def codes(self, *values):
        for v in values:
            self.ts += 10
            self.now[0] += 0.01
            self.c.handle(CodeEvent(int(v, 16), self.ts))
        self.c.pump()

    def wait(self, seconds):
        self.now[0] += seconds
        self.c.pump()

    def test_nothing_recorded_without_rec(self):
        self.reset(); self.codes("D0", "D4", "2A", "00"); self.wait(5)
        self.assertEqual(rec_mod.IDLE, self.c.rec.state)
        self.assertFalse(self.c.reports_dir.exists())

    def test_double_boot_is_one_recording(self):
        self.c.arm_recording()
        self.assertEqual(rec_mod.ARMED, self.c.rec.state)
        self.reset(); self.codes("D0", "D4", "D5", "19")
        self.reset(); self.codes("D0", "D4", "2A", "B0", "2C", "31", "37", "38", "75", "78", "00")
        self.wait(1)
        self.assertEqual(rec_mod.RECORDING, self.c.rec.state)       # 1 s ciszy to jeszcze nie koniec
        self.wait(3)
        rec = self.c.rec.last
        self.assertEqual(rec_mod.DONE, self.c.rec.state)
        self.assertEqual("rec.end_done", rec.end_key)
        self.assertEqual(2, len(rec.starts))
        self.assertEqual(15, rec.code_count)
        txt, csv = rec.saved
        self.assertTrue(txt.name.startswith("NIUCHACZ_REC_"))
        report = txt.read_text(encoding="utf-8")
        self.assertIn("START 1 (4 codes) – reset after code 19", report)
        self.assertIn("START 2 (11 codes)", report)
        self.assertEqual(16, len(csv.read_text(encoding="utf-8-sig").splitlines()))

    def test_restart_loop_stops_after_max_starts(self):
        self.c.arm_recording()
        for last in ("19", "2A", "19", "2B"):
            self.reset(); self.codes("D0", "D4", last)
        self.assertEqual(rec_mod.RECORDING, self.c.rec.state)
        self.reset()
        rec = self.c.rec.last
        self.assertEqual("rec.end_loop", rec.end_key)
        self.assertEqual(4, len(rec.starts))
        self.assertIn("19, 2A, 19, 2B", rec.result)

    def test_bios_waiting_ends_after_wait_seconds(self):
        self.c.arm_recording()
        self.reset(); self.codes("D0", "D4", "2A", "85")
        self.wait(3)
        self.assertEqual(rec_mod.RECORDING, self.c.rec.state)
        self.wait(3)
        self.assertEqual("rec.end_wait", self.c.rec.last.end_key)
        self.assertIn("code 85", self.c.rec.last.result)

    def test_stall_ends_recording(self):
        self.c.arm_recording()
        self.reset(); self.codes("D0", "D4", "2A")
        self.wait(16)
        self.assertEqual("rec.end_stop", self.c.rec.last.end_key)

    def test_manual_stop_and_cancel(self):
        self.c.arm_recording()
        self.c.stop_recording()
        self.assertEqual(rec_mod.IDLE, self.c.rec.state)
        self.c.arm_recording()
        self.reset(); self.codes("D0", "D4")
        self.c.stop_recording()
        self.assertEqual("rec.end_manual", self.c.rec.last.end_key)
        self.assertEqual(rec_mod.DONE, self.rec_events[-1][0])

    def test_armed_before_power_on_without_reset_line(self):
        self.c.arm_recording()
        self.codes("D0", "D4", "2A", "2C", "31", "37", "38", "75", "78", "B1", "00"); self.wait(4)
        self.assertEqual("rec.end_done", self.c.rec.last.end_key)

    def test_power_on_garbage_is_not_end_of_post(self):
        """26.10.2026, włączenie zasilania: 04 00 10 12 1A, po 0,9 s 00 – to nie koniec POST."""
        self.c.arm_recording()
        self.reset(); self.codes("04", "00", "10", "12", "1A", "00")
        self.wait(4)
        self.assertEqual(rec_mod.RECORDING, self.c.rec.state)
        self.codes("CD"); self.reset()
        self.codes("D0", "D1", "D3", "DE", "D4", "D5", "DA", "03", "2A", "78", "B1", "00"); self.wait(4)
        self.assertEqual("rec.end_done", self.c.rec.last.end_key)
        self.assertEqual(2, len(self.c.rec.last.starts))

    def test_asrock_775v88_boot_is_two_starts(self):
        """Prawdziwy przebieg (26.10.2026): jeden zaplanowany reset po CD; DE po 90 to NIE reset."""
        self.c.arm_recording()
        self.codes("D0", "D1", "CD")
        self.codes("D0", "D1", "D3", "10", "20", "21", "22", "23", "24", "30", "40", "41", "50", "90",
                   "DE", "D4", "D5", "D7", "D8", "D9", "DA", "03", "04", "2A", "85", "87", "B1", "00")
        self.wait(4)
        rec = self.c.rec.last
        self.assertEqual("rec.end_done", rec.end_key)
        self.assertEqual(["CD", "00"], [s.last_code for s in rec.starts])

    def test_save_last_run(self):
        self.reset(); self.codes("D0", "D4", "2A")
        rec = self.c.save_last_run()
        self.assertEqual("rec.end_snapshot", rec.end_key)
        self.assertTrue(all(p.exists() for p in rec.saved))
        self.assertEqual(("saved", rec), self.rec_events[-1])

    def test_report_in_polish(self):
        self.c.arm_recording()
        self.reset(); self.codes("D0", "19")
        self.reset(); self.codes("D0", "2A", "2C", "31", "37", "38", "75", "78", "B1", "00"); self.wait(4)
        rec = self.c.rec.last
        pl = self.c.report_text(rec, self.c.default_report_meta(), lang="pl")
        en = self.c.report_text(rec, self.c.default_report_meta(), lang="en")
        self.assertIn("reset po kodzie 19", pl)
        self.assertIn("OSTATNI KOD KAŻDEGO STARTU", pl)
        self.assertIn("reset after code 19", en)

if __name__ == "__main__":
    unittest.main()
