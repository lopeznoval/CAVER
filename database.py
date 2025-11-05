# database.py
from sqlalchemy import create_engine, Column, Float, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

engine = create_engine('mysql+pymysql://usuario:password@localhost/sensores')
Base = declarative_base()

class Medicion(Base):
    __tablename__ = 'mediciones'
    id = Column(Integer, primary_key=True)
    temperatura = Column(Float)
    humedad = Column(Float)
    presion = Column(Float)
    fecha = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
