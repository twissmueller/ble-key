"""Printable housing for the ble-key: a Seeed XIAO (ESP32-S3 or nRF52840) and a 3.5 mm paddle jack.

Two variants, each made of a base and a flat lid held by M2 self-tapping screws:

- usb:      the board and the jack only, powered from USB-C.
- battery:  three layers: a 350 mAh LP-552035 LiPo on the floor, a 3 mm wiring layer above it
            for the joints and wires on the board's underside (BAT pads, and the paddle wires
            soldered to D1 / D2 / GND from below), and the board on wall brackets on top. The
            jack sits above the cell, and the cell's JST-PH connector and spare lead have a bay
            of their own under the jack.

Run with

    .venv/bin/python enclosure.py          # MJF / SLA print service, 0.25 mm fit
    .venv/bin/python enclosure.py --fdm    # own FDM printer (PETG), 0.35 mm fit, out/*-fdm/

to regenerate everything in out/<variant>/: STEP and STL per part, a lid STL turned over for
printing, and base64 GLB meshes (including the board, a placeholder jack and battery) for the
preview page.

Frame: interior floor is z = 0, the jack wall is at x = 0, the USB wall at x = v.inner_l. The
compartment is centred on y = 0. All dimensions in mm.
"""

import base64
import copy
import sys
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
JACK_PANEL = 1.5    # wall thickness at the jack: spot-faced from inside, the PJ-392 takes at most 1.9
SPOT_D = 10.0

# --- Battery: LP-552035, 3.7 V 350 mAh, with protection board and JST-PH lead ------------------
# Worst case of PKCELL's drawings (nominal 5.5 x 20 x 35 mm), as in board_case.py.
BAT_T, BAT_W, BAT_L = 5.8, 20.3, 37.0
BAT_SLACK = 0.5     # each side and on top; pouch cells swell a little
CONN_L = 10.0       # bay under the jack for the mated JST-PH pair (laid across) and the spare lead
RIB_T = 1.2         # floor rib between that bay and the cell
RIB_H = 1.5
LEAD_GAP = 8.0      # gap in the rib for the cell's lead
WIRE_H = 3.0        # wiring layer between the cell and the board's underside
BRACKET_IN = 1.2    # how far the wall brackets reach under the board's long edges
SNAP_T = 0.8        # snap lip thickness
SNAP_HOOK = 0.25    # how far its hook reaches over the board's top edge
SNAP_ROOT = 1.6     # lip root below the bracket top
SNAP_SLOT = 0.6     # slot between lip and wall

# --- Layout ---------------------------------------------------------------------------------
WIRE_BAY = 6.0                              # USB variant: between jack body and board
SIDE_W = PCB_W + 2 * SIDE_GAP               # compartment width around the board

# Screws: M2 self-tapping into bosses that stand against a wall, intruding only into the
# electronics compartment.
BOSS_R = 2.6
PILOT_D = 1.7       # M2 self-tapping pilot
SCREW_D = 2.4       # lid clearance hole
CSK_D = 4.6         # 90° countersink for 2.2 mm countersunk screws (DIN 7982, head up to 4.4 mm)

# Lid alignment lip, hanging down inside the walls.
LIP_T = 1.0
LIP_H = 2.0

# Status LEDs beside the USB receptacle (measured from Seeed's photos), as light holes in the lid.
LED_DX = 3.6                                # from the USB wall
LED_Y = PCB_W / 2 - 2.8
LED_HOLE = 1.6


@dataclass(frozen=True)
class Variant:
    name: str
    battery: bool

    @property
    def inner_l(self):
        if self.battery:
            return CONN_L + RIB_T + BAT_L + 2 * BAT_SLACK
        return JACK_DEPTH + WIRE_BAY + PCB_L

    @property
    def inner_w(self):
        return max(SIDE_W, BAT_W + 2 * BAT_SLACK) if self.battery else SIDE_W

    @property
    def bay_h(self):
        """Height of the cell bay on the floor (0 without a cell)."""
        return BAT_T + BAT_SLACK if self.battery else 0.0

    @property
    def board_z(self):
        """PCB bottom above the floor."""
        return self.bay_h + WIRE_H if self.battery else PCB_LIFT

    @property
    def board_top(self):
        return self.board_z + PCB_T

    @property
    def jack_z(self):
        """Jack axis above the floor; with a cell the jack body clears it."""
        return max(5.0, self.bay_h + 0.3 + JACK_BODY / 2)

    @property
    def inner_h(self):
        return max(self.jack_z + JACK_BODY / 2 + 0.6, self.board_z + USB_Z1 + 1.0)

    @property
    def pcb_x0(self):
        """PCB sits against the USB wall."""
        return self.inner_l - PCB_L

    @property
    def screw_y(self):
        return self.inner_w / 2 - 0.6

    @property
    def screws(self):
        """Bosses against the long walls. USB: one pair in the wiring bay. Battery: a pair beside
        the jack and a pair between the jack and the board, both hung above the cell bay."""
        if self.battery:
            xs = [5.0, (JACK_DEPTH + self.pcb_x0) / 2]
        else:
            xs = [JACK_DEPTH + WIRE_BAY / 2]
        return [(x, sy * self.screw_y) for x in xs for sy in (-1, 1)]

    @property
    def outer(self):
        return self.inner_l + 2 * WALL, self.inner_w + 2 * WALL, FLOOR + self.inner_h + LID


USB = Variant("usb", battery=False)
BATTERY = Variant("battery", battery=True)


def boss_footprint(x, y, grow=0.0, height=0.0, z0=0.0):
    """Boss cylinder plus the web that joins it to its wall, from z0 up (plain solids, outside any
    builder)."""
    sy = 1 if y > 0 else -1
    r, web = BOSS_R + grow, 1.2 + grow
    boss = Pos(x, y, z0) * Solid.make_cylinder(r, height)
    joint = Pos(x - r, y + sy * 0.6 - web / 2, z0) * Solid.make_box(2 * r, web, height)
    return boss + joint


def hung_boss(x, y, z0, top):
    """Boss that starts at z0 instead of the floor, with a 45° cone under it so it prints without
    supports. The cone ends in a point BOSS_R below z0; the caller keeps that above the cell bay."""
    cone_h = BOSS_R
    cone = Pos(x, y, z0 - cone_h) * Solid.make_cone(0.0, BOSS_R, cone_h)
    return boss_footprint(x, y, height=top - z0, z0=z0) + cone


def snap_lip(v: Variant, x0, length, sy, zr):
    """Springy lip outside the board's long edge, from zr up: it locates the board in y and hooks
    SNAP_HOOK over its top edge, with a lead-in on top, so the board clicks in and stays put with
    the lid off. Its free height from zr sets how far it can bend; keep the strain within what
    PETG takes (~4 %)."""
    yi = PCB_W / 2 + CLEAR / 2                  # lip inner face
    yo = yi + SNAP_T                            # lip outer face
    yt = PCB_W / 2 - SNAP_HOOK                  # hook tip, over the board
    zh = v.board_top + 0.1                      # hook underside
    zt = zh + 0.6                               # lip top
    pts = [(sy * yi, zr), (sy * yi, zh), (sy * yt, zh), (sy * (yo - 0.3), zt), (sy * yo, zt), (sy * yo, zr)]
    with BuildPart() as p:
        with BuildSketch(Plane.YZ.offset(x0)):
            Polygon(*pts, align=None)
        extrude(amount=length)
    return p.part


def board_brackets(v: Variant):
    """Battery variant: the board rests on four wedges on the long walls, above the cell. 45°
    underneath, so they print without supports; 2 mm long at the USB end so they stay clear of
    the first castellated pad, which may carry a wire soldered from below. The far pair reaches
    back behind the board and carries the end stops.

    Each bracket carries a snap lip (see snap_lip). A slot between lip and wall lets it spring
    outwards; it is rooted SNAP_ROOT below the bracket top so the bend stays within what PETG
    takes."""
    reach = v.inner_w / 2 - (PCB_W / 2 - BRACKET_IN)
    assert v.board_z - reach >= v.bay_h, "brackets would reach into the cell bay"
    yo = PCB_W / 2 + CLEAR / 2 + SNAP_T         # lip outer face
    zr = v.board_z - SNAP_ROOT                  # lip root, at the bottom of the slot
    assert v.board_z - (yo + SNAP_SLOT - (PCB_W / 2 - BRACKET_IN)) < zr - 0.4, "slot cuts through the bracket"
    parts = []
    for x0, length, stop in ((v.inner_l - 2.0, 2.0, False),
                             (v.pcb_x0 - CLEAR - 0.8, 2.0 + CLEAR + 0.8, True)):
        for sy in (-1, 1):
            y_in, y_wall = sy * (PCB_W / 2 - BRACKET_IN), sy * (v.inner_w / 2 + 0.5)
            pts = [(y_in, v.board_z), (y_wall, v.board_z), (y_wall, v.board_z - reach - 0.5)]
            with BuildPart() as w:
                with BuildSketch(Plane.YZ.offset(x0)):
                    Polygon(*pts, align=None)
                extrude(amount=length)
                # slot behind the lip, so it can spring
                with Locations((x0 + length / 2, sy * (yo + SNAP_SLOT / 2), zr)):
                    Box(length + 1, SNAP_SLOT, v.board_z - zr + 1,
                        align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                insert(snap_lip(v, x0, length, sy, zr))
                if stop:
                    # end stop behind the board, so a pushed-in USB plug cannot shove it back
                    with Locations((x0 + 0.4, sy * (PCB_W / 2 - BRACKET_IN / 2), v.board_z)):
                        Box(0.8, BRACKET_IN + 1.0, 1.2, align=(Align.CENTER, Align.CENTER, Align.MIN))
            parts.append(w.part)
    return parts


def base(v: Variant):
    outer_l, outer_w, _ = v.outer
    L, H = v.inner_l, v.inner_h
    with BuildPart() as p:
        with Locations((L / 2, 0, -FLOOR)):
            with BuildSketch():
                RectangleRounded(outer_l, outer_w, CORNER_R)
            extrude(amount=FLOOR + H)
        with Locations((L / 2, 0, 0)):
            with BuildSketch():
                RectangleRounded(L, v.inner_w, CORNER_R - WALL)
            extrude(amount=H, mode=Mode.SUBTRACT)

        if v.battery:
            # low floor rib between the connector bay (under the jack) and the cell, with a gap for
            # the cell's lead
            seg = (v.inner_w - LEAD_GAP) / 2
            for sy in (-1, 1):
                with Locations((CONN_L, sy * (LEAD_GAP / 2 + seg / 2), 0)):
                    Box(RIB_T, seg, RIB_H, align=(Align.MIN, Align.CENTER, Align.MIN))
            for bracket in board_brackets(v):
                insert(bracket)
        for x, y in v.screws:
            if v.battery:
                insert(hung_boss(x, y, v.bay_h + BOSS_R, H))
            else:
                insert(boss_footprint(x, y, height=H))
            pilot = H - 1.0 if not v.battery else H - v.bay_h - BOSS_R - 0.5
            with Locations((x, y, H)):
                Cylinder(PILOT_D / 2, pilot, align=(Align.CENTER, Align.CENTER, Align.MAX),
                         mode=Mode.SUBTRACT)

        if not v.battery:
            # board supports: four corner pads under the PCB, each with a snap lip beside it that
            # stands free from the floor (2 mm long, clear of the first pin pad)
            pad = 3.0
            bz = v.board_z
            for px, lx in ((v.pcb_x0 + pad / 2, v.pcb_x0), (L - pad / 2, L - 2.0)):
                for sy in (-1, 1):
                    # set back from the edge so the lip beside it stays free to bend
                    with Locations((px, sy * (PCB_W / 2 - 0.6 - pad / 2), 0)):
                        Box(pad, pad, bz, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    insert(snap_lip(v, lx, 2.0, sy, 0.0))
            # end stop behind the board, so a pushed-in USB plug cannot shove it away from the wall
            with Locations((v.pcb_x0 - CLEAR - 0.6, 0, 0)):
                Box(1.2, 6.0, bz + 1.2, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # USB-C: a notch open to the top so the board drops in; the lid closes it with a tab
        with Locations((L + WALL / 2, 0, v.board_z + USB_Z0 - CLEAR)):
            Box(WALL + 2, USB_W + 2 * CLEAR, H,
                align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # shallow recess on the outside so thick plug overmolds sit flush
        with Locations((L + WALL, 0, v.board_z + (USB_Z0 + USB_Z1) / 2)):
            Box(1.0, 12.4, 7.0, mode=Mode.SUBTRACT)

        # 3.5 mm jack through the end wall, spot-faced inside so the thread reaches the nut
        with Locations(Location((-WALL / 2, 0, v.jack_z), (0, 90, 0))):
            Cylinder(JACK_HOLE / 2, WALL + 2, mode=Mode.SUBTRACT)
        with Locations(Location((0, 0, v.jack_z), (0, 90, 0))):
            Cylinder(SPOT_D / 2, 2 * (WALL - JACK_PANEL), mode=Mode.SUBTRACT)
    return p.part


def lid(v: Variant):
    outer_l, outer_w, _ = v.outer
    L, H = v.inner_l, v.inner_h
    with BuildPart() as p:
        with Locations((L / 2, 0, H)):
            with BuildSketch():
                RectangleRounded(outer_l, outer_w, CORNER_R)
            extrude(amount=LID)
        fillet(p.faces().sort_by(Axis.Z)[-1].edges(), radius=0.8)

        # alignment lip, cut back wherever bosses reach the top
        lip_l, lip_w = L - 2 * CLEAR, v.inner_w - 2 * CLEAR
        with Locations((L / 2, 0, H)):
            with BuildSketch():
                RectangleRounded(lip_l, lip_w, CORNER_R - WALL - CLEAR)
                RectangleRounded(lip_l - 2 * LIP_T, lip_w - 2 * LIP_T, 0.3, mode=Mode.SUBTRACT)
            extrude(amount=-LIP_H)
        for x, y in v.screws:
            # only as tall as the lip: the lid plate above the boss must stay solid
            insert(boss_footprint(x, y, CLEAR, LIP_H, H - LIP_H), mode=Mode.SUBTRACT)
        with Locations(Location((LIP_T + 1.0, 0, v.jack_z), (0, 90, 0))):
            Cylinder(JACK_BODY / 2 + 0.5, 2 * (LIP_T + 1.0), mode=Mode.SUBTRACT)
        # where the board sits high (battery variant), the lip would come down onto the USB-C socket
        usb_top = v.board_z + USB_Z1 + 0.1
        if usb_top > H - LIP_H:
            with Locations((L, 0, H - LIP_H)):
                Box(LIP_T + CLEAR + 1.0, USB_W + 2 * CLEAR + 1.0, usb_top - (H - LIP_H),
                    align=(Align.MAX, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)

        # tab that closes the USB notch above the receptacle and holds the board down at that end
        tab_bottom = v.board_z + USB_Z1 + 0.1
        with Locations((L + WALL / 2, 0, H)):
            Box(WALL, USB_W + 2 * CLEAR - 0.2, H - tab_bottom,
                align=(Align.CENTER, Align.CENTER, Align.MAX))
        with Locations((L + WALL, 0, v.board_z + (USB_Z0 + USB_Z1) / 2)):
            Box(1.0, 12.4, 7.0, mode=Mode.SUBTRACT)

        # hold-down on the PCB's far corners, on bare board on both the XIAO ESP32-S3 and the
        # XIAO nRF52840 (clear of the S3's U.FL socket, a small part on the nRF52840, and the pin pads)
        for sy in (-1, 1):
            # an L-shaped rib hung from the lid's lip, stiffer than a free pin: it presses right
            # above the far support and clears the snap lip beside it
            x0 = v.pcb_x0 + 0.1
            with Locations((x0, sy * (PCB_W / 2 - 0.95), H)):
                Box(1.2, 0.9, H - v.board_top - 0.1, align=(Align.MIN, Align.CENTER, Align.MAX))
            y0, y1 = PCB_W / 2 - 0.5, v.inner_w / 2 - CLEAR
            with Locations((x0, sy * (y0 + y1) / 2, H)):
                Box(1.2, y1 - y0, H - v.board_top - 1.0, align=(Align.MIN, Align.CENTER, Align.MAX))

        # screw holes with countersinks
        for x, y in v.screws:
            with Locations((x, y, H + LID)):
                Cylinder(SCREW_D / 2, LID, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
                # 90° countersink: the cone spreads the load and leaves ~1 mm of solid lid under the head
                Cone(SCREW_D / 2, CSK_D / 2, (CSK_D - SCREW_D) / 2,
                     align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)

        # light holes over the two status LEDs
        for sy in (-1, 1):
            with Locations((L - LED_DX, sy * LED_Y, H + LID)):
                Cylinder(LED_HOLE / 2, LID, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
    return p.part


def board(v: Variant):
    """Seeed's model, rotated into the housing frame and seated on the supports."""
    xiao = import_step(HERE / "vendor" / "XIAO-ESP32S3 v2.step")
    xiao = xiao.rotate(Axis.X, 90)
    pcb = sorted(xiao.solids(), key=lambda s: -s.volume)[0].bounding_box()
    placed = xiao.translate((v.inner_l - pcb.max.X, -pcb.center().Y, v.board_z - pcb.min.Z))
    # flatten the STEP assembly so exporters do not re-apply its nested locations
    return Compound([copy.copy(s) for s in placed.solids()])


def jack(v: Variant):
    """PJ-392 stand-in for the preview: body, thread and nut."""
    z = v.jack_z
    body = Cylinder(JACK_BODY / 2, JACK_DEPTH - 2, rotation=(0, 90, 0)).translate(
        ((JACK_DEPTH - 2) / 2 - (WALL - JACK_PANEL), 0, z))
    lugs = Box(2.5, 6.0, 0.6).translate((JACK_DEPTH - 1.5, 0, z))
    thread = Cylinder(3.0, 4.5, rotation=(0, 90, 0)).translate((-WALL - 0.25, 0, z))
    nut = Cylinder(4.5, 1.8, rotation=(0, 90, 0)).translate((-WALL - 0.9, 0, z))
    return body + lugs + thread + nut


def battery(v: Variant):
    # built in a BuildPart so the placement is baked into the geometry; the glTF exporter
    # mishandles a located primitive
    with BuildPart() as p:
        with Locations((v.inner_l - BAT_SLACK, 0, 0)):
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

    others = {"board": board(v), "jack": jack(v)}
    if v.battery:
        others["battery"] = battery(v)
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
    global CLEAR
    if "--fdm" in sys.argv:
        # FDM (e.g. PETG on a Bambu Lab A1 mini) prints a little fat: looser fit, own output folders
        CLEAR = 0.35
        variants = (Variant("usb-fdm", battery=False), Variant("battery-fdm", battery=True))
    else:
        variants = (USB, BATTERY)
    for v in variants:
        export(v)


if __name__ == "__main__":
    main()
