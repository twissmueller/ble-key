"""Export the JLCPCB production files: Gerbers + drill (zipped), BOM and placement (CPL).

    python3 export_jlc.py

writes jlcpcb/ble-key-gerbers.zip, jlcpcb/ble-key-bom.csv and jlcpcb/ble-key-cpl.csv. Parts come
from the schematic; each needs an "LCSC" field (JLCPCB's part number, e.g. C5118826). Parts without
one are listed so they can be fixed in gen_schematic.py.
"""

import csv
import io
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "jlcpcb"
KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
PCB = HERE / "ble-key.kicad_pcb"
SCH = HERE / "ble-key.kicad_sch"

LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"

# JLCPCB's part models are not always oriented like KiCad's footprints. After uploading, check the
# placement preview and put corrections (degrees, added to KiCad's rotation) here.
ROTATION_FIX = {}


def run(*args):
    subprocess.run([KICAD_CLI, *args], check=True, stdout=subprocess.DEVNULL)


def gerbers():
    with tempfile.TemporaryDirectory() as tmp:
        run("pcb", "export", "gerbers", "--layers", LAYERS, "-o", tmp + "/", str(PCB))
        run("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
            "--drill-origin", "absolute", "-o", tmp + "/", str(PCB))
        target = OUT / "ble-key-gerbers.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(Path(tmp).iterdir()):
                z.write(f, f.name)
    return target


def bom():
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "bom.csv"
        run("sch", "export", "bom", "--fields", "Value,Reference,Footprint,LCSC,${QUANTITY}",
            "--group-by", "Value,Footprint,LCSC", "--exclude-dnp", "-o", str(raw), str(SCH))
        rows = list(csv.DictReader(io.StringIO(raw.read_text())))
    missing, refs = [], set()
    target = OUT / "ble-key-bom.csv"
    with target.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for r in rows:
            designators = r["Reference"]
            refs.update(d.strip() for d in designators.split(","))
            footprint = r["Footprint"].split(":")[-1]
            if not r["LCSC"]:
                missing.append(designators)
            w.writerow([r["Value"], designators, footprint, r["LCSC"]])
    return target, refs, missing


def cpl(refs):
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "pos.csv"
        run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
            "-o", str(raw), str(PCB))
        rows = list(csv.DictReader(io.StringIO(raw.read_text())))
    target = OUT / "ble-key-cpl.csv"
    with target.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            ref = r["Ref"]
            if ref not in refs:              # mounting holes, the SWD pads: nothing to place
                continue
            rot = (float(r["Rot"]) + ROTATION_FIX.get(ref, 0)) % 360
            layer = "Top" if r["Side"].lower() == "top" else "Bottom"
            w.writerow([ref, f'{float(r["PosX"]):.3f}mm', f'{float(r["PosY"]):.3f}mm', layer, f"{rot:g}"])
    return target


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    g = gerbers()
    b, refs, missing = bom()
    c = cpl(refs)
    for p in (g, b, c):
        print("wrote", p.relative_to(HERE))
    if missing:
        print("no LCSC part number:", "; ".join(missing))


if __name__ == "__main__":
    main()
