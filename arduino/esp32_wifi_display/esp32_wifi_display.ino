/*
 * esp32_wifi_display.ino
 * ESP32 (e.g. ESP-WROOM-32) — bridges RP2040 UART telemetry to a phone/browser.
 *
 * - Creates WiFi access point (default SSID TekkenMini / password tekken123)
 * - HTTP :80 serves a minimal HTML5 canvas viewer
 * - WebSocket :81 broadcasts JSON lines from the game board (one JSON object per line)
 *
 * WIRING (3.3 V logic, common GND)
 *   RP2040 UART TX  → ESP32 RX  (see tekken_mini.ino PIN_SERIAL1_TX)
 *   RP2040 UART RX  ← ESP32 TX  (optional: for future remote input)
 *   GND ↔ GND
 *
 * LIBRARIES (Arduino Library Manager)
 *   - WebSockets by Markus Sattler (Links2004)
 *
 * BOARD: ESP32 Dev Module (or your AITRIP module), Partition Scheme: default
 */

#include <WiFi.h>
#include <WebServer.h>
#include <WebSocketsServer.h>

// ---- WiFi mode -----------------------------------------------------------------
// Set to 1 to join your router instead of hosting an AP (fill STA_* below).
#ifndef WIFI_USE_STA
#define WIFI_USE_STA 0
#endif

#define AP_SSID     "TekkenMini"
#define AP_PASSWORD "tekken123"

#if WIFI_USE_STA
#define STA_SSID     "YOUR_SSID"
#define STA_PASSWORD "YOUR_PASSWORD"
#endif

// UART to RP2040 — GPIO16 = RX2, GPIO17 = TX2 on many ESP32 modules (swap if needed)
#define SERIAL_GAME_BAUD 115200
#define PIN_RX2 16
#define PIN_TX2 17

WebServer server(80);
WebSocketsServer webSocket(81);

const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Tekken Mini — WiFi Display</title>
<style>
body{margin:0;background:#0a0e18;color:#eee;font-family:sans-serif;text-align:center}
#c{background:#111;border:2px solid #444;max-width:100%;touch-action:none}
#s{font-size:12px;color:#888;margin:6px}
</style></head>
<body>
<h2>Tekken Mini</h2>
<canvas id="c" width="320" height="256"></canvas>
<p id="s">Connecting…</p>
<script>
const c=document.getElementById('c');
const x=c.getContext('2d');
const s=document.getElementById('s');
const W=160,H=128,scale=2;
let host=location.hostname||'192.168.4.1';
let ws;
function line(msg){
  try{
    const d=JSON.parse(msg);
    if(d.t!=='frame')return;
    x.fillStyle='#0a0e18';
    x.fillRect(0,0,c.width,c.height);
    x.save();
    x.scale(scale,scale);
    x.fillStyle='#222';
    x.fillRect(0,0,W,H);
    if(d.st===0){
      x.fillStyle='#ffd700';
      x.font='10px sans-serif';
      x.fillText('MENU — start game on cabinet',8,60);
      s.textContent='Menu';
      x.restore();
      return;
    }
    x.fillStyle='#400';
    x.fillRect(4,4,W-8,8);
    const hw=W-8;
    x.fillStyle='#080';
    x.fillRect(4,4,Math.max(0,Math.round(hw*d.p1.hp/100)),8);
    x.fillStyle='#800';
    x.fillRect(4+hw-Math.max(0,Math.round(hw*d.p2.hp/100)),4,Math.max(0,Math.round(hw*d.p2.hp/100)),8);
    x.fillStyle='#4af';
    x.fillRect(d.p1.x|0,d.p1.y|0,10,d.p1.h|20);
    x.fillStyle='#f44';
    x.fillRect(d.p2.x|0,d.p2.y|0,10,d.p2.h|20);
    x.fillStyle='#fff';
    x.font='8px monospace';
    x.fillText('R'+d.rn+' W'+d.w1+'-'+d.w2+' st'+d.st,4,H-6);
    s.textContent='Frame OK';
    x.restore();
  }catch(e){s.textContent='Bad frame: '+e;}
}
function connect(){
  ws=new WebSocket('ws://'+host+':81/');
  ws.onopen=()=>{s.textContent='WebSocket open';};
  ws.onclose=()=>{s.textContent='Reconnecting…';setTimeout(connect,2000);};
  ws.onerror=()=>{};
  ws.onmessage=(ev)=>line(ev.data);
}
connect();
</script>
</body></html>
)rawliteral";

void handleRoot() {
  server.send(200, "text/html", INDEX_HTML);
}

void webSocketEvent(uint8_t num, WStype_t type, uint8_t* payload, size_t length) {
  (void)num;
  (void)payload;
  (void)length;
  if (type == WStype_CONNECTED) {
    Serial.println("[ws] client connected");
  } else if (type == WStype_DISCONNECTED) {
    Serial.println("[ws] client disconnected");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("esp32_wifi_display starting");

  Serial2.begin(SERIAL_GAME_BAUD, SERIAL_8N1, PIN_RX2, PIN_TX2);

#if WIFI_USE_STA
  WiFi.mode(WIFI_STA);
  WiFi.begin(STA_SSID, STA_PASSWORD);
  Serial.print("Connecting STA ");
  Serial.println(STA_SSID);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("STA failed, starting AP fallback");
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASSWORD);
    Serial.print("AP IP: ");
    Serial.println(WiFi.softAPIP());
  }
#else
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASSWORD);
  IPAddress ip = WiFi.softAPIP();
  Serial.print("AP SSID: ");
  Serial.println(AP_SSID);
  Serial.print("AP IP: ");
  Serial.println(ip);
#endif

  server.on("/", handleRoot);
  server.begin();

  webSocket.begin();
  webSocket.onEvent(webSocketEvent);
  Serial.println("HTTP :80  WebSocket :81");
}

static String readLineSerial2() {
  static char buf[384];
  static size_t len = 0;
  while (Serial2.available()) {
    char ch = (char)Serial2.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      if (len == 0) return String();
      buf[len] = '\0';
      String out(buf);
      len = 0;
      return out;
    }
    if (len < sizeof(buf) - 1) buf[len++] = ch;
  }
  return String();
}

void loop() {
  server.handleClient();
  webSocket.loop();

  String line = readLineSerial2();
  if (line.length() > 0) {
    webSocket.broadcastTXT(line.c_str());
    if (Serial.availableForWrite() > 0) {
      // USB debug: echo first 120 chars
      if (line.length() > 120) {
        Serial.println(line.substring(0, 120) + "…");
      } else {
        Serial.println(line);
      }
    }
  }
}
