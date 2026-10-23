# NIUCHACZ – zapis przebiegu multipleksu w czasie (viper, ok. 1 us/próbka).
# Uruchom w Thonny (F5) przy stałym kodzie na wyświetlaczu (najlepiej 0061).
# Wymaga sampler.py na ESP32.
#
# Wypisuje:
#   1. najczęstsze stany (linie cyfr + segmenty) i ich udział w czasie,
#   2. pierwsze 60 odcinków przebiegu: czas trwania, linie DIG1-4, segmenty k1-k7.
# Krótkie zakłócenia (< 3 próbek) są pomijane.

import array
import machine
import micropython
import time

from sampler import setup_pins

N = 15000
MIN_RUN = 3


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


def bits(v, n):
    return "".join("1" if v & (1 << k) else "0" for k in range(n))


def main():
    setup_pins()
    buf = array.array("H", bytes(2 * N))
    st = machine.disable_irq()
    t0 = time.ticks_us()
    capture(buf, N)
    dt = time.ticks_diff(time.ticks_us(), t0)
    machine.enable_irq(st)
    us = dt / N
    print("Próbek: %d w %d us (%.2f us/próbka)" % (N, dt, us))

    # odcinki stałego stanu (bez kanału 8) – liczone na bieżąco, bez listy wszystkich
    total = {}
    runs = []
    nruns = 0
    cur = buf[0] & 0xF7F
    length = 0
    for v in buf:
        v &= 0xF7F
        if v == cur:
            length += 1
            continue
        if length >= MIN_RUN:
            total[cur] = total.get(cur, 0) + length
            nruns += 1
            if len(runs) < 60:
                runs.append((cur, length))
        cur = v
        length = 1
    if length >= MIN_RUN:
        total[cur] = total.get(cur, 0) + length
        nruns += 1
    print("Odcinków (>= %d próbek): %d  -> średnio %.1f us na odcinek" % (MIN_RUN, nruns, dt / max(nruns, 1)))
    print("Najczęstsze stany  (DIG1..4 | segmenty k1..k7, 0 = świeci)  [% czasu]:")
    for s in sorted(total, key=lambda x: -total[x])[:16]:
        print("  DIG %s | SEG %s   %5.1f%%" % (bits(s >> 8, 4), bits(s, 7), 100 * total[s] / N))

    print("Przebieg (pierwsze 60 odcinków):  czas_us  DIG1..4  k1..k7")
    for s, l in runs[:60]:
        print("  %6.1f  %s  %s" % (l * us, bits(s >> 8, 4), bits(s, 7)))


main()
