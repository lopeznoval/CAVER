from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import hashlib
import os

Base = declarative_base()


# ---------------------------
# MODELOS
# ---------------------------

class SensorData(Base):
    __tablename__ = "sensores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now)
    temp = Column(Float, nullable=False)
    hum = Column(Float, nullable=False)
    sinc = Column(Boolean, default=False)


class RobotMovimiento(Base):
    __tablename__ = "robot_movimiento"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now)
    L = Column(Float, nullable=False)
    R = Column(Float, nullable=False)
    sinc = Column(Boolean, default=False)


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now)
    es_video = Column(Boolean, default=False)  # True = video, False = foto
    path = Column(String, nullable=False)
    checksum = Column(String, nullable=True)
    sinc = Column(Boolean, default=False)

    def generar_checksum(self):
        """Calcula SHA256 del archivo"""
        try:
            with open(self.path, "rb") as f:
                data = f.read()
                self.checksum = hashlib.sha256(data).hexdigest()
        except Exception:
            self.checksum = None


# ---------------------------
# CLASE ROBOT DATABASE
# ---------------------------

class RobotDatabase:
    def __init__(self, db_path="robot.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    # ---------------------------
    # SESIÓN
    # ---------------------------
    def new_session(self):
        return self.Session()

    # ---------------------------
    # INSERTAR DATOS
    # ---------------------------
    def insert_sensor(self, temp, hum, timestamp=None) -> int:
        """Inserta una lectura de sensor y devuelve su ID"""
        s = self.new_session()
        lectura = SensorData(temp=temp, hum=hum, timestamp=timestamp or datetime.now())
        s.add(lectura)
        s.commit()
        s.close()
        return lectura.id

    def insert_movimiento(self, L, R, timestamp=None) -> int:
        """Inserta un registro de movimiento y devuelve su ID"""
        s = self.new_session()
        mov = RobotMovimiento(L=L, R=R, timestamp=timestamp or datetime.now())
        s.add(mov)
        s.commit()
        s.close()
        return mov.id

    def insert_media(self, path, es_video=False, generar_checksum=True, sinc=False, timestamp=None) -> int:
        """Inserta un registro de media y devuelve su ID"""
        s = self.new_session()
        media = Media(path=path, es_video=es_video, sinc=sinc, timestamp=timestamp or datetime.now())
        if generar_checksum:
            media.generar_checksum()
        s.add(media)
        s.commit()
        s.close()
        return media.id

    # ---------------------------
    # CONSULTAS GENERALES
    # ---------------------------
    def get_latest_sensor(self, n=1) -> list:
        """Obtiene las últimas n lecturas de sensores"""
        s = self.new_session()
        result = s.query(SensorData).order_by(SensorData.timestamp.desc()).limit(n).all()
        s.close()
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "temp": r.temp,
                "hum": r.hum
            } for r in result
        ]


    def get_sensor_range(self, start_time, end_time) -> list:
        """Obtiene lecturas de sensores en un rango de tiempo"""
        s = self.new_session()
        result = s.query(SensorData).filter(
            SensorData.timestamp >= start_time,
            SensorData.timestamp <= end_time
        ).all()
        s.close()
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "temp": r.temp,
                "hum": r.hum
            } for r in result
        ]


    def get_latest_movimiento(self, n=1) -> list:
        """Obtiene los últimos n registros de movimiento"""
        s = self.new_session()
        result = s.query(RobotMovimiento).order_by(RobotMovimiento.timestamp.desc()).limit(n).all()
        s.close()
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "L": r.L,
                "R": r.R
            } for r in result
        ]


    def get_movimiento_range(self, start_time, end_time) -> list:
        """Obtiene registros de movimiento en un rango de tiempo"""
        s = self.new_session()
        result = s.query(RobotMovimiento).filter(
            RobotMovimiento.timestamp >= start_time,
            RobotMovimiento.timestamp <= end_time
        ).all()
        s.close()
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "L": r.L,
                "R": r.R
            } for r in result
        ]

    def get_latest_media(self, n=1) -> list:
        """Obtiene los últimos n registros de media"""
        s = self.new_session()
        result = s.query(Media).order_by(Media.timestamp.desc()).limit(n).all()
        s.close()
        return [
            {
                "id": m.id,
                "timestamp": m.timestamp.isoformat(),
                "es_video": m.es_video,
                "path": m.path,
                "checksum": m.checksum
            } for m in result
        ]


    def get_media_range(self, start_time, end_time) -> list:
        """Obtiene registros de media en un rango de tiempo"""
        s = self.new_session()
        result = s.query(Media).filter(
            Media.timestamp >= start_time,
            Media.timestamp <= end_time
        ).all()
        s.close()
        return [
            {
                "id": m.id,
                "timestamp": m.timestamp.isoformat(),
                "es_video": m.es_video,
                "path": m.path,
                "checksum": m.checksum
            } for m in result
        ]
    
    # ---------------------------
    # CONSULTAS DE DATOS NO SINCRONIZADOS
    # ---------------------------
    
    def get_latest_unsynced_sensor(self, n=1):
        s = self.new_session()
        result = s.query(SensorData).filter_by(sinc=False)\
            .order_by(SensorData.timestamp.desc()).limit(n).all()
        s.close()
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "temp": r.temp,
                "hum": r.hum
            } for r in result
        ]


    def get_latest_unsynced_movimiento(self, n=1):
        s = self.new_session()
        result = s.query(RobotMovimiento).filter_by(sinc=False)\
            .order_by(RobotMovimiento.timestamp.desc()).limit(n).all()
        s.close()
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat(),
                "L": r.L,
                "R": r.R
            } for r in result
        ]


    def get_latest_unsynced_media(self, n=1):
        s = self.new_session()
        result = s.query(Media).filter_by(sinc=False)\
            .order_by(Media.timestamp.desc()).limit(n).all()
        s.close()
        return [
            {
                "id": m.id,
                "timestamp": m.timestamp.isoformat(),
                "es_video": m.es_video,
                "path": m.path,
                "checksum": m.checksum
            } for m in result
        ]


    
    # ---------------------------
    # FUNCIONES GET UNSYNC
    # ---------------------------

    def get_unsynced_sensors(self, limit=None) -> list:
        """Devuelve registros de sensores pendientes de sincronizar"""
        s = self.new_session()
        query = s.query(SensorData).filter_by(sinc=False).order_by(SensorData.timestamp.asc())
        if limit:
            query = query.limit(limit)
        results = query.all()
        s.close()
        return [
            {
                "table": "sensores",
                "id": d.id,
                "data": {
                    "timestamp": d.timestamp.isoformat(),
                    "temp": d.temp,
                    "hum": d.hum
                }
            } for d in results
        ]


    def get_unsynced_movimientos(self, limit=None) -> list:
        """Devuelve registros de movimientos pendientes de sincronizar"""
        s = self.new_session()
        query = s.query(RobotMovimiento).filter_by(sinc=False).order_by(RobotMovimiento.timestamp.asc())
        if limit:
            query = query.limit(limit)
        results = query.all()
        s.close()
        return [
            {
                "table": "robot_movimiento",
                "id": d.id,
                "data": {
                    "timestamp": d.timestamp.isoformat(),
                    "L": d.L,
                    "R": d.R
                }
            } for d in results
        ]


    def get_unsynced_media(self, limit=None) -> list:
        """Devuelve registros de multimedia pendientes de sincronizar"""
        s = self.new_session()
        query = s.query(Media).filter_by(sinc=False).order_by(Media.timestamp.asc())
        if limit:
            query = query.limit(limit)
        results = query.all()
        s.close()
        return [
            {
                "table": "media",
                "id": d.id,
                "data": {
                    "timestamp": d.timestamp.isoformat(),
                    "es_video": d.es_video,
                    "path": d.path,
                    "checksum": d.checksum
                }
            } for d in results
        ]


    def get_unsynced_entries(self, limit=None) -> list:
        """
        Devuelve registros pendientes de sincronizar de todas las tablas
        de forma combinada. Se respeta el orden temporal dentro de cada tabla.
        El límite aplica al total combinado.
        """
        sensors = self.get_unsynced_sensors(limit)
        remaining = None if limit is None else limit - len(sensors)

        movimientos = []
        if remaining is None or remaining > 0:
            movimientos = self.get_unsynced_movimientos(remaining)
        remaining = None if remaining is None else remaining - len(movimientos)

        media = []
        if remaining is None or remaining > 0:
            media = self.get_unsynced_media(remaining)

        combined = sensors + movimientos + media
        if limit:
            combined = combined[:limit]

        return combined


    # ---------------------------
    # LIMPIEZA AUTOMÁTICA
    # ---------------------------
    def delete_old_data(self, days=30):
        """Elimina registros más antiguos que 'days' días"""
        s = self.new_session()
        limite = datetime.utcnow() - timedelta(days=days)
        s.query(SensorData).filter(SensorData.timestamp < limite).delete()
        s.query(RobotMovimiento).filter(RobotMovimiento.timestamp < limite).delete()
        s.query(Media).filter(Media.timestamp < limite).delete()
        s.commit()
        s.close()

    def mark_as_synced(self, packet_entries):
        """Marca los registros indicados como sincronizados"""
        s = self.new_session()

        for entry in packet_entries:
            table_name = entry["table"]
            record_id = entry["id"]

            if table_name == "sensores":
                s.query(SensorData).filter(SensorData.id == record_id).update({"sinc": True})
            elif table_name == "robot_movimiento":
                s.query(RobotMovimiento).filter(RobotMovimiento.id == record_id).update({"sinc": True})
            elif table_name == "media":
                s.query(Media).filter(Media.id == record_id).update({"sinc": True})

        s.commit()
        s.close()


# Ejemplo de uso:
# db = RobotDatabase("datos/robot_data.db")

# # Insertar datos
# db.insert_sensor(temp=23.5, hum=45)
# db.insert_movimiento(L=0.6, R=0.55)
# db.insert_media("imagenes/foto1.jpg", es_video=False)

# # Consultas
# ultimos_sensores = db.get_latest_sensor(5)
# ultimos_movs = db.get_latest_movimiento(5)
# ultimas_media = db.get_latest_media(5)

# # Borrar datos antiguos
# db.delete_old_data(days=60)