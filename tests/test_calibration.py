"""Kreator kalibracji na danych z prawdziwych pomiarów."""
import random
import unittest

from niuchacz.decoding.calibration import Sample, solve
from niuchacz.decoding.code_assembler import CardProfile
from niuchacz.decoding.seven_segment import SegmentMap, SevenSegmentDecoder


def raw(lit_channels):
    b = 0xFF
    for ch in lit_channels:
        b &= ~(1 << (ch - 1))
    return b & 0xFF


class CalibrationTest(unittest.TestCase):
    def test_de24_measurement_plus_second_reading(self):
        # pomiar 18.10.2026 (dE24): DIG1..DIG4
        s1 = Sample((raw({2, 3, 6, 7}), raw({1, 2, 4, 5, 7}), raw({1, 4, 5, 6, 7}), raw({2, 3, 4, 5, 7})), "DE24")
        sols = solve([s1])
        self.assertTrue(any(s.channel_to_segment[:7] == tuple("abcdefg") and s.display_order == (3, 2, 1, 0)
                            and s.active_low for s in sols))

    def test_random_wiring_is_recovered(self):
        rnd = random.Random(7)
        segs = list("abcdefg")
        rnd.shuffle(segs)
        smap = SegmentMap(channel_to_segment=segs + ["dp"], active_low=True)
        prof = CardProfile(digits=4, display_order=(1, 3, 0, 2))

        def sample(text):
            lines = prof.to_lines(list(text))
            return Sample(tuple(smap.canonical_to_raw(SevenSegmentDecoder.encode_char(c)) for c in lines), text)

        sols = solve([sample("8584"), sample("D427"), sample("C3F0")])
        self.assertEqual(len(sols), 1)
        self.assertEqual(list(sols[0].channel_to_segment), segs + ["dp"])
        self.assertEqual(sols[0].display_order, (1, 3, 0, 2))
        self.assertTrue(sols[0].active_low)

    def test_auto_rank_from_post_frames(self):
        from niuchacz.decoding.calibration import auto_rank
        smap = SegmentMap(channel_to_segment=["d", "a", "b", "e", "g", "c", "f", "dp"], active_low=True)
        rnd = random.Random(3)
        codes = ["D8", "D4", "8B", "24", "2C", "33", "37", "75", "78", "84", "85", "87", "8C", "8D", "E8", "AA"]

        def fr(text):
            return tuple(smap.canonical_to_raw(SevenSegmentDecoder.encode_char(c)) for c in text)

        frames = [fr(rnd.choice(codes) + rnd.choice(codes)) for _ in range(200)]
        frames += [tuple(rnd.randrange(128) for _ in range(4)) for _ in range(20)]   # śmieci z przejść
        ranked = auto_rank(frames, [Sample(fr("8785"), "8785")])
        self.assertEqual(list(ranked[0][1].channel_to_segment), smap.channel_to_segment)
        self.assertGreater(ranked[0][0] - ranked[1][0], 0.02)

    def test_impossible_reading(self):
        self.assertEqual(solve([Sample((0xFF, 0xFF, 0xFF, 0x00), "8888")]), [])


if __name__ == "__main__":
    unittest.main()
