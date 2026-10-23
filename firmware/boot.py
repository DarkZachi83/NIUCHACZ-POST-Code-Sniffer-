# NIUCHACZ firmware – start: punkt dostępowy Wi-Fi "NIUCHACZ" (192.168.4.1)
#
# Zgodny z nowymi (1.24+: ssid/key/security, WLAN.SEC_*) i starszymi
# (essid/password/authmode, network.AUTH_*) wersjami MicroPythona.
import network

import config


def _wpa2():
    sec = getattr(network.WLAN, "SEC_WPA2", None)
    if sec is None:
        sec = getattr(network, "AUTH_WPA2_PSK", 3)
    return sec


def start_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    sec = _wpa2()
    try:
        ap.config(ssid=config.AP_SSID, key=config.AP_PASSWORD, security=sec)
    except (TypeError, ValueError, OSError):
        ap.config(essid=config.AP_SSID, password=config.AP_PASSWORD, authmode=sec)
    print("NIUCHACZ: Wi-Fi", ap.config("essid"), "aktywne:", ap.active())
    return ap


try:
    start_ap()
except Exception as exc:  # błąd Wi-Fi nie może zablokować startu (USB nadal działa)
    print("NIUCHACZ: blad uruchamiania Wi-Fi:", repr(exc))
