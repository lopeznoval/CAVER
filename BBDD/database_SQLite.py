import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Definir la URL de la base de datos
DATABASE_FILE = "robot_data_orm.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

# 2. Configuración de SQLAlchemy
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 3. Definición de Modelos (Tablas) ---
class LecturaSensor(Base):
    __tablename__ = "lecturas_sensores"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now)
    temperatura = Column(Float, nullable=False)
    humedad = Column(Float, nullable=False)
    sincronizado = Column(Boolean, default=False)

class Imagen(Base):
    __tablename__ = "imagenes"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now)
    ruta_archivo = Column(String, nullable=False)
    sincronizado = Column(Boolean, default=False)

# --- 4. Funciones ---
def crear_tablas():
    print("Asegurando que las tablas SQLite existan...")
    Base.metadata.create_all(bind=engine)
    print("Tablas listas.")

def get_db_session():
    return SessionLocal()