# Custom PCB plan — nRF52840 key, built by AISLER

**Status:** plan, nothing ordered. Prices were checked on 1 October 2026 and are **net (no VAT)**
unless marked. Figures marked *estimate* could not be read from a price list and must be confirmed
before ordering — mostly the AISLER assembly fee, which their calculator only shows after a project
is uploaded.

## Why

The XIAO ESP32-S3 does far more than the key needs (two cores, Wi-Fi, camera support) and costs
battery life. The key needs BLE, two inputs, a battery measurement, a charger and USB-C. A custom
board with an **nRF52840** module gives:

- much lower power draw while connected, so the battery version lasts far longer between charges;
- no hand wiring: USB-C, the 3.5 mm jack and the battery connector sit on the board, and the
  housing has openings exactly where they are;
- real charge and USB-power signals from the charger chip instead of the two voltage dividers and
  the soldered charge-sense wire;
- the same product every time, assembled by AISLER in Germany.

It is **not cheaper per unit** than the XIAO build at 30 pieces. The gain is battery life, build
quality and no assembly work.

## The board

About **30 × 20 mm, 2 layers, 1.6 mm, ENIG**, all parts on the top side, all SMD.

| Function | Part | Price @30 | Source |
|---|---|---|---|
| BLE + MCU | Raytac **MDBT50Q-1MV2** (nRF52840, chip antenna, FCC/CE/TELEC certified), sold as Seeed 113990582 | 10.27 € | [DigiKey](https://www.digikey.de/de/products/detail/seeed-technology-co-ltd/113990582/9697025) |
| Charger with power path | TI **BQ24074RGTR** — runs the key from USB while it charges; CHG and PGOOD pins go straight to GPIOs | 1.41 € | [DigiKey](https://www.digikey.de/de/products/detail/texas-instruments/BQ24074RGTR/2047269) |
| USB-C | GCT **USB4105-GF-A** (USB 2.0, 16 pin) | 0.54 € | [DigiKey](https://www.digikey.de/de/products/detail/gct/USB4105-GF-A/11198441) |
| Paddle jack | Same Sky **SJ-3523-SMT-TR** (3.5 mm TRS, right angle) | 0.60 € | [DigiKey](https://www.digikey.de/de/products/detail/same-sky-formerly-cui-devices/SJ-3523-SMT-TR/281297) |
| Battery connector | JST **S2B-PH-SM4-TB** (PH 2.0, SMD) | 0.36 € | [DigiKey](https://www.digikey.de/de/products/detail/jst-sales-america-inc/S2B-PH-SM4-TB/926655) |
| USB ESD protection | ST **USBLC6-2SC6** | 0.28 € | [DigiKey](https://www.digikey.de/de/products/detail/stmicroelectronics/USBLC6-2SC6/1040559) |
| Reset / bootloader button | Panasonic **EVP-AKE31A** (side push) | 0.41 € | [DigiKey](https://www.digikey.de/de/products/detail/panasonic-industry/EVP-AKE31A/8568272) |
| 2 status LEDs | Würth 150060VS75000 (0603) | 0.26 € | [DigiKey](https://www.digikey.de/de/products/detail/w%C3%BCrth-elektronik/150060VS75000/4489906) |
| Resistors, capacitors, battery divider | 0603 passives, ~15 pieces | ~1.50 € *estimate* | — |
| **Parts per board** | | **≈ 15.60 €** | |

Design notes:

- **Why this module:** it is the module on Adafruit's Feather nRF52840, so its UF2 bootloader runs
  unchanged and updates work by dragging a file onto a USB drive. Its VDDH input takes the battery
  voltage directly, so no voltage regulator is needed. The certification covers the radio, as long
  as the antenna area stays clear of copper — the module goes at a board edge.
- **The module has pads underneath (LGA).** That is fine for AISLER's machines but rules out hand
  soldering. Their guide for modules: [setting up SoMs for assembly](https://community.aisler.net/t/setting-up-socs-for-assembly/3443).
  Suitability of this exact module should be confirmed with them before the first order.
- **Battery version and USB-only version are the same board**; the USB-only key simply has no
  cell plugged in.
- **Pins follow the Feather nRF52840 where possible** (LEDs, button), so the Feather board
  definition in the Arduino core can be used without a custom one.
- **Programming pads (SWD)** for the one-time bootloader flash: SWDIO, SWCLK, GND, VDD, RESET,
  as a Tag-Connect footprint so a cable clips on without a connector on the board.
- **Charge current** set to ~175 mA (0.5 C for 350 mAh), so a full charge takes about 2½ hours
  instead of the XIAO's 7.

## Firmware

Port `ble-key.ino` to the **Adafruit nRF52 Arduino core** (Bluefruit library):

- the Longpath contract stays: same service and characteristic UUIDs, same event format, same
  Battery Service;
- battery level from the divider, USB power from PGOOD, charging from CHG — the three readings
  the current firmware has to infer from analog voltages become plain pin reads;
- deep sleep becomes nRF52 **System OFF** with wake-up on the dit or dah pin (a few µA);
- `flash.sh` switches to the Feather nRF52840 board and uploads over USB.

The port can start **now, before any board exists**, on a Seeed XIAO nRF52840 — same nRF52840
chip, same USB bootloader, and it fits the housing in `enclosure/` unchanged.

## Housing

The current `enclosure/` script gets a third variant shaped around the new board: the board
screws or clips to the base, USB-C, the jack and the button sit flush with their openings, the cell
lies under or beside the board. Printed by an outside service in MJF PA12 (dyed black) — AISLER
makes no enclosures.

## Costs

### Prototype run: 3 boards

| Item | Cost | Notes |
|---|---|---|
| PCBs, 2L 1.6 mm ENIG Budget, 6 cm² × 3 | 13.75 € | 12.00 € job fee + 6 cm² × 0.097 €/cm² × 3 ([pricing](https://community.aisler.net/t/our-simple-pricing/102)) |
| Assembly fee | ~150 € *estimate* | paid mostly per unique part (~20 part numbers); AISLER no longer publishes the rates |
| Parts, bought by AISLER | ~65 € *estimate* | 3 × 15.60 € plus minimum quantities; leftovers come back with the boards |
| Stencil | ~5.60 € | 5.00 € + 6 cm² × 0.095 €/cm²; may already be in the assembly fee |
| 3 housings, MJF or SLA | ~20–30 € *estimate* | small orders pay minimum fees per part |
| 3 cells LP-552035 | 12.54 € | [Eckstein](https://eckstein-shop.de/LiPo-Battery-Lithium-Ion-Polymer-Battery-37V-350mAh-with-JST-PHR-2-Connector-LP552035-EN), 4.18 € each |
| Debug probe for the bootloader flash | ~13 € *estimate* | Raspberry Pi Debug Probe; once |
| Tag-Connect TC2030 cable | ~40 € *estimate* | once |
| XIAO nRF52840 for porting the firmware | ~10 € *estimate* | once |
| **Total** | **≈ 330–350 €** | |

### Production run: 30 keys

| Item | Total | Per key |
|---|---|---|
| PCBs, 6 cm² × 30 | 29.46 € | 0.98 € |
| Assembly fee | ~200 € *estimate* | ~6.70 € |
| Parts | ~470 € | ~15.60 € |
| Housings, MJF PA12 | ~90–180 € *estimate* | 3–6 € |
| Screws | ~10 € | 0.35 € |
| **Total without battery** | **≈ 800–890 €** | **≈ 27–30 €** |
| Cells, 30 × LP-552035 | 125.40 € | 4.18 € |
| **Total with battery** | **≈ 925–1,015 €** | **≈ 31–34 €** |

Cheaper with the same design: buying the module from Raytac's DigiKey marketplace listing
(MDBT50Q-P1MV2, about 6 € including shipping, 14 days, no returns, PCB-trace antenna) brings the
parts down to about 11 € per board and the total down by about 130 €.

Shipping from AISLER is free within Germany (untracked); UPS is extra. Lead times as of
September 2026: about **18 working days** for an assembled order (PCB plus parts plus assembly).

### Not included: selling the keys

Selling assembled keys in the EU makes you the manufacturer, which brings costs that are not in
the tables above and need checking before the first sale:

- **CE marking under the Radio Equipment Directive.** The certified module helps a lot, but the
  finished product still needs a declaration of conformity; a pre-scan at a test lab is the usual
  safeguard. This can cost more than the whole production run.
- **WEEE registration** (stiftung ear) for electronic devices sold in Germany.
- **Battery registration** (BattG / EU battery regulation) if keys ship with a cell — or sell the
  cell separately, or let buyers fit their own.

Kits the buyer assembles and the open-hardware files themselves are a different situation.

## Order of work

1. **Firmware port** on a XIAO nRF52840 — proves BLE, sleep and battery life before any money
   goes into boards.
2. **Schematic and layout in KiCad**, with MPN fields filled in so AISLER matches the parts on
   upload.
3. **Upload to AISLER** to get the real assembly price; confirm the module with their support.
4. **Prototype run of 3**, housing variant printed alongside. Test charging, range, sleep current.
5. Fixes, then **production run of 30**.
