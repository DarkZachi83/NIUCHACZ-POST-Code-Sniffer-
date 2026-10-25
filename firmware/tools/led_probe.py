# NIUCHACZ – prosty „analizator stanów” do szukania sygnałów diod karty (CLK, IRDY, FRAME, RESET).
# Uruchom w Thonny (F5). Co sekundę wypisuje dla wolnych wejść NIUCHACZA:
#   % czasu w stanie wysokim i liczbę zmian stanu na sekundę.
#
# Linia, która się ZMIENIA (dużo zmian/s, albo inny % przy wciśniętym RESET) = to jest sygnał diody.
# Stałe 0 % / 100 % bez zmian = w tym punkcie nie ma sygnału (zasilanie, masa albo nic).
#
# Wejścia (DB25 w pudełku):
#   pin 10 -> GPIO32, pin 11 -> GPIO33, pin 12 -> GPIO25   (sprawdzone, działają)
#   pin 14..17 -> GPIO34, 35, 36, 39                     (docelowe dla diod – jeśli są podłączone w pudełku)
# Stop: Ctrl+C.

import array
import time
import micropython

from sampler import setup_pins

N = 20000
NAMES = ("p12", "p9", "p10", "p11", "p14", "p15", "p16", "p17")   # kolejność bitów 0..7


@micropython.viper
def capture(buf, n: int):
    p = ptr8(buf)            # noqa: F821
    r0 = ptr32(0x3FF4403C)   # noqa: F821  GPIO 0..31
    r1 = ptr32(0x3FF44040)   # noqa: F821  GPIO 32..39
    i = 0
    while i < n:
        a = int(r0[0])
        b = int(r1[0])
        p[i] = (((a >> 25) & 1) | ((a >> 26) & 2) | ((b & 3) << 2) | ((b & 0x1C) << 2) | ((b >> 0) & 0x80))
        i += 1


def main():
    setup_pins()
    buf = bytearray(N)
    print("     " + "  ".join("%9s" % n for n in NAMES))
    print("     " + "  ".join("%9s" % "wys% zm/s" for _ in NAMES))
    while True:
        t0 = time.ticks_us()
        capture(buf, N)
        dt = time.ticks_diff(time.ticks_us(), t0) / 1e6
        hi = [0] * 8
        ed = [0] * 8
        prev = buf[0]
        for v in buf:
            x = v ^ prev
            for k in range(8):
                if v >> k & 1:
                    hi[k] += 1
                if x >> k & 1:
                    ed[k] += 1
            prev = v
        print("     " + "  ".join("%3d %5d" % (100 * hi[k] // N, int(ed[k] / dt)) for k in range(8)))
        time.sleep_ms(500)


main()
