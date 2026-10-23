# NIUCHACZ – szybki pomiar multipleksu (viper, ok. 1 us/próbka).
# Uruchom w Thonny (F5) przy stałym kodzie na wyświetlaczu karty.
# Wymaga sampler.py na ESP32 (setup_pins).
#
# Pokazuje:
#   * czas próbkowania i częstotliwość multipleksu,
#   * jak często aktywna jest każda kombinacja linii cyfr DIG1-4,
#   * dla każdej cyfry: wzór segmentów (kanały 1-7), które świecą.

import array
import machine
import micropython
import time

from sampler import setup_pins

N = 15000   # 15000 próbek x 2 bajty = 30 kB RAM


@micropython.viper
def capture(buf, n: int):
    p = ptr16(buf)
    r0 = ptr32(0x3FF4403C)   # GPIO_IN_REG  (GPIO 0-31)
    r1 = ptr32(0x3FF44040)   # GPIO_IN1_REG (GPIO 32-39)
    i = 0
    while i < n:
        a = r0[0]
        b = r1[0]
        # bity 0-7: kanały 1-8 (GPIO 16,17,18,19,21,22,23,25)
        # bity 8-11: DIG1-4 (GPIO 26,27,32,33)
        # bity 12-15: CLK, IRDY, FRAME, RST (GPIO 34,35,36,39)
        p[i] = (((a >> 16) & 0x0F) | ((a >> 17) & 0x70) | ((a >> 18) & 0x80)
                | (((a >> 26) & 3) << 8) | ((b & 3) << 10)
                | (((b >> 2) & 7) << 12) | (((b >> 7) & 1) << 15))
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

    # wypełnienie linii
    names = ("k1", "k2", "k3", "k4", "k5", "k6", "k7", "k8",
             "DIG1", "DIG2", "DIG3", "DIG4", "CLK", "IRDY", "FRAME", "RST")
    highs = [0] * 16
    for v in buf:
        for k in range(16):
            if v & (1 << k):
                highs[k] += 1
    print("Stan wysoki [%]:")
    print("  " + "  ".join("%s=%d" % (names[k], 100 * highs[k] // N) for k in range(16)))

    # kombinacje cyfr i częstotliwość
    combos = {}
    rises = 0
    prev = 0
    for v in buf:
        d = (v >> 8) & 0xF
        combos[d] = combos.get(d, 0) + 1
        if d == 1 and prev != 1:
            rises += 1
        prev = d
    print("Kombinacje DIG (kolejność DIG1..DIG4) [% czasu]:")
    for d in sorted(combos, key=lambda x: -combos[x]):
        print("  %s  %5.1f%%" % (bits(d, 4), 100 * combos[d] / N))
    if rises:
        print("Multipleks: ok. %d Hz (wejść w samą DIG1: %d)" % (rises * 1000000 // dt, rises))

    # wzór segmentów dla każdej pojedynczej cyfry (pomijamy 3 próbki po zmianie)
    print("Segmenty dla cyfr (kanały 1-7, 1 = linia wysoka; segmenty aktywne stanem niskim):")
    for j in range(4):
        want = 1 << j
        pats = {}
        stable = 0
        prev = -1
        for v in buf:
            d = (v >> 8) & 0xF
            stable = stable + 1 if d == prev else 0
            prev = d
            if d == want and stable >= 3:
                s = v & 0x7F
                pats[s] = pats.get(s, 0) + 1
        tot = sum(pats.values())
        if not tot:
            print("  DIG%d: brak próbek" % (j + 1))
            continue
        top = sorted(pats, key=lambda x: -pats[x])[:3]
        desc = ", ".join("%s (%d%%)" % (bits(s, 7), 100 * pats[s] // tot) for s in top)
        lit = [str(k + 1) for k in range(7) if not top[0] & (1 << k)]
        print("  DIG%d: %s  -> świecą kanały: %s" % (j + 1, desc, ",".join(lit) or "żaden"))


main()
