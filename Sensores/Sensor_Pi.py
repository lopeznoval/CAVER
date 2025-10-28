import time
import Adafruit_DHT
import serial

# === Configuración del DHT22 ===
sensor = Adafruit_DHT.DHT22
pin = 4  # GPIO4

# === Configuración del LoRa HAT (ajusta el puerto según tu módulo) ===
lora = serial.Serial('/dev/ttyS0', 115200, timeout=1)  # o /dev/ttyAMA0

print("Robot de rescate iniciado. Esperando comandos LoRa...")

while True:
    if lora.in_waiting > 0:
        command = lora.readline().decode('utf-8').strip()
        print("Comando recibido:", command)

        if command.upper() == "MEASURE":
            humedad, temperatura = Adafruit_DHT.read_retry(sensor, pin)
            if humedad is not None and temperatura is not None:
                mensaje = f"TEMP:{temperatura:.1f},HUM:{humedad:.1f}"
                print("Enviando:", mensaje)
                lora.write((mensaje + "\n").encode('utf-8'))
            else:
                print("Error al leer DHT22")
                lora.write(b"ERROR_SENSOR\n")

    time.sleep(1)
