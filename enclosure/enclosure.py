"""Printable housing for the ble-key: a Seeed XIAO ESP32-S3 and a 3.5 mm paddle jack.

Two variants, each made of a base and a flat lid held by M2 self-tapping screws:

- usb:      the board and the jack only, powered from USB-C.
- battery:  the same compartment plus a second one beside it for a 350 mAh LP-552035 LiPo.

Run with

    .venv/bin/python enclosure.py

to regenerate everything in out/<variant>/: STEP and STL per part, a lid STL turned over for
printing, and base64 GLB meshes (including the board, a placeholder jack and battery) for the
preview page.

Frame: interior floor is z = 0, the jack wall is at x = 0, the USB wall at x = INNER_L. The
electronics compartment is centred on y = 0; the battery compartment lies on the +y side.
All dimensions in mm.
"""

import base64
import copy
from dataclasses import dataclass
from pathlib import Path

from build123d import *

HERE = Path(__file__).parent
OUT = HERE / "out"

# --- Printing -------------------------------------------------------------------------------
WALL = 2.0          # outer walls and the battery divider
FLOOR = 2.0         # base floor
LID = 2.0           # lid plate
CLEAR = 0.25        # fit clearance between printed parts and parts that drop in
CORNER_R = 3.0      # outer vertical edge radius

# --- XIAO ESP32-S3 (measured from Seeed's STEP model) -----------------------------------------
PCB_L = 21.0        # along x, USB end at +x
PCB_W = 17.8
PCB_T = 1.25
USB_W = 8.94        # receptacle width (y)
USB_Z0 = 0.26       # receptacle bottom above PCB bottom
USB_Z1 = 4.46       # receptacle top above PCB bottom
PCB_LIFT = 3.0      # PCB bottom above the floor: room for solder joints and wires underneath
SIDE_GAP = 1.6      # room beside the castellated edges for wires

# --- 3.5 mm panel jack: PJ-392 (1/4" hole, panels up to 1.9 mm, body 8 mm, 16 mm overall) -------
JACK_HOLE = 6.5     # through-hole for the thread
JACK_BODY = 8.0     # body diameter behind the panel
JACK_DEPTH = 12.0   # body plus solder lugs behind the panel
JACK_Z = 5.0        # jack axis above the floor
JACK_PANEL = 1.5    # wall thickness at the jack: spot-faced from inside, the PJ-392 takes at most 1.9
SPOT_D = 10.0

# --- Battery: LP-552035, 3.7 V 350 mAh, 5.5 x 20 x 35 mm with protection board and JST-PH lead ----
BAT_T, BAT_W, BAT_L = 5.5, 20.0, 35.0
BAT_SLACK = 0.5     # each side; pouch cells swell a little
BAT_HOLD = 0.4      # gap between the cell and the lid ribs, for a strip of foam tape

# --- Layout ---------------------------------------------------------------------------------
WIRE_BAY = 6.0                              # between jack body and board: wiring, resistors, bosses
INNER_L = JACK_DEPTH + WIRE_BAY + PCB_L
INNER_W = PCB_W + 2 * SIDE_GAP              # electronics compartment
INNER_H = max(JACK_Z + JACK_BODY / 2 + 0.6, PCB_LIFT + USB_Z1 + 1.0)
PCB_X0 = INNER_L - PCB_L                    # PCB sits against the USB wall
BAT_COMP_W = BAT_W + 2 * BAT_SLACK
BAT_Y = INNER_W / 2 + WALL + BAT_COMP_W / 2  # battery compartment centre

# Screws: M2 self-tapping into bosses that stand against a wall, intruding only into the
# electronics compartment.
BOSS_R = 2.6
SCREW_Y = INNER_W / 2 - 0.6
PILOT_D = 1.7       # M2 self-tapping pilot
SCREW_D = 2.4       # lid clearance hole
HEAD_D = 4.2        # counterbore for the screw head
HEAD_H = 1.2

# Lid alignment lip, hanging down inside the walls.
LIP_T = 1.0
LIP_H = 2.0

# Status LEDs beside the USB receptacle (measured from Seeed's photos), as light holes in the lid.
LED_X = INNER_L - 3.6
LED_Y = PCB_W / 2 - 2.8
LED_HOLE = 1.6

BOARD_Z = PCB_LIFT                          # PCB bottom
BOARD_TOP = PCB_LIFT + PCB_T


@dataclass(frozen=True)
class Variant:
    name: str
    battery: bool

    @property
    def y_min(self):
        return -INNER_W / 2

    @property
    def y_max(self):
        return INNER_W / 2 + (WALL + BAT_COMP_W if self.battery else 0)

    @property
    def inner_w(self):
        return self.y_max - self.y_min

    @property
    def y_mid(self):
        return (self.y_min + self.y_max) / 2

    @property
    def screws(self):
        """Bosses in the wiring bay; the battery variant adds a pair at the jack end."""
        xs = [JACK_DEPTH + WIRE_BAY / 2] + ([4.0] if self.battery else [])
        return [(x, sy * SCREW_Y) for x in xs for sy in (-1, 1)]

    @property
    def outer(self):
        return INNER_L + 2 * WALL, self.inner_w + 2 * WALL, FLOOR + INNER_H + LID


USB = Variant("usb", battery=False)
BATTERY = Variant("battery", battery=True)


def boss_footprint(x, y, grow=0.0):
    """Boss cylinder plus the web that joins it to its wall (plain solids, outside any builder)."""
    sy = 1 if y > 0 else -1
    r, web = BOSS_R + grow, 1.2 + grow
    boss = Pos(x, y, 0) * Solid.make_cylinder(r, INNER_H)
    joint = Pos(x - r, y + sy * 0.6 - web / 2, 0) * Solid.make_box(2 * r, web, INNER_H)
    return boss + joint


def base(v: Variant):
    outer_l, outer_w, _ = v.outer
    with BuildPart() as p:
        with Locations((INNER_L / 2, v.y_mid, -FLOOR)):
            with BuildSketch():
                RectangleRounded(outer_l, outer_w, CORNER_R)
            extrude(amount=FLOOR + INNER_H)
        with Locations((INNER_L / 2, v.y_mid, 0)):
            with BuildSketch():
                RectangleRounded(INNER_L, v.inner_w, CORNER_R - WALL)
            extrude(amount=INNER_H, mode=Mode.SUBTRACT)

        if v.battery:
            # divider between the electronics and the battery, with a slot for the battery lead
            with Locations((INNER_L / 2, INNER_W / 2 + WALL / 2, 0)):
                Box(INNER_L, WALL, INNER_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
            with Locations((PCB_X0 + 7.0, INNER_W / 2 + WALL / 2, 0)):
                Box(6.0, WALL + 1, 4.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
            # stop at the jack end so the cell sits against the USB end, with room for its lead
            with Locations((0, BAT_Y, 0)):
                Box(INNER_L - BAT_L - 2 * BAT_SLACK, BAT_COMP_W, 2.0,
                    align=(Align.MIN, Align.CENTER, Align.MIN))

        for x, y in v.screws:
            insert(boss_footprint(x, y))
            with Locations((x, y, INNER_H)):
                Cylinder(PILOT_D / 2, INNER_H - 1.0, align=(Align.CENTER, Align.CENTER, Align.MAX),
                         mode=Mode.SUBTRACT)

        # board supports: four corner pads under the PCB, with side lips that locate it in y
        pad = 3.0
        for px, lx in ((PCB_X0 + pad / 2, PCB_X0 + 1.0), (INNER_L - pad / 2, INNER_L - 1.0)):
            for sy in (-1, 1):
                with Locations((px, sy * (PCB_W / 2 - pad / 2), 0)):
                    Box(pad, pad, BOARD_Z, align=(Align.CENTER, Align.CENTER, Align.MIN))
                # lip outside the long edge, 2 mm long so it stays clear of the first pin pad
                with Locations((lx, sy * (PCB_W / 2 + CLEAR / 2 + 0.4), 0)):
                    Box(2.0, 0.8, BOARD_Z + 1.2, align=(Align.CENTER, Align.CENTER, Align.MIN))
                with Locations((lx, sy * (PCB_W / 2 + CLEAR / 2 + 0.4 + SIDE_GAP / 2), 0)):
                    Box(2.0, SIDE_GAP - 0.4, BOARD_Z, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # end stop behind the board, so a pushed-in USB plug cannot shove it away from the wall
        with Locations((PCB_X0 - CLEAR - 0.6, 0, 0)):
            Box(1.2, 6.0, BOARD_Z + 1.2, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # USB-C: a notch open to the top so the board drops in; the lid closes it with a tab
        with Locations((INNER_L + WALL / 2, 0, BOARD_Z + USB_Z0 - CLEAR)):
            Box(WALL + 2, USB_W + 2 * CLEAR, INNER_H,
                align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # shallow recess on the outside so thick plug overmolds sit flush
        with Locations((INNER_L + WALL, 0, BOARD_Z + (USB_Z0 + USB_Z1) / 2)):
            Box(1.0, 12.4, 7.0, mode=Mode.SUBTRACT)

        # 3.5 mm jack through the end wall, spot-faced inside so the thread reaches the nut
        with Locations(Location((-WALL / 2, 0, JACK_Z), (0, 90, 0))):
            Cylinder(JACK_HOLE / 2, WALL + 2, mode=Mode.SUBTRACT)
        with Locations(Location((0, 0, JACK_Z), (0, 90, 0))):
            Cylinder(SPOT_D / 2, 2 * (WALL - JACK_PANEL), mode=Mode.SUBTRACT)
    return p.part


def lid(v: Variant):
    outer_l, outer_w, _ = v.outer
    with BuildPart() as p:
        with Locations((INNER_L / 2, v.y_mid, INNER_H)):
            with BuildSketch():
                RectangleRounded(outer_l, outer_w, CORNER_R)
            extrude(amount=LID)
        fillet(p.faces().sort_by(Axis.Z)[-1].edges(), radius=0.8)

        # alignment lip, cut back wherever bosses or the divider reach the top
        lip_l, lip_w = INNER_L - 2 * CLEAR, v.inner_w - 2 * CLEAR
        with Locations((INNER_L / 2, v.y_mid, INNER_H)):
            with BuildSketch():
                RectangleRounded(lip_l, lip_w, CORNER_R - WALL - CLEAR)
                RectangleRounded(lip_l - 2 * LIP_T, lip_w - 2 * LIP_T, 0.3, mode=Mode.SUBTRACT)
            extrude(amount=-LIP_H)
        for x, y in v.screws:
            insert(Pos(0, 0, INNER_H - LIP_H) * boss_footprint(x, y, CLEAR), mode=Mode.SUBTRACT)
        with Locations(Location((LIP_T + 1.0, 0, JACK_Z), (0, 90, 0))):
            Cylinder(JACK_BODY / 2 + 0.5, 2 * (LIP_T + 1.0), mode=Mode.SUBTRACT)
        if v.battery:
            with Locations((INNER_L / 2, INNER_W / 2 + WALL / 2, INNER_H)):
                Box(INNER_L + 2, WALL + 2 * CLEAR, LIP_H, align=(Align.CENTER, Align.CENTER, Align.MAX),
                    mode=Mode.SUBTRACT)
            # ribs that keep the cell down
            for rx in (INNER_L - BAT_L * 0.75, INNER_L - BAT_L * 0.25):
                with Locations((rx, BAT_Y, INNER_H)):
                    Box(1.2, BAT_W - 2, INNER_H - BAT_T - BAT_HOLD,
                        align=(Align.CENTER, Align.CENTER, Align.MAX))

        # tab that closes the USB notch above the receptacle and holds the board down at that end
        tab_bottom = BOARD_Z + USB_Z1 + 0.1
        with Locations((INNER_L + WALL / 2, 0, INNER_H)):
            Box(WALL, USB_W + 2 * CLEAR - 0.2, INNER_H - tab_bottom,
                align=(Align.CENTER, Align.CENTER, Align.MAX))
        with Locations((INNER_L + WALL, 0, BOARD_Z + (USB_Z0 + USB_Z1) / 2)):
            Box(1.0, 12.4, 7.0, mode=Mode.SUBTRACT)

        # hold-down pins on the PCB's far corners, on bare board on both the XIAO ESP32-S3 and the
        # XIAO nRF52840 (clear of the S3's U.FL socket, a small part on the nRF52840, and the pin pads)
        for sy in (-1, 1):
            with Locations((PCB_X0 + 0.8, sy * (PCB_W / 2 - 0.8), INNER_H)):
                Cylinder(0.7, INNER_H - BOARD_TOP - 0.1, align=(Align.CENTER, Align.CENTER, Align.MAX))

        # screw holes with counterbores
        for x, y in v.screws:
            with Locations((x, y, INNER_H + LID)):
                Cylinder(SCREW_D / 2, LID, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
                Cylinder(HEAD_D / 2, HEAD_H, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)

        # light holes over the two status LEDs
        for sy in (-1, 1):
            with Locations((LED_X, sy * LED_Y, INNER_H + LID)):
                Cylinder(LED_HOLE / 2, LID, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
    return p.part


def board():
    """Seeed's model, rotated into the housing frame and seated on the supports."""
    xiao = import_step(HERE / "vendor" / "XIAO-ESP32S3 v2.step")
    xiao = xiao.rotate(Axis.X, 90)
    pcb = sorted(xiao.solids(), key=lambda s: -s.volume)[0].bounding_box()
    placed = xiao.translate((INNER_L - pcb.max.X, -pcb.center().Y, BOARD_Z - pcb.min.Z))
    # flatten the STEP assembly so exporters do not re-apply its nested locations
    return Compound([copy.copy(s) for s in placed.solids()])


def jack():
    """PJ-392 stand-in for the preview: body, thread and nut."""
    body = Cylinder(JACK_BODY / 2, JACK_DEPTH - 2, rotation=(0, 90, 0)).translate(
        ((JACK_DEPTH - 2) / 2 - (WALL - JACK_PANEL), 0, JACK_Z))
    lugs = Box(2.5, 6.0, 0.6).translate((JACK_DEPTH - 1.5, 0, JACK_Z))
    thread = Cylinder(3.0, 4.5, rotation=(0, 90, 0)).translate((-WALL - 0.25, 0, JACK_Z))
    nut = Cylinder(4.5, 1.8, rotation=(0, 90, 0)).translate((-WALL - 0.9, 0, JACK_Z))
    return body + lugs + thread + nut


def battery():
    # built in a BuildPart so the placement is baked into the geometry; the glTF exporter
    # mishandles a located primitive
    with BuildPart() as p:
        with Locations((INNER_L - BAT_SLACK, BAT_Y, 0)):
            Box(BAT_L, BAT_W, BAT_T, align=(Align.MAX, Align.CENTER, Align.MIN))
    return p.part


def export(v: Variant):
    out = OUT / v.name
    out.mkdir(parents=True, exist_ok=True)
    b, l = base(v), lid(v)
    for name, part in (("base", b), ("lid", l)):
        export_step(part, out / f"ble-key-{v.name}-{name}.step")
        export_stl(part, out / f"ble-key-{v.name}-{name}.stl", tolerance=0.01, angular_tolerance=0.1)
    # lid turned over for printing: flat top on the bed
    export_stl(l.rotate(Axis.X, 180), out / f"ble-key-{v.name}-lid-print.stl",
               tolerance=0.01, angular_tolerance=0.1)

    others = {"board": board(), "jack": jack()}
    if v.battery:
        others["battery"] = battery()
    # one mesh per part for the preview page, which colours and toggles them separately; as
    # base64 text because the published page can only serve text files
    for name, part in {"base": b, "lid": l, **others}.items():
        glb = out / f"preview-{name}.glb"
        export_gltf(part, str(glb), binary=True, linear_deflection=0.01, angular_deflection=0.2)
        glb.with_suffix(".b64.txt").write_text(base64.b64encode(glb.read_bytes()).decode())
        glb.unlink()

    print(f"{v.name}: outer {v.outer[0]:.1f} x {v.outer[1]:.1f} x {v.outer[2]:.1f} mm")
    pairs = [("base", b, "lid", l)] + [(pn, pp, on, op) for on, op in others.items()
                                       for pn, pp in (("base", b), ("lid", l))]
    for an, a, bn, bb in pairs:
        clash = a & bb
        vol = clash.volume if clash else 0
        if vol > 0.01:
            print(f"  overlap {an}/{bn}: {vol:.3f} mm3")


def main():
    for v in (USB, BATTERY):
        export(v)


if __name__ == "__main__":
    main()
