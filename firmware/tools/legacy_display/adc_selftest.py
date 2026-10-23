# NIUCHACZ – test samej sondy ADC: GND, +5 V, sonda w powietrzu.
# Jeśli sonda działa: GND ~0 V, +5 V ~5 V, a wynik NIE zależy od cyfry.
#
# Podłączenie (zasilanie wyłączone):
#   wybrany pin DB25 (linia segmentu) ── 100 kΩ ──┬── GPIO13 ESP32
#                                                  └── 100 kΩ ── GND
# Dzielnik 1:2 – 5 V z karty daje 2,5 V na wejściu ESP32 (bezpiecznie).
#
# Uruchom w Thonny (F5) przy STAŁYM napisie na karcie. Wi-Fi zostaje na czas pomiaru
# wyłączone (przetwornik ADC2 nie działa razem z Wi-Fi) – po restarcie ESP32 wraca samo.
#
# Wynik: dla każdej cyfry DIG1..DIG4 średnie, minimalne i maksymalne napięcie linii
# (już przeliczone na napięcie na karcie, czyli x2).

import time
import machine
import network
import micropython
from machine import ADC, Pin

from sampler import setup_pins

ADC_PIN = 13
DIVIDER = 2.0          # 100k + 100k
SAMPLES = 6000

network.WLAN(network.AP_IF).active(False)
network.WLAN(network.STA_IF).active(False)
time.sleep_ms(200)

setup_pins()
adc = ADC(Pin(ADC_PIN))
adc.atten(ADC.ATTN_11DB)          # zakres ok. 0–3,1 V
use_uv = hasattr(adc, "read_uv")


@micropython.viper
def dig_mask() -> int:
    a = int(ptr32(0x3FF4403C)[0])  # noqa: F821
    b = int(ptr32(0x3FF44040)[0])  # noqa: F821
    return ((a >> 26) & 3) | ((b & 3) << 2)


def read_volts():
    if use_uv:
        return adc.read_uv() / 1000000 * DIVIDER
    return adc.read_u16() / 65535 * 3.3 * DIVIDER


def measure():
    idx = {1: 0, 2: 1, 4: 2, 8: 3}
    s = [0.0] * 4
    n = [0] * 4
    for _ in range(SAMPLES):
        d1 = dig_mask()
        v = read_volts()
        d2 = dig_mask()
        if d1 == d2 and d1 in idx:
            k = idx[d1]
            s[k] += v
            n[k] += 1
    return [s[k] / n[k] if n[k] else None for k in range(4)]


def fmt(v):
    return "  ".join("%5.2f" % x if x is not None else "  -- " for x in v)


def main():
    tests = [("masa: DB25 pin 13 (GND)", "ok. 0,0 V we wszystkich kolumnach"),
             ("+5 V: szyna rezystorów na płytce przejściowej", "ok. 5,0 V we wszystkich kolumnach"),
             ("w POWIETRZU (niczego nie dotyka)", "tylko informacyjnie")]
    rows = []
    for name, expect in tests:
        input("Sonda -> %s, potem Enter (trzymaj ok. 2 s)... " % name)
        v = measure()
        rows.append((name, expect, v))
        print("  %s" % fmt(v))
    print()
    print("Test                                              DIG1   DIG2   DIG3   DIG4   oczekiwane")
    for name, expect, v in rows:
        print("%-48s  %s   %s" % (name, fmt(v), expect))
    print("Odczyt 6,3 V = sufit przetwornika (na GPIO13 jest >3,1 V) - dzielnik nie dzieli.")


main()
