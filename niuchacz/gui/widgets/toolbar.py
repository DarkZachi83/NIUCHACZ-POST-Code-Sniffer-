"""Pasek narzędzi: wybór połączenia i producenta BIOS."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from niuchacz.app import event_bus as ev
from niuchacz.domain.enums import BiosVendor, ConnectionState, TransportKind
from niuchacz.gui import theme


def _kind_from_settings(value) -> TransportKind:
    try:
        return TransportKind(value)
    except ValueError:          # np. dawne "mock" (symulator usunięty)
        return TransportKind.TCP


class Toolbar(ttk.Frame):
    def __init__(self, master, bus: ev.EventBus, controller, on_report):
        super().__init__(master, padding=(8, 6))
        self.controller = controller
        settings = controller.settings

        self._kinds = list(TransportKind)
        ttk.Label(self, text="Połączenie:").pack(side="left")
        self.kind = ttk.Combobox(self, state="readonly", width=13, values=[k.label for k in self._kinds])
        self.kind.current(self._kinds.index(_kind_from_settings(settings.get("transport", "tcp"))))
        self.kind.pack(side="left", padx=(4, 10))

        self.button = ttk.Button(self, text="Połącz", command=self._toggle)
        self.button.pack(side="left", padx=(0, 6))
        ttk.Button(self, text="Raport", command=on_report).pack(side="left", padx=(0, 16))

        self._vendors = list(BiosVendor)
        ttk.Label(self, text="BIOS:").pack(side="left")
        self.vendor = ttk.Combobox(self, state="readonly", width=9, values=[v.label for v in self._vendors])
        self.vendor.current(self._vendors.index(BiosVendor(controller.vendor)))
        self.vendor.pack(side="left", padx=4)
        self.vendor.bind("<<ComboboxSelected>>",
                         lambda _e: controller.set_vendor(self._vendors[self.vendor.current()].value))

        self.state = tk.Label(self, text="● rozłączony", fg=theme.MUTED, font=theme.FONT_BOLD)
        self.state.pack(side="right")

        self._connected = False
        bus.subscribe(ev.CONNECTION, self._on_connection)

    def _selected_kind(self) -> TransportKind:
        return self._kinds[self.kind.current()]

    def _toggle(self) -> None:
        if self._connected:
            self.controller.disconnect()
            return
        self.controller.connect(self._selected_kind())

    def _on_connection(self, payload) -> None:
        state, detail = payload
        self._connected = state is ConnectionState.CONNECTED
        self.button.config(text="Rozłącz" if self._connected else "Połącz")
        color = {ConnectionState.CONNECTED: theme.OK, ConnectionState.ERROR: "#c0392b",
                 ConnectionState.CONNECTING: theme.HANG}.get(state, theme.MUTED)
        text = f"● {state.value}" + (f" – {detail}" if detail else "")
        self.state.config(text=text[:60], fg=color)
