# Printable cases

Two scripts, both in build123d (Python CAD). Each writes STEP and STL per part to `out/`, plus a lid
STL turned over for printing. `preview.html` shows all four cases in 3D after the scripts have run.

| Script | Case | Outer size |
|---|---|---|
| `board_case.py` | **nRF52840 board** from `../hardware`, USB only | 52.4 × 31.6 × 12.4 mm |
| `board_case.py` | **nRF52840 board** with the 350 mAh LP-552035 in the lid | 52.4 × 31.6 × 18.8 mm |
| `enclosure.py` | XIAO ESP32-S3 + PJ-392 panel jack, USB only | 43.0 × 25.0 × 13.6 mm |
| `enclosure.py` | XIAO ESP32-S3 + PJ-392, battery beside it | 43.0 × 48.0 × 13.6 mm |

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python board_case.py
.venv/bin/python enclosure.py
```

## The nRF52840 board case

- **Two parts, two screws.** The base holds the board on two standoffs and four pads, 1.5 mm off
  the floor; its walls end flush with the board's top. Two **M2 × 8 self-tapping screws** go up
  through the base, the board's mounting holes and into posts in the lid, clamping it all.
- **Openings:** the lid's walls arch over the USB-C socket and the paddle jack, so the board drops in
  from above. The jack's barrel ends flush with the outside; the wall at USB-C is 1.55 mm, so a
  USB-C plug's overmold (which sits 1.85 mm in front of the socket) always seats.
- **Reset:** a flexible tongue in the wall with a nub that reaches the side-push switch.
- **Status LEDs:** a light channel from the two LEDs up through the lid.
- **Battery version:** the cell is taped into a pocket under the lid, above the board, located by two
  ribs and clear of the antenna strip along the top edge. Its spare lead tucks under the cell next to
  the JST socket.

Positions come from `../hardware/mechanics.json` and the board model from
`vendor/ble-key-board.step` (exported with `kicad-cli pcb export step`). Re-export both after a
layout change. Connector heights are from the Same Sky SJ-352x-SMT, GCT USB4105, JST PH and
Panasonic EVQ-PU drawings; the cell is sized to the worst case of PKCELL's drawings (37 × 20.3 ×
5.8 mm) plus 0.5 mm for swelling.

**Before ordering prints,** check one sample of the actual cell and its plug polarity, and print
one case to test the reset tongue's feel and the screw posts' grip.
