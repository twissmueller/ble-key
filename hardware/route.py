"""Autoroute ble-key.kicad_pcb with Freerouting and refill the ground pours.

Exports a Specctra DSN, runs Freerouting 2.4.1 headless in its official Docker image (no network),
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


def main():
    board = pcbnew.LoadBoard(str(PCB))
    # route on a board without pours, so the router sees the real copper; pours come back after
    zones = list(board.Zones())
    for z in zones:
        board.Remove(z)
    if not pcbnew.ExportSpecctraDSN(board, str(DSN)):
        raise SystemExit("DSN export failed")
    add_keepouts(zones)
    SES.unlink(missing_ok=True)
    subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{HERE}:/work", IMAGE,
                    "java", "-jar", "/app/freerouting-executable.jar",
                    "-de", f"/work/{DSN.name}", "-do", f"/work/{SES.name}", "-mp", str(PASSES),
                    "--gui-enabled=false", "--api_server-enabled=false"], check=True, cwd=HERE,
                   stdout=subprocess.DEVNULL)
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
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(str(PCB))
    print("routed", PCB)


if __name__ == "__main__":
    main()
