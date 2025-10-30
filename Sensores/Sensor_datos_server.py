import time
import requests
import Adafruit_DHT
import RPi.GPIO as GPIO

#Instalar librerías (solo funcionan en la Raspberry Pi):
#sudo pip3 install Adafruit_DHT requests RPi.GPIO
#pip3 install Adafruit_DHT requests RPi.GPIO

# ==== CONFIGURACIÓN ====
DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN = 14              # Pin GPIO (no número físico del conector)
LED_PIN = 12              # Pin GPIO para LED indicador
SERVER_URL = "http://10.38.20.189:1880/esp32"   # Cambia por la IP de tu servidor Node-RED

# ==== CONFIGURAR GPIO ====
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

# ==== INICIO ====
print("DHT22 sensor is working")
print("Connecting to server Node-RED...")

while True:
    # === Leer sensor DHT22 ===
    humidity, temperature = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)

    if humidity is None or temperature is None:
        print("Failed to read from DHT22!")
        GPIO.output(LED_PIN, GPIO.LOW)
    else:
        print(f"Humidity: {humidity:.1f}%  Temperature: {temperature:.1f}°C")
        GPIO.output(LED_PIN, GPIO.HIGH)

        # === Preparar datos en formato JSON ===
        payload = {
            "temperature": temperature,
            "humidity": humidity
        }

        try:
            # === Enviar datos al servidor Node-RED ===
            response = requests.post(SERVER_URL, json=payload, timeout=5)

            if response.status_code == 200:
                print(f"POST Success ({response.status_code})")
                print(f"Server response: {response.text}")
            else:
                print(f"Server returned status {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"POST failed: {e}")

    time.sleep(3)  # Espera 3 segundos antes de la siguiente lectura
