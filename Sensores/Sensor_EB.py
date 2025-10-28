import serial
import time
import requests

lora_pc = serial.Serial('COM3', 115200, timeout=2)  # Ajusta el puerto
print("Estación base lista")

while True:
    comando = input("Comando (MEASURE/MOVE/...): ").strip()
    lora_pc.write((comando + "\n").encode('utf-8'))

    time.sleep(1)
    if lora_pc.in_waiting > 0:
        respuesta = lora_pc.readline().decode('utf-8').strip()
        print("Respuesta del robot:", respuesta)
        
    #Para enviarselo al servidor NODE-RED
    requests.post("http://localhost:1880/CAVER", json={"temp": 23.4, "hum": 56.1})
    #Con esto en la terminal funciona: curl -X POST http://localhost:1880/CAVER -H "Content-Type: application/json" -d '{"temperature":25,"humidity":60}'
