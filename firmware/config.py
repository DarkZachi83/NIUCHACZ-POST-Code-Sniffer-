# NIUCHACZ firmware – konfiguracja (MicroPython, ESP32-WROOM-32U)
#
# Mapa kanałów zgodna ze specyfikacją:
#   kanały 1-8  (segmenty a..g, dp) -> GPIO 16,17,18,19,21,22,23,25
#   kanały 9-12 (cyfry DIG1..DIG4)  -> GPIO 26,27,32,33
#   kanały 13-16 (CLK, IRDY, FRAME, RESET) -> GPIO 34,35,36,39
# Uwaga: GPIO20 nie istnieje w ESP32, dlatego segmenty nie leżą w ciągłym bloku.

FW_VERSION = "0.1.0"
CHANNELS = 16

# --- Wi-Fi: własny punkt dostępowy ---
AP_SSID = "NIUCHACZ"
AP_PASSWORD = "niuchacz123"   # min. 8 znaków; zmień przed użyciem w warsztacie
TCP_PORT = 7080

# --- USB ---
USB_ENABLED = True   # ten sam protokół na porcie szeregowym (REPL)

# --- źródło kodu ---
# "latch"   = 8 przewodów z wyjść Q0–Q7 kostki 74LCX374 na karcie (od 22.10.2026, zalecane)
# "display" = stary odczyt multipleksowanego wyświetlacza
INPUT_MODE = "latch"

# --- polaryzacje (ustal skryptem tools/mux_probe.py) ---
SEG_ACTIVE_LOW = True    # informacyjnie (pomiar: wspólna anoda); dekodowanie robi aplikacja PC
DIG_ACTIVE_LOW = False   # pomiar 11.10.2026: cyfry B1-B4 aktywne stanem wysokim (ok. 1/4 z 5 V)
RST_ACTIVE_HIGH = False  # pomiar 26.10.2026 (JR16, strona układu): w resecie linia = 0

# --- diody karty (kanały 13-16: CLK, IRDY, FRAME, RESET) ---
# False, dopóki przewody od diod nie są podłączone: niepodłączone wejścia
# łapią szum, a fałszywy RESET tworzyłby fałszywe sesje.
LEDS_CONNECTED = True   # 26.10.2026: JR17 CLK→14, JR15 IRDY→15, JR14 FRAME→16, JR16 RESET→17

# --- tryb demo (test Wi-Fi i aplikacji bez karty) ---
# True = ESP32 wysyła symulowane kody zamiast odczytu karty (demo.py)
DEMO_MODE = False

# --- czasy ---
SAMPLES_PER_WINDOW = 400   # NIEUŻYWANE od 18.10.2026 – okno ustala sampler.WINDOW_SAMPLES
DEBOUNCE_MS = 16           # kod musi być stabilny tyle ms (pełny cykl multipleksu ok. 14 ms)
LED_REPORT_MS = 250        # jak często wysyłać stan diod
HEARTBEAT_MS = 1000

# --- sesje ---
SESSION_DIR = "/sessions"
MAX_SESSIONS = 50
