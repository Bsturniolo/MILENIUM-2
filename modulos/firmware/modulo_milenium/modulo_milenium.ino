/*
  Módulo Milenium 2 · firmware para ESP32 (Arduino)
  -------------------------------------------------
  ESTADO: escrito y revisado, PERO TODAVÍA NO PROBADO EN UNA PLACA REAL.
  Ver modulos/FALTA-PARTE-FISICA.md antes de conectarlo a una máquina.

  Qué hace:
  - Se conecta al Wi-Fi y al servidor de Milenium 2 por HTTPS.
  - Se vincula una sola vez con el código de 6 dígitos que muestra el sistema.
  - Cada 2 segundos pide órdenes. Solo obedece órdenes firmadas con su secreto,
    no vencidas y con número mayor a la última (una orden copiada no sirve).
  - Maneja su propio temporizador: si se corta internet, apaga igual a tiempo.
  - Avisa: inicio, fin, latido cada 30 s, uso sin pago y caja abierta.

  Configuración por el monitor serie (115200 baudios), una vez:
    wifi <red> <clave>
    servidor https://tu-servidor.com
    salida rele        (mantiene la máquina encendida el tiempo pagado)
    salida pulso       (da un pulso de "ficha" al empezar, para máquinas con monedero)
    vincular 123456
    estado
    borrar             (olvida todo; hay que volver a vincular)

  Bibliotecas: ArduinoJson 7 (Benoit Blanchon). El resto viene con el core ESP32.
*/
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <time.h>
#include "mbedtls/md.h"

// ---------------- pines (ajustar según la placa armada) ----------------
const int PIN_SALIDA = 26;      // al relé o al optoacoplador que da la ficha
const int PIN_EN_USO = 27;      // entrada aislada: LOW = la máquina está funcionando
const int PIN_TAPA = 14;        // microswitch de la caja: LOW = cerrada
const int PIN_LED = 2;

const char* VERSION_FW = "fw-0.1";
const unsigned long MAX_SEGUNDOS_LOCAL = 4UL * 3600UL;  // tope propio, diga lo que diga la orden
const unsigned long CADA_ORDENES_MS = 2000, CADA_LATIDO_MS = 30000, PULSO_MS = 200;

// Certificado raíz del servidor (PEM). Completar al tener el servidor en internet.
// Sin esto la conexión no es segura: NO usar setInsecure() en una máquina real.
const char* CA_RAIZ = R"PEM(
-----BEGIN CERTIFICATE-----
PEGAR_AQUI_EL_CERTIFICADO_RAIZ_DEL_SERVIDOR
-----END CERTIFICATE-----
)PEM";

Preferences prefs;
String wifiRed, wifiClave, servidor, moduloId, secreto, modoSalida = "rele";
long long ultimaOrden = 0, ultimoTs = 0;
bool encendido = false;
unsigned long apagaEnMs = 0, proxOrdenes = 0, proxLatido = 0, usoSinPagoDesde = 0, ultimaAlertaUso = 0;
bool tapaAvisada = false;

// ---------------- utilidades ----------------
String hex(const uint8_t* b, size_t n) {
  static const char* h = "0123456789abcdef"; String s; s.reserve(n * 2);
  for (size_t i = 0; i < n; i++) { s += h[b[i] >> 4]; s += h[b[i] & 15]; }
  return s;
}
bool desdeHex(const String& s, uint8_t* out, size_t n) {
  if (s.length() != n * 2) return false;
  for (size_t i = 0; i < n; i++) out[i] = strtoul(s.substring(i * 2, i * 2 + 2).c_str(), nullptr, 16);
  return true;
}
String sha256hex(const String& datos) {
  uint8_t r[32]; mbedtls_md(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), (const uint8_t*)datos.c_str(), datos.length(), r);
  return hex(r, 32);
}
String hmac(const String& mensaje) {
  uint8_t clave[32], r[32];
  if (!desdeHex(secreto, clave, 32)) return "";
  mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), clave, 32, (const uint8_t*)mensaje.c_str(), mensaje.length(), r);
  return hex(r, 32);
}
bool igualesSeguro(const String& a, const String& b) {  // comparación sin cortar antes (evita ataques de tiempo)
  if (a.length() != b.length()) return false;
  uint8_t d = 0; for (size_t i = 0; i < a.length(); i++) d |= a[i] ^ b[i];
  return d == 0;
}
long long ahoraMs() {  // hora real por NTP, en milisegundos, siempre creciente
  struct timeval tv; gettimeofday(&tv, nullptr);
  long long t = (long long)tv.tv_sec * 1000LL + tv.tv_usec / 1000;
  if (t <= ultimoTs) t = ultimoTs + 1;
  ultimoTs = t; return t;
}
void salida(bool on) {
  if (modoSalida == "pulso") {
    if (on) { digitalWrite(PIN_SALIDA, HIGH); delay(PULSO_MS); digitalWrite(PIN_SALIDA, LOW); }
  } else digitalWrite(PIN_SALIDA, on ? HIGH : LOW);
  digitalWrite(PIN_LED, on ? HIGH : LOW);
}

// ---------------- comunicación ----------------
int pedido(const char* metodo, const String& ruta, const String& cuerpo, String& respuesta, bool firmar = true) {
  if (WiFi.status() != WL_CONNECTED || servidor.isEmpty()) return -1;
  WiFiClientSecure cli; cli.setCACert(CA_RAIZ);
  HTTPClient http; http.setTimeout(8000);
  if (!http.begin(cli, servidor + ruta)) return -1;
  if (cuerpo.length()) http.addHeader("Content-Type", "application/json");
  if (firmar) {
    long long ts = ahoraMs();
    String tsS = String(ts);
    String firma = hmac(String(metodo) + "\n" + ruta + "\n" + tsS + "\n" + sha256hex(cuerpo));
    http.addHeader("X-Modulo", moduloId); http.addHeader("X-Ts", tsS); http.addHeader("X-Firma", firma);
  }
  int cod = strcmp(metodo, "GET") == 0 ? http.GET() : http.POST(cuerpo);
  respuesta = cod > 0 ? http.getString() : "";
  http.end();
  return cod;
}
void reportar(const char* tipo, long long ordenId = 0, long segundos = -1, const char* detalle = "") {
  JsonDocument d; d["tipo"] = tipo;
  if (ordenId) d["orden_id"] = ordenId;
  if (segundos >= 0) d["segundos_restantes"] = segundos;
  if (detalle[0]) d["detalle"] = detalle;
  String c, r; serializeJson(d, c);
  pedido("POST", "/modulo/reporte", c, r);
}

// ---------------- lógica ----------------
void apagar(const char* motivo) {
  if (!encendido) return;
  encendido = false; salida(false);
  reportar("fin", 0, -1, motivo);
}
void procesarOrdenes(const String& json) {
  JsonDocument d; if (deserializeJson(d, json)) return;
  long long ahoraServidor = d["ahora_ms"] | 0LL;
  for (JsonObject o : d["ordenes"].as<JsonArray>()) {
    long long id = o["id"] | 0LL; String accion = o["accion"] | ""; long seg = o["segundos"] | 0L;
    long long expira = o["expira_ms"] | 0LL; String firma = o["firma"] | "";
    String esperada = hmac(String((long)id) + "|" + accion + "|" + String(seg) + "|" + String(expira));
    if (!igualesSeguro(firma, esperada) || id <= ultimaOrden || expira < ahoraServidor) continue;  // orden falsa, repetida o vencida
    ultimaOrden = id; prefs.putLong64("ultimaOrden", ultimaOrden);
    reportar("confirmacion", id);
    if (accion == "activar") {
      unsigned long s = min((unsigned long)seg, MAX_SEGUNDOS_LOCAL);
      encendido = true; apagaEnMs = millis() + s * 1000UL; salida(true);
      reportar("inicio", id, s);
    } else if (accion == "detener") apagar("detenido desde el sistema");
  }
}
void vigilarEntradas() {
  // Uso sin pago: la máquina funciona más de 10 s sin que el módulo la haya habilitado.
  bool enUso = digitalRead(PIN_EN_USO) == LOW;
  if (enUso && !encendido) {
    if (!usoSinPagoDesde) usoSinPagoDesde = millis();
    if (millis() - usoSinPagoDesde > 10000 && millis() - ultimaAlertaUso > 300000) { reportar("uso_sin_pago"); ultimaAlertaUso = millis(); }
  } else usoSinPagoDesde = 0;
  // Caja abierta
  bool abierta = digitalRead(PIN_TAPA) == HIGH;
  if (abierta && !tapaAvisada) { reportar("tapa_abierta"); tapaAvisada = true; }
  if (!abierta) tapaAvisada = false;
}

// ---------------- configuración por serie ----------------
void guardar() {
  prefs.putString("wifiRed", wifiRed); prefs.putString("wifiClave", wifiClave); prefs.putString("servidor", servidor);
  prefs.putString("moduloId", moduloId); prefs.putString("secreto", secreto); prefs.putString("salida", modoSalida);
}
void comandoSerie(String l) {
  l.trim(); int e = l.indexOf(' '); String cmd = e < 0 ? l : l.substring(0, e), arg = e < 0 ? "" : l.substring(e + 1);
  if (cmd == "wifi") { int s = arg.indexOf(' '); wifiRed = arg.substring(0, s); wifiClave = s < 0 ? "" : arg.substring(s + 1); guardar(); WiFi.begin(wifiRed.c_str(), wifiClave.c_str()); Serial.println("Wi-Fi guardado"); }
  else if (cmd == "servidor") { servidor = arg; guardar(); Serial.println("Servidor guardado"); }
  else if (cmd == "salida" && (arg == "rele" || arg == "pulso")) { modoSalida = arg; guardar(); Serial.println("Salida: " + arg); }
  else if (cmd == "vincular") {
    String r; int cod = pedido("POST", "/modulo/vincular", "{\"codigo\":\"" + arg + "\",\"firmware\":\"" + VERSION_FW + "\"}", r, false);
    JsonDocument d;
    if (cod == 200 && !deserializeJson(d, r)) {
      moduloId = d["modulo_id"].as<String>(); secreto = d["secreto"].as<String>(); ultimaOrden = 0;
      prefs.putLong64("ultimaOrden", 0); guardar(); reportar("reinicio", 0, -1, "vinculado");
      Serial.println("Vinculado como " + moduloId);
    } else Serial.println("No se pudo vincular (codigo " + String(cod) + "): revisá el código, que no esté vencido, y la conexión");
  }
  else if (cmd == "estado") Serial.printf("wifi=%s servidor=%s modulo=%s salida=%s encendido=%d\n", WiFi.status() == WL_CONNECTED ? "ok" : "no", servidor.c_str(), moduloId.c_str(), modoSalida.c_str(), encendido);
  else if (cmd == "borrar") { prefs.clear(); ESP.restart(); }
  else Serial.println("Comandos: wifi <red> <clave> | servidor <url> | salida rele|pulso | vincular <codigo> | estado | borrar");
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SALIDA, OUTPUT); digitalWrite(PIN_SALIDA, LOW);  // siempre arranca apagado
  pinMode(PIN_LED, OUTPUT); pinMode(PIN_EN_USO, INPUT_PULLUP); pinMode(PIN_TAPA, INPUT_PULLUP);
  prefs.begin("milenium", false);
  wifiRed = prefs.getString("wifiRed", ""); wifiClave = prefs.getString("wifiClave", ""); servidor = prefs.getString("servidor", "");
  moduloId = prefs.getString("moduloId", ""); secreto = prefs.getString("secreto", ""); modoSalida = prefs.getString("salida", "rele");
  ultimaOrden = prefs.getLong64("ultimaOrden", 0);
  if (wifiRed.length()) WiFi.begin(wifiRed.c_str(), wifiClave.c_str());
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  Serial.println("Módulo Milenium " + String(VERSION_FW) + ". Escribí 'estado' para ver la configuración.");
}

void loop() {
  if (Serial.available()) comandoSerie(Serial.readStringUntil('\n'));
  // El temporizador local manda, haya o no internet.
  if (encendido && (long)(millis() - apagaEnMs) >= 0) apagar("terminó el tiempo pagado");
  if (moduloId.isEmpty() || WiFi.status() != WL_CONNECTED || time(nullptr) < 1700000000) { delay(50); return; }
  static bool avisoArranque = false;
  if (!avisoArranque) { reportar("reinicio", 0, -1, "arranque"); avisoArranque = true; }
  vigilarEntradas();
  if (millis() >= proxOrdenes) {
    proxOrdenes = millis() + CADA_ORDENES_MS;
    String r; if (pedido("GET", "/modulo/ordenes", "", r) == 200) procesarOrdenes(r);
  }
  if (millis() >= proxLatido) { proxLatido = millis() + CADA_LATIDO_MS; reportar("latido"); }
  delay(20);
}
