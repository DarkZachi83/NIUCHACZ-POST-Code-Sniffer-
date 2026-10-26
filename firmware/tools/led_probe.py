# NIUCHACZ – „analizator stanów” do szukania sygnałów diod karty (CLK, IRDY, FRAME, RESET).
# Uruchom w Thonny (F5). Co ok. 0,3 s wypisuje dla wolnych wejść NIUCHACZA:
#   % czasu w stanie wysokim i liczbę zmian stanu na sekundę.
# Pomiar jest ciągły (bez przerw), więc nawet krótki reset będzie widoczny.
#
# Linia, która się ZMIENIA (dużo zmian/s, albo inny % przy wciśniętym RESET) = sygnał diody.
# Stałe 0 % / 100 % bez zmian = w tym punkcie nie ma sygnału (zasilanie, masa albo nic).
#
# Wejścia (DB25 w pudełku):
#   pin 9 -> GPIO27, pin 10 -> GPIO32, pin 11 -> GPIO33, pin 12 -> GPIO25
#   pin 14..17 -> GPIO34, 35, 36, 39   (CLK, IRDY, FRAME, RESET)
# Stop: Ctrl+C.

import array
import time
import micropython

from sampler import setup_pins

N = 200000          # próbek na wiersz (ok. 0,2–0,3 s, cały czas bez przerw)
NAMES = ("p12", "p9", "p10", "p11", "p14", "p15", "p16", "p17")   # bity 0..7


@micropython.viper
def measure(n: int, out):
    o = ptr32(out)           # noqa: F821  out[0..7] = stan wysoki, out[8..15] = zmiany
    r0 = ptr32(0x3FF4403C)   # noqa: F821  GPIO 0..31
    r1 = ptr32(0x3FF44040)   # noqa: F821  GPIO 32..39
    k = 0
    while k < 16:
        o[k] = 0
        k += 1
    prev = 0
    i = 0
    while i < n:
        a = int(r0[0])
        b = int(r1[0])
        v = ((a >> 25) & 1) | ((a >> 26) & 2) | ((b & 3) << 2) | ((b & 0x1C) << 2) | (b & 0x80)
        x = v ^ prev
        if i == 0:
            x = 0
        if v:
            k = 0
            while k < 8:
                if (v >> k) & 1:
                    o[k] += 1
                k += 1
        if x:
            k = 0
            while k < 8:
                if (x >> k) & 1:
                    o[8 + k] += 1
                k += 1
        prev = v
        i += 1


def main():
    setup_pins()
    out = array.array("I", bytes(64))
    print("     " + "  ".join("%9s" % n for n in NAMES))
    print("     " + "  ".join("%9s" % "wys% zm/s" for _ in NAMES))
    while True:
        t0 = time.ticks_us()
        measure(N, out)
        dt = time.ticks_diff(time.ticks_us(), t0) / 1e6
        print("     " + "  ".join("%3d %5d" % (100 * out[k] // N, int(out[8 + k] / dt)) for k in range(8)))


main()
