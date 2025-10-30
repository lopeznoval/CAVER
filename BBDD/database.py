# database.py
from sqlalchemy import create_engine, Column, Float, DateTime, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

# --- Configuración de conexión ---
USER = "root"          # o tu usuario MySQL
PASSWORD = "flick123_caver"
HOST = "localhost"
DB_NAME = "sensores"

# Cadena de conexión SQLAlchemy
engine = create_engine(f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}/{DB_NAME}", echo=False)

Base = declarative_base()

# --- Definición del modelo ---
class Medicion(Base):
    __tablename__ = 'mediciones'
    id = Column(Integer, primary_key=True)
    temperatura = Column(Float)
    humedad = Column(Float)
    presion = Column(Float)
    fecha = Column(DateTime, default=datetime.utcnow)

# --- Crear tabla si no existe ---
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
