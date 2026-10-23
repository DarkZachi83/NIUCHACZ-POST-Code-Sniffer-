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
from niuchacz.knowledge.diagnosis_service import DiagnosisService
from niuchacz.protocol import commands
from niuchacz.session import exporter, golden
from niuchacz.session.recorder import Session, SessionRecorder
from niuchacz.session.report import ReportMeta, build_report
from niuchacz.transport.base import Transport, TransportError

log = logging.getLogger(__name__)


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

    def disconnect(self) -> None:
        if self._reader:
            self._reader.stop()
        if self._transport:
            try:
                self._transport.close()
            except TransportError:
                pass
        if self._reader:
            self._reader.join(timeout=1.5)
        self._reader, self._transport = None, None
        self.bus.publish(ev.CONNECTION, (ConnectionState.DISCONNECTED, ""))

    def send(self, line: str) -> None:
        if not self._transport:
            return
        try:
            self._transport.write_line(line)
        except TransportError as exc:
            self.bus.publish(ev.STATUS, f"Nie wysłano komendy: {exc}")

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
            self.bus.publish(ev.STATUS, "Brak jakichkolwiek danych z urządzenia od 5 s – port otwarty, "
                                        "ale ESP32 milczy (zrestartuj ESP32 przyciskiem EN)")
        hang = self.assembler.check_hang(float(self.settings.get("hang_seconds", 15)))
        if hang:
            self._on_stall(hang)

    def _on_stall(self, hang) -> None:
        """Brak zmian kodu przez hang_seconds. To NIE musi być awaria: BIOS może czekać na
        użytkownika (Setup, F1) albo zakończyć POST. Sesja zostaje otwarta – jeśli przyjdzie
        nowy kod, przebieg leci dalej."""
        session = self.recorder.current
        code = hang.code.value if hang.code else None
        stage = self._stage_for(code) if code else ""
        if stage.upper().startswith("CZEKA"):
            kind = "wait"
            session.result = f"CZEKA NA UŻYTKOWNIKA – kod {code}: {stage.split(':', 1)[-1].strip()}"
        elif code in ("FF", "00") and len(session.items) > 1:
            kind = "done"
            session.result = f"POST zakończony – kod {code} (przekazanie sterowania do systemu)"
        else:
            kind = "stop"
            self.recorder.mark_hang(code)
            session.result = (f"POSTÓJ na kodzie {code or '?'} – brak zmian {hang.seconds:.0f} s "
                              f"(zawieszenie albo płyta czeka – sprawdź monitor)")
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
                self.bus.publish(ev.STATUS, "Dane z urządzenia dochodzą")
        if isinstance(event, FrameEvent):
            self.last_raw = tuple(event.digits_raw)
            self.raw_history.append(self.last_raw)
            for change in self.assembler.feed_all(event):
                self._on_code(change)
        elif isinstance(event, CodeEvent):
            for change in self.assembler.feed_code(event.code, event.ts_ms):
                self._on_code(change)
        elif isinstance(event, LedState):
            self.bus.publish(ev.LEDS, event)
        elif isinstance(event, SessionStart):
            self._new_session(event.session_id)
        elif isinstance(event, DeviceHello):
            self.bus.publish(ev.DEVICE, event)
            self.bus.publish(ev.STATUS, f"Urządzenie: firmware {event.firmware}, kanałów {event.channels}")
        elif isinstance(event, Heartbeat):
            pass
        elif isinstance(event, DeviceError):
            self.bus.publish(ev.STATUS, f"Urządzenie zgłasza: {event.message}")
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
        if not session.result:
            if session.last_code == "FF" and len(session.items) > 1:
                session.result = "POST zakończony – kod FF (przekazanie do systemu)"
            else:
                session.result = f"Przerwana resetem – ostatni kod {session.last_code}"
        session.ended = True
        self.bus.publish(ev.SESSION_END, session)

    def _new_session(self, session_id: Optional[int] = None, source: str = "na żywo") -> None:
        self._finish_session()
        self.assembler.reset()
        session = self.recorder.start(session_id, source)
        self.bus.publish(ev.SESSION, session)

    def _on_code(self, change: CodeChange) -> None:
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
        if session.result and not session.ended:
            # po postoju / oczekiwaniu przyszedł nowy kod – płyta pracuje dalej
            session.result = ""
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
        self.bus.publish(ev.STATUS, "Zapisano kalibrację wyświetlacza")

    def _is_new_boot(self, code: str) -> bool:
        """Czy ten kod oznacza początek nowego startu płyty (bez linii RESET)."""
        codes = self.recorder.current.codes
        if not codes:
            return False
        vendor = getattr(self, "settings", {}).get("bios_vendor", "award")
        if vendor == "ami":
            boot = lambda c: c[0] == "D"                      # blok startowy AMIBIOS8
            post = lambda c: int(c, 16) < 0xD0                # właściwy POST
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
        if self.recorder.current.source != f"ESP32 #{event.session_id}":
            self._new_session(event.session_id, source=f"ESP32 #{event.session_id}")
        if isinstance(event.event, FrameEvent):
            for change in self.assembler.feed_all(event.event):
                self._on_code(change)
        elif isinstance(event.event, CodeEvent):
            for change in self.assembler.feed_code(event.event.code, event.event.ts_ms):
                self._on_code(change)

    def reload_codes(self, directory: Path) -> int:
        count = self.diagnosis.repository.import_directory(directory)
        self.bus.publish(ev.STATUS, f"Przeładowano bazę kodów: {count} wpisów")
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
        self.bus.publish(ev.STATUS, f"Zapisano wzorzec: {path.name} ({len(run.codes)} kodów)")

    def load_golden(self, path: Path) -> None:
        self.golden_run = golden.GoldenRun.load(path)
        self.bus.publish(ev.STATUS, f"Wzorzec: {self.golden_run.board} ({len(self.golden_run.codes)} kodów)")
        self._compare_golden()

    def _compare_golden(self) -> None:
        if not self.golden_run or not self.recorder.current.items:
            return
        div = golden.compare(self.recorder.current.codes, self.golden_run.codes)
        text = f"{golden.describe(div, self.golden_run)} (wzorzec: {self.golden_run.board})"
        self.recorder.current.golden_text = text
        self.bus.publish(ev.GOLDEN, text)

    # ---------- raport tekstowy ----------

    def finish_session_now(self) -> None:
        """Ręczne zakończenie sesji (przycisk / menu) – otwiera raport."""
        session = self.recorder.current
        if session.ended:
            self.bus.publish(ev.SESSION_END, session)
            return
        if not session.items:
            self.bus.publish(ev.STATUS, "Bieżąca sesja nie ma jeszcze żadnych kodów.")
            return
        session.result = f"Zakończona ręcznie – ostatni kod {session.last_code}"
        self._finish_session()

    def _stage_for(self, code: str) -> str:
        entries = self.diagnosis.repository.find(code, self.vendor)
        return entries[0].stage if entries else ""

    def report_text(self, session: Session, meta: ReportMeta) -> str:
        diag_text = ""
        if session.last_code:
            post = PostCode.parse(session.last_code)
            if post:
                diag_text = DiagnosisService.format(self.diagnosis.diagnose(post, self.vendor, meta.board))
        vendor_label = BiosVendor(self.vendor).label if self.vendor in [v.value for v in BiosVendor] else self.vendor
        return build_report(session, vendor_label, meta, self._stage_for, diag_text)

    def default_report_meta(self) -> ReportMeta:
        return ReportMeta(board=self.settings.get("board", ""),
                          technician=self.settings.get("technician", ""))

    def save_report(self, path: Path, text: str) -> None:
        printing.save_text(path, text)
        self.bus.publish(ev.STATUS, f"Zapisano raport: {path}")

    def print_report(self, path: Path, text: str) -> None:
        """Zapisuje (jeśli trzeba) i drukuje. Rzuca printing.PrintError."""
        printing.save_text(path, text)
        printing.print_file(path)
        self.bus.publish(ev.STATUS, f"Wysłano do drukarki: {path.name}")

    def export_report(self, path: Path) -> None:
        self.save_report(path, self.report_text(self.recorder.current, self.default_report_meta()))

    def export_csv(self, path: Path) -> None:
        exporter.export_csv(self.recorder.current, path)
        self.bus.publish(ev.STATUS, f"Zapisano CSV: {path.name}")
