"""Panel diod karty pod wyświetlaczem: CLK, IRDY, FRAME (aktywność) i RESET (poziom)."""
from __future__ import annotations

import tkinter as tk

from niuchacz.app import event_bus as ev
from niuchacz.gui import theme

_LEDS = (("clk", "CLK", "zegar"),
         ("irdy", "IRDY", "transfer PCI"),
         ("frame", "FRAME", "cykl PCI"),
         ("rst", "RESET", "płyta w resecie"))


class LedPanel(tk.Frame):
    """Rząd czterech diod w kolorystyce wyświetlacza – jak na karcie."""

    def __init__(self, master, bus: ev.EventBus):
        super().__init__(master, bg=theme.DISPLAY_BG, padx=8, pady=8)
        self._dots: dict[str, tuple[tk.Canvas, int]] = {}
        for col, (key, name, hint) in enumerate(_LEDS):
            self.columnconfigure(col, weight=1, uniform="led")
            cell = tk.Frame(self, bg=theme.DISPLAY_BG)
            cell.grid(row=0, column=col, sticky="n")
            top = tk.Frame(cell, bg=theme.DISPLAY_BG)
            top.pack()
            c = tk.Canvas(top, width=16, height=16, bg=theme.DISPLAY_BG, highlightthickness=0)
            dot = c.create_oval(2, 2, 14, 14, fill=theme.LED_OFF, outline="")
            c.pack(side="left", padx=(0, 4))
            tk.Label(top, text=name, bg=theme.DISPLAY_BG, fg="#e8e8e8", font=theme.FONT_BOLD).pack(side="left")
            tk.Label(cell, text=hint, bg=theme.DISPLAY_BG, fg=theme.MUTED, font=theme.FONT_SMALL).pack()
            self._dots[key] = (c, dot)
        bus.subscribe(ev.LEDS, self._on_leds)

    def _on_leds(self, state) -> None:
        for key, (canvas, dot) in self._dots.items():
            canvas.itemconfigure(dot, fill=theme.LED_ON if getattr(state, key) else theme.LED_OFF)
