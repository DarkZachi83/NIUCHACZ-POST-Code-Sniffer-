"""Nowa sesja przy ponownym starcie płyty – bez linii RESET (raporty 19.10.2026)."""
import tempfile
import unittest
from pathlib import Path

from niuchacz.app import event_bus as ev
from niuchacz.app.config import ConfigStore
from niuchacz.app.controller import AppController
from niuchacz.decoding.code_assembler import CardProfile
from niuchacz.decoding.seven_segment import SegmentMap, SevenSegmentDecoder
from niuchacz.domain.models import FrameEvent
from niuchacz.knowledge.diagnosis_service import DiagnosisService
from niuchacz.knowledge.repository import CodeRepository

ROOT = Path(__file__).resolve().parents[1]
PROF = CardProfile(digits=4, display_order=(3, 2, 1, 0), code_digits=(0, 1), prev_code_digits=(2, 3))
SMAP = SegmentMap(active_low=True)


def frame(visual, ts):
    by_line = PROF.to_lines(list(visual))
    return FrameEvent(digits_raw=tuple(SMAP.canonical_to_raw(SevenSegmentDecoder.encode_char(c))
                                       for c in by_line), ts_ms=ts)


class AutoSessionTest(unittest.TestCase):
    def test_ami_restart_starts_new_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = CodeRepository()
            repo.import_directory(ROOT / "data" / "post_codes")
            cfg = ConfigStore(Path(tmp))
            cfg.save_settings({**cfg.load_settings(), "bios_vendor": "ami"})
            ctrl = AppController(ev.EventBus(), cfg, DiagnosisService(repo), None, SMAP, PROF)
            first = ["D8  ", "D4D8", "8BD4", "248B", "3824", "8438", "8584"]
            second = ["D885", "D4D8", "24D4"]
            for i, vis in enumerate(first + second):
                ctrl.handle(frame(vis, i * 100))
            sessions = ctrl.recorder.sessions
            self.assertEqual(len(sessions), 2)
            self.assertEqual(sessions[0].codes, ["D8", "D4", "8B", "24", "38", "84", "85"])
            self.assertEqual(sessions[1].codes, ["D8", "D4", "24"])


if __name__ == "__main__":
    unittest.main()
