// The board-independent half of the ble-key firmware, shared by esp32s3/ and nrf52840/.
// Everything here is either part of the Longpath BLE contract or pure logic without
// hardware access: UUIDs, the event packet, the debounce, the LiPo curve, the power-state
// values and the charge-LED window. The sketches add the BLE stack, the pins and the sleep.
//
// Both flash.sh and the bench-build commands in the READMEs pass this folder to
// arduino-cli with --library, so it needs no installation.

#pragma once

#include <Arduino.h>
#include <string.h>

// ---- BLE contract ----
#define SVC_UUID "6e3a0001-0000-1000-8000-00805f9b34fb"   // Longpath contract — do not change
#define CHR_UUID "6e3a0002-0000-1000-8000-00805f9b34fb"   // Longpath contract — do not change
#define DEVICE_NAME "Paddle"

// SIG-assigned numbers (not part of the Longpath contract, but standard — do not change).
const uint16_t BATTERY_SVC_UUID   = 0x180F;   // Battery Service
const uint16_t BATTERY_LVL_UUID   = 0x2A19;   // Battery Level, uint8 percent 0–100
const uint16_t BATTERY_STATE_UUID = 0x2A1A;   // Battery Power State, uint8 bit fields (see PowerState)

enum Evt : uint8_t { DIT_DOWN = 0, DIT_UP = 1, DAH_DOWN = 2, DAH_UP = 3 };

const size_t EVENT_PACKET_LEN = 5;

// 5-byte little-endian packet: [event][uint32 millis timestamp]. Both MCUs are little-endian.
inline void encodeEvent(uint8_t pkt[EVENT_PACKET_LEN], Evt e, uint32_t t) {
  pkt[0] = e;
  memcpy(&pkt[1], &t, 4);
}

// ---- Link parameters ----
// Keying edges must not wait for a skipped connection event: ask the central for a short
// interval and no slave latency as soon as it connects. Apple accepts 15–30 ms with latency 0
// (its accessory guidelines); a central that negotiated, say, 30 ms with latency 4 would
// otherwise deliver an UP edge up to 150 ms late, which the app's keyer hears as extra dits.
const uint16_t CONN_INTERVAL_MIN = 12;    // × 1.25 ms = 15 ms
const uint16_t CONN_INTERVAL_MAX = 24;    // × 1.25 ms = 30 ms
const uint16_t CONN_LATENCY      = 0;
const uint16_t CONN_TIMEOUT      = 400;   // × 10 ms = 4 s

// ---- Debounce ----
// Report a paddle edge only after the reading is stable this long. Well below the
// shortest Morse element (a dit at 40 WPM ~30 ms), so timing is unaffected. A paddle's
// contacts were seen bouncing for 6 ms, so 5 ms was not enough.
const uint32_t DEBOUNCE_MS = 12;

// Per-paddle debounce: only report a state change once the raw reading has held
// steady for DEBOUNCE_MS. `raw`/`edgeMs` track the latest (possibly bouncing) reading;
// `reported` is the last debounced state we emitted.
struct Debounced {
  bool reported = false;
  bool raw = false;
  uint32_t edgeMs = 0;

  // Returns true (with the new stable state in `reported`) when a debounced edge occurs.
  bool update(bool sample, uint32_t now) {
    if (sample != raw) { raw = sample; edgeMs = now; }          // raw change (maybe bounce)
    if (sample != reported && (now - edgeMs) >= DEBOUNCE_MS) {  // held steady -> accept
      reported = sample;
      return true;
    }
    return false;
  }
};

// ---- Idle sleep ----
// Deep sleep after this long without a paddle edge (counted from boot or the last edge,
// connected or not). Long enough to only ever trigger between sessions, never mid-word:
// the press that wakes the key is lost to the ~1 s boot + reconnect, so a sleep during a
// session would cost an element.
// Overridable for bench tests, e.g. a 30 s build:
//   arduino-cli compile --build-property "compiler.cpp.extra_flags=-DIDLE_SLEEP_MS=30000" ...
#ifndef IDLE_SLEEP_MS
#define IDLE_SLEEP_MS (10UL * 60UL * 1000UL)   // 10 minutes
#endif

// ---- Battery ----
const uint32_t VBAT_PERIOD_MS = 10000;   // how often the level is re-measured
const uint32_t VBUS_PERIOD_MS = 1000;    // how often USB presence is re-sampled
const uint16_t VBAT_LOW_MV    = 3500;    // boot double-blink below this
const uint16_t VBAT_PLAUSIBLE_MIN_MV = 2500;   // outside this window the reading is
const uint16_t VBAT_PLAUSIBLE_MAX_MV = 4600;   // treated as "no cell / no divider"
// Published instead of a percentage while USB power is present and the key cannot vouch for
// a cell being charged (the measurement then sees the charger, not the cell). Outside the
// SIG's 0–100 range on purpose; Longpath reads it as unknown.
const uint8_t  BATTERY_LEVEL_UNKNOWN = 0xFF;

// Open-circuit LiPo discharge curve (single cell, light load), linearly interpolated.
// Flat between 3.6 V and 3.9 V, which is where a cell spends most of its life — a plain
// linear 3.3–4.2 V map would sit at "60 %" for hours and then collapse.
inline uint8_t batteryPercent(uint16_t mv) {
  static const uint16_t MV[]  = { 3300, 3500, 3600, 3700, 3750, 3800, 3850, 3900, 3950, 4000, 4100, 4200 };
  static const uint8_t  PCT[] = {    0,    5,   10,   20,   30,   40,   50,   60,   70,   80,   90,  100 };
  const int n = sizeof(MV) / sizeof(MV[0]);
  if (mv <= MV[0])     return PCT[0];
  if (mv >= MV[n - 1]) return PCT[n - 1];
  int i = 1;
  while (mv > MV[i]) i++;
  // interpolate between point i-1 and i
  return (uint8_t)(PCT[i - 1] + (uint32_t)(mv - MV[i - 1]) * (PCT[i] - PCT[i - 1]) / (MV[i] - MV[i - 1]));
}

inline bool batteryPlausible(uint16_t mv) {
  return mv >= VBAT_PLAUSIBLE_MIN_MV && mv <= VBAT_PLAUSIBLE_MAX_MV;
}

// What the key can say about its power, published as the SIG Battery Power State (0x2A1A):
// bits 0–1 present (2 no, 3 yes), bits 2–3 discharging (2 no, 3 yes), bits 4–5 charging
// (2 no, 3 yes), bits 6–7 level (0 unknown — the level lives in 0x2A19). 0 = nothing known.
enum PowerState : uint8_t {
  POWER_UNKNOWN  = 0x00,                        // no report, or the key cannot tell yet
  POWER_ON_CELL  = 0x03 | (3 << 2) | (2 << 4),  // present, discharging, not charging
  POWER_CHARGING = 0x03 | (2 << 2) | (3 << 4),  // present, not discharging, charging
  POWER_CHARGED  = 0x03 | (2 << 2) | (2 << 4),  // present, not discharging, not charging
  POWER_NO_CELL  = 0x02,                        // not present
};

inline const char* powerStateName(PowerState ps) {
  switch (ps) {
    case POWER_ON_CELL:  return "on cell";
    case POWER_CHARGING: return "charging";
    case POWER_CHARGED:  return "charged";
    case POWER_NO_CELL:  return "no cell";
    default:             return "unknown";
  }
}

// ---- Charge LED ----
// The charge IC's status line (the net of the red charge LED) is sampled on every loop pass
// (a digitalRead, no ADC burst) and judged once per window: two or more edges in a window =
// flashing; otherwise the level at the window's end, on or off. The window must be longer
// than one blink period of the charge IC. What a verdict means differs per charge IC, so the
// sketches turn it into a PowerState themselves.
const uint32_t CHG_WINDOW_MS      = 3000;
const uint8_t  CHG_FLASH_EDGES    = 2;
const uint8_t  CHG_STEADY_WINDOWS = 2;   // a solid or dark LED counts after this many windows

enum ChargeLed : uint8_t { LED_OFF, LED_ON, LED_FLASHING };

// Watches the charge-LED line across CHG_WINDOW_MS windows. Returns true once per window,
// with the verdict in `verdict`.
struct ChargeLedWatch {
  ChargeLed verdict = LED_OFF;
  bool lastLow = false;
  uint8_t edges = 0;
  uint32_t windowStartMs = 0;

  bool sample(bool ledOn, uint32_t now) {
    if (ledOn != lastLow) { lastLow = ledOn; if (edges < 255) edges++; }
    if ((now - windowStartMs) < CHG_WINDOW_MS) return false;
    verdict = edges >= CHG_FLASH_EDGES ? LED_FLASHING : (lastLow ? LED_ON : LED_OFF);
    edges = 0;
    windowStartMs = now;
    return true;
  }
};
