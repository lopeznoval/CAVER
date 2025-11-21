#include <DHT.h>
#include "Adafruit_Sensor.h"

#define DHTPIN 14
#define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);
const int ledPin = 12;
const int LDRPin = 34; // Pin de la Foto Resistencia

int ValorSensorLuz = 0; 
int UmbralLuz = 2000;

bool ledState = false; //Estado actual del led
bool modoAuto = false; //Modo automático para encender la luz

void setup() {
  Serial.begin(115200);
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW); //Led inicialmente apagado
  delay(5000);

  dht.begin();
}

void loop() {
  // Comprobar si hay datos disponibles por el puerto serie
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // Quita espacios y saltos de línea

    if (command.equalsIgnoreCase("ON")) {
      modoAuto = false;
      ledState = true;
      digitalWrite(ledPin, HIGH);
      Serial.println("💡 LED encendido");
    } else if (command.equalsIgnoreCase("OFF")) {
      modoAuto = false;
      ledState = false;
      digitalWrite(ledPin, LOW);
      Serial.println("💤 LED apagado");
    } else if (command.equalsIgnoreCase("AUTO")) {
      modoAuto = true;
    } else {
      Serial.println("⚠️ Comando no reconocido. Usa 'ON' o 'OFF'.");
    }
  }

  // Detectar luminosidad
  if (modoAuto){
      // Valores de luminosidad medidos por la Foto Resistencia
      ValorSensorLuz = analogRead(LDRPin);
      Serial.println(ValorSensorLuz);
      if (ValorSensorLuz < UmbralLuz){
        digitalWrite(ledPin, HIGH);
      } else {
        digitalWrite(ledPin, LOW);
      }
  }

  // Leer temperatura y humedad
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
  }

  delay(3000);
}
