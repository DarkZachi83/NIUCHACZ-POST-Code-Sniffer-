"""Most między wątkiem czytającym a tkinterem.

Wątek czytający wrzuca zdarzenia do kolejki kontrolera; tutaj co POLL_MS
kontroler opróżnia ją w wątku GUI. To jedyne miejsce styku wątków z tkinterem.
"""
from __future__ import annotations

import tkinter as tk

POLL_MS = 50


class GuiAdapter:
    def __init__(self, root: tk.Tk, controller):
        self.root = root
        self.controller = controller
        self._job = None

    def start(self) -> None:
        self._tick()

    def stop(self) -> None:
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None

    def _tick(self) -> None:
        self.controller.pump()
        self._job = self.root.after(POLL_MS, self._tick)
