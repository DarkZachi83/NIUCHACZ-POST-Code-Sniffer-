# NIUCHACZ firmware – tryb demo: symulowany przebieg POST bez karty.
#
# Służy do testu łączności ESP32 -> Wi-Fi -> aplikacja, zanim sprzęt odczytu
# będzie gotowy. Włączenie: w config.py dopisz  DEMO_MODE = True
#
# Cykle na zmianę:
#   * poprawny start (Award): C0 C1 C3 C5 C7 CF ... FF
#   * zawieszenie na C1 (brak RAM) – aplikacja powinna wykryć zawieszenie
# Kolejność jak na karcie PC Analyzer: DIG1 = skrajna prawa cyfra, kod = dwie prawe cyfry
# (card_profile.json: display_order [3,2,1,0], code_digits [2,3]). DIG3, DIG4 puste.

import time

import config

_PAT = {
    "0": 0x3F, "1": 0x06, "2": 0x5B, "3": 0x4F, "4": 0x66, "5": 0x6D,
    "6": 0x7D, "7": 0x07, "8": 0x7F, "9": 0x6F, "A": 0x77, "B": 0x7C,
    "C": 0x39, "D": 0x5E, "E": 0x79, "F": 0x71, " ": 0x00,
}

OK_RUN = ("C0", "C1", "C3", "C5", "C7", "CF", "FF")
HANG_RUN = ("C0", "C1")

STEP_MS = 900      # czas wyświetlania jednego kodu
HOLD_MS = 9000     # ile trwa ostatni kod przed kolejnym cyklem


def _raw(ch):
    # kanał i = segment i (mapa a..g, dp jak w segment_map.json)
    p = _PAT.get(ch, 0)
    return (~p) & 0xFF if config.SEG_ACTIVE_LOW else p


def frame_for(code):
    return bytes((_raw(code[1]), _raw(code[0]), _raw(" "), _raw(" ")))


class Demo:
    def __init__(self, now):
        self.t0 = now
        self.cycle = 0

    def _seq(self):
        return OK_RUN if self.cycle % 2 == 0 else HANG_RUN

    def step(self, now):
        """Zwraca (bajty 4 cyfr, czy zaczął się nowy cykl = nowa sesja)."""
        seq = self._seq()
        el = time.ticks_diff(now, self.t0)
        idx = el // STEP_MS
        new_session = False
        if idx >= len(seq):
            if el >= len(seq) * STEP_MS + HOLD_MS:
                self.cycle += 1
                self.t0 = now
                seq = self._seq()
                idx = 0
                new_session = True
            else:
                idx = len(seq) - 1
        return frame_for(seq[idx]), new_session
