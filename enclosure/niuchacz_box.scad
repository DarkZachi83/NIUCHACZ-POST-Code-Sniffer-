// NIUCHACZ – obudowa (OpenSCAD, parametryczna)
// Druk: Anycubic Kobra 3 V2, PLA, warstwa 0.2 mm, 3 obrysy, 20% wypełnienia, bez podpór.
// Dno drukuj dnem do stołu, wieczko napisem do stołu (część "lid" jest już obrócona).
//
// Układ (widok z góry, przód = strona USB-C):
//
//    TYŁ:  [przepust Molex 12V]          [DSUB do karty]
//          +-------------------+   +-----------------------+
//          |   (wolne miejsce) |   |                       |
//          |-------------------|   |   ESP32 + adapter ARK |
//          |  płytka           |   |   77 x 63 mm          |
//          |  konwerterów      |   |                       |
//          |  50 x 70 mm       |   |                       |
//          +-------------------+   +-----------------------+
//    PRZÓD:          (dioda zasilania)        [USB-C]
//
// Wszystkie wymiary w mm. Zmieniaj tylko sekcję PARAMETRY.

/* ===================== PARAMETRY ===================== */

part = "both";           // "base", "lid", "both" (podgląd), "assembly" (złożone)

// --- ścianki ---
wall   = 2.4;           // grubość ścianek (6 obrysów dyszy 0.4)
floor_t = 2.0;          // grubość dna
lid_t  = 2.0;           // grubość wieczka
gap    = 6.0;           // luz między płytkami a ścianką (min. 6: słupki w rogach)
inner_h = 34;           // wysokość wnętrza (od dna do wieczka)

// --- płytka z konwerterami (pomiar 14.10.2026) ---
conv_w = 50;            // szerokość (X)
conv_l = 70;            // długość (Y)
conv_hole_d = 2.0;      // średnica otworów montażowych
conv_hole_edge = 1.5;   // odległość brzegu otworu od krawędzi płytki
mini_out = 0;           // v2: Mini560 usunięty (zasilanie z USB-C JRC-C009)
mini_cable = 0;
conv_standoff = 5;      // wysokość tulejek pod płytkę
conv_screw_pilot = 1.6; // otwór pod wkręt M2 (samogwintujący w PLA)

// --- ESP32 na adapterze ARK (pomiar 14.10.2026) ---
esp_w = 63;             // szerokość (X)
esp_l = 77;             // długość (Y)
esp_h = 19;             // wysokość z adapterem
esp_pad = 4;            // podkładki pod adapter (wysokość)
esp_between = 8;        // odstęp między płytkami (przewody A)

// --- USB-C w przedniej ściance (SPRAWDŹ na swojej płytce!) ---
usb_x_from_esp_left = 30.5;   // środek gniazda od lewej krawędzi adaptera (v2: ze zdjęcia)
usb_z_above_esp_bottom = 15.5; // v2: + listwy, na których ESP32 stoi nad adapterem
usb_w = 15; usb_h = 11;       // przekrój tunelu na osłonę wtyczki (z zapasem)
// v3: tunel od ścianki do gniazda ESP32 – wtyczka (ładowarka lub komputer) dochodzi prosto do gniazda
usb_tunnel = true;
usb_mouth_from_esp_front = 15; // wylot gniazda od przedniej krawędzi adaptera ARK (ze zdjęcia)
usb_tunnel_gap = 2;            // tunel kończy się tyle mm przed gniazdem
usb_tunnel_wall = 1.6;

// --- przyciski BOOT / EN (otwory w wieczku na wykałaczkę) ---
btn_holes = true;
btn_d = 3.2;
btn_pos = [[22, 20.5], [39, 20.5]]; // EN, BOOT [X od lewej krawędzi adaptera, Y od przedniej] (v2: ze zdjęcia)

// --- antena 30x30 na wieczku ---
ant_size = 30.6;        // gniazdo pod antenę (antena 30x30 + luz)
ant_depth = 1.0;        // głębokość wgłębienia
ant_cable_d = 4.0;      // otwór na przewód U.FL

// --- złącze DSUB do karty (tylna ścianka) ---
// typy: "DE9", "DA15", "DB25", "DC37", "none"
dsub1 = "DB25";
dsub2 = "none";         // drugie złącze (np. "DE9" na diody/buzzer)
dsub_z = 17;            // wysokość środka złącza nad dnem

// --- zasilanie ---
power_hole = false;     // v2: przepust Molex usunięty
power_hole_d = 8;
power_ziptie = false;   // v2: niepotrzebny
power_led = false;      // v2: brak diody zasilania
led_d = 3.2;

// --- gniazdo zasilania USB-C na płytce JRC-C009 (tylna ścianka, za płytką CD4050) ---
// Płytka leży poziomo na dwóch szynach, wylot gniazda w otworze ścianki. Przyklej klejem na gorąco.
// Wymiary orientacyjne – SPRAWDŹ wydrukiem testowym (part = "test").
jrc = false;            // v3: niepotrzebne – zasilanie przez gniazdo USB-C samego ESP32
jrc_pcb_w = 12.5;       // szerokość płytki (wzdłuż ścianki)
jrc_pcb_l = 10.0;       // głębokość płytki (od ścianki do środka)
jrc_pcb_t = 1.0;        // grubość laminatu
jrc_sock_h = 3.3;       // wysokość metalowego gniazda USB-C
jrc_ped_h = 6;          // wysokość szyn nad dnem (miejsce na nóżki i przewody pod płytką)
jrc_open_w = 10.6;      // otwór na wtyczkę C (gniazdo 8,9 mm + zapas)
jrc_open_h = 5.0;

// --- wentylacja i opis ---
vents = true;
label = "NIUCHACZ";
label_size = 9;
label_depth = 0.6;

// --- skręcanie wieczka ---
screw_post_d = 7;       // słupki w rogach
screw_pilot = 2.5;      // pod wkręt M3 (samogwintujący)
lid_screw_d = 3.4;
lid_lip = 1.6;          // wysokość kołnierza centrującego
fit = 0.3;              // luz pasowania wieczka

$fn = 40;

/* ===================== WYLICZENIA ===================== */

conv_total_l = conv_l + mini_out + mini_cable;
in_x = gap + conv_w + esp_between + esp_w + gap;
in_y = gap + max(conv_total_l, esp_l + 28) + gap;   // 28 mm za ESP na DSUB
out_x = in_x + 2*wall;
out_y = in_y + 2*wall;
out_z = floor_t + inner_h;

conv_x0 = wall + gap;
conv_y0 = wall + gap;
esp_x0  = conv_x0 + conv_w + esp_between;
esp_y0  = wall + gap;

/* ===================== DSUB ===================== */
// [szerokość otworu u góry, wysokość otworu, rozstaw śrub]
function dsub_dims(t) =
    t == "DE9"  ? [20.0, 11.0, 25.0] :
    t == "DA15" ? [33.3, 11.0, 33.3+5.0] :
    t == "DB25" ? [47.0, 11.0, 47.0] :
    t == "DC37" ? [63.5, 11.0, 63.5] : [0,0,0];

function dsub_cut(t) =
    t == "DE9"  ? [19.6, 10.6] :
    t == "DA15" ? [27.9, 10.6] :
    t == "DB25" ? [41.9, 10.6] :
    t == "DC37" ? [58.4, 10.6] : [0,0];

module dsub_hole(t) {
    if (t != "none") {
        c = dsub_cut(t); d = dsub_dims(t);
        // trapez 10 stopni
        top = c[0]; h = c[1]; bot = top - 2*h*tan(10);
        rotate([90,0,0]) linear_extrude(height = wall*3, center = true)
            polygon([[-top/2, h/2], [top/2, h/2], [bot/2, -h/2], [-bot/2, -h/2]]);
        for (s = [-1, 1]) translate([s*d[2]/2, 0, 0])
            rotate([90,0,0]) cylinder(d = 3.2, h = wall*3, center = true);
    }
}

function dsub_flange(t) = t == "none" ? 0 : dsub_dims(t)[2] + 8;

/* ===================== DNO ===================== */

module rounded_box(x, y, z, r = 3) {
    hull() for (i = [r, x-r], j = [r, y-r]) translate([i, j, 0]) cylinder(r = r, h = z);
}

module standoff(h, d_out, d_in) {
    difference() {
        cylinder(d = d_out, h = h);
        translate([0,0,0.8]) cylinder(d = d_in, h = h);
    }
}

function jrc_x() = conv_x0 + conv_w/2;
function jrc_z() = floor_t + jrc_ped_h + jrc_pcb_t + jrc_sock_h/2;

module jrc_holder() {
    yb = wall + in_y;                    // wewnętrzna strona tylnej ścianki
    l = jrc_pcb_l + 0.4;
    for (s = [-1, 1]) {
        x_edge = jrc_x() + s * (jrc_pcb_w/2 + 0.2);
        // szyna: półka 1,5 mm pod krawędzią płytki + ścianka boczna 1,2 mm wyżej
        translate([s < 0 ? x_edge - 1.2 : x_edge - 1.5, yb - l, floor_t]) cube([2.7, l, jrc_ped_h]);
        translate([s < 0 ? x_edge - 1.2 : x_edge, yb - l, floor_t]) cube([1.2, l, jrc_ped_h + jrc_pcb_t + 1.2]);
    }
    // ogranicznik z tyłu płytki (dociska wylot gniazda do ścianki)
    translate([jrc_x() - jrc_pcb_w/2, yb - l - 1.2, floor_t]) cube([jrc_pcb_w, 1.2, jrc_ped_h + jrc_pcb_t + 1.2]);
}

function usb_cx() = esp_x0 + usb_x_from_esp_left;
function usb_cz() = floor_t + esp_pad + usb_z_above_esp_bottom;
function usb_tunnel_end() = esp_y0 + usb_mouth_from_esp_front - usb_tunnel_gap;

module usb_tunnel_shell() {
    t = usb_tunnel_wall;
    difference() {
        translate([usb_cx() - usb_w/2 - t, wall - 0.01, usb_cz() - usb_h/2 - t])
            cube([usb_w + 2*t, usb_tunnel_end() - wall, usb_h + 2*t]);
        translate([usb_cx(), 0, usb_cz()]) rotate([-90,0,0])
            linear_extrude(height = usb_tunnel_end() + 1)
                offset(r = 1.5) square([usb_w-3, usb_h-3], center = true);
    }
}

module base() {
    difference() {
        rounded_box(out_x, out_y, out_z);
        translate([wall, wall, floor_t]) cube([in_x, in_y, inner_h + 1]);

        // USB-C (przód)
        translate([esp_x0 + usb_x_from_esp_left, 0, floor_t + esp_pad + usb_z_above_esp_bottom])
            rotate([90,0,0]) linear_extrude(height = wall*3, center = true)
                offset(r = 1.5) square([usb_w-3, usb_h-3], center = true);

        // dioda zasilania (przód, nad płytką konwerterów)
        if (power_led)
            translate([conv_x0 + conv_w/2, 0, floor_t + 22]) rotate([90,0,0])
                cylinder(d = led_d, h = wall*3, center = true);

        // DSUB (tył, za ESP32)
        if (dsub2 == "none") {
            translate([esp_x0 + esp_w/2, out_y, floor_t + dsub_z]) dsub_hole(dsub1);
        } else {
            translate([esp_x0 + esp_w/2 - dsub_flange(dsub2)/2 - 2, out_y, floor_t + dsub_z]) dsub_hole(dsub1);
            translate([esp_x0 + esp_w/2 + dsub_flange(dsub1)/2 + 2, out_y, floor_t + dsub_z]) dsub_hole(dsub2);
        }

        // przepust zasilania (wersja 1, Molex)
        if (power_hole)
            translate([conv_x0 + conv_w/2, out_y, floor_t + 10]) rotate([90,0,0])
                cylinder(d = power_hole_d, h = wall*3, center = true);

        // gniazdo zasilania USB-C (JRC-C009)
        if (jrc)
            translate([jrc_x(), out_y, jrc_z()]) rotate([90,0,0])
                linear_extrude(height = wall*3, center = true)
                    offset(r = 1.2) square([jrc_open_w-2.4, jrc_open_h-2.4], center = true);

        // gumowe nóżki: płytkie gniazda pod spodem
        for (i = [12, out_x-12], j = [12, out_y-12])
            translate([i, j, -0.01]) cylinder(d = 10.4, h = 0.6);
    }

    // tulejki pod płytkę konwerterów
    hc = conv_hole_edge + conv_hole_d/2;
    for (i = [hc, conv_w - hc], j = [hc, conv_l - hc])
        translate([conv_x0 + i, conv_y0 + j, floor_t]) standoff(conv_standoff, 5, conv_screw_pilot);
    // podpora pod Mini560 (tylko wersja 1)
    if (mini_out > 0)
        translate([conv_x0 + conv_w/2 - 8, conv_y0 + conv_l + 4, floor_t]) cube([16, 3, conv_standoff + 1.6]);

    // szyny pod płytkę JRC-C009
    if (jrc) jrc_holder();

    // tunel na wtyczkę USB-C (od ścianki prawie do gniazda ESP32)
    if (usb_tunnel) usb_tunnel_shell();

    // ESP32: podkładki i narożne prowadnice
    for (i = [0, esp_w], j = [0, esp_l]) translate([esp_x0 + i, esp_y0 + j, floor_t]) {
        translate([-4, -4, 0]) intersection() {
            cube([8, 8, esp_pad]);
            translate([4,4,0]) cylinder(r = 4, h = esp_pad);
        }
    }
    for (i = [0, 1], j = [0, 1]) {
        px = esp_x0 + (i ? esp_w + 0.4 : -0.4);
        py = esp_y0 + (j ? esp_l + 0.4 : -0.4);
        translate([px, py, floor_t]) mirror([i,0,0]) mirror([0,j,0])
            difference() {
                translate([-2, -2, 0]) cube([8, 8, esp_pad + 6]);
                translate([0, 0, -1]) cube([10, 10, esp_pad + 8]);
            }
    }

    // mostek na opaskę przy przepuście zasilania
    if (power_ziptie)
        translate([conv_x0 + conv_w/2, wall + in_y - 9, floor_t]) difference() {
            translate([-6, -2, 0]) cube([12, 4, 6]);
            translate([-7, -2.5, 1.2]) cube([14, 5, 2.4]);
        }

    // słupki na wkręty wieczka
    for (i = [wall + screw_post_d/2 - 0.5, out_x - wall - screw_post_d/2 + 0.5],
         j = [wall + screw_post_d/2 - 0.5, out_y - wall - screw_post_d/2 + 0.5])
        translate([i, j, floor_t]) difference() {
            cylinder(d = screw_post_d, h = inner_h);
            translate([0,0,inner_h - 12]) cylinder(d = screw_pilot, h = 13);
        }
}

/* ===================== WIECZKO ===================== */

module lid() {
    difference() {
        union() {
            rounded_box(out_x, out_y, lid_t);
            // kołnierz centrujący (wchodzi do środka)
            translate([wall + fit, wall + fit, -lid_lip]) difference() {
                cube([in_x - 2*fit, in_y - 2*fit, lid_lip]);
                translate([1.2, 1.2, -1]) cube([in_x - 2*fit - 2.4, in_y - 2*fit - 2.4, lid_lip + 2]);
            }
        }
        // wycięcia kołnierza na słupki
        for (i = [wall + screw_post_d/2 - 0.5, out_x - wall - screw_post_d/2 + 0.5],
             j = [wall + screw_post_d/2 - 0.5, out_y - wall - screw_post_d/2 + 0.5]) {
            translate([i, j, -lid_lip - 1]) cylinder(d = screw_post_d + 1, h = lid_lip + 1);
            translate([i, j, -1]) cylinder(d = lid_screw_d, h = lid_t + 2);
            translate([i, j, lid_t - 1.6]) cylinder(d1 = lid_screw_d, d2 = 6.4, h = 1.61);
        }

        // gniazdo na antenę (nad ESP32, z tyłu)
        ax = esp_x0 + esp_w/2; ay = esp_y0 + esp_l - ant_size/2 - 4;
        translate([ax - ant_size/2, ay - ant_size/2, lid_t - ant_depth]) cube([ant_size, ant_size, 1]);
        translate([ax, ay - ant_size/2 - ant_cable_d/2 - 1, -1]) cylinder(d = ant_cable_d, h = lid_t + 2);

        // przyciski BOOT/EN
        if (btn_holes) for (p = btn_pos)
            translate([esp_x0 + p[0], esp_y0 + p[1], -1]) cylinder(d = btn_d, h = lid_t + 2);

        // wentylacja nad Mini560
        if (vents) for (k = [0:5])
            translate([conv_x0 + 8, conv_y0 + conv_l + 2 + k*4.5, -1]) cube([conv_w - 16, 2, lid_t + 2]);

        // napis (wgłębiony)
        translate([conv_x0 + conv_w/2, conv_y0 + conv_l/2, lid_t - label_depth])
            linear_extrude(height = 1) rotate([0,0,90])
                text(label, size = label_size, font = "DejaVu Sans:style=Bold",
                     halign = "center", valign = "center");
    }
}

/* ===================== WYBÓR CZĘŚCI ===================== */

if (part == "base") base();
else if (part == "lid") translate([0, out_y, lid_t]) rotate([180,0,0]) lid();
else if (part == "both") {
    base();
    translate([out_x + 10, out_y, lid_t]) rotate([180,0,0]) lid();
}
else if (part == "test") {
    // wydruk testowy: tylko fragmenty ścianek z otworem USB ESP32 i gniazdem JRC-C009
    intersection() {
        base();
        union() {
            translate([esp_x0 + usb_x_from_esp_left - 15, -1, -1]) cube([30, usb_tunnel_end() + 2, out_z + 2]);
            translate([jrc_x() - 15, out_y - wall - jrc_pcb_l - 6, -1]) cube([30, jrc_pcb_l + wall + 7, out_z + 2]);
        }
    }
}
else if (part == "assembly") {
    base();
    color("orange", 0.6) translate([0, 0, out_z]) lid();
}

echo(str("Wymiary zewnętrzne: ", out_x, " x ", out_y, " x ", out_z + lid_t, " mm"));
