# NIUCHACZ – test samego pudełka (taśma DB25 ODPIĘTA, karta niepotrzebna).
# Program prowadzi krok po kroku. Przewodem z zacisku 3V3 dotykasz pinów 1–7
# gniazda DB25 w pudełku. Dotknięty kanał ma spaść do 0 %, pozostałe zostają na ok. 100 %.

import array
import micropython
import time

from sampler import setup_pins

N = 6000
_buf = None


@micropython.viper
def capture(buf, n: int):
    p = ptr16(buf)
    r0 = ptr32(0x3FF4403C)
    i = 0
    while i < n:
        a = r0[0]
        p[i] = ((a >> 16) & 0x0F) | ((a >> 17) & 0x70)
        i += 1


def low_percent():
    global _buf
    if _buf is None:
        _buf = array.array("H", bytes(2 * N))
    buf = _buf
    capture(buf, N)
    low = [0] * 7
    for v in buf:
        for k in range(7):
            if not (v >> k) & 1:
                low[k] += 1
    return [100 * x // N for x in low]


def fmt(row):
    return "  ".join("%3d" % x for x in row)


def main():
    import gc
    gc.collect()
    setup_pins()
    print("k = kanał, wartość = % czasu w stanie 'świeci' (powinno być ok. 100, dotknięty = 0)")
    print("           k1   k2   k3   k4   k5   k6   k7")
    rows = [("nic", low_percent())]
    print("nic        " + fmt(rows[0][1]))
    for pin in range(1, 8):
        input("Przewód 3V3 na DB25 pin %d (gniazdo w pudełku), potem Enter, trzymaj 1 s... " % pin)
        r = low_percent()
        rows.append(("pin %d" % pin, r))
        print("pin %d      " % pin + fmt(r))
    print()
    print("PODSUMOWANIE      k1   k2   k3   k4   k5   k6   k7")
    bad = []
    for i, (name, r) in enumerate(rows):
        print("%-14s  %s" % (name, fmt(r)))
        for k in range(7):
            expect_low = (i == 0) or (k != i - 1)
            ok = r[k] >= 90 if expect_low else r[k] <= 10
            if not ok:
                bad.append("%s: k%d = %d%%" % (name, k + 1, r[k]))
    print()
    print("WSZYSTKO OK - pudełko sprawne" if not bad else "NIEZGODNOŚCI:\n  " + "\n  ".join(bad))


main()
