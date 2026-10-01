"""Export the Seeed Fusion PCBA files: Gerbers + drill (zipped), BOM and pick-and-place.

    python3 export_seeed.py

writes seeed/ble-key-gerbers.zip, seeed/ble-key-bom.csv (Fusion template: Designator, MPN/Seeed SKU,
Qty, Link) and seeed/ble-key-pnp.csv. Seeed accepts a manufacturer part number or a Seeed SKU per
line; the module goes in as Seeed's own SKU, which Seeed stocks.
"""

import csv
import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import export_jlc as jlc

HERE = Path(__file__).parent
OUT = HERE / "seeed"

# Manufacturer part numbers (or Seeed SKUs) by schematic reference. Chips and connectors use the
# schematic's MPN field; the generic passives use the parts JLCPCB matched, which are real MPNs.
MPN = {
    "U1": ("113990582", ""),   # Seeed SKU of the MDBT50Q-1MV2
    "C1": ("CL05A105KA5NQNC", ""), "C2": ("CL10A475KO8NNNC", ""), "C3": ("CL10A475KO8NNNC", ""),
    "C4": ("CL05B104KO5NNNC", ""), "C7": ("CL05B104KO5NNNC", ""),
    "C5": ("CL10A106KP8NNNC", ""), "C6": ("CL10A106KP8NNNC", ""), "C8": ("CL10A106KP8NNNC", ""),
    "R1": ("0402WGF5101TCE", ""), "R2": ("0402WGF5101TCE", ""), "R5": ("0402WGF5101TCE", ""),
    "R3": ("0402WGF1002TCE", ""), "R4": ("0402WGF3091TCE", ""),
    "R6": ("0402WGF1003TCE", ""), "R7": ("0402WGF1003TCE", ""),
    "R8": ("0402WGF1004TCE", ""), "R9": ("0402WGF1004TCE", ""),
    "R10": ("0402WGF4700TCE", ""), "R11": ("0402WGF4700TCE", ""),
    "R12": ("0402WGF1001TCE", ""), "R13": ("0402WGF1001TCE", ""),
    "R14": ("0402WGF270JTCE", ""), "R15": ("0402WGF270JTCE", ""),
}


def bom():
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "bom.csv"
        jlc.run("sch", "export", "bom", "--fields", "Reference,Value,MPN", "--exclude-dnp",
                "-o", str(raw), str(jlc.SCH))
        rows = list(csv.DictReader(io.StringIO(raw.read_text())))
    lines, refs, missing = {}, set(), []
    for r in rows:
        for ref in (x.strip() for x in r["Reference"].split(",")):
            mpn, link = MPN.get(ref, (r["MPN"], ""))
            if not mpn:
                missing.append(ref)
                continue
            lines.setdefault((mpn, link), []).append(ref)
            refs.add(ref)
    target = OUT / "ble-key-bom.csv"
    with target.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "MPN/Seeed SKU", "Qty", "Link"])
        for (mpn, link), designators in sorted(lines.items(), key=lambda kv: kv[1][0]):
            w.writerow([",".join(sorted(designators)), mpn, len(designators), link])
    return target, refs, missing


def pnp(refs):
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "pos.csv"
        jlc.run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                "-o", str(raw), str(jlc.PCB))
        rows = list(csv.DictReader(io.StringIO(raw.read_text())))
    target = OUT / "ble-key-pnp.csv"
    with target.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X(mm)", "Mid Y(mm)", "Layer", "Rotation"])
        for r in rows:
            if r["Ref"] in refs:
                layer = "T" if r["Side"].lower() == "top" else "B"
                w.writerow([r["Ref"], f'{float(r["PosX"]):.3f}', f'{float(r["PosY"]):.3f}', layer,
                            f'{float(r["Rot"]) % 360:g}'])
    return target


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    jlc.OUT = OUT
    g = jlc.gerbers()
    b, refs, missing = bom()
    p = pnp(refs)
    for f in (g, b, p):
        print("wrote", f.relative_to(HERE))
    if missing:
        print("no MPN:", ", ".join(missing))


if __name__ == "__main__":
    main()
