"""Autoroute ble-key.kicad_pcb with Freerouting and refill the ground pours.

Ground is routed like any other net, then a grid of stitching vias ties the pours on both layers
together and extra vias join pour patches that traces have cut off. Exports a Specctra DSN, runs Freerouting 2.4.1 headless in its official Docker image (no network),
imports the session back and saves the board. Run with KiCad's Python after gen_board.py:

    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 route.py
"""

import subprocess
import sys
from pathlib import Path

import pcbnew

HERE = Path(__file__).parent
PCB = HERE / "ble-key.kicad_pcb"
DSN = HERE / "ble-key.dsn"
SES = HERE / "ble-key.ses"
IMAGE = "ghcr.io/freerouting/freerouting:2.4.1"
PASSES = int(sys.argv[1]) if len(sys.argv) > 1 else 40
GROUND = "GND"
STITCH_PITCH = 1.0      # mm grid for stitching vias
VIA_D, VIA_DRILL = 0.6, 0.3
BRIDGE_D, BRIDGE_DRILL = 0.45, 0.25    # AISLER ENIG minimum: 0.25 mm drill, 0.1 mm annular ring


def add_keepouts(zones):
    """KiCad's DSN export drops board-level rule areas; add them so the router respects them."""
    lines = []
    for z in zones:
        if not (z.GetIsRuleArea() and z.GetDoNotAllowTracks()):
            continue
        outline = z.Outline().Outline(0)
        pts = [outline.CPoint(i) for i in range(outline.PointCount())] + [outline.CPoint(0)]
        # DSN is in µm with y pointing up
        coords = " ".join(f"{round(pcbnew.ToMM(p.x) * 1000)} {round(-pcbnew.ToMM(p.y) * 1000)}" for p in pts)
        for layer in ("F.Cu", "B.Cu"):
            lines.append(f'    (keepout "{z.GetZoneName()}" (polygon {layer} 0 {coords}))')
    text = DSN.read_text()
    marker = "    (via "
    DSN.write_text(text.replace(marker, "\n".join(lines) + "\n" + marker, 1))


def holes(board):
    """(position, radius) of every drilled hole: vias and through-hole pads."""
    out = [(t.GetPosition(), t.GetDrill() / 2) for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    out += [(p.GetPosition(), max(p.GetDrillSizeX(), p.GetDrillSizeY()) / 2) for p in board.GetPads()
            if p.GetDrillSizeX() > 0]
    return out


def far_from_holes(existing, x, y, drill):
    gap = pcbnew.FromMM(0.35)            # AISLER: 0.3 mm between drills, plus margin
    return all((x - p.x) ** 2 + (y - p.y) ** 2 >= (r + drill / 2 + gap) ** 2 for p, r in existing)


def stitch(board, gnd):
    """Ground vias on a grid wherever both pours have room for one (outside part courtyards)."""
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    fills = [z.GetFilledPolysList(z.GetLayer()) for z in board.Zones()
             if not z.GetIsRuleArea() and z.GetNetname() == GROUND]
    courtyards = []
    for fp in board.GetFootprints():
        if fp.GetReference() == "U1":       # Raytac wants ground vias around and under the module
            continue
        for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            c = fp.GetCourtyard(layer)
            if c.OutlineCount():
                courtyards.append(c)
    bbox = board.GetBoardEdgesBoundingBox()
    r = pcbnew.FromMM(VIA_D / 2 + 0.2)
    step = pcbnew.FromMM(STITCH_PITCH)
    ring = [(0, 0)] + [(round(r * dx), round(r * dy)) for dx, dy in
                       ((1, 0), (-1, 0), (0, 1), (0, -1), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7))]
    placed = 0
    drilled = holes(board)
    y = bbox.GetY() + step
    while y < bbox.GetBottom():
        x = bbox.GetX() + step
        while x < bbox.GetRight():
            pts = [pcbnew.VECTOR2I(x + dx, y + dy) for dx, dy in ring]
            if all(f.Contains(p) for f in fills for p in pts) and \
                    not any(c.Contains(p) for c in courtyards for p in pts) and \
                    far_from_holes(drilled, x, y, pcbnew.FromMM(VIA_DRILL)):
                drilled.append((pcbnew.VECTOR2I(x, y), pcbnew.FromMM(VIA_DRILL) / 2))
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pcbnew.VECTOR2I(x, y))
                v.SetWidth(pcbnew.FromMM(VIA_D))
                v.SetDrill(pcbnew.FromMM(VIA_DRILL))
                v.SetNet(gnd)
                board.Add(v)
                placed += 1
            x += step
        y += step
    filler.Fill(board.Zones())
    return placed


def ground_fragments(board):
    """Connected groups of ground copper: fill fragments joined by vias, pads and tracks."""
    frags = []                               # (layer, SHAPE_POLY_SET with one outline)
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != GROUND:
            continue
        polys = z.GetFilledPolysList(z.GetLayer())
        for i in range(polys.OutlineCount()):
            one = pcbnew.SHAPE_POLY_SET()
            one.AddOutline(polys.Outline(i))
            for h in range(polys.HoleCount(i)):
                one.AddHole(polys.Hole(i, h))
            frags.append((z.GetLayer(), one))
    parent = list(range(len(frags)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union_at(point, layers):
        hit = [i for i, (layer, poly) in enumerate(frags) if layer in layers and poly.Contains(point)]
        for a, b in zip(hit, hit[1:]):
            parent[find(a)] = find(b)
        return hit

    both = (pcbnew.F_Cu, pcbnew.B_Cu)
    for t in board.GetTracks():
        if t.GetNetname() != GROUND:
            continue
        if t.GetClass() == "PCB_VIA":
            union_at(t.GetPosition(), both)
        else:                                 # a track joins whatever its two ends touch
            a = union_at(t.GetStart(), (t.GetLayer(),))
            b = union_at(t.GetEnd(), (t.GetLayer(),))
            if a and b:
                parent[find(a[0])] = find(b[0])
    for p in board.GetPads():
        if p.GetNetname() == GROUND:
            union_at(p.GetPosition(), both if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else (p.GetLayer(),))
    groups = {}
    for i in range(len(frags)):
        groups.setdefault(find(i), []).append(i)
    return frags, sorted(groups.values(), key=lambda g: -sum(frags[i][1].Area() for i in g))


def bridge_fragments(board, gnd):
    """Join cut-off pieces of ground to the main ground with a via wherever both overlap."""
    added = 0
    for _ in range(10):
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        frags, groups = ground_fragments(board)
        if len(groups) < 2:
            break
        main = groups[0]
        progress = False
        for g in groups[1:]:
            done = False
            for i in g:
                layer, poly = frags[i]
                others = [frags[j][1] for j in main if frags[j][0] != layer]
                box = poly.BBox()
                step = pcbnew.FromMM(0.1)
                r = pcbnew.FromMM(BRIDGE_D / 2 + 0.13)
                y = box.GetY()
                while y < box.GetBottom() and not done:
                    x = box.GetX()
                    while x < box.GetRight() and not done:
                        pts = [pcbnew.VECTOR2I(x + dx, y + dy) for dx, dy in
                               ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r))]
                        if all(poly.Contains(p) for p in pts) and \
                                any(all(o.Contains(p) for p in pts) for o in others) and \
                                far_from_holes(holes(board), x, y, pcbnew.FromMM(BRIDGE_DRILL)):
                            v = pcbnew.PCB_VIA(board)
                            v.SetPosition(pcbnew.VECTOR2I(x, y))
                            v.SetWidth(pcbnew.FromMM(BRIDGE_D))
                            v.SetDrill(pcbnew.FromMM(BRIDGE_DRILL))
                            v.SetNet(gnd)
                            board.Add(v)
                            added += 1
                            done = progress = True
                        x += step
                    y += step
                if done:
                    break
        if not progress:
            break
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return added


def freeroute(board, zones, passes):
    """One Freerouting pass on the board as it is (pours removed); replaces its tracks."""
    for z in zones:
        board.Remove(z)
    if not pcbnew.ExportSpecctraDSN(board, str(DSN)):
        raise SystemExit("DSN export failed")
    add_keepouts(zones)
    SES.unlink(missing_ok=True)
    subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{HERE}:/work", IMAGE,
                    "java", "-jar", "/app/freerouting-executable.jar",
                    "-de", f"/work/{DSN.name}", "-do", f"/work/{SES.name}", "-mp", str(passes),
                    "--gui-enabled=false", "--api_server-enabled=false"], check=True, cwd=HERE,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not SES.exists():
        raise SystemExit("Freerouting wrote no session")
    if not pcbnew.ImportSpecctraSES(board, str(SES)):
        raise SystemExit("SES import failed")
    # Freerouting necks tracks down between fine-pitch pads; bring them back to AISLER's minimum
    minimum = pcbnew.FromMM(0.125)
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < minimum:
            t.SetWidth(minimum)
    for z in zones:
        board.Add(z)


def route_once():
    board = pcbnew.LoadBoard(str(PCB))
    gnd = board.FindNet(GROUND)
    zones = list(board.Zones())
    # route everything, ground included, so every pad gets a real connection; then tie the two
    # ground pours together with stitching vias and join any pour patches the traces cut off
    freeroute(board, zones, PASSES)
    placed = stitch(board, gnd)
    placed += bridge_fragments(board, gnd)
    board.BuildConnectivity()
    return board, placed, board.GetConnectivity().GetUnconnectedCount(True)


def main():
    board, placed, unconnected = route_once()
    board.Save(str(PCB))
    print(f"routed {PCB}: {placed} stitching vias, {unconnected} unconnected")


if __name__ == "__main__":
    main()
