from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from database import Session as DBSession, Medicion
from fastapi.templating import Jinja2Templates
from fastapi import Request

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Servir carpeta templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/datos")
def obtener_datos():
    session = DBSession()
    datos = session.query(Medicion).order_by(Medicion.fecha.asc()).all()
    session.close()
    return [
        {"fecha": d.fecha.isoformat(), "temperatura": d.temperatura, 
         "humedad": d.humedad, "presion": d.presion}
        for d in datos
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
