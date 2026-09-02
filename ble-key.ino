// Morse key -> BLE (XIAO ESP32-S3)
// A BLE interface for a Morse key: plug in your own straight key or paddle and it streams
// the keying as timed edges (5-byte notifications) to the Longpath app, which produces the
// audio/sidetone. The onboard LED gives instant, BLE-independent visual feedback.
//
// Library: NimBLE-Arduino  ->  arduino-cli lib install "NimBLE-Arduino"
// The two UUIDs below are the Longpath BLE contract — keep them as they are, or the
// Longpath app will not find the key. Fork with your own (`uuidgen`) only for a
// different client.
//
// Battery (optional mod, see BATTERY.md): a LiPo on the BAT pads plus a 2 × 220 kΩ divider
// from BAT+ to GND, tapped into A0. The cell level is published through the SIG-standard
// Battery Service (0x180F / 0x2A19) next to the Longpath service — the keying contract is
// untouched, and clients that do not know the service simply ignore it. A battery key also
// deep-sleeps after IDLE_SLEEP_MS without a paddle edge and wakes on the next press
// (14 µA instead of tens of mA); the press that wakes it is consumed by the boot.
//
// On USB neither makes sense: BAT+ is the charger's output and reads ~3.9–4.2 V whether a cell
// is fitted or not, and a sleep would only cost the first press. So while USB power is present
// the key publishes BATTERY_LEVEL_UNKNOWN (0xFF) instead of a percentage — the Longpath app
// shows no level for it — and the idle sleep is off. USB power is sensed on the 5V pin (VBUS)
// through a second 2 × 220 kΩ divider into D10, so a plain charger or power bank counts too;
// a USB host (serial) is detected as well, as a fallback for a key without that divider.

#include <NimBLEDevice.h>
#include <string.h>
#include <esp_sleep.h>
#include <driver/rtc_io.h>
#include <driver/gpio.h>

// ---- Pins ----
const int PIN_DIT   = D1;   // GPIO2, Tip
const int PIN_DAH   = D2;   // GPIO3, Ring
const int PIN_VBAT  = A0;   // GPIO1, battery divider tap (BATTERY_MOD only)
const int PIN_VBUS  = D10;  // GPIO9, USB-power (5V pin) divider tap (BATTERY_MOD only)
// LED_BUILTIN = GPIO21 on the XIAO, active-low (LOW = on, HIGH = off)

// ---- Debounce ----
// Report a paddle edge only after the reading is stable this long. Well below the
// shortest Morse element (a dit at 40 WPM ~30 ms), so timing is unaffected.
const uint32_t DEBOUNCE_MS = 5;

// ---- Battery ----
// 1 = the battery code is compiled in and the key checks at boot whether the mod is actually
//     fitted (see detectBatteryMod): with it, the level is reported over BLE and the key
//     deep-sleeps when idle; without it — a stock USB key, both divider taps floating — the
//     Battery Service is not created and the key never sleeps, so one build fits every key.
// 0 = compile the battery code out entirely (no ADC, no sleep, smaller image):
//   arduino-cli compile --build-property "compiler.cpp.extra_flags=-DBATTERY_MOD=0" ...
#ifndef BATTERY_MOD
#define BATTERY_MOD 1
#endif

// ---- Idle sleep (BATTERY_MOD only) ----
// Deep sleep after this long without a paddle edge (counted from boot or the last edge,
// connected or not). Long enough to only ever trigger between sessions, never mid-word:
// the press that wakes the key is lost to the ~1 s boot + reconnect, so a sleep during a
// session would cost an element.
// Overridable for bench tests, e.g. a 30 s build:
//   arduino-cli compile --build-property "compiler.cpp.extra_flags=-DIDLE_SLEEP_MS=30000" ...
#ifndef IDLE_SLEEP_MS
#define IDLE_SLEEP_MS (10UL * 60UL * 1000UL)   // 10 minutes
#endif

// The divider halves the cell voltage (220 kΩ over 220 kΩ), which keeps a full cell
// (4.2 V → 2.1 V) inside the ADC range at 11 dB attenuation (~0–3.1 V). The VBUS divider is
// the same 1:1 pair: 5 V → 2.5 V.
const float    VBAT_DIVIDER   = 2.0f;
const float    VBUS_DIVIDER   = 2.0f;
const uint16_t VBUS_PRESENT_MV = 4000;   // above this the 5V pin carries USB power
const uint32_t VBUS_PERIOD_MS  = 1000;   // how often USB presence is re-sampled
const uint8_t  VBAT_SAMPLES   = 16;      // oversampling — the ESP32 ADC is noisy
const uint32_t VBAT_PERIOD_MS = 10000;   // how often the level is re-measured
const uint16_t VBAT_LOW_MV    = 3500;    // boot double-blink below this
const uint16_t VBAT_PLAUSIBLE_MIN_MV = 2500;   // outside this window the reading is
const uint16_t VBAT_PLAUSIBLE_MAX_MV = 4600;   // treated as "no cell / no divider"
// Published instead of a percentage while a USB host is attached (the divider then sees the
// charger, not the cell). Outside the SIG's 0–100 range on purpose; Longpath reads it as unknown.
const uint8_t  BATTERY_LEVEL_UNKNOWN = 0xFF;

// ---- BLE contract ----
#define SVC_UUID "6e3a0001-0000-1000-8000-00805f9b34fb"   // Longpath contract — do not change
#define CHR_UUID "6e3a0002-0000-1000-8000-00805f9b34fb"   // Longpath contract — do not change

// SIG-assigned numbers (not part of the Longpath contract, but standard — do not change).
const uint16_t BATTERY_SVC_UUID = 0x180F;   // Battery Service
const uint16_t BATTERY_LVL_UUID = 0x2A19;   // Battery Level, uint8 percent 0–100

enum Evt : uint8_t { DIT_DOWN = 0, DIT_UP = 1, DAH_DOWN = 2, DAH_UP = 3 };

NimBLECharacteristic* evtChar     = nullptr;
NimBLECharacteristic* batteryChar = nullptr;
bool batteryModFitted = false;   // decided once at boot by detectBatteryMod()

// 5-byte little-endian packet: [event][uint32 millis timestamp]
void sendEvent(Evt e) {
  uint8_t pkt[5];
  uint32_t t = millis();
  pkt[0] = e;
  memcpy(&pkt[1], &t, 4);          // ESP32 is little-endian
  evtChar->setValue(pkt, sizeof(pkt));
  evtChar->notify();
}

// ---- Battery measurement ----

// Cell voltage in millivolts, from the calibrated ADC reading at the divider tap.
uint16_t readBatteryMillivolts() {
  uint32_t sum = 0;
  for (uint8_t i = 0; i < VBAT_SAMPLES; i++) sum += analogReadMilliVolts(PIN_VBAT);
  return (uint16_t)((sum / VBAT_SAMPLES) * VBAT_DIVIDER);
}

// Open-circuit LiPo discharge curve (single cell, light load), linearly interpolated.
// Flat between 3.6 V and 3.9 V, which is where a cell spends most of its life — a plain
// linear 3.3–4.2 V map would sit at "60 %" for hours and then collapse.
uint8_t batteryPercent(uint16_t mv) {
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

bool batteryPlausible(uint16_t mv) {
  return mv >= VBAT_PLAUSIBLE_MIN_MV && mv <= VBAT_PLAUSIBLE_MAX_MV;
}

// USB power on the 5V pin, in millivolts, from the divider tap on D10.
uint16_t readVbusMillivolts() {
  uint32_t sum = 0;
  for (uint8_t i = 0; i < VBAT_SAMPLES; i++) sum += analogReadMilliVolts(PIN_VBUS);
  return (uint16_t)((sum / VBAT_SAMPLES) * VBUS_DIVIDER);
}

// USB power is present: VBUS is up (charger, power bank or host), or a USB host is talking to
// the serial port (fallback for a key without the VBUS divider — then D10 floats low-ish).
bool usbPowered() {
  return readVbusMillivolts() >= VBUS_PRESENT_MV || Serial.isPlugged();
}

// Is the battery mod actually on this board? With the mod, at least one of the two divider
// taps reads something real at boot: VBUS ≥ 4 V (the key is on USB) or a plausible cell
// voltage on A0. On a stock key both pins float, and a floating ADC input is noisy — so the
// reading has to hold across a few samples spread over ~50 ms before it counts.
bool detectBatteryMod() {
  bool vbusAll = true, cellAll = true;
  for (int i = 0; i < 5; i++) {
    if (readVbusMillivolts() < VBUS_PRESENT_MV) vbusAll = false;
    if (!batteryPlausible(readBatteryMillivolts())) cellAll = false;
    delay(10);
  }
  return vbusAll || cellAll;
}

// Push [value] to the client if it differs from what was last published.
static void publishBattery(uint8_t value, const char* why) {
  static int lastPublished = -1;
  if (value == lastPublished) return;
  lastPublished = value;
  batteryChar->setValue(&value, 1);
  batteryChar->notify();
  Serial.printf("[battery] %s\n", why);
}

// Re-measure the cell, and push the level to the client if it changed. Called from loop()
// every VBAT_PERIOD_MS; the first call after boot always publishes.
void updateBattery() {
  if (!batteryChar) return;

  if (usbPowered()) {
    // BAT+ carries the charger output now, with or without a cell: no level to report.
    publishBattery(BATTERY_LEVEL_UNKNOWN, "on USB — level unknown");
    return;
  }

  uint16_t mv = readBatteryMillivolts();
  if (!batteryPlausible(mv)) {
    // Floating A0 (divider missing?) or the cell unplugged while on USB. Keep the last
    // published value rather than reporting a random number.
    Serial.printf("[battery] implausible reading %u mV — no cell or no divider?\n", mv);
    return;
  }

  int percent = batteryPercent(mv);
  char why[40];
  snprintf(why, sizeof(why), "%u mV -> %d %%", mv, percent);
  publishBattery((uint8_t)percent, why);
}

// BLE-independent low-battery hint at boot: two short blinks of the onboard LED.
void blinkLowBattery() {
  for (int i = 0; i < 2; i++) {
    digitalWrite(LED_BUILTIN, LOW);  delay(120);
    digitalWrite(LED_BUILTIN, HIGH); delay(120);
  }
}

// ---- Idle sleep ----

// Deep sleep until either paddle line goes LOW. Deep sleep is a reset: setup() runs again
// on wake, millis() restarts at 0 and the BLE connection is gone — which is fine, the app
// re-scans on its own, and its keyers detect pauses by wall clock, not device time.
void sleepUntilKeyPress() {
  Serial.println("[sleep] idle — entering deep sleep, wake on dit/dah");

  // Tell the app now rather than letting it wait for the supervision timeout.
  NimBLEServer* server = NimBLEDevice::getServer();
  if (server && server->getConnectedCount() > 0) {
    server->disconnect(server->getPeerInfo(0).getConnHandle());
    delay(150);                                    // let the disconnect go out
  }
  NimBLEDevice::getAdvertising()->stop();

  // The plain INPUT_PULLUP is a digital-domain pull-up and dies in deep sleep; without an
  // RTC pull-up both lines float low and the board wakes straight away in a loop. Both
  // GPIO2 and GPIO3 are RTC IOs on the S3, so re-arm them there.
  //
  // Deliberately NOT keeping the RTC-peripheral power domain on (esp_sleep_pd_config
  // ESP_PD_DOMAIN_RTC_PERIPH / ESP_PD_OPTION_ON), although the IDF docs suggest it for
  // internal pull-ups: measured on the XIAO ESP32-S3 with IDF 5.5, ext1 ANY_LOW never fires
  // with the domain forced on, while with AUTO the IDF holds the pad configuration
  // (pull-up included) through the sleep and the wake works — at lower sleep current, too.
  const gpio_num_t DIT = (gpio_num_t)PIN_DIT;
  const gpio_num_t DAH = (gpio_num_t)PIN_DAH;
  for (gpio_num_t pin : { DIT, DAH }) {
    rtc_gpio_init(pin);
    rtc_gpio_set_direction(pin, RTC_GPIO_MODE_INPUT_ONLY);
    rtc_gpio_pulldown_dis(pin);
    rtc_gpio_pullup_en(pin);
  }
  esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_AUTO);

  // Park the LED off and hold it there: a floating GPIO21 would let the active-low LED
  // glow faintly through the whole sleep.
  digitalWrite(LED_BUILTIN, HIGH);
  gpio_hold_en((gpio_num_t)LED_BUILTIN);
  gpio_deep_sleep_hold_en();

  const uint64_t mask = (1ULL << PIN_DIT) | (1ULL << PIN_DAH);
  esp_err_t armed = esp_sleep_enable_ext1_wakeup_io(mask, ESP_EXT1_WAKEUP_ANY_LOW);   // dit OR dah
  delay(5);
  Serial.printf("[sleep] ext1 armed (%d), rtc levels dit=%u dah=%u\n",
                armed, rtc_gpio_get_level(DIT), rtc_gpio_get_level(DAH));
#ifdef SLEEP_TEST_TIMER_S
  // Bench builds only: also wake after a fixed time, to test the wake/boot path without a key.
  esp_sleep_enable_timer_wakeup((uint64_t)SLEEP_TEST_TIMER_S * 1000000ULL);
#endif
  Serial.flush();
  esp_deep_sleep_start();
}

// After a wake, release the holds and hand the wake pins back from the RTC domain to the
// digital GPIO matrix — otherwise pinMode() is silently ineffective and digitalWrite()
// cannot drive the LED.
void releaseSleepHolds() {
  gpio_hold_dis((gpio_num_t)LED_BUILTIN);
  gpio_deep_sleep_hold_dis();
  for (gpio_num_t pin : { (gpio_num_t)PIN_DIT, (gpio_num_t)PIN_DAH }) {
    rtc_gpio_hold_dis(pin);
    rtc_gpio_deinit(pin);
  }
}

// Re-advertise whenever a central disconnects, so the app can reconnect (e.g. after an app
// restart) without power-cycling the board. NimBLE stops advertising once connected and does
// not resume on its own.
// ---- Link parameters ----
// Keying edges must not wait for a skipped connection event: ask the central for a short
// interval and no slave latency as soon as it connects. Apple accepts 15–30 ms with latency 0
// (its accessory guidelines); a central that negotiated, say, 30 ms with latency 4 would
// otherwise deliver an UP edge up to 150 ms late, which the app's keyer hears as extra dits.
const uint16_t CONN_INTERVAL_MIN = 12;    // × 1.25 ms = 15 ms
const uint16_t CONN_INTERVAL_MAX = 24;    // × 1.25 ms = 30 ms
const uint16_t CONN_LATENCY      = 0;
const uint16_t CONN_TIMEOUT      = 400;   // × 10 ms = 4 s

volatile uint32_t connectedAtMs = 0;      // for the one-off parameter log in loop()

void logConnParams(const char* when) {
  NimBLEServer* server = NimBLEDevice::getServer();
  if (!server || server->getConnectedCount() == 0) return;
  NimBLEConnInfo info = server->getPeerInfo(0);
  Serial.printf("[paddle] link %s: interval %.2f ms, latency %u, timeout %u ms\n", when,
                info.getConnInterval() * 1.25f, info.getConnLatency(), info.getConnTimeout() * 10);
}

class ServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo) override {
    Serial.printf("[paddle] central connected (interval %.2f ms, latency %u, timeout %u ms)\n",
                  connInfo.getConnInterval() * 1.25f, connInfo.getConnLatency(), connInfo.getConnTimeout() * 10);
    pServer->updateConnParams(connInfo.getConnHandle(), CONN_INTERVAL_MIN, CONN_INTERVAL_MAX,
                              CONN_LATENCY, CONN_TIMEOUT);
    connectedAtMs = millis();
  }
  void onDisconnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo, int reason) override {
    Serial.printf("[paddle] central disconnected (reason %d) — re-advertising\n", reason);
    NimBLEDevice::startAdvertising();
  }
};

void setup() {
  Serial.begin(115200);
  // Woken by a key press? Then every millisecond counts towards the reconnect — skip
  // the serial-monitor grace period a cold boot affords.
  esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  bool wokeFromSleep = cause == ESP_SLEEP_WAKEUP_EXT1;
  if (!wokeFromSleep) delay(400);
  if (wokeFromSleep) {
    uint64_t pins = esp_sleep_get_ext1_wakeup_status();
    Serial.printf("\n[paddle] woke on key press (%s)\n",
                  (pins & (1ULL << PIN_DAH)) ? "dah" : "dit");
  } else {
    Serial.printf("\n[paddle] boot (wake cause %d)\n", (int)cause);
  }

#if BATTERY_MOD
  releaseSleepHolds();
#endif

  pinMode(PIN_DIT, INPUT_PULLUP);
  pinMode(PIN_DAH, INPUT_PULLUP);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);                 // LED off (active-low)
  Serial.println("[paddle] pins ready");

#if BATTERY_MOD
  analogSetPinAttenuation(PIN_VBAT, ADC_11db);     // full 0–3.1 V range for the 2.1 V tap
  analogSetPinAttenuation(PIN_VBUS, ADC_11db);     // and for the 2.5 V VBUS tap
  analogReadResolution(12);
  batteryModFitted = detectBatteryMod();
  if (!batteryModFitted) {
    Serial.println("[battery] no divider or cell detected — stock key, battery features off");
  } else if (usbPowered()) {
    Serial.printf("[battery] on USB (VBUS %u mV) — level not measured, idle sleep off\n", readVbusMillivolts());
  } else {
    uint16_t bootMv = readBatteryMillivolts();
    Serial.printf("[battery] %u mV at boot (%d %%)\n", bootMv, batteryPercent(bootMv));
    if (bootMv < VBAT_LOW_MV) blinkLowBattery();
  }
#endif

  NimBLEDevice::init("Paddle");
  Serial.print("[paddle] BLE MAC: ");
  Serial.println(NimBLEDevice::getAddress().toString().c_str());

  NimBLEServer*  server = NimBLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());
  NimBLEService* svc    = server->createService(SVC_UUID);
  evtChar = svc->createCharacteristic(CHR_UUID, NIMBLE_PROPERTY::NOTIFY);
  svc->start();

#if BATTERY_MOD
  // Standard Battery Service, only on a key that actually has the mod: the client reads the
  // level once after connecting and then subscribes to changes. Seeded with "unknown" until
  // the first updateBattery() below replaces it (the first call always publishes).
  if (batteryModFitted) {
    NimBLEService* batterySvc = server->createService(NimBLEUUID(BATTERY_SVC_UUID));
    batteryChar = batterySvc->createCharacteristic(NimBLEUUID(BATTERY_LVL_UUID),
                                                   NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY);
    uint8_t seed = BATTERY_LEVEL_UNKNOWN;
    batteryChar->setValue(&seed, 1);
    batterySvc->start();
    updateBattery();
  }
#endif

  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->setName("Paddle");          // NimBLE 2.x: name is NOT advertised by default
  adv->addServiceUUID(SVC_UUID);   // the app scans for the Longpath service only
  adv->enableScanResponse(true);   // NimBLE 2.x: scan response (carries the name) is off by default
  bool ok = adv->start();
  Serial.print("[paddle] advertising started: ");
  Serial.println(ok ? "yes" : "NO");
}

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

void loop() {
  static Debounced dit, dah;
  static uint32_t lastBatteryMs = 0;
  static uint32_t lastEdgeMs = 0;                   // boot counts as activity
  static bool readyLogged = false;
  static bool wasOnUsb = false;
  static bool onUsb = false;
  static uint32_t lastVbusMs = 0;

  uint32_t now = millis();

  // USB-CDC drops everything printed before the host opens the port, i.e. the whole boot
  // log after a wake. Repeat the essentials once the monitor has had a chance to attach.
  if (!readyLogged && now >= 3000) {
    readyLogged = true;
    esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
    uint64_t pins = (cause == ESP_SLEEP_WAKEUP_EXT1) ? esp_sleep_get_ext1_wakeup_status() : 0;
    Serial.printf("[paddle] ready — %s, %s\n",
                  cause == ESP_SLEEP_WAKEUP_EXT1
                      ? ((pins & (1ULL << PIN_DAH)) ? "woke on dah" : "woke on dit")
                      : "cold boot",
                  NimBLEDevice::getServer()->getConnectedCount() ? "connected" : "advertising");
#if BATTERY_MOD
    Serial.printf("[battery] VBUS %u mV, BAT %u mV — %s\n", readVbusMillivolts(), readBatteryMillivolts(),
                  !batteryModFitted ? "no mod detected, battery features off"
                  : usbPowered() ? "on USB, level unknown, idle sleep off" : "on the cell");
#endif
  }
  // Log the negotiated link parameters once, a few seconds after the connect (the central
  // answers the update request asynchronously).
  if (connectedAtMs && (now - connectedAtMs) >= 3000) {
    connectedAtMs = 0;
    logConnParams("settled");
  }

  bool ditSample = (digitalRead(PIN_DIT) == LOW);  // pressed = LOW
  bool dahSample = (digitalRead(PIN_DAH) == LOW);

  if (dit.update(ditSample, now)) {
    sendEvent(dit.reported ? DIT_DOWN : DIT_UP);
    Serial.println(dit.reported ? "[paddle] DIT down" : "[paddle] DIT up");
    lastEdgeMs = now;
  }
  if (dah.update(dahSample, now)) {
    sendEvent(dah.reported ? DAH_DOWN : DAH_UP);
    Serial.println(dah.reported ? "[paddle] DAH down" : "[paddle] DAH up");
    lastEdgeMs = now;
  }

  bool keyed = dit.reported || dah.reported;        // debounced state drives the LED
  digitalWrite(LED_BUILTIN, keyed ? LOW : HIGH);    // active-low

#if BATTERY_MOD
  if (!batteryModFitted) return;                    // stock key: no level, no sleep

  // Measured only while the key is idle: the 16-sample ADC burst takes a few hundred µs
  // and must not land between two paddle edges.
  if (!keyed && (now - lastBatteryMs) >= VBAT_PERIOD_MS) {
    lastBatteryMs = now;
    updateBattery();
  }

  // USB presence is re-sampled once a second while idle (an ADC burst must not land between
  // two paddle edges), and remembered in between.
  if (!keyed && (now - lastVbusMs) >= VBUS_PERIOD_MS) {
    lastVbusMs = now;
    onUsb = usbPowered();
    if (onUsb != wasOnUsb) Serial.println(onUsb ? "[battery] USB power present" : "[battery] USB power gone");
  }

  // No idle sleep on USB: there is nothing to save and a sleep would cost the first press
  // (and drop the serial port). Unplugging restarts the idle clock, so a key taken off the
  // charger stays awake for a full idle period first.
  if (wasOnUsb && !onUsb) lastEdgeMs = now;
  wasOnUsb = onUsb;

  // Idle long enough → sleep. Never while a paddle is held: a held line is LOW and would
  // wake the board again immediately (and a key left resting on its contact should keep
  // the LED on, which is the visible hint that something is wrong).
  if (!onUsb && !keyed && (now - lastEdgeMs) >= IDLE_SLEEP_MS) {
    sleepUntilKeyPress();                           // does not return
  }
#endif
}
