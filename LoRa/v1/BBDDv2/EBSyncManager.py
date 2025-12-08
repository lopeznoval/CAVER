import json
from datetime import datetime
import os

class BaseStationSyncManager:
    def __init__(self, media_folder="media", db=None):
        """
        media_folder: carpeta local donde se guardan fotos/videos
        db: instancia de BaseStationDatabase
        """
        self.media_folder = media_folder
        os.makedirs(media_folder, exist_ok=True)
        self.db = db

    def process_packet(self, packet_json: str) -> dict:
        """
        Procesa un paquete JSON recibido desde un robot.
        packet_json: string JSON con formato:
        {
            "packet_id": "...",
            "entries": [
                {"table":"sensores", "id":1, "data": {...}},
                {"table":"robot_movimiento", "id":2, "data": {...}},
                {"table":"media", "id":3, "data": {...}}
            ]
        }
        Devuelve un dict tipo ACK con los registros guardados.
        """
        packet = json.loads(packet_json)
        packet_id = packet.get("packet_id")
        entries = packet.get("entries", [])

        ack = {
            "packet_id": packet_id,
            "saved": []
        }

        print(f"Processing packet {packet_id} with {len(entries)} entries")
        for e in entries:
            table = e.get("table")
            data = e.get("data", {})
            robot_id = data.get("robot_id", "unknown")  # puedes añadir robot_id en el JSON si quieres
            timestamp = datetime.fromisoformat(data.get("timestamp")) if "timestamp" in data else None

            if table == "sensores":
                inserted_id = self.db.insert_sensor(
                    robot_id=robot_id,
                    temp=data.get("temp"),
                    hum=data.get("hum"),
                    timestamp=timestamp
                )
            elif table == "robot_movimiento":
                inserted_id = self.db.insert_movimiento(
                    robot_id=robot_id,
                    L=data.get("L"),
                    R=data.get("R"),
                    timestamp=timestamp
                )
            elif table == "media":
                path = data.get("path")
                # copiar archivo al media_folder si se necesita
                # para ejemplo solo guardamos la ruta
                inserted_id = self.db.insert_media(
                    robot_id=robot_id,
                    path=path,
                    es_video=data.get("es_video", False),
                    checksum=data.get("checksum"),
                    timestamp=timestamp
                )
            else:
                continue

            ack["saved"].append({
                "table": table,
                "robot_id": robot_id,
                "original_id": e.get("id"),
                "inserted_id": inserted_id
            })

        print(f"Se guardaron {len(ack['saved'])} registros del paquete {packet_id}")

        return ack
    