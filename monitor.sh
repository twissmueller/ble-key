#!/usr/bin/env bash
set -euo pipefail

# Serial monitor for the paddle firmware (115200 baud).
# Usage: ./monitor.sh [port]   (auto-detects the port if omitted)
# Exit with Ctrl-C.

BAUD=115200

PORT="${1:-}"
if [[ -z "$PORT" ]]; then
  PORT=$(ls /dev/cu.usbmodem* /dev/ttyACM* 2>/dev/null | head -n1 || true)
fi
if [[ -z "$PORT" ]]; then
  echo "No port found. Connect the board over USB or pass one: ./monitor.sh /dev/cu.usbmodemXXXX" >&2
  exit 1
fi

echo "==> Serial monitor on $PORT ($BAUD baud) — exit with Ctrl-C"
arduino-cli monitor -p "$PORT" -c baudrate="$BAUD"
