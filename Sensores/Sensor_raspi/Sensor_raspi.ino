#include <DHT.h>
#include "Adafruit_Sensor.h"

#define DHTPIN 14
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);
const int ledPin = 12;

void setup() {
  Serial.begin(115200);
  pinMode(ledPin, OUTPUT);
  delay(5000);

  dht.begin();
}

void loop() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("❌ Failed to read from DHT22!");
  } else {
    Serial.print("Humidity:");
    Serial.print(h);
    Serial.print("%  ");
    Serial.print("Temperature:");
    Serial.print(t);
    Serial.println("°C");
    digitalWrite(ledPin, HIGH);
  }

  delay(3000);
}
