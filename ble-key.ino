// Morse key -> BLE (XIAO ESP32-S3)
// A BLE interface for a Morse key: plug in your own straight key or paddle and it streams
// the keying as timed edges (5-byte notifications) to the Sidetone app, which produces the
// audio/sidetone. The onboard LED gives instant, BLE-independent visual feedback.
//
// Library: NimBLE-Arduino  ->  arduino-cli lib install "NimBLE-Arduino"
// Generate your own UUIDs with `uuidgen` and replace the two below.

#include <NimBLEDevice.h>
#include <string.h>

// ---- Pins ----
const int PIN_DIT   = D1;   // GPIO2, Tip
const int PIN_DAH   = D2;   // GPIO3, Ring
// LED_BUILTIN = GPIO21 on the XIAO, active-low (LOW = on, HIGH = off)

// ---- Debounce ----
// Report a paddle edge only after the reading is stable this long. Well below the
// shortest Morse element (a dit at 40 WPM ~30 ms), so timing is unaffected.
const uint32_t DEBOUNCE_MS = 5;

// ---- BLE contract ----
#define SVC_UUID "6e3a0001-0000-1000-8000-00805f9b34fb"   // <-- replace (uuidgen)
#define CHR_UUID "6e3a0002-0000-1000-8000-00805f9b34fb"   // <-- replace (uuidgen)

enum Evt : uint8_t { DIT_DOWN = 0, DIT_UP = 1, DAH_DOWN = 2, DAH_UP = 3 };

NimBLECharacteristic* evtChar = nullptr;

// 5-byte little-endian packet: [event][uint32 millis timestamp]
void sendEvent(Evt e) {
  uint8_t pkt[5];
  uint32_t t = millis();
  pkt[0] = e;
  memcpy(&pkt[1], &t, 4);          // ESP32 is little-endian
  evtChar->setValue(pkt, sizeof(pkt));
  evtChar->notify();
}

// Re-advertise whenever a central disconnects, so the app can reconnect (e.g. after an app
// restart) without power-cycling the board. NimBLE stops advertising once connected and does
// not resume on its own.
class ServerCallbacks : public NimBLEServerCallbacks {
  void onConnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo) override {
    Serial.println("[paddle] central connected");
  }
  void onDisconnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo, int reason) override {
    Serial.printf("[paddle] central disconnected (reason %d) — re-advertising\n", reason);
    NimBLEDevice::startAdvertising();
  }
};

void setup() {
  Serial.begin(115200);
  delay(400);
  Serial.println("\n[paddle] boot");

  pinMode(PIN_DIT, INPUT_PULLUP);
  pinMode(PIN_DAH, INPUT_PULLUP);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);                 // LED off (active-low)
  Serial.println("[paddle] pins ready");

  NimBLEDevice::init("Paddle");
  Serial.print("[paddle] BLE MAC: ");
  Serial.println(NimBLEDevice::getAddress().toString().c_str());

  NimBLEServer*  server = NimBLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());
  NimBLEService* svc    = server->createService(SVC_UUID);
  evtChar = svc->createCharacteristic(CHR_UUID, NIMBLE_PROPERTY::NOTIFY);
  svc->start();

  NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
  adv->setName("Paddle");          // NimBLE 2.x: name is NOT advertised by default
  adv->addServiceUUID(SVC_UUID);
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

  uint32_t now = millis();
  bool ditSample = (digitalRead(PIN_DIT) == LOW);  // pressed = LOW
  bool dahSample = (digitalRead(PIN_DAH) == LOW);

  if (dit.update(ditSample, now)) {
    sendEvent(dit.reported ? DIT_DOWN : DIT_UP);
    Serial.println(dit.reported ? "[paddle] DIT down" : "[paddle] DIT up");
  }
  if (dah.update(dahSample, now)) {
    sendEvent(dah.reported ? DAH_DOWN : DAH_UP);
    Serial.println(dah.reported ? "[paddle] DAH down" : "[paddle] DAH up");
  }

  bool keyed = dit.reported || dah.reported;        // debounced state drives the LED
  digitalWrite(LED_BUILTIN, keyed ? LOW : HIGH);    // active-low
}
