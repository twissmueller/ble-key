"""Printable housing for the ble-key: a Seeed XIAO (ESP32-S3 or nRF52840) and a 3.5 mm paddle jack.

Two variants, each made of a base and a flat lid held by M2 self-tapping screws (the battery
variant has a third part, the frame):

- usb:      the board and the jack only, powered from USB-C.
- battery:  three layers: a 350 mAh LP-552035 LiPo in a pocket on the floor, a 3 mm wiring
            layer above it for the joints and wires on the board's underside (BAT pads, and the
            paddle wires soldered to D1 / D2 / GND from below), and the board on top. The board
            sits in a frame that drops in on top of the cell. The lid is screwed into bosses that
            hang in the base's four corners. The jack sits above the cell in a cradle on the
            frame, and the cell's spare lead has a bay of its own under the jack.

Both variants take the jack through a slot in the end wall, open to the top and closed by a tab on
the lid, so the jack drops in from above already soldered to the board. In the battery variant,
board, jack and frame are put together outside the case and lowered in as one module.

Run with

    .venv/bin/python enclosure.py          # MJF / SLA print service, 0.25 mm fit
    .venv/bin/python enclosure.py --fdm    # own FDM printer (PETG), 0.35 mm fit, out/*-fdm/
    .venv/bin/python enclosure.py --snap-test   # FDM test pieces for the snap lips, out/snap-test-fdm/
    ... --jack pj392                       # for the PJ-392 jack instead of the Cliff FC681374V

to regenerate everything in out/<variant>/: STEP and STL per part, a lid STL turned over for
printing, and base64 GLB meshes (including the board, a placeholder jack and battery) for the
preview page.

Frame: interior floor is z = 0, the jack wall is at x = 0, the USB wall at x = v.inner_l. The
compartment is centred on y = 0. All dimensions in mm.
"""

import base64
import copy
import math
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

# --- 3.5 mm panel jack ------------------------------------------------------------------------
# Both go in from inside, thread through the end wall, nut outside. Choose with --jack.
@dataclass(frozen=True)
class Jack:
    name: str
    hole: float         # through-hole for the thread
    body_w: float       # body across (y) behind the panel; equal to body_h for a round body
    body_h: float       # body height (z)
    round: bool
    depth: float        # body plus solder lugs / pins behind the panel
    panel: float        # wall thickness at the jack (spot-faced from inside where thinner than WALL)
    thread_d: float     # for the preview model
    nut_d: float
    nut_t: float


JACKS = {
    # PJ-392: 1/4" hole, panels up to 1.9 mm, round body 8 mm, 16 mm overall (TinyTronics)
    "pj392": Jack("pj392", hole=6.5, body_w=8.0, body_h=8.0, round=True, depth=12.0, panel=1.5,
                  thread_d=6.0, nut_d=9.0, nut_t=1.8),
    # Cliff FC681374V: M8 x 0.75 thread 4.5 long, ring nut 10 x 2, square body 10.5 x 9.0 x 13.5
    # (5.0 / 5.5 either side of the axis) plus 4 mm pins (Reichelt). The full 2 mm wall leaves
    # 0.5 mm of thread beyond the nut; the body's front face rests against the inside of the wall.
    "cliff": Jack("cliff", hole=8.5, body_w=11.0, body_h=9.0, round=False, depth=17.5, panel=WALL,
                  thread_d=8.0, nut_d=10.0, nut_t=2.0),
}
JACK = JACKS["cliff"]
SPOT_D = 10.0       # spot face inside the wall where the jack needs a thinner panel

# --- Battery: LP-552035, 3.7 V 350 mAh, with protection board; its lead is soldered to the BAT pads
# Worst case of PKCELL's drawings (nominal 5.5 x 20 x 35 mm).
BAT_T, BAT_W, BAT_L = 5.8, 20.3, 37.0
BAT_SLACK = 0.5     # each side and on top; pouch cells swell a little
CONN_L = 10.0       # bay under the jack for the cell's spare lead (and its protection board's end)
RIB_T = 1.2         # floor rib between that bay and the cell
RIB_H = 1.5
LEAD_GAP = 8.0      # gap in the rib for the cell's lead
WIRE_H = 3.0        # wiring layer between the cell and the board's underside
BRACKET_IN = 1.2    # how far the brackets reach under the board's long edges
FRAME_LEDGE = 1.0   # shoulder along each long wall, above the cell pocket, that the frame rests on
RAIL_H = 1.2        # height of the frame's rails
FRAME_WEB = 0.6     # web along the outside of each rail, up to the board: makes the rails L-shaped
SNAP_GAP = 0.4      # gap around a snap lip where it rises through its rail
SNAP_BASE = 0.4     # floor left under that pocket: it ties the lip to the rail (two 0.2 mm layers)
SNAP_T = 0.8        # snap lip thickness
SNAP_HOOK = 0.7     # how far its hook reaches over the board's top edge, at most (see Variant.snap_hook)
SNAP_STRAIN = 0.04  # bending strain a lip may take while the board clicks in: what PETG takes
SNAP_LEAD = 1.0     # height of the lead-in above the hook
SNAP_L = 1.6        # lip length along the board's long edge
SNAP_TAB = 2.0      # lip top above the board's top: a tab to push the lip open with a small screwdriver
SNAP_X = 4.0        # lip centre from each end of the board: the corners are rounded (r ≈ 2) and
                    # the first castellated pad notches the edge 2.5-3.0 from the end, so the lips
                    # sit on the straight stretch between the first and second pad (3.1-5.0)
SNAP_X_USB = 6.7    # battery: lip centre from the USB end, between the second and third pad
                    # (5.65-7.75): the corner bosses there leave no room for the lips at SNAP_X

# --- Layout ---------------------------------------------------------------------------------
WIRE_BAY = 6.0                              # USB variant: between jack body and board
SIDE_W = PCB_W + 2 * SIDE_GAP               # compartment width around the board

# Screws: M2 self-tapping into bosses. USB: bosses that stand against a wall, intruding only into
# the electronics compartment. Battery: bosses that hang in the case's four corners from the top,
# so the lid is screwed to the case itself.
BOSS_R = 2.6
PILOT_D = 1.7       # M2 self-tapping pilot
CORNER_IN = 1.5     # battery: screw axes in from both walls of a corner
CORNER_DEPTH = 6.5  # battery: corner boss from the lid down; below it a 45° slope back to the walls
CORNER_PILOT = 5.5  # its pilot hole: a 6.5 mm screw reaches 4.5 below the lid's underside
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
        return JACK.depth + WIRE_BAY + PCB_L

    @property
    def bay_w(self):
        """Width of the cell pocket (battery variant)."""
        return BAT_W + 2 * BAT_SLACK

    @property
    def inner_w(self):
        """Width above the cell pocket. The battery variant is wider: by the shoulders the frame
        rests on, and so that the corner bosses at the USB end stand clear beside the board, which
        reaches right up to that wall."""
        if not self.battery:
            return SIDE_W
        beside_board = 2 * (PCB_W / 2 + CLEAR + CORNER_IN + BOSS_R)
        return max(SIDE_W, self.bay_w + 2 * FRAME_LEDGE, beside_board)

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
        """Jack axis above the floor. USB: the body rests on the floor. Battery: it rests on the
        frame's cradle plate, above the cell."""
        if self.battery:
            return self.bay_h + RAIL_H + JACK.body_h / 2
        return max(5.0, JACK.body_h / 2 + 0.3)

    @property
    def inner_h(self):
        return max(self.jack_z + JACK.body_h / 2 + 0.6, self.board_z + USB_Z1 + 1.0)

    @property
    def pcb_x0(self):
        """PCB sits against the USB wall."""
        return self.inner_l - PCB_L

    @property
    def lip_xs(self):
        """Start x of the snap lips: one pair near the far end, one near the USB end."""
        usb = SNAP_X_USB if self.battery else SNAP_X
        return (self.pcb_x0 + SNAP_X - SNAP_L / 2, self.inner_l - usb - SNAP_L / 2)

    @property
    def lip_root(self):
        """Height the snap lips stand free from: the floor, or the thin floor of the pockets they
        rise through in the frame's rails."""
        return self.bay_h + SNAP_BASE if self.battery else 0.0

    @property
    def lip_room(self):
        """Free space behind a snap lip, to the wall (USB) or to the frame's web (battery)."""
        back = self.inner_w / 2 - (CLEAR + FRAME_WEB if self.battery else 0.0)
        return back - (PCB_W / 2 + CLEAR / 2 + SNAP_T)

    @property
    def snap_hook(self):
        """Hook size: as big as the lip's free height allows within SNAP_STRAIN (a cantilever bent
        by the hook takes 1.5 · t · hook / h²) and as the room behind it allows, up to SNAP_HOOK."""
        h = self.board_top + 0.1 - self.lip_root
        by_strain = SNAP_STRAIN * h * h / (1.5 * SNAP_T)
        return min(SNAP_HOOK, math.floor(min(by_strain, self.lip_room - 0.1) * 100) / 100)

    @property
    def screws(self):
        """Screw axes. USB: one pair of bosses along the long walls in the wiring bay, from the
        floor. Battery: one in each corner of the case, hanging from the top."""
        if self.battery:
            xs, y = (CORNER_IN, self.inner_l - CORNER_IN), self.inner_w / 2 - CORNER_IN
        else:
            xs, y = (JACK.depth + WIRE_BAY / 2,), self.inner_w / 2 - 0.6
        return [(x, sy * y) for x in xs for sy in (-1, 1)]

    @property
    def frame_bar_x(self):
        """Battery: the frame's cross bar, between the jack and the board."""
        return (JACK.depth + self.pcb_x0) / 2

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


def corner_boss(v: Variant, x, y, grow=0.0, z0=0.0, z1=0.0, slope=False):
    """Battery: the footprint of the boss in the corner nearest (x, y), from z0 to z1: the boss
    cylinder filled out to both walls (plain solid, outside any builder). It reaches past the walls,
    to be trimmed to the case outline or cut from parts inside. With slope, a 45° slope hangs below
    z0 and runs back into the walls, so the boss prints without supports."""
    sx = 1 if x < v.inner_l / 2 else -1        # into the room from the end wall
    sy = 1 if y > 0 else -1                     # towards the long wall
    xw, yw = (0.0 if sx > 0 else v.inner_l), sy * v.inner_w / 2
    r = BOSS_R + grow
    reach = CORNER_IN + BOSS_R + 0.5            # past the walls, so the slope still meets them

    def rect(xa, xb, ya, yb):
        with Locations(((xa + xb) / 2, (ya + yb) / 2)):
            Rectangle(abs(xb - xa), abs(yb - ya))

    with BuildPart() as p:
        with BuildSketch(Plane.XY.offset(z0)) as s:
            rect(xw - sx * reach, x + sx * r, y, yw + sy * reach)
            rect(xw - sx * reach, x, y - sy * r, yw + sy * reach)
            with Locations((x, y)):
                Circle(r)
        extrude(amount=z1 - z0)
        if slope:
            # down until the inner edge has receded to the walls
            extrude(s.sketch, amount=CORNER_IN + r, dir=(0, 0, -1), taper=45)
    return p.part


def snap_lip(v: Variant, x0, length, sy, zr):
    """Springy lip outside the board's long edge, from zr up: it locates the board in y and hooks
    v.snap_hook over its top edge, with a lead-in above the hook, so the board clicks in and stays
    put with the lid off. Above the lead-in it goes on straight as a tab, SNAP_TAB above the board,
    to push the lip open with a small screwdriver. Free on both sides from zr up; its free height
    to the hook sets how big the hook may be (see Variant.snap_hook)."""
    yi = PCB_W / 2 + CLEAR / 2                  # lip inner face
    yo = yi + SNAP_T                            # lip outer face
    yt = PCB_W / 2 - v.snap_hook                # hook tip, over the board
    zh = v.board_top + 0.1                      # hook underside
    zl = zh + SNAP_LEAD                         # top of the lead-in
    assert v.lip_room >= v.snap_hook + 0.1, "no room behind the lip to open it"
    assert zl < v.board_top + SNAP_TAB, "lead-in taller than the tab"
    zt = v.board_top + SNAP_TAB                 # tab top
    pts = [(sy * yi, zr), (sy * yi, zh), (sy * yt, zh), (sy * yi, zl), (sy * yi, zt), (sy * yo, zt),
           (sy * yo, zr)]
    with BuildPart() as p:
        with BuildSketch(Plane.YZ.offset(x0)):
            Polygon(*pts, align=None)
        extrude(amount=length)
    return p.part


def frame(v: Variant):
    """Battery variant: drops in on top of the cell, past the base's corner bosses (it is cut away
    round them), and carries the board and the jack. Two low rails rest on the shoulders above the
    cell pocket, joined by a cross bar between the jack and the board, by the jack's cradle at the
    jack end and by a cross wall at the USB end; on them stand the board brackets and the snap
    lips. The lid's screws go into the base; the lid holds the frame down through the board. Flat
    underneath: it prints as it sits, without supports.

    Brackets: four 45° wedges carry the board's corners; 2 mm long at the USB end so they stay
    clear of the first castellated pad, which may carry a wire soldered from below. The far pair
    reaches back behind the board and carries the end stops. The snap lips (see snap_lip) rise
    free from the frame's underside through pockets in the rails, between the first and second
    castellated pad, where the board's edge is straight; at the corners it is rounded and the hook
    would not reach it. A web along the outside of each rail makes the rails L-shaped, and a cross
    wall at the USB end carries the board's end."""
    L, H = v.inner_l, v.inner_h
    z0, zt = v.bay_h, v.bay_h + RAIL_H          # frame bottom, rail top
    yo = v.inner_w / 2 - CLEAR                  # outer faces, against the walls
    yi = PCB_W / 2 + 0.1                        # rails' inner faces, under the snap lips
    y_in = PCB_W / 2 - BRACKET_IN               # brackets' inner edge, under the board
    reach = v.board_z - zt
    assert y_in + reach >= yi, "brackets would overhang the rails"
    assert SNAP_BASE < RAIL_H, "pocket floor as thick as the rail"
    with BuildPart() as p:
        for sy in (-1, 1):
            with Locations((L / 2, sy * (yi + yo) / 2, z0)):
                Box(L - 2 * CLEAR, yo - yi, RAIL_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # web along the outside, up to the board: L-shaped rails, much stiffer than flat ones
            with Locations((L / 2, sy * (yo - FRAME_WEB / 2), z0)):
                Box(L - 2 * CLEAR, FRAME_WEB, v.board_z - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # cross wall at the USB end, under the board's end: ties the rails there and carries the
        # board across its full width
        with Locations((L - CLEAR, 0, z0)):
            Box(1.2, 2 * yi, v.board_z - z0, align=(Align.MAX, Align.CENTER, Align.MIN))
        # the corner bosses at the USB end cut the rails short of the cross wall there: a bar under
        # each of the board's long edges ties the cross wall back to the rails
        x_cut = L - (CORNER_IN + BOSS_R + CLEAR)
        for sy in (-1, 1):
            y0, y1 = PCB_W / 2 - 1.3, yi + 0.5
            with Locations(((x_cut - 1.0 + L - CLEAR) / 2, sy * (y0 + y1) / 2, z0)):
                Box(L - CLEAR - (x_cut - 1.0), y1 - y0, RAIL_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # cross bar between the jack and the board, so the frame is one part; wires pass over it
        with Locations((v.frame_bar_x, 0, z0)):
            Box(1.5, 2 * yi, RAIL_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # cradle for the jack: a plate it rests on, over the connector bay, and a cheek either side,
        # so board, jack and frame go in as one; the plate also ties the rails at this end
        cradle_l = JACK.depth - 5.0
        with Locations((CLEAR, 0, z0)):
            Box(cradle_l, 2 * yi, RAIL_H, align=(Align.MIN, Align.CENTER, Align.MIN))
        for sy in (-1, 1):
            y_c = JACK.body_w / 2 + CLEAR / 2
            with Locations((CLEAR, sy * (y_c + yi) / 2, zt)):
                Box(cradle_l, yi - y_c, v.jack_z - zt, align=(Align.MIN, Align.CENTER, Align.MIN))
        for x0, length, stop in ((L - 2.0, 2.0, False), (v.pcb_x0 - CLEAR - 0.8, 2.0 + CLEAR + 0.8, True)):
            for sy in (-1, 1):
                pts = [(sy * y_in, v.board_z), (sy * yo, v.board_z), (sy * yo, zt), (sy * (y_in + reach), zt)]
                with BuildSketch(Plane.YZ.offset(x0)):
                    Polygon(*pts, align=None)
                extrude(amount=length)
                if stop:
                    # end stop behind the board, so a pushed-in USB plug cannot shove it back
                    with Locations((x0 + 0.4, sy * (PCB_W / 2 - BRACKET_IN / 2), v.board_z)):
                        Box(0.8, BRACKET_IN + 1.0, 1.2, align=(Align.CENTER, Align.CENTER, Align.MIN))
        for x0 in v.lip_xs:
            for sy in (-1, 1):
                # pocket in the rail down to a thin floor, so the lip rises free from just above the
                # frame's underside: taller, so it bends further and takes a bigger hook; the floor
                # ties it to the rail and the web
                y_back = yo - FRAME_WEB
                with Locations((x0 + SNAP_L / 2, sy * (yi + y_back) / 2, v.lip_root)):
                    Box(SNAP_L + 2 * SNAP_GAP, y_back - yi, zt - v.lip_root,
                        align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
                insert(snap_lip(v, x0, SNAP_L, sy, v.lip_root))
        # trim to the space above the shoulders, rounded like the case's inside
        with Locations((L / 2, 0, z0)):
            with BuildSketch(mode=Mode.PRIVATE) as trim:
                RectangleRounded(L - 2 * CLEAR, 2 * yo, CORNER_R - WALL - CLEAR)
        extrude(trim.sketch, amount=H - z0, mode=Mode.INTERSECT)
        # leave the case's corner bosses free over the frame's whole height, so it drops in past them
        for x, y in v.screws:
            insert(corner_boss(v, x, y, CLEAR, z0, H), mode=Mode.SUBTRACT)
    return p.part


def base(v: Variant):
    outer_l, outer_w, _ = v.outer
    L, H = v.inner_l, v.inner_h
    with BuildPart() as p:
        with Locations((L / 2, 0, -FLOOR)):
            with BuildSketch():
                RectangleRounded(outer_l, outer_w, CORNER_R)
            extrude(amount=FLOOR + H)
        outline = copy.copy(p.part)
        # battery: a pocket for the cell, and above it shoulders along the long walls for the frame
        z_wide = v.bay_h if v.battery else 0.0
        with Locations((L / 2, 0, z_wide)):
            with BuildSketch():
                RectangleRounded(L, v.inner_w, CORNER_R - WALL)
            extrude(amount=H - z_wide, mode=Mode.SUBTRACT)
        if v.battery:
            with Locations((L / 2, 0, 0)):
                with BuildSketch():
                    RectangleRounded(L, v.bay_w, CORNER_R - WALL)
                extrude(amount=v.bay_h, mode=Mode.SUBTRACT)
            # low floor rib between the connector bay (under the jack) and the cell, with a gap for
            # the cell's lead
            seg = (v.bay_w - LEAD_GAP) / 2
            for sy in (-1, 1):
                with Locations((CONN_L, sy * (LEAD_GAP / 2 + seg / 2), 0)):
                    Box(RIB_T, seg, RIB_H, align=(Align.MIN, Align.CENTER, Align.MIN))
            # a boss hanging in each corner from the top, for the lid's screws; the cell goes in
            # tilted, USB end first, as its far corners reach under the bosses at that end
            for x, y in v.screws:
                insert(corner_boss(v, x, y, z0=H - CORNER_DEPTH, z1=H, slope=True) & outline)
                with Locations((x, y, H)):
                    Cylinder(PILOT_D / 2, CORNER_PILOT, align=(Align.CENTER, Align.CENTER, Align.MAX),
                             mode=Mode.SUBTRACT)
        else:
            for x, y in v.screws:
                insert(boss_footprint(x, y, height=H))
                with Locations((x, y, H)):
                    Cylinder(PILOT_D / 2, H - 1.0, align=(Align.CENTER, Align.CENTER, Align.MAX),
                             mode=Mode.SUBTRACT)

        if not v.battery:
            # board supports: four corner pads under the PCB, and four snap lips that stand free
            # from the floor beside the straight stretch of the long edges (see SNAP_X)
            pad = 3.0
            bz = v.board_z
            for px, lx in zip((v.pcb_x0 + pad / 2, L - pad / 2), v.lip_xs):
                for sy in (-1, 1):
                    # set back from the edge so the lip stays free to bend
                    with Locations((px, sy * (PCB_W / 2 - 0.6 - pad / 2), 0)):
                        Box(pad, pad, bz, align=(Align.CENTER, Align.CENTER, Align.MIN))
                    insert(snap_lip(v, lx, SNAP_L, sy, 0.0))
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

        # 3.5 mm jack through the end wall, spot-faced inside where the thread needs a thinner panel;
        # both open to the top as a slot, so the jack drops in already soldered to the board (the
        # lid closes the slot with a tab)
        with Locations(Location((-WALL / 2, 0, v.jack_z), (0, 90, 0))):
            Cylinder(JACK.hole / 2, WALL + 2, mode=Mode.SUBTRACT)
        with Locations((-WALL / 2, 0, v.jack_z)):
            Box(WALL + 2, JACK.hole, H, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        if JACK.panel < WALL:
            spot = 2 * (WALL - JACK.panel)
            with Locations(Location((0, 0, v.jack_z), (0, 90, 0))):
                Cylinder(SPOT_D / 2, spot, mode=Mode.SUBTRACT)
            with Locations((0, 0, v.jack_z)):
                Box(spot, SPOT_D, H, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
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
            if v.battery:
                insert(corner_boss(v, x, y, CLEAR, H - LIP_H, H), mode=Mode.SUBTRACT)
            else:
                insert(boss_footprint(x, y, CLEAR, LIP_H, H - LIP_H), mode=Mode.SUBTRACT)
        if JACK.round:
            with Locations(Location((LIP_T + 1.0, 0, v.jack_z), (0, 90, 0))):
                Cylinder(JACK.body_w / 2 + 0.5, 2 * (LIP_T + 1.0), mode=Mode.SUBTRACT)
        else:
            # square body: cut the lip back over it (the floor or the frame's cradle keeps it from
            # turning when the nut is tightened)
            body_top = v.jack_z + JACK.body_h / 2
            if body_top + CLEAR > H - LIP_H:
                with Locations((0, 0, H - LIP_H)):
                    Box(LIP_T + CLEAR + 1.0, JACK.body_w + 2 * CLEAR + 1.0, body_top + CLEAR - (H - LIP_H),
                        align=(Align.MIN, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
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

        # tab that closes the jack slot down to the thread, hollowed round it; only in the panel
        # (outer part of the wall), the spot face behind it stays open
        with BuildPart(mode=Mode.PRIVATE) as jack_tab:
            with Locations((-WALL + JACK.panel / 2, 0, H)):
                Box(JACK.panel, JACK.hole - 0.2, H - v.jack_z, align=(Align.CENTER, Align.CENTER, Align.MAX))
            with Locations(Location((-WALL + JACK.panel / 2, 0, v.jack_z), (0, 90, 0))):
                Cylinder(JACK.hole / 2, JACK.panel + 1, mode=Mode.SUBTRACT)
        insert(jack_tab.part)

        # hold-down on the PCB's far corners, on bare board on both the XIAO ESP32-S3 and the
        # XIAO nRF52840 (clear of the S3's U.FL socket, a small part on the nRF52840, and the pin pads)
        for sy in (-1, 1):
            # an L-shaped rib hung from the lid's lip, stiffer than a free pin: it presses right
            # above the far support
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
    """Stand-in for the preview: body, lugs or pins, thread and nut."""
    z = v.jack_z
    if JACK.round:
        body = Cylinder(JACK.body_w / 2, JACK.depth - 2, rotation=(0, 90, 0)).translate(
            ((JACK.depth - 2) / 2 - (WALL - JACK.panel), 0, z))
        lugs = Box(2.5, 6.0, 0.6).translate((JACK.depth - 1.5, 0, z))
    else:
        body_l = JACK.depth - 4.0
        # 10.5 wide in reality (5.0 / 5.5 either side of the axis); the pocket allows 11
        body = Box(body_l, 10.5, JACK.body_h).translate((body_l / 2, 0.25, z))
        lugs = Box(4.0, 8.6, 1.0).translate((body_l + 2.0, 0, z - 1.0))
    thread = Cylinder(JACK.thread_d / 2, 4.5, rotation=(0, 90, 0)).translate((-2.25, 0, z))
    nut = Cylinder(JACK.nut_d / 2, JACK.nut_t, rotation=(0, 90, 0)).translate(
        (-WALL - JACK.nut_t / 2, 0, z))
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
    printed = {"base": b, "lid": l}
    if v.battery:
        printed["frame"] = frame(v)
    for name, part in printed.items():
        assert len(part.solids()) == 1, f"{v.name} {name} is in {len(part.solids())} pieces"
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
    for name, part in {**printed, **others}.items():
        glb = out / f"preview-{name}.glb"
        export_gltf(part, str(glb), binary=True, linear_deflection=0.01, angular_deflection=0.2)
        glb.with_suffix(".b64.txt").write_text(base64.b64encode(glb.read_bytes()).decode())
        glb.unlink()

    print(f"{v.name}: outer {v.outer[0]:.1f} x {v.outer[1]:.1f} x {v.outer[2]:.1f} mm")
    names = list(printed)
    pairs = [(an, printed[an], bn, printed[bn]) for i, an in enumerate(names) for bn in names[i + 1:]]
    pairs += [(pn, pp, on, op) for on, op in others.items() for pn, pp in printed.items()]
    for an, a, bn, bb in pairs:
        clash = a & bb
        vol = clash.volume if clash else 0
        if vol > 0.01:
            print(f"  overlap {an}/{bn}: {vol:.3f} mm3")


def snap_test():
    """Test pieces for the snap lips, FDM fit only: a short slice around the board's far-end
    supports, cut just above the lips' tabs, plus a stand-in for the board's end to click in. USB:
    a slice of the base (floor, walls, supports, snap lips, end stop). Battery: a slice of the
    frame (rails, brackets, snap lips, end stops) on a plate that stands in for the case walls
    holding the rails apart. Written to out/snap-test-fdm/, each part flat on the bed. Prints in
    minutes; tune SNAP_* before printing a whole case."""
    out = OUT / "snap-test-fdm"
    out.mkdir(parents=True, exist_ok=True)
    pieces, board_dz = {}, {}
    for v in (Variant("usb-fdm", battery=False), Variant("battery-fdm", battery=True)):
        x0, x1 = v.pcb_x0 - CLEAR - 1.4, v.lip_xs[0] + SNAP_L + 0.8
        top = v.board_top + SNAP_TAB + 0.5
        keep = Pos((x0 + x1) / 2, 0, (top - FLOOR) / 2) * Box(x1 - x0, 60, top + FLOOR)
        if v.battery:
            yo = v.inner_w / 2 - CLEAR
            plate = Pos((x0 + x1) / 2, 0, v.bay_h + RAIL_H / 2) * Box(x1 - x0, PCB_W + 0.2, RAIL_H)
            piece = (frame(v) & keep) + plate
        else:
            piece = base(v) & keep
        bb = piece.bounding_box()
        name = v.name.replace("-fdm", "")
        pieces[name] = piece.translate((-bb.min.X, 0, -bb.min.Z))
        board_dz[name] = v.board_z - bb.min.Z
    # the board's far end: full width, PCB thickness, long enough to hold on to
    pieces["board"] = Box(15.0, PCB_W, PCB_T).translate((0, 0, PCB_T / 2))
    for name, part in pieces.items():
        assert len(part.solids()) == 1, f"snap test {name} is in {len(part.solids())} pieces"
        export_stl(part, out / f"ble-key-snap-test-{name}.stl", tolerance=0.01, angular_tolerance=0.1)
        bb = part.bounding_box()
        print(f"snap test {name}: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")

    # preview: the two slices side by side across the view from the jack end, each with the stand-in clicked in (it reaches past the
    # slice towards where the USB end would be)
    shown, boards = {}, []
    for i, (name, battery) in enumerate((("usb", False), ("battery", True))):
        v = Variant(name, battery=battery)
        dy = (0.5 - i) * 32.0                   # USB slice on the left seen from the jack end
        # built inside BuildPart so the placement is baked into the geometry; the glTF exporter
        # mishandles located shapes (see battery())
        with BuildPart() as piece:
            with Locations((0, dy, 0)):
                insert(pieces[name])
        shown[f"test-{name}"] = piece.part
        boards.append((CLEAR + 1.4 + 7.5, dy, board_dz[name] + PCB_T / 2))
    with BuildPart() as stand_ins:
        with Locations(*boards):
            Box(15.0, PCB_W, PCB_T)
    shown["board"] = stand_ins.part
    for name, part in shown.items():
        glb = out / f"preview-{name}.glb"
        export_gltf(part, str(glb), binary=True, linear_deflection=0.01, angular_deflection=0.2)
        glb.with_suffix(".b64.txt").write_text(base64.b64encode(glb.read_bytes()).decode())
        glb.unlink()
    clash = (shown["test-usb"] + shown["test-battery"]) & shown["board"]
    if clash and clash.volume > 0.01:
        print(f"  overlap pieces/board: {clash.volume:.3f} mm3")


def main():
    global CLEAR, JACK
    if "--jack" in sys.argv:
        JACK = JACKS[sys.argv[sys.argv.index("--jack") + 1]]
    if "--snap-test" in sys.argv:
        CLEAR = 0.35
        snap_test()
        return
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
