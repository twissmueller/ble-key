#!/usr/bin/env bash
set -euo pipefail

# Compile and flash the key firmware.
# Usage: ./flash.sh <esp32s3|nrf52840> [port]   (auto-detects the port if omitted)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BOARD="${1:-}"
case "$BOARD" in
  esp32s3)  FQBN="esp32:esp32:XIAO_ESP32S3" ;;
  nrf52840) FQBN="Seeeduino:nrf52:xiaonRF52840" ;;
  *)
    echo "Usage: ./flash.sh <esp32s3|nrf52840> [port]" >&2
    exit 1
    ;;
esac
SKETCH_DIR="$ROOT/$BOARD"

# Port: pass as the second argument, otherwise auto-detect.
PORT="${2:-}"
if [[ -z "$PORT" ]]; then
  PORT=$(ls /dev/cu.usbmodem* /dev/ttyACM* 2>/dev/null | head -n1 || true)
fi
if [[ -z "$PORT" ]]; then
  echo "No port found. Plug in the board or pass one: ./flash.sh $BOARD /dev/cu.usbmodemXXXX" >&2
  exit 1
fi

if [[ "$BOARD" == nrf52840 ]]; then
  # The Seeed nRF52 core packs the image with scripts that call `python` (not `python3`)
  # and with adafruit-nrfutil, which refuses to run under an ASCII locale.
  if ! command -v python >/dev/null 2>&1; then
    SHIM="$(mktemp -d)"
    trap 'rm -rf "$SHIM"' EXIT
    ln -s "$(command -v python3)" "$SHIM/python"
    export PATH="$SHIM:$PATH"
  fi
  export LC_ALL="${LC_ALL:-en_US.UTF-8}" LANG="${LANG:-en_US.UTF-8}"
fi

echo "==> Compiling ($FQBN)"
arduino-cli compile --fqbn "$FQBN" --library "$ROOT/lib/BleKeyCore" "$SKETCH_DIR"

echo "==> Flashing to $PORT"
arduino-cli upload --fqbn "$FQBN" -p "$PORT" "$SKETCH_DIR"

echo "==> Done."
