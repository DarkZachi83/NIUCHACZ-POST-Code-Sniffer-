"""Sesja nie może mieszać dwóch zegarów (np. symulator -> ESP32 albo restart ESP32)."""
import unittest

from niuchacz.domain.models import CodeChange, PostCode


class FakeBus:
    def __init__(self):
        self.events = []

    def publish(self, topic, payload=None):
        self.events.append((topic, payload))


class ClockTest(unittest.TestCase):
    def test_clock_going_back_starts_new_session(self):
        from niuchacz.session.recorder import SessionRecorder
        from niuchacz.app import controller as ctl

        c = ctl.AppController.__new__(ctl.AppController)
        c.recorder = SessionRecorder()
        c.bus = FakeBus()
        from niuchacz.session.recording import RecordingManager
        c.rec = RecordingManager()
        finished = []
        c._finish_session = lambda: finished.append(c.recorder.current.session_id)
        c.assembler = type("A", (), {"reset": lambda self: None})()
        c._publish_diagnosis = lambda code: None
        first = c.recorder.current
        c._on_code(CodeChange(code=PostCode("C0"), display="", ts_ms=500000))
        c._on_code(CodeChange(code=PostCode("C1"), display="", ts_ms=500400))
        c._on_code(CodeChange(code=PostCode("F8"), display="", ts_ms=2000))
        self.assertEqual(first.codes, ["C0", "C1"])
        self.assertEqual(c.recorder.current.codes, ["F8"])
        self.assertEqual(c.recorder.relative_ms(c.recorder.current.items[0]), 0)


if __name__ == "__main__":
    unittest.main()
