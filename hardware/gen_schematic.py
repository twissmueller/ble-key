"""Generate the ble-key nRF52840 schematic (ble-key.kicad_sch).

Every part is placed with a short wire and a net label on each connected pin, so the
connectivity is defined by the NETS tables below rather than by drawn wires. Unused module pins
get no-connect flags. Symbols come from KiCad's standard libraries, copied into .kilib/.

    .venv/bin/python gen_schematic.py
"""

import math
import re
import uuid
from pathlib import Path

from kiutils.symbol import SymbolLib

HERE = Path(__file__).parent
LIB = HERE / ".kilib"
OUT = HERE / "ble-key.kicad_sch"
PROJECT = "ble-key"
STUB = 2.54

# --- Part values ---------------------------------------------------------------------------------
R_CC = "5.1k"         # USB-C sink: 5.1 kOhm Rd on CC1 and CC2
R_ISET = "5.1k"       # BQ24074 fast charge: K_ISET (890) / 175 mA = 0.5 C for 350 mAh
R_ILIM = "3.09k"      # BQ24074 input current limit: K_ILIM (1525) / 0.5 A
R_TS = "10k"          # TS without a thermistor
R_PULL = "100k"       # PGOOD / CHG pull-ups to VDD
R_DIV = "1M"          # battery divider, both halves
R_LED = "1k"
R_KEY = "470"         # series resistors from the paddle jack, for ESD robustness
R_USB = "27"          # USB series resistors, per Raytac's reference circuit

FONT = "(effects (font (size 1.27 1.27)))"
HIDDEN = "(effects (font (size 1.27 1.27)) (hide yes))"
_parsed, _raw = {}, {}


_count = 0


def U():
    """Deterministic UUIDs, so regenerating gives the same file and clean diffs."""
    global _count
    _count += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ble-key/{_count}"))


def q(text):
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace("\n", "\\n") + '"'


def raw_symbol(lib, name):
    """The library's own text for a symbol, so nothing is lost in a round trip."""
    if lib not in _raw:
        _raw[lib] = (LIB / f"{lib}.kicad_sym").read_text()
    text = _raw[lib]
    i = text.index(f'\n\t(symbol "{name}"')
    depth, j = 0, i + 1
    while True:
        c = text[j]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[i + 1:j + 1]
        elif c == '"':
            j = text.index('"', j + 1)
            while text[j - 1] == "\\":
                j = text.index('"', j + 1)
        j += 1


def parsed_symbol(lib, name):
    if lib not in _parsed:
        _parsed[lib] = {s.entryName: s for s in SymbolLib.from_file(str(LIB / f"{lib}.kicad_sym")).symbols}
    return _parsed[lib][name]


def embedded_symbol(lib, name, footprint=None):
    """Symbol text for lib_symbols, flattened when it extends another symbol."""
    sym = parsed_symbol(lib, name)
    base = sym.extends or name
    text = raw_symbol(lib, base)
    text = text.replace(f'(symbol "{base}"', f'(symbol "{lib}:{name}"', 1)
    text = text.replace(f'(symbol "{base}_', f'(symbol "{name}_')
    if sym.extends:
        text = re.sub(r'\(property "Value" "[^"]*"', f'(property "Value" "{name}"', text, 1)
        fp = next((p.value for p in sym.properties if p.key == "Footprint"), "")
        text = re.sub(r'\(property "Footprint" "[^"]*"', f'(property "Footprint" "{fp}"', text, 1)
    return text


def pins_of(lib, name):
    sym = parsed_symbol(lib, name)
    if sym.extends:
        sym = parsed_symbol(lib, sym.extends)
    return [p for u in sym.units for p in u.pins]


def footprint_of(lib, name):
    sym = parsed_symbol(lib, name)
    return next((p.value for p in sym.properties if p.key == "Footprint"), "")


class Sheet:
    def __init__(self):
        self.root = U()
        self.libs = {}
        self.items = []

    def place(self, lib, name, ref, value, at, nets, footprint=None, mpn=None, nc_rest=False, bom=True):
        key = f"{lib}:{name}"
        if key not in self.libs:
            self.libs[key] = embedded_symbol(lib, name)
        pins = pins_of(lib, name)
        x0, y0 = (round(round(v / 2.54) * 2.54, 2) for v in at)   # on the 100 mil grid
        h = max([abs(p.position.Y) for p in pins] or [2.54])
        power = ref.startswith("#")
        small = len(pins) == 2 and not power        # resistors, capacitors, LEDs, switch, battery plug
        vertical = small and all(abs(p.position.X) < 0.01 for p in pins)
        if vertical:                                  # beside the part, clear of the stub labels
            ref_at, val_at, just = (x0 + 2.54, y0 - 1.27), (x0 + 2.54, y0 + 1.27), " (justify left)"
        else:
            ref_at, val_at, just = (x0, y0 - h - 2.54), (x0, y0 + h + 2.54), ""
        props = [
            ("Reference", ref, ref_at, power),
            ("Value", value, val_at, False),
            ("Footprint", footprint or footprint_of(lib, name), (x0, y0), True),
            ("Datasheet", "", (x0, y0), True),
        ]
        if mpn:
            props.append(("MPN", mpn, (x0, y0), True))
        body = [f'(symbol (lib_id {q(key)}) (at {x0} {y0} 0) (unit 1)',
                f'  (exclude_from_sim no) (in_bom {"yes" if bom else "no"}) (on_board yes) (dnp no)',
                f'  (uuid {q(U())})']
        for k, v, (px, py), hide in props:
            eff = HIDDEN if hide else FONT
            if k in ("Reference", "Value") and just:
                eff = eff[:-1] + just + ")"
            body.append(f'  (property {q(k)} {q(v)} (at {px} {py} 0) {eff})')
        for p in pins:
            body.append(f'  (pin {q(p.number)} (uuid {q(U())}))')
        body.append(f'  (instances (project {q(PROJECT)} (path {q("/" + self.root)} (reference {q(ref)}) (unit 1))))')
        body.append(')')
        self.items.append("\n".join(body))

        seen = set()
        for p in pins:
            px, py = round(x0 + p.position.X, 2), round(y0 - p.position.Y, 2)
            if (px, py) in seen:
                continue
            seen.add((px, py))
            net = nets.get(p.number, nets.get(p.name))
            if net is None:
                if nc_rest:
                    self.items.append(f'(no_connect (at {px} {py}) (uuid {q(U())}))')
                continue
            a = math.radians((p.position.angle + 180) % 360)
            dx, dy = int(round(math.cos(a))), int(round(-math.sin(a)))
            ex, ey = round(px + dx * STUB, 2), round(py + dy * STUB, 2)
            self.items.append(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid {q(U())}))')
            angle = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[(dx, dy)]
            just = "left" if angle in (0, 90) else "right"
            self.items.append(f'(label {q(net)} (at {ex} {ey} {angle}) '
                              f'(effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid {q(U())}))')

    def note(self, text, at, size=1.27):
        self.items.append(f'(text {q(text)} (exclude_from_sim no) (at {at[0]} {at[1]} 0) '
                          f'(effects (font (size {size} {size})) (justify left top)) (uuid {q(U())}))')

    def save(self):
        out = ['(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0")',
               f'(uuid {q(self.root)})', '(paper "A3")',
               '(title_block (title "ble-key nRF52840") (rev "0.1") (company "Ramus Labs"))',
               '(lib_symbols', *self.libs.values(), ')', *self.items,
               '(sheet_instances (path "/" (page "1")))', '(embedded_fonts no)', ')']
        OUT.write_text("\n".join(out) + "\n")


def R(sh, ref, value, at, a, b, mpn=None):
    sh.place("Device", "R", ref, value, at, {"1": a, "2": b},
             footprint="Resistor_SMD:R_0603_1608Metric", mpn=mpn)


def C(sh, ref, value, at, a, b, mpn=None):
    sh.place("Device", "C", ref, value, at, {"1": a, "2": b},
             footprint="Capacitor_SMD:C_0603_1608Metric", mpn=mpn)


def build():
    sh = Sheet()

    # ---------------- USB-C, ESD ----------------
    sh.note("USB-C (USB 2.0 device, 5 V sink)", (20, 20), 2.0)
    sh.place("Connector", "USB_C_Receptacle_USB2.0_16P", "J1", "USB4105-GF-A", (45, 60), {
        "VBUS": "VBUS", "CC1": "CC1", "CC2": "CC2", "D+": "USB_DP_C", "D-": "USB_DN_C",
        "GND": "GND", "SHIELD": "GND"}, nc_rest=True,
        footprint="Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", mpn="USB4105-GF-A")
    R(sh, "R1", R_CC, (80, 45), "CC1", "GND")
    R(sh, "R2", R_CC, (90, 45), "CC2", "GND")
    sh.place("Power_Protection", "USBLC6-2SC6", "U3", "USBLC6-2SC6", (85, 80), {
        "1": "USB_DP_C", "6": "USB_DP_C", "3": "USB_DN_C", "4": "USB_DN_C", "5": "VBUS", "2": "GND"},
        mpn="USBLC6-2SC6")
    R(sh, "R14", R_USB, (110, 70), "USB_DP_C", "USB_DP")
    R(sh, "R15", R_USB, (120, 70), "USB_DN_C", "USB_DN")

    # ---------------- Charger / power path ----------------
    sh.note("Charger and power path: BQ24074 (OUT = VSYS, 4.4 V on USB, powers the module's VDDH)\n"
            "175 mA charge, 500 mA input limit (EN2 = 1, EN1 = 0), ITERM and TMR open for the defaults", (20, 110), 2.0)
    sh.place("Battery_Management", "BQ24074RGT", "U2", "BQ24074RGTR", (60, 145), {
        "IN": "VBUS", "OUT": "VSYS", "BAT": "VBAT", "TS": "TS", "~{CE}": "GND", "EN1": "GND", "EN2": "VBUS",
        "~{PGOOD}": "~{PGOOD}", "~{CHG}": "~{CHG}", "ILIM": "ILIM", "ISET": "ISET", "VSS": "GND"},
        nc_rest=True, mpn="BQ24074RGTR")   # ITERM, TMR open: 10 % termination, 5 h safety timer
    C(sh, "C1", "1u", (25, 175), "VBUS", "GND")
    C(sh, "C2", "4.7u", (35, 175), "VSYS", "GND")
    C(sh, "C3", "4.7u", (45, 175), "VBAT", "GND")
    R(sh, "R3", R_TS, (95, 175), "TS", "GND")
    R(sh, "R4", R_ILIM, (55, 175), "ILIM", "GND")
    R(sh, "R5", R_ISET, (65, 175), "ISET", "GND")
    R(sh, "R6", R_PULL, (75, 175), "VDD", "~{PGOOD}")
    R(sh, "R7", R_PULL, (85, 175), "VDD", "~{CHG}")

    sh.place("Connector", "Conn_01x02_Pin", "J3", "JST PH battery", (110, 145),
             {"1": "VBAT", "2": "GND"},
             footprint="Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal", mpn="S2B-PH-SM4-TB(LF)(SN)")
    R(sh, "R8", R_DIV, (110, 175), "VBAT", "VBAT_SENSE")
    R(sh, "R9", R_DIV, (120, 175), "VBAT_SENSE", "GND")
    C(sh, "C4", "100n", (130, 175), "VBAT_SENSE", "GND")

    # ---------------- Module ----------------
    sh.note("nRF52840 module, high-voltage mode (Raytac spec 8.1, REG0 DC/DC):\n"
            "VDDH from VSYS, VDD is the internal 3.3 V output via L1\n"
            "UICR.REGOUT0 must be set to 3.3 V when the bootloader is flashed", (160, 20), 2.0)
    sh.place("RF_Module", "MDBT50Q-1MV2", "U1", "MDBT50Q-1MV2", (210, 110), {
        "VDDH": "VSYS", "VDD": "VDD", "VBUS": "VBUS", "D+": "USB_DP", "D-": "USB_DN", "GND": "GND",
        "SWDIO": "SWDIO", "SWDCLK": "SWDCLK", "P0.18": "~{RESET}",
        "P0.04": "DIT", "P0.05": "DAH", "P0.29": "VBAT_SENSE", "P0.30": "~{PGOOD}", "P0.28": "~{CHG}",
        "P1.15": "LED_RED", "P1.10": "LED_BLUE", "P0.00": "XL1", "P0.01": "XL2", "DCCH": "DCCH"},
        nc_rest=True, mpn="MDBT50Q-1MV2")
    sh.place("Device", "L", "L1", "10u", (240, 175), {"1": "DCCH", "2": "VDD"},
             footprint="Inductor_SMD:L_0603_1608Metric")
    sh.place("Device", "Crystal", "Y1", "32.768k", (255, 160), {"1": "XL1", "2": "XL2"},
             footprint="Crystal:Crystal_SMD_2012-2Pin_2.0x1.2mm")
    C(sh, "C9", "12p", (250, 175), "XL1", "GND")
    C(sh, "C10", "12p", (260, 175), "XL2", "GND")
    C(sh, "C5", "10u", (180, 175), "VSYS", "GND")
    C(sh, "C6", "10u", (190, 175), "VDD", "GND")
    C(sh, "C7", "100n", (200, 175), "VDD", "GND")
    C(sh, "C8", "10u", (210, 175), "VBUS", "GND")

    # ---------------- Paddle jack ----------------
    sh.note("Paddle jack: tip = dit, ring = dah, sleeve = GND (internal pull-ups)", (285, 40), 2.0)
    sh.place("Connector_Audio", "AudioJack3", "J2", "SJ-3523-SMT", (285, 50),
             {"T": "JACK_T", "R": "JACK_R", "S": "GND"},
             footprint="Connector_Audio:Jack_3.5mm_CUI_SJ-3523-SMT_Horizontal", mpn="SJ-3523-SMT-TR")
    R(sh, "R10", R_KEY, (310, 45), "JACK_T", "DIT")
    R(sh, "R11", R_KEY, (320, 45), "JACK_R", "DAH")

    # ---------------- LEDs, reset, SWD ----------------
    sh.note("Status LEDs (Feather nRF52840 pins), reset button, SWD for the bootloader", (285, 80), 2.0)
    R(sh, "R12", R_LED, (285, 100), "LED_RED", "LED_R_A")
    sh.place("Device", "LED", "D1", "red", (310, 100), {"2": "LED_R_A", "1": "GND"},
             footprint="LED_SMD:LED_0603_1608Metric", mpn="150060RS75000")
    R(sh, "R13", R_LED, (285, 120), "LED_BLUE", "LED_B_A")
    sh.place("Device", "LED", "D2", "blue", (310, 120), {"2": "LED_B_A", "1": "GND"},
             footprint="LED_SMD:LED_0603_1608Metric", mpn="150060BS75000")
    sh.place("Switch", "SW_Push", "SW1", "reset", (290, 145), {"1": "~{RESET}", "2": "GND"},
             footprint="Button_Switch_SMD:Panasonic_EVQPUL_EVQPUC", mpn="EVQ-PUC02K")
    sh.place("Connector", "Conn_ARM_SWD_TagConnect_TC2030-NL", "J4", "SWD", (300, 175), {
        "VCC": "VDD", "SWDIO": "SWDIO", "~{RESET}": "~{RESET}", "SWCLK": "SWDCLK", "GND": "GND"},
        nc_rest=True, bom=False,   # pads only: the Tag-Connect cable clips onto the board
        footprint="Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical")

    # ---------------- Power flags ----------------
    for i, (net, x) in enumerate((("GND", 140), ("VBUS", 150), ("VDD", 160))):
        sh.place("power", "PWR_FLAG", f"#FLG0{i + 1}", "PWR_FLAG", (x, 230), {"1": net})
    sh.save()


if __name__ == "__main__":
    build()
    print("wrote", OUT)
