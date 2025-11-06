# sincronizar_lora.py
import serial
import json
import time
from sqlalchemy.orm import sessionmaker
from database_SQLite import get_db_session, LecturaSensor, Imagen

# --- Configuración ---

SERIAL_PORT = "/dev/ttyUSB0" 
BAUD_RATE = 9600
ACK_TIMEOUT_SEC = 5

def inicializar_serial():
    """Intenta conectar al puerto serie."""
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=ACK_TIMEOUT_SEC)
        print(f"Conectado a LoRa en {SERIAL_PORT}")
        time.sleep(2) # Esperar a que el módulo LoRa se inicialice
        return ser
    except serial.SerialException as e:
        print(f"Error: No se puede abrir el puerto {SERIAL_PORT}: {e}")
        return None

def sincronizar_lecturas_lora(ser, session):
    """
    Obtiene lecturas pendientes y las envía una por una vía LoRa,
    esperando confirmación (ACK) antes de borrarla.
    """
    lecturas_pendientes = session.query(LecturaSensor).filter(LecturaSensor.sincronizado == False).all()
    
    if not lecturas_pendientes:
        print("No hay nuevas lecturas de sensores para sincronizar.")
        return

    print(f"Iniciando envío de {len(lecturas_pendientes)} lecturas por LoRa...")
    
    for lectura in lecturas_pendientes:
        # 1. Preparar el paquete de datos (JSON)
        payload = {
            "type": "sensor", # Para futura expansión (ej. "imagen_chunk")
            "ts": lectura.timestamp.isoformat(),
            "temp": lectura.temperatura,
            "hum": lectura.humedad
        }
        
        # Convertir a string JSON y luego a bytes, añadiendo un newline
        packet_str = json.dumps(payload)
        packet_bytes = (packet_str + '\n').encode('utf-8')
        
        if len(packet_bytes) > 250: # Límite de seguridad de LoRa
            print(f"Error: El paquete de datos es demasiado grande ({len(packet_bytes)} bytes). Saltando.")
            continue
            
        try:
            # 2. Enviar datos por LoRa
            print(f"Enviando: {packet_str}")
            ser.write(packet_bytes)
            
            # 3. Esperar ACK de la Estación Base
            ack = ser.readline().decode('utf-8').strip()
            
            if ack == "ACK":
                # 4. Éxito: El servidor guardó el dato. Lo borramos localmente.
                print("ACK recibido. Borrando lectura local.")
                session.delete(lectura)
                session.commit()
            elif ack == "NACK":
                # El servidor lo recibió pero no pudo guardarlo
                print("NACK recibido. El servidor no pudo guardar el dato. Reintentando más tarde.")
                session.rollback()
                break # Dejar de enviar por ahora
            else:
                # Timeout o respuesta corrupta
                print("Error: No se recibió ACK (timeout o respuesta inválida). Reintentando más tarde.")
                session.rollback()
                break # Dejar de enviar por ahora

            # Respetar el "duty cycle" de LoRa (muy importante)
            time.sleep(2) # Pausa entre envíos
            
        except serial.SerialException as e:
            print(f"Error de comunicación serial: {e}")
            session.rollback()
            break # Salir del bucle si falla la comunicación
        except Exception as e:
            print(f"Error inesperado: {e}")
            session.rollback()
            break

def sincronizar_imagenes_lora(ser, session):
    """Función de advertencia sobre la inviabilidad de enviar imágenes."""
    imagenes_pendientes = session.query(Imagen).filter(Imagen.sincronizado == False).count()
    if imagenes_pendientes > 0:
        print(f"ADVERTENCIA: Hay {imagenes_pendientes} imágenes pendientes.")
        print("El envío de imágenes completas por LoRa no es viable debido al tamaño.")
        print("Esta función no intentará enviarlas.")
        # Aquí iría la lógica compleja de fragmentación si se implementase.
        pass

# --- Ejecución Principal ---
def main():
    ser = inicializar_serial()
    if not ser:
        return # Salir si no hay conexión LoRa
    
    session = get_db_session()
    
    try:
        sincronizar_lecturas_lora(ser, session)
        sincronizar_imagenes_lora(ser, session) # Imprimirá la advertencia
    finally:
        session.close()
        ser.close()
        print("Sincronización LoRa finalizada. Puerto cerrado.")

if __name__ == "__main__":
    main()