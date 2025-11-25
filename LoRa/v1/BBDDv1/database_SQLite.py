import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Definir la URL de la base de datos
DATA_SUBFOLDER = "datos"
DATABASE_NAME = "robot_data_orm.db"
os.makedirs(DATA_SUBFOLDER, exist_ok=True)
DATABASE_FILE = os.path.join(DATA_SUBFOLDER, DATABASE_NAME)
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"
# DATABASE_URL = f"sqlite:///{DATABASE_NAME}"

# 2. Configuración de SQLAlchemy
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 3. Definición de Modelos (Tablas) ---
class LecturaSensor(Base):
    __tablename__ = "lecturas_sensores"
    id = Column(Integer, primary_key=True, index=True)
    robot_id = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    temperatura = Column(Float, nullable=False)
    humedad = Column(Float, nullable=False)
    sincronizado = Column(Boolean, default=False) 

class Video(Base):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True, index=True)
    robot_id = Column(Integer, nullable=False)
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