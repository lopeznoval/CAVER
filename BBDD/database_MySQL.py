import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base

# --- 1. Definición de la Conexión a MySQL ---
DB_USER = "robot_user"
DB_PASSWORD = "tu_clave_muy_segura"
DB_HOST = "localhost"
DB_NAME = "robot_db"

# El 'dialecto' es 'mysql+mysqlconnector'
DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

# --- 2. Configuración de SQLAlchemy (Engine) ---

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 3. Definición de Modelos (Tablas) ---

class LecturaSensor(Base):
    """Modelo para las lecturas de Temperatura y Humedad."""
    __tablename__ = "lecturas_sensores"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now)
    temperatura = Column(Float, nullable=False)
    humedad = Column(Float, nullable=False)
    sincronizado = Column(Boolean, default=False)
    
    # def __repr__(self):
    #     return f"<Lectura(id={self.id}, temp={self.temperatura}, sync={self.sincronizado})>"

class Imagen(Base):
    """Modelo para los registros de imágenes."""
    __tablename__ = "imagenes"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now)
    ruta_archivo = Column(String(255), nullable=False) 
    sincronizado = Column(Boolean, default=False)

    # def __repr__(self):
    #     return f"<Imagen(id={self.id}, ruta={self.ruta_archivo}, sync={self.sincronizado})>"

# --- 4. Funciones (sin cambios) ---
def crear_tablas():
    """Crea todas las tablas en la base de datos si no existen."""
    print("Asegurando que las tablas existan en MySQL...")
    Base.metadata.create_all(bind=engine)
    print("Tablas listas.")

def get_db_session():
    """Genera una nueva sesión de base de datos."""
    return SessionLocal()