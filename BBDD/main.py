# main.py (Versión MongoDB)
import os
import uuid
import shutil
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from pymongo import MongoClient

# --- Configuración de MongoDB ---
client = MongoClient("mongodb://localhost:27017/")
db = client["robot_bs_db"]
videos_collection = db["videos"] # La "tabla" para los videos

# --- Configuración de FastAPI ---
app = FastAPI(title="Robot Base Station API (MongoDB)")
UPLOAD_DIR = "videos_recibidos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def root():
    return {"message": "Servidor de Estación Base - Activo (MongoDB)"}


@app.post("/sync/video")
async def recibir_video(
    timestamp: datetime = Form(...), 
    file: UploadFile = File(...) 
):
    try:
        # 1. Guardar el archivo de video (igual que antes)
        ext = os.path.splitext(file.filename)[1] or ".mp4"
        nuevo_nombre = f"{uuid.uuid4()}{ext}"
        ruta_guardado = os.path.join(UPLOAD_DIR, nuevo_nombre)
        with open(ruta_guardado, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 2. Guardar el registro en MongoDB
        documento_video = {
            "timestamp": timestamp,
            "ruta_archivo": ruta_guardado,
            "nombre_original": file.filename
        }
        videos_collection.insert_one(documento_video)
        
        return {"status": "ok", "archivo_guardado": ruta_guardado}
        
    except Exception as e:
        print(f"Error al guardar video: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await file.close()