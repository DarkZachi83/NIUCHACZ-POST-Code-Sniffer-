# NIUCHACZ – co naprawdę jest na liniach segmentów w czasie KAŻDEJ cyfry.
# Uruchom w Thonny (F5), gdy karta pokazuje STAŁY napis (np. przy oczekiwaniu na F1).
# Zapisz, co dokładnie widzisz na karcie, i wklej wynik.
#
# Dla każdej linii DIG1..DIG4 wypisuje stany segmentów, które pojawiały się w czasie
# tej cyfry: udział w czasie, najdłuższy ciągły odcinek i odczytany znak.
# Wymaga sampler.py na ESP32. Zbiera 8 paczek po ok. 11 ms (różne fazy multipleksu).

import array
import micropython
import time

from sampler import setup_pins

N = 15000
ROUNDS = 8

# segmenty a..g = bity 0..6 (kanały 1..7), 1 = świeci
_CH = {0x3F: "0", 0x06: "1", 0x5B: "2", 0x4F: "3", 0x66: "4", 0x6D: "5", 0x7D: "6",
       0x07: "7", 0x7F: "8", 0x6F: "9", 0x77: "A", 0x7C: "b", 0x39: "C", 0x5E: "d",
       0x79: "E", 0x71: "F", 0x00: " ", 0x40: "-"}


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
    # stats[dig][seg] = [suma_próbek, najdłuższy_odcinek, liczba_odcinków]
    stats = [{}, {}, {}, {}]
    total = 0
    us_total = 0
    for _ in range(ROUNDS):
        t0 = time.ticks_us()
        capture(buf, N)
        us_total += time.ticks_diff(time.ticks_us(), t0)
        total += N
        prev = buf[0]
        run = 1
        for i in range(1, N + 1):
            v = buf[i] if i < N else 0xFFFF
            if v == prev:
                run += 1
                continue
            dm = (prev >> 8) & 0x0F
            d = {1: 0, 2: 1, 4: 2, 8: 3}.get(dm, -1)
            if d >= 0:
                seg = (~prev) & 0x7F          # 1 = świeci
                s = stats[d].get(seg)
                if s is None:
                    stats[d][seg] = [run, run, 1]
                else:
                    s[0] += run
                    if run > s[1]:
                        s[1] = run
                    s[2] += 1
            prev = v
            run = 1
        time.sleep_ms(7)   # kolejna paczka w innej fazie multipleksu
    us_per = us_total / total
    print("Próbek: %d, %.2f us/próbka" % (total, us_per))
    print("DIG  znak  segmenty a..g (1=świeci)  udział  najdłuższy[us]  odcinków")
    for d in range(4):
        items = sorted(stats[d].items(), key=lambda kv: -kv[1][0])
        dig_sum = sum(v[0] for _, v in items) or 1
        for seg, (cnt, longest, nruns) in items[:5]:
            pat = "".join("1" if seg & (1 << k) else "0" for k in range(7))
            print("DIG%d   %s    %s               %5.1f%%  %9.0f  %6d" % (
                d + 1, _CH.get(seg, "?"), pat, 100 * cnt / dig_sum, longest * us_per, nruns))
        print()


main()
