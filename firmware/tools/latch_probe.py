# NIUCHACZ – podgląd kodu z zatrzasku 74LCX374 (Q0–Q7 -> DB25 1–8).
# Uruchom w Thonny (F5). Wersja 2 (z kolumną 'surowo'). Co 0,5 s wypisuje bajt: hex, bity Q7..Q0 i ile zmian złapano.
# Porównaj z lewą parą cyfr na karcie. Stop: Ctrl+C.

import time
import machine

from sampler import setup_pins, latch_byte, latch_window, LATCH_SAMPLES, LATCH_QUIET, LATCH_MAX, LATCH_BUF, build_remap

setup_pins()
remap = build_remap()
vals = bytearray(LATCH_BUF)
import array
idx = array.array("I", bytes(4 * LATCH_BUF))
act = bytearray(2)
last = -1
print("kod   Q7..Q0     zmian w 0,5 s   ostatnie kody")
while True:
    seen = []
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 500:
        n = latch_window(LATCH_SAMPLES, LATCH_QUIET, LATCH_MAX, last, vals, idx, LATCH_BUF, act)
        for k in range(n):
            seen.append(remap[vals[k]])
        if n:
            last = vals[n - 1]
    raw = latch_byte(machine.mem32[0x3FF4403C])
    cur = remap[raw]
    bits = "".join("1" if cur & (1 << b) else "0" for b in range(7, -1, -1))
    tail = " ".join("%02X" % v for v in seen[-8:])
    print(" %02X   %s %s   %3d            %s   (surowo %02X)" % (cur, bits[:4], bits[4:], len(seen), tail, raw))
