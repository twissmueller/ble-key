#!/usr/bin/env bash
set -euo pipefail

FQBN="esp32:esp32:XIAO_ESP32S3"
SKETCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Port: pass as an argument, otherwise auto-detect.
PORT="${1:-}"
if [[ -z "$PORT" ]]; then
  PORT=$(ls /dev/cu.usbmodem* /dev/ttyACM* 2>/dev/null | head -n1 || true)
fi
if [[ -z "$PORT" ]]; then
  echo "No port found. Plug in the board or pass one: ./flash.sh /dev/cu.usbmodemXXXX" >&2
  exit 1
fi

echo "==> Compiling ($FQBN)"
arduino-cli compile --fqbn "$FQBN" "$SKETCH_DIR"

echo "==> Flashing to $PORT"
arduino-cli upload --fqbn "$FQBN" -p "$PORT" "$SKETCH_DIR"

echo "==> Done."
