"""Testy warstwy tłumaczeń (wzór z Nornicy: testy/test_i18n.py).

Pilnują, żeby słowniki en/pl miały te same klucze i pola formatowania, żeby każdy
klucz użyty w kodzie istniał i żeby bazy kodów POST miały opisy w obu językach.
"""
import json
import re
import string
import unittest
from datetime import datetime
from pathlib import Path

from niuchacz import i18n
from niuchacz.i18n import LANGUAGES, localized, set_language, t

ROOT = Path(__file__).resolve().parents[1]
I18N_DIR = ROOT / "niuchacz" / "i18n"
CODES_DIR = ROOT / "data" / "post_codes"
POLISH = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")


def _dict(lang):
    return json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def _fields(text):
    return {f for _, f, _, _ in string.Formatter().parse(text) if f is not None}


class DictionariesTest(unittest.TestCase):
    def setUp(self):
        self.dicts = {lang: _dict(lang) for lang in LANGUAGES}
        self.base = self.dicts[i18n.DEFAULT_LANGUAGE]

    def test_same_keys(self):
        for lang, d in self.dicts.items():
            with self.subTest(lang=lang):
                self.assertEqual(set(), set(self.base) - set(d), "brakujące klucze")
                self.assertEqual(set(), set(d) - set(self.base), "nadmiarowe klucze")

    def test_same_format_fields(self):
        for lang, d in self.dicts.items():
            for key, text in self.base.items():
                with self.subTest(lang=lang, key=key):
                    self.assertEqual(_fields(text), _fields(d.get(key, "")))

    def test_no_empty_texts(self):
        for lang, d in self.dicts.items():
            for key, text in d.items():
                with self.subTest(lang=lang, key=key):
                    self.assertTrue(text.strip())

    def test_every_language_has_a_name(self):
        for lang in LANGUAGES:
            self.assertIn(f"lang.{lang}", self.base)

    def test_english_has_no_polish_letters(self):
        bad = [k for k, v in self.base.items() if POLISH.search(v) and not k.startswith("lang.")]
        self.assertEqual([], bad)

    def test_keys_used_in_code_exist(self):
        """t("klucz"...) z pełnym literałem oraz klucze w krotkach/słownikach ("led.clk" itp.)."""
        call = re.compile(r"""\bt\(\s*["']([a-z_]+\.[a-z0-9_]+)["']""")
        literal = re.compile(r"""["']((?:led|result|golden|history|stage|confidence)\.[a-z0-9_]+)["']""")
        missing = []
        for path in (ROOT / "niuchacz").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for key in set(call.findall(text)) | set(literal.findall(text)):
                if key not in self.base:
                    missing.append(f"{path.name}: {key}")
        self.assertEqual([], missing)


class TranslatorTest(unittest.TestCase):
    def tearDown(self):
        set_language("en")

    def test_fallbacks(self):
        self.assertEqual(i18n.DEFAULT_LANGUAGE, set_language("klingon"))
        self.assertEqual("no.such.key", t("no.such.key"))
        self.assertEqual("Ready. Choose a connection and click Connect.", t("status.ready"))
        set_language("pl")
        self.assertTrue(t("status.ready").startswith("Gotowy"))
        self.assertTrue(t("status.ready", lang="en").startswith("Ready"))

    def test_bad_format_does_not_raise(self):
        self.assertIn("{code}", t("display.code"))          # brak pól -> surowy tekst

    def test_localized(self):
        value = {"en": "Boot block", "pl": "Blok startowy"}
        set_language("pl")
        self.assertEqual("Blok startowy", localized(value))
        self.assertEqual("Boot block", localized(value, "en"))
        self.assertEqual("Boot block", localized(json.dumps(value), "en"))   # tak leży w SQLite
        self.assertEqual("tylko jeden język", localized("tylko jeden język", "en"))
        self.assertEqual("Boot block", localized({"en": "Boot block"}, "pl"))


class CodeDatabasesTest(unittest.TestCase):
    def test_entries_have_both_languages(self):
        missing = []
        for path in CODES_DIR.glob("*.json"):
            for e in json.loads(path.read_text(encoding="utf-8"))["entries"]:
                for field in ("stage", "fault", "check"):
                    value = e.get(field)
                    if not value:
                        continue
                    if not isinstance(value, dict) or set(LANGUAGES) - {k for k, v in value.items() if v}:
                        missing.append(f"{path.name} {e['code']} {field}")
        self.assertEqual([], missing)

    def test_wait_codes_are_marked(self):
        ami = json.loads((CODES_DIR / "ami.json").read_text(encoding="utf-8"))
        wait = {e["code"] for e in ami["entries"] if e.get("kind") == "wait"}
        self.assertEqual({"85", "87", "A9"}, wait)


class ReportLanguageTest(unittest.TestCase):
    def tearDown(self):
        set_language("en")

    def test_same_session_in_both_languages(self):
        from niuchacz.domain.models import SequenceItem
        from niuchacz.session.recorder import Session
        from niuchacz.session.report import ReportMeta, build_report

        s = Session(session_id=7, started_at=datetime(2026, 10, 23, 15, 8))
        s.items = [SequenceItem("D4", 0), SequenceItem("87", 10_370)]
        s.set_result("result.wait", code="87", stage={"en": "BIOS Setup open", "pl": "BIOS Setup otwarty"})
        stage = lambda c: ""
        en = build_report(s, "AMI", ReportMeta(), stage, "", datetime(2026, 1, 1), lang="en")
        pl = build_report(s, "AMI", ReportMeta(), stage, "", datetime(2026, 1, 1), lang="pl")
        self.assertIn("RESULT: WAITING FOR USER – code 87: BIOS Setup open", en)
        self.assertIn("POST SEQUENCE (2 codes)", en)
        self.assertIn("WYNIK: CZEKA NA UŻYTKOWNIKA – kod 87: BIOS Setup otwarty", pl)
        self.assertIsNone(POLISH.search(en))


if __name__ == "__main__":
    unittest.main()
