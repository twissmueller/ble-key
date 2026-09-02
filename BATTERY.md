# Battery mod — running the key on a LiPo

**Status:** hardware path is verified against the Seeed wiki and low-risk. The firmware
measures the cell through a 2 × 220 kΩ divider, reports the level to the app over the
standard BLE Battery Service (see [Battery level](#battery-level-over-ble)) and deep-sleeps
after ten idle minutes, waking on the next key press (see [Idle sleep](#idle-sleep)). What
is left is measuring on real hardware (see [TODO](#todo--firmware-work)). The stock,
USB-powered key is unaffected — this is an optional mod for people who want a cordless key.

The [XIAO ESP32-S3](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/) has a LiPo
charger on board, so going cordless needs no extra charging module: solder a cell to two
pads and the same USB-C port that flashes the board also charges it.

## What the board gives you

- Two solder pads on the **underside**, labelled `BAT`, for a single-cell 3.7 V LiPo.
- An **on-board charge IC**. Plug in USB-C and the cell charges while the board keeps
  running and keying — no need to disconnect anything.
- A red charge LED: on when USB is connected *without* a battery (it gives up after ~30 s),
  flashing while charging, off when the cell is full.
- **14 µA in deep sleep** (per Seeed's specification table), which is what makes a
  battery-powered key practical at all.

Three constraints that shape every decision below:

- **The charge current is only 50 mA** (3.8 mA trickle) on the plain XIAO ESP32-S3. Note
  that the *Sense* variant charges at 100 mA — do not carry that number over. 50 mA is
  fixed in hardware and cannot be raised in firmware, so **capacity costs you charge
  time**: a 500 mAh cell needs roughly 10 hours from empty. That is fine overnight and
  painful otherwise.
- The charger has **no NTC / temperature input**. The cell's own protection circuit is the
  only safety net, which is why the cell choice below is not optional.
- Seeed states plainly that there is **no GPIO for battery voltage**: *"we cannot get the
  battery voltage at the software level by reading the analog value of one of the GPIOs."*
  The state-of-charge display therefore needs an external divider — two resistors, see
  [The voltage divider](#the-voltage-divider).

## Choosing a cell

A single-cell 3.7 V LiPo pouch with an **integrated protection circuit (PCM)** —
over-charge, over-discharge, over-current and short-circuit protection built into the tab
end. Cells sold with a JST-PH connector normally have one; bare cells often do not.

**400–500 mAh is the sweet spot here**, and the 50 mA charge current is the reason: a
larger pack does not buy runtime you need (the key sleeps at 14 µA between sessions) but
it does stretch charging past a night. Physical size is rarely the constraint — even a
500 mAh pouch at ~35 × 30 × 5 mm disappears into the base of a key, next to a board that
is only 21 × 17.5 mm.

## Shopping list (German shops)

Prices are VAT-inclusive and were checked in August 2026 — verify before ordering.

| # | Item | Where | Price |
|---|------|-------|-------|
| 1 | **LiPo 3.7 V / 500 mAh, JST-PH 2.0, protected** — PKCell LP-503035, ca. 35.5 × 30.0 × 5.05 mm, ~9 cm lead, integrated protection against over-charge, deep discharge and short circuit | [Eckstein LP503035](https://eckstein-shop.de/LiPo-Battery-Lithium-Ion-Polymer-Battery-37V-500mAh-with-JST-PHR-2-Connector-LP503035-EN) · [BerryBase Art. 70398](https://www.berrybase.de/lp-503035-lithium-polymer-lipo-akku-3-7v-500mah-mit-2-pin-jst-stecker) | 5.19 € (Eckstein) |
| 2 | **JST-PH 2.0 mating pigtail** for the `BAT` pads — see the gender note below | [Eckstein 20-pair kit](https://eckstein-shop.de/2Pin-JST-PH-20-Kable-Kit-20-Paare-EN) · [BerryBase extension cable 50 cm](https://www.berrybase.de/en/extension-cable-2-pin-jst-ph-2.0mm-male-female-awg24-50cm) | 5.95 € / ~1 € |
| 3 | **2 × 220 kΩ resistor** (metal film, 0207) for the battery-level divider | [Reichelt 220 kΩ 0207](https://www.reichelt.de/de/de/shop/produkt/widerstand_metallschicht_220_kohm_0207_0_6_w_0_1_-12876) | ~0.10 € each |

**Equally good: the 350 mAh LP-552035** — [Eckstein, 4.97 €](https://eckstein-shop.de/LiPo-Battery-Lithium-Ion-Polymer-Battery-37V-350mAh-with-JST-PHR-2-Connector-LP552035-EN)
or [BerryBase](https://www.berrybase.de/en/lp-552035-lithium-polymer-lipo-akku-3-7v-350mah-mit-2-pin-jst-stecker).
Same connector and chemistry, and at ca. 35 × 20 × 5.5 mm it is a **third narrower** than
the 500 mAh cell, which sits better beside a 17.5 mm wide board. It charges in ~7 h
instead of ~10 h and gives roughly 6–8 h of active keying instead of 8–12 h. Pick by
whether charge time or session length annoys you more; standby life is identical, because
that is set by deep sleep, not capacity. [EXP-Tech](https://exp-tech.de/en/collections/lipo-batteries)
carries the DTP range with the same JST-PH connector. The board itself, if you need
another: [Eckstein, 10.95 €](https://eckstein-shop.de/Seeed-Studio-XIAO-ESP32S3-Dual-Core-24GHz-Wi-Fi-BLE50-Battery-Charge-Supported-EN).

**Check the protection circuit before you buy either.** BerryBase documents integrated
protection for these PKCell packs (over-charge, deep discharge, short circuit); Eckstein's
listings do not state it. On a protected cell you can see the small PCB under the tape at
the tab end. If you cannot confirm it, buy the BerryBase variant.

**Cheapest route: the 0.99 € add-on.** Eckstein's battery pages offer a *JST PH2.0-2P auf
XH2.5-2P Strom-Adapterkabel, 50 mm* as an accessory. Add one to the battery order, cut the
**XH2.5 end** off, and the remaining PH2.0 plug with two open wires is exactly the pigtail
this mod needs — one order, no extra shipping. Two conditions: take the
**"Vorwärtsanschluss"** variant, and expect only ~4 cm of usable wire after the cut, which
is enough for a cell sitting directly under the board but leaves no slack for routing
through a case.

**Connector gender.** LiPo cells ship with the *female* housing, so the exposed pins can
never short against something. The board side therefore needs the **male** half. Before
cutting anything, plug the pigtail into the battery once to confirm it mates. Alternatives
to the add-on cable: the Eckstein kit contains both genders (20 pairs — a lifetime supply),
and the BerryBase male-to-female extension cable can be cut in half, the male end becoming
the board pigtail.

**Polarity is not implied by wire colour.** The same vendor sells the adapter cable in a
"Vorwärtsanschluss" and a "Rückwärtsanschluss" version — identical-looking cables with
*inverted* polarity, and their own listing says to check before use. Ring every pigtail out
with a meter from connector pin to wire end before soldering, no matter which one you
bought.

## Wiring it up

Solder the pigtail to the pads and mate it with the battery's connector, rather than
soldering the cell on directly — you can then swap or remove the cell without reworking
the board.

### Polarity

Seeed documents the orientation unambiguously: **the negative terminal is the pad closest
to the USB-C port, the positive terminal is the pad further away from it.** The silkscreen
prints the sign to the left of each pad, with `BAT` beneath the pair:

```
  −  ▢     pad nearer the USB-C port  = minus (GND)
  +  ▢     pad further from the port  = plus
     BAT
```

**Confirm with a meter before soldering anyway.** Reversed polarity destroys the board
instantly, and silkscreen markings sometimes sit ambiguously between two pads. The check
takes ten seconds: multimeter on continuity, one probe on the pad nearer the USB-C jack,
the other on a known ground — a `GND` pin on the header, or the metal shell of the USB-C
jack itself. It beeps → that pad is minus, and the other is plus.

### Soldering

- Tin the pads first, then lay the tinned wire on and reflow. Do not try to feed solder
  into the joint while holding the wire in place.
- Keep the cell **unplugged** the whole time. Solder the pigtail to the board, verify
  polarity at the connector with a meter, and only then plug in the cell.
- If you do solder a cell directly: strip and attach **one wire at a time**, so the two
  bare ends can never touch. A shorted LiPo is not a minor mistake.
- Add strain relief (a dab of hot glue, or a cable tie to the case). Without it the pads
  eventually tear off the PCB.

### The voltage divider

The board has no battery-sense pin, so the firmware measures the cell through an external
divider: **two 220 kΩ resistors in series from `BAT+` to `GND`, with the midpoint wired to
`A0`** (GPIO1 — free, the key uses only `D1`/`D2` and the LED).

```
  BAT+ ──┤ 220 kΩ ├──┬──┤ 220 kΩ ├── GND
                     │
                    A0
```

- The divider halves the cell voltage: a full cell at 4.2 V shows up as 2.1 V at `A0`,
  comfortably inside the ADC's range at 11 dB attenuation (about 0–3.1 V). The firmware
  multiplies the calibrated reading (`analogReadMilliVolts`) by two.
- 440 kΩ across the cell draws **~9.5 µA** continuously — the same order as the whole
  deep-sleep budget of 14 µA, so it roughly halves standby life versus the datasheet
  figure: still months, not weeks. Two resistors keep the mod dead simple; switching the top
  of the divider with a GPIO instead of wiring it to `BAT+` directly is the refinement if
  those microamps ever matter (see the TODO list).
- Land the top resistor on the `BAT+` pad on the underside (the same pad as the pigtail's
  plus wire), the bottom one on any `GND` — the header pin is the easiest. Tap `A0` from the
  junction. Keep the leads short; the node is high-impedance and picks up noise, which is why
  the firmware averages 16 samples per reading.
- **Do not fit the divider without setting `BATTERY_MOD` accordingly.** With `BATTERY_MOD 1`
  and no divider, `A0` floats and the app shows nonsense; with `BATTERY_MOD 0` the resistors
  are harmless but the level is never read. The default in `ble-key.ino` is `1`.

## Charging and power behaviour

- USB-C connected: the board runs from USB and charges the cell simultaneously. Flashing
  with a battery attached is fine.
- USB-C disconnected: the board runs from the cell through the on-board regulator, down to
  roughly 3.4 V, below which the cell's protection circuit eventually cuts out.
- Charging is slow by design (50 mA). Plan on charging overnight; there is no fast-charge
  option on this board.

## Runtime expectations

Estimates apart from the deep-sleep figure, which is Seeed's specification. Measure before
trusting them:

| State                                         | Draw        | 500 mAh cell |
|-----------------------------------------------|-------------|--------------|
| Connected + advertising, CPU at 240 MHz       | 40–60 mA*   | ~8–12 h      |
| Same, CPU at 80 MHz, long connection interval | 20–30 mA*   | ~16–24 h     |
| Deep sleep, waiting for the operator          | 14 µA + ~10 µA divider* | months |
| Charging from empty                           | 50 mA in    | ~10 h        |

\* estimated, not measured.

The firmware deep-sleeps after ten idle minutes, so the hours in the table are *keying
hours*, not wall-clock hours: a key that is used an hour a day lasts a week or two on a
charge, and a key left in a drawer keeps its charge for months. Idle sleep is by far the
biggest power lever here — a Morse key is idle almost all of the time, and 14 µA versus
50 mA is a factor of several thousand.

## Battery level over BLE

Implemented in `ble-key.ino` behind `#define BATTERY_MOD 1`:

- The cell is measured through the divider on `A0` every **10 s while the key is idle**
  (never between two paddle edges — the 16-sample ADC burst must not disturb keying), and
  once at boot.
- The voltage is mapped to a percentage through an **open-circuit LiPo discharge curve**
  (3.30 V → 0 %, 3.70 V → 20 %, 3.85 V → 50 %, 4.00 V → 80 %, 4.20 V → 100 %, linearly
  interpolated). A plain linear map would sit at "60 %" for hours and then collapse,
  because the cell spends most of its life between 3.6 V and 3.9 V. Under load the cell
  sags a little, so the reading is slightly pessimistic while keying — fine for a key.
- The level is published through the SIG-standard **Battery Service `0x180F` / Battery
  Level `0x2A19`** (`uint8` percent, read + notify), notified only when the percentage
  changes. The Longpath contract — the `6e3a…` service, the packet format — is untouched;
  older app builds ignore the extra service.
- Readings outside 2.5–4.6 V are treated as implausible (no cell, no divider) and dropped;
  the last published value stands.
- On USB the divider sees the **charger's output, not the cell**: BAT+ sits at ~3.9–4.2 V
  whether a cell is fitted or not (a bare board on USB reads "62 %"). So USB power is sensed
  separately: a second **2 × 220 kΩ divider from the 5V pin (VBUS) into `D10`** (GPIO9,
  ADC1) reads ~2.5 V whenever anything is plugged in — host, charger or power bank — and
  0 V on the cell. Above 4 V on VBUS the firmware publishes **`0xFF` = level unknown**
  instead of a percentage, and the idle sleep is off (nothing to save, and a sleep would
  cost the first press and drop the serial port). Unplugging restarts the idle clock. A USB
  host on the serial port (`Serial.isPlugged()`) counts as USB power too, as the fallback
  for a key without the VBUS divider.
- Below **3.5 V** the onboard LED double-blinks once at boot — the BLE-independent
  low-battery hint in the spirit of the keying LED.

The Longpath app reads the level once after connecting and then subscribes: the connection
chip shows "BLE key connected · 78 %", and Settings › Device adds a battery line that turns
into a charge hint at 15 % and below. A key without the Battery Service — or one on USB,
publishing `0xFF` — shows the plain connected chip and no level.

## Idle sleep

Implemented in `ble-key.ino` behind `BATTERY_MOD 1` (a stock USB key never sleeps — there
is nothing to save, and sleeping costs the first press):

- **When.** After `IDLE_SLEEP_MS` (10 minutes) without a paddle edge, counted from boot or
  the last edge, connected or not. Never while a paddle is held: a held line is LOW and
  would wake the board again immediately, and a key resting on its contact should keep the
  LED on as the visible hint that something is wrong.
- **How.** The firmware first disconnects the central deliberately (so the app sees the
  drop at once instead of after the supervision timeout), stops advertising, re-arms the
  paddle pull-ups as **RTC pull-ups** (`rtc_gpio_pullup_en`) — the plain `INPUT_PULLUP` is
  a digital-domain pull-up and dies in deep sleep, which is the classic way this feature
  fails: both lines float low and the board wakes in a loop. `LED_BUILTIN` is parked HIGH
  and held (`gpio_hold_en`) so the active-low LED cannot glow through the sleep. Then
  `esp_sleep_enable_ext1_wakeup_io()` with `ESP_EXT1_WAKEUP_ANY_LOW` on `GPIO2 | GPIO3`
  (both RTC IOs on the S3) and `esp_deep_sleep_start()`.
- **The RTC-peripheral power domain must stay on AUTO.** The IDF docs suggest keeping
  `ESP_PD_DOMAIN_RTC_PERIPH` powered (`esp_sleep_pd_config(…, ESP_PD_OPTION_ON)`) when
  internal pull-ups are used with ext1. On the XIAO ESP32-S3 with IDF 5.5 that silently
  breaks the wake: measured on the bench, ext1 `ANY_LOW` never fires with the domain forced
  on — not with two pins, not with one, not with a held key — while ext1 `ANY_HIGH` and
  ext0 work in the same configuration. With the domain on AUTO the IDF latches the pad
  configuration (pull-up included) through the sleep via the HOLD feature, and ext1
  `ANY_LOW` wakes on either paddle. Bonus: the RTC peripherals are powered down, so sleep
  current is lower than with the documented approach.
- **Wake.** Any dit or dah press. Deep sleep is a reset: `setup()` runs again, hands the
  wake pins back from the RTC domain (`rtc_gpio_deinit`, or `pinMode` is silently
  ineffective), releases the LED hold, skips the 400 ms serial grace period a cold boot
  affords, and is advertising again after roughly half a second. Expect the **waking press
  to be lost** — it is consumed by the boot, and the app has not reconnected yet. The next
  press keys normally. That is why the timeout is ten minutes: it should only ever trigger
  between sessions, never mid-word.
- **`millis()` across a sleep cycle.** Restarts at 0 — deep sleep is a reset. This is
  harmless: the sleep always coincides with a BLE disconnect, and the Longpath keyers
  detect pauses by wall-clock timeout, not by device timestamps, so the only place a
  consecutive-timestamp comparison spans the wake (the character-gap check) has already
  been flushed by the pause. Verified by reading the keyer code, not on hardware.
- **App side.** The Longpath app re-scans automatically whenever an established link ends
  (`PaddleConnection.keepConnected()`), so the wake needs no "Connect" tap: the chip shows
  "Scanning…" while the key sleeps and flips back to connected within a second or two of
  the wake press. A scan that fails outright (Bluetooth off) backs off up to 15 s between
  attempts so it cannot trip Android's scan throttling.
- **Divider during sleep.** The 2 × 220 kΩ divider stays connected and draws ~9.5 µA
  through the sleep, on top of the ESP32-S3's 14 µA — roughly halved standby life versus
  the datasheet figure, still months. Switching the divider with a GPIO is the obvious
  next refinement if that ever matters.

## TODO — firmware work

Still open in `ble-key.ino`:

- [x] **Sleep when idle, wake on the key** — done, see [Idle sleep](#idle-sleep).
- [x] **RTC pull-ups for the sleep path** — done, part of the sleep entry.
- [x] **`millis()` across a sleep cycle** — restarts at 0; harmless, see above. The app
      treats every reconnect as a hard resync anyway.
- [x] **Verify the sleep path on hardware** — done on a XIAO ESP32-S3 with a TRS-wired
      key (no battery, no divider yet): the board stays asleep indefinitely (no wake loop),
      a held paddle keeps it awake, dit and dah each wake it (wake pin confirmed from the
      ext1 status register), and a wake cycle repeats reliably. USB re-enumerates on wake
      within about a second. Found and fixed on the way: the RTC-peripheral domain must
      *not* be forced on (see [Idle sleep](#idle-sleep)).
- [ ] **Measure the sleep current** with the divider and cell fitted, and the
      wake-to-first-notification time with the app; replace the estimates above.
- [x] **Battery level over BLE** via the SIG-standard Battery Service `0x180F` — done, see
      [above](#battery-level-over-ble).
- [x] **Measuring the cell voltage** through the 2 × 220 kΩ divider on `A0` — done. The
      divider's ~9.5 µA standby draw is accepted for now; switching it with a GPIO belongs
      to the sleep work below.
- [x] **Low-battery indication** independent of BLE — the boot double-blink below 3.5 V.
      Once the key sleeps, this should also run on every wake.
- [ ] **Calibrate the curve against a real cell.** The discharge table is a textbook LiPo
      curve; measure the PKCell packs from the shopping list with a meter at a few points
      and adjust the table if the percentages feel off.
- [ ] **Lower the connected-state draw**: CPU at 80 MHz, and a longer BLE connection
      interval. Keying edges are event-driven, not periodic, but the interval still bounds
      the latency of the *first* edge after an idle stretch — so this trades against feel
      and needs testing with a real operator, not just a meter.
- [ ] **Measure, then replace the estimates** in the runtime table with real numbers from a
      bench supply or an inline current meter.
- [ ] **Switch the divider with a GPIO** if the ~10 µA it draws through deep sleep turns
      out to matter.

## Open questions

- Whether BLE + light sleep (keeping the connection alive at much lower current) would be
  worth the complexity compared to the deep sleep + reconnect that is implemented now. Deep
  sleep is simpler, and the app-side reconnect makes the wake invisible apart from the lost
  first press.
- Whether ten minutes is the right idle timeout. Shorter saves little (the connected draw
  is the same whether idle or keying, but ten minutes of it is under 1 % of a cell) and
  risks a sleep inside a slow session; longer only costs battery when the key is forgotten
  switched on.

## Safety

Lithium cells deserve the boring precautions: use a protected cell, never charge
unattended, do not charge a cell that is swollen or has been crushed, and do not seal an
unprotected cell inside a printed case. If the pack gets warm while charging, unplug it and
retire the cell.
