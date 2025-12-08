import json
from re import S
import uuid

class SyncPacket:
    def __init__(self, entries):
        """
        entries: lista de diccionarios, cada uno con un registro de sensor, movimiento o media
        """
        self.packet_id = str(uuid.uuid4())  # ID único para ACK
        self.entries = entries
        self.length = len(self.to_json().encode('utf-8'))

    def to_json(self) -> str:
        """
        Devuelve un JSON serializable del paquete
        """
        return json.dumps({
            "packet_id": self.packet_id,
            "entries": self.entries
        })


class NodeSyncManager:
    def __init__(self, db, r_id=0, max_bytes=240) -> list[SyncPacket]:
        """
        db: instancia de RobotDatabase
        max_bytes: tamaño máximo del paquete en bytes
        """
        self.db = db
        self.max_bytes = max_bytes
        self.robot_id = r_id

    # ---------------------------
    # Preparar paquetes JSON
    # ---------------------------
    def prepare_packets_sensors(self):
        """
        Lee registros pendientes de sincronización y los divide en paquetes ≤ max_bytes
        Devuelve lista de SyncPacket, listos para serializar a JSON.
        """
        unsynced = self.db.get_unsynced_sensors()  # lista de dicts por tabla
        packets = []
        current_entries = []

        for entry in unsynced:
            entry["data"]["robot_id"] = self.robot_id
            current_entries.append(entry)
            packet_size = len(json.dumps(current_entries).encode('utf-8'))
            if packet_size > self.max_bytes:
                current_entries.pop()  # quitar último registro
                if current_entries:
                    packets.append(SyncPacket(current_entries))
                current_entries = [entry]  # empezar nuevo paquete

        if current_entries:
            packets.append(SyncPacket(current_entries))

        return packets
    
    def prepare_packets_movs(self):
        """
        Lee registros pendientes de sincronización y los divide en paquetes ≤ max_bytes
        Devuelve lista de SyncPacket, listos para serializar a JSON.
        """
        unsynced = self.db.get_unsynced_movimientos()  # lista de dicts por tabla
        packets = []
        current_entries = []

        for entry in unsynced:
            entry["data"]["robot_id"] = self.robot_id
            current_entries.append(entry)
            packet_size = len(json.dumps(current_entries).encode('utf-8'))
            if packet_size > self.max_bytes:
                current_entries.pop()  # quitar último registro
                if current_entries:
                    packets.append(SyncPacket(current_entries))
                current_entries = [entry]  # empezar nuevo paquete

        if current_entries:
            packets.append(SyncPacket(current_entries))

        return packets
    
    def prepare_packets_media(self):
        """
        Lee registros pendientes de sincronización y los divide en paquetes ≤ max_bytes
        Devuelve lista de SyncPacket, listos para serializar a JSON.
        """
        unsynced = self.db.get_unsynced_media()  # lista de dicts por tabla
        packets = []
        current_entries = []

        for entry in unsynced:
            entry["data"]["robot_id"] = self.robot_id
            current_entries.append(entry)
            packet_size = len(json.dumps(current_entries).encode('utf-8'))
            if packet_size > self.max_bytes:
                current_entries.pop()  # quitar último registro
                if current_entries:
                    packets.append(SyncPacket(current_entries))
                current_entries = [entry]  # empezar nuevo paquete

        if current_entries:
            packets.append(SyncPacket(current_entries))

        return packets
    
    def prepare_packets_all(self):
        """
        Lee registros pendientes de sincronización y los divide en paquetes ≤ max_bytes
        Devuelve lista de SyncPacket, listos para serializar a JSON.
        """
        unsynced = self.db.get_unsynced_entries()  # lista de dicts por tabla
        packets = []
        current_entries = []

        for entry in unsynced:
            entry["data"]["robot_id"] = self.robot_id
            current_entries.append(entry)
            packet_size = len(json.dumps(current_entries).encode('utf-8'))
            if packet_size > self.max_bytes:
                current_entries.pop()  # quitar último registro
                if current_entries:
                    packets.append(SyncPacket(current_entries))
                current_entries = [entry]  # empezar nuevo paquete

        if current_entries:
            packets.append(SyncPacket(current_entries))

        return packets

    # ---------------------------
    # Marcar registros como sincronizados
    # ---------------------------
    def handle_ack(self, ack_json: str):
        """
        ack_json: string JSON recibido que contiene la lista de registros confirmados
        Ejemplo:
        '{"entries": [{"table": "sensores", "id": 1, "inserted_id": 10}, {"table": "media", "id": 3, "inserted_id": 5}]}'
        """
        print(f"Procesando ACK de sincronización de {ack_json}...")
        try:
            data = json.loads(ack_json)
            entries = data.get("entries", [])
            if entries:
                self.db.mark_as_synced(entries)
        except Exception as e:
            print(f"Error procesando ACK: {e}")

# Ejemplo de uso:
# sync = SyncManager(db)

# # Preparar paquetes para enviar
# packets = sync.prepare_packets()
# for pkt in packets:
#     json_string = pkt.to_json()  # Este string es lo que envías por LoRa
#     # Enviar json_string por LoRa (fuera de la clase)

# # Cuando recibes un ACK (string JSON)
# ack_json = '{"entries": [{"table": "sensores", "id": 1}, {"table": "media", "id": 3}]}'
# sync.handle_ack(ack_json)  # marca los registros como sincronizados en SQLite

