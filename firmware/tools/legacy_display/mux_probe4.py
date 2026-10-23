# NIUCHACZ – test filtrowania: czy z drgań da się odzyskać sygnał karty?
# Każde okno W próbek (ok. 0,73 us/próbka) -> dla każdej linii głos większości.
# Uruchom (F5) przy kodzie 0061 na karcie, kabel podłączony. Wymaga sampler.py.

import array
import machine
import micropython
import time

from sampler import setup_pins

N = 15000
W = 16          # próbek w oknie (~12 us)
MIN_RUN = 2     # minimalna długość odcinka w oknach


@micropython.viper
def capture(buf, n: int):
    p = ptr16(buf)
    r0 = ptr32(0x3FF4403C)
    r1 = ptr32(0x3FF44040)
    i = 0
    while i < n:
        a = r0[0]
        b = r1[0]
        p[i] = (((a >> 16) & 0x0F) | ((a >> 17) & 0x70)
                | (((a >> 26) & 3) << 8) | ((b & 3) << 10))
        i += 1


@micropython.viper
def majority(buf, out, n: int, w: int):
    # out[j] = dla każdego z 12 bitów: 1 gdy w oknie j przeważa stan wysoki
    p = ptr16(buf)
    q = ptr16(out)
    j = 0
    while j * w + w <= n:
        res = 0
        bit = 0
        while bit < 12:
            cnt = 0
            k = 0
            while k < w:
                cnt += (p[j * w + k] >> bit) & 1
                k += 1
            if cnt * 2 > w:
                res |= 1 << bit
            bit += 1
        q[j] = res
        j += 1


@micropython.viper
def balance(buf, n: int, bit: int) -> int:
    # ile próbek w stanie wysokim (do oceny, czy drgania są symetryczne)
    p = ptr16(buf)
    s = 0
    i = 0
    while i < n:
        s += (p[i] >> bit) & 1
        i += 1
    return s


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
    print("Próbek: %d w %d us (%.2f us/próbka), okno %d próbek = %.1f us" % (N, dt, us, W, W * us))
    print("Stan wysoki surowo [%]: " + " ".join(
        "%s=%d" % (nm, 100 * balance(buf, N, b) // N)
        for b, nm in enumerate(("k1", "k2", "k3", "k4", "k5", "k6", "k7", "-", "D1", "D2", "D3", "D4")) if nm != "-"))

    nw = N // W
    out = array.array("H", bytes(2 * nw))
    majority(buf, out, N, W)
    del buf

    total = {}
    runs = []
    nruns = 0
    cur = out[0] & 0xF7F
    length = 0
    for v in out:
        v &= 0xF7F
        if v == cur:
            length += 1
            continue
        if length >= MIN_RUN:
            total[cur] = total.get(cur, 0) + length
            nruns += 1
            if len(runs) < 40:
                runs.append((cur, length))
        cur = v
        length = 1
    if length >= MIN_RUN:
        total[cur] = total.get(cur, 0) + length
        nruns += 1
    print("Po filtrze: odcinków %d, średnio %.0f us" % (nruns, dt / max(nruns, 1)))
    print("Najczęstsze stany (DIG1..4 | k1..k7, 0 = świeci) [% okien]:")
    for s in sorted(total, key=lambda x: -total[x])[:12]:
        print("  DIG %s | SEG %s  %5.1f%%" % (bits(s >> 8, 4), bits(s, 7), 100 * total[s] / nw))
    print("Przebieg po filtrze (pierwsze 40 odcinków): czas_us DIG1..4 k1..k7")
    for s, l in runs:
        print("  %6.0f  %s  %s" % (l * W * us, bits(s >> 8, 4), bits(s, 7)))


main()
