# Printable cases

`enclosure.py` (build123d, Python CAD) builds the cases for a XIAO ESP32-S3 or XIAO nRF52840 with a
3.5 mm paddle jack. It writes STEP and STL per part to `out/`, plus a lid STL turned over for
printing. `preview.html` shows the cases in 3D after the script has run. Three cases, all kept:

- **USB** (`out/usb/`): the small case without a battery, the official version today.
- **Battery, drop-in frame** (`out/battery/`): the cell soldered in, under the board in a frame.
- **Modular** (`out/modular/`, XIAO nRF52840): a USB base unit and a battery tray that screws on
  underneath, at once or as a later upgrade (see [The battery tray](#the-battery-tray)).

| Case | Outer size, Cliff FC681374V (default) | with `--jack pj392` |
|---|---|---|
| USB | 48.5 × 25.0 × 14.1 mm | 43.0 × 25.0 × 13.6 mm |
| Battery under the board, drop-in frame | 53.2 × 30.5 × 21.1 mm | 53.2 × 30.5 × 20.1 mm |
| Modular base unit | 57.9 × 30.5 × 14.5 mm | 57.9 × 30.5 × 14.5 mm |
| Modular base unit with battery tray | 57.9 × 30.5 × 22.8 mm | 57.9 × 30.5 × 22.8 mm |

**The jack.** The default is the **Cliff FC681374V** (Reichelt 228160): M8 × 0.75 thread through an
8.5 mm slot in the full 2 mm wall, open to the top and closed by a tab on the lid, ring nut outside,
square body 10.5 × 9 × 13.5 mm plus 4 mm pins inside. The floor (USB case) or the frame's cradle
(battery case) keeps the square body from turning when the nut is tightened.
Pins: 3 = tip (D1), 2 = ring (D2), 1 = sleeve (GND), 4 = switch contact, unused. The **PJ-392**
(TinyTronics; round 8 mm body, 6.5 mm hole, 12 mm deep) still works with `--jack pj392`, which
writes the same file names, so regenerate before printing.

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python enclosure.py          # MJF / SLA print service, 0.25 mm fit
.venv/bin/python enclosure.py --fdm    # own FDM printer (PETG), 0.35 mm fit → out/usb-fdm/, out/modular-fdm/, out/battery-fdm/
.venv/bin/python enclosure.py --snap-test   # FDM test pieces for the snap lips → out/snap-test-fdm/
.venv/bin/python enclosure.py --jack pj392   # any of the above for the PJ-392 instead of the Cliff jack
```

**Printing in PETG on an FDM printer** (e.g. Bambu Lab A1 mini): use the base upright, floor on
the plate, and the lid's `-lid-print.stl` (already turned over), from `out/usb-fdm/`,
`out/modular-fdm/` or `out/battery-fdm/`; for the modular case's battery key also
`ble-key-modular-fdm-tray.stl`, floor on the plate. 0.2 mm layers, 3 walls, 20 % infill, no
supports. Screws: countersunk self-tapping 2.2 × 6.5 (DIN 7982): 2 for the USB case, 4 for the
battery case, 4 for the modular case plus 4 for its tray, one in each corner; the lid has 90°
countersinks for them. The jack drops into a slot in the end wall that is open to the top (the lid
closes it with a tab), so it goes in already soldered to the board; then tighten its ring nut.

**Holding the board:** in all three cases the board clicks in: four springy snap lips hook over the
long edges (0.52 mm in the USB and battery cases, 0.7 mm in the modular one), so it stays put with
the lid off; each lip goes on as a tab 2 mm above the board, to push it open with a small
screwdriver. They sit where the edge is straight: 4 mm in from each end, between the first and
second castellated pad; in the battery and modular cases the pair at the USB end sits 6.7 mm in,
between the second and third pad, clear of the corner bosses there. The XIAO's corners are rounded
(r ≈ 2 mm), so a lip at a corner would not reach the edge. The board sits 3 mm above the floor in
the USB case and 5 mm in the modular one. With the lid on, the
tab presses on the USB-C socket and two stiff L-shaped ribs press on the far corners. If a lip holds
too little or breaks, tune `SNAP_STRAIN` and `SNAP_HOOK` in `enclosure.py`: each hook is as big as
its lip's free height allows within `SNAP_STRAIN` (4 %), at most `SNAP_HOOK`. Try the fit first with
the test pieces from `--snap-test`: a 7 mm slice of the USB base and of the battery frame around the
far supports, and a 15 mm stand-in for the board's end (or use the real XIAO).

## The battery tray

The base unit has everything the battery needs from the start, so a key bought without a battery
can get one later without soldering:

- **Battery lead:** every key gets a short lead with a JST-PH plug, soldered to the XIAO
  nRF52840's `BAT` pads (on the underside between D2 and D3) when it is built. Without a battery it
  waits under the board, which sits 5 mm above the floor so the plug fits there.
- **Knock-out:** right under the plug, a 5.4 × 7.5 mm plate in the floor, held only by 0.3 mm of
  floor in a groove round it. A small dimple in its middle marks it from below.
- **Corner columns:** one in each corner, from the floor to the lid. The lid's four screws go in
  from above, the tray's four from below, into the same columns. Without a tray the holes from
  below stay closed by a 0.4 mm skin with a centring dimple; the tray's screws go through it.

The case is as wide as the corner columns need beside the board at the USB end (the board reaches
right up to that wall) and as long as the tray needs to hold the cell between the corner columns
at the jack end.

The tray is the base's footprint and 8.3 mm tall; the base's floor closes it. The LP-552035 lies
between the jack-end corner columns, held across by two low rails; a low rib with a gap for its
lead separates it from the 10 mm bay at the USB end where its JST-PH plug meets the board's lead.
Four countersunk 2.2 × 6.5 screws (DIN 7982; 6 mm works too), one in each corner, from below, their
heads in counterbores. Prints floor down, without supports.

To fit a battery: push the knock-out out from below with a small screwdriver and pull the plug
through; the case stays closed. Tape the cell into the tray, plug the leads together in the bay and
screw the tray on with its four screws.

## The XIAO battery case (drop-in frame)

Three layers and three parts: the LP-552035 lies flat in a pocket on the floor of the base, a 3 mm
wiring layer sits above it, and the XIAO sits on top in a **frame** that drops into the base on top
of the cell. Everything that holds the board is on the frame.

**Screws:** 4 × countersunk self-tapping 2.2 × 6.5 (DIN 7982; 6 mm works too, 8 mm does not), one in
each corner. The lid is screwed to the base itself: a boss hangs in each of the base's corners from
the top, 6.5 mm deep with a 5.5 mm pilot hole, and below it a 45° slope runs back into the walls, so
it prints without supports. The case is 3 mm wider than the cell needs, so the two bosses at the USB
end stand clear beside the board, which reaches right up to that wall; the frame is cut away round
all four bosses and drops in past them. The cell's far corners at the USB end reach about 1 mm under
those two bosses: put the cell in tilted, USB end first, then lower the jack end.

The frame's two low rails rest on shoulders along the long walls, 0.5 mm above the cell, and are
joined by a cross bar between the jack and the board (the wires pass over it), by the jack's cradle
at the jack end and by a cross wall at the USB end that carries the board's end; the corner bosses
cut the rails short of that wall, so a bar under each of the board's long edges ties it back to
them. A web along the outside of each rail, up to the board, makes the rails L-shaped and stiff. On
the rails: four 45° brackets under the board's corners, the four snap lips (rising free from a thin
floor in pockets in the rails, just above the frame's underside, 0.52 mm hook) and the cradle the jack
rests in. With the lid on, its tab presses on the USB-C socket and two stiff ribs hung from its lip
press the board's far corners down right above the brackets, so the lid holds the frame down
through the board. The frame is flat underneath and prints as it sits, without supports; print
base, frame and lid in one go.

Everything is soldered directly, no connectors: the jack's wires to D1 / D2 / GND and the cell's
lead (plug cut off) to the BAT pads, all on the board's underside, so every wire runs in the wiring
layer, out of sight. Board, jack and frame are put together on the bench and lowered in as one
module: the jack's thread drops into a slot in the end wall that is open to the top (the lid closes
it with a tab), then the ring nut goes on outside. To change the cell, unscrew the lid and lift the
frame out with everything on it. Under the jack is a 10 mm bay for the cell's spare lead, separated
from the cell by a low rib with a gap for the lead. Keep the joints under the board flat (3 mm is
the limit) and tape the cell to the floor; it has 0.5 mm of play up to the frame.

## XIAO ESP32-S3 and XIAO nRF52840

Both XIAO cases fit either board: the two share the outline, board thickness and USB-C position
(checked against Seeed's STEP models, `vendor/XIAO-ESP32S3 v2.step` and
`vendor/nrf/XIAO-nRF52840 v15.step`), and the lid's two hold-down ribs sit on bare board on both.
The light holes are placed for the ESP32-S3's LEDs; on the nRF52840 they are not verified.
