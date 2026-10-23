"""Baner NIUCHACZA w lewej kolumnie okna."""
from __future__ import annotations

import tkinter as tk

from niuchacz.gui import theme


class Banner(tk.Label):
    def __init__(self, master, image):
        if image is not None:
            super().__init__(master, image=image, bd=0, bg=theme.DISPLAY_BG)
        else:  # brak pliku grafiki – sam napis
            super().__init__(master, text="NIUCHACZ", font=("Segoe UI", 28, "bold"),
                             fg="#ff8a1a", bg=theme.DISPLAY_BG, height=4)
