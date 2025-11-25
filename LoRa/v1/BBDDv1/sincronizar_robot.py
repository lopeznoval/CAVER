import os
import serial
import json
import time
import requests
from sqlalchemy.orm import sessionmaker
from BBDDv1.database_SQLite import get_db_session, LecturaSensor, Video

# --- Configuración de Conexiones ---
SERIAL_PORT = "/dev/ttyUSB0" 
BAUD_RATE = 9600
ACK_TIMEOUT_SEC = 5

# IMPORTANTE: IP de la Estación Base en la red Wi-Fi
BS_API_URL = "http://192.168.1.100:8000" 

# --- Lógica de Sincronización LoRa (Solo Sensores) ---
def sincronizar_sensores_lora(lora, session):
    """Envía lecturas de sensores pendientes vía LoRa."""
    lecturas_pendientes = session.query(LecturaSensor).filter(LecturaSensor.sincronizado == False).all()
    
    if not lecturas_pendientes:
        print("(LoRa) No hay nuevas lecturas de sensores para sincronizar.")
        return
    
    print(f"(LoRa) Iniciando envío de {len(lecturas_pendientes)} lecturas...")
    for lectura in lecturas_pendientes:
        payload = {
            "type": "sensor",
            "ir": lectura.robot_id,
            "ts": lectura.timestamp.isoformat(),
            "temp": lectura.temperatura,
            "hum": lectura.humedad
        }
        packet_str = json.dumps(payload)
        packet_bytes = (packet_str + '\n').encode('utf-8')
        
        # try:
        #     lora.send_message(0xFFFF, 1, 0, packet_str)
        #     ack = lora.readline().decode('utf-8').strip()
            
        #     if ack == "ACK":
        #         print("(LoRa) ACK recibido. Borrando lectura local.")
        #         session.delete(lectura) # <-- CAMBIO: Borrar en lugar de marcar
        #         session.commit()
        #     elif ack == "NACK":
        #         print("(LoRa) NACK recibido. El servidor no pudo guardar. Reintentando más tarde.")
        #         session.rollback()
        #         break
        #     else:
        #         print("(LoRa) Error: No se recibió ACK (timeout). Reintentando más tarde.")
        #         session.rollback()
        #         break
        #     time.sleep(1) # Pausa entre envíos
        # except Exception as e:
        #     print(f"(LoRa) Error de comunicación serial: {e}")
        #     session.rollback()
        #     break

# --- Lógica de Sincronización Wi-Fi (Solo Videos) ---

def check_wifi_connection(base_url):
    """Comprueba si hay conexión con el servidor de la Estación Base."""
    try:
        response = requests.get(base_url, timeout=3)
        if response.status_code == 200:
            print(f"(Wi-Fi) Conexión con la Estación Base ({base_url}) exitosa.")
            return True
        return False
    except requests.exceptions.RequestException:
        print("(Wi-Fi) No se pudo conectar con la Estación Base.")
        return False

def sincronizar_videos_wifi(session, base_url):
    """Envía videos pendientes vía Wi-Fi/HTTP."""
    videos_pendientes = session.query(Video).filter(Video.sincronizado == False).all()

    if not videos_pendientes:
        print("(Wi-Fi) No hay videos nuevos para sincronizar.")
        return

    print(f"(Wi-Fi) Iniciando subida de {len(videos_pendientes)} videos...")
    
    for video in videos_pendientes:
        if not os.path.exists(video.ruta_archivo):
            print(f"(Wi-Fi) Error: Archivo de video no encontrado: {video.ruta_archivo}. Saltando.")
            continue

        print(f"(Wi-Fi) Subiendo {video.ruta_archivo}...")
        
        try:
            # Preparamos el archivo para la subida 'multipart/form-data'
            with open(video.ruta_archivo, 'rb') as f:
                files = {'file': (os.path.basename(video.ruta_archivo), f, 'video/mp4')}
                data = {'timestamp': video.timestamp.isoformat()}
                
                # Enviamos el archivo y los datos del formulario
                response = requests.post(f"{base_url}/sync/video", files=files, data=data, timeout=300) # Timeout 5 min

            if response.status_code == 200:
                print("(Wi-Fi) Subida exitosa. Borrando video local.")
                # 1. Borrar el registro de la BD
                session.delete(video)
                # 2. Borrar el archivo físico
                os.remove(video.ruta_archivo)
                session.commit()
            else:
                print(f"(Wi-Fi) Error del servidor al subir video: {response.status_code} - {response.text}")
                session.rollback()
                break # Reintentar más tarde

        except requests.exceptions.RequestException as e:
            print(f"(Wi-Fi) Error de red al subir video: {e}")
            session.rollback()
            break
        except Exception as e:
            print(f"(Wi-Fi) Error inesperado al procesar video {video.ruta_archivo}: {e}")
            session.rollback()
            break

# --- Ejecución Principal ---
def bucle_sincro():
    print("--- Iniciando ciclo de sincronización dual ---")
    session = get_db_session()
    
    # 1. Sincronizar Sensores (LoRa)
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=ACK_TIMEOUT_SEC) as ser:
            print(f"(LoRa) Conectado a {SERIAL_PORT}")
            time.sleep(2)
            sincronizar_sensores_lora(ser, session)
    except serial.SerialException as e:
        print(f"(LoRa) No se pudo conectar al puerto {SERIAL_PORT}. Saltando sincronización de sensores.")
        print(f"  Error: {e}")

    # 2. Sincronizar Videos (Wi-Fi)
    if check_wifi_connection(BS_API_URL):
        sincronizar_videos_wifi(session, BS_API_URL)
    else:
        print("(Wi-Fi) Red no disponible. Saltando sincronización de videos.")

    session.close()
    print("--- Ciclo de sincronización finalizado ---")
