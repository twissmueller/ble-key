# ble-key on the XIAO ESP32-S3

Firmware and wiring for the [Seeed Studio XIAO ESP32-S3](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/).
The BLE contract, the build tools and the case are shared with the nRF52840 key and described in
the [main README](../README.md). The board-independent firmware lives in
[`../lib/BleKeyCore`](../lib/BleKeyCore/src/BleKeyCore.h); this sketch adds NimBLE, the pins,
the ADC and the deep sleep.

## Pins and wiring

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

## Battery (optional)

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

## How the power state is read

Off USB a plausible cell reading means *on cell*. On USB the charge LED, read through the
charge-sense wire on `D3`, is the only evidence: flashing → *charging*; dark for two windows
after having flashed → *charged*; solid for two windows without ever flashing → *no cell*.
Dark from the start says nothing (a key booted on USB, a cell that was already full, or a key
without the wire) and stays *unknown*. USB power itself is sensed on `D10`.

## Idle sleep

The battery key deep-sleeps after ten idle minutes and wakes on either paddle line through
ext1. Details, including the RTC pull-up handling that makes this work, are in
[BATTERY.md](BATTERY.md#idle-sleep).

## Build & flash

```sh
../flash.sh esp32s3           # from the repository root: ./flash.sh esp32s3
```

FQBN `esp32:esp32:XIAO_ESP32S3`, BLE through [NimBLE-Arduino](https://github.com/h2zero/NimBLE-Arduino).

### Bench builds

Two compile-time overrides make the idle sleep testable without waiting ten minutes
(run from the repository root):

```sh
# sleep after 20 s instead of 10 min
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 --library lib/BleKeyCore \
  --build-property "compiler.cpp.extra_flags=-DIDLE_SLEEP_MS=20000" esp32s3
# additionally wake by timer after 15 s, to test the wake/boot path without a key
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 --library lib/BleKeyCore \
  --build-property "compiler.cpp.extra_flags=-DIDLE_SLEEP_MS=20000 -DSLEEP_TEST_TIMER_S=15" esp32s3

# leave the battery code out of the image entirely (no ADC, no Battery Service, no sleep)
arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32S3 --library lib/BleKeyCore \
  --build-property "compiler.cpp.extra_flags=-DBATTERY_MOD=0" esp32s3
```

A sleeping key has no USB port (native USB dies with the chip), so a build that cannot wake
can only be re-flashed after a power cycle. Hold the key down while plugging USB back in —
a held paddle keeps the firmware awake indefinitely — and flash then. The serial monitor
misses everything printed before it attaches, which after a wake is the whole boot log;
the firmware therefore repeats the essentials once, 3 s after boot
(`[paddle] ready — woke on dit, advertising`).
