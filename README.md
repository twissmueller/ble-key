# ble-key

A Bluetooth Low Energy interface for a Morse **key**, built on a
[Seeed Studio XIAO ESP32-S3](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/).

Plug in your own straight key or iambic paddle. The board reads the contacts (dit / dah),
debounces them, and streams **timed keying edges** over BLE as notifications to the
[Longpath](https://wissmueller.net/en/longpath.html) Morse-training app, which produces the
audio/sidetone and does the training. The device itself makes no sound — it's purely the
key interface. The onboard LED gives instant, BLE-independent visual feedback while keying.

The BLE contract below is simple and app-agnostic — anything that speaks GATT can consume it.

## Getting a key

The BLE key is open hardware — get one in whichever way suits you:

1. **Build it yourself** — source the parts ([Hardware](#hardware)) and flash the firmware
   ([Build & flash](#build--flash)); everything you need is in this repository.
2. **Order a parts kit** — I'll send you the board and connectors, you assemble and flash.
3. **Order a ready-built key** — assembled, flashed, and tested.

For a parts kit or a ready-built key, email
[hello@wissmueller.net](mailto:hello@wissmueller.net) with your shipping address. The Longpath
app offers the same three options (with pre-filled order emails) in its BLE-key dialog — keep
that dialog and this section in sync.

## Hardware

| Signal      | XIAO pin | GPIO   | Notes                                        |
|-------------|----------|--------|----------------------------------------------|
| Dit         | `D1`     | GPIO2  | Tip, `INPUT_PULLUP`, pressed = LOW           |
| Dah         | `D2`     | GPIO3  | Ring, `INPUT_PULLUP`, pressed = LOW          |
| LED         | `GPIO21` | —      | `LED_BUILTIN`, active-low                    |
| Battery     | `A0`     | GPIO1  | Divider tap, ADC — battery mod only          |
| USB power   | `D10`    | GPIO9  | Divider tap from `5V` (VBUS), ADC — battery mod only |
| Charge LED  | `D3`     | GPIO4  | Tap on the charge-LED net, `INPUT_PULLUP`, LOW = LED on — charge-sense wire only |

Wire each key/paddle contact between its input pin and ground; the internal pull-ups mean
no external resistors are needed. A straight key uses the dit line only; an iambic paddle
uses both. The tip/ring assignment matches a standard 3.5 mm TRS paddle plug:

![Wiring: XIAO ESP32-S3 to a 3.5 mm TRS jack — D1 to tip (dit), D2 to ring (dah), GND to sleeve; optional LiPo on the BAT pads with a 2 × 220 kΩ divider into A0, a second 2 × 220 kΩ divider from 5V into D10 to sense USB power, and the optional charge-sense wire from the charge LED's cathode pad through 100 kΩ into D3](wiring.svg)

### Battery (optional)

The key runs from USB-C as it is. For a cordless key, solder a single-cell LiPo to the
`BAT` pads on the underside of the XIAO — it has the charger on board — and add a
**2 × 220 kΩ voltage divider** from `BAT+` to `GND`, tapped into `A0`, so the firmware can
measure the cell and report its level to the app. Add a **second 2 × 220 kΩ divider from the
`5V` pin to `GND`, tapped into `D10`**: the 5V pin is USB VBUS, so this tells the firmware
when the key is on USB power — from a host, a charger or a power bank alike. That matters
because on USB the `BAT+` pad carries the charger's output, not the cell, and would read as a
meaningless "62 %" even with no cell fitted. Cell choice, polarity, soldering order and
runtime expectations are in [BATTERY.md](BATTERY.md).

To see *charging* in the app as well, add the **charge-sense wire**: one wire (through a
100 kΩ series resistor) from the net of the red charge LED into `D3`. The charge IC drives
that LED and nothing else — flashing while a cell charges, off when it is full, solid for
~30 s after plug-in without a cell — and reading it is the only way the firmware can tell
those apart. With the wire the key reports charging / charged / no cell over BLE and keeps
publishing the live level while charging; without it, USB shows the plain connected chip
as before. Details in [BATTERY.md](BATTERY.md#the-charge-sense-wire); the last strip of the wiring diagram shows it.

One build fits every key: at boot the firmware checks whether the mod is actually fitted
(VBUS on `D10`, or a plausible cell voltage on `A0`, steady over a few samples) and switches
the battery features on or off accordingly. A battery key reports its level over BLE and
**deep-sleeps after ten idle minutes** — the next dit or dah wakes it (that press is consumed
by the boot; keying resumes with the following one, and the Longpath app reconnects on its
own). A stock USB key exposes no Battery Service and never sleeps. To leave the battery code
out of the image altogether, build with `-DBATTERY_MOD=0` (see [Bench builds](#bench-builds)).

## BLE contract

The device advertises as **`Paddle`** with one service and one notify characteristic.
On every debounced paddle edge it sends a **5-byte little-endian** packet:

```
byte 0     : event   (uint8)
bytes 1..4 : millis  (uint32, little-endian) — device millis() at the edge
```

Events:

| Value | Event      |
|-------|------------|
| `0`   | `DIT_DOWN` |
| `1`   | `DIT_UP`   |
| `2`   | `DAH_DOWN` |
| `3`   | `DAH_UP`   |

The client reconstructs element and gap timing from consecutive timestamps. The board
re-advertises automatically after a central disconnects, so a client can reconnect
without power-cycling.

### Battery level

With the battery mod fitted the key additionally exposes the SIG-standard
**Battery Service `0x180F`** with the **Battery Level characteristic `0x2A19`** (`uint8`,
0–100 %, read + notify). The level is re-measured every 10 s while the key is idle and
notified only when it changes; a client reads it once after connecting and then subscribes.
The service is *not* advertised — clients find it during service discovery — and it sits
next to the Longpath service without touching the packet format or UUIDs above. Clients
that do not know it, and older app builds, simply ignore it; a key without the mod exposes
no Battery Service at all, and the Longpath app then shows no level.

The percentage comes from an open-circuit LiPo discharge curve (3.30 V → 0 %, 4.20 V →
100 %, flat in the middle), not a linear map. On USB power (sensed on `D10`, see above) the
divider would only see the charger, so the key publishes **`0xFF` = level unknown** instead
of a percentage — outside the SIG's 0–100 on purpose; Longpath shows no level for it, other
clients should treat it the same way — and the idle sleep is off. Below 3.5 V the onboard
LED double-blinks once at boot, independently of BLE.

### Battery power state

Next to the level the same service carries the SIG-standard **Battery Power State
characteristic `0x2A1A`** (`uint8`, read + notify): bits 0–1 *present*, bits 2–3
*discharging*, bits 4–5 *charging* (each 2 = no, 3 = yes; 0 = unknown), bits 6–7 unused.
The key publishes five values:

| Meaning   | Value  | present | discharging | charging |
|-----------|--------|---------|-------------|----------|
| unknown   | `0x00` | ?       | ?           | ?        |
| on cell   | `0x2F` | yes     | yes         | no       |
| charging  | `0x3B` | yes     | no          | yes      |
| charged   | `0x2B` | yes     | no          | no       |
| no cell   | `0x02` | no      | —           | —        |

Off USB a plausible cell reading means *on cell*. On USB the charge LED, read through the
charge-sense wire on `D3`, is the only evidence: flashing → *charging*; dark for two windows
after having flashed → *charged*; solid for two windows without ever flashing → *no cell*.
Dark from the start says nothing (a key booted on USB, a cell that was already full, or a key
without the wire) and stays *unknown*. While *charging* or *charged* the level in `0x2A19`
is the live reading of the cell under charge instead of `0xFF` — a few points high and
climbing; the Longpath app shows it next to "charging" and forces 100 % once the key reports
*charged*. In every other state on USB the level stays `0xFF`. Notified only on change; a
client reads it once after connecting and subscribes.

### Idle sleep

A battery key enters deep sleep after ten minutes without a paddle edge.
It disconnects the central first, so a client sees a clean disconnect rather than a
supervision timeout, and wakes on either paddle line going LOW. Waking is a reset: the key
advertises again after about half a second, and `millis()` restarts at 0 — clients must
treat a reconnect as a timing resync (Longpath does). Details, including the RTC pull-up
handling that makes this work, are in [BATTERY.md](BATTERY.md#idle-sleep).

### UUIDs

The service and characteristic UUIDs in `ble-key.ino` are the **fixed Longpath contract**
— the app looks for exactly this service, so leave them unchanged if your key should work
with Longpath (whether self-built, from a kit, or bought ready-made). Only when building
for a *different* client should you mint your own pair (`uuidgen`, run twice) and replace
`SVC_UUID` / `CHR_UUID` near the top of the sketch.

## Build & flash

Requires [`arduino-cli`](https://arduino.github.io/arduino-cli/) with the ESP32 core and
the NimBLE library:

```sh
arduino-cli core install esp32:esp32
arduino-cli lib install "NimBLE-Arduino"
```

Then:

```sh
./flash.sh            # auto-detects the serial port
./flash.sh /dev/cu.usbmodemXXXX   # or pass one explicitly

./monitor.sh          # serial monitor at 115200 baud
```

Both scripts target the XIAO ESP32-S3 (`FQBN esp32:esp32:XIAO_ESP32S3`).

### Bench builds

Two compile-time overrides make the idle sleep testable without waiting ten minutes:

```sh
# sleep after 20 s instead of 10 min
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 \
  --build-property "compiler.cpp.extra_flags=-DIDLE_SLEEP_MS=20000" .
# additionally wake by timer after 15 s, to test the wake/boot path without a key
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 \
  --build-property "compiler.cpp.extra_flags=-DIDLE_SLEEP_MS=20000 -DSLEEP_TEST_TIMER_S=15" .

# leave the battery code out of the image entirely (no ADC, no Battery Service, no sleep)
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 \
  --build-property "compiler.cpp.extra_flags=-DBATTERY_MOD=0" .
```

A sleeping key has no USB port (native USB dies with the chip), so a build that cannot wake
can only be re-flashed after a power cycle. Hold the key down while plugging USB back in —
a held paddle keeps the firmware awake indefinitely — and flash then. The serial monitor
misses everything printed before it attaches, which after a wake is the whole boot log;
the firmware therefore repeats the essentials once, 3 s after boot
(`[paddle] ready — woke on dit, advertising`).

## License

[MIT](LICENSE) © 2026 Tobias Wissmüller
