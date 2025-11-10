import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Definir la URL de la base de datos PostgreSQL
DATABASE_URL = "postgresql://postgres:tu_contraseña@localhost/robot_bs_db"

# 2. Configuración de SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 3. Definición de Modelos (Tablas) ---
class LecturaSensor(Base):
    __tablename__ = "lecturas_sensores"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False)
    temperatura = Column(Float, nullable=False)
    humedad = Column(Float, nullable=False)

class Video(Base):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False)
    ruta_archivo = Column(String, nullable=False) 

# --- 4. Funciones ---
def crear_tablas():
    print("Asegurando que las tablas PostgreSQL existan...")
    Base.metadata.create_all(bind=engine)
    print("Tablas listas.")

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Ejecutar esto una vez para crear las tablas en PostgreSQL
if __name__ == "__main__":
    crear_tablas()