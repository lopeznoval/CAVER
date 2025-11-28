from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timedelta
import os

class BaseStationDatabase:
    def __init__(self, mongo_uri="mongodb://localhost:27017/", db_name="robot_bs_db"):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]

        # Colecciones coherentes con SQLite
        self.sensores_col = self.db["sensores"]
        self.movimientos_col = self.db["movimientos"]
        self.media_col = self.db["media"]

        # Crear índices para optimizar consultas por timestamp y robot_id
        self.sensores_col.create_index([("robot_id", ASCENDING), ("timestamp", DESCENDING)])
        self.movimientos_col.create_index([("robot_id", ASCENDING), ("timestamp", DESCENDING)])
        self.media_col.create_index([("robot_id", ASCENDING), ("timestamp", DESCENDING)])

    # ---------------------------
    # INSERTAR DATOS
    # ---------------------------
    def insert_sensor(self, robot_id, temp, hum, timestamp=None):
        doc = {
            "robot_id": robot_id,
            "timestamp": timestamp or datetime.now(),
            "temp": temp,
            "hum": hum
        }
        result = self.sensores_col.insert_one(doc)
        return str(result.inserted_id)

    def insert_movimiento(self, robot_id, L, R, timestamp=None):
        doc = {
            "robot_id": robot_id,
            "timestamp": timestamp or datetime.now(),
            "L": L,
            "R": R
        }
        result = self.movimientos_col.insert_one(doc)
        return str(result.inserted_id)

    def insert_media(self, robot_id, path, es_video=False, checksum=None, timestamp=None):
        doc = {
            "robot_id": robot_id,
            "timestamp": timestamp or datetime.now(),
            "es_video": es_video,
            "path": path,
            "checksum": checksum
        }
        result = self.media_col.insert_one(doc)
        return str(result.inserted_id)

    # ---------------------------
    # CONSULTAS
    # ---------------------------
    def get_latest_sensors(self, robot_id=None, n=1):
        query = {"robot_id": robot_id} if robot_id else {}
        return list(self.sensores_col.find(query).sort("timestamp", DESCENDING).limit(n))

    def get_sensors_range(self, start, end, robot_id=None):
        query = {"timestamp": {"$gte": start, "$lte": end}}
        if robot_id:
            query["robot_id"] = robot_id
        return list(self.sensores_col.find(query).sort("timestamp", ASCENDING))

    def get_latest_movimientos(self, robot_id=None, n=1):
        query = {"robot_id": robot_id} if robot_id else {}
        return list(self.movimientos_col.find(query).sort("timestamp", DESCENDING).limit(n))

    def get_movimientos_range(self, start, end, robot_id=None):
        query = {"timestamp": {"$gte": start, "$lte": end}}
        if robot_id:
            query["robot_id"] = robot_id
        return list(self.movimientos_col.find(query).sort("timestamp", ASCENDING))

    def get_latest_media(self, robot_id=None, n=1):
        query = {"robot_id": robot_id} if robot_id else {}
        return list(self.media_col.find(query).sort("timestamp", DESCENDING).limit(n))

    def get_media_range(self, start, end, robot_id=None):
        query = {"timestamp": {"$gte": start, "$lte": end}}
        if robot_id:
            query["robot_id"] = robot_id
        return list(self.media_col.find(query).sort("timestamp", ASCENDING))

    # ---------------------------
    # LIMPIEZA OPCIONAL
    # ---------------------------
    def delete_old_data(self, days=30):
        limite = datetime.now() - timedelta(days=days)
        self.sensores_col.delete_many({"timestamp": {"$lt": limite}})
        self.movimientos_col.delete_many({"timestamp": {"$lt": limite}})
        self.media_col.delete_many({"timestamp": {"$lt": limite}})



# Ejemplo de uso:
# from datetime import datetime, timedelta

# db = BaseStationDatabase()

# # Insertar registros
# db.insert_sensor(robot_id="UGV02", temp=22.5, hum=60)
# db.insert_movimiento(robot_id="UGV02", L=0.5, R=0.55)
# db.insert_media(robot_id="UGV02", path="videos/foto1.jpg", es_video=False)

# # Consultas
# ultimos_sensores = db.get_latest_sensors(robot_id="UGV02", n=5)
# ultimos_movs = db.get_latest_movimientos(robot_id="UGV02", n=5)
# ultimas_media = db.get_latest_media(robot_id="UGV02", n=5)

# # Consultar rango de tiempo
# inicio = datetime.utcnow() - timedelta(hours=2)
# fin = datetime.utcnow()
# sensores_rango = db.get_sensors_range(inicio, fin, robot_id="UGV02")

# # Limpiar datos antiguos
# db.delete_old_data(days=60)
