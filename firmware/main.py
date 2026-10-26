# NIUCHACZ firmware – pętla główna. Tylko składa moduły.
#
# Przepływ: sampler -> filtr stabilności -> (sesja na flash, Wi-Fi, USB)
# Nowa sesja zaczyna się, gdy linia RESET przechodzi z "reset" na "praca".

import array
import asyncio
import gc
import time

import config
import protocol
import sampler
import demo
from net_server import NetServer
from session_store import SessionStore
from usb_link import UsbLink

USB_BUDGET_US = 2500         # USB w trakcie serii: najwyżej ok. 1 linia na przerwę
IDLE_USB_BUDGET_US = 50000   # gdy płyta stoi: dośle resztę kolejki
USB_Q_MAX = 400              # bez PC na USB kolejka nie może rosnąć bez końca
IDLE_MS = 1000               # tyle ms bez nowego kodu = płyta stoi (zapis flash, gc)
LED_KEEPALIVE_MS = 2000


class Niuchacz:
    def __init__(self):
        sampler.setup_pins()
        self.store = SessionStore()
        self.net = NetServer(self.handle_command)
        self.usb = UsbLink(self.handle_command, config.USB_ENABLED)
        self.debounce_ms = config.DEBOUNCE_MS
        self.raw_dump = False
        self.digits = bytearray(4)
        self.act = bytearray(2)
        self.sent = bytes(4)
        self.candidate = bytes(4)
        self.candidate_since = 0
        self.prev_rst = None
        self.no_mux_windows = 0
        self.demo_mode = getattr(config, "DEMO_MODE", False)
        self.demo = None
        # "latch" = kod z 74LCX374 (8 linii danych), "display" = stary odczyt wyświetlacza
        self.mode = getattr(config, "INPUT_MODE", "latch")
        self.latch_last = -1
        self.latch_vals = bytearray(sampler.LATCH_BUF)
        self.latch_idx = array.array("I", bytes(4 * sampler.LATCH_BUF))
        self.remap = sampler.build_remap()   # kolejność przewodów Q0..Q7 na DB25
        # tłumienie migania: BIOS potrafi w pętli pisać na zmianę dwa kody (np. 83/87 w Setup)
        # setki razy na sekundę – bez tego zalalibyśmy Wi-Fi, USB i pamięć flash
        self.code_hist = []          # ostatnie wysłane kody
        self.flap = None             # para kodów, które migają
        self.flap_last = -1          # ostatni kod w czasie migania (nie wysłany)
        self.flap_quiet_since = 0
        # --- ślepe przerwy: czas między oknami próbkowania, gdy ESP32 nie patrzy na zatrzask ---
        # Kod zapisany w przerwie nie ginie (zatrzask go trzyma). Giną kody pośrednie, gdy
        # w jednej przerwie BIOS zapisze dwa albo więcej. Dlatego przerwy mają być krótkie.
        self.win_end_us = None       # koniec poprzedniego okna
        self.gap_max_us = 0          # najdłuższa przerwa od ostatniego heartbeat
        self.gap_sum_us = 0
        self.stat_since_us = time.ticks_us()
        self.last_code_ms = time.ticks_ms()
        self.idle_done = False       # flush + gc już zrobione w tym postoju
        self.usb_q = []              # linie dla USB – wysyłane porcjami między oknami
        self.led_sent = None
        self.led_sent_ms = 0

    # ---------- wyjście ----------

    def emit(self, text, store=True):
        self.net.broadcast(text)     # Wi-Fi: tylko dopisanie do bufora, wysyła drain_task
        if self.usb.enabled:
            # USB (UART 115200) blokuje ok. 3 ms na linię – zawsze, nawet bez podłączonego PC.
            # Dlatego nie piszemy tu, tylko kolejkujemy i wysyłamy porcjami (usb_pump).
            if len(self.usb_q) < USB_Q_MAX:
                self.usb_q.append(text)
        if store:
            self.store.append(text)

    def usb_pump(self, budget_us=USB_BUDGET_US):
        """Wysyła kolejkę USB, ale najwyżej budget_us na jedną przerwę między oknami."""
        q = self.usb_q
        if not q:
            return
        t0 = time.ticks_us()
        while q and time.ticks_diff(time.ticks_us(), t0) < budget_us:
            self.usb.send(q.pop(0))

    # ---------- komendy ----------

    def handle_command(self, text, reply):
        cmd = protocol.parse_command(text)
        if cmd is None:
            return
        name = cmd["cmd"]
        if name == "ping":
            reply(protocol.reply("ping", ok=True, impl=sampler.IMPL, mode=self.mode))
            # aplikacja pyta po połączeniu: od razu podaj bieżący stan
            # (dane idą tylko przy zmianie, więc przy stałym kodzie aplikacja nic by nie dostała)
            if self.mode == "latch":
                if self.latch_last >= 0:
                    reply(protocol.code(self.remap[self.latch_last], time.ticks_ms()))
            else:
                reply(protocol.frame(self.sent, time.ticks_ms()))
        elif name == "set":
            self.debounce_ms = int(cmd.get("debounce_ms", self.debounce_ms))
            reply(protocol.reply("set", ok=True, debounce_ms=self.debounce_ms))
        elif name == "raw_dump":
            self.raw_dump = bool(cmd.get("on"))
            reply(protocol.reply("raw_dump", ok=True, on=self.raw_dump))
        elif name == "list_sessions":
            reply(protocol.reply("list_sessions", ids=self.store.list_ids()))
        elif name == "get_session":
            sid = int(cmd.get("id", 0))
            n = 0
            for line in self.store.read_lines(sid):
                reply('{"t":"replay","id":%d,"ev":%s}' % (sid, line))
                n += 1
            reply(protocol.reply("get_session", id=sid, n=n))
        elif name == "clear_sessions":
            self.store.clear()
            reply(protocol.reply("clear_sessions", ok=True))
        else:
            reply(protocol.reply(name, ok=False, msg="nieznana komenda"))

    # ---------- logika próbkowania ----------

    def process_window(self, now):
        # okno = pełny obieg multipleksu (stała w sampler.py; stare SAMPLES_PER_WINDOW z config ignorujemy)
        captured = sampler.sample_window(sampler.WINDOW_SAMPLES, self.digits, self.act,
                                         1 if config.DIG_ACTIVE_LOW else 0)
        if captured == 0:
            self.no_mux_windows += 1
            if self.no_mux_windows == 50:    # ok. 1 s bez multipleksu (okno ok. 19 ms)
                self.emit(protocol.error("no_mux_activity"), store=False)
        else:
            self.no_mux_windows = 0

        if config.LEDS_CONNECTED:
            leds = sampler.leds_from_activity(self.act[0], self.act[1], config.RST_ACTIVE_HIGH)
            self._handle_reset(leds["rst"], now)
        else:
            leds = None   # diody niepodłączone: brak raportów i brak sesji z linii RESET

        current = bytes(self.digits)
        if current != self.candidate:
            self.candidate = current
            self.candidate_since = now
        elif current != self.sent and time.ticks_diff(now, self.candidate_since) >= self.debounce_ms:
            self.sent = current
            self.emit(protocol.frame(current, now))
        if self.raw_dump:
            self.emit(protocol.line({"t": "raw", "d": list(current), "a": [self.act[0], self.act[1]],
                                     "ts": now}), store=False)
        return leds

    def process_latch(self, now):
        """Tryb zatrzasku: każda zmiana bajtu Q0–Q7 = nowy kod POST."""
        t0 = time.ticks_us()
        gap_us = time.ticks_diff(t0, self.win_end_us) if self.win_end_us is not None else 0
        cnt = sampler.latch_window(sampler.LATCH_SAMPLES, sampler.LATCH_QUIET, sampler.LATCH_MAX,
                                   self.latch_last, self.latch_vals, self.latch_idx, sampler.LATCH_BUF,
                                   self.act)
        self.win_end_us = time.ticks_us()
        if gap_us > self.gap_max_us:
            self.gap_max_us = gap_us
        self.gap_sum_us += gap_us
        leds = None
        if config.LEDS_CONNECTED:
            # diody karty: IRDY/FRAME = aktywność (zmiany w oknie), RESET = poziom przez całe okno
            leds = sampler.leds_from_activity(self.act[0], self.act[1], config.RST_ACTIVE_HIGH)
            if leds["rst"] and not self.prev_rst:
                self.code_hist = []          # nowy start płyty – miganie z poprzedniego się nie liczy
                self.flap = None
            self._handle_reset(leds["rst"], now)
        if cnt:
            # czas próbki z tej samej serii: ostatnia zmiana -> ok. ostatni indeks; przybliżamy
            # stałą szybkością pętli zmierzoną na tym oknie
            n_done = max(self.latch_idx[cnt - 1] + sampler.LATCH_QUIET, sampler.LATCH_SAMPLES)
            us_per = time.ticks_diff(time.ticks_us(), t0) / n_done
        else:
            us_per = 0
        for k in range(cnt):
            ts = now + int(self.latch_idx[k] * us_per / 1000)
            # zmiana już na początku okna = bajt zmienił się w przerwie, gdy nikt nie patrzył:
            # przed tym kodem mogły zginąć kody pośrednie (aplikacja oznaczy go w raporcie)
            gap = gap_us if k == 0 and self.latch_idx[0] <= 1 else 0
            self._latch_code(self.remap[self.latch_vals[k]], ts, gap)
        if cnt:
            self.latch_last = self.latch_vals[cnt - 1]
            self.flap_quiet_since = now
            self.last_code_ms = now
            self.idle_done = False
        elif self.flap is not None and time.ticks_diff(now, self.flap_quiet_since) > 300:
            # miganie ustało – wyślij kod, na którym się zatrzymało, jeśli różni się od ostatniego
            if self.code_hist and self.flap_last >= 0 and self.flap_last != self.code_hist[-1]:
                self._send_code(self.flap_last, now)
            self.flap = None
        return leds

    def _latch_code(self, c, ts, gap=0):
        if self.flap is not None:
            if c in self.flap:
                self.flap_last = c
                return
            self.flap = None
        h = self.code_hist
        if len(h) >= 2 and c == h[-2] and c != h[-1]:
            # A B A -> od teraz para {A, B} miga; ten jeden wysyłamy, kolejne tłumimy
            self.flap = (h[-1], c)
            self.flap_last = c
        self._send_code(c, ts, gap)

    def _send_code(self, c, ts, gap=0):
        self.code_hist = (self.code_hist + [c])[-3:]
        self.emit(protocol.code(c, ts, gap))

    def demo_window(self, now):
        # tryb demo: symulowane kody zamiast odczytu karty
        if self.demo is None:
            self.demo = demo.Demo(now)
        current, new_session = self.demo.step(now)
        if new_session:
            sid = self.store.start()
            self.sent = bytes(4)
            self.emit(protocol.session(sid, now))
        if current != self.sent:
            self.sent = current
            self.emit(protocol.frame(current, now))
        return None

    def _handle_reset(self, rst, now):
        if self.prev_rst == 1 and rst == 0:
            sid = self.store.start()
            self.sent = bytes(4)   # pierwszy kod nowej sesji zawsze zostanie wysłany
            self.emit(protocol.session(sid, now))
        self.prev_rst = rst

    # ---------- zadania asyncio ----------

    async def sampling_task(self):
        last_hb = time.ticks_ms()
        while True:
            now = time.ticks_ms()
            if self.demo_mode:
                leds = self.demo_window(now)
            elif self.mode == "latch":
                leds = self.process_latch(now)
            else:
                leds = self.process_window(now)
            if leds is not None:
                # diody: tylko przy zmianie (+ co LED_KEEPALIVE_MS), bez zapisu na flash
                if leds != self.led_sent or time.ticks_diff(now, self.led_sent_ms) >= LED_KEEPALIVE_MS:
                    self.emit(protocol.leds(leds, now), store=False)
                    self.led_sent = leds
                    self.led_sent_ms = now
            if time.ticks_diff(now, last_hb) >= config.HEARTBEAT_MS:
                total = time.ticks_diff(time.ticks_us(), self.stat_since_us)
                blind = (self.gap_sum_us * 1000 // total) if total > 0 else 0
                self.emit(protocol.heartbeat(now, self.gap_max_us, blind), store=False)
                self.gap_max_us = 0
                self.gap_sum_us = 0
                self.stat_since_us = time.ticks_us()
                last_hb = now
            if time.ticks_diff(now, self.last_code_ms) >= IDLE_MS:
                # płyta stoi na jednym kodzie: teraz wolno blokować na dłużej (flash, gc)
                if not self.idle_done:
                    self.store.flush()
                    gc.collect()
                    self.idle_done = True
                self.usb_pump(IDLE_USB_BUDGET_US)
            else:
                self.idle_done = False
                self.usb_pump()
            self.usb.poll()
            await asyncio.sleep_ms(20 if self.demo_mode else 0)   # oddaj czas obsłudze sieci

    async def drain_task(self):
        while True:
            await self.net.drain()
            await asyncio.sleep_ms(20)

    async def run(self):
        await self.net.start()
        self.usb.send(protocol.hello())
        # ESP32 zasilany z +5V karty startuje razem z płytą: włączenie = nowa sesja.
        # Kolejne sesje zaczynają się na zboczu RESET.
        sid = self.store.start()
        self.emit(protocol.session(sid, time.ticks_ms()))
        asyncio.create_task(self.drain_task())
        await self.sampling_task()


def _safe_start(seconds=3):
    """Okno na przerwanie startu: Ctrl+C w Thonny albo przytrzymany przycisk BOOT."""
    import machine
    boot_btn = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
    print("NIUCHACZ: start za %d s (Ctrl+C lub przytrzymaj BOOT = zostań w REPL)" % seconds)
    for _ in range(seconds * 10):
        if boot_btn.value() == 0:
            return False
        time.sleep_ms(100)
    return True


if _safe_start():
    asyncio.run(Niuchacz().run())
else:
    print("NIUCHACZ: zatrzymano przyciskiem BOOT – tryb REPL")
