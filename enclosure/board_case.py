"""Printable case for the custom nRF52840 board (../hardware), in a USB-only and a battery version.

Two parts. The base holds the board on two screw standoffs and four support pads; its walls end
at the board's top surface. The lid's walls come down to that surface, with cut-outs for the
paddle jack and USB-C, so the board drops in from above. Two M2 x 8 self-tapping screws go up
through the base, the board's mounting holes and into posts in the lid, clamping everything. In
the battery version the cell sits in a pocket under the lid, above the board, clear of the antenna.

    .venv/bin/python board_case.py

writes out/board-usb/ and out/board-battery/: STEP and STL per part, a lid STL turned over for
printing, and base64 GLB meshes for the preview page.

Frame: board coordinates from ../hardware/mechanics.json (x right, y down from the board's top
edge) become X = x, Y = BOARD_H - y. Z = 0 is the base floor's top surface. All dimensions in mm.
"""

import base64
import copy
import json
from dataclasses import dataclass
from pathlib import Path

from build123d import *

HERE = Path(__file__).parent
OUT = HERE / "out"
MECH = json.loads((HERE.parent / "hardware" / "mechanics.json").read_text())
BOARD_STEP = HERE / "vendor" / "ble-key-board.step"

BOARD_W = MECH["board"]["w"]
BOARD_H = MECH["board"]["h"]
BOARD_T = MECH["board"]["thickness"]
PARTS = MECH["parts"]
HOLES = MECH["mounting_holes"]


def P(x, y):
    """Board coordinates to case coordinates."""
    return x, BOARD_H - y


# --- Printing -------------------------------------------------------------------------------
WALL = 2.0
FLOOR = 1.6
LID = 1.6
GAP = 0.25          # board edge to wall
CORNER_R = 2.5

# --- Heights (datasheets: Same Sky SJ-352x-SMT, GCT USB4105, JST PH, Panasonic EVQ-PU) --------
UNDER = 1.5                 # board bottom above the floor: jack pegs reach 0.8 below the board
ZB = UNDER                  # board bottom
ZT = UNDER + BOARD_T        # board top = base wall top = lid wall bottom
JACK_H, JACK_AXIS, JACK_NOZZLE_D, JACK_NOZZLE_L = 5.0, 2.5, 5.0, 2.5
JACK_BODY_W, JACK_BODY_L = 6.0, 14.5
USB_H, USB_AXIS, USB_W = 3.31, 1.73, 8.94
JST_H = 5.5
SW_PLATE_Z = (0.25, 1.65)   # push plate above the board
SW_PLATE_Y = 26.45          # push plate face, board y (board edge at 27.0)
TALLEST = JST_H

# --- Battery: LP-552035, worst case of PKCELL's drawings plus swelling ------------------------
BAT_L, BAT_W, BAT_T = 37.0, 20.3, 5.8
BAT_SWELL = 0.5
BAT_ABOVE = 0.5             # air between the tallest part under it and the cell

# --- Layout ---------------------------------------------------------------------------------
X_MIN, X_MAX = -GAP, BOARD_W + 0.3          # interior, board coordinates
Y_MIN_B, Y_MAX_B = -GAP, BOARD_H + 0.4      # interior in board y (bottom edge gets room for the cell)
LEFT_OUT = -JACK_NOZZLE_L                    # jack nozzle ends flush with the outside
RIGHT_OUT = BOARD_W + 1.85                   # USB-C plug overmold seats 1.85 in front of the receptacle
SCREW_CLEAR, SCREW_PILOT, HEAD_D, HEAD_H = 2.4, 1.6, 4.2, 1.0
POST_R = 1.7
STANDOFF_R = 2.2
SUPPORTS = [(2.0, 2.0), (30.0, 1.5), (30.0, 25.5), (46.5, 20.0)]   # board y, bottom side is free there

# light channel over the two status LEDs (board x 41, y 3.4 and 5.2)
LED_C = (41.0, 4.3)
LED_IN = (1.8, 3.4)
LED_WALL = 0.6

# battery placement (board coordinates): from the plug side to the USB wall, clear of the antenna
BAT_X0 = X_MAX - BAT_L
BAT_Y0 = 6.85


@dataclass(frozen=True)
class Variant:
    name: str
    battery: bool

    @property
    def ceiling(self):
        if self.battery:
            return ZT + TALLEST + BAT_ABOVE + BAT_T + BAT_SWELL + 0.2
        return ZT + TALLEST + 0.6

    @property
    def outer(self):
        return RIGHT_OUT - LEFT_OUT, (Y_MAX_B - Y_MIN_B) + 2 * WALL, FLOOR + self.ceiling + LID


USB = Variant("board-usb", battery=False)
BATTERY = Variant("board-battery", battery=True)


def footprint(z0, height):
    """The case's outline as a solid between two heights."""
    x0, x1 = LEFT_OUT, RIGHT_OUT
    (_, y_top), (_, y_bot) = P(0, Y_MIN_B - WALL), P(0, Y_MAX_B + WALL)
    with BuildPart() as p:
        with Locations(((x0 + x1) / 2, (y_top + y_bot) / 2, z0)):
            with BuildSketch():
                RectangleRounded(x1 - x0, y_top - y_bot, CORNER_R)
            extrude(amount=height)
    return p.part


def interior(z0, height):
    (_, y_top), (_, y_bot) = P(0, Y_MIN_B), P(0, Y_MAX_B)
    with BuildPart() as p:
        with Locations(((X_MIN + X_MAX) / 2, (y_top + y_bot) / 2, z0)):
            with BuildSketch():
                RectangleRounded(X_MAX - X_MIN, y_top - y_bot, 0.2)
            extrude(amount=height)
    return p.part


def base(v: Variant):
    part = footprint(-FLOOR, FLOOR + ZT) - interior(0, ZT + 1)
    with BuildPart() as extra:
        for h in HOLES:
            with Locations((*P(h["x"], h["y"]), 0)):
                Cylinder(STANDOFF_R, ZB, align=(Align.CENTER, Align.CENTER, Align.MIN))
        for x, y in SUPPORTS:
            with Locations((*P(x, y), 0)):
                Box(2.5, 2.5, ZB, align=(Align.CENTER, Align.CENTER, Align.MIN))
    part = part + extra.part
    with BuildPart() as cuts:
        for h in HOLES:
            with Locations((*P(h["x"], h["y"]), -FLOOR)):
                Cylinder(SCREW_CLEAR / 2, FLOOR + ZB + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
                Cylinder(HEAD_D / 2, HEAD_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return part - cuts.part


def lid(v: Variant):
    top = v.ceiling
    part = footprint(ZT, top + LID - ZT) - interior(ZT - 1, top - ZT + 1)

    with BuildPart() as add_:
        # screw posts down to the board's top surface
        for h in HOLES:
            with Locations((*P(h["x"], h["y"]), ZT)):
                Cylinder(POST_R, top - ZT, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # light channel from the LEDs to the top
        cx, cy = P(*LED_C)
        with Locations((cx, cy, ZT + 1.2)):
            Box(LED_IN[0] + 2 * LED_WALL, LED_IN[1] + 2 * LED_WALL, top - ZT - 1.2,
                align=(Align.CENTER, Align.CENTER, Align.MIN))
        # reset: a nub on the inside of the flexible tongue, reaching the switch's push plate
        sx, _ = P(PARTS["SW1"]["x"], 0)
        _, wall_in = P(0, Y_MAX_B)
        _, plate = P(0, SW_PLATE_Y)
        with Locations((sx, (wall_in + plate - 0.1) / 2, ZT + sum(SW_PLATE_Z) / 2)):
            Box(2.0, plate - 0.1 - wall_in + 0.2, 1.2)
        if v.battery:
            # ribs that locate the cell: across its plug end and along its antenna side
            bx0, _ = P(BAT_X0, 0)
            _, by_top = P(0, BAT_Y0)
            _, by_bot = P(0, BAT_Y0 + BAT_W)
            z0 = top - (BAT_T + BAT_SWELL) + 1.5
            with Locations((bx0 - 0.7, (by_top + by_bot) / 2 + 1.5, z0)):
                Box(1.2, by_top - by_bot - 3.0, top - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))
            led_x0 = cx - (LED_IN[0] + 2 * LED_WALL) / 2
            with Locations(((bx0 + led_x0) / 2, by_top + 0.7, z0)):
                Box(led_x0 - bx0 - 0.5, 1.2, top - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    part = part + add_.part

    with BuildPart() as cuts:
        for h in HOLES:
            with Locations((*P(h["x"], h["y"]), ZT)):
                Cylinder(SCREW_PILOT / 2, top - ZT - 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # LED light channel, open through the top
        with Locations((cx, cy, ZT)):
            Box(LED_IN[0], LED_IN[1], top + LID, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # paddle jack: the nozzle rests on the base wall, the lid wall arches over it
        _, jy = P(0, PARTS["J2"]["y"])
        r = JACK_NOZZLE_D / 2 + 0.3
        with Locations((LEFT_OUT - 1, jy, ZT - 0.01)):
            Box(-LEFT_OUT + 1 + 0.5, 2 * r, JACK_AXIS, align=(Align.MIN, Align.CENTER, Align.MIN))
        with Locations(Location((LEFT_OUT / 2, jy, ZT + JACK_AXIS), (0, 90, 0))):
            Cylinder(r, -LEFT_OUT + 2)
        # USB-C
        _, uy = P(0, PARTS["J1"]["y"])
        with Locations((BOARD_W, uy, ZT - 0.01)):
            Box(RIGHT_OUT - BOARD_W + 1, USB_W + 0.6, USB_H + 0.35, align=(Align.MIN, Align.CENTER, Align.MIN))
        # reset tongue: two slits from the lid's bottom edge up through the wall
        _, wall_out = P(0, Y_MAX_B + WALL)
        tongue_h = min(6.0, top - ZT - 1.0)
        for dx in (-2.7, 2.7):
            with Locations((sx + dx, (wall_in + wall_out) / 2, ZT - 0.01)):
                Box(0.6, WALL + 1, tongue_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    part = part - cuts.part

    # soften the top edges
    top_face = part.faces().sort_by(Axis.Z)[-1]
    try:
        part = fillet(top_face.outer_wire().edges(), radius=0.8)
    except Exception:
        pass
    return part


def board():
    pcb = import_step(BOARD_STEP)
    bb = pcb.bounding_box()
    # the STEP has the board's top-left corner at (100, -100) and its bottom at z = 0
    moved = pcb.translate((-bb.min.X, -bb.min.Y, ZB))
    # flatten, so exporters do not re-apply the STEP assembly's nested locations
    return Compound([copy.copy(s) for s in moved.solids()])


def jack():
    """SJ-3523-SMT stand-in (the board STEP has no model for it)."""
    x, y = P(PARTS["J2"]["x"], PARTS["J2"]["y"])
    with BuildPart() as p:
        with Locations((0, y, ZT)):
            Box(JACK_BODY_L, JACK_BODY_W, JACK_H, align=(Align.MIN, Align.CENTER, Align.MIN))
        with Locations(Location((-JACK_NOZZLE_L / 2, y, ZT + JACK_AXIS), (0, 90, 0))):
            Cylinder(JACK_NOZZLE_D / 2, JACK_NOZZLE_L)
    return p.part


def jst():
    """S2B-PH-SM4-TB with a PHR-2 plug, facing +x (no model in the board STEP)."""
    x, y = P(PARTS["J3"]["x"], PARTS["J3"]["y"])
    with BuildPart() as p:
        with Locations((x - 1.6, y, ZT)):
            Box(6.0, 7.9, JST_H, align=(Align.MIN, Align.CENTER, Align.MIN))
        with Locations((x + 4.4 - 4.85, y, ZT + 0.5)):
            Box(6.85, 5.8, 4.5, align=(Align.MIN, Align.CENTER, Align.MIN))
    return p.part


def battery(v: Variant):
    x0, _ = P(BAT_X0, 0)
    _, y1 = P(0, BAT_Y0)
    with BuildPart() as p:
        with Locations((x0, y1, ZT + TALLEST + BAT_ABOVE)):
            Box(BAT_L, BAT_W, BAT_T, align=(Align.MIN, Align.MAX, Align.MIN))
    return p.part


def export(v: Variant):
    out = OUT / v.name
    out.mkdir(parents=True, exist_ok=True)
    b, l = base(v), lid(v)
    for name, part in (("base", b), ("lid", l)):
        export_step(part, out / f"ble-key-{v.name}-{name}.step")
        export_stl(part, out / f"ble-key-{v.name}-{name}.stl", tolerance=0.01, angular_tolerance=0.1)
    export_stl(l.rotate(Axis.X, 180), out / f"ble-key-{v.name}-lid-print.stl", tolerance=0.01,
               angular_tolerance=0.1)

    others = {"board": board(), "jack": jack(), "jst": jst()}
    if v.battery:
        others["battery"] = battery(v)
    for name, part in {"base": b, "lid": l, **others}.items():
        glb = out / f"preview-{name}.glb"
        export_gltf(part, str(glb), binary=True, linear_deflection=0.02, angular_deflection=0.3)
        glb.with_suffix(".b64.txt").write_text(base64.b64encode(glb.read_bytes()).decode())
        glb.unlink()

    print(f"{v.name}: outer {v.outer[0]:.1f} x {v.outer[1]:.1f} x {v.outer[2]:.1f} mm")
    checks = [("base", b), ("lid", l)]
    for an, a in checks:
        for on, o in others.items():
            clash = a & o
            vol = clash.volume if clash else 0
            if vol > 0.01:
                print(f"  overlap {an}/{on}: {vol:.3f} mm3")
    if v.battery:
        for on in ("board", "jack", "jst"):
            clash = others["battery"] & others[on]
            if clash and clash.volume > 0.01:
                print(f"  overlap battery/{on}: {clash.volume:.3f} mm3")
    clash = b & l
    if clash and clash.volume > 0.01:
        print(f"  overlap base/lid: {clash.volume:.3f} mm3")


def main():
    for v in (USB, BATTERY):
        export(v)


if __name__ == "__main__":
    main()
