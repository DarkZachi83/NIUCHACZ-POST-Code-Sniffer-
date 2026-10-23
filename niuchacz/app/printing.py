"""Zapis raportu na dysk i wysłanie pliku .txt do drukarki systemowej."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class PrintError(OSError):
    pass


def save_text(path: Path, text: str) -> None:
    # BOM: Notatnik w każdej wersji Windows poprawnie pokaże polskie znaki
    Path(path).write_text(text, encoding="utf-8-sig", newline="\r\n" if os.name == "nt" else "\n")


def print_file(path: Path) -> None:
    """Windows: drukuje domyślnym programem dla .txt (Notatnik) na domyślnej drukarce."""
    path = Path(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path), "print")  # type: ignore[attr-defined]
        else:
            subprocess.run(["lpr", str(path)], check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PrintError(f"Nie udało się wydrukować: {exc}") from exc
