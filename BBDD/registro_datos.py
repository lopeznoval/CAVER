import os
from database_SQLite import get_db_session, LecturaSensor, Imagen, crear_tablas

def registrar_lectura(temp, hum):
    """Inserta una nueva lectura de sensor en SQLite."""
    nueva_lectura = LecturaSensor(temperatura=temp, humedad=hum)
    session = get_db_session()
    try:
        session.add(nueva_lectura)
        session.commit()
        print(f"Datos de sensor registrados (SQLite): {temp}°C, {hum}%")
    except Exception as e:
        print(f"Error al registrar lectura: {e}")
        session.rollback()
    finally:
        session.close()

def registrar_imagen(ruta):
    """Inserta el registro de una nueva imagen en SQLite."""
    if not os.path.exists(ruta):
        print(f"Error: El archivo de imagen no existe en '{ruta}'")
        return

    nuevo_registro_imagen = Imagen(ruta_archivo=ruta)
    session = get_db_session()
    try:
        session.add(nuevo_registro_imagen)
        session.commit()
        print(f"Registro de imagen guardado (SQLite): {ruta}")
    except Exception as e:
        print(f"Error al registrar imagen: {e}")
        session.rollback()
    finally:
        session.close()

# --- Bloque principal para crear la DB y probar ---
if __name__ == "__main__":
    # 1. Esto crea el archivo 'robot_data_orm.db' y las tablas
    crear_tablas()
    
    # 2. Simulación: El robot toma una lectura
    registrar_lectura(25.1, 60.5)
    
    # 3. Simulación: El robot toma una foto
    ruta_foto_prueba = "/home/robot/fotos/mi_foto.jpg"
    os.makedirs(os.path.dirname(ruta_foto_prueba), exist_ok=True)
    with open(ruta_foto_prueba, "w") as f: f.write("test de imagen")
        
    registrar_imagen(ruta_foto_prueba)