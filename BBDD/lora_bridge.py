# lora_bridge.py
import serial
import json
import requests
import time

# --- Configuración ---
# Puerto serie donde está el módulo LoRa RECEPTOR en la Estación Base
SERIAL_PORT = "/dev/ttyS0" 
BAUD_RATE = 9600
# URL del servidor FastAPI
API_URL = "http://127.0.0.1:8000/sync/lecturas"

def procesar_paquete_lora(linea_json, ser):
    """
    Intenta decodificar el JSON, enviarlo al servidor FastAPI
    y enviar un ACK/NACK de vuelta al robot.
    """
    try:
        data = json.loads(linea_json)
        
        # Validar que es un paquete de sensor
        if data.get("type") == "sensor" and "ts" in data and "temp" in data and "hum" in data:
            
            # El servidor FastAPI espera una lista de lecturas
            payload = [{
                "timestamp": data["ts"],
                "temperatura": data["temp"],
                "humedad": data["hum"]
            }]
            
            # Enviar los datos al servidor FastAPI local
            try:
                response = requests.post(API_URL, json=payload, timeout=5)
                
                if response.status_code == 200:
                    print(f"Datos guardados en BD: {payload}")
                    # Enviar ACK al robot
                    ser.write(b"ACK\n")
                else:
                    # El servidor FastAPI falló
                    print(f"Error del servidor API: {response.status_code} {response.text}")
                    ser.write(b"NACK\n") # NACK = Negative Acknowledge
                    
            except requests.exceptions.RequestException as e:
                print(f"Error: No se puede conectar al servidor API local: {e}")
                ser.write(b"NACK\n")
                
        else:
            print(f"Paquete JSON no reconocido: {linea_json}")
            
    except json.JSONDecodeError:
        print(f"Error: Paquete LoRa corrupto (no es JSON): {linea_json}")
    except Exception as e:
        print(f"Error procesando paquete: {e}")

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
                        procesar_paquete_lora(linea_str, ser)
                        
        except serial.SerialException as e:
            print(f"Error de conexión en {SERIAL_PORT}: {e}")
            print("Reintentando en 10 segundos...")
            time.sleep(10)
        except KeyboardInterrupt:
            print("Cerrando puente LoRa.")
            break

if __name__ == "__main__":
    iniciar_escucha_lora()