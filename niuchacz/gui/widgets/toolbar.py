"""Pasek narzędzi: wybór połączenia i producenta BIOS."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from niuchacz.app import event_bus as ev
from niuchacz.domain.enums import BiosVendor, ConnectionState, TransportKind
from niuchacz.gui import theme
from niuchacz.i18n import localized, t


def _kind_from_settings(value) -> TransportKind:
    try:
        return TransportKind(value)
    except ValueError:          # np. dawne "mock" (symulator usunięty)
        return TransportKind.TCP


class Toolbar(ttk.Frame):
    def __init__(self, master, bus: ev.EventBus, controller, on_report):
        super().__init__(master, padding=(8, 6))
        self.controller = controller
        self.bus = bus
        settings = controller.settings

        self._kinds = list(TransportKind)
        ttk.Label(self, text=t("toolbar.connection")).pack(side="left")
        self.kind = ttk.Combobox(self, state="readonly", width=13, values=[k.label for k in self._kinds])
        self.kind.current(self._kinds.index(_kind_from_settings(settings.get("transport", "tcp"))))
        self.kind.pack(side="left", padx=(4, 10))

        self.button = ttk.Button(self, text=t("toolbar.connect"), command=self._toggle)
        self.button.pack(side="left", padx=(0, 6))
        ttk.Button(self, text=t("toolbar.report"), command=on_report).pack(side="left", padx=(0, 16))

        # producent + generacja BIOS-u – lista z plików bazy kodów (data/post_codes/*.json)
        self._vendors = [p["vendor"] for p in controller.bios_profiles()] or [v.value for v in BiosVendor]
        if controller.vendor not in self._vendors:
            self._vendors.append(controller.vendor)
        ttk.Label(self, text="BIOS:").pack(side="left")
        self.vendor = ttk.Combobox(self, state="readonly", width=22,
                                   values=[controller.vendor_label(v) for v in self._vendors])
        self.vendor.current(self._vendors.index(controller.vendor))
        self.vendor.pack(side="left", padx=4)
        self.vendor.bind("<<ComboboxSelected>>", self._on_vendor)

        self.state = tk.Label(self, text="● " + t("conn.disconnected"), fg=theme.MUTED, font=theme.FONT_BOLD)
        self.state.pack(side="right")

        self._connected = False
        bus.subscribe(ev.CONNECTION, self._on_connection)
        if controller.is_connected:   # przebudowa okna przy otwartym połączeniu
            self._on_connection((ConnectionState.CONNECTED, controller.transport_name))

    def _on_vendor(self, _event=None) -> None:
        vendor = self._vendors[self.vendor.current()]
        self.controller.set_vendor(vendor)
        hint = self.controller.diagnosis.repository.profile(vendor).get("recognise")
        if hint:
            self.bus.publish(ev.STATUS, localized(hint))

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
        self.button.config(text=t("toolbar.disconnect") if self._connected else t("toolbar.connect"))
        color = {ConnectionState.CONNECTED: theme.OK, ConnectionState.ERROR: "#c0392b",
                 ConnectionState.CONNECTING: theme.HANG}.get(state, theme.MUTED)
        text = "● " + t(f"conn.{state.value}") + (f" – {detail}" if detail else "")
        self.state.config(text=text[:60], fg=color)
