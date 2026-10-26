# NIUCHACZ firmware – próbkowanie multipleksowanego wyświetlacza
#
# Jeden odczyt rejestru GPIO_IN daje stan pinów 0..31, GPIO_IN1 pinów 32..39.
# Dla każdej próbki: która cyfra jest aktywna i jakie segmenty świecą.
# Wynik okna: bajt segmentów dla każdej z 4 cyfr + maski "widziano 1 / widziano 0"
# dla linii diod (aktywność szybkich sygnałów CLK/IRDY/FRAME).

import machine
try:
    import micropython
except ImportError:      # testy na PC
    micropython = None
from machine import Pin

GPIO_IN_REG = 0x3FF4403C
GPIO_IN1_REG = 0x3FF44040

INPUT_PINS = (16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39)

# Okno obejmuje CAŁY obieg multipleksu (4 cyfry × ok. 4 ms ≈ 16 ms), żeby każda cyfra
# była widziana w całości. Dla każdej cyfry bierzemy stan segmentów, który trwał w oknie
# NAJDŁUŻEJ. Pomiar 18.10.2026: przy przełączaniu cyfr karta na chwilę zapala/gasi wszystkie
# segmenty ("duch" = 8 albo pusta cyfra). Duch trwa µs–dziesiątki µs, prawdziwa cyfra ok. 4 ms,
# więc wybór najdłuższego odcinka odrzuca duchy niezależnie od ich długości.
WINDOW_SAMPLES = 26000   # ok. 19 ms przy 0.73 µs/próbkę – więcej niż jeden obieg (ok. 16 ms)
MIN_RUN = 48             # krótsze odcinki nie są uznawane za cyfrę (ok. 40 µs)


def setup_pins():
    # 34-39 to piny tylko-wejściowe bez podciągania; pozostałe też jako wejścia bez pull.
    for n in INPUT_PINS:
        Pin(n, Pin.IN)


def _decode(a, b, dig_low):
    seg = ((a >> 16) & 0x0F) | ((a >> 17) & 0x70) | ((a >> 18) & 0x80)
    dm = ((a >> 26) & 0x03) | ((b & 0x03) << 2)
    if dig_low:
        dm ^= 0x0F
    lv = ((b >> 2) & 0x07) | ((b >> 4) & 0x08)
    return seg, dm, lv


_DIG_INDEX = {1: 0, 2: 1, 4: 2, 8: 3}


# ---------- implementacja w czystym MicroPythonie (zapasowa, też do testów na PC) ----------

def _sample_python(n, digits_out, act_out, dig_low):
    mem = machine.mem32
    seen1 = 0
    seen0 = 0
    best_len = [0, 0, 0, 0]
    best_seg = [0, 0, 0, 0]
    prev_dm = -1
    prev_seg = -1
    run = 0
    for _ in range(n + 1):
        if _ < n:
            a = mem[GPIO_IN_REG]
            b = mem[GPIO_IN1_REG]
            seg, dm, lv = _decode(a, b, dig_low)
            seen1 |= lv
            seen0 |= lv ^ 0x0F
        else:
            seg, dm = -2, -2          # sztuczny koniec: zamyka ostatni odcinek
        if dm == prev_dm and seg == prev_seg:
            run += 1
            continue
        d = _DIG_INDEX.get(prev_dm, -1)
        if d >= 0 and run > best_len[d]:
            best_len[d] = run
            best_seg[d] = prev_seg
        prev_dm, prev_seg, run = dm, seg, 1
    captured = 0
    for d in range(4):
        if best_len[d] >= MIN_RUN:
            digits_out[d] = best_seg[d]
            captured += 1
    act_out[0] = seen1
    act_out[1] = seen0
    return captured


# ---------- szybka implementacja viper (ta sama logika) ----------

try:
    import micropython

    @micropython.viper
    def _sample_viper(n: int, digits_out, act_out, dig_low: int) -> int:
        in0 = ptr32(0x3FF4403C)   # noqa: F821  (ptr32 istnieje tylko w viper)
        in1 = ptr32(0x3FF44040)   # noqa: F821
        dout = ptr8(digits_out)   # noqa: F821
        aout = ptr8(act_out)      # noqa: F821
        seen1 = 0
        seen0 = 0
        l0 = 0
        l1 = 0
        l2 = 0
        l3 = 0
        s0 = 0
        s1 = 0
        s2 = 0
        s3 = 0
        prev_dm = -1
        prev_seg = -1
        run = 0
        i = 0
        while i <= n:
            if i < n:
                a = int(in0[0])
                b = int(in1[0])
                seg = ((a >> 16) & 0x0F) | ((a >> 17) & 0x70) | ((a >> 18) & 0x80)
                dm = ((a >> 26) & 0x03) | ((b & 0x03) << 2)
                if dig_low:
                    dm = dm ^ 0x0F
                lv = ((b >> 2) & 0x07) | ((b >> 4) & 0x08)
                seen1 = seen1 | lv
                seen0 = seen0 | (lv ^ 0x0F)
            else:
                seg = -2
                dm = -2
            if dm == prev_dm and seg == prev_seg:
                run += 1
            else:
                if prev_dm == 1:
                    if run > l0:
                        l0 = run
                        s0 = prev_seg
                elif prev_dm == 2:
                    if run > l1:
                        l1 = run
                        s1 = prev_seg
                elif prev_dm == 4:
                    if run > l2:
                        l2 = run
                        s2 = prev_seg
                elif prev_dm == 8:
                    if run > l3:
                        l3 = run
                        s3 = prev_seg
                prev_dm = dm
                prev_seg = seg
                run = 1
            i += 1
        captured = 0
        if l0 >= 48:   # = MIN_RUN
            dout[0] = s0
            captured += 1
        if l1 >= 48:
            dout[1] = s1
            captured += 1
        if l2 >= 48:
            dout[2] = s2
            captured += 1
        if l3 >= 48:
            dout[3] = s3
            captured += 1
        aout[0] = seen1
        aout[1] = seen0
        return captured

    sample_window = _sample_viper
    IMPL = "viper"
except Exception:  # brak emitera viper -> wersja zwykła
    sample_window = _sample_python
    IMPL = "python"


# bity aktywności: 0=CLK, 1=IRDY, 2=FRAME, 3=RESET
LED_CLK, LED_IRDY, LED_FRAME, LED_RST = 1, 2, 4, 8


def leds_from_activity(seen1, seen0, rst_active_high):
    """Zamienia maski okna na stan diod: aktywność (0 i 1 w oknie) oraz poziom RESET."""
    toggling = seen1 & seen0
    if rst_active_high:
        rst = 1 if (seen1 & LED_RST) and not (seen0 & LED_RST) else 0
    else:
        rst = 1 if (seen0 & LED_RST) and not (seen1 & LED_RST) else 0
    return {
        "clk": 1 if toggling & LED_CLK else 0,
        "irdy": 1 if toggling & LED_IRDY else 0,
        "frame": 1 if toggling & LED_FRAME else 0,
        "rst": rst,
    }


# =====================================================================================
# TRYB ZATRZASKU (od 22.10.2026): kod POST prosto z wyjść Q0–Q7 kostki 74LCX374 na karcie.
#   Q0..Q6 -> DB25 1..7 -> kanały 1..7 -> GPIO 16,17,18,19,21,22,23
#   Q7     -> DB25 8    -> kanał 9      -> GPIO 26
# Linie są statyczne (zatrzask trzyma bajt do następnego zapisu BIOS-u do portu 80h),
# więc wystarczy czytać rejestr i notować każdą zmianę, która utrzymała się 2 odczyty z rzędu.
# =====================================================================================

LATCH_SAMPLES = 20000     # ok. 15 ms – minimalne okno
# Okno nie kończy się w środku serii kodów: trwa dalej, dopóki od ostatniej zmiany nie minie
# LATCH_QUIET próbek (ok. 30 ms ciszy), najwyżej LATCH_MAX (ok. 300 ms). Wysyłanie danych
# (USB, Wi-Fi) odbywa się dopiero po serii – w tym czasie ESP32 nie patrzy na linie, więc
# przerwa nie może wypadać w środku szybkiej sekwencji (pomiar 23.10: zgubione 7C, 84, 90–AC).
LATCH_QUIET = 40000
LATCH_MAX = 400000
LATCH_BUF = 256

# Które bity odczytu (0..6 = DB25 piny 1..7, 7 = DB25 pin 8) niosą Q0..Q7.
# Rysunek zakłada (0,1,2,3,4,5,6,7). Pomiary 23.10.2026 na płytce przejściowej:
#   Q7 jest na DB25 pin 5, a Q4 na DB25 pin 8 (kod 87 w Setup),
#   Q5 i Q6 zamienione (piny 6/7) – wyszło z przebiegu POST: B0 zamiast D0, 4A zamiast 2A itd.
# Zamienione w programie, nie w kablach. Można nadpisać w config.py:  LATCH_ORDER = (...)
LATCH_ORDER = (0, 1, 2, 3, 7, 6, 5, 4)


def build_remap(order=None):
    """Tablica 256 bajtów: surowy odczyt -> prawdziwy kod Q7..Q0."""
    if order is None:
        try:
            import config
            order = getattr(config, "LATCH_ORDER", LATCH_ORDER)
        except ImportError:
            order = LATCH_ORDER
    t = bytearray(256)
    for raw in range(256):
        v = 0
        for q in range(8):
            if raw & (1 << order[q]):
                v |= 1 << q
        t[raw] = v
    return t


def latch_byte(a):
    return ((a >> 16) & 0x0F) | ((a >> 17) & 0x70) | ((a >> 19) & 0x80)


def _latch_python(n, quiet, maxn, last, vals, idx, maxcnt, act=None):
    mem = machine.mem32
    prev = last
    cand = -1
    cnt = 0
    lastchg = -quiet
    s1 = 0
    s0 = 0
    i = 0
    while i < maxn and (i < n or i - lastchg < quiet):
        b = latch_byte(mem[GPIO_IN_REG])
        lv = ((mem[GPIO_IN1_REG] >> 2) & 0x07) | ((mem[GPIO_IN1_REG] >> 4) & 0x08)
        s1 |= lv
        s0 |= lv ^ 0x0F
        if b != prev:
            if b == cand:
                vals[cnt] = b
                idx[cnt] = i
                cnt += 1
                prev = b
                cand = -1
                lastchg = i
                if cnt >= maxcnt:
                    break
            else:
                cand = b
        else:
            cand = -1
        i += 1
    if act is not None:
        act[0] = s1
        act[1] = s0
    return cnt


try:
    @micropython.viper
    def _latch_viper(n: int, quiet: int, maxn: int, last: int, vals, idx, maxcnt: int, act) -> int:
        in0 = ptr32(0x3FF4403C)   # noqa: F821
        in1 = ptr32(0x3FF44040)   # noqa: F821  diody: GPIO34/35/36/39
        v = ptr8(vals)            # noqa: F821
        ix = ptr32(idx)           # noqa: F821
        ac = ptr8(act)            # noqa: F821
        s1 = 0
        s0 = 0
        prev = last
        cand = -1
        cnt = 0
        lastchg = 0 - quiet
        i = 0
        while i < maxn:
            if i >= n and i - lastchg >= quiet:
                break
            a = int(in0[0])
            c = int(in1[0])
            lv = ((c >> 2) & 0x07) | ((c >> 4) & 0x08)
            s1 = s1 | lv
            s0 = s0 | (lv ^ 0x0F)
            b = ((a >> 16) & 0x0F) | ((a >> 17) & 0x70) | ((a >> 19) & 0x80)
            if b != prev:
                if b == cand:
                    v[cnt] = b
                    ix[cnt] = i
                    cnt += 1
                    prev = b
                    cand = -1
                    lastchg = i
                    if cnt >= maxcnt:
                        break
                else:
                    cand = b
            else:
                cand = -1
            i += 1
        ac[0] = s1
        ac[1] = s0
        return cnt

    latch_window = _latch_viper
except Exception:
    latch_window = _latch_python
