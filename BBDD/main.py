# main.py
import os
import base64
import uuid
from datetime import datetime
from typing import List
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import database_BS as db_bs  # Importamos nuestro módulo de DB de la BS

# --- Modelos Pydantic (para validación de datos de entrada) ---
#     Estos modelos definen lo que la API ESPERA recibir

class LecturaSensorBase(BaseModel):
    timestamp: datetime
    temperatura: float
    humedad: float

class ImagenBase(BaseModel):
    timestamp: datetime
    # Recibiremos la imagen como un string en Base64
    image_data_base64: str 
    # Guardamos el nombre original para referencia
    original_filename: str 

# --- Configuración de la App ---
app = FastAPI(title="Robot Base Station API")

# Directorio para guardar las imágenes recibidas
UPLOAD_DIR = "imagenes_recibidas"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Endpoints de la API ---

@app.post("/sync/lecturas")
def recibir_lecturas(
    lecturas: List[LecturaSensorBase], 
    db: Session = Depends(db_bs.get_db_session)
):
    """
    Endpoint para recibir un lote de lecturas de sensores.
    """
    try:
        print(f"Recibiendo {len(lecturas)} lecturas de sensores...")
        for data in lecturas:
            db_lectura = db_bs.LecturaSensor(
                timestamp=data.timestamp,
                temperatura=data.temperatura,
                humedad=data.humedad
            )
            db.add(db_lectura)
        
        db.commit()
        return {"status": "ok", "recibidas": len(lecturas)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync/imagenes")
def recibir_imagenes(
    imagenes: List[ImagenBase], 
    db: Session = Depends(db_bs.get_db_session)
):
    """
    Endpoint para recibir un lote de imágenes (en Base64).
    Las decodifica, las guarda en disco y almacena la ruta en la BD.
    """
    try:
        print(f"Recibiendo {len(imagenes)} imágenes...")
        nombres_archivos = []
        for data in imagenes:
            # Decodificar la imagen Base64
            try:
                img_data = base64.b64decode(data.image_data_base64)
            except Exception:
                print(f"Error decodificando imagen: {data.original_filename}")
                continue # Salta esta imagen y sigue con la siguiente

            # Generar un nombre de archivo único para la BS
            ext = os.path.splitext(data.original_filename)[1]
            nuevo_nombre = f"{uuid.uuid4()}{ext}"
            ruta_guardado = os.path.join(UPLOAD_DIR, nuevo_nombre)

            # Guardar la imagen en el disco de la BS
            with open(ruta_guardado, "wb") as f:
                f.write(img_data)
            
            # Guardar la referencia en la BD de la BS
            db_imagen = db_bs.Imagen(
                timestamp=data.timestamp,
                ruta_archivo=ruta_guardado 
            )
            db.add(db_imagen)
            nombres_archivos.append(ruta_guardado)
        
        db.commit()
        return {"status": "ok", "recibidas": len(nombres_archivos), "archivos": nombres_archivos}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"message": "Servidor de la Estación Base del Robot - Activo"}