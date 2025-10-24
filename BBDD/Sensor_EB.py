import serial
import time
import requests
from datetime import datetime
from database import Session, Medicion

#Para guardar los datos en la Base de datos
def guardar_datos(t, h, p):
    session = Session()
    medicion = Medicion(temperatura=t, humedad=h, presion=p)
    session.add(medicion)
    session.commit()
    session.close()

#Parámetros ESP32
Puerto = '/dev/ttyUSB0'
BAU = 115200

#Parámetros Servidor NODE-RED
SERVER_URL = "http://10.38.9.114:1880/CAVER"   # Cambia por la IP de tu servidor Node-RED
#Para monitorizar los valores de temperatura y humedad poner en el buscador: http://10.38.9.114:1880/ui

ser = serial.Serial(Puerto, BAU, timeout=2)  # Ajusta el puerto
time.sleep(2)  # Espera a que el puerto inicialice

print("Leyendo datos del ESP32...\n")

while True:
    try:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            if line.startswith("H") and "T" in line:
                # Ejemplo de línea:Humidity:72% Temperature:21ºC
                parts = line.split()
                hum = float(parts[0].split(':')[1].replace('%',''))
                temp = float(parts[1].split(':')[1].replace('°C',''))
                #print(f"Temperatura: {temp:.1f}°C  |  Humedad: {hum:.1f}%")

                #Guardar datos en la BBDD
                guardar_datos(temp, hum, p=10)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"T={temp}°C  H={hum}% → guardado en MySQL.")

                #Envio a NODE-RED
                payload = {
                    "temperature": temp,
                    "humidity": hum
                }
                try: 
                    response = requests.post(SERVER_URL, json=payload, timeout=2)
                    if response.status_code == 200:
                        print("Datos enviados a Node-RED")
                    else:
                        print(f"Error Node-RED: {response.status_code}")
                except requests.exceptions.RequestException as e:
                    print("Error leyendo el ESP32:", e)
    
    except Exception as e:
        print("Error leyendo el ESP32:", e)