# NIUCHACZ – skrypt pomiarowy (uruchom w Thonny PRZED wgraniem main.py).
#
# Mierzy przez ~1 s, jak często każda z 16 linii jest w stanie wysokim.
# Na tej podstawie ustalisz:
#   * linie cyfr DIG1-4: aktywne ok. 25% czasu -> polaryzacja (DIG_ACTIVE_LOW)
#   * linie segmentów: zmieniają się zależnie od kodu na wyświetlaczu
#   * CLK/IRDY/FRAME: wartości pośrednie = sygnał przełącza się (aktywny)
#   * częstotliwość multipleksu (liczba przejść DIG1 w oknie)

import machine
import time

from sampler import setup_pins, GPIO_IN_REG, GPIO_IN1_REG

NAMES = ("seg1/16", "seg2/17", "seg3/18", "seg4/19", "seg5/21", "seg6/22", "seg7/23", "seg8/25",
         "DIG1/26", "DIG2/27", "DIG3/32", "DIG4/33", "CLK/34", "IRDY/35", "FRAME/36", "RST/39")
BITS0 = (16, 17, 18, 19, 21, 22, 23, 25, 26, 27)   # z GPIO_IN
BITS1 = (0, 1, 2, 3, 4, 7)                          # z GPIO_IN1 (32,33,34,35,36,39)


def probe(duration_ms=1000):
    setup_pins()
    mem = machine.mem32
    highs = [0] * 16
    edges_dig1 = 0
    prev_dig1 = 0
    n = 0
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < duration_ms:
        a = mem[GPIO_IN_REG]
        b = mem[GPIO_IN1_REG]
        for i, bit in enumerate(BITS0):
            if a & (1 << bit):
                highs[i] += 1
        for j, bit in enumerate(BITS1):
            if b & (1 << bit):
                highs[10 + j] += 1
        d1 = (a >> 26) & 1
        if d1 != prev_dig1:
            edges_dig1 += 1
            prev_dig1 = d1
        n += 1
    print("Próbek: %d w %d ms (%.1f us/próbka)" % (n, duration_ms, duration_ms * 1000 / n))
    print("Przejść DIG1: %d -> multipleks ok. %d Hz" % (edges_dig1, edges_dig1 // 2 * 1000 // duration_ms))
    for name, h in zip(NAMES, highs):
        pct = 100 * h / n
        bar = "#" * int(pct / 4)
        print("%-9s %5.1f%%  %s" % (name, pct, bar))


probe()
print("Uwaga: CLK/IRDY/FRAME/RST bez podłączonych diod pokazują przypadkowe wartości.")
