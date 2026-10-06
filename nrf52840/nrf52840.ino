// Morse key -> BLE (XIAO nRF52840)  — see README.md next to this file
// A BLE interface for a Morse key: plug in your own straight key or paddle and it streams
// the keying as timed edges (5-byte notifications) to the Longpath app, which produces the
// audio/sidetone. The onboard LED gives instant, BLE-independent visual feedback.
//
// Board package: "Seeed nRF52 Boards" (Seeeduino:nrf52, not the mbed one), BLE through its
// bundled Bluefruit library. The board-independent part (UUIDs, packet, debounce, battery
// curve, power states) is in ../lib/BleKeyCore, shared with the ESP32-S3 sketch; ../flash.sh
// passes it to arduino-cli.
//
// Battery: unlike the ESP32-S3, the XIAO nRF52840 brings everything the battery features need,
// so there is no mod beyond soldering a LiPo to the BAT pads:
//   - the cell voltage through an on-board 1 MΩ / 510 kΩ divider into P0.31 (AIN7), switched
//     by P0.14 (VBAT_ENABLE, LOW = on);
//   - USB power from the chip's own VBUS detector (POWER->USBREGSTATUS);
//   - the BQ25100 charger's ~CHG line on P0.17, LOW while a cell charges.
// The Battery Service (0x180F: level 0x2A19 and power state 0x2A1A) is therefore always there.
// Off USB the key can only be running from a cell; on USB without one it publishes the level
// as unknown (0xFF), exactly like the ESP32-S3 key, and the power state stays unknown unless
// the charger says otherwise.
//
// Idle sleep is the nRF52's System OFF (a few µA) with both paddle lines armed as wake-up
// sources. Waking is a reset, as on the ESP32-S3; plugging USB in wakes the key as well.

#include <bluefruit.h>
#include <BleKeyCore.h>
#include <stdarg.h>

// ---- Pins ----
// Same XIAO pads as on the ESP32-S3 key, so the wiring and the case are unchanged.
// Wired as on the ESP32-S3 (D1 and D2 to the jack the same way), yet on the nRF prototype dit
// and dah came out swapped (October 2026), so the nRF reads them the other way round.
const int PIN_DIT      = D2;         // P0.28
const int PIN_DAH      = D1;         // P0.03
const int PIN_KEY_LED  = LED_BLUE;   // P0.06, keying feedback
const int PIN_WARN_LED = LED_RED;    // P0.26, low-battery blink at boot
const int PIN_CHG      = 23;         // P0.17, BQ25100 ~CHG, LOW = charging (no name in the variant)
// PIN_VBAT (P0.31) and VBAT_ENABLE (P0.14) come from the variant.
// The RGB LED is active-low (LOW = on), whatever LED_STATE_ON in the variant says.

// ---- Battery ----
// 1 MΩ over 510 kΩ: a full cell (4.2 V) reads 1.42 V at P0.31, inside the 2.4 V range below.
// The divider is high-impedance (≈340 kΩ source), so the SAADC needs its longest acquisition
// time to settle.
const uint32_t VBAT_DIVIDER_NUM = 1510;
const uint32_t VBAT_DIVIDER_DEN = 510;
const uint32_t ADC_RANGE_MV     = 2400;    // AR_INTERNAL_2_4
const uint32_t ADC_MAX          = 4096;    // 12 bit
const uint8_t  VBAT_SAMPLES     = 16;

BLEService        keySvc(SVC_UUID);
BLECharacteristic evtChar(CHR_UUID);
BLEService        batterySvc(BATTERY_SVC_UUID);
BLECharacteristic batteryChar(BATTERY_LVL_UUID);
BLECharacteristic batteryStateChar(BATTERY_STATE_UUID);
PowerState powerState = POWER_UNKNOWN;   // what the key currently believes, see judgePowerState()

// ---- Logging ----
// Never block on the console. The TinyUSB serial waits as long as the host holds DTR and its
// buffer is full — a monitor that stopped reading would stall the loop and stretch the keying.
// A line that does not fit right now is dropped instead.
void logf(const char* fmt, ...) {
  char buf[160];
  va_list ap;
  va_start(ap, fmt);
  int n = vsnprintf(buf, sizeof(buf), fmt, ap);
  va_end(ap);
  if (n <= 0) return;
  if (n > (int)sizeof(buf) - 1) n = sizeof(buf) - 1;
  if (Serial && Serial.availableForWrite() >= n) Serial.write(buf, n);
}

void sendEvent(Evt e) {
  uint8_t pkt[EVENT_PACKET_LEN];
  encodeEvent(pkt, e, millis());
  evtChar.notify(pkt, sizeof(pkt));   // false while nobody is subscribed — nothing to do then
}

// ---- Battery measurement ----

// Cell voltage in millivolts. Off USB this is the cell; on USB it is the charger's output
// whenever no cell is charging.
uint16_t readBatteryMillivolts() {
  uint32_t sum = 0;
  for (uint8_t i = 0; i < VBAT_SAMPLES; i++) sum += analogRead(PIN_VBAT);
  uint32_t adcMv = (sum / VBAT_SAMPLES) * ADC_RANGE_MV / ADC_MAX;
  return (uint16_t)(adcMv * VBAT_DIVIDER_NUM / VBAT_DIVIDER_DEN);
}

// USB power is present: the nRF52840's own VBUS detector, so a charger or power bank counts
// as much as a host; an enumerated USB connection counts as well, as a second opinion that
// keeps a key on a host from ever sleeping. The register belongs to the SoftDevice once BLE
// runs.
bool usbPowered() {
  if (TinyUSBDevice.mounted()) return true;
  uint32_t status = 0;
  uint8_t sdEnabled = 0;
  sd_softdevice_is_enabled(&sdEnabled);
  if (sdEnabled) sd_power_usbregstatus_get(&status);
  else           status = NRF_POWER->USBREGSTATUS;
  return status & POWER_USBREGSTATUS_VBUSDETECT_Msk;
}

// Push [value] to the client if it differs from what was last published.
static void publishBattery(uint8_t value, const char* why) {
  static int lastPublished = -1;
  if (value == lastPublished) return;
  lastPublished = value;
  batteryChar.write(&value, 1);
  batteryChar.notify(&value, 1);
  logf("[battery] %s\n", why);
}

// Re-measure the cell, and push the level to the client if it changed. Called from loop()
// every VBAT_PERIOD_MS and whenever the power state changes; the first call after boot
// always publishes.
void updateBattery() {
  bool onUsb = usbPowered();
  if (onUsb && powerState != POWER_CHARGING && powerState != POWER_CHARGED) {
    // The pin sees the charger's output now and the key cannot vouch for a cell: no level.
    publishBattery(BATTERY_LEVEL_UNKNOWN, "on USB — level unknown");
    return;
  }

  uint16_t mv = readBatteryMillivolts();
  if (!batteryPlausible(mv)) {
    logf("[battery] implausible reading %u mV — no cell?\n", mv);
    return;
  }

  // While charging this is the cell under charge — a few points high, and climbing; the app
  // shows it as-is next to "charging" and forces 100 % once the key reports charged.
  int percent = batteryPercent(mv);
  char why[48];
  snprintf(why, sizeof(why), "%u mV -> %d %%%s", mv, percent, onUsb ? " (under charge)" : "");
  publishBattery((uint8_t)percent, why);
}

// ---- Charge sense ----

// What the key believes about its power. The BQ25100 pulls ~CHG low for as long as it charges
// a cell and releases it when the cell is full, so: low for whole windows → charging; released
// after having charged → charged. Anything else on USB — released from the start (a full cell,
// or no cell at all) or a flickering line (what the charger does without a cell is not
// verified) — says nothing and stays unknown. Off USB the key runs from the cell, so a
// plausible reading means on cell.
//
// A steady verdict has to hold for CHG_STEADY_WINDOWS windows in a row before it counts.
PowerState judgePowerState(bool onUsb, bool usbJustArrived, bool ledJudged, ChargeLed led) {
  static bool sawCharging = false;   // since USB arrived
  static ChargeLed lastLed = LED_OFF;
  static uint8_t steadyWindows = 0;  // consecutive windows with the same verdict
  if (usbJustArrived) { sawCharging = false; steadyWindows = 0; }

  if (!onUsb) {
    sawCharging = false; steadyWindows = 0;
    return batteryPlausible(readBatteryMillivolts()) ? POWER_ON_CELL : POWER_UNKNOWN;
  }
  if (ledJudged) {
    steadyWindows = (led == lastLed && steadyWindows < 255) ? steadyWindows + 1 : 1;
    lastLed = led;
  }
  bool steady = steadyWindows >= CHG_STEADY_WINDOWS;
  if (lastLed == LED_ON && steady) { sawCharging = true; return POWER_CHARGING; }
  if (sawCharging && lastLed == LED_OFF && steady) return POWER_CHARGED;
  if (sawCharging && lastLed == LED_ON) return POWER_CHARGING;   // still charging, window pending
  return POWER_UNKNOWN;
}

// Push the power state to the client if it changed, and re-run the level, whose meaning on
// USB depends on it (a level is only published while charging or charged).
static void publishPowerState(PowerState ps) {
  if (ps == powerState) return;
  powerState = ps;
  uint8_t value = (uint8_t)ps;
  batteryStateChar.write(&value, 1);
  batteryStateChar.notify(&value, 1);
  logf("[battery] power state: %s\n", powerStateName(ps));
  updateBattery();
}

// BLE-independent low-battery hint at boot: two short red blinks.
void blinkLowBattery() {
  for (int i = 0; i < 2; i++) {
    digitalWrite(PIN_WARN_LED, LOW);  delay(120);
    digitalWrite(PIN_WARN_LED, HIGH); delay(120);
  }
}

// ---- Idle sleep ----

// System OFF until either paddle line goes LOW. Waking is a reset: setup() runs again,
// millis() restarts at 0 and the BLE connection is gone — which is fine, the app re-scans on
// its own, and its keyers detect pauses by wall clock, not device time.
void sleepUntilKeyPress() {
  logf("[sleep] idle — entering System OFF, wake on dit/dah\n");

  // Tell the app now rather than letting it wait for the supervision timeout.
  Bluefruit.Advertising.restartOnDisconnect(false);
  if (Bluefruit.connected()) {
    Bluefruit.disconnect(Bluefruit.connHandle());
    delay(150);                                    // let the disconnect go out
  }
  Bluefruit.Advertising.stop();

  // GPIO configuration survives System OFF: the LEDs stay off (active-low, driven HIGH),
  // VBAT_ENABLE stays LOW, and the pull-ups plus the SENSE setting on the paddle lines are
  // what wakes the chip.
  digitalWrite(PIN_KEY_LED, HIGH);
  digitalWrite(PIN_WARN_LED, HIGH);
  nrf_gpio_cfg_sense_input(g_ADigitalPinMap[PIN_DIT], NRF_GPIO_PIN_PULLUP, NRF_GPIO_PIN_SENSE_LOW);
  nrf_gpio_cfg_sense_input(g_ADigitalPinMap[PIN_DAH], NRF_GPIO_PIN_PULLUP, NRF_GPIO_PIN_SENSE_LOW);
  delay(5);

  uint8_t sdEnabled = 0;
  sd_softdevice_is_enabled(&sdEnabled);
  if (sdEnabled) sd_power_system_off();
  else           NRF_POWER->SYSTEMOFF = 1;
  while (true) {}                                  // not reached
}

// ---- Link ----

// The callbacks run in Bluefruit's callback task; they only record what happened, and loop()
// does the logging, so the USB serial is only ever written from one task.
volatile uint32_t connectedAtMs = 0;      // for the one-off parameter log in loop()
volatile bool     connectSeen = false;
volatile int      disconnectReason = -1;

void logConnParams(const char* when) {
  if (!Bluefruit.connected()) return;
  BLEConnection* conn = Bluefruit.Connection(Bluefruit.connHandle());
  if (!conn) return;
  uint32_t interval = conn->getConnectionInterval() * 125;   // × 1.25 ms, in 1/100 ms
  logf("[paddle] link %s: interval %lu.%02lu ms, latency %u, timeout %u ms\n", when,
       interval / 100, interval % 100, conn->getSlaveLatency(), conn->getSupervisionTimeout() * 10);
}

void onConnect(uint16_t connHandle) {
  Bluefruit.Connection(connHandle)->requestConnectionParameter(CONN_INTERVAL_MIN, CONN_LATENCY, CONN_TIMEOUT);
  connectedAtMs = millis();
  connectSeen = true;
}

// Bluefruit re-advertises on its own after a disconnect (restartOnDisconnect), so the app can
// reconnect without power-cycling the board.
void onDisconnect(uint16_t connHandle, uint8_t reason) {
  disconnectReason = reason;
}

// Which paddle woke the chip: the GPIO LATCH register keeps the pins whose SENSE condition
// was met. Read before pinMode() reconfigures the pins.
static bool wokeFromSleep = false;
static bool wokeOnDah = false;

void setup() {
  uint32_t latch = NRF_P0->LATCH;
  NRF_P0->LATCH = latch;                           // write-1-to-clear
  wokeFromSleep = readResetReason() & POWER_RESETREAS_OFF_Msk;
  wokeOnDah = latch & (1UL << g_ADigitalPinMap[PIN_DAH]);

  Serial.begin(115200);
  // Woken by a key press? Then every millisecond counts towards the reconnect — skip the
  // serial-monitor grace period a cold boot affords.
  if (!wokeFromSleep) delay(400);
  if (wokeFromSleep) logf("\n[paddle] woke on key press (%s)\n", wokeOnDah ? "dah" : "dit");
  else               logf("\n[paddle] boot (reset reason 0x%08lx)\n", readResetReason());

  pinMode(PIN_DIT, INPUT_PULLUP);                  // also clears the SENSE setting of the sleep
  pinMode(PIN_DAH, INPUT_PULLUP);
  pinMode(PIN_KEY_LED, OUTPUT);
  digitalWrite(PIN_KEY_LED, HIGH);                     // off (active-low)
  pinMode(PIN_WARN_LED, OUTPUT);
  digitalWrite(PIN_WARN_LED, HIGH);
  logf("[paddle] pins ready\n");

  // The variant parks VBAT_ENABLE HIGH. Seeed's advice is the opposite: with it HIGH, a full
  // cell lifts P0.31 above VDD through the divider. LOW for good costs ~3 µA through the
  // divider and keeps the pin safe, in System OFF as well.
  pinMode(VBAT_ENABLE, OUTPUT);
  digitalWrite(VBAT_ENABLE, LOW);
  pinMode(PIN_CHG, INPUT_PULLUP);
  analogReference(AR_INTERNAL_2_4);
  analogReadResolution(12);
  analogSampleTime(40);
  if (usbPowered()) {
    logf("[battery] on USB — idle sleep off, watching ~CHG\n");
  } else {
    uint16_t bootMv = readBatteryMillivolts();
    logf("[battery] %u mV at boot (%d %%)\n", bootMv, batteryPercent(bootMv));
    if (bootMv < VBAT_LOW_MV) blinkLowBattery();
  }

  Bluefruit.autoConnLed(false);                    // the LED belongs to the keying
  Bluefruit.begin();
  Bluefruit.setName(DEVICE_NAME);
  Bluefruit.Periph.setConnInterval(CONN_INTERVAL_MIN, CONN_INTERVAL_MAX);
  Bluefruit.Periph.setConnSlaveLatency(CONN_LATENCY);
  Bluefruit.Periph.setConnSupervisionTimeout(CONN_TIMEOUT);
  Bluefruit.Periph.setConnectCallback(onConnect);
  Bluefruit.Periph.setDisconnectCallback(onDisconnect);
  uint8_t mac[6];
  Bluefruit.getAddr(mac);
  logf("[paddle] BLE MAC: %02X:%02X:%02X:%02X:%02X:%02X\n", mac[5], mac[4], mac[3], mac[2], mac[1], mac[0]);

  keySvc.begin();
  evtChar.setProperties(CHR_PROPS_NOTIFY);
  evtChar.setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
  evtChar.setFixedLen(EVENT_PACKET_LEN);
  evtChar.begin();

  // Standard Battery Service: the client reads the level once after connecting and then
  // subscribes to changes. Seeded with "unknown" until the first updateBattery() below
  // replaces it (the first call always publishes).
  batterySvc.begin();
  BLECharacteristic* batteryChars[] = { &batteryChar, &batteryStateChar };
  for (BLECharacteristic* chr : batteryChars) {
    chr->setProperties(CHR_PROPS_READ | CHR_PROPS_NOTIFY);
    chr->setPermission(SECMODE_OPEN, SECMODE_NO_ACCESS);
    chr->setFixedLen(1);
    chr->begin();
  }
  uint8_t seed = BATTERY_LEVEL_UNKNOWN;
  batteryChar.write(&seed, 1);
  uint8_t stateSeed = POWER_UNKNOWN;
  batteryStateChar.write(&stateSeed, 1);
  bool onUsb = usbPowered();
  publishPowerState(judgePowerState(onUsb, onUsb, false, LED_OFF));
  updateBattery();

  // Flags and the 128-bit Longpath UUID fill the advertising packet; the name goes into the
  // scan response. The app scans for the Longpath service only.
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addService(keySvc);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);      // × 0.625 ms: 20 ms fast, then 152.5 ms
  Bluefruit.Advertising.setFastTimeout(30);        // seconds of fast advertising
  bool ok = Bluefruit.Advertising.start(0);        // 0 = forever
  logf("[paddle] advertising started: %s\n", ok ? "yes" : "NO");
}

void loop() {
  static Debounced dit, dah;
  static uint32_t lastBatteryMs = 0;
  static uint32_t lastEdgeMs = 0;                   // boot counts as activity
  static bool readyLogged = false;
  static bool wasOnUsb = usbPowered();
  static bool onUsb = wasOnUsb;
  static uint32_t lastVbusMs = 0;
  static ChargeLedWatch chargeLed;

  uint32_t now = millis();

  // The serial monitor misses everything printed before it attaches, i.e. the whole boot
  // log after a wake. Repeat the essentials once the monitor has had a chance to attach.
  if (!readyLogged && now >= 3000) {
    readyLogged = true;
    logf("[paddle] ready — %s, %s\n",
         wokeFromSleep ? (wokeOnDah ? "woke on dah" : "woke on dit") : "cold boot",
         Bluefruit.connected() ? "connected" : "advertising");
    logf("[battery] BAT %u mV — %s, power state %s\n", readBatteryMillivolts(),
         usbPowered() ? "on USB, idle sleep off" : "on the cell", powerStateName(powerState));
  }
  if (connectSeen) { connectSeen = false; logConnParams("at connect"); }
  if (disconnectReason >= 0) {
    logf("[paddle] central disconnected (reason 0x%02x) — re-advertising\n", disconnectReason);
    disconnectReason = -1;
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
    logf(dit.reported ? "[paddle] DIT down\n" : "[paddle] DIT up\n");
    lastEdgeMs = now;
  }
  if (dah.update(dahSample, now)) {
    sendEvent(dah.reported ? DAH_DOWN : DAH_UP);
    logf(dah.reported ? "[paddle] DAH down\n" : "[paddle] DAH up\n");
    lastEdgeMs = now;
  }

  bool keyed = dit.reported || dah.reported;        // debounced state drives the LED
  digitalWrite(PIN_KEY_LED, keyed ? LOW : HIGH);        // active-low

  // Measured only while the key is idle: the 16-sample ADC burst at 40 µs each takes about a
  // millisecond and must not land between two paddle edges.
  if (!keyed && (now - lastBatteryMs) >= VBAT_PERIOD_MS) {
    lastBatteryMs = now;
    // Off USB the cell speaks for itself; re-judge with every measurement.
    if (!onUsb) publishPowerState(judgePowerState(false, false, false, LED_OFF));
    updateBattery();
  }

  // USB presence is a register read, but is still only re-sampled once a second so a plug
  // that bounces does not reset the charge classifier several times.
  bool usbJustArrived = false;
  if ((now - lastVbusMs) >= VBUS_PERIOD_MS) {
    lastVbusMs = now;
    onUsb = usbPowered();
    if (onUsb != wasOnUsb) {
      logf(onUsb ? "[battery] USB power present\n" : "[battery] USB power gone\n");
      usbJustArrived = onUsb;
      if (!onUsb) publishPowerState(judgePowerState(false, false, false, LED_OFF));
    }
  }

  // ~CHG is cheap to sample, so it is watched on every pass; its verdict, once a window, is
  // what moves the power state while on USB.
  bool ledJudged = chargeLed.sample(digitalRead(PIN_CHG) == LOW, now);
  if (onUsb && (ledJudged || usbJustArrived)) {
    publishPowerState(judgePowerState(true, usbJustArrived, ledJudged, chargeLed.verdict));
  }

  // No idle sleep on USB: there is nothing to save and a sleep would cost the first press
  // (and drop the serial port). Unplugging restarts the idle clock, so a key taken off the
  // charger stays awake for a full idle period first.
  if (wasOnUsb && !onUsb) lastEdgeMs = now;
  wasOnUsb = onUsb;

  // Idle long enough → sleep. Never while a paddle is held: a held line is LOW and would
  // wake the chip again immediately (and a key left resting on its contact should keep the
  // LED on, which is the visible hint that something is wrong).
  if (!onUsb && !keyed && (now - lastEdgeMs) >= IDLE_SLEEP_MS) {
    sleepUntilKeyPress();                           // does not return
  }
}
