"""Pełna ścieżka bez GUI: udawane ESP32 (tests/fake_esp32.py) -> wątek czytający -> kontroler -> szyna zdarzeń."""
import tempfile
import time
import unittest
from pathlib import Path

from niuchacz.app import event_bus as ev
from niuchacz.app.config import ConfigStore
from niuchacz.app.controller import AppController
from niuchacz.decoding.code_assembler import CardProfile
from niuchacz.decoding.seven_segment import SegmentMap
from niuchacz.domain.enums import ConnectionState, TransportKind
from niuchacz.knowledge.diagnosis_service import DiagnosisService
from niuchacz.knowledge.repository import CodeRepository
from tests.fake_esp32 import MockTransport

ROOT = Path(__file__).resolve().parents[1]


def make(scenario, tmp, smap=None):
    smap = smap or SegmentMap(channel_to_segment=["b", "a", "c", "d", "e", "f", "g", "dp"], active_low=True)
    repo = CodeRepository()
    repo.import_directory(ROOT / "data" / "post_codes")
    bus = ev.EventBus()
    config = ConfigStore(Path(tmp))
    config.save_settings({**config.load_settings(), "hang_seconds": 1.0, "mock_scenario": scenario})

    def factory(kind, settings, segment_map, digits, profile=None):
        return MockTransport(segment_map=segment_map, scenario=scenario, digits=digits, speed=8.0, loop=False,
                             profile=profile)

    ctrl = AppController(bus, config, DiagnosisService(repo), factory, smap, CardProfile())
    seen = {"codes": [], "hang": [], "conn": [], "diag": [], "sessions": 0}
    bus.subscribe(ev.CODE, lambda c: seen["codes"].append(str(c.code)))
    bus.subscribe(ev.HANG, lambda h: seen["hang"].append(str(h.code)))
    bus.subscribe(ev.CONNECTION, lambda p: seen["conn"].append(p[0]))
    bus.subscribe(ev.DIAGNOSIS, lambda p: seen["diag"].append(p[1]))
    bus.subscribe(ev.SESSION, lambda s: seen.__setitem__("sessions", seen["sessions"] + 1))
    return ctrl, seen


def run_for(ctrl, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ctrl.pump()
        time.sleep(0.02)


class EndToEndTest(unittest.TestCase):
    def test_normal_boot(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctrl, seen = make("normal", tmp)
            ctrl.connect(TransportKind.TCP)
            run_for(ctrl, 1.6)
            ctrl.disconnect()
            self.assertIn(ConnectionState.CONNECTED, seen["conn"])
            self.assertEqual(seen["codes"][:3], ["CF", "C0", "C1"])
            self.assertEqual(seen["codes"][-1], "FF")
            self.assertEqual(seen["sessions"], 1)
            self.assertEqual(ctrl.recorder.current.codes, seen["codes"])

    def test_no_ram_hangs_on_c1(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctrl, seen = make("no_ram", tmp)
            ctrl.connect(TransportKind.TCP)
            run_for(ctrl, 1.8)
            ctrl.disconnect()
            self.assertEqual(seen["codes"], ["CF", "C0", "C1"])
            self.assertEqual(seen["hang"], ["C1"])
            self.assertEqual(ctrl.recorder.current.hung_on, "C1")
            self.assertIn("RAM", seen["diag"][-1])

    def test_golden_comparison_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctrl, seen = make("normal", tmp)
            ctrl.connect(TransportKind.TCP)
            run_for(ctrl, 1.6)
            ctrl.disconnect()
            gpath = Path(tmp) / "wzorzec.json"
            ctrl.save_golden(gpath, board="Test-P55")

            ctrl2, _ = make("no_ram", tmp)
            msgs = []
            ctrl2.bus.subscribe(ev.GOLDEN, msgs.append)
            ctrl2.load_golden(gpath)
            ctrl2.connect(TransportKind.TCP)
            run_for(ctrl2, 1.8)
            ctrl2.disconnect()
            self.assertTrue(any("zatrzymał się po 3" in m and "C3" in m for m in msgs), msgs)

            report = Path(tmp) / "raport.txt"
            ctrl2.export_report(report)
            text = report.read_text(encoding="utf-8-sig")
            self.assertIn("POSTÓJ na kodzie C1", text)
            self.assertIn("PORÓWNANIE ZE WZORCEM", text)


class ReportTest(unittest.TestCase):
    def test_session_end_opens_report_with_full_text(self):
        from niuchacz.session.report import WIDTH, ReportMeta, default_filename
        with tempfile.TemporaryDirectory() as tmp:
            ctrl, _ = make("no_ram", tmp)
            ended = []
            ctrl.bus.subscribe(ev.SESSION_END, ended.append)
            ctrl.connect(TransportKind.TCP)
            run_for(ctrl, 1.8)
            ctrl.disconnect()
            self.assertEqual(len(ended), 1)
            session = ended[0]
            self.assertIn("POSTÓJ na kodzie C1", session.result)

            meta = ReportMeta(repair_no="2026/014", board="ASUS P/I-P55T2P4", owner="pudełko 3",
                              technician="Rafał", notes="Płyta bez RAM, do sprawdzenia sloty SIMM. " * 3)
            text = ctrl.report_text(session, meta)
            for needle in ("2026/014", "ASUS P/I-P55T2P4", "pudełko 3", "Rafał", "Award",
                           "PRZEBIEG POST (3 kodów)", "Wykrywanie i określanie rozmiaru pamięci RAM",
                           "DIAGNOZA OSTATNIEGO KODU", "Prawdopodobna usterka", "sloty SIMM"):
                self.assertIn(needle, text)
            self.assertTrue(all(len(line) <= WIDTH for line in text.splitlines()), "linia za długa do druku")

            path = Path(tmp) / default_filename(session, meta)
            ctrl.save_report(path, text)
            self.assertTrue(path.name.startswith("NIUCHACZ_2026_014_ASUS_P_I-P55T2P4_"))
            self.assertEqual(path.read_bytes()[:3], b"\xef\xbb\xbf")   # BOM dla Notatnika
            self.assertIn("C1", path.read_text(encoding="utf-8-sig"))

    def test_manual_finish_and_reset_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctrl, _ = make("normal", tmp)
            ended = []
            ctrl.bus.subscribe(ev.SESSION_END, ended.append)
            ctrl.finish_session_now()             # pusta sesja – nic się nie dzieje
            self.assertEqual(ended, [])
            ctrl.connect(TransportKind.TCP)
            run_for(ctrl, 0.5)
            ctrl.finish_session_now()
            ctrl.disconnect()
            self.assertEqual(len(ended), 1)
            self.assertIn("Zakończona ręcznie", ended[0].result)
            ctrl.finish_session_now()             # ponownie: to samo okno, bez nowej sesji
            self.assertIs(ended[-1], ended[0])


if __name__ == "__main__":
    unittest.main()
