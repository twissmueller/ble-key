# BLE-Key: explainer

Narrated by the approved female voice (NA17), rendered with `explainer.py`; lines and pictures in `explainer.json`.

**Title:** Turn your Morse key or paddle into a Bluetooth key: open hardware with a XIAO board
**Description:** BLE-Key reads your straight key or paddle through a 3.5 mm jack and streams the keying over Bluetooth LE to Longpath on phone, tablet or Mac. Open firmware for the XIAO ESP32-S3 and nRF52840; build it yourself or get a kit.
**Chapters:** 0:00 The idea · 0:15 Inside · 0:41 Connecting · 0:47 Practising · 0:59 Build or buy

## The idea

- Want to practise Morse on your own paddle, without a radio, and without a cable to the laptop? *(compact-IMG_2447.jpg)*
- BLE-Key is a tiny Bluetooth box that sits between your key and the app. *(mini-esp-white-IMG_2455.jpg)*

## Inside

- It's built around a Seeed XIAO board: the ESP32-S3, or the nRF52840. *(mini-esp-black-IMG_2453.jpg)*
- The paddle goes into the three and a half millimetre jack. The tip is dit, the ring is dah. *(modular-IMG_2440.jpg)*
- The box makes no sound itself. It just sends exact keying edges, and the LED shows when you key. *(mini-nrf-IMG_2457.jpg)*
- There's a version with a battery, too. *(modular-IMG_2441.jpg)*

## Connecting

- Power it over USB-C. In Longpath, it shows up as a paddle. Tap it, and you're connected. *(longpath-device.png)*

## Practising

- Now the app makes the sidetone, decodes what you send, and shows your timing. *(longpath-send.png)*
- It works with straight keys, single paddles and iambic paddles, on phone, tablet or Mac. *(longpath-mac-send.png)*

## Build or buy

- Firmware and enclosure are open on GitHub. Print the case, solder the jack, flash the board. *(modular-IMG_2437.jpg)*
- Or get a parts kit or a finished key from the Ramus Labs shop. *(modular-IMG_2445.jpg)*

## Closing

- Links to the shop, to Longpath and to GitHub are in the description. Seventy-three!
