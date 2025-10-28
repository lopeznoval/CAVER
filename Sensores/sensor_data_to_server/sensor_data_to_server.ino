#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include "Adafruit_Sensor.h"

#define DHTPIN 14
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);
const int ledPin = 12;
const char* ssid = "Ordenador";
const char* password = "2j4891QU";

void setup() {
  Serial.begin(115200);
  pinMode(ledPin, OUTPUT);
  delay(5000);

  dht.begin();
  Serial.println("DHT22 sensor is working");
  Serial.println("Connecting to WiFi...");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int maxAttempts = 20;
  int attempt = 0;
  while (WiFi.status() != WL_CONNECTED && attempt < maxAttempts) {
    delay(500);
    Serial.print(".");
    attempt++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi connected.");
  } else {
    Serial.println("\n❌ Failed to connect to WiFi.");
  }

  Serial.println("setup done...");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi not connected. Skipping HTTP requests.");
    delay(3000);
    return;
  }

  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("❌ Failed to read from DHT22!");
  } else {
    Serial.print("Humidity: ");
    Serial.print(h);
    Serial.print("%  ");
    Serial.print("Temperature: ");
    Serial.print(t);
    Serial.println("°C");
    digitalWrite(ledPin, HIGH);
  }

  // === Receive data from server ===
  // HTTPClient http;
  // http.begin(" http://127.0.0.1:1880/data");  // Replace with your actual server IP
  // Serial.print("➡️ Connecting to server for GET... ");
  // int httpCode = http.GET();

  // if (httpCode > 0) {
  //   Serial.print("✅ Response code: ");
  //   Serial.println(httpCode);
  //   String response = http.getString();
  //   Serial.println(response);
  // } else {
  //   Serial.print("❌ GET failed, error: ");
  //   Serial.println(httpCode);
  // }
  // http.end();  // Clean up

  // === Send data to server ===
  HTTPClient postHttp;
  postHttp.begin("http://10.38.20.189:1880/esp32");  // Same or different endpoint
  postHttp.addHeader("Content-Type", "application/json");

  String payload = String("{\"temperature\":") + t + ",\"humidity\":" + h + "}";
  Serial.println(payload);
  int postCode = postHttp.POST(payload);

  if (postCode > 0) {
    Serial.print("✅ POST Success: ");
    Serial.println(postCode);
    Serial.print("Se envía: ");
    Serial.println(postHttp.getString());
  } else {
    Serial.print("❌ POST failed: ");
    Serial.println(postCode);
  }
  postHttp.end();

  delay(3000);
}
