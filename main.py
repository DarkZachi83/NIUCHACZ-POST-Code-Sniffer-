"""NIUCHACZ – punkt startowy.

main.py tylko składa obiekty (konfiguracja -> baza -> kontroler -> GUI).
Logika biznesowa żyje w pakiecie niuchacz/, GUI w niuchacz/gui/.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from niuchacz.app.config import ConfigStore
from niuchacz.app.controller import AppController
from niuchacz.app.event_bus import EventBus
from niuchacz.i18n import LANGUAGES, set_language
from niuchacz.knowledge.diagnosis_service import DiagnosisService
from niuchacz.knowledge.repository import CodeRepository
from niuchacz.transport.factory import create_transport

ROOT = Path(__file__).resolve().parent
PATHS = {
    "config": ROOT / "config",
    "codes": ROOT / "data" / "post_codes",
    "db": ROOT / "data" / "niuchacz.db",
    "golden": ROOT / "data" / "golden_runs",
    "reports": ROOT / "reports",
    "assets": ROOT / "assets",
}


def build_controller(lang: str | None = None) -> tuple[AppController, EventBus]:
    """Złożenie warstw bez GUI – używane też w testach.

    Język: argument `lang` (np. z --lang) > ustawienie "language" > język systemu."""
    config = ConfigStore(PATHS["config"])
    settings = config.load_settings()
    if lang:
        settings["language"] = lang
        config.save_settings(settings)
    set_language(settings.get("language"))
    repository = CodeRepository(PATHS["db"])
    repository.import_directory(PATHS["codes"])
    bus = EventBus()
    controller = AppController(
        bus=bus,
        config=config,
        diagnosis=DiagnosisService(repository),
        transport_factory=create_transport,
        segment_map=config.load_segment_map(),
        profile=config.load_card_profile(),
    )
    controller.reports_dir = PATHS["reports"]
    return controller, bus


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NIUCHACZ – POST code logger")
    parser.add_argument("--lang", choices=LANGUAGES, help="language / język (en, pl)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for key in ("golden", "reports"):
        PATHS[key].mkdir(parents=True, exist_ok=True)

    import tkinter as tk  # import dopiero tutaj: logika działa bez tkintera
    from niuchacz.gui.main_window import MainWindow

    controller, bus = build_controller(args.lang)
    root = tk.Tk()
    MainWindow(root, controller, bus, PATHS)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
