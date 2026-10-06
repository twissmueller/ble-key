# ble-key

A Bluetooth Low Energy interface for a Morse **key**, built on a Seeed Studio XIAO board —
either the [XIAO ESP32-S3](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/) or the
[XIAO nRF52840](https://wiki.seeedstudio.com/XIAO_BLE/).

Plug in your own straight key or iambic paddle. The board reads the contacts (dit / dah),
debounces them, and streams **timed keying edges** over BLE as notifications to the
[Longpath](https://wissmueller.net/en/longpath.html) Morse-training app, which produces the
audio/sidetone and does the training. The device itself makes no sound — it's purely the
key interface. The onboard LED gives instant, BLE-independent visual feedback while keying.

The BLE contract below is simple and app-agnostic — anything that speaks GATT can consume it.
Both boards implement it identically; the app cannot tell them apart.

## Repository layout

| Path | What |
|------|------|
| [`esp32s3/`](esp32s3/) | XIAO ESP32-S3: firmware, pins and wiring, the battery mod ([BATTERY.md](esp32s3/BATTERY.md)) |
| [`nrf52840/`](nrf52840/) | XIAO nRF52840: firmware, pins, battery |
| [`lib/BleKeyCore/`](lib/BleKeyCore/src/BleKeyCore.h) | Shared firmware: the BLE contract, debounce, LiPo curve, power states |
| [`enclosure/`](enclosure/) | Printable cases — the XIAO case fits both boards |
| `flash.sh`, `monitor.sh` | Build, flash and watch either board |

## Which board?

| | XIAO ESP32-S3 | XIAO nRF52840 |
|---|---|---|
| Keying, LED, BLE contract | ✓ | ✓ |
| Wiring of the paddle jack | `D1` tip, `D2` ring, `GND` sleeve | the same |
| Battery level | LiPo **plus two dividers** soldered on | LiPo only — divider is on the board |
| Charging / charged | extra charge-sense wire | read from the charger on the board |
| Idle sleep | deep sleep, ~14 µA | System OFF, a few µA |
| Current while connected | tens of mA | a few mA (typical figures, not measured here) |

For a battery key the nRF52840 is the better choice: no extra parts and much longer runtime.
The ESP32-S3 key stays supported.

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

With a battery the key additionally exposes the SIG-standard
**Battery Service `0x180F`** with the **Battery Level characteristic `0x2A19`** (`uint8`,
0–100 %, read + notify). The level is re-measured every 10 s while the key is idle and
notified only when it changes; a client reads it once after connecting and then subscribes.
The service is *not* advertised — clients find it during service discovery — and it sits
next to the Longpath service without touching the packet format or UUIDs above. Clients
that do not know it, and older app builds, simply ignore it. Whether a key without a cell
exposes the service at all depends on the board (see its README); either way the Longpath
app then shows no level.

The percentage comes from an open-circuit LiPo discharge curve (3.30 V → 0 %, 4.20 V →
100 %, flat in the middle), not a linear map. On USB power the
measurement would only see the charger, so the key publishes **`0xFF` = level unknown** instead
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

Off USB a plausible cell reading means *on cell*. On USB the charger's status line is the
only evidence; how each board reads it is in its README. Anything the key cannot vouch for
stays *unknown*. While *charging* or *charged* the level in `0x2A19`
is the live reading of the cell under charge instead of `0xFF` — a few points high and
climbing; the Longpath app shows it next to "charging" and forces 100 % once the key reports
*charged*. In every other state on USB the level stays `0xFF`. Notified only on change; a
client reads it once after connecting and subscribes.

### Idle sleep

A battery key enters deep sleep after ten minutes without a paddle edge.
It disconnects the central first, so a client sees a clean disconnect rather than a
supervision timeout, and wakes on either paddle line going LOW. Waking is a reset: the key
advertises again after about half a second, and `millis()` restarts at 0 — clients must
treat a reconnect as a timing resync (Longpath does). A key on USB never sleeps.

### UUIDs

The service and characteristic UUIDs in [`BleKeyCore.h`](lib/BleKeyCore/src/BleKeyCore.h) are the **fixed Longpath contract**
— the app looks for exactly this service, so leave them unchanged if your key should work
with Longpath (whether self-built, from a kit, or bought ready-made). Only when building
for a *different* client should you mint your own pair (`uuidgen`, run twice) and replace
`SVC_UUID` / `CHR_UUID` there — both boards pick them up.

## Build & flash

Requires [`arduino-cli`](https://arduino.github.io/arduino-cli/) and the core for your board:

```sh
# XIAO ESP32-S3
arduino-cli core install esp32:esp32
arduino-cli lib install "NimBLE-Arduino"

# XIAO nRF52840 (Seeed's non-mbed core, which brings the Bluefruit BLE library)
arduino-cli config add board_manager.additional_urls \
  https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json
arduino-cli core update-index
arduino-cli core install Seeeduino:nrf52
```

Then:

```sh
./flash.sh esp32s3            # or: ./flash.sh nrf52840
./flash.sh nrf52840 /dev/cu.usbmodemXXXX   # pass the port explicitly

./monitor.sh                  # serial monitor at 115200 baud, either board
```

`flash.sh` passes the shared `lib/BleKeyCore` to arduino-cli with `--library`; a manual
`arduino-cli compile` needs the same flag. Bench builds and board-specific notes are in
[esp32s3/README.md](esp32s3/README.md) and [nrf52840/README.md](nrf52840/README.md).

## License

[MIT](LICENSE) © 2026 Tobias Wissmüller
