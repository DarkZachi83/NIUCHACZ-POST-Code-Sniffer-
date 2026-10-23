"""Duży wyświetlacz kodu w stylu 7-segmentowym (rysowany na Canvas)."""
from __future__ import annotations

import tkinter as tk

from niuchacz.app import event_bus as ev
from niuchacz.decoding.seven_segment import SEGMENTS, SevenSegmentDecoder
from niuchacz.gui import theme
from niuchacz.i18n import t

DW, DH, T, GAP = 58, 104, 11, 22   # szerokość/wysokość cyfry, grubość segmentu, odstęp


def _segment_polys(x: float, y: float) -> dict[str, list[float]]:
    """Wielokąty segmentów a..g z fazowanymi końcami."""
    h2 = DH / 2
    t2 = T / 2

    def horiz(cx0, cx1, cy):
        return [cx0, cy, cx0 + t2, cy - t2, cx1 - t2, cy - t2, cx1, cy, cx1 - t2, cy + t2, cx0 + t2, cy + t2]

    def vert(cx, cy0, cy1):
        return [cx, cy0, cx + t2, cy0 + t2, cx + t2, cy1 - t2, cx, cy1, cx - t2, cy1 - t2, cx - t2, cy0 + t2]

    l, r = x + t2, x + DW - t2
    return {
        "a": horiz(l + 2, r - 2, y + t2),
        "b": vert(r, y + t2 + 2, y + h2 - 2),
        "c": vert(r, y + h2 + 2, y + DH - t2 - 2),
        "d": horiz(l + 2, r - 2, y + DH - t2),
        "e": vert(l, y + h2 + 2, y + DH - t2 - 2),
        "f": vert(l, y + t2 + 2, y + h2 - 2),
        "g": horiz(l + 2, r - 2, y + h2),
    }


class CodeDisplay(tk.Frame):
    def __init__(self, master, bus: ev.EventBus, digits: int = 4, code_digits=(0, 1)):
        super().__init__(master, bg=theme.DISPLAY_BG, highlightthickness=3,
                         highlightbackground=theme.DISPLAY_BG)
        self.digits = digits
        self.code_digits = set(code_digits)
        width = 24 + digits * (DW + GAP) + 12
        self.canvas = tk.Canvas(self, width=width, height=DH + 40, bg=theme.DISPLAY_BG,
                                highlightthickness=0)
        self.canvas.pack(padx=8, pady=(8, 0))
        self.caption = tk.Label(self, text=t("display.waiting"), bg=theme.DISPLAY_BG,
                                fg=theme.MUTED, font=theme.FONT_UI)
        self.caption.pack(pady=(0, 8))
        self._items: list[dict[str, int]] = []
        self._draw_frame()
        bus.subscribe(ev.CODE, self._on_code)
        bus.subscribe(ev.HANG, self._on_hang)
        bus.subscribe(ev.SESSION, lambda _s: self._set_alert(False))

    def _draw_frame(self) -> None:
        for i in range(self.digits):
            x = 24 + i * (DW + GAP) + (8 if i >= 2 else 0)
            polys = _segment_polys(x, 18)
            ids = {seg: self.canvas.create_polygon(*pts, fill=theme.LED_OFF, outline="")
                   for seg, pts in polys.items()}
            ids["dp"] = self.canvas.create_oval(x + DW + 3, 18 + DH - 9, x + DW + 12, 18 + DH,
                                                fill=theme.LED_OFF, outline="")
            self._items.append(ids)

    def show(self, text: str) -> None:
        text = text.ljust(self.digits)[: self.digits]
        for i, ch in enumerate(text):
            pattern = SevenSegmentDecoder.encode_char(ch) if ch != "?" else 0x49  # "?" = trzy belki
            for bit, seg in enumerate(SEGMENTS):
                if seg in self._items[i]:
                    on = bool(pattern & (1 << bit))
                    self.canvas.itemconfigure(self._items[i][seg], fill=theme.LED_ON if on else theme.LED_OFF)

    def _on_code(self, change) -> None:
        self.show(change.display)
        self._set_alert(False)
        self.caption.config(text=t("display.code", code=change.code) if change.code else t("display.no_hex"),
                            fg=theme.MUTED)

    def _on_hang(self, hang) -> None:
        kind = getattr(hang, "kind", "stop")
        code = hang.code or "?"
        if kind == "wait":
            self._set_alert(False)
            self.caption.config(text=t("display.wait", code=code), fg=theme.OK)
        elif kind == "done":
            self._set_alert(False)
            self.caption.config(text=t("display.done", code=code), fg=theme.OK)
        else:
            self._set_alert(True)
            self.caption.config(text=t("display.stop", code=code, seconds=f"{hang.seconds:.0f}"), fg=theme.HANG)

    def _set_alert(self, on: bool) -> None:
        self.config(highlightbackground=theme.HANG if on else theme.DISPLAY_BG)
