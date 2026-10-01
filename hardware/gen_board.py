"""Generate the ble-key board (ble-key.kicad_pcb) from the schematic's netlist.

Places every footprint at the positions in PLACEMENT, assigns the nets from ble-key.net, draws
the outline, mounting holes and ground pours, and writes ble-key.kicad_pcb (unrouted).
Routing is done afterwards by route.sh (Freerouting).

Run with KiCad's own Python, which has the pcbnew module:

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_board.py

Board frame: origin at the top-left corner, x to the right, y down, millimetres. The antenna end
of the module is on the top edge, USB-C on the right edge, the paddle jack on the left edge.
"""

import re
from pathlib import Path

import pcbnew

HERE = Path(__file__).parent
NETLIST = HERE / "ble-key.net"
OUT = HERE / "ble-key.kicad_pcb"
FP_ROOT = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")

W, H = 46.0, 26.0          # board size
ORIGIN = (100.0, 100.0)    # where the board sits on KiCad's page
CORNER = 1.5               # outline corner radius
MX, MY = 25.0, 8.29        # module centre: antenna flush with the top edge
ANT_X0, ANT_X1, ANT_DEPTH = 12.0, 34.0, 4.2   # copper-free strip along the top edge around the antenna

# ref: (x, y, rotation in degrees, side)  — side "F" or "B"
PLACEMENT = {
    # module, antenna on the top edge; crystal, DC/DC inductor and decoupling below its pad row
    "U1": (MX, MY, 0, "F"),
    "C9": (19.8, 18.2, 90, "F"),
    "Y1": (22.2, 18.2, 0, "F"),
    "C10": (24.5, 18.2, 90, "F"),
    "L1": (26.0, 18.2, 90, "F"),
    "C6": (27.8, 18.2, 90, "F"),
    "C8": (29.6, 18.2, 90, "F"),
    "C5": (27.4, 21.4, 90, "F"),
    "C7": (29.0, 21.4, 90, "F"),
    # status LEDs below the module
    "D1": (17.2, 21.4, 0, "F"),
    "R12": (20.1, 21.4, 0, "F"),
    "D2": (22.9, 21.4, 0, "F"),
    "R13": (25.5, 21.4, 0, "F"),
    # USB-C on the right edge, opening to +x, with CC resistors, ESD and series resistors
    "J1": (W - 3.675, 12.0, 90, "F"),
    "R1": (36.0, 3.8, 0, "F"),
    "R2": (36.0, 2.2, 0, "F"),
    "U3": (34.2, 10.5, 0, "F"),
    "R14": (32.4, 15.4, 90, "F"),
    "R15": (34.0, 15.4, 90, "F"),
    # charger in the bottom-right corner, reset button on the bottom edge
    "U2": (35.0, 20.6, 0, "F"),
    "C1": (39.9, 19.0, 0, "F"),
    "C2": (31.2, 20.6, 90, "F"),
    "C3": (34.0, 24.4, 0, "F"),
    "R3": (37.0, 24.4, 0, "F"),
    "R4": (31.4, 24.0, 90, "F"),
    "R5": (30.0, 24.0, 90, "F"),
    "SW1": (42.0, 23.2, 180, "F"),
    # battery: JST at the top-left, cable entering from the left edge; divider and pull-ups beside it
    "J3": (5.5, 5.0, 270, "F"),
    "R8": (12.5, 6.2, 90, "F"),
    "R9": (14.0, 6.2, 90, "F"),
    "C4": (15.5, 6.2, 90, "F"),
    "R6": (17.0, 6.2, 90, "F"),
    "R7": (18.5, 6.2, 90, "F"),
    # paddle jack on the left edge, opening to -x, series resistors beside it
    "J2": (6.0, 16.0, 90, "F"),
    "R10": (17.0, 13.0, 90, "F"),
    "R11": (17.0, 16.0, 90, "F"),
    # SWD pads on the back, below the jack
    "J4": (5.5, 23.8, 0, "B"),
}

MOUNTING_HOLES = [(W - 2.6, 2.6), (12.4, 24.1)]

# net classes: (track width, clearance)
CLASSES = {
    "Default": (0.2, 0.15),
    "Power": (0.3, 0.15),
    "Fine": (0.15, 0.125),    # escape between the module's outer pads to the inner-row reset pad
}
NET_CLASS = {
    "GND": "Power", "VBUS": "Power", "VSYS": "Power", "VBAT": "Power", "VDD": "Power", "DCCH": "Power",
    "~{RESET}": "Fine",
}


# --- netlist ------------------------------------------------------------------------------------
def sexpr(text):
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            last = stack.pop()
            stack[-1].append(last)
        else:
            stack[-1].append(t[1:-1].replace('\\"', '"') if t.startswith('"') else t)
    return stack[0][0]


def field(node, key):
    for item in node[1:]:
        if isinstance(item, list) and item and item[0] == key:
            return item
    return None


def read_netlist():
    tree = sexpr(NETLIST.read_text())
    comps = {}
    for c in field(tree, "components")[1:]:
        ref = field(c, "ref")[1]
        comps[ref] = {"value": field(c, "value")[1], "footprint": field(c, "footprint")[1]}
    nets = {}
    for n in field(tree, "nets")[1:]:
        name = field(n, "name")[1]
        if name.startswith("unconnected-"):
            continue
        name = name.removeprefix("/")          # local labels on the single sheet
        for node in n[1:]:
            if isinstance(node, list) and node[0] == "node":
                nets.setdefault(name, []).append((field(node, "ref")[1], field(node, "pin")[1]))
    return comps, nets


# --- board --------------------------------------------------------------------------------------
def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(ORIGIN[0] + x), pcbnew.FromMM(ORIGIN[1] + y))


def load_fp(lib_id):
    lib, name = lib_id.split(":")
    fp = pcbnew.FootprintLoad(str(FP_ROOT / f"{lib}.pretty"), name)
    if fp is None:
        raise SystemExit(f"footprint not found: {lib_id}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def outline(board):
    r = CORNER
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(mm(*a)); s.SetEnd(mm(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)
    def arc(center, start, angle):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetCenter(mm(*center)); s.SetStart(mm(*start))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T), True)
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)
    seg((r, 0), (W - r, 0)); seg((W, r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, r))
    arc((W - r, r), (W - r, 0), 90)
    arc((W - r, H - r), (W, H - r), 90)
    arc((r, H - r), (r, H), 90)
    arc((r, r), (0, r), 90)


def antenna_keepout(board):
    """Raytac: no copper beside the antenna on any layer, extended sideways as far as possible."""
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetLayerSet(pcbnew.LSET.AllCuMask())
    z.SetZoneName("antenna keep-out")
    poly = z.Outline()
    poly.NewOutline()
    for x, y in ((ANT_X0, 0), (ANT_X1, 0), (ANT_X1, ANT_DEPTH), (ANT_X0, ANT_DEPTH)):
        poly.Append(mm(x, y))
    board.Add(z)


def ground_zone(board, layer, net):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net)
    z.SetZoneName(f"GND {board.GetLayerName(layer)}")
    z.SetLocalClearance(pcbnew.FromMM(0.2))
    z.SetMinThickness(pcbnew.FromMM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)   # SMD pads solid, THT relieved
    z.SetThermalReliefGap(pcbnew.FromMM(0.25))
    z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.3))
    poly = z.Outline()
    poly.NewOutline()
    for x, y in ((0, 0), (W, 0), (W, H), (0, H)):
        poly.Append(mm(x, y))
    board.Add(z)


def net_settings(board):
    ns = board.GetDesignSettings().m_NetSettings
    for name, (width, clearance) in CLASSES.items():
        nc = ns.GetDefaultNetclass() if name == "Default" else pcbnew.NETCLASS(name)
        nc.SetTrackWidth(pcbnew.FromMM(width))
        nc.SetClearance(pcbnew.FromMM(clearance))
        nc.SetViaDiameter(pcbnew.FromMM(0.6))
        nc.SetViaDrill(pcbnew.FromMM(0.3))
        nc.SetDiffPairWidth(pcbnew.FromMM(0.2))
        nc.SetDiffPairGap(pcbnew.FromMM(0.15))
        if name != "Default":
            ns.SetNetclass(name, nc)
    for net, cls in NET_CLASS.items():
        ns.SetNetclassPatternAssignment(net, cls)


def build():
    comps, nets = read_netlist()
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    ds.m_MinClearance = pcbnew.FromMM(0.125)
    ds.m_TrackMinWidth = pcbnew.FromMM(0.125)
    ds.m_ViasMinSize = pcbnew.FromMM(0.5)
    ds.m_MinThroughDrill = pcbnew.FromMM(0.25)
    ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
    ds.m_HoleToHoleMin = pcbnew.FromMM(0.3)
    ds.m_HoleClearance = pcbnew.FromMM(0.15)   # KiCad's USB4105 footprint has 0.19 mm pad-to-NPTH

    netinfo = {}
    for name in sorted(nets):
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        netinfo[name] = n
    net_settings(board)

    pin_net = {(ref, pin): name for name, nodes in nets.items() for ref, pin in nodes}
    missing = sorted(set(comps) - set(PLACEMENT))
    if missing:
        raise SystemExit(f"no placement for: {', '.join(missing)}")

    for ref, c in sorted(comps.items()):
        fp = load_fp(c["footprint"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        x, y, rot, side = PLACEMENT[ref]
        board.Add(fp)
        if side == "B":
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(mm(x, y))
        # references on the fab layer only: the board is too dense for readable silkscreen labels
        fp.Reference().SetLayer(pcbnew.B_Fab if side == "B" else pcbnew.F_Fab)
        for pad in fp.Pads():
            net = pin_net.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(netinfo[net])

    for i, (x, y) in enumerate(MOUNTING_HOLES, 1):
        fp = load_fp("MountingHole:MountingHole_2.2mm_M2")
        fp.SetReference(f"H{i}")
        fp.SetValue("M2")
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM
                         | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        fp.SetPosition(mm(x, y))
        fp.Reference().SetLayer(pcbnew.F_Fab)
        board.Add(fp)

    antenna_keepout(board)
    outline(board)
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        ground_zone(board, layer, netinfo["GND"])
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(OUT))
    print("wrote", OUT)


if __name__ == "__main__":
    build()
