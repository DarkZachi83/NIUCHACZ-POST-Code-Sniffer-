"""Kontroler aplikacji: spina transport, dekodowanie, bazę i sesje.

Nie zna żadnego widżetu – komunikuje się z GUI wyłącznie przez EventBus.
Metoda `handle()` jest wołana w wątku GUI (przez GuiAdapter), więc stan
kontrolera nie wymaga blokad.
"""
from __future__ import annotations

import logging
from collections import deque
import time
from dataclasses import replace
import queue
from pathlib import Path
from typing import Optional

from niuchacz.app import event_bus as ev
from niuchacz.app.config import ConfigStore
from niuchacz.app.reader_thread import ReaderThread, TransportClosed
from niuchacz.decoding.code_assembler import CardProfile, CodeAssembler
from niuchacz.decoding.seven_segment import SegmentMap, SevenSegmentDecoder
from niuchacz.app import printing
from niuchacz.domain.enums import BiosVendor, ConnectionState, TransportKind
from niuchacz.domain.models import (
    CodeChange, CodeEvent, CommandReply, DeviceError, DeviceHello, FrameEvent, Heartbeat,
    LedState, PostCode, ReplayEvent, SessionStart,
)
from niuchacz.i18n import t
from niuchacz.knowledge.diagnosis_service import DiagnosisService
from niuchacz.protocol import commands
from niuchacz.session import exporter, golden
from niuchacz.session import recording as rec_mod
from niuchacz.session.recording import Recording, RecordingManager
from niuchacz.session.recorder import LIVE, Session, SessionRecorder
from niuchacz.session.report import ReportMeta, build_recording_report, build_report
from niuchacz.transport.base import Transport, TransportError

log = logging.getLogger(__name__)


MIN_DONE_CODES = 10    # tyle kodów musi mieć start, żeby 00/FF uznać za koniec POST


class AppController:
    def __init__(self, bus: ev.EventBus, config: ConfigStore, diagnosis: DiagnosisService,
                 transport_factory, segment_map: SegmentMap, profile: CardProfile):
        self.bus = bus
        self.config = config
        self.settings = config.load_settings()
        self.diagnosis = diagnosis
        self.transport_factory = transport_factory
        self.segment_map = segment_map
        self.profile = profile
        self.assembler = CodeAssembler(SevenSegmentDecoder(segment_map), profile)
        self.recorder = SessionRecorder()
        self.events: "queue.Queue[object]" = queue.Queue()
        self._transport: Optional[Transport] = None
        self._reader: Optional[ReaderThread] = None
        self.golden_run: Optional[golden.GoldenRun] = None
        self._last_rx = 0.0          # kiedy ostatnio przyszło cokolwiek z urządzenia
        self._silence_warned = False
        self.last_raw: Optional[tuple] = None   # ostatni surowy stan linii (do kalibracji)
        self.raw_history: deque = deque(maxlen=3000)   # ramki do kalibracji automatycznej
        self.calibrating = False                # otwarty kreator kalibracji – bez wyskakujących raportów
        self.last_change: Optional[CodeChange] = None   # do odtworzenia wyświetlacza po przebudowie okna
        self.rec = RecordingManager(int(self.settings.get("rec_max_starts", 4)))
        self.reports_dir = Path("reports")      # main.py podmienia na właściwy katalog

    # ---------- ustawienia ----------

    @property
    def vendor(self) -> str:
        return self.settings.get("bios_vendor", "award")

    def set_vendor(self, vendor: str) -> None:
        self.settings["bios_vendor"] = vendor
        self.config.save_settings(self.settings)
        code = self.assembler.current_code
        if code:
            self._publish_diagnosis(code)

    def update_settings(self, changes: dict) -> None:
        self.settings.update(changes)
        self.config.save_settings(self.settings)

    # ---------- połączenie ----------

    def connect(self, kind: TransportKind) -> None:
        self.disconnect()
        self.settings["transport"] = kind.value
        self.config.save_settings(self.settings)
        self.bus.publish(ev.CONNECTION, (ConnectionState.CONNECTING, kind.label))
        try:
            transport = self.transport_factory(kind, self.settings, self.segment_map, self.profile.digits,
                                               profile=self.profile)
            transport.open()
        except TransportError as exc:
            self.bus.publish(ev.CONNECTION, (ConnectionState.ERROR, str(exc)))
            return
        self._transport = transport
        self._last_rx = time.monotonic()
        self._silence_warned = False
        self._reader = ReaderThread(transport, self.events)
        self._reader.start()
        # nowe połączenie = nowa sesja (inne źródło ma inny zegar ts)
        if self.recorder.current.items:
            self._new_session()
        else:
            self.assembler.reset()
        self.bus.publish(ev.CONNECTION, (ConnectionState.CONNECTED, transport.name))
        self.send(commands.set_debounce(self.settings.get("debounce_ms", 16)))
        self.send(commands.ping())

    @property
    def is_connected(self) -> bool:
        return self._transport is not None

    @property
    def transport_name(self) -> str:
        return getattr(self._transport, "name", "") if self._transport else ""

    def disconnect(self) -> None:
        # kolejność: najpierw zatrzymać i poczekać na wątek czytający (read_line ma timeout 0,3 s),
        # dopiero potem zamknąć port – zamknięcie portu w trakcie odczytu wywracało pyserial
        if self._reader:
            self._reader.stop()
            self._reader.join(timeout=1.5)
        if self._transport:
            try:
                self._transport.close()
            except TransportError:
                pass
        self._reader, self._transport = None, None
        self.bus.publish(ev.CONNECTION, (ConnectionState.DISCONNECTED, ""))

    def send(self, line: str) -> None:
        if not self._transport:
            return
        try:
            self._transport.write_line(line)
        except TransportError as exc:
            self.bus.publish(ev.STATUS, t("status.send_failed", error=exc))

    # ---------- pętla zdarzeń (wątek GUI) ----------

    def pump(self, max_events: int = 200) -> None:
        """Opróżnia kolejkę zdarzeń z wątku czytającego. Wołane z GuiAdapter."""
        for _ in range(max_events):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            self.handle(event)
        if self._transport and not self._silence_warned and time.monotonic() - self._last_rx > 5:
            # ESP32 wysyła "heartbeat" co 1 s – 5 s ciszy znaczy, że dane nie dochodzą
            self._silence_warned = True
            self.bus.publish(ev.STATUS, t("status.silence"))
        hang = self.assembler.check_hang(float(self.settings.get("hang_seconds", 15)))
        if hang:
            self._on_stall(hang)
        if self.rec.state == rec_mod.RECORDING:
            self._check_recording_end()

    def _on_stall(self, hang) -> None:
        """Brak zmian kodu przez hang_seconds. To NIE musi być awaria: BIOS może czekać na
        użytkownika (Setup, F1) albo zakończyć POST. Sesja zostaje otwarta – jeśli przyjdzie
        nowy kod, przebieg leci dalej."""
        session = self.recorder.current
        code = hang.code.value if hang.code else None
        entries = self.diagnosis.repository.find(code, self.vendor) if code else []
        wait = next((e for e in entries if e.kind == "wait"), None)
        if wait is not None:
            kind = "wait"
            session.set_result("result.wait", code=code, stage=wait.stage)
        elif code in ("FF", "00") and len(session.items) > 1:
            kind = "done"
            session.set_result("result.done", code=code)
        else:
            kind = "stop"
            self.recorder.mark_hang(code)
            session.set_result("result.stop", code=code or "?", seconds=f"{hang.seconds:.0f}")
        self.bus.publish(ev.HANG, replace(hang, kind=kind))
        self.bus.publish(ev.STATUS, session.result)
        if kind == "done":
            self._finish_session()
        elif kind == "stop":
            # raport od razu (porównanie ze wzorcem też), ale sesja zostaje otwarta:
            # jeśli płyta ruszy dalej, kolejne kody dopiszą się do tego samego przebiegu
            self._compare_golden()
            self.bus.publish(ev.SESSION_END, session)

    def handle(self, event: object) -> None:
        if not isinstance(event, TransportClosed):
            self._last_rx = time.monotonic()
            if self._silence_warned:
                self._silence_warned = False
                self.bus.publish(ev.STATUS, t("status.data_back"))
        if isinstance(event, FrameEvent):
            self.last_raw = tuple(event.digits_raw)
            self.raw_history.append(self.last_raw)
            for change in self.assembler.feed_all(event):
                self._on_code(change)
        elif isinstance(event, CodeEvent):
            for change in self.assembler.feed_code(event.code, event.ts_ms, event.gap_us):
                self._on_code(change)
        elif isinstance(event, LedState):
            self.bus.publish(ev.LEDS, event)
        elif isinstance(event, SessionStart):
            self._new_session(event.session_id)
        elif isinstance(event, DeviceHello):
            self.bus.publish(ev.DEVICE, event)
            self.bus.publish(ev.STATUS, t("status.device", firmware=event.firmware, channels=event.channels))
        elif isinstance(event, Heartbeat):
            cur = self.recorder.current
            if cur is not None and event.gap_max_us > cur.gap_max_us:
                cur.gap_max_us = event.gap_max_us
        elif isinstance(event, DeviceError):
            self.bus.publish(ev.STATUS, t("status.device_error", message=event.message))
        elif isinstance(event, CommandReply):
            self.bus.publish(ev.REPLY, event)
        elif isinstance(event, ReplayEvent):
            self._on_replay(event)
        elif isinstance(event, TransportClosed):
            self._reader, self._transport = None, None
            state = ConnectionState.ERROR if event.reason else ConnectionState.DISCONNECTED
            self.bus.publish(ev.CONNECTION, (state, event.reason))

    # ---------- logika ----------

    def _finish_session(self) -> None:
        """Zamyka bieżącą sesję i ogłasza ją do raportu (raz na sesję)."""
        session = self.recorder.current
        if session.ended or not session.items:
            return
        self._compare_golden()
        if not session.result_key:
            if session.last_code == "FF" and len(session.items) > 1:
                session.set_result("result.done", code="FF")
            else:
                session.set_result("result.reset", code=session.last_code)
        session.ended = True
        self.bus.publish(ev.SESSION_END, session)

    def _new_session(self, session_id: Optional[int] = None, source: str = LIVE) -> None:
        self._finish_session()
        self.assembler.reset()
        session = self.recorder.start(session_id, source)
        self.bus.publish(ev.SESSION, session)
        if source == LIVE:
            self._on_board_start(session)

    # ---------- nagrywanie (REC) ----------

    def arm_recording(self) -> None:
        """REC: czekamy na reset / włączenie płyty, dopiero wtedy nagrywamy."""
        self.rec.max_starts = max(1, int(self.settings.get("rec_max_starts", 4)))
        if self.rec.arm():
            self.bus.publish(ev.REC, (rec_mod.ARMED, None))
            self.bus.publish(ev.STATUS, t("rec.status_armed"))

    def stop_recording(self) -> None:
        """STOP: anuluje oczekiwanie albo kończy trwające nagranie."""
        if self.rec.cancel():
            self.bus.publish(ev.REC, (rec_mod.IDLE, None))
            self.bus.publish(ev.STATUS, t("rec.status_cancelled"))
        elif self.rec.state == rec_mod.RECORDING:
            self._finish_recording("rec.end_manual", code=self.recorder.current.last_code or "?")

    def _on_board_start(self, session: Session) -> None:
        if not hasattr(self, "rec"):      # kontroler złożony częściowo (testy)
            return
        what = self.rec.on_new_start(session)
        if what == "started":
            self.bus.publish(ev.REC, (rec_mod.RECORDING, self.rec.current))
            self.bus.publish(ev.STATUS, t("rec.status_recording"))
        elif what == "next":
            self.bus.publish(ev.REC, (rec_mod.RECORDING, self.rec.current))
            self.bus.publish(ev.STATUS, t("rec.status_next_start", n=len(self.rec.current.starts)))
        elif what == "loop":
            starts = self.rec.current.starts
            self._finish_recording("rec.end_loop", n=len(starts),
                                   codes=", ".join(s.last_code or "?" for s in starts))

    def _check_recording_end(self) -> None:
        """Koniec nagrania: POST zakończony, BIOS czeka na użytkownika albo postój."""
        idle = self.assembler.idle_seconds()
        code = self.assembler.current_code
        session = self.recorder.current
        if idle is None or code is None or not session.items:
            return
        value = code.value
        # 00/FF to koniec POST tylko po prawdziwym przebiegu: zaraz po włączeniu zasilania
        # zatrzask pokazuje przypadkowe bajty i 00 (pomiar 26.10: 04 00 10 12 1A, potem 00)
        if value in ("00", "FF") and len(session.items) >= MIN_DONE_CODES \
                and idle >= float(self.settings.get("rec_done_seconds", 3)):
            self._finish_recording("rec.end_done", code=value)
        elif idle >= float(self.settings.get("rec_wait_seconds", 5)) and any(
                e.kind == "wait" for e in self.diagnosis.repository.find(value, self.vendor)):
            entry = next(e for e in self.diagnosis.repository.find(value, self.vendor) if e.kind == "wait")
            self._finish_recording("rec.end_wait", code=value, stage=entry.stage)
        elif idle >= float(self.settings.get("hang_seconds", 15)):
            self._finish_recording("rec.end_stop", code=value, seconds=f"{idle:.0f}")

    def _finish_recording(self, key: str, **fields) -> None:
        rec = self.rec.finish(key, **fields)
        if rec is None:
            return
        self._save_recording(rec)
        self.bus.publish(ev.REC, (rec_mod.DONE, rec))

    def _save_recording(self, rec: Recording) -> None:
        """Automatyczny zapis TXT (raport) i CSV (czasy) do katalogu raportów."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        meta = self.default_report_meta()
        # numer REC liczy się od 1 po każdym uruchomieniu – w nazwie pliku sekundy, żeby nic nie nadpisać
        stem = "_".join(p for p in (meta.repair_no, meta.board) if p)
        stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)[:50]
        txt = self.reports_dir / "_".join(p for p in ("NIUCHACZ_REC", stem, f"{rec.started_at:%Y%m%d_%H%M%S}") if p)
        txt = txt.with_suffix(".txt")
        try:
            printing.save_text(txt, self.report_text(rec, meta))
            csv_path = txt.with_suffix(".csv")
            exporter.export_recording_csv(rec, csv_path)
            rec.saved = [txt, csv_path]
            self.bus.publish(ev.STATUS, t("rec.status_saved", result=rec.result, name=txt.name))
        except OSError as exc:
            self.bus.publish(ev.STATUS, t("rec.status_save_failed", error=exc))

    def save_last_run(self) -> Optional[Recording]:
        """„Zapisz ostatni przebieg” – dla przebiegu, który nie był nagrywany przyciskiem REC."""
        session = next((s for s in reversed(self.recorder.sessions) if s.items), None)
        if session is None:
            self.bus.publish(ev.STATUS, t("status.no_codes_yet"))
            return None
        rec = self.rec.snapshot(session)
        self._save_recording(rec)
        self.bus.publish(ev.REC, ("saved", rec))
        return rec

    def _on_code(self, change: CodeChange) -> None:
        self.last_change = change
        if not change.is_new:
            self.bus.publish(ev.CODE, change)   # tylko odświeżenie wyświetlacza
            return
        items = self.recorder.current.items
        if items and change.ts_ms < items[-1].ts_ms:
            # zegar urządzenia cofnął się (restart ESP32) – to już inny przebieg
            self._new_session()
        if not change.recovered and self._is_new_boot(change.code.value):
            # płyta startuje od nowa (np. AMI: kod bloku startowego D0–DF po kodach POST)
            self._new_session()
        session = self.recorder.current
        if self.rec.state == rec_mod.ARMED and not session.items and session.source == LIVE:
            # REC wciśnięty przed włączeniem płyty, bez linii RESET: pierwszy kod to start
            self._on_board_start(session)
        if session.result_key and not session.ended:
            # po postoju / oczekiwaniu przyszedł nowy kod – płyta pracuje dalej
            session.set_result()
            session.hung_on = None
        self.bus.publish(ev.CODE, change)
        item = self.recorder.record(change)
        if item:
            self.bus.publish(ev.SEQUENCE, (item, self.recorder.relative_ms(item)))
        if change.code:
            self._publish_diagnosis(change.code)

    def apply_calibration(self, solution) -> None:
        """Zapisuje wynik kreatora kalibracji i od razu go używa."""
        self.segment_map = SegmentMap(channel_to_segment=list(solution.channel_to_segment),
                                      active_low=solution.active_low)
        self.config.save_segment_map(self.segment_map)
        self.config.save_display_order(solution.display_order)
        self.profile = self.config.load_card_profile()
        self.assembler = CodeAssembler(SevenSegmentDecoder(self.segment_map), self.profile)
        self.bus.publish(ev.STATUS, t("status.calibration_saved"))

    def _is_new_boot(self, code: str) -> bool:
        """Czy ten kod oznacza początek nowego startu płyty (bez linii RESET)."""
        codes = self.recorder.current.codes
        if not codes:
            return False
        vendor = getattr(self, "settings", {}).get("bios_vendor", "award")
        if vendor == "ami":
            # Tylko D0 = wektor resetu. Inne kody D* bywają w środku startu: ASRock 775V88
            # robi D3 -> kody kodu pamięci 10..90 -> DE, D4, D5… bez żadnego resetu.
            # D0 zginie tylko przy wolnym odczycie (stary tryb wyświetlacza) – wtedy inny kod D*
            # uznajemy za nowy start tylko po oczekiwaniu/postoju płyty (85, 87, brak zmian).
            session = self.recorder.current
            stopped = bool(session.result_key) or (hasattr(self, "diagnosis") and any(
                e.kind == "wait" for e in self.diagnosis.repository.find(codes[-1], "ami")))
            boot = lambda c: c == "D0" or (c[0] == "D" and stopped)
            post = lambda c: int(c, 16) < 0xD0
        elif vendor == "award":
            boot = lambda c: c[0] == "C"
            post = lambda c: c[0] != "C"
        else:
            return False
        return boot(code) and any(post(c) for c in codes)

    def _publish_diagnosis(self, code) -> None:
        diag = self.diagnosis.diagnose(code, self.vendor, self.settings.get("board", ""))
        self.bus.publish(ev.DIAGNOSIS, (diag, DiagnosisService.format(diag)))

    def _on_replay(self, event: ReplayEvent) -> None:
        if self.recorder.current.source != f"esp32:{event.session_id}":
            self._new_session(event.session_id, source=f"esp32:{event.session_id}")
        if isinstance(event.event, FrameEvent):
            for change in self.assembler.feed_all(event.event):
                self._on_code(change)
        elif isinstance(event.event, CodeEvent):
            for change in self.assembler.feed_code(event.event.code, event.event.ts_ms, event.event.gap_us):
                self._on_code(change)

    def reload_codes(self, directory: Path) -> int:
        count = self.diagnosis.repository.import_directory(directory)
        self.bus.publish(ev.STATUS, t("status.codes_reloaded", n=count))
        code = self.assembler.current_code
        if code:
            self._publish_diagnosis(code)
        return count

    # ---------- sesje z ESP32 ----------

    def request_session_list(self) -> None:
        self.send(commands.list_sessions())

    def request_session(self, session_id: int) -> None:
        self.send(commands.get_session(session_id))

    # ---------- wzorce i eksport ----------

    def save_golden(self, path: Path, **meta) -> None:
        run = golden.GoldenRun.from_session(self.recorder.current, bios_vendor=self.vendor, **meta)
        run.save(path)
        self.bus.publish(ev.STATUS, t("status.golden_saved", name=path.name, n=len(run.codes)))

    def load_golden(self, path: Path) -> None:
        self.golden_run = golden.GoldenRun.load(path)
        self.bus.publish(ev.STATUS, t("status.golden_loaded", board=self.golden_run.board,
                                      n=len(self.golden_run.codes)))
        self._compare_golden()

    def _compare_golden(self) -> None:
        if not self.golden_run or not self.recorder.current.items:
            return
        div = golden.compare(self.recorder.current.codes, self.golden_run.codes)
        key, fields = golden.describe(div, self.golden_run)
        self.recorder.current.set_golden(key, **fields)
        self.bus.publish(ev.GOLDEN, (key, fields))

    # ---------- raport tekstowy ----------

    def finish_session_now(self) -> None:
        """Ręczne zakończenie sesji (przycisk / menu) – otwiera raport."""
        session = self.recorder.current
        if session.ended:
            self.bus.publish(ev.SESSION_END, session)
            return
        if not session.items:
            self.bus.publish(ev.STATUS, t("status.no_codes_yet"))
            return
        session.set_result("result.manual", code=session.last_code)
        self._finish_session()

    def _stage_for(self, code: str, lang: Optional[str] = None) -> str:
        entries = self.diagnosis.repository.find(code, self.vendor)
        return DiagnosisService.stage(entries[0], lang) if entries else ""

    def report_text(self, session, meta: ReportMeta, lang: Optional[str] = None) -> str:
        """Raport sesji albo nagrania (Recording) – w podanym albo bieżącym języku."""
        diag_text = ""
        if session.last_code:
            post = PostCode.parse(session.last_code)
            if post:
                diag_text = DiagnosisService.format(self.diagnosis.diagnose(post, self.vendor, meta.board), lang)
        vendor_label = BiosVendor(self.vendor).label if self.vendor in [v.value for v in BiosVendor] else self.vendor
        stage = lambda c: self._stage_for(c, lang)  # noqa: E731
        if isinstance(session, Recording):
            return build_recording_report(session, vendor_label, meta, stage, diag_text, lang=lang)
        return build_report(session, vendor_label, meta, stage, diag_text, lang=lang)

    def refresh_language(self) -> None:
        """Po zmianie języka: ponownie publikuje teksty, które widoki pokazują na stałe."""
        if self.last_change is not None:
            self.bus.publish(ev.CODE, self.last_change)
        code = self.assembler.current_code
        if code:
            self._publish_diagnosis(code)
        session = self.recorder.current
        if session.golden_key:
            self.bus.publish(ev.GOLDEN, (session.golden_key, session.golden_fields))

    def default_report_meta(self) -> ReportMeta:
        return ReportMeta(board=self.settings.get("board", ""),
                          technician=self.settings.get("technician", ""))

    def save_report(self, path: Path, text: str) -> None:
        printing.save_text(path, text)
        self.bus.publish(ev.STATUS, t("status.report_saved", path=path))

    def print_report(self, path: Path, text: str) -> None:
        """Zapisuje (jeśli trzeba) i drukuje. Rzuca printing.PrintError."""
        printing.save_text(path, text)
        printing.print_file(path)
        self.bus.publish(ev.STATUS, t("status.printed", name=path.name))

    def export_report(self, path: Path) -> None:
        self.save_report(path, self.report_text(self.recorder.current, self.default_report_meta()))

    def export_csv(self, path: Path) -> None:
        exporter.export_csv(self.recorder.current, path)
        self.bus.publish(ev.STATUS, t("status.csv_saved", name=path.name))
