# lora_bridge.py (Versión MongoDB)
from os import error
import serial
import json
import time
from pymongo import MongoClient

# --- Configuración ---
SERIAL_PORT = "/dev/ttyS0" 
BAUD_RATE = 9600

# Conectar a MongoDB (¡Así de simple!)
# Si la DB o la colección no existen, se crearán al usarlas.
sensores_collection = None

def connect_mongo():
    try:
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
        db = client["CAVER_db"]
        sensores_collection = db["lecturas_sensores"] # Selecciona la "tabla"
        print("Conectado a MongoDB (localhost:27017)")
    except Exception as e:
        print(f"Error al conectar a MongoDB: {e}")
        exit()

def procesar_paquete_lora(json_str):      #cambiar para que se reciban todos los json, entonces hacer strip y analizar cada uno
    """Procesa un paquete JSON recibido vía LoRa."""
    try:
        data = json.loads(json_str)   # convertir el string a dict
        error_found = False
        for linea_json in data["lecturas"]:
            data = json.loads(linea_json)
            
            if data.get("type") == "sensor":
                # 1. Preparamos el documento para MongoDB
                #    (Convertimos el timestamp a un objeto datetime)
                from datetime import datetime
                documento = {
                    "ID_robot": data["ir"],
                    "timestamp": datetime.fromisoformat(data["ts"]),
                    "temperatura": data["temp"],
                    "humedad": data["hum"]
                }

                # 2. Insertar directamente en MongoDB
                try:
                    sensores_collection.insert_one(documento)
                    print(f"Dato de sensor guardado en MongoDB.")
                    error_found = False
                except Exception as e:
                    print(f"Error al guardar en MongoDB: {e}")
                    error_found = True
                    break
            else:
                error_found = True
                break

        if error_found == False:
            return b"ACK\n"
        else:
            return b"NACK\n"
        
    except Exception as e:
        print(f"Error procesando paquete: {e}")
        return b"NACK\n"

def iniciar_escucha_lora():
    """Bucle principal que escucha datos del módulo LoRa."""
    print("Iniciando puente LoRa <-> API...")
    while True:
        try:
            # Conectar al puerto serie
            with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=None) as ser:
                print(f"Escuchando en {SERIAL_PORT}...")
                while True:
                    linea_bytes = ser.readline()
                    if not linea_bytes:
                        continue
                        
                    linea_str = linea_bytes.decode('utf-8').strip()
                    
                    if linea_str:
                        print(f"Paquete LoRa recibido: {linea_str}")
                        procesar_paquete_lora(linea_str)
                        
        except serial.SerialException as e:
            print(f"Error de conexión en {SERIAL_PORT}: {e}")
            print("Reintentando en 10 segundos...")
            time.sleep(10)
        except KeyboardInterrupt:
            print("Cerrando puente LoRa.")
            break