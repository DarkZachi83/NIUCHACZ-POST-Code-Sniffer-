"""Wczytywanie i zapis plików konfiguracyjnych z katalogu config/."""
from __future__ import annotations

import json
from pathlib import Path

from niuchacz.decoding.code_assembler import CardProfile
from niuchacz.decoding.seven_segment import SegmentMap

DEFAULT_SETTINGS = {
    "transport": "tcp",
    "tcp": {"host": "192.168.4.1", "port": 7080},
    "serial": {"port": "COM3", "baud": 115200},
    "bios_vendor": "award",
    "board": "",
    "hang_seconds": 15,
    "debounce_ms": 16,
    "report_auto_open": True,
    "technician": "",
    "language": "",          # "" = język systemu (pl -> polski, reszta -> angielski)
}


class ConfigStore:
    def __init__(self, config_dir: Path):
        self.dir = Path(config_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _read(self, name: str, default: dict) -> dict:
        path = self.dir / name
        if not path.exists():
            return dict(default)
        data = json.loads(path.read_text(encoding="utf-8"))
        return {**default, **data}

    def _write(self, name: str, data: dict) -> None:
        (self.dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_settings(self) -> dict:
        return self._read("settings.json", DEFAULT_SETTINGS)

    def save_settings(self, settings: dict) -> None:
        self._write("settings.json", settings)

    def load_segment_map(self) -> SegmentMap:
        return SegmentMap.from_dict(self._read("segment_map.json", SegmentMap().to_dict()))

    def save_segment_map(self, segment_map: SegmentMap) -> None:
        self._write("segment_map.json", segment_map.to_dict())

    def load_card_profile(self) -> CardProfile:
        return CardProfile.from_dict(self._read("card_profile.json", {}))

    def save_display_order(self, display_order) -> None:
        """Zapisuje kolejność cyfr z kalibracji, zostawiając resztę card_profile.json."""
        data = self._read("card_profile.json", {})
        data["display_order"] = list(display_order)
        self._write("card_profile.json", data)
