"""Add-ons for the BLE Key Modular, for prompting in Frame: a foot pedal and a hand switch.

Both take the Modular as it is and connect to it only through its 3.5 mm jack, with a stereo plug
wired the way the key expects: tip = dit (Frame: forward), ring = dah (Frame: back), sleeve = GND.
Nothing inside the Modular changes.

- pedal:  two foot keys side by side (left back, right forward) on Cherry-MX-style switches, a
          return spring under each key, and a pocket at the toe end that the Modular drops into.
          A 3.5 mm plug sits fixed in the pocket's end wall; the Modular goes in at the far end,
          slides onto the plug, and a keeper block fills the gap behind it. USB-C stays reachable
          through the keeper and the pedal's side wall. A spacer lifts a Modular without battery
          tray to the same height, so the plug fits both.
- hand:   a sleeve that slides over the Modular's jack end; the plug in its end block goes into
          the jack as it slides home. Two 12 x 12 mm tactile buttons on top (front forward, rear
          back). One sleeve per height: without and with battery tray.

All parts are for FDM (PETG), 0.35 mm fit, and fit a 180 x 180 mm bed (Bambu Lab A1 mini).

    .venv/bin/python addons.py           # out/pedal-fdm/, out/hand-fdm/
    .venv/bin/python addons.py --views   # also PNG views in out/addons-views/ (needs vtk)

The Modular's dimensions come from enclosure.py (Variant "modular-fdm"), so the add-ons follow
any change there. Modular frame used here: jack end face at x = 0, USB end at x = MOD_L, centred
on y = 0, z = 0 at the base's underside (the battery tray hangs below it, down to -TRAY_H).

Bought parts whose sizes are assumed, not measured (see README, "Add-ons"):
PLUG_* (a 3.5 mm stereo solder plug with its handle taken off), MX_* (Cherry MX footprint),
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

# --- 3.5 mm stereo plug, handle removed (assumed: typical metal solder plug) ------------------
PLUG_SHAFT = 14.0   # from the shoulder to the tip; goes fully into the jack
PLUG_D = 6.0        # insulating collar and solder part behind the shoulder
PLUG_BODY = 16.0    # collar plus solder lugs and strain relief, behind the shoulder
PLUG_BORE = PLUG_D + 0.3

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


def plug_stand_in():
    """Plug in the Modular frame: shoulder at x = -NUT_OUT, shaft into the jack, body behind."""
    with BuildPart() as p:
        with Locations(Location((-NUT_OUT + PLUG_SHAFT / 2, 0, JACK_Z), (0, 90, 0))):
            Cylinder(1.75, PLUG_SHAFT)
        with Locations(Location((-NUT_OUT - PLUG_BODY / 2, 0, JACK_Z), (0, 90, 0))):
            Cylinder(PLUG_D / 2, PLUG_BODY)
    return p.part


# ============================================================================================
# Hand switch: a sleeve over the jack end with the plug in its end block and two buttons on top
# ============================================================================================

HAND_WALL = 2.0
HAND_REACH = 40.0           # how far the sleeve reaches over the Modular from its jack end
HAND_BLOCK = PLUG_BODY + 4.0    # end block behind the end wall face: plug bore, retaining screw
POD_H = 6.0                 # button pod on top of the sleeve
POD_W = 26.0
BTN_X = (9.0, 28.0)         # rear button (back / dah / ring), front button (forward / dit / tip)


def hand(tray: bool):
    zb = (-TRAY_H if tray else 0.0) - C          # sleeve inside, bottom
    zt = MOD_H + C                               # sleeve inside, top
    yi = MOD_W / 2 + C
    x_face = -NUT_OUT                            # end wall face: the nut rests on it
    x_back = x_face - HAND_BLOCK
    x_open = HAND_REACH
    top = zt + HAND_WALL                         # top of the sleeve, floor of the pod
    pod_top = top + POD_H
    with BuildPart() as p:
        # outer shell plus end block
        with Locations(((x_back + x_open) / 2, 0, (zb - HAND_WALL + top) / 2)):
            Box(x_open - x_back, 2 * (yi + HAND_WALL), top - zb + HAND_WALL)
        fillet(p.edges().filter_by(Axis.X), radius=1.5)
        # button pod
        with Locations(((x_back + x_open) / 2, 0, top)):
            Box(x_open - x_back, POD_W, POD_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # tunnel for the Modular, open at the USB side
        with Locations(((x_face + x_open + 1) / 2, 0, (zb + zt) / 2)):
            Box(x_open + 1 - x_face, 2 * yi, zt - zb, mode=Mode.SUBTRACT)
        # the Modular's vertical corner radius at its jack end: the tunnel's inside corners stay
        # square, which clears it
        # plug bore from the end wall face back through the block; the plug goes in from behind
        with Locations(Location((x_face - HAND_BLOCK / 2, 0, JACK_Z), (0, 90, 0))):
            Cylinder(PLUG_BORE / 2, HAND_BLOCK + 0.2, mode=Mode.SUBTRACT)
        # narrow step at the face so the plug's collar stops there and only the shaft goes through
        # (the collar's front face sits flush with the wall face, at the thread's end)
        # retaining screw across behind the plug: M2 x 10 self-tapping, from below
        with Locations((x_back + 2.0, 0, zb - HAND_WALL)):
            Cylinder(0.85, JACK_Z - zb + HAND_WALL + PLUG_BORE / 2 + 1.5,
                     align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # button pockets from the pod's top, wire holes from their floors down into a channel
        for bx in BTN_X:
            with Locations((bx, 0, pod_top)):
                Box(TACT_POCKET, TACT_POCKET, TACT_BODY, align=(Align.CENTER, Align.CENTER, Align.MAX),
                    mode=Mode.SUBTRACT)
            for dx in (-1, 1):
                with Locations((bx + dx * 4.5, 0, pod_top - TACT_BODY)):
                    Box(2.0, 9.0, POD_H - TACT_BODY - 0.8, align=(Align.CENTER, Align.CENTER, Align.MAX),
                        mode=Mode.SUBTRACT)
        # wire channel along the pod, from the front button back over the end block
        ch_z0, ch_z1 = top + 0.4, pod_top - TACT_BODY - 0.8
        with Locations(((x_back + 3.0 + BTN_X[1] + 4.5) / 2, 0, ch_z0)):
            Box(BTN_X[1] + 4.5 - x_back - 3.0, 4.0, ch_z1 - ch_z0, align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)
        # and down from the channel into the plug bore, behind the plug's lugs
        with Locations((x_back + 4.5, 0, JACK_Z)):
            Box(3.0, 4.0, ch_z1 - JACK_Z, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # arrows beside the buttons, 0.6 deep: rear points back (to the jack), front forward
        for bx, d in ((BTN_X[0], -1), (BTN_X[1], 1)):
            with BuildSketch(Plane.XY.offset(pod_top)) as s:
                with Locations((bx, -(TACT_POCKET / 2 + 3.6))):
                    Triangle(a=4.0, b=4.0, c=4.0, rotation=-90 * d)
            extrude(amount=-0.6, mode=Mode.SUBTRACT)
    return p.part


# ============================================================================================
# Foot pedal
# ============================================================================================
# Pedal frame: x across (left to right), y from the heel (0) to the toe end, z = 0 on the floor.

PW, PD = 122.0, 178.0        # footprint; fits a 180 mm bed
KEY_Z = 14.0                 # top of the base under the keys (plate the switches clip into)
KEY_W, KEY_GAP = 52.0, 6.0
KEY_T = 5.0
KEY_Y0, KEY_Y1 = 2.0, 135.0  # key from the heel to its toe edge
HINGE_Y = 8.0
SWITCH_Y = 112.0
SPRING_Y = 88.0
STOP_Y = 124.0
KEY_UNDER = KEY_Z + MX_STEM + 0.8 + 1.0   # key underside at rest (presser pad 1.8 below it)
HINGE_Z = KEY_UNDER + KEY_T / 2
KNUCKLE_W = 16.0
LUG_W = 5.0
KNUCKLE_R = 5.0
PLATE_Y0 = HINGE_Y + KNUCKLE_R + 2 + 1.5   # the key's plate starts clear of the heel ridge
BLOCK_Y0 = 138.0             # toe block with the Modular pocket
POCKET_DEPTH = MOD_H + TRAY_H + 0.8
POCKET_FLOOR = 3.0
BLOCK_Z = POCKET_FLOOR + POCKET_DEPTH
SLIDE = PLUG_SHAFT + 1.5     # the Modular goes in this far from the plug, then slides onto it
POCKET_Y = (BLOCK_Y0 + PD) / 2
POCKET_W = MOD_W + 2 * C
POCKET_X0 = -26.0            # end wall face with the plug; the nut rests on it
POCKET_L = NUT_OUT + MOD_L + SLIDE + 2 * C
BOTTOM_T = 2.4               # bottom cover


def key_xs():
    return (-(KEY_GAP + KEY_W) / 2, (KEY_GAP + KEY_W) / 2)


def mod_in_pedal(part):
    """Place a part from the Modular frame into the pedal, Modular engaged on the plug."""
    return part.translate((POCKET_X0 + NUT_OUT, POCKET_Y, POCKET_FLOOR + TRAY_H + C))


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
        # hinge: two lugs per key either side of its knuckle, on an M3 x 30 screw from the outer
        # side with a nut on the inner lug (lug 5 + knuckle 16 + lug 5 + nut fits 30 mm)
        lug_h = HINGE_Z + KNUCKLE_R + 0.5 - KEY_Z
        for kx in key_xs():
            sx = 1 if kx > 0 else -1
            for d in (-1, 1):
                with Locations((kx + d * (KNUCKLE_W / 2 + 0.4 + LUG_W / 2), HINGE_Y, KEY_Z)):
                    Box(LUG_W, 2 * KNUCKLE_R + 4, lug_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
            with Locations(Location((kx, HINGE_Y, HINGE_Z), (0, 90, 0))):
                Cylinder(1.6, KNUCKLE_W + 2 * LUG_W + 2, mode=Mode.SUBTRACT)
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
        # wire channel from below: across under both switches, then forward to the plug cavity
        ch = 6.0
        with Locations((0, SWITCH_Y, 0)):
            Box(KEY_W + KEY_GAP + 2, ch, KEY_Z - 4.0, align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)
        plug_x0 = POCKET_X0 - PLUG_BODY - 4.0
        with Locations((plug_x0 + 3.0, (SWITCH_Y + POCKET_Y) / 2, 0)):
            Box(ch, POCKET_Y - SWITCH_Y + ch, KEY_Z - 4.0, align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT)

        # the pocket
        z_plug = POCKET_FLOOR + TRAY_H + C + JACK_Z
        with Locations((POCKET_X0 + POCKET_L / 2, POCKET_Y, POCKET_FLOOR)):
            with BuildSketch():
                Rectangle(POCKET_L, POCKET_W)
            extrude(amount=POCKET_DEPTH + 1, mode=Mode.SUBTRACT)
        # finger notches on both long sides, to lift the Modular out
        with Locations((POCKET_X0 + NUT_OUT + MOD_L / 2, POCKET_Y, BLOCK_Z)):
            Box(22.0, POCKET_W + 12.0, 9.0, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
        # plug: bore from the end wall face back, open from below for fitting it; channel down
        with Locations(Location((POCKET_X0 - (PLUG_BODY + 4) / 2, POCKET_Y, z_plug), (0, 90, 0))):
            Cylinder(PLUG_BORE / 2, PLUG_BODY + 4 + 0.2, mode=Mode.SUBTRACT)
        with Locations((POCKET_X0 - (PLUG_BODY + 4) / 2, POCKET_Y, 0)):
            Box(PLUG_BODY + 4, PLUG_BORE, z_plug, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # USB-C: opening through the right side wall at the plug's height, for the cable
        usb_z = POCKET_FLOOR + TRAY_H + C + USB_Z
        x_end = POCKET_X0 + POCKET_L
        with Locations(((x_end + PW / 2 + 1) / 2, POCKET_Y, usb_z)):
            Box(PW / 2 + 1 - x_end, 13.0, 8.0, mode=Mode.SUBTRACT)
        # screw holes for the bottom cover: M3 self-tapping from below, pilot 2.5
        for x, y in cover_screws():
            with Locations((x, y, 0)):
                Cylinder(1.25, 10.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    return p.part


def cover_screws():
    return [(-PW / 2 + 8, 30), (PW / 2 - 8, 30), (0, 60), (-PW / 2 + 8, 100), (PW / 2 - 8, 100),
            (PW / 2 - 8, PD - 8), (-PW / 2 + 8, PD - 8)]


def pedal_cover():
    """Bottom cover: closes the channels, four recesses for stick-on rubber feet (Ø 10)."""
    with BuildPart() as p:
        with Locations((0, PD / 2, -BOTTOM_T)):
            with BuildSketch():
                RectangleRounded(PW, PD, 6.0)
            extrude(amount=BOTTOM_T)
        for x, y in cover_screws():
            with Locations((x, y, 0)):
                Cylinder(1.7, BOTTOM_T, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
                Cone(1.7, 3.1, 1.4, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT,
                     rotation=(180, 0, 0))
        for x, y in ((-PW / 2 + 14, 14), (PW / 2 - 14, 14), (-PW / 2 + 14, PD - 14), (PW / 2 - 14, PD - 14)):
            with Locations((x, y, -BOTTOM_T)):
                Cylinder(5.3, 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    return p.part


def pedal_key(right: bool):
    """Foot key: plate with ribs, hinge knuckle at the heel, presser pad over the switch, spring
    seat and stop pads. Modelled at rest, horizontal."""
    kx = key_xs()[1 if right else 0]
    with BuildPart() as p:
        with Locations((kx, (PLATE_Y0 + KEY_Y1) / 2, KEY_UNDER)):
            with BuildSketch():
                RectangleRounded(KEY_W, KEY_Y1 - PLATE_Y0, 4.0)
            extrude(amount=KEY_T)
        # knuckle round the hinge pin
        with Locations(Location((kx, HINGE_Y, HINGE_Z), (0, 90, 0))):
            Cylinder(KNUCKLE_R, KNUCKLE_W)
        with Locations((kx, (HINGE_Y + PLATE_Y0 + 3) / 2, HINGE_Z)):
            Box(KNUCKLE_W, PLATE_Y0 + 3 - HINGE_Y, KEY_T, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        with Locations(Location((kx, HINGE_Y, HINGE_Z), (0, 90, 0))):
            Cylinder(1.8, KNUCKLE_W + 1, mode=Mode.SUBTRACT)
        # ribs underneath, along the key
        for dx in (-KEY_W / 2 + 3, 0, KEY_W / 2 - 3):
            if dx == 0:
                continue
            with Locations((kx + dx, (PLATE_Y0 + 4 + KEY_Y1 - 6) / 2, KEY_UNDER)):
                Box(2.0, KEY_Y1 - 6 - PLATE_Y0 - 4, 3.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
        # presser pad over the switch stem
        with Locations((kx, SWITCH_Y, KEY_UNDER)):
            Cylinder(3.5, 1.8, align=(Align.CENTER, Align.CENTER, Align.MAX))
        # stop pads over the posts
        for dx in (-1, 1):
            with Locations((kx + dx * 16, STOP_Y, KEY_UNDER)):
                Cylinder(3.0, 1.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
        # spring seat
        with Locations((kx, SPRING_Y, KEY_UNDER)):
            Cylinder(SPRING_D / 2 + 1.6, 3.0, align=(Align.CENTER, Align.CENTER, Align.MAX))
            Cylinder(SPRING_D / 2 + 0.4, 3.0, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
        # grip: shallow grooves across the top; arrow towards the toe on the right key, the heel on
        # the left
        for i in range(8):
            with Locations((kx, 40 + i * 10, KEY_UNDER + KEY_T)):
                Box(KEY_W - 12, 1.6, 0.8, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
        with BuildSketch(Plane.XY.offset(KEY_UNDER + KEY_T)):
            with Locations((kx, 24)):
                Triangle(a=12, b=12, c=12, rotation=0 if right else 180)
        extrude(amount=-0.8, mode=Mode.SUBTRACT)
    return p.part


def pedal_keeper():
    """Fills the gap behind the Modular once it is on the plug; slot for the USB-C cable."""
    x0 = POCKET_X0 + NUT_OUT + MOD_L + C
    x1 = POCKET_X0 + POCKET_L - C
    w = POCKET_W - 2 * C
    z0 = POCKET_FLOOR
    z1 = BLOCK_Z
    usb_z = POCKET_FLOOR + TRAY_H + C + USB_Z
    with BuildPart() as p:
        with Locations(((x0 + x1) / 2, POCKET_Y, z0)):
            Box(x1 - x0, w, z1 - z0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations(((x0 + x1) / 2, POCKET_Y, usb_z)):
            Box(x1 - x0 + 1, 13.0, 8.0, mode=Mode.SUBTRACT)
        # a slot from the top down to the USB opening, so the keeper goes in with the cable plugged
        with Locations(((x0 + x1) / 2, POCKET_Y, usb_z)):
            Box(x1 - x0 + 1, 5.0, z1 - usb_z + 1, align=(Align.CENTER, Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
        # a grip ridge on top to pull it out
        with Locations(((x0 + x1) / 2, POCKET_Y + 9.0, z1)):
            Box(x1 - x0 - 4, 3.0, 3.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


def pedal_spacer():
    """For a Modular without battery tray: lifts it to the tray's height, so the plug fits."""
    x0 = POCKET_X0 + C
    x1 = POCKET_X0 + NUT_OUT + MOD_L - C     # up to the keeper, which stands on the pocket floor
    w = POCKET_W - 2 * C
    with BuildPart() as p:
        with Locations(((x0 + x1) / 2, POCKET_Y, POCKET_FLOOR)):
            with BuildSketch():
                Rectangle(x1 - x0, w)
                Rectangle(x1 - x0 - 6, w - 6, mode=Mode.SUBTRACT)
            extrude(amount=TRAY_H)
        with Locations(((x0 + x1) / 2, POCKET_Y, POCKET_FLOOR)):
            Box(x1 - x0 - 6, 3.0, TRAY_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return p.part


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
                add(Solid(solid.wrapped))
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
    for tray in (False, True):
        tag = "tray" if tray else "usb"
        h = hand(tray)
        mod, plug = modular_stand_in(tray), plug_stand_in()
        check(f"hand-{tag}", {"sleeve": h}, {"modular": mod, "plug": plug})
        # prints standing on its end block, the tunnel upright: no supports
        save(h, out, f"ble-key-hand-{tag}", flip=lambda s: s.rotate(Axis.Y, -90))
        preview({"base": h, "modular": mod, "plug": plug}, out, f"-{tag}")
        bb = h.bounding_box()
        print(f"hand {tag}: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")
        if render:
            views(f"hand-{tag}", [(h, "#c2541b"), (mod, "#2b2f2e"), (plug, "#b9b9b9")], views_out,
                  elev_azims=((28, -50), (20, 140), (12, -95)))

    # --- pedal ---
    out = OUT / "pedal-fdm"
    out.mkdir(parents=True, exist_ok=True)
    base, cover = pedal_base(), pedal_cover()
    keys = {"key-left": pedal_key(False), "key-right": pedal_key(True)}
    keeper, spacer = pedal_keeper(), pedal_spacer()
    mod_tray = mod_in_pedal(modular_stand_in(True))
    plug = mod_in_pedal(plug_stand_in())
    switches = {f"switch-{i}": pedal_switch_stand_in(kx) for i, kx in enumerate(key_xs())}
    printed = {"base": base, "cover": cover, **keys, "keeper": keeper}
    check("pedal", printed, {"modular": mod_tray, "plug": plug, **switches})
    # a Modular without tray, on the spacer
    mod_usb = mod_in_pedal(modular_stand_in(False))
    check("pedal (no tray)", {"spacer": spacer, "keeper": keeper}, {"modular": mod_usb})
    save(base, out, "ble-key-pedal-base")
    save(cover, out, "ble-key-pedal-cover", flip=lambda s: s.rotate(Axis.X, 180))
    for k, part in keys.items():
        save(part, out, f"ble-key-pedal-{k}", flip=lambda s: s.rotate(Axis.X, 180))   # top on the bed
    save(keeper, out, "ble-key-pedal-keeper")
    save(spacer, out, "ble-key-pedal-spacer")
    sw = switches["switch-0"] + switches["switch-1"]
    preview({"base": base + cover, "keys": keys["key-left"] + keys["key-right"], "keeper": keeper,
             "modular": mod_tray, "plug": plug, "switches": sw}, out)
    bb = base.bounding_box()
    print(f"pedal: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm, "
          f"toe height {KEY_UNDER + KEY_T:.1f} mm")
    if render:
        shown = [(base, "#c2541b"), (keys["key-left"], "#e07a3f"), (keys["key-right"], "#e07a3f"),
                 (keeper, "#8a8f8d"), (mod_tray, "#2b2f2e"), (plug, "#b9b9b9")]
        views("pedal", shown, views_out, elev_azims=((35, -60), (30, 115), (85, -90)))
        views("pedal-open", [(base, "#c2541b"), (spacer, "#8a8f8d")] + [(sw, "#3a3f3d") for sw in switches.values()],
              views_out, elev_azims=((40, -60), (-55, -60)))


if __name__ == "__main__":
    main()
