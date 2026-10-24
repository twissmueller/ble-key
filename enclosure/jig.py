"""Soldering jig for a Seeed XIAO (ESP32-S3 or nRF52840): a flat plate that a PCB holder (e.g. the
DONAU PPH4) clamps like a board, with the XIAO held on top.

The XIAO rests on two ledges under its short ends, 5 mm above the plate, over a window: its long
edges with all the castellated pads are free from above, from the side and from below (turn the
holder over to reach the underside). Two holders grip it, both at the short ends, away from the
pads, so the iron cannot melt them:

- At the USB end a rigid block hooks over the USB-C socket's metal shell where it reaches past the
  board. It does not flex at all: the board goes in tilted, shell first under the hook, and is then
  lowered at its far end. The block is joined to the two posts beside the shell, which centre the
  board, and braced against the plate by gussets on both sides.
- At the far end a springy clip hooks over the board's end, in the one gap that is free of parts on
  both boards, and clicks in as the board is lowered. It stands on a wide body beyond the board,
  with gussets at its root so it does not break there.

The first version flexed both holders, 1.2 mm thick with sharp roots; printed upright they bend
across the layers and snapped at the root.

Run with

    .venv/bin/python jig.py

to write out/jig/ble-key-xiao-jig.stl (flat on the bed as written, no supports) and a STEP.

Frame: the board's far end at x = 0, USB end at +x, centred on y = 0. All dimensions in mm.
"""

import copy
import math
from pathlib import Path

from build123d import *

HERE = Path(__file__).parent
OUT = HERE / "out" / "jig"

CLEAR = 0.3         # FDM fit around the board
PLATE_L, PLATE_W, PLATE_T = 100.0, 40.0, 1.6     # clamped like a 1.6 mm board
LIFT = 5.0          # board underside above the plate: room for wires and the iron underneath,
                    # and a long enough spring for the far clip
LEDGE = 1.2         # how far each ledge reaches under the board's end
LEDGE_W = 13.0      # ledge width (y): inside the rounded corners
WINDOW_W = 26.0     # window across (y): wider than the board, so the pads are free from below

PCB_L, PCB_T = 20.95, 1.25                      # Seeed's STEP models
USB_OVER = 1.53     # USB-C shell beyond the board's end
USB_HALF = 4.47     # half its width
USB_TOP = 4.46      # its top above the board's underside

# USB end: rigid block
USB_T = 3.0         # block thickness (x)
USB_W = 16.0        # block width (y), centred
USB_HOOK = 0.8      # hook over the USB-C shell
USB_HOOK_W = 8.0    # its width (the shell is 8.94 wide)
USB_GAP = 0.2       # hook underside above the shell: the hook does not flex, so a little more play
USB_GUSSET = 3.0    # gusset on the outer side; the posts brace the inner side

# far end: springy clip
CLIP_T = 1.6        # clip thickness
CLIP_W = 16.0       # clip body width (y), centred: it stands beyond the board, so it can be wide
CLIP_GUSSET = 0.8   # gussets at the root on both sides: no sharp corner for a crack to start in
CLIP_STRAIN = 0.04  # bending strain the clip may take while the board clicks in (PETG)
CLIP_HOOK = 0.8     # at most this far over the board's end
CLIP_GAP = 0.1      # hook underside above the board
# far-end hook (centre y, width): in the gap that is free of parts on both the XIAO ESP32-S3 and the
# XIAO nRF52840 (checked against the STEP models in main)
FAR_HOOK = (-1.3, 2.3)

HOOK_LEAD = 1.0     # lead-in above each hook
HOOK_FLAT = 0.4     # flat front on each hook tip instead of a sharp edge

Z_PLATE = PLATE_T
Z_BOARD = PLATE_T + LIFT


def clip_hook():
    """Hook size for the far clip: as big as its free height (above the gussets, up to the hook)
    allows within CLIP_STRAIN (a cantilever bent by the hook takes 1.5 · t · hook / h²), up to
    CLIP_HOOK."""
    h = Z_BOARD + PCB_T + CLIP_GAP - (Z_PLATE + CLIP_GUSSET)
    return min(CLIP_HOOK, math.floor(CLIP_STRAIN * h * h / (1.5 * CLIP_T) * 100) / 100)


def holder(end, t, body_w, hook, hook_yc, hook_w, gap, gusset_in, gusset_out, tab):
    """A holder beyond one short end (end = +1 at the USB end, -1 at the far end), standing on the
    plate: a body `t` thick, centred, with gussets at its root, and a hook only where there is room
    for it, over the USB-C shell or over the board's end; a lead-in above the hook, and on a clip
    a tab above that to push it open."""
    edge, top = (PCB_L + USB_OVER, USB_TOP) if end > 0 else (0.0, PCB_T)
    xi = edge + end * CLEAR                     # inner face, towards the board
    xo = xi + end * t                           # outer face
    xt = edge - end * hook                      # hook tip
    zh = Z_BOARD + top + gap                    # hook underside
    zl = zh + HOOK_FLAT + HOOK_LEAD             # top of the lead-in
    zt = zl + (1.0 if tab else 0.0)             # body top
    body = [(xi - end * gusset_in, Z_PLATE), (xi, Z_PLATE + gusset_in), (xi, zt), (xo, zt),
            (xo, Z_PLATE + gusset_out), (xo + end * gusset_out, Z_PLATE)]
    hook_pts = [(xi, zh), (xt, zh), (xt, zh + HOOK_FLAT), (xi, zl)]
    with BuildPart() as p:
        # Plane.XZ faces -y: start at the +y side and extrude towards -y
        for pts, yc, w in ((body, 0.0, body_w), (hook_pts, hook_yc, hook_w)):
            with BuildSketch(Plane.XZ.offset(-(yc + w / 2))):
                Polygon(*pts, align=None)
            extrude(amount=w)
    bb = p.part.bounding_box()
    assert abs(bb.min.Y + body_w / 2) < 0.01, "holder extruded the wrong way"
    return p.part


def jig():
    with BuildPart() as p:
        with Locations((PCB_L / 2, 0, 0)):
            with BuildSketch():
                RectangleRounded(PLATE_L, PLATE_W, 3.0)
            extrude(amount=PLATE_T)
            # window under the board, between the two ledges
            Box(PCB_L - 2 * LEDGE, WINDOW_W, PLATE_T, align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)
        # ledges under the board's two ends
        for x0 in (0.0, PCB_L - LEDGE):
            with Locations((x0, 0, Z_PLATE)):
                Box(LEDGE, LEDGE_W, LIFT, align=(Align.MIN, Align.CENTER, Align.MIN))
        insert(holder(+1, USB_T, USB_W, USB_HOOK, 0.0, USB_HOOK_W, USB_GAP, 0.0, USB_GUSSET,
                      tab=False))
        insert(holder(-1, CLIP_T, CLIP_W, clip_hook(), *FAR_HOOK, CLIP_GAP, CLIP_GUSSET,
                      CLIP_GUSSET, tab=True))
        # posts beside the USB-C shell where it reaches past the board: they centre the board and,
        # running into the block, brace it from the inside
        for sy in (-1, 1):
            with Locations((PCB_L + CLEAR, sy * (USB_HALF + CLEAR), Z_PLATE)):
                Box(USB_OVER, 1.0, LIFT + USB_TOP,
                    align=(Align.MIN, Align.MIN if sy > 0 else Align.MAX, Align.MIN))
    return p.part


def boards():
    """Both XIAO models, seated on the ledges."""
    out = {}
    for name, f in (("ESP32-S3", HERE / "vendor" / "XIAO-ESP32S3 v2.step"),
                    ("nRF52840", HERE / "vendor" / "nrf" / "XIAO-nRF52840 v15.step")):
        x = import_step(f).rotate(Axis.X, 90)
        pcb = sorted(x.solids(), key=lambda s: -s.volume)[0].bounding_box()
        placed = x.translate((-pcb.min.X, -pcb.center().Y, Z_BOARD - pcb.min.Z))
        # flatten the STEP assembly, or booleans re-apply its nested locations
        out[name] = Compound([copy.copy(s) for s in placed.solids()])
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    j = jig()
    assert len(j.solids()) == 1, f"jig is in {len(j.solids())} pieces"
    for name, b in boards().items():
        pcb = sorted(b.solids(), key=lambda s: -s.volume)[0].bounding_box()
        assert abs(pcb.size.X - PCB_L) < 0.05 and abs(pcb.min.Z - Z_BOARD) < 0.01, name
        clash = j & b
        vol = clash.volume if clash else 0
        assert vol < 0.001, f"jig overlaps the XIAO {name}: {vol:.3f} mm3"
    export_stl(j, OUT / "ble-key-xiao-jig.stl", tolerance=0.01, angular_tolerance=0.1)
    export_step(j, OUT / "ble-key-xiao-jig.step")
    bb = j.bounding_box()
    print(f"jig: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm; hooks: "
          f"{USB_HOOK} mm over the USB-C shell (rigid), {clip_hook()} mm over the far end")


if __name__ == "__main__":
    main()
