# NIUCHACZ – poziomy napięć kresek w czasie każdej cyfry (do doboru progu komparatora).
#
# Sonda NOWA, na P34 (ADC1 – działa pewniej niż stary GPIO13):
#   końcówka sondy ── R1 100 kΩ ──┬── P34
#                                  └── R2 100 kΩ ── GND
# Stare R1/R2 przy P13 odłącz.
#
# Przebieg (Thonny, F5), karta pokazuje STAŁY napis, np. „0061”:
#   1. test sondy: masa (DB25 pin 13) i +5 V  -> jeśli zły, program kończy i mówi dlaczego,
#   2. piny 1–7 płytki przejściowej po kolei: przykładasz sondę, Enter, trzymasz ok. 2 s.
# Wynik: dla każdej cyfry trzy liczby  min / środek / max  [V na linii karty].

import array
import time
import micropython
import network
from machine import ADC, Pin

from sampler import setup_pins

ADC_PIN = 34
DIVIDER = 2.0
SAMPLES = 3000
PER_DIG = 1200

network.WLAN(network.AP_IF).active(False)
network.WLAN(network.STA_IF).active(False)
time.sleep_ms(200)

setup_pins()
adc = ADC(Pin(ADC_PIN))
adc.atten(ADC.ATTN_11DB)
use_uv = hasattr(adc, "read_uv")

_bufs = [array.array("H", bytes(2 * PER_DIG)) for _ in range(4)]


@micropython.viper
def dig_mask() -> int:
    a = int(ptr32(0x3FF4403C)[0])  # noqa: F821
    b = int(ptr32(0x3FF44040)[0])  # noqa: F821
    return ((a >> 26) & 3) | ((b & 3) << 2)


def read_mv():
    if use_uv:
        return int(adc.read_uv() * DIVIDER / 1000)
    return int(adc.read_u16() * 3300 * DIVIDER / 65535)


def measure():
    """Zwraca dla każdej cyfry (min, mediana, max) w V – min/max jako 5. i 95. percentyl."""
    idx = {1: 0, 2: 1, 4: 2, 8: 3}
    n = [0, 0, 0, 0]
    for _ in range(SAMPLES):
        d1 = dig_mask()
        v = read_mv()
        d2 = dig_mask()
        if d1 == d2 and d1 in idx:
            k = idx[d1]
            if n[k] < PER_DIG:
                _bufs[k][n[k]] = v
                n[k] += 1
    res = []
    for k in range(4):
        if n[k] < 20:
            res.append(None)
            continue
        vals = sorted(_bufs[k][:n[k]])
        m = n[k]
        res.append((vals[m * 5 // 100] / 1000, vals[m // 2] / 1000, vals[m * 95 // 100] / 1000))
    return res


def measure_all():
    """Bez podziału na cyfry – do testu sondy."""
    s = 0
    for _ in range(500):
        s += read_mv()
    return s / 500 / 1000


def fmt(res):
    out = []
    for r in res:
        out.append("   --  --  --  " if r is None else "%4.2f %4.2f %4.2f" % r)
    return " | ".join(out)


def main():
    print("TEST SONDY")
    input("Sonda na MASE (DB25 pin 13), Enter... ")
    g = measure_all()
    print("  masa: %.2f V (ma być < 0,3)" % g)
    input("Sonda na +5 V (szyna rezystorów 4,7k), Enter... ")
    p = measure_all()
    print("  +5 V: %.2f V (ma być 4,6–5,2)" % p)
    if g > 0.3 or not (4.6 <= p <= 5.2):
        print("SONDA NIE DZIAŁA POPRAWNIE – sprawdź R1/R2 i połączenie z P34. Koniec.")
        return
    print("Sonda OK.\n")
    rows = []
    for pin in range(1, 8):
        input("Sonda na DB25 pin %d (płytka przejściowa), Enter, trzymaj 2 s... " % pin)
        r = measure()
        rows.append((pin, r))
        print("  pin %d: %s" % (pin, fmt(r)))
    print()
    print("pin |      DIG1      |      DIG2      |      DIG3      |      DIG4")
    print("    | min  śr.  max  | min  śr.  max  | min  śr.  max  | min  śr.  max")
    for pin, r in rows:
        print(" %d  | %s" % (pin, fmt(r)))
    print("\nWklej całą tabelę do rozmowy.")


main()
