# NIUCHACZ – surowy stan linii CYFR i SEGMENTÓW (bez żadnego filtrowania).
# Uruchom w Thonny (F5). Pokazuje, jak często występuje każdy układ linii DIG1..DIG4
# oraz jak często każdy kanał segmentu jest w stanie niskim (0 = "świeci").
# Wymaga sampler.py na ESP32.

import array
import micropython
import time

from sampler import setup_pins

N = 15000
ROUNDS = 8


@micropython.viper
def capture(buf, n: int):
    p = ptr16(buf)
    r0 = ptr32(0x3FF4403C)
    r1 = ptr32(0x3FF44040)
    i = 0
    while i < n:
        a = r0[0]
        b = r1[0]
        p[i] = (((a >> 16) & 0x0F) | ((a >> 17) & 0x70) | ((a >> 18) & 0x80)
                | (((a >> 26) & 3) << 8) | ((b & 3) << 10))
        i += 1


def main():
    setup_pins()
    buf = array.array("H", bytes(2 * N))
    dig = [0] * 16
    low = [0] * 8
    total = 0
    for _ in range(ROUNDS):
        capture(buf, N)
        for v in buf:
            dig[(v >> 8) & 0x0F] += 1
            s = v & 0xFF
            for k in range(8):
                if not (s >> k) & 1:
                    low[k] += 1
        total += N
        time.sleep_ms(7)
    print("Próbek:", total)
    print("Linie cyfr DIG1..DIG4 (1 = aktywna)   udział")
    for m in range(16):
        if dig[m]:
            print("   %s%s%s%s                          %5.1f%%" % (
                m & 1, (m >> 1) & 1, (m >> 2) & 1, (m >> 3) & 1, 100 * dig[m] / total))
    print("Kanały segmentów 1..8: jak często stan niski (0 = świeci)")
    print("   " + "  ".join("k%d:%3d%%" % (k + 1, 100 * low[k] // total) for k in range(8)))


main()
