# NIUCHACZ – "oscyloskop" z ESP32: napięcie JEDNEJ linii segmentu w czasie każdej cyfry.
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


def main():
    idx = {1: 0, 2: 1, 4: 2, 8: 3}
    s = [0.0] * 4
    n = [0] * 4
    lo = [9.9] * 4
    hi = [0.0] * 4
    t0 = time.ticks_ms()
    for _ in range(SAMPLES):
        d1 = dig_mask()
        v = read_volts()
        d2 = dig_mask()
        if d1 == d2 and d1 in idx:      # cała próbka w czasie jednej cyfry
            k = idx[d1]
            s[k] += v
            n[k] += 1
            if v < lo[k]:
                lo[k] = v
            if v > hi[k]:
                hi[k] = v
    dt = time.ticks_diff(time.ticks_ms(), t0)
    print("Próbek ADC: %d w %d ms (%s)" % (SAMPLES, dt, "read_uv" if use_uv else "read_u16"))
    print("Cyfra   próbek   średnio    min     max   [V na linii karty]")
    for k in range(4):
        if n[k]:
            print("DIG%d   %6d    %5.2f   %5.2f   %5.2f" % (k + 1, n[k], s[k] / n[k], lo[k], hi[k]))
        else:
            print("DIG%d   brak próbek" % (k + 1))
    print("Próg CD4050 (zasilanie 3,3 V) to ok. 1,65 V: poniżej = 'świeci', powyżej = 'zgaszony'.")


main()
