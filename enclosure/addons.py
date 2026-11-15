"""Add-ons for the BLE Key Modular, for prompting in Frame: a foot pedal and a hand switch.

Both take the Modular as it is and connect to it only through its 3.5 mm jack, with a stereo plug
wired the way the key expects: tip = dit (Frame: forward), ring = dah (Frame: back), sleeve = GND.
Nothing inside the Modular changes.

- pedal:  two foot keys side by side (left back, right forward) on Cherry-MX-style switches, a
          return spring under each key, and a pocket at the toe end that the Modular drops into.
          The Modular slides into a tunnel in the toe block from the pedal's right side, onto
          the fixed plug, and stands out of the side a little so it can be pulled out again.
          The plug lies in a cradle open to the top, closed by a small lid with the Modular's
          own countersunk screws.
- hand:   a sleeve that slides over the Modular's jack end; the plug in its end block goes into
          the jack as it slides home. On top a wiring bay, open to the top: the plug in the same
          cradle as in the pedal, two 12 x 12 mm tactile buttons on the bay's floor (front
          forward, rear back), the wires beside them, and a flush lid with four screws.

Both are made for the Modular with its battery tray: in the hand and under the foot the key has to
run on its battery.

All parts are for FDM (PETG), 0.35 mm fit, and fit a 180 x 180 mm bed (Bambu Lab A1 mini).

    .venv/bin/python addons.py           # out/pedal-fdm/, out/hand-fdm/
    .venv/bin/python addons.py --views   # also PNG views in out/addons-views/ (needs vtk)

The Modular's dimensions come from enclosure.py (Variant "modular-fdm"), so the add-ons follow
any change there. Modular frame used here: jack end face at x = 0, USB end at x = MOD_L, centred
on y = 0, z = 0 at the base's underside (the battery tray hangs below it, down to -TRAY_H).

Bought parts whose sizes are assumed, not measured (see README, "Add-ons"):
MX_* (Cherry MX footprint),
TACT_* (12 x 12 mm tactile switch), SPRING_* (compression spring).
"""

import math
import sys
from pathlib import Path

from build123d import *

import enclosure as enc

HERE = Path(__file__).parent
OUT = HERE / "out"

C = 0.35            # FDM fit clearance, as enclosure.py --fdm

# --- the Modular, from enclosure.py --------------------------------------------------------
_V = enc.Variant("modular-fdm", battery=False, modular=True)
MOD_L, MOD_W, MOD_H = _V.outer                       # 57.9 x 30.5 x 14.46
TRAY_H = _V.tray_h                                   # 10.3
JACK_Z = enc.FLOOR + _V.jack_z                       # jack axis above the base's underside (7.0)
NUT_OUT = enc.JACK.nut_t + 0.5                       # ring nut plus the thread beyond it (2.5)
NUT_D = enc.JACK.nut_d
USB_Z = enc.FLOOR + _V.board_z + (enc.USB_Z0 + enc.USB_Z1) / 2   # USB-C centre above the underside
LED_X = enc.WALL + _V.inner_l - enc.LED_DX           # light holes, from the jack end face

# --- 3.5 mm stereo plug: Rean NYS231, metal, handle left on (docs/TZ_NYS231.pdf) ---------------
# 39.0 long overall, body Ø 9.0, cable hole Ø 4.5 (dimensioned); shaft and body lengths are taken
# off the drawing's scale, not dimensioned: check on the real part.
PLUG_SHAFT = 14.7   # tip to the body's nose
PLUG_D = 9.0
PLUG_BODY = 39.0 - PLUG_SHAFT   # 24.3
PLUG_BORE = PLUG_D + 0.3
# The plug's cradle, the same in both add-ons, along the jack's axis from the wall face backwards:
# a recess the ring nut goes into, a U-shaped lip the body's nose rests on (the Ø 9 body cannot
# pass), a trough for the body, two shoulders behind its end. It is open to the top, so the plug
# drops in, and a lid's tongue holds it down.
FACE_GAP = 1.5      # wall face to the Modular's end face; the nut reaches SEAT_RECESS into the wall
SEAT_RECESS = NUT_OUT - FACE_GAP
SEAT_LIP = 1.0
SEAT_LIP_D = 7.5
WIRE_SLOT = 5.0

# --- Cherry MX-style switch, plate mount ----------------------------------------------------
MX_CUT = 14.0       # square plate cut-out
MX_PLATE = 1.5      # plate thickness the clips need
MX_BELOW = 8.5      # body plus pins below the plate's top
MX_STEM = 10.2      # stem top above the plate's top, at rest (assumed)
MX_TRAVEL = 4.0

# --- 12 x 12 mm tactile switch (body 12 x 12 x 3.5, 7.3 to the top of the actuator) -----------
TACT = 12.0
TACT_BODY = 3.6
TACT_POCKET = TACT + 0.3

# --- return spring under each foot key --------------------------------------------------------
SPRING_D = 8.0      # outer diameter (assumed: 8 x 20 mm, about 0.3 N/mm)
SPRING_POCKET = 5.0


def views(name, parts, out, elev_azims=((25, -60), (25, 120), (80, -90)), size=(1600, 1200)):
    """PNG views of a set of parts, one file per angle. Needs vtk (uv pip install vtk); only run
    with --views. Angles are elevation above the floor and azimuth round z, in degrees."""
    import tempfile
    import vtk

    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    with tempfile.TemporaryDirectory() as tmp:
        for i, (part, color) in enumerate(parts):
            path = str(Path(tmp) / f"{i}.stl")
            export_stl(part, path, tolerance=0.02, angular_tolerance=0.2)
            reader = vtk.vtkSTLReader()
            reader.SetFileName(path)
            reader.Update()
            normals = vtk.vtkPolyDataNormals()
            normals.SetInputConnection(reader.GetOutputPort())
            normals.SetFeatureAngle(30)
            normals.Update()
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(normals.GetOutput())
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            rgb = [int(color[k:k + 2], 16) / 255 for k in (1, 3, 5)]
            actor.GetProperty().SetColor(*rgb)
            actor.GetProperty().SetAmbient(0.25)
            actor.GetProperty().SetDiffuse(0.75)
            actor.GetProperty().SetSpecular(0.1)
            ren.AddActor(actor)
            edges = vtk.vtkFeatureEdges()
            edges.SetInputData(normals.GetOutput())
            edges.BoundaryEdgesOff(); edges.NonManifoldEdgesOff(); edges.ManifoldEdgesOff()
            edges.FeatureEdgesOn(); edges.SetFeatureAngle(30)
            emap = vtk.vtkPolyDataMapper()
            emap.SetInputConnection(edges.GetOutputPort())
            emap.ScalarVisibilityOff()
            emap.SetResolveCoincidentTopologyToPolygonOffset()
            eact = vtk.vtkActor()
            eact.SetMapper(emap)
            eact.GetProperty().SetColor(0.1, 0.1, 0.1)
            eact.GetProperty().SetLineWidth(1.5)
            ren.AddActor(eact)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.AddRenderer(ren)
    win.SetSize(*size)
    for i, (elev, azim) in enumerate(elev_azims):
        cam = ren.GetActiveCamera()
        e, a = math.radians(elev), math.radians(azim)
        cam.SetFocalPoint(0, 0, 0)
        cam.SetPosition(math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))
        cam.SetViewUp(0, 0, 1) if abs(elev) < 80 else cam.SetViewUp(0, 1, 0)
        cam.ParallelProjectionOn()
        ren.ResetCamera()
        cam.Zoom(1.25)
        win.Render()
        grab = vtk.vtkWindowToImageFilter()
        grab.SetInput(win)
        grab.Update()
        writer = vtk.vtkPNGWriter()
        writer.SetFileName(str(out / f"{name}-{i + 1}.png"))
        writer.SetInputConnection(grab.GetOutputPort())
        writer.Write()


def modular_stand_in(tray: bool):
    """The Modular as a block, with nut and USB-C opening, for views and clash checks."""
    z0 = -TRAY_H if tray else 0.0
    with BuildPart() as p:
        with Locations((MOD_L / 2, 0, z0)):
            with BuildSketch():
                RectangleRounded(MOD_L, MOD_W, enc.CORNER_R)
            extrude(amount=MOD_H - z0)
        with Locations(Location((-NUT_OUT / 2, 0, JACK_Z), (0, 90, 0))):
            Cylinder(NUT_D / 2, NUT_OUT)
        with Locations((MOD_L, 0, USB_Z)):
            Box(2.0, 9.0, 3.2, mode=Mode.SUBTRACT)
    return p.part


def plug_stand_in(x0=-FACE_GAP - SEAT_RECESS - SEAT_LIP):
    """Plug in the Modular frame: its body's nose at x0 (by default on the seat's lip), shaft into
    the jack, body behind."""
    with BuildPart() as p:
        with Locations(Location((x0 + PLUG_SHAFT / 2, 0, JACK_Z), (0, 90, 0))):
            Cylinder(1.75, PLUG_SHAFT)
        with Locations(Location((x0 - PLUG_BODY / 2, 0, JACK_Z), (0, 90, 0))):
            Cylinder(PLUG_D / 2, PLUG_BODY)
    return p.part


# ============================================================================================
# Hand switch: a sleeve over the jack end with the plug in its end block and two buttons on top
# ============================================================================================

HAND_WALL = 2.0
HAND_REACH = 40.0           # how far the sleeve reaches over the Modular from its jack end
POD_H = 6.0                 # wiring bay on top of the sleeve, lid included
POD_W = MOD_W + 2 * C + 2 * HAND_WALL   # as wide as the sleeve: one block, no step
POD_WALL = 2.0
HAND_LID_T = 2.0
BTN_X = (8.0, 26.0)         # rear button (back / dah / ring), front button (forward / dit / tip)
TACT_STEM_D = 7.0           # the button's round actuator (assumed)
HAND_BOSS = 5.0             # corner bosses in the bay for the lid's screws


def hand_x():
    """Back and open end of the hand switch in the Modular frame. The end block holds the plug's
    cradle: nut recess, lip, the plug's body, the wire slot behind it and a 3 mm end wall."""
    x_back = CRADLE_X0 - CRADLE_WIRES - 3.0
    return x_back, HAND_REACH


def hand_lid_screws():
    x_back, x_open = hand_x()
    d = POD_WALL + HAND_BOSS / 2
    return [(x, sy * (POD_W / 2 - d)) for x in (x_back + d, x_open - d) for sy in (-1, 1)]


def hand(tray: bool):
    """Sleeve with a wiring bay on top, open to the top and closed by hand_lid(). Everything is
    fitted from above: the plug drops into its cradle (as in the pedal), its wires come up behind
    it into the bay and run along both sides of the buttons, which sit on the bay's floor between
    low ribs. No closed channels to thread wires through."""
    zb = (-TRAY_H if tray else 0.0) - C          # sleeve inside, bottom
    zt = MOD_H + C                               # sleeve inside, top
    yi = MOD_W / 2 + C
    x_face = -FACE_GAP                           # end wall face; the nut goes into the cradle's recess
    x_back, x_open = hand_x()
    top = zt + HAND_WALL                         # top of the sleeve, floor of the bay
    bay_h = POD_H - HAND_LID_T
    with BuildPart() as p:
        # one block: sleeve, end block and the bay's walls, rounded along the bottom edges
        with Locations(((x_back + x_open) / 2, 0, zb - HAND_WALL)):
            Box(x_open - x_back, POD_W, top + bay_h - zb + HAND_WALL, align=(Align.CENTER, Align.CENTER, Align.MIN))
        fillet(p.edges().filter_by(Axis.X).group_by(Axis.Z)[0], radius=1.5)
        # the bay, open to the top
        with Locations(((x_back + x_open) / 2, 0, top)):
            Box(x_open - x_back - 2 * POD_WALL, POD_W - 2 * POD_WALL, bay_h + 1,
                align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # corner bosses for the lid's screws
        for x, y in hand_lid_screws():
            with Locations((x, y, top)):
                Box(HAND_BOSS, HAND_BOSS, bay_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # the buttons sit on the bay's floor: a rib along each side without legs, a post at the
        # middle of each side with legs (between the two legs)
        for bx in BTN_X:
            for sy in (-1, 1):
                with Locations((bx, sy * (TACT_POCKET / 2 + 0.6), top)):
                    Box(8.0, 1.2, 2.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
            for sx in (-1, 1):
                with Locations((bx + sx * (TACT_POCKET / 2 + 0.75), 0, top)):
                    Box(1.5, 2.0, 2.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # tunnel for the Modular, open at the USB side
        with Locations(((x_face + x_open + 1) / 2, 0, (zb + zt) / 2)):
            Box(x_open + 1 - x_face, 2 * yi, zt - zb, mode=Mode.SUBTRACT)
        # the plug's cradle, open to the top into the bay; the wires come up behind the plug
        insert(cradle_cut(0.0), mode=Mode.SUBTRACT)
        # pilots for the lid's screws
        for x, y in hand_lid_screws():
            with Locations((x, y, top + bay_h)):
                Cylinder(enc.PILOT_D / 2, 5.0, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
    return p.part


def hand_lid():
    """Lid of the hand switch, flush with the bay's walls all round: holes for the two buttons'
    actuators (it holds the buttons down), a tongue down onto the plug, four countersunk
    2.2 x 6.5 screws, arrows beside the buttons. Prints top down."""
    x_back, x_open = hand_x()
    z1 = MOD_H + C + HAND_WALL + POD_H
    z0 = z1 - HAND_LID_T
    with BuildPart() as p:
        with Locations(((x_back + x_open) / 2, 0, z0)):
            Box(x_open - x_back, POD_W, HAND_LID_T, align=(Align.CENTER, Align.CENTER, Align.MIN))
        chamfer(p.edges().filter_by(Axis.X).group_by(Axis.Z)[-1], length=1.0)
        # tongue onto the plug's body
        with Locations(((CRADLE_X0 + CRADLE_X1) / 2, 0, z0)):
            Box(CRADLE_X1 - CRADLE_X0 - 0.6, PLUG_D - 0.3, z0 - JACK_Z, align=(Align.CENTER, Align.CENTER, Align.MAX))
        with Locations(Location(((CRADLE_X0 + CRADLE_X1) / 2, 0, JACK_Z), (0, 90, 0))):
            Cylinder(PLUG_D / 2 + 0.1, CRADLE_X1 - CRADLE_X0, mode=Mode.SUBTRACT)
        for bx in BTN_X:
            with Locations((bx, 0, z0)):
                Cylinder(TACT_STEM_D / 2 + 0.3, HAND_LID_T, align=(Align.CENTER, Align.CENTER, Align.MIN),
                         mode=Mode.SUBTRACT)
        for x, y in hand_lid_screws():
            with Locations((x, y, z1)):
                Cylinder(enc.SCREW_D / 2, HAND_LID_T, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
                Cone(enc.SCREW_D / 2, enc.CSK_D / 2, (enc.CSK_D - enc.SCREW_D) / 2,
                     align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
        # arrows beside the buttons, 0.6 deep: rear points back (to the jack), front forward
        for bx, d in ((BTN_X[0], -1), (BTN_X[1], 1)):
            with BuildSketch(Plane.XY.offset(z1)):
                with Locations((bx, -(TACT_STEM_D / 2 + 4.5))):
                    Triangle(a=4.0, b=4.0, c=4.0, rotation=-90 * d)
            extrude(amount=-0.6, mode=Mode.SUBTRACT)
    return p.part


def tact_stand_in():
    """The two buttons on the bay's floor, for the views and the clash check."""
    top = MOD_H + C + HAND_WALL
    with BuildPart() as p:
        for bx in BTN_X:
            with Locations((bx, 0, top)):
                Box(TACT, TACT, 3.5, align=(Align.CENTER, Align.CENTER, Align.MIN))
            with Locations((bx, 0, top + 3.5)):
                Cylinder(TACT_STEM_D / 2, 3.8, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


# ============================================================================================
# Foot pedal
# ============================================================================================
# Pedal frame: x across (left to right), y from the heel (0) to the toe end, z = 0 on the floor.

PW, PD = 122.0, 168.0        # footprint; 6 mm to spare all round on the A1 mini's 180 mm bed
KEY_Z = 14.0                 # top of the base under the keys (plate the switches clip into)
KEY_W, KEY_GAP = 52.0, 6.0
KEY_T = 5.0
KEY_Y0, KEY_Y1 = 2.0, 125.0  # key from the heel to its toe edge
HINGE_Y = 9.5
SWITCH_Y = 102.0
SPRING_Y = 80.0
STOP_Y = 114.0
KEY_UNDER = KEY_Z + MX_STEM + 0.8 + 1.0   # key underside at rest (presser pad 1.8 below it)
KNUCKLE_W = 16.0
LUG_W = 6.0
KNUCKLE_R = 5.5
BLOCK_Y0 = 128.0             # toe block with the Modular pocket
HINGE_GAP = 1.0              # between the lugs' tops and the key's underside, at the hinge
# The hinges are sunk into the deck, in a trench across the heel end, so the keys slope: low at
# the heel, where the foot rests, rising to the switches at the toe.
TRENCH_Z = 3.0               # the trench's floor
TRENCH_Y = (2.0, 17.0)
HINGE_Z = TRENCH_Z + KNUCKLE_R + 0.5
KEY_FLAT = HINGE_Z + KNUCKLE_R + HINGE_GAP    # the key's underside in its own flat frame
# tilt that brings the underside up to KEY_UNDER over the switch
KEY_TILT = math.degrees(math.asin((KEY_UNDER - HINGE_Z - (KEY_FLAT - HINGE_Z)) / (SWITCH_Y - HINGE_Y)))
for _ in range(5):
    KEY_TILT = math.degrees(math.asin(
        (KEY_UNDER - HINGE_Z - (KEY_FLAT - HINGE_Z) * math.cos(math.radians(KEY_TILT))) / (SWITCH_Y - HINGE_Y)))
# A hook under each key's toe edge catches under a lip on the toe block: the upper stop, which
# sets the rest position against the spring. Both faces slope 45 degrees, so they print unsupported.
HOOK_W = 30.0
HOOK_Y0 = KEY_Y1 - 2.5       # the hook's web under the plate; its nose reaches 2.5 beyond the toe edge
HOOK_NOSE = (KEY_Y1 + 2.5, KEY_FLAT - 6.0)   # flat frame: the nose's upper outer corner


def tilted(y, z):
    """A point of the key's flat frame (y, z), in the pedal at rest."""
    a = math.radians(KEY_TILT)
    dy, dz = y - HINGE_Y, z - HINGE_Z
    return HINGE_Y + dy * math.cos(a) - dz * math.sin(a), HINGE_Z + dy * math.sin(a) + dz * math.cos(a)


_ny, _nz = tilted(*HOOK_NOSE)
LIP_REACH = 2.4
LIP_Z = _nz - (BLOCK_Y0 - _ny) + 0.2    # where the lip's sloped underside meets the block's face
HINGE_BOLT = 6.0             # M6 x 40 hex bolt (DIN 933) and two M6 nuts, as in the IC-705 mount's set
PLATE_Y0 = 1.0               # the key's plate runs from the heel edge and covers the hinge
TUNNEL_H = MOD_H + TRAY_H + 2 * C   # inside height of the tunnel
TUNNEL_ROOF = 2.0
POCKET_FLOOR = 3.0
BLOCK_Z = POCKET_FLOOR + TUNNEL_H + TUNNEL_ROOF
POCKET_Y = (BLOCK_Y0 + PD) / 2
POCKET_W = MOD_W + 2 * C
# The Modular slides onto the fixed plug from the pedal's right side, as into the hand switch's
# sleeve, and stands out of the side by STICK_OUT, to pull it out again. The plug lies in a cradle
# that is open to the top: a U-shaped lip in front that its body's nose rests on, two shoulders
# behind its end with a slot between them for the wires, and a lid from above whose tongue holds
# it down. The toe block runs across the whole pedal, for an even look.
STICK_OUT = 8.0
POCKET_X0 = PW / 2 + STICK_OUT - MOD_L - FACE_GAP   # end wall face of the tunnel
CRADLE_X1 = -FACE_GAP - SEAT_RECESS - SEAT_LIP      # Modular frame: the plug body's nose
CRADLE_X0 = CRADLE_X1 - PLUG_BODY - 0.3             # the plug body's end, at the shoulders
CRADLE_WIRES = 6.0                                  # wire slot behind the plug
LID_T = 2.0
LID_W = 24.0
LID_X0, LID_X1 = CRADLE_X0 - CRADLE_WIRES - 1.5, CRADLE_X1 + SEAT_LIP   # Modular frame
LID_SCREWS = [(x, sy * 8.5) for x in (CRADLE_X0 - 2.0, CRADLE_X1 - 3.5) for sy in (-1, 1)]
BOTTOM_T = 2.4               # bottom cover


def key_xs():
    return (-(KEY_GAP + KEY_W) / 2, (KEY_GAP + KEY_W) / 2)


def mod_in_pedal(part):
    """Place a part from the Modular frame into the pedal."""
    return part.translate((POCKET_X0 + FACE_GAP, POCKET_Y, POCKET_FLOOR + TRAY_H + C))


def cradle_cut(z_floor: float):
    """What to cut for the plug's cradle, in the Modular frame; z_floor is how far below the
    jack's axis the wire slot goes down (0: not at all, the wires leave upwards)."""
    up = 40.0
    with BuildPart() as p:
        # ring nut recess in the tunnel's end wall
        with Locations(Location((-FACE_GAP - SEAT_RECESS / 2 + 0.05, 0, JACK_Z), (0, 90, 0))):
            Cylinder(NUT_D / 2 + 0.4, SEAT_RECESS + 0.1)
        # U-shaped lip: only the shaft passes, and the plug drops in from above
        for w, x0, x1 in ((SEAT_LIP_D, CRADLE_X1 - 0.05, CRADLE_X1 + SEAT_LIP + 0.1),
                          (PLUG_BORE, CRADLE_X0, CRADLE_X1),
                          (WIRE_SLOT, CRADLE_X0 - CRADLE_WIRES, CRADLE_X0 + 0.05)):
            with Locations(Location(((x0 + x1) / 2, 0, JACK_Z), (0, 90, 0))):
                Cylinder(w / 2, x1 - x0)
            with Locations(((x0 + x1) / 2, 0, JACK_Z)):
                Box(x1 - x0, w, up, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # the wires go down behind the plug
        if z_floor > 0:
            with Locations((CRADLE_X0 - CRADLE_WIRES / 2, 0, JACK_Z)):
                Box(CRADLE_WIRES, WIRE_SLOT, z_floor, align=(Align.CENTER, Align.CENTER, Align.MAX))
    return p.part


def pedal_lid(z_top: float):
    """Lid over the plug, in the Modular frame with its top at z_top: a plate let into the toe
    block, a tongue down onto the plug's body, four countersunk 2.2 x 6.5 screws (the Modular's
    lid screws). Prints plate down."""
    with BuildPart() as p:
        with Locations(((LID_X0 + LID_X1) / 2, 0, z_top - LID_T)):
            with BuildSketch():
                RectangleRounded(LID_X1 - LID_X0 - 2 * C, LID_W - 2 * C, 2.0)
            extrude(amount=LID_T)
        with Locations(((CRADLE_X0 + CRADLE_X1) / 2, 0, z_top - LID_T)):
            Box(CRADLE_X1 - CRADLE_X0 - 0.6, PLUG_D - 0.3, z_top - LID_T - JACK_Z,
                align=(Align.CENTER, Align.CENTER, Align.MAX))
        with Locations(Location(((CRADLE_X0 + CRADLE_X1) / 2, 0, JACK_Z), (0, 90, 0))):
            Cylinder(PLUG_D / 2 + 0.1, CRADLE_X1 - CRADLE_X0, mode=Mode.SUBTRACT)
        for x, y in LID_SCREWS:
            with Locations((x, y, z_top)):
                Cylinder(enc.SCREW_D / 2, LID_T, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
                Cone(enc.SCREW_D / 2, enc.CSK_D / 2, (enc.CSK_D - enc.SCREW_D) / 2,
                     align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
    return p.part


def lid_z_top():
    """The lid's top in the Modular frame: flush with the toe block's top."""
    return BLOCK_Z - (POCKET_FLOOR + TRAY_H + C)


def pedal_base():
    with BuildPart() as p:
        # key deck and toe block, as one solid; channels from below, closed by the bottom cover
        with Locations((0, PD / 2, 0)):
            with BuildSketch():
                RectangleRounded(PW, PD, 6.0)
            extrude(amount=KEY_Z)
        with Locations((0, (BLOCK_Y0 + PD) / 2, 0)):
            with BuildSketch():
                RectangleRounded(PW, PD - BLOCK_Y0, 6.0)
            extrude(amount=BLOCK_Z)
        # hinge trench across the heel end, open at both sides (the bolts go in from there) and,
        # in the middle, to the back (a spanner reaches the nuts from behind)
        ty0, ty1 = TRENCH_Y
        with Locations((0, (ty0 + ty1) / 2, TRENCH_Z)):
            Box(PW + 2, ty1 - ty0, KEY_Z, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        mid = KEY_GAP + KEY_W - KNUCKLE_W - 0.8     # between the two inner lugs
        with Locations((0, ty0 / 2, TRENCH_Z)):
            Box(mid, ty0 + 0.2, KEY_Z, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # two lugs per key either side of its knuckle, standing in the trench, on an M6 x 40 hex
        # bolt from the outer side with two nuts locked against each other on the inner lug (lug 6
        # + knuckle 16 + lug 6 + two nuts fits 40 mm); the IC-705 mount's bolts and nuts
        lug_h = HINGE_Z + KNUCKLE_R - TRENCH_Z
        for kx in key_xs():
            for d in (-1, 1):
                with Locations((kx + d * (KNUCKLE_W / 2 + 0.4 + LUG_W / 2), (ty0 + ty1) / 2, TRENCH_Z)):
                    Box(LUG_W, ty1 - ty0, lug_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            with Locations(Location((kx, HINGE_Y, HINGE_Z), (0, 90, 0))):
                Cylinder(HINGE_BOLT / 2 + 0.2, KNUCKLE_W + 2 * LUG_W + 2, mode=Mode.SUBTRACT)
        # the lip on the toe block's face that the keys' hooks catch under, sloped 45 degrees below
        with BuildSketch(Plane.YZ.offset(-PW / 2 + 6)):
            Polygon((BLOCK_Y0 + 0.1, LIP_Z - 0.1), (BLOCK_Y0 - LIP_REACH, LIP_Z + LIP_REACH),
                    (BLOCK_Y0 - LIP_REACH, BLOCK_Z), (BLOCK_Y0 + 0.1, BLOCK_Z), align=None)
        extrude(amount=PW - 12)
        for kx in key_xs():
            # switch: plate cut-out, cavity below it down to the cover, channel to the plug
            with Locations((kx, SWITCH_Y, KEY_Z)):
                Box(MX_CUT, MX_CUT, MX_PLATE, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
            with Locations((kx, SWITCH_Y, 0)):
                Box(MX_CUT + 2, MX_CUT + 2, KEY_Z - MX_PLATE, align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT)
            # spring pocket
            with Locations((kx, SPRING_Y, KEY_Z)):
                Cylinder(SPRING_D / 2 + 0.4, SPRING_POCKET, align=(Align.CENTER, Align.CENTER, Align.MAX),
                         mode=Mode.SUBTRACT)
            # travel stops: two posts beside the switch; the key's pads land on them first
            for dx in (-1, 1):
                with Locations((kx + dx * 16, STOP_Y, KEY_Z)):
                    Cylinder(3.0, KEY_UNDER - KEY_Z - 3.6, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # wire channel from below: across under both switches
        ch = 6.0
        with Locations((0, SWITCH_Y, 0)):
            Box(KEY_W + KEY_GAP + 2, ch, KEY_Z - 4.0, align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)
        # from there straight forward to under the plug's end, where the wires come down from the
        # cradle through the slot behind the plug
        x_wires = POCKET_X0 + FACE_GAP + CRADLE_X0 - CRADLE_WIRES / 2
        assert abs(x_wires) < (KEY_W + KEY_GAP + 2) / 2, "the channel misses the one under the switches"
        with Locations((x_wires, (SWITCH_Y + POCKET_Y) / 2, 0)):
            Box(ch, POCKET_Y - SWITCH_Y + ch, KEY_Z - 4.0, align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)

        # the tunnel for the Modular, roofed, from the end wall face out through the right side
        z_plug = POCKET_FLOOR + TRAY_H + C + JACK_Z
        with Locations(((POCKET_X0 + PW / 2 + 1) / 2, POCKET_Y, POCKET_FLOOR)):
            Box(PW / 2 + 1 - POCKET_X0, POCKET_W, TUNNEL_H, align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)
        # the plug's cradle, open to the top, and the wire slot down to the floor channel
        insert(mod_in_pedal(cradle_cut(z_plug - 1.0)), mode=Mode.SUBTRACT)
        # recess for the lid and pilots for its screws
        zt = lid_z_top()
        with BuildPart(mode=Mode.PRIVATE) as lid_cut:
            with Locations(((LID_X0 + LID_X1) / 2, 0, zt - LID_T)):
                with BuildSketch():
                    RectangleRounded(LID_X1 - LID_X0, LID_W, 2.0)
                extrude(amount=LID_T + 1)
            for x, y in LID_SCREWS:
                with Locations((x, y, zt - LID_T)):
                    Cylinder(enc.PILOT_D / 2, 5.5, align=(Align.CENTER, Align.CENTER, Align.MAX))
        insert(mod_in_pedal(lid_cut.part), mode=Mode.SUBTRACT)
        # screw holes for the bottom cover: countersunk 2.2 x 6.5 (DIN 7982) from below, as on the
        # Modular's lid; the pedal stands on the cover, so the screws only keep it in place
        for x, y in cover_screws():
            with Locations((x, y, 0)):
                Cylinder(enc.PILOT_D / 2, 5.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    return p.part


def cover_screws():
    return [(-PW / 2 + 8, 30), (PW / 2 - 8, 30), (0, 60), (-PW / 2 + 8, 100), (PW / 2 - 8, 100),
            (PW / 2 - 6, BLOCK_Y0 - 8), (-PW / 2 + 8, PD - 8)]   # none under the tunnel: its floor is thin


def pedal_cover():
    """Bottom cover: closes the channels, four recesses for stick-on rubber feet (Ø 10)."""
    with BuildPart() as p:
        with Locations((0, PD / 2, -BOTTOM_T)):
            with BuildSketch():
                RectangleRounded(PW, PD, 6.0)
            extrude(amount=BOTTOM_T)
        for x, y in cover_screws():
            with Locations((x, y, 0)):
                Cylinder(enc.SCREW_D / 2, BOTTOM_T, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
                Cone(enc.SCREW_D / 2, enc.CSK_D / 2, (enc.CSK_D - enc.SCREW_D) / 2, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT,
                     rotation=(180, 0, 0))
        for x, y in ((-PW / 2 + 14, 14), (PW / 2 - 14, 14), (-PW / 2 + 14, PD - 14), (PW / 2 - 14, PD - 14)):
            with Locations((x, y, -BOTTOM_T)):
                Cylinder(5.3, 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    return p.part


def pedal_key(right: bool, flat: bool = False):
    """Foot key: a plate from the heel edge to the toe with nothing standing above it, ribs
    underneath, the hinge knuckle hanging below its heel end, presser pad over the switch, spring
    seat, stop pads and the hook under its toe edge. Built flat, then tilted about the hinge into
    its rest position (flat=True leaves it flat, for printing)."""
    kx = key_xs()[1 if right else 0]
    U = KEY_FLAT
    with BuildPart() as p:
        with Locations((kx, (PLATE_Y0 + KEY_Y1) / 2, U)):
            with BuildSketch():
                RectangleRounded(KEY_W, KEY_Y1 - PLATE_Y0, 4.0)
            extrude(amount=KEY_T)
        # top edge eased all round, kind to socks; a chamfer, as the key prints top down
        chamfer(p.faces().sort_by(Axis.Z)[-1].edges(), length=1.0)
        # knuckle round the hinge bolt, hanging from the plate
        with Locations(Location((kx, HINGE_Y, HINGE_Z), (0, 90, 0))):
            Cylinder(KNUCKLE_R, KNUCKLE_W)
        with Locations((kx, HINGE_Y, HINGE_Z)):
            Box(KNUCKLE_W, 2 * KNUCKLE_R, U - HINGE_Z, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations(Location((kx, HINGE_Y, HINGE_Z), (0, 90, 0))):
            Cylinder(HINGE_BOLT / 2 + 0.3, KNUCKLE_W + 1, mode=Mode.SUBTRACT)
        # ribs underneath, along the key, starting clear of the hinge and its bolt head
        rib_y0 = HINGE_Y + KNUCKLE_R + 8.0
        for dx in (-KEY_W / 2 + 3, KEY_W / 2 - 3):
            with Locations((kx + dx, (rib_y0 + KEY_Y1 - 6) / 2, U)):
                Box(2.0, KEY_Y1 - 6 - rib_y0, 3.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
        # presser pad over the switch stem
        with Locations((kx, SWITCH_Y, U)):
            Cylinder(3.5, 1.4, align=(Align.CENTER, Align.CENTER, Align.MAX))   # short of the stem by the tilt
        # stop pads over the posts
        for dx in (-1, 1):
            with Locations((kx + dx * 16, STOP_Y, U)):
                Cylinder(3.0, 1.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
        # spring seat
        with Locations((kx, SPRING_Y, U)):
            Cylinder(SPRING_D / 2 + 1.6, 3.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
            Cylinder(SPRING_D / 2 + 0.4, 3.0, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
        # hook under the toe edge: a web down from the plate and a nose forward, its top sloped
        ny, nz = HOOK_NOSE
        with BuildSketch(Plane.YZ.offset(kx - HOOK_W / 2)):
            Polygon((HOOK_Y0, U + 0.1), (KEY_Y1, U + 0.1), (KEY_Y1, nz + (ny - KEY_Y1)), (ny, nz),
                    (ny, nz - 2.0), (HOOK_Y0, nz - 2.0), align=None)
        extrude(amount=HOOK_W)
        # grip: shallow grooves across the top; arrow towards the toe on the right key, the heel on
        # the left
        for i in range(7):
            with Locations((kx, 40 + i * 10, U + KEY_T)):
                Box(KEY_W - 12, 1.6, 0.8, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
        with BuildSketch(Plane.XY.offset(U + KEY_T)):
            with Locations((kx, 26)):
                Triangle(a=12, b=12, c=12, rotation=0 if right else 180)
        extrude(amount=-0.8, mode=Mode.SUBTRACT)
    if flat:
        return p.part
    return p.part.rotate(Axis((0, HINGE_Y, HINGE_Z), (1, 0, 0)), KEY_TILT)


def pedal_switch_stand_in(kx):
    with BuildPart() as p:
        with Locations((kx, SWITCH_Y, KEY_Z)):
            Box(15.6, 15.6, MX_STEM - 3.6, align=(Align.CENTER, Align.CENTER, Align.MIN))
            Box(MX_CUT - 0.1, MX_CUT - 0.1, MX_BELOW - 3.3, align=(Align.CENTER, Align.CENTER, Align.MAX))
        with Locations((kx, SWITCH_Y, KEY_Z + MX_STEM - 3.6)):
            Box(4.0, 4.0, 3.6, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


def check(name, printed, others):
    names = list(printed)
    pairs = [(a, printed[a], b, printed[b]) for i, a in enumerate(names) for b in names[i + 1:]]
    pairs += [(a, printed[a], b, o) for b, o in others.items() for a in printed]
    for an, a, bn, b in pairs:
        clash = a & b
        vol = clash.volume if clash else 0
        if vol > 0.05:
            print(f"  {name}: overlap {an}/{bn}: {vol:.2f} mm3")


def preview(parts, out, suffix=""):
    """One mesh per part for preview.html, as base64 text like enclosure.py writes them. Each part
    is rebuilt inside BuildPart first, so moved shapes have their placement baked in."""
    import base64
    for name, part in parts.items():
        with BuildPart() as baked:
            for solid in part.solids():
                insert(Solid(solid.wrapped))
        glb = out / f"preview-{name}{suffix}.glb"
        export_gltf(baked.part, str(glb), binary=True, linear_deflection=0.02, angular_deflection=0.2)
        glb.with_suffix(".b64.txt").write_text(base64.b64encode(glb.read_bytes()).decode())
        glb.unlink()


def save(part, out, stem, flip=None):
    assert len(part.solids()) == 1, f"{stem} is in {len(part.solids())} pieces"
    export_step(part, out / f"{stem}.step")
    export_stl(flip(part) if flip else part, out / f"{stem}.stl", tolerance=0.01, angular_tolerance=0.1)


def main():
    views_out = OUT / "addons-views"
    views_out.mkdir(parents=True, exist_ok=True)
    render = "--views" in sys.argv

    # --- hand switch ---
    out = OUT / "hand-fdm"
    out.mkdir(parents=True, exist_ok=True)
    if True:
        h, hl = hand(True), hand_lid()
        mod, plug, btn = modular_stand_in(True), plug_stand_in(), tact_stand_in()
        check("hand", {"sleeve": h, "lid": hl}, {"modular": mod, "plug": plug, "buttons": btn})
        # the sleeve prints standing on its end block, the tunnel upright; the lid top down
        save(h, out, "ble-key-hand", flip=lambda s: s.rotate(Axis.Y, -90))
        save(hl, out, "ble-key-hand-lid", flip=lambda s: s.rotate(Axis.X, 180))
        preview({"base": h, "lid": hl, "modular": mod, "plug": plug, "switches": btn}, out)
        bb = (h + hl).bounding_box()
        print(f"hand: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")
        if render:
            views("hand", [(h, "#c2541b"), (hl, "#e07a3f"), (mod, "#2b2f2e"), (plug, "#b9b9b9"), (btn, "#3a3f3d")],
                  views_out, elev_azims=((28, -50), (20, 140), (12, -95)))
            views("hand-open", [(h, "#c2541b"), (plug, "#b9b9b9"), (btn, "#3a3f3d")], views_out,
                  elev_azims=((45, 140), (70, -90)))

    # --- pedal ---
    out = OUT / "pedal-fdm"
    out.mkdir(parents=True, exist_ok=True)
    base, cover = pedal_base(), pedal_cover()
    keys = {"key-left": pedal_key(False), "key-right": pedal_key(True)}
    mod_tray = mod_in_pedal(modular_stand_in(True))
    plug = mod_in_pedal(plug_stand_in())
    lid = mod_in_pedal(pedal_lid(lid_z_top()))
    save(pedal_lid(lid_z_top()), out, "ble-key-pedal-plug-lid", flip=lambda s: s.rotate(Axis.X, 180))
    switches = {f"switch-{i}": pedal_switch_stand_in(kx) for i, kx in enumerate(key_xs())}
    printed = {"base": base, "cover": cover, **keys, "lid": lid}
    check("pedal", printed, {"modular": mod_tray, "plug": plug, **switches})
    save(base, out, "ble-key-pedal-base")
    save(cover, out, "ble-key-pedal-cover", flip=lambda s: s.rotate(Axis.X, 180))
    for k, right in (("key-left", False), ("key-right", True)):
        save(pedal_key(right, flat=True), out, f"ble-key-pedal-{k}", flip=lambda s: s.rotate(Axis.X, 180))   # top on the bed
    sw = switches["switch-0"] + switches["switch-1"]
    preview({"base": base + cover, "lid": lid, "keys": keys["key-left"] + keys["key-right"], "modular": mod_tray, "plug": plug, "switches": sw}, out)
    bb = base.bounding_box()
    print(f"pedal: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, "
          f"keys tilted {KEY_TILT:.1f} deg, toe edge at {tilted(KEY_Y1, KEY_FLAT + KEY_T)[1]:.1f} mm, "
          f"heel edge at {tilted(PLATE_Y0, KEY_FLAT + KEY_T)[1]:.1f} mm")
    if render:
        shown = [(base, "#c2541b"), (keys["key-left"], "#e07a3f"), (keys["key-right"], "#e07a3f"),
                 (lid, "#8a8f8d"), (mod_tray, "#2b2f2e"), (plug, "#b9b9b9")]
        views("pedal", shown, views_out, elev_azims=((35, -60), (30, 115), (85, -90)))
        views("pedal-open", [(base, "#c2541b")] + [(sw, "#3a3f3d") for sw in switches.values()],
              views_out, elev_azims=((40, -60), (-55, -60)))


if __name__ == "__main__":
    main()
