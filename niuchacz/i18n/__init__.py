"""Warstwa tłumaczeń NIUCHACZA / NIUCHACZ translation layer.

Wzorowana na Nornicy (i18n/tlumacz.py). Zasady:
  * Teksty żyją w plikach en.json i pl.json obok tego modułu – nie w kodzie.
  * Napis powstaje w chwili wyświetlenia, nigdy przy wczytaniu modułu:
    stałe i zapisane stany (np. wynik sesji) przechowują KLUCZE i pola, nie gotowe zdania.
  * Bieżący język jest jeden, centralny i czytany przy każdym wywołaniu t().
    Funkcje, które muszą działać w konkretnym języku (raport), przyjmują `lang`.
  * Cofnięcia: nieznany język -> domyślny, brakujący klucz -> domyślny -> sam klucz.
    Błąd w polach formatowania daje surowy tekst i wpis w logu, a nie wyjątek u użytkownika.

Dodanie języka: skopiuj en.json do np. de.json, przetłumacz wartości, dopisz kod do LANGUAGES
oraz klucz "lang.de" w każdym pliku. Test tests/test_i18n.py pilnuje kompletności.
"""
from __future__ import annotations

import json
import locale
import logging
from pathlib import Path
from typing import Mapping, Optional

DIRECTORY = Path(__file__).resolve().parent
DEFAULT_LANGUAGE = "en"
LANGUAGES = ("en", "pl")

_log = logging.getLogger(__name__)
_dicts: dict[str, dict[str, str]] = {}
_current = DEFAULT_LANGUAGE


def _load(lang: str) -> dict[str, str]:
    """Wczytuje słownik języka (raz, potem z pamięci)."""
    if lang not in _dicts:
        path = DIRECTORY / f"{lang}.json"
        try:
            _dicts[lang] = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            _dicts[lang] = {}
    return _dicts[lang]


def reload() -> None:
    """Czyści pamięć słowników (przy edycji plików JSON i w testach)."""
    _dicts.clear()


def system_language() -> str:
    """Język systemu, jeśli go obsługujemy; inaczej domyślny."""
    try:
        code = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "").lower()
    except (ValueError, TypeError):
        code = ""
    if code.startswith(("pl", "polish")):
        return "pl"
    return DEFAULT_LANGUAGE


def set_language(lang: Optional[str]) -> str:
    """Ustawia bieżący język; pusty -> język systemu, nieznany -> domyślny. Zwraca ustawiony kod."""
    global _current
    if not lang:
        lang = system_language()
    _current = lang if lang in LANGUAGES else DEFAULT_LANGUAGE
    return _current


def current_language() -> str:
    return _current


def has_key(key: str) -> bool:
    return key in _load(DEFAULT_LANGUAGE)


def t(key: str, lang: Optional[str] = None, **fields) -> str:
    """Tekst dla klucza w bieżącym (albo podanym) języku, z opcjonalnymi polami {nazwa}."""
    lang = lang or _current
    text = _load(lang).get(key) or _load(DEFAULT_LANGUAGE).get(key) or key
    if not fields:
        return text
    try:
        return text.format(**fields)
    except (KeyError, IndexError, ValueError) as exc:
        _log.warning("Błąd formatowania klucza %r (%s): %s", key, lang, exc)
        return text


def localized(value, lang: Optional[str] = None) -> str:
    """Wybiera tekst z pola wielojęzycznego bazy kodów: {"en": ..., "pl": ...}.

    Przyjmuje też zwykły napis (wpis tylko w jednym języku) i napis JSON (tak pole leży w SQLite).
    Cofnięcia: bieżący język -> domyślny -> pierwszy niepusty -> "".
    """
    if value is None:
        return ""
    if isinstance(value, str):
        s = value.strip()
        if not s.startswith("{"):
            return value
        try:
            value = json.loads(s)
        except json.JSONDecodeError:
            return value
    if not isinstance(value, Mapping):
        return str(value)
    lang = lang or _current
    return (value.get(lang) or value.get(DEFAULT_LANGUAGE)
            or next((v for v in value.values() if v), ""))
