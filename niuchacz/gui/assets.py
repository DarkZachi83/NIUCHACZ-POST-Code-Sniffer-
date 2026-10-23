"""Grafika programu: ikona okna (wszystkie okna dziedziczą) i baner z jamnikiem."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

ICON_ICO = "niuchacz.ico"
ICON_PNGS = ("icon_256.png", "icon_64.png", "icon_32.png", "icon_16.png")
BANNER = "banner.png"


class Assets:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self._images: list[tk.PhotoImage] = []   # referencje, inaczej tkinter zgubi obrazy

    def apply_icon(self, root: tk.Tk) -> None:
        """Ikona na pasku tytułu i pasku zadań; default=True obejmuje też okna dialogowe."""
        try:
            photos = [tk.PhotoImage(file=str(self.dir / name)) for name in ICON_PNGS
                      if (self.dir / name).exists()]
            if photos:
                self._images += photos
                root.iconphoto(True, *photos)
            if os.name == "nt" and (self.dir / ICON_ICO).exists():
                root.iconbitmap(default=str(self.dir / ICON_ICO))
        except tk.TclError:
            log.warning("Nie udało się ustawić ikony programu", exc_info=True)

    def banner(self) -> Optional[tk.PhotoImage]:
        path = self.dir / BANNER
        if not path.exists():
            return None
        try:
            img = tk.PhotoImage(file=str(path))
        except tk.TclError:
            log.warning("Nie udało się wczytać banera", exc_info=True)
            return None
        self._images.append(img)
        return img
