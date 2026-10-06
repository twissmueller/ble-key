# Custom PCB plan — nRF52840 key, built by AISLER

**Status:** schematic, layout and case done (this folder, `../../enclosure/`); design uploaded to AISLER
and quoted on 1 October 2026; nothing ordered. Prices are **net (no VAT)** unless marked. Figures
marked *estimate* do not come from a price list or quote.

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

**48 × 27 mm, 2 layers, 1.6 mm, ENIG**, all parts on the top side, all SMD (see this folder).

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

Port the firmware to the **Adafruit nRF52 Arduino core** (Bluefruit library). Started on the XIAO
nRF52840 in [`../nrf52840.ino`](../nrf52840.ino), on Seeed's fork of that core; the board needs
its own pin table on top of it:

- the Longpath contract stays: same service and characteristic UUIDs, same event format, same
  Battery Service;
- battery level from the divider, USB power from PGOOD, charging from CHG — the three readings
  the current firmware has to infer from analog voltages become plain pin reads;
- deep sleep becomes nRF52 **System OFF** with wake-up on the dit or dah pin (a few µA);
- `flash.sh` gets a third target with the Feather nRF52840 board and uploads over USB.

The port runs **before any board exists**, on a Seeed XIAO nRF52840 — same nRF52840
chip, same USB bootloader, and it fits the housing in `enclosure/` unchanged.

## Housing

`../../enclosure/board_case.py` builds the case around the board, USB-only (52.4 × 31.6 × 12.4 mm) or with
the cell in the lid above the board (52.4 × 31.6 × 18.8 mm). Printed by an outside service in MJF
PA12 (dyed black) — AISLER makes no enclosures. See `../../enclosure/README.md`.

## Costs

### AISLER quote, 1 October 2026

From the uploaded design (project TBHYNBKB, revision 1), with every part assigned and prices
calculated. Net prices, **plus 19 % VAT**, valid 24 hours; dispatch about 18 working days after
ordering. Service "Amazing Assembly": 2 layers, 1.6 mm, ENIG, green, one-sided assembly, 36 parts
(24 different).

| Assembled boards | Net total | Per board |
|---|---|---|
| 1 | 327.18 € | 327.18 € |
| 3 | 406.56 € | 135.52 € |
| 10 | 712.19 € | 71.22 € |
| **30** | **1,423.21 €** | **47.44 €** |

### Where the money goes

The quote splits into three parts. Bare boards and parts come straight from AISLER's own price
lists; assembly is what is left of the total.

| Per board | 1 board | 10 boards | 30 boards |
|---|---|---|---|
| Bare PCB (ENIG) | 16.42 € *(set of 3)* | ~2.70 € *(set of 12)* | 1.68 € |
| Parts, as AISLER buys them | 132.28 € | 33.23 € | ~31.40 € *(between their 10 and 50 prices)* |
| Assembly | ~178 € | ~35.50 € | ~14.40 € |
| **Total** | **327.18 €** | **71.22 €** | **47.44 €** |

The cost drivers, in order:

1. **Parts at about twice their list price.** The parts add up to about 16 € per board at
   distributor list prices, but AISLER charges 33.23 € at 10 boards and 29.57 € at 50. Their parts
   price includes "assembly surplus and sourcing and handling costs" and minimum order quantities.
   Even at 1,000 boards it is still 23.81 €.
2. **The radio module.** It is the only part AISLER marks as a large price impact: 8.85 € each as
   Seeed 113990582. The listing also says "the factory is currently not accepting orders", so stock
   is finite.
3. **Assembly setup.** Roughly 180 € for a single board and about 430 € for 30, so it is mostly a
   fixed cost per order. AISLER does not publish the rates, but the cost is known to grow with the
   number of *different* parts (24 today), more than with the number of boards.
4. **The bare board is negligible:** 1.68 € per board at 30.

Compared with the earlier estimate (27–30 € per key including the case), assembled boards alone
cost about 47 € at 30. The parts surplus and the assembly setup were both underestimated.

### Ways to bring it down

| Change | Effect |
|---|---|
| **Order more at once** | Parts drop from 33.23 € (10) to 29.57 € (50) and 26.55 € (100) per board, and the assembly setup spreads further. |
| **Fewer different parts** (24 → about 17) | Cuts the per-part setup work: <br>– drop the reset button (the bootloader is reachable over USB, recovery over SWD), which also removes the tongue from the case; <br>– use the module's internal pull-ups for PGOOD and CHG (R6, R7); <br>– one 10 µF value for all bulk capacitors (C1–C3 at the charger too, within the BQ24074's ranges); <br>– 1 kΩ instead of 470 Ω for the paddle series resistors; <br>– 5.1 kΩ for ILIM as well (about 300 mA input limit, enough for 175 mA charging); <br>– two LEDs of the same colour. |
| **Supply the module yourself** | Raytac's own listing is about 6 € including shipping, against 8.85 € plus AISLER's surplus. Costs a one-off 15 € fee per supplied part number, so it pays off from about 10 boards. It also protects the run against the Seeed listing running dry. |
| **Ask for a personal quote** | AISLER's account management quotes larger or repeat runs individually. |

Each change in the "fewer different parts" row needs a schematic change and a new upload to see
its real effect; AISLER prices only the design it has.

### JLCPCB quote, 1 October 2026

Same design, uploaded to JLCPCB (`jlcpcb/`), 30 boards, ENIG, economic assembly on the
top side. Prices in USD, before shipping (DHL about 23 $) and EU import VAT:

| Item | 30 boards |
|---|---|
| Bare boards | 76.15 $ — of which about 51 $ come from the 0.25 mm vias, which make JLCPCB add via plugging and a 4-wire test; with 0.3 mm vias the boards cost 26 $ |
| Parts (22 of 24 types) | 140.35 $ |
| Extended-part fees | 30.90 $ |
| Setup, stencil, assembly, nitrogen reflow | 17.44 $ |
| **Total without module and switch** | **264.84 $ (8.83 $ per board)** |

Not in that total, because JLCPCB has no stock: the **module** (MDBT50Q-1MV2, listed at 18.94 $
each, so about 570 $ for 30 if pre-ordered there) and the **reset switch**. With the module bought
through JLCPCB the order comes to roughly **850–870 $**, about 29 $ per board; with modules bought
elsewhere at 9–10 € each and sent in, considerably less. Either way about half of AISLER's
1,423 € net.

To order there: pre-order or consign the module and switch, tick "Confirm Parts Placement" (JLCPCB's
model of the jack sits about 0.7 mm off the pads; their engineers correct it), and keep in mind
that shipping from China and customs add a few days and the import VAT.

### Seeed Fusion quote, 1 October 2026

Same design (`seeed/`), 30 boards, ENIG, 0.25 mm drill, 4/4 mil, 0.1 mm mask dam. USD,
free DHL express shipping to Germany, before EU import VAT and coupons:

| Item | 30 boards |
|---|---|
| Bare boards | 162.70 $ (the tight drill/trace/mask rules double the board price) |
| Parts, 17 of 24 lines matched | 207.41 $ |
| Assembly | 332.70 $ |
| Setup and consumables | 65.00 $ |
| **Subtotal** | **767.81 $** |

Not yet priced: the module (Seeed SKU 113990582) and six resistor values, which Seeed checks by
hand within a working day once the order is in the cart. With the module at about 9–10 $ the total
comes to roughly **1,050–1,100 $, about 35–37 $ per board.** Per-board prices fall to 18.77 $ (50)
and 13.28 $ (100) for the matched part of the quote.

### Comparison, 30 assembled boards

| Supplier | Total | Per board | Status |
|---|---|---|---|
| AISLER (Germany) | 1,423.21 € net | 47.44 € | complete quote, all parts in stock |
| Seeed Fusion (China) | ~1,050–1,100 $ | ~35–37 $ | module and 6 resistors priced on manual review |
| JLCPCB (China) | ~850–870 $ | ~29 $ | module and reset switch out of stock there |

### Everything else (unchanged estimates)

| Item | Cost |
|---|---|
| Cells, LP-552035 | 4.18 € each ([Eckstein](https://eckstein-shop.de/LiPo-Battery-Lithium-Ion-Polymer-Battery-37V-350mAh-with-JST-PHR-2-Connector-LP552035-EN)) |
| Cases, MJF PA12, from an EU print service | ~3–6 € per case *estimate* |
| Screws, 2 × M2 × 8 per case | ~0.20 € |
| Once: Raspberry Pi Debug Probe, Tag-Connect TC2030 cable, XIAO nRF52840 for the firmware port | ~65 € *estimate* |

**Per key at 30, with battery: about 47.44 + 4.18 + ~4.50 + 0.20 ≈ 56 € net.**

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
   goes into boards. Written ([`../nrf52840.ino`](../nrf52840.ino)); measurements still open.
2. ~~Schematic and layout in KiCad~~ — done, with MPN fields filled in.
3. ~~Upload to AISLER~~ — done, quote above. Still to do: confirm the module's bottom pads with
   their support, and decide on the cost reductions.
4. **Prototype run of 3**, housing variant printed alongside. Test charging, range, sleep current.
5. Fixes, then **production run of 30**.
