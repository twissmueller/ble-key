# ble-key nRF52840 board — schematic

The custom board from [PCB-PLAN.md](../PCB-PLAN.md): a Raytac MDBT50Q-1MV2 (nRF52840), a BQ24074
charger with power path, USB-C, a 3.5 mm paddle jack and a JST-PH socket for the LiPo.

| File | What |
|---|---|
| `ble-key.kicad_pro`, `ble-key.kicad_sch` | KiCad 10 project and schematic — open the project in KiCad |
| `ble-key-schematic.pdf` | the schematic as a PDF |
| `ble-key-bom.csv` | parts list with MPNs where chosen |
| `gen_schematic.py` | generates the schematic; the parts, values and nets live here |

**Status:** schematic only, passes KiCad's electrical rules check (0 errors; 2 warnings that two
derived library symbols are stored flattened). No layout yet.

## Design

| Block | Choice |
|---|---|
| USB-C | GCT USB4105, 5.1 kΩ on CC1/CC2 (5 V sink), USBLC6-2SC6 ESD, 27 Ω series resistors to the module (Raytac reference) |
| Charger | BQ24074: 175 mA charge (R_ISET 5.1 kΩ, 0.5 C for 350 mAh), 500 mA input limit (R_ILIM 3.09 kΩ, EN2 = 1, EN1 = 0), TS on 10 kΩ (no thermistor), ITERM and TMR open for the datasheet defaults (10 % termination, 5 h safety timer) |
| Power | BQ24074 OUT (VSYS: 4.4 V on USB, battery voltage otherwise) feeds the module's VDDH. VDD is the module's own 3.3 V output, through its REG0 DC/DC converter with L1 (Raytac spec §8.1) |
| Module | MDBT50Q-1MV2, 32.768 kHz crystal on P0.00/P0.01 (the module has none) |
| Battery level | 1 MΩ + 1 MΩ divider with 100 nF into P0.29 / AIN5, about 2 µA drain |
| Charger status | ~PGOOD (USB present) on P0.30, ~CHG (charging) on P0.28, 100 kΩ pull-ups to VDD |
| Paddle | tip → 470 Ω → P0.04 (dit), ring → 470 Ω → P0.05 (dah), sleeve → GND; internal pull-ups |
| LEDs, reset | red P1.15, blue P1.10 — the Feather nRF52840 pins, so its bootloader drives them; reset button on P0.18 |
| Programming | Tag-Connect TC2030 pads for SWD (no part fitted) |

## Before layout

- **UICR.REGOUT0 = 3.3 V** must be written when the bootloader is flashed over SWD. In VDDH mode
  the nRF52840 starts with VDD at 1.8 V.
- **BQ24074 footprint:** KiCad's default has a 1.6 mm exposed pad, TI's drawing for the related
  RGT0016C package shows 1.68 mm. Check TI's RGT0016B drawing for the BQ24074 and pick the matching
  footprint.
- **Reset switch:** the footprint is Panasonic EVQ-PUC (side push). The EVP-AKE31A from the plan
  has no footprint in KiCad's library and would need a custom one.
- **MPNs still to choose** for the passives, L1 (10 µH 0603, ≥ 80 mA) and Y1 (32.768 kHz,
  2.0 × 1.2 mm, load capacitance matching the 12 pF capacitors), so AISLER can match them.
- **Layout rules from Raytac:** module at the board edge with the antenna end outward, a 3.8 mm
  copper-free strip across the antenna end on every layer, plenty of GND vias at the module corners.
  Raytac reviews layouts for free (service@raytac.com).

## Regenerating

The generator copies symbols from KiCad's standard libraries into `.kilib/` (not committed):

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
mkdir -p .kilib && docker run --rm --platform linux/amd64 -v "$PWD/.kilib":/out kicad/kicad:10.0 bash -c 'cd /usr/share/kicad/symbols && cp RF_Module.kicad_sym Battery_Management.kicad_sym Connector.kicad_sym Connector_Audio.kicad_sym Power_Protection.kicad_sym Device.kicad_sym Switch.kicad_sym power.kicad_sym /out/'
.venv/bin/python gen_schematic.py
```

With KiCad installed, the libraries can be copied from `/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/`
instead, and `kicad-cli sch erc ble-key.kicad_sch` checks the result.
