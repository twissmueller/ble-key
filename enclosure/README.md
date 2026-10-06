# Printable cases

`enclosure.py` (build123d, Python CAD) builds the case for a XIAO ESP32-S3 or XIAO nRF52840 with a
3.5 mm paddle jack, in two versions. It writes STEP and STL per part to `out/`, plus a lid STL turned
over for printing. `preview.html` shows both cases in 3D after the script has run.

| Case | Outer size, Cliff FC681374V (default) | with `--jack pj392` |
|---|---|---|
| USB only | 48.5 × 25.0 × 14.1 mm | 43.0 × 25.0 × 13.6 mm |
| Battery under the board | 53.2 × 25.3 × 20.2 mm | 53.2 × 25.3 × 19.2 mm |

**The jack.** The default is the **Cliff FC681374V** (Reichelt 228160): M8 × 0.75 thread through an
8.5 mm hole in the full 2 mm wall, ring nut outside, square body 10.5 × 9 × 13.5 mm plus 4 mm pins
inside. A block under the lid sits on the body's flat top, so tightening the nut cannot turn it.
Pins: 3 = tip (D1), 2 = ring (D2), 1 = sleeve (GND), 4 = switch contact, unused. The **PJ-392**
(TinyTronics; round 8 mm body, 6.5 mm hole, 12 mm deep) still works with `--jack pj392`, which
writes the same file names, so regenerate before printing.

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python enclosure.py          # MJF / SLA print service, 0.25 mm fit
.venv/bin/python enclosure.py --fdm    # own FDM printer (PETG), 0.35 mm fit → out/usb-fdm/, out/battery-fdm/
.venv/bin/python enclosure.py --snap-test   # FDM test pieces for the snap lips → out/snap-test-fdm/
.venv/bin/python enclosure.py --jack pj392   # any of the above for the PJ-392 instead of the Cliff jack
```

**Printing the XIAO case in PETG on an FDM printer** (e.g. Bambu Lab A1 mini): use
`out/usb-fdm/ble-key-usb-fdm-base.stl` upright, floor on the plate, and
`out/usb-fdm/ble-key-usb-fdm-lid-print.stl` (already turned over). 0.2 mm layers, 3 walls, 20 %
infill, no supports. Screws: 2 × countersunk self-tapping 2.2 × 6.5 (DIN 7982); the lid has 90°
countersinks for them.

**Holding the board:** in both XIAO cases the board clicks in: four springy snap lips beside its
corners hook 0.25 mm over the long edges, so it stays put with the lid off. With the lid on, the
tab presses on the USB-C socket and two stiff L-shaped ribs press on the far corners. If a lip
holds too little or breaks, tune `SNAP_HOOK`, `SNAP_T` and `SNAP_ROOT` in `enclosure.py`. Try the
fit first with the test pieces from `--snap-test`: a 5.8 mm slice of each base around the far
supports, and a 15 mm stand-in for the board's end (or use the real XIAO).

## The XIAO battery case

Three layers instead of a second compartment: the LP-552035 lies flat on the floor, a 3 mm wiring
layer sits above it, and the XIAO rests on four 45° brackets on the side walls on top (no
supports needed when printing). Each bracket has a springy snap lip with a 0.25 mm hook over the
board's edge, so the board clicks in and stays put with the lid off; with the lid on, two stiff
ribs hung from its lip press the far corners down right above the brackets. The BAT pads and the
paddle wires are soldered on the board's underside, so every wire runs in that layer, out of sight. The jack sits above the cell; under it
is a 10 mm bay for the mated JST-PH pair and the spare lead, separated from the cell by a low rib
with a gap for the lead. Four countersunk screws go into bosses that hang from the side walls
above the cell. Keep the joints under the board flat — 3 mm is the limit — and tape the cell to
the floor, it has 0.5 mm of play upwards.

## XIAO ESP32-S3 and XIAO nRF52840

Both XIAO cases fit either board: the two share the outline, board thickness and USB-C position
(checked against Seeed's STEP models, `vendor/XIAO-ESP32S3 v2.step` and
`vendor/nrf/XIAO-nRF52840 v15.step`), and the lid's two hold-down ribs sit on bare board on both.
The light holes are placed for the ESP32-S3's LEDs; on the nRF52840 they are not verified.
