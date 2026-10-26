# POST cards – compatibility / Karty POST – zgodność

[English](#english) · [Polski](#polski)

---

## English

NIUCHACZ does not replace the POST card – it reads it. What you get depends on the card.
Check your card against the table first, then follow the build guide for its type.

### Feature matrix

| Feature | Type A – reference | Type B – single-chip |
|---|---|---|
| POST codes | ✓ complete – read from the 74LCX374 latch (82 codes / boot on ASRock 775V88) | ~ from the display only – fast codes are lost |
| Very short codes (~1 µs) | ✓ marked `~` | ✗ |
| Board RESET (new boot) | ✓ from the RESET LED | ~ guessed from code D0 (AMI) / C0 (Award) |
| PCI activity IRDY / FRAME | ✓ from the LEDs | ✗ no such LEDs |
| PCI CLK | ✗ 33 MHz, too fast for the ESP32 | ✗ |
| Beep codes (speaker) | ? planned – card has a buzzer | ? planned – J2 (+/−) header next to SP1 |
| Card's own code history (PRE/NEXT) | – | ? to be checked |
| Modifications | wires to the latch outputs, the JR resistors and the buzzer | display tap only, unless U1 can be read |
| Status | **works** | **to be evaluated** |

✓ works · ~ works with limits · ✗ not possible · ? not checked yet

### How to recognise the type

- **Type A:** separate logic chips next to the display – look for **74xx374 / 74xx574** (8-bit latch) –
  and LEDs labelled CLK, IRDY, FRAME, RESET. Example: "PC Analyzer PCI/ISA" with 74LCX374.
- **Type B:** one square chip (QFP) drives the display directly, only power LEDs (−12 V, +12 V, VCC),
  buttons PRE/NEXT, buzzer SP1 with a J2 header.
- **Other:** send a photo of both sides and the chip markings – the table will grow.

### Cards under test (10/2026)

| # | Card | Expected type | Role |
|---|---|---|---|
| 1 | Green PCI/ISA "PC Analyzer" with 74LCX374 | A | prototype (modified live, glued) |
| 2 | Same card as #1 | A | clean reference build for the build guide |
| 3 | Green PCI/ISA single-chip (U1 drives the display) | B | display reading + speaker on J2 |
| 4 | Red PCI "YME" (seller ships one of two versions) | A? | look for the code byte on the GAL16V8 outputs |
| 5 | Yellow Mini PCI / Mini PCI-E / LPC (laptops) | B + RESET | 2-digit display, RST− LED |

Common test: one REC run on ASRock 775V88 – how many of the 82 codes per boot the card delivers.

### Before buying

1. Photo of the back side – are there 74xx374/574 chips?
2. Which LEDs: only power, or also RESET / bus signals?
3. Buzzer with a header for the motherboard speaker?
4. Never connect anything to the ±12 V LEDs.

---

## Polski

NIUCHACZ nie zastępuje karty POST – on ją czyta. To, co dostaniesz, zależy od karty.
Najpierw sprawdź swoją kartę w tabeli, potem idź do instrukcji budowy dla jej typu.

### Tabela możliwości

| Funkcja | Typ A – wzorcowa | Typ B – jednoukładowa |
|---|---|---|
| Kody POST | ✓ komplet – z zatrzasku 74LCX374 (82 kody na start ASRock 775V88) | ~ tylko z wyświetlacza – szybkie kody giną |
| Bardzo krótkie kody (ok. 1 µs) | ✓ oznaczone `~` | ✗ |
| RESET płyty (nowy start) | ✓ z diody RESET | ~ zgadywany po kodzie D0 (AMI) / C0 (Award) |
| Aktywność PCI IRDY / FRAME | ✓ z diod | ✗ brak takich diod |
| Zegar PCI CLK | ✗ 33 MHz – za szybki dla ESP32 | ✗ |
| Sygnały dźwiękowe (beep) | ? w planach – karta ma brzęczyk | ? w planach – złącze J2 (+/−) przy SP1 |
| Historia kodów w karcie (PRE/NEXT) | – | ? do sprawdzenia |
| Przeróbki | przewody do wyjść zatrzasku, rezystorów JR i brzęczyka | tylko odczyt wyświetlacza, chyba że da się czytać U1 |
| Stan | **działa** | **do oceny** |

✓ działa · ~ działa z ograniczeniami · ✗ niemożliwe · ? jeszcze nie sprawdzone

### Jak rozpoznać typ

- **Typ A:** osobne układy logiczne przy wyświetlaczu – szukaj **74xx374 / 74xx574** (zatrzask 8-bitowy)
  – i diod opisanych CLK, IRDY, FRAME, RESET. Przykład: „PC Analyzer PCI/ISA” z 74LCX374.
- **Typ B:** jeden kwadratowy układ (QFP) steruje wprost wyświetlaczem, tylko diody zasilań
  (−12 V, +12 V, VCC), przyciski PRE/NEXT, brzęczyk SP1 ze złączem J2.
- **Inna:** zdjęcie obu stron i oznaczeń układów – tabela będzie rosła.

### Karty w testach (10/2026)

| # | Karta | Spodziewany typ | Rola |
|---|---|---|---|
| 1 | Zielona PCI/ISA „PC Analyzer” z 74LCX374 | A | prototyp (przerabiany na żywo, klejony) |
| 2 | Taka sama jak nr 1 | A | czysty egzemplarz wzorcowy do instrukcji budowy |
| 3 | Zielona PCI/ISA jednoukładowa (U1 steruje wyświetlaczem) | B | odczyt wyświetlacza + brzęczyk na J2 |
| 4 | Czerwona PCI „YME” (sprzedawca wysyła jedną z dwóch wersji) | A? | szukamy bajtu kodu na wyjściach GAL16V8 |
| 5 | Żółta Mini PCI / Mini PCI-E / LPC (laptopy) | B + RESET | wyświetlacz 2-cyfrowy, dioda RST− |

Wspólny test: jedno nagranie REC na ASRock 775V88 – ile z 82 kodów na start daje karta.

### Zanim kupisz

1. Zdjęcie strony spodniej – są układy 74xx374/574?
2. Jakie diody: tylko zasilania, czy też RESET / sygnały magistrali?
3. Brzęczyk ze złączem na głośnik płyty głównej?
4. Nigdy nic nie podłączaj do diod ±12 V.
