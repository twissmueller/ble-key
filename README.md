# ble-key

A Bluetooth Low Energy interface for a Morse **key**, built on a
[Seeed Studio XIAO ESP32-S3](https://wiki.seeedstudio.com/xiao_esp32s3_getting_started/).

Plug in your own straight key or iambic paddle. The board reads the contacts (dit / dah),
debounces them, and streams **timed keying edges** over BLE as notifications to the
[Sidetone](https://github.com/twissmueller/sidetone) Morse-training app, which produces the
audio/sidetone and does the training. The device itself makes no sound — it's purely the
key interface. The onboard LED gives instant, BLE-independent visual feedback while keying.

The BLE contract below is simple and app-agnostic — anything that speaks GATT can consume it.

## Hardware

| Signal   | XIAO pin | GPIO   | Notes                          |
|----------|----------|--------|--------------------------------|
| Dit      | `D1`     | GPIO2  | Tip, `INPUT_PULLUP`, pressed = LOW |
| Dah      | `D2`     | GPIO3  | Ring, `INPUT_PULLUP`, pressed = LOW |
| LED      | `GPIO21` | —      | `LED_BUILTIN`, active-low      |

Wire each key/paddle contact between its input pin and ground; the internal pull-ups mean
no external resistors are needed. A straight key uses the dit line only; an iambic paddle
uses both. The tip/ring assignment matches a standard 3.5 mm TRS paddle plug.

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

### UUIDs

The service and characteristic UUIDs in `ble-key.ino` are **placeholders**. Generate your
own before flashing:

```sh
uuidgen   # run twice — one for the service, one for the characteristic
```

and replace `SVC_UUID` / `CHR_UUID` near the top of the sketch.

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

## License

[MIT](LICENSE) © 2026 Tobias Wissmüller
