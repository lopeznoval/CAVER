import os
import threading
import time
import random
from BBDDv1.database_SQLite import get_db_session, LecturaSensor, Video, crear_tablas

def registrar_lectura(temp, hum, sess):
    """Inserta una nueva lectura de sensor en SQLite."""
    try:
        nueva_lectura = LecturaSensor(temperatura=temp, humedad=hum)
        sess.add(nueva_lectura)
        sess.commit()
        print(f"Datos de sensor registrados (SQLite): {temp:.2f}°C, {hum:.2f}%")
    except Exception as e:
        print(f"Error al registrar lectura: {e}")
        sess.rollback()

def registrar_video(ruta):
    """Inserta el registro de un nuevo video en SQLite."""
    if not os.path.exists(ruta):
        print(f"Error: El archivo de video no existe en '{ruta}'")
        return

    nuevo_registro_video = Video(ruta_archivo=ruta)
    session = get_db_session()
    try:
        session.add(nuevo_registro_video)
        session.commit()
        print(f"Registro de video guardado (SQLite): {ruta}")
    except Exception as e:
        print(f"Error al registrar video: {e}")
        session.rollback()
    finally:
        session.close()

def bucle_lectura_sensores():
    """
    Esta función se ejecuta en un hilo separado.
    Toma lecturas de sensores cada 5 segundos.
    """
    print(f"(Hilo Sensor) Hilo iniciado. Tomando lecturas cada 5 segundos.")
    while True:
        try:
            # 1. Leer del sensor
            temperatura, humedad = leer_sensor_simulado()
            
            # 2. Registrar en la base de datos
            registrar_lectura(temperatura, humedad)
            
            # 3. Esperar para la siguiente lectura
            time.sleep(5)
            
        except Exception as e:
            print(f"(Hilo Sensor) Error en el bucle: {e}")
            time.sleep(10) # Esperar más si hay un error

def leer_sensor_simulado():
    """
    Simula una función que tarda tiempo en leer un sensor 
    y devuelve temperatura y humedad.
    """
    # print("  (Hilo Sensor) Leyendo sensor...") # Comentado para no saturar la consola
    time.sleep(1) # Simula que la lectura tarda 1 segundo
    temp = random.uniform(20.0, 30.0)
    hum = random.uniform(40.0, 60.0)
    return temp, hum

# --- Bloque principal para crear la DB y probar ---
if __name__ == "__main__":
    # 1. Esto crea el archivo 'robot_data_orm.db' y las tablas la primera vez
    print("(Hilo Principal) Creando tablas si no existen...")
    crear_tablas()
    
    # 2. Iniciar el hilo de lectura de sensores en segundo plano
    print("(Hilo Principal) Iniciando el hilo de lectura de sensores...")
    # Usamos daemon=True para que el hilo termine automáticamente
    # cuando el hilo principal (este script) se detenga.
    sensor_thread = threading.Thread(target=bucle_lectura_sensores, daemon=True)
    sensor_thread.start()
    
    # 3. Simulación: El hilo principal hace otras tareas
    print("(Hilo Principal) El hilo principal está libre y puede hacer otras tareas.")
    time.sleep(2) # Esperar un poco
    
    # # Simular la grabación de un video
    # print("(Hilo Principal) Tarea: Grabar un video...")
    # ruta_video_prueba = "/home/robot/videos/mi_video_01.mp4"
    
    # # Asegurarse de que el directorio exista (ignorar error si ya existe)
    # os.makedirs(os.path.dirname(ruta_video_prueba), exist_ok=True)
    
    # try:
    #     # Simular la creación del archivo de video
    #     with open(ruta_video_prueba, "w") as f:
    #         f.write("simulacion de datos de video .mp4")
        
    #     # CAMBIO: Registrar el video en la BD
    #     registrar_video(ruta_video_prueba)
    # except (IOError, OSError) as e:
    #     # CAMBIO: Actualizamos el mensaje
    #     print(f"(Hilo Principal) No se pudo crear el archivo de video de prueba (ignorado): {e}")

    
    # 4. Mantener el hilo principal vivo
    print("\n(Hilo Principal) Tareas completadas. El robot está en modo de espera.")
    print("Las lecturas de sensores continúan en segundo plano.")
    print("Presiona Ctrl+C para detener el programa.")
    try:
        while True:
            # El hilo principal puede dormir o hacer comprobaciones de bajo nivel
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n(Hilo Principal) Deteniendo el robot. ¡Adiós!")