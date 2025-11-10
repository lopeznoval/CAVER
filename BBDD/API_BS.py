import os
import uuid
import shutil
from datetime import datetime
from typing import List
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
import database_BS as db_bs

# --- Modelos Pydantic (para validación de JSON) ---
class LecturaSensorBase(BaseModel):
    timestamp: datetime
    temperatura: float
    humedad: float

# --- Configuración de la App ---
app = FastAPI(title="Robot Base Station API")

# Directorio para guardar los videos recibidos
UPLOAD_DIR = "videos_recibidos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Endpoints de la API ---

@app.get("/")
def root():
    """Endpoint para que el robot compruebe la conexión Wi-Fi."""
    return {"message": "Servidor de la Estación Base del Robot - Activo"}

@app.post("/sync/lecturas")
def recibir_lecturas(
    lecturas: List[LecturaSensorBase], 
    db: Session = Depends(db_bs.get_db_session)
):
    """
    Endpoint para recibir un lote de lecturas de sensores (desde lora_bridge.py).
    """
    try:
        # print(f"Recibiendo {len(lecturas)} lecturas de sensores...")
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

@app.post("/sync/video")
async def recibir_video(
    db: Session = Depends(db_bs.get_db_session),
    # El timestamp se envía como parte del formulario (data)
    timestamp: datetime = Form(...), 
    # El archivo se envía como 'file'
    file: UploadFile = File(...) 
):
    """
    Endpoint para recibir UN video (subido como multipart/form-data).
    """
    try:
        # Generar un nombre de archivo único para la BS
        ext = os.path.splitext(file.filename)[1]
        if not ext:
            ext = ".mp4" # Extensión por defecto
        
        nuevo_nombre = f"{uuid.uuid4()}{ext}"
        ruta_guardado = os.path.join(UPLOAD_DIR, nuevo_nombre)

        print(f"Recibiendo video: {file.filename} -> Guardando como: {ruta_guardado}")

        # Guardar el archivo en el disco de la BS de forma eficiente
        with open(ruta_guardado, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Guardar la referencia en la BD de la BS
        db_video = db_bs.Video(
            timestamp=timestamp,
            ruta_archivo=ruta_guardado 
        )
        db.add(db_video)
        db.commit()
        
        return {"status": "ok", "archivo_guardado": ruta_guardado}
        
    except Exception as e:
        db.rollback()
        print(f"Error al guardar video: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await file.close()