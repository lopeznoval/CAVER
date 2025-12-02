# LoRaNode organizado
import io
import sys
import json
import queue
import time
import threading
import platform
import base64
import math
import socket
import serial
from PIL import Image
from BBDDv1.lora_bridge_mongo import connect_mongo, procesar_paquete_lora
from BBDDv1.registro_datos import registrar_lectura
from BBDDv1.database_SQLite import *
from BBDDv1.sincronizar_robot import actualizar_BBDD_robot, sincronizar_sensores_lora
from BBDDv2.db_SQLite import RobotDatabase
from BBDDv2.NodeSyncManager import NodeSyncManager
from BBDDv2.EBSyncManager import BaseStationSyncManager
from BBDDv2.db_mongo import BaseStationDatabase
from NodoLoRa.sx126x_bis import sx126x
from parameters import *
from Multimediav1.LoraCamSender import LoRaCamSender

class LoRaNode:
    def __init__(self, ser_port, addr, freq=433, pw=0, rssi=True, 
                 EB=0, robot_port=None, robot_baudrate=None, ip_sock=None, port_sock=None, sens_port=None, sens_baudrate=None):  # EB = 1 si es estación base
        
        self.running = True
        self.lora_port = ser_port
        self.node = sx126x(serial_num=ser_port, freq=freq, addr=addr, power=pw, rssi=rssi)
        print(f"LoRaNode initialized on {ser_port} with address {addr}, freq {freq}MHz, power {pw}dBm")
        self.pending_requests = {}                                  # msg_id -> callback/event
        self.lock_pending = threading.Lock()
        self.robot = None
        self.is_base = EB  # External Board reference
        self.is_relay = False

        self.addr = addr
        self.freq = freq
        self.power = pw

        self.robot_port = robot_port
        self.robot_baudrate = robot_baudrate
        self.response_queue = queue.Queue()
        
        self.sensores = None
        self.sens_port = sens_port
        self.sens_baudrate = sens_baudrate
        self.temp = None
        self.hum = None

        self.radar_sock = None
        self.ip_sock = ip_sock
        self.port_sock = port_sock

        if self.is_base:
            self.lock_nodes = threading.Lock()
            self.connected_nodes = {}
            self.node_timers = {}
            self.photo = None
            self.temp_mes = None
            self.hum_mes = None

        if platform.system() == "Linux":
            try:
                from picamera2 import Picamera2, Preview # type: ignore
                self.camera = Picamera2()
                self.lora_cam_sender = LoRaCamSender(camera=self.camera)

                self.stream = io.BytesIO()
                self.recording = False
                # carpetas
                home_dir = os.path.expanduser("~")
                self.photo_dir = os.path.join(home_dir, "photos")
                self.video_dir = os.path.join(home_dir, "videos") 
                self.pending_file = os.path.join(home_dir, "pending.json") 
                
                os.makedirs(self.photo_dir, exist_ok=True)
                os.makedirs(self.video_dir, exist_ok=True)
                if not os.path.exists(self.pending_file):
                    with open(self.pending_file, "w") as f:
                        json.dump([], f)

                # Pending in-memory for speed
                self._load_pending_list()
                # variables auxiliares
                self.pending_lock = threading.Lock()
            except Exception as e:
                print(f"Error al conectarse a la cámara: {e}")
                self.camera = None
                self.stream = None
        else:
            self.camera = None
            self.stream = None

        self.auto_move_running = False
        self.detect_collisions_running = False


        self.on_alert = lambda alrt: print(f"⚠️ [ALERT] {alrt}")
        self.on_message = lambda msg: print(f"💬 [MESSAGE] {msg}")
        self.on_bytes = lambda data: print(f"📦 [BYTES] {data}")
        self.on_position = lambda pos: print(f"[POSITION UPDATE] {pos}")
        self.on_sensor = lambda sensor: print(f"[SENSOR UPDATE]{sensor}")
        self.on_periodic_sensor = lambda temp, hum: print(f"[SENSOR PERIODIC UPDATE]{temp} ºC, {hum}%")
        self.on_battery = lambda battery_level: print(f"🔋 [BATTERY UPDATE]: {battery_level}")
        self.on_feedback = lambda feedback: print(f"[FEEDBACK UPDATE]: {feedback}")
        self.on_imu = lambda imu: print(f"[IMU UPDATE]: {imu}")
        self.on_photo = lambda photo: print(f"[RECEIVED PHOTO]")
        self.on_collision = lambda: print(f"[OBJECT DETECTED]")
        self.on_overturn = lambda vuelco: print(f"[OVERTURN] : {vuelco}")

    # -------------------- MENSAJES --------------------
    def pack_message(self, addr_dest:int, msg_type: int, msg_id: int, message: str, relay_flag: int =0) -> bytes:
        offset_freq = self.freq - 410 # assuming base freq is 410MHz
        header = bytes([
            (addr_dest >> 8) & 0xFF, addr_dest & 0xFF,
            (self.addr >> 8) & 0xFF, self.addr & 0xFF,
            (0x00),
            (relay_flag << 7) | (msg_type & 0x7F),
            msg_id & 0xFF
        ])
        print(f"Message size: {len(message.encode())} / Total size: {len(header) + len(message.encode())} bytes")
        if len(header) + len(message.encode()) > 242:
            print("⚠️ Message too long to pack in just a LoRa packet.")
            return
        return header + message.encode()
    
    def pack_bytes(self, addr_dest:int, msg_type: int, msg_id: int, data: bytes, relay_flag: int = 0, part: int = 0) -> bytes:
        offset_freq = self.freq - 410 # assuming base freq is 410MHz
        header = bytes([
            (addr_dest >> 8) & 0xFF, addr_dest & 0xFF,
            (self.addr >> 8) & 0xFF, self.addr & 0xFF,
            (0x01 if part == 0 else 0x02),
            (relay_flag << 7) | (msg_type & 0x7F),
            msg_id & 0xFF
        ])
        print(f"Bytes size: {len(data)} / Total size: {len(header) + len(data)} bytes")
        if len(header) + len(data) > 242:
            print("⚠️ Data too long to pack in just a LoRa packet.")
            return
        return header + data

    def unpack_message(self, r_buff: bytes) -> tuple:
        if len(r_buff) < 7:
            print(f"⚠️ Paquete recibido demasiado corto: len={len(r_buff)} -> {r_buff}")
            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Paquete recibido demasiado corto")
            return None
        
        addr_dest = (r_buff[0] << 8) + r_buff[1]
        addr_sender = (r_buff[2] << 8) + r_buff[3]
        part = r_buff[4] & 0x02
        is_b = r_buff[4] & 0x01
        msg_type = r_buff[5] & 0x7F
        relay_flag = r_buff[5] >> 7
        msg_id = r_buff[6]
        if is_b == 0:
            message = r_buff[7:].decode(errors='ignore')
        else:   
            message = r_buff[7:] 

        print(f"Unpacked message: from {addr_sender} to {addr_dest}, type {msg_type}, id {msg_id}, relay {relay_flag}, msg: {message}")
        
        return addr_sender, addr_dest, msg_type, msg_id, relay_flag, message, part, is_b

    # -------------------- HILOS --------------------
    def periodic_status(self):
        while self.running:
            self.send_message(0xFFFF, 5, 0, "", 0)
            print(f"[{time.strftime('%H:%M:%S')}] PING enviado")
            time.sleep(40) # intervalos de 40 segundos entre envío y envío

    def send_message(self, addr_dest: int, msg_type: int, msg_id: int, message: str, relay_flag: int = 0, callback=None):
        data = self.pack_message(addr_dest, msg_type, msg_id, message, relay_flag)
        if data is None:
            return
        self.node.send_bytes(data)
        if self.is_base and addr_dest != 0xFFFF:
            self.add_pending(addr_dest, msg_id)

    def send_bytes(self, addr_dest: int, msg_type: int, msg_id: int, data: bytes, relay_flag: int = 0, callback=None):
        while len(data) > 230:
            chunk = data[:230]
            data = data[230:]
            part = 1
            packed_data = self.pack_bytes(addr_dest, msg_type, msg_id, chunk, relay_flag, part)
            if packed_data is None:
                return
            self.node.send_bytes(packed_data)
            time.sleep(0.5)  # pequeño retardo entre fragmentos
        part = 0
        packed_data = self.pack_bytes(addr_dest, msg_type, msg_id, data, relay_flag, part)
        self.node.send_bytes(packed_data)
        # packed_data = self.pack_bytes(addr_dest, msg_type, msg_id, data, relay_flag)
        # self.node.send_bytes(packed_data)
        # if self.is_base and addr_dest != 0xFFFF:
        #     self.add_pending(addr_dest, msg_id)

    def receive_loop(self):
        while self.running:
            msg = self.node.receive_bytes()
            if not msg:
                time.sleep(0.05)
                continue
            threading.Thread(target=self.processing_loop, args=(msg,), daemon=True).start()

    def processing_loop(self, msg):
            try:
                addr_sender, addr_dest, msg_type, msg_id, relay_flag, message, part, is_b = self.unpack_message(msg)
            except Exception as e:
                print(f"Error unpacking message: {e}")
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Error unpacking message")
                return
            print(f"[{time.strftime('%H:%M:%S')}] Received from {addr_sender}: {message}")
            
            if addr_dest != self.addr and addr_dest != 0xFFFF:
                if self.is_relay:
                    print(f"Relaying message from {addr_sender} to {addr_dest}")
                    self.on_alert(f"[{time.strftime('%H:%M:%S')}] Relaying message from {addr_sender} to {addr_dest}")
                    self.send_message(addr_dest, msg_type, msg_id, message)
                else:
                    self.on_message(f"[{time.strftime('%H:%M:%S')}] ✖️ Received from {addr_sender} to {addr_dest}: {message}.")
                    self.on_alert(f"[{time.strftime('%H:%M:%S')}] Received message not for this node (dest: {addr_dest}), discarding.")
                return            
            # -------------------- HANDLER DE TIPOS --------------------
            self.on_message(f"[{time.strftime('%H:%M:%S')}] ✔️ Received from {addr_sender} to {addr_dest}: {message}.")
            
            try: 
                # Mensajes tipo 0 -son los enviados por el robot directamente-, por lo que aquí se describe la lógica de recepción de datos
                if msg_type == 0:
                    if msg_id == 20: # hacer lo que sea en la EB
                    #     try:
                    #         resp = procesar_paquete_lora(message)
                    #         self.send_message(addr_sender, 0, 21, resp)
                    #     except Exception as e:
                    #         self.on_alert(f"[{time.strftime('%H:%M:%S')}] Error sincronizando sensores LoRa: {e}")
                    # if msg_id == 21: 
                    #     with get_db_session() as session:
                    #         actualizar_BBDD_robot(message, session)  
                    #     print(f"[{time.strftime('%H:%M:%S')}] BBDD robot actualizada tras ACK")
                        ack = self.process_packet_base(message)
                        self.send_message(addr_sender, 0, 21, ack)
                    if msg_id == 21: 
                        self.ack_BBDD_packet(message)
                    
                    elif msg_id == 30:
                        try:
                            if part == 1:
                                if self.photo is None:
                                    self.photo = bytearray()
                                self.photo.extend(message)
                            if part == 0 and self.photo is not None:
                                self.photo.extend(message)
                                img = Image.open(io.BytesIO(bytes(self.photo)))
                                self.on_photo(img)
                                self.photo = None  

                        except Exception as e:
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Error decodificando foto: {e}")
                    elif msg_id == 40: # sensores
                        try:
                            self.temp_hum(message)
                        except Exception as e:
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Error procesando sensores periódicos (ID 40): {e}")
                    elif msg_id == 50: # colision
                        self.on_collision()
                    elif msg_id == 63: #imu
                        self.imu_pos(message)
                    elif msg_id == 64: # beteria
                        battery_level = message
                        self.on_battery(battery_level)
                    elif msg_id == 65: # feedback
                        self.on_feedback(message)
                    elif msg_id == 66: # imu
                        self.on_imu(message)
                    elif msg_id == 69: 
                        if self.is_base:
                            # resp = procesar_paquete_lora(message)
                            # self.send_message(addr_sender, 4, msg_id, resp)
                            ...
                
                # Respuestas posibles: 1- Error, 2- Consulta estándar, 3- Respuesta robot, 4- Respuesta sensores/camara/radar (o BBDD), 5- Ack Relay
                elif 0 < msg_type < 5: 
                    if msg_type == 2:  # Respuesta estándar
                        with self.lock_nodes:
                            self.connected_nodes[addr_sender] = {
                                "robot": bool(int(message[0])),      
                                "radar": bool(int(message[1])),      
                                "sensors": bool(int(message[2])),   
                                "camera": bool(int(message[3]))     
                            }
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Nodos: {self.connected_nodes}")
                        
                        if addr_sender in self.node_timers:
                            self.node_timers[addr_sender].cancel()
                        timer = threading.Timer(60, self.remove_node, args=(addr_sender,))
                        self.node_timers[addr_sender] = timer
                        print(self.node_timers)
                        timer.start()

                    if msg_type == 4:
                        if message.startswith("Temp:"):
                            try:
                                parts = message.split(",")
                                temp_str = parts[0].split(":")[1].strip().replace("°C", "")
                                hum_str = parts[1].split(":")[1].strip().replace("%", "")
                                self.temp_mes = float(temp_str)
                                self.hum_mes = float(hum_str)
                                self.on_sensor(f"[{time.strftime('%H:%M:%S')}] Sensor data from {addr_sender} - Temp: {self.temp_mes}°C, Hum: {self.hum_mes}%")
                            except Exception as e:
                                print(f"[{time.strftime('%H:%M:%S')}] Error parsing sensor data: {e}")

                    self.remove_pending(addr_sender, msg_id)
                    return

                elif 4 < msg_type < 10:  # Comandos generales
                    if msg_type == 5:  # Ping
                        resp = ""
                        resp += "1" if self.robot is not None else "0"
                        resp += "1" if self.radar_sock is not None else "0"
                        resp += "1" if self.sensores is not None else "0"
                        resp += "1" if self.camera is not None else "0"
                        time.sleep(0.2*self.addr)  # evitar colisiones
                        self.send_message(addr_sender, 2, msg_id, resp)
                    elif msg_type == 6:  # Status
                        status = f"Node {self.addr} OK. Freq: {self.freq} MHz, Power: {self.power} dBm"
                        time.sleep(0.2*self.addr)  # evitar colisiones
                        self.send_message(addr_sender, 2, msg_id, status)
                    elif msg_type == 7:  # Stop
                        resp = "Node stopping..."
                        time.sleep(0.2*self.addr)  # evitar colisiones
                        self.send_message(addr_sender, 2, msg_id, resp)
                        self.stop()
                    elif msg_type == 8: # Check RSSI
                        ...
                    elif msg_type == 9: 
                        ...

                elif 9 < msg_type < 20:  # Comandos hacia el robot
                    # -------------------- feedback --------------------
                    if msg_type == 10:
                        if "0" in message:
                            self.feeedback_running = False
                        elif "1" in message:
                            self.feeedback_running = True
                            self.feedback_dest = addr_sender
                            self.feedback_thread = threading.Thread(target=self._feedback_loop, daemon=True)
                            self.feedback_thread.start()
                        elif "2" in message:
                            resp = self.send_to_robot("{\"T\":130}")  
                            self.send_message(addr_sender, 0, 65, resp)
                        else:
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}]⚠️ Comando de feedback desconocido: {message}") 

                    elif msg_type == 13: # pedir o parar datos imu
                        if "1" in message:
                            print("llego el 1 para empezar")
                            if getattr(self, "imu_thread", None) and self.imu_thread.is_alive():
                                self.on_alert("[{time.strftime('%H:%M:%S')}] ⚠️ IMU loop ya estaba activo.")
                            else:
                                self.stop_imu_flag = False
                                self.imu_dest = addr_sender
                                self.imu_thread = threading.Thread(target=self._get_imu_loop_raspi, daemon=True)
                                self.imu_thread.start()
                                self.on_alert(f"[{time.strftime('%H:%M:%S')}] 🟢 IMU loop activado por EB.")
                        elif "0" in message:
                            self.stop_imu_flag = True
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] 🔴 IMU loop detenido por EB.")
                        elif "2" in message:
                            resp = self.send_to_robot("{\"T\":126}")  
                            self.send_message(addr_sender, 0, 66, resp)
                        else:
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] ⚠️ Comando IMU desconocido: {message}") 
                    
                    elif msg_type == 14:
                        if "1" in message:
                            self.auto_move_running = True
                            self.detect_collisions_running = True
                            self.colision_dest = addr_sender
                            if not getattr(self, "mov_aut_thread", None) or not self.mov_aut_thread.is_alive():
                                self.mov_aut_thread = threading.Thread(target=self._move_robot_loop, daemon=True)
                                self.mov_aut_thread.start()
                        elif "0" in message:
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Movimiento autónomo loop detenido por EB.")
                            self.auto_move_running = False
                            self.detect_collisions_running = False
                        else: 
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] ⚠️ Comando movimiento autónomo desconocido: {message}") 

                    elif msg_type == 15:
                        if "0" in message:
                            self.battery_monitor_running = False
                        elif "1" in message:
                            self.battery_monitor_running = True
                            self.battery_dest = addr_sender
                            self.battery_monitor_thread = threading.Thread(target=self._battery_monitor_loop, daemon=True)
                            self.battery_monitor_thread.start()
                        elif "2" in message:
                            resp = self.send_to_robot("{\"T\":130}")  
                            print("[DEBUG RAW RESP]:", repr(resp))
                            data = json.loads(resp)
                            battery = data.get("v", 0)   # por si no existe, devuelve 0
                            print("BATERIA")
                            print(battery)
                            print("BATERIA ")
                            # self.send_message(self.battery_dest, 0, 64, battery)
                            self.send_message(addr_sender, 0, 64, str(battery))
                        else:
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] ⚠️ Comando de monitorización de batería desconocido: {message}") 

                    elif msg_type == 16:
                        if "1" in message:
                            self.detect_collisions_running = True
                            self.colision_dest = addr_sender
                            if not getattr(self, "mov_aut_thread", None) or not self.mov_aut_thread.is_alive():
                                self.mov_aut_thread = threading.Thread(target=self._move_robot_loop, daemon=True)
                                self.mov_aut_thread.start()
                        elif "0" in message:
                            self.on_alert("Detacción de colisiones detenida por EB.")
                            self.detect_collisions_running = False
                        else: 
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] ⚠️ Comando detección de colisiones desconocido: {message}") 

                    if self.robot.is_open and self.robot:
                        resp = self.send_to_robot(message)
                        self.send_message(addr_sender, 3, msg_id, resp)
                    else:
                        self.send_message(addr_sender, 3, msg_id, "Error: CAVER is not defined in this node.")
                    

                elif 19 < msg_type < 25:  # Comando para los sensores y BBDD
                    if msg_type == 21:  # Lectura temperatura y humedad
                        self.sensor_dest = addr_sender
                        if self.on_sensor is None:
                            self.connect_sensors()
                            self.sensor_dest = addr_sender
                            sensor_th = threading.Thread(target=self.read_sensors_loop, daemon=True)
                            sensor_th.start()
                        self.send_message(addr_sender, 4, msg_id, f"Temp: {self.temp:.1f}°C, Hum: {self.hum:.1f}%")
                    if msg_type == 22:  # Realizar lectura mandada por la EB
                        self.read_sensors_once()
                        self.send_message(addr_sender, 4, msg_id, f"Temp: {self.temp:.1f}°C, Hum: {self.hum:.1f}%")
                    if msg_type == 20:  # Encender led
                        self.control_led("ON")
                    if msg_type == 23:  # Apagar led
                        self.control_led("OFF")
                    if msg_type == 24:  # Modo automático led
                        self.control_led("AUTO")

                elif 24 < msg_type < 31:  # Comandos para cámara y radar
                     # ---------------------- FOTO ----------------------
                    if msg_type == 25:  # Tomar foto
                        # img_b64 = self.take_picture_and_save()
                        # ------ PROBAR ------
                        resp = self.take_picture_and_save_compressed(addr_sender)
                        self.send_message(addr_sender, 1, msg_id, "ACK Foto recibida y en proceso de envío.")
                        if resp is not None:
                            self.send_bytes(addr_sender, 0, msg_id, resp)
                        print(f"[{time.strftime('%H:%M:%S')}] Foto enviada a {addr_sender}")

                    # ---------------------- VIDEO ----------------------
                    elif msg_type == 26:  # iniciar grabación
                        video_bytes = self.start_video_recording()
                        if video_bytes:
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Vídeo comprimido listo ({len(video_bytes)} bytes).")
                       
                        # # ---------------------- INICIAR VIDEO ----------------------
                        # if "1" in message:
                        #     filename = self.start_video_recording()
                        #     self.send_message(addr_sender, 4, msg_id, f"Video recording started: {filename}")
                        #     print(f"[{time.strftime('%H:%M:%S')}] Grabación iniciada: {filename}")
                        # elif "0" in message:
                        #     # ---------------------- DETENER VIDEO ----------------------
                        #     filename = self.stop_video_recording()
                        #     self.send_message(addr_sender, 4, msg_id, f"Video recording stopped: {filename}")
                        #     print(f"[{time.strftime('%H:%M:%S')}] Grabación detenida: {filename}")
                        # else: 
                        #     self.on_alert(f"⚠️ Comando camara desconocido: {message}") 

                    elif msg_type == 27:
                        try:
                            host_eb, port_eb = message.split(":")
                            img_bytes, path = self.lora_cam_sender.capture_recording_optimized(self.photo_dir)

                            if self.lora_cam_sender.send_photo_file_wifi(host_eb, port_eb, img_bytes):
                                self.db.insert_media(path=path, es_video=False, sinc=True)
                                print(f"[{time.strftime('%H:%M:%S')}] Foto enviada vía WiFi a EB.")
                                print(f"[{time.strftime('%H:%M:%S')}] Foto guardada en SQLite y sincronizada.")
                            else:
                                self.db.insert_media(path=path, es_video=False)
                                print(f"[{time.strftime('%H:%M:%S')}] Foto guardada en SQLite.")
                        except Exception as e:
                            print(f"[{time.strftime('%H:%M:%S')}] Error enviando foto vía WiFi: {e}")


                    elif msg_type == 28: 
                        try:
                            data = json.loads(message)
                            host_eb = data.get("host", "192.168.1.1")
                            port_eb = data.get("port", 6000)
                            duration = data.get("duracion", 3)

                            img_bytes, path = self.lora_cam_sender.video_recording_optimized(self.video_dir, duration)

                            if self.lora_cam_sender.send_video_file_wifi(host_eb, port_eb, img_bytes):
                                self.db.insert_media(path=path, es_video=False, sinc=True)
                                print(f"[{time.strftime('%H:%M:%S')}] Foto enviada vía WiFi a EB.")
                                print(f"[{time.strftime('%H:%M:%S')}] Foto guardada en SQLite y sincronizada.")
                            else:
                                self.db.insert_media(path=path, es_video=False)
                                print(f"[{time.strftime('%H:%M:%S')}] Foto guardada en SQLite.")
                        except Exception as e:
                            print(f"[{time.strftime('%H:%M:%S')}] Error enviando foto vía WiFi: {e}")

                elif msg_type == 31:
                    print("Relay mode set to: ", relay_flag)
                    self.is_relay = bool(relay_flag)
                    self.send_message(addr_sender, 5, msg_id, "OK")

            except Exception as e:
                self.on_alert(f"Error processing message: {e}")
                self.send_message(addr_sender, 1, msg_id, "Error")

            finally:
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Finished processing message.")
                time.sleep(0.1)

    # ------------------- PENDING REQUESTS -----------------

    def add_pending(self, addr_dest: int, msg_id: int):
        with self.lock_pending:
            self.pending_requests.setdefault(addr_dest, []).append(msg_id)
        self.on_alert(f"[{time.strftime('%H:%M:%S')}] Added pending request: {msg_id} to {addr_dest}")

    def remove_pending(self, addr_dest: int, msg_id: int) -> bool:
        with self.lock_pending:
            if addr_dest in self.pending_requests:
                try:
                    self.pending_requests[addr_dest].remove(msg_id) 
                    if not self.pending_requests[addr_dest]:
                        del self.pending_requests[addr_dest]
                    self.on_alert(f"[{time.strftime('%H:%M:%S')}] Removed pending request: {msg_id} to {addr_dest}")
                    return True
                except ValueError:
                    pass  
            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Unavailable pending request: {msg_id} to {addr_dest}")
            return False
        
    def remove_node(self, addr_sender):
        with self.lock_nodes:
            if addr_sender in self.connected_nodes:
                del self.connected_nodes[addr_sender]
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Nodo {addr_sender} eliminado por timeout.")


    # -------------------- SERIAL ROBOT --------------------
    def swap_robot_port(self, new_port: str, new_baudrate: int):
        if self.robot and self.robot.is_open:
            self.robot.close()
        self.robot_port = new_port
        self.robot_baudrate = new_baudrate
        self.connect_robot()
    
    def connect_robot(self):
        try:
            self.robot = serial.Serial(self.robot_port, self.robot_baudrate, dsrdtr=None, rtscts=False)
            self.robot.setRTS(False)
            self.robot.setDTR(False)
            self.robot.write(("{\"T\":131,\"cmd\":0}" + "\r\n").encode('utf-8'))      # se desactiva el chasis feedback
            # self.robot.write(("{\"T\":142,\"cmd\":10000}" + "\r\n").encode('utf-8'))  # timer cahsis feedback
            print(f"[{time.strftime('%H:%M:%S')}] Connected to robot on {self.robot_port}")
            self.robot.flushInput()
            self.robot_listener = threading.Thread(target=self.receive_from_robot)
            self.robot_listener.daemon = True
            self.robot_listener.start()
            return True
        except serial.SerialException as e:
            print(f"[{time.strftime('%H:%M:%S')}] Failed to connect to robot: {e}")
            return False 

    def receive_from_robot(self):
        while self.robot:
            data = self.robot.readline().decode('utf-8')
            if data:
                try:
                    print(f"[{time.strftime('%H:%M:%S')}] Received from robot: {data}")
                    self.response_queue.put(data)  # Guarda cada respuesta
                except Exception as e:
                    print(f"[{time.strftime('%H:%M:%S')}] Error reading: {e}")

    def send_to_robot(self, command: str) -> str:
        """Envía un comando al robot y devuelve la respuesta."""
        if self.running and self.robot and self.robot.is_open:
            self.robot.reset_input_buffer()
            self.robot.write((command + "\r\n").encode('utf-8'))
            print(f"[{time.strftime('%H:%M:%S')}] Enviando comando al robot.")  
            try:
                response = self.response_queue.get(timeout=5)
                return response
            except queue.Empty:
                return "OK"
        #else:
        #    return "OK"
        
    def _get_imu_loop_raspi(self): # IMU
        while not getattr(self, "stop_imu_flag", False):
            try:
                imu_data = self.send_to_robot("{\"T\":126}")
                if imu_data:
                    self.send_message(self.imu_dest, 0, 63, imu_data)
                time.sleep(10)
                # time.sleep(40)
            except Exception as e:
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Error en IMU loop: {e}")
                time.sleep(2)
        self.on_alert(f"[{time.strftime('%H:%M:%S')}] IMU loop finalizado.")
    
    # def _move_robot_loop(self):

    #     UDP_IP = "0.0.0.0"
    #     UDP_PORT = 5005

    #     radar_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     radar_sock.bind((UDP_IP, UDP_PORT))
    #     radar_sock.settimeout(0.01)         # más rápido para vaciar buffer
    #     radar_sock.setblocking(False)

    #     print("🔄 Autonomía iniciada...")
        
    #     self.auto_move_running = True
    #     last_cmd = None                     # para no enviar comandos repetidos
    #     last_state = 0                      # último estado recibido del radar
    #     self.robot.reset_input_buffer()

    #     while self.auto_move_running :

    #         # --- 1. Vaciar el buffer UDP ---
    #         mensaje = None
    #         while True:
    #             try:
    #                 data, _ = radar_sock.recvfrom(1024)
    #                 mensaje = data.decode()
    #             except BlockingIOError:
    #                 break
    #             except socket.timeout:
    #                 break

    #         # --- 2. Procesar último mensaje disponible ---
    #         if mensaje is not None:
    #             print(f"⚠️ Mensaje radar recibido: {mensaje}")
    #             last_state = int(mensaje)   # 0 o 1

    #         # --- 3. Lógica de control ---
    #         if last_state == 1:
    #             # Parar
    #             cmd = {"T": 1, "L": 0, "R": 0}
    #             print("⚠️ Colisión detectada → PARAR")
    #             self.robot.write((json.dumps(cmd) + "\r\n").encode('utf-8'))

    #             # Girar
    #             time.sleep(0.5)
    #             cmd = {"T": 1, "L": 0.1, "R": -0.1}
    #             if cmd != last_cmd:
    #                 print("⚠️ Colisión detectada → GIRAR")
    #                 self.robot.write((json.dumps(cmd) + "\r\n").encode('utf-8'))
    #                 time.sleep(1)
    #                 last_cmd = cmd

    #         else:
    #             # Avanzar
    #             cmd = {"T": 1, "L": 0.1, "R": 0.1}
    #             print("✔️ Libre → AVANZAR")
    #             self.robot.write((json.dumps(cmd) + "\r\n").encode('utf-8'))
    #             last_cmd = cmd

    #         time.sleep(0.15)  # control loop

    #     radar_sock.close()
    #     print("🛑 Autonomía detenida.")


    def _move_robot_loop(self):

        UDP_IP = "0.0.0.0"
        UDP_PORT = 5005

        radar_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        radar_sock.bind((UDP_IP, UDP_PORT))
        radar_sock.settimeout(0.01)         # más rápido para vaciar buffer
        radar_sock.setblocking(False)

        print(f"[{time.strftime('%H:%M:%S')}] 🔄 Autonomía iniciada...")
        
        self.auto_move_running = True
        last_cmd = None                     # para no enviar comandos repetidos
        last_state = 0                      # último estado recibido del radar
        self.robot.reset_input_buffer()

        while self.auto_move_running: #or self.detect_collisions_running:

            # --- 1. Vaciar el buffer UDP ---
            mensaje = None
            while True:
                try:
                    data, _ = radar_sock.recvfrom(1024)
                    mensaje = data.decode()
                except BlockingIOError:
                    break
                except socket.timeout:
                    break

            # --- 2. Procesar último mensaje disponible ---
            if mensaje is not None:
                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Mensaje radar recibido: {mensaje}")
                last_state = int(mensaje)   # 0 o 1

            # --- 3. Lógica de control ---
            if self.auto_move_running:
                print("🔄 Autonomía iniciada...")
                if last_state == 1:
                    self.send_message(self.colision_dest, 0, 50, "1")
                                                                
                    # Parar
                    cmd = {"T": 1, "L": 0, "R": 0}
                    print("[{time.strftime('%H:%M:%S')}] ⚠️ Colisión detectada → PARAR")
                    self.robot.write((json.dumps(cmd) + "\r\n").encode('utf-8'))

                    # Girar
                    time.sleep(0.5)
                    cmd = {"T": 1, "L": 0.1, "R": -0.1}
                    if cmd != last_cmd:
                        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Colisión detectada → GIRAR")
                        self.robot.write((json.dumps(cmd) + "\r\n").encode('utf-8'))
                        time.sleep(1)
                        last_cmd = cmd

                else:
                    # Avanzar
                    cmd = {"T": 1, "L": 0.1, "R": 0.1}
                    print(f"[{time.strftime('%H:%M:%S')}] ✔️ Libre → AVANZAR")
                    self.robot.write((json.dumps(cmd) + "\r\n").encode('utf-8'))
                    last_cmd = cmd

                time.sleep(0.15)  # control loop
                                

        radar_sock.close()
        print(f"[{time.strftime('%H:%M:%S')}]🛑 Autonomía detenida.")
            
    def _battery_monitor_loop(self):
        """
        Envía periódicamente la lectura de batería al nodo solicitante mientras self.battery_monitor_running sea True.
        """
        while getattr(self, "battery_monitor_running", False) and self.running:
            if self.robot and self.robot.is_open:
                try:
                    resp = self.send_to_robot("{\"T\":130}")
                    data = json.loads(resp)
                    battery = data.get("v", 0)
                    self.send_message(self.battery_dest, 0, 64, str(battery))
                except Exception as e:
                    self.on_alert(f"Error leyendo batería: {e}")
            time.sleep(60)
    
    def _feedback_loop(self):
        """
        Envía periódicamente la lectura de feedback al nodo solicitante.
        """
        while getattr(self, "feeedback_running", False) and self.running:
            if self.robot and self.robot.is_open:
                try:
                    resp = self.send_to_robot("{\"T\":130}")  
                    self.send_message(self.feedback_dest, 0, 65, resp)
                except Exception as e:
                    self.on_alert(f"Error leyendo feedback: {e}")
            time.sleep(5)



    # def _move_robot_loop(self):

    #     UDP_IP = "0.0.0.0"#"192.168.1.10"
    #     UDP_PORT = 5005

    #     radar_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     radar_sock.bind((UDP_IP, UDP_PORT))
    #     radar_sock.settimeout(0.05)
    #     # radar_sock.setblocking(False)

    #     self.auto_move_running = True
    #     self.colision = 0

    #     print("🔄 Autonomía iniciada...")

    #     while self.auto_move_running:

    #         # Leer radar
    #         # self.colision = 0
    #         # Decidir movimiento
    #         # if self.colision == 1:
    #         #     cmd = {"T": 1, "L": 0, "R": 0} 
    #         #     print("⚠️ Colisión detectada → PARAR")
    #         #     time.sleep(1)
    #         #     cmd = {"T": 1, "L": 0.1, "R": -0.1}   # girar para evitar
    #         #     print("⚠️ Colisión detectada → GIRAR")
    #         # else:
    #         #     cmd = {"T": 1, "L": 0.1, "R": 0.1}   # avanzar recto
    #         #     print("✔️ Libre → AVANZAR")

    #         # # Enviar al robot
    #         # self.send_to_robot(json.dumps(cmd))
    #         try:
    #             data, _ = radar_sock.recvfrom(1024)
    #             mensaje = data.decode() #val = int.from_bytes(data, "little")
    #             print(f"⚠️ Mensaje radar recibido: {mensaje}")

    #             if mensaje=="1":   #mensaje = "STOP_ROBOT":
    #                 self.colision = 1 
    #                 cmd = {"T": 1, "L": 0, "R": 0} 
    #                 print("⚠️ Colisión detectada → PARAR")
    #                 self.send_to_robot(json.dumps(cmd))
    #                 time.sleep(1)
    #                 cmd = {"T": 1, "L": 0.1, "R": -0.1}   # girar para evitar
    #                 print("⚠️ Colisión detectada → GIRAR") 
    #                 self.send_to_robot(json.dumps(cmd))
    #             else: 
    #                 self.colision = 0                       
                
    #         except socket.timeout:
    #             if self.colision == 0:
    #                 cmd = {"T": 1, "L": 0.1, "R": 0.1}   # avanzar recto
    #                 print("✔️ Libre → AVANZAR")
                    
    #                 self.send_to_robot(json.dumps(cmd))

            

    #         #time.sleep(1)

    #     print("🛑 Autonomía detenida.")
    #     radar_sock.close()


    # ------------------------------ IMU ------------------------------
    #  Se asume respuesta asi:
    # {"T":1002, "r":-89.04126934, "p":-0.895245861, "ax":-0.156085625, "ay":-9.987277031, "az":0.167132765, 
    # "gx":0.00786881, "gy":0.0033449, "gz":0.00259476, "mx":1.261048317, "my":-14.89113426, "mz":118.1274872, "temp":30.20118523}
    
    def imu_pos(self, imudata):
        """
        Calcula posición y orientación estimada a partir de ax, ay, az, gx, gy, gz.
        """        
        # dt = 0.05  # periodo 50 ms
        # alpha = 0.98  # peso del giroscopio

        # --- Decodificar JSON ---
        if isinstance(imudata, str):
            try:
                imudata = json.loads(imudata)
            except json.JSONDecodeError:
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] ⚠️ IMU data inválida (no es JSON).")
                return

        # --- Inicializar variables persistentes ---
        if not hasattr(self, "_last_imu_t"):
            self._last_imu_t = time.time()  
        if not hasattr(self, "vx"): 
            self.vx, self.vy, self.vz = 0.0, 0.0, 0.0
        if not hasattr(self, "x"): 
            self.x, self.y, self.z = 0.0, 0.0, 0.0
        if not hasattr(self, "roll"): 
            self.roll, self.pitch = 0.0, 0.0

        # === dt ===
        now = time.time()
        dt = now - self._last_imu_t
        self._last_imu_t = now
                    
        # === Lecturas crudas ===
        roll = imudata.get("r", 0)
        pitch = imudata.get("p", 0)
        ax = imudata.get("ax", 0)
        ay = imudata.get("ay", 0)
        az = imudata.get("az", 0)
        gx = imudata.get("gx", 0)
        gy = imudata.get("gy", 0)
        gz = imudata.get("gz", 0)

        # === Calcular orientación desde acelerómetro (inclinación absoluta) ===
        roll_acc = math.degrees(math.atan2(az, ay))
        pitch_acc = math.degrees(math.atan2(-ax, math.sqrt(ay**2 + az**2)))

        # Filtro complementario
        # if not hasattr(self, "roll"):
        #     self.roll, self.pitch = 0.0, 0.0
        # self.roll = alpha * (self.roll + gx * dt * 180 / math.pi) + (1 - alpha) * roll_acc
        # self.pitch = alpha * (self.pitch + gy * dt * 180 / math.pi) + (1 - alpha) * pitch_acc

        # === Compensar gravedad en eje principal (asumimos eje Y vertical) ===
        ay_corrected = ay + 9.81 if abs(ay) > abs(ax) and abs(ay) > abs(az) else ay

        # === Integrar aceleración para obtener velocidad y posición ===
        self.vx += ax * dt
        self.vy += ay_corrected * dt
        self.vz += az * dt

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        position = {"x": self.x, "y": self.y, "z": self.z}
        # self.on_position(position)

        # --- Detectar vuelco ---
        ROLLOVER_THRESHOLD = 60  # grados, ajustar según necesidad
        if abs(roll) > ROLLOVER_THRESHOLD or abs(pitch) > ROLLOVER_THRESHOLD:
            self.on_alert(f"⚠️ ¡Posible vuelco detectado! Roll: {roll:.1f}°, Pitch: {pitch:.1f}°")
            # notificar a quien esté escuchando
            self.on_overturn({
                "roll": roll,
                "pitch": pitch,
                "stable": False,
                "timestamp": time.time()
            })
        else:
            # por si quieres notificar que volvió a estar estable
            self.on_overturn({
                "roll": roll,
                "pitch": pitch,
                "stable": True,
                "timestamp": time.time()
            })

    # ---------- SENSOR PERIODICO ----------
    def temp_hum(self, sensordata):
        # El formato del mensaje es:
        # "Temp: 23.5°C, Hum: 58.0%"
        # parts = sensordata.replace("°C", "").replace("%", "").replace("Temp:", "").replace("Hum:", "")
        # temp_str, hum_str = parts.split(",")
        # temp = float(temp_str.strip())
        # hum = float(hum_str.strip())
        # self.on_periodic_sensor(temp,hum)

        try:
            temp_str, hum_str = sensordata.split(",")
            temp = float(temp_str.strip())
            hum = float(hum_str.strip())
            self.on_periodic_sensor(temp, hum)
        except Exception as e:
            self.on_alert(f"Error procesando datos de sensores en temp_hum: {e}")



    # # -------------------- WIFI --------------------
    # def take_picture(self):
    #     if self.camera is not None:
    #         self.stream.seek(0)
    #         self.stream.truncate()
    #         self.camera.capture(self.stream, format='jpeg')

    #         # Convertir a Base64
    #         img_b64 = base64.b64encode(self.stream.getvalue()).decode('utf-8')
    #         self.stream.truncate(0)

    #         return img_b64
    #     else:
    #         return None
    

    # ---------- pending list ----------
    def _load_pending_list(self):
        try:
            with open(self.pending_file, "r") as f:
                self.pending = json.load(f)
        except Exception:
            self.pending = []

    def _save_pending_list(self):
        with open(self.pending_file, "w") as f:
            json.dump(self.pending, f, indent=2)

    def _mark_pending(self, filepath):
        with self.pending_lock:
            if filepath not in self.pending:
                self.pending.append(filepath)
                self._save_pending_list()
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Archivo marcado como pendiente: {filepath}")

    def clear_pending(self, filepath):
        with self.pending_lock:
            if filepath in self.pending:
                self.pending.remove(filepath)
                self._save_pending_list()
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Archivo enviado/limpiado: {filepath}")

    # -------------------- FOTO --------------------
    def take_picture_and_save(self, quality_jpeg=80, max_lora_bytes=18000):
        """
        Toma una foto con Picamera2, la guarda en fotos/ y devuelve:
        (filename_on_disk, b64_string_if_small_or_None)
        Si la imagen es > max_lora_bytes se devuelve None como b64 y queda en pending.
        """
        if self.camera is None:
            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Cámara no disponible para foto.")
            return None, None

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.photo_dir, f"photo_{timestamp}.jpg")

            # Captura a archivo (más robusto que capturar en stream en algunas versiones)
            # Usamos capture_file para guardar directamente
            try:
                # picamera2 API: capture_file
                self.camera.start()
            except Exception:
                # start puede fallar si ya está arrancada; ignorar
                pass

            # capturar directamente en archivo
            try:
                self.camera.capture_file(filename, format="jpeg")
            except TypeError:
                # en algunas versiones capture_file acepta objecto, intentamos con IO
                buf = io.BytesIO()
                self.camera.capture_file(buf, format="jpeg")
                with open(filename, "wb") as f:
                    f.write(buf.getvalue())

            # Leer bytes
            with open(filename, "rb") as f:
                data = f.read()

            # Si el tamaño es pequeño, devolver base64 listo para enviar por LoRa
            if len(data) <= max_lora_bytes:
                b64 = base64.b64encode(data).decode("utf-8")
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Foto tomada y codificada (size {len(data)} bytes).")
                return filename, b64
            else:
                # Guardar como pendiente para envio por WiFi
                self._mark_pending(filename)
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Foto tomada (size {len(data)} bytes) — marcada pendiente (demasiado grande para LoRa).")
                return filename, None

        except Exception as e:
            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Error tomando foto: {e}")
            return None, None
    
    # ------ PROBAR ------
    def take_picture_and_save_compressed(self, photo_dest, max_lora_bytes=18000, quality=15):
        """
        Captura imagen usando capture_recording_optimized de LoRaCamSender.
        """
        img_bytes = self.lora_cam_sender.capture_recording_optimized()
        if img_bytes is not None:
            if len(img_bytes) <= 18000:  # tamaño máximo LoRa
                return img_bytes
            else:
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] ⚠️ Imagen demasiado grande para LoRa, marcada como pendiente.")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(self.photo_dir, f"photo_{timestamp}.jpg")
                with open(filename, "wb") as f:
                    f.write(img_bytes)
                self._mark_pending(filename)
                print(f"[{time.strftime('%H:%M:%S')}] Foto guardada y marcada como pendiente: {filename}")
                return None
        else:
            self.on_alert("⚠️ Error tomando foto.")
    
    # ---------- VIDEO ----------      
    def start_video_recording(self):
        """
        Captura vídeo usando video_recording_optimized de LoRaCamSender.
        """
        self.video_bytes = self.lora_cam_sender.video_recording_optimized()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.video_dir, f"video_{timestamp}.h264")
        with open(filename, "wb") as f:
            f.write(self.video_bytes)
        self._mark_pending(filename)
        print(f"[{time.strftime('%H:%M:%S')}] Vídeo guardado y marcado como pendiente: {filename}")
        self.video_bytes = None


    # ---------- UTILIDADES ----------
    def list_pending(self):
        """Devuelve lista actual de pendientes (ruta completa)."""
        self._load_pending_list()
        return list(self.pending)

    # -------------------- SENSORES --------------------
    def connect_sensors(self):
        try:
            self.sensores = serial.Serial(self.sens_port, self.sens_baudrate, timeout=2)
            time.sleep(2)
            print("[SENSORS] Conectado al ESP32 en", self.sens_port)
            return True
        except Exception as e:
            print(f"[SENSORS] ❌ Error abriendo puerto {self.sens_port}: {e}")
            return False
        
    def read_sensors_loop(self):
        """Lee datos de temperatura y humedad del ESP32 conectado por serie."""
        while self.running:
            try:
                line = self.sensores.readline().decode('utf-8', errors='ignore').strip()
                if line and line.startswith("H") and "T" in line:
                    # Ejemplo: "Humidity:72% Temperature:21°C"
                    parts = line.split()
                    self.hum = float(parts[0].split(':')[1].replace('%', ''))
                    self.temp = float(parts[1].split(':')[1].replace('°C', ''))

                    print(f"[{time.strftime('%H:%M:%S')}] [SENSORS] Temp={self.temp:.1f}°C | Hum={self.hum:.1f}%")

                    # self.send_message(self.sensor_dest, 0, 40, f"Temp: {self.temp:.1f}°C, Hum: {self.hum:.1f}%")
                    if hasattr(self, "sensor_dest"):
                        temp_str = parts[1].split(':')[1].replace('°C', '')
                        hum_str = parts[0].split(':')[1].replace('%', '')
                        self.send_message(self.sensor_dest, 0, 40, f"{temp_str},{hum_str}")
                    else:
                        print("⚠️ sensor_dest no existe, no se envía mensaje")
                        
                    # with get_db_session() as session:
                    #     registrar_lectura(self.temp, self.hum, session)

                    self.db.insert_sensor(id=self.addr, temp=self.temp, hum=self.hum)

            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] [SENSORS] Error leyendo ESP32: {e}")
            
            time.sleep(5) #cmabiar a 120 o lo que queramos

    def read_sensors_once(self):
        """Lee datos de temperatura y humedad del ESP32 conectado por serie una vez."""
        if self.running:
            try:
                line = self.sensores.readline().decode('utf-8', errors='ignore').strip()
                if line and line.startswith("H") and "T" in line:
                    parts = line.split()
                    self.hum = float(parts[0].split(':')[1].replace('%', ''))
                    self.temp = float(parts[1].split(':')[1].replace('°C', ''))

                    print(f"[{time.strftime('%H:%M:%S')}][SENSORS] Temp={self.temp:.1f}°C | Hum={self.hum:.1f}%")

                    # with get_db_session() as session:
                    #     registrar_lectura(self.temp, self.hum, session)

            except Exception as e:
                print(f"[SENSORS] Error leyendo ESP32: {e}")

    # -------------------- RADAR ------------------------

    # def listen_udp_radar(self):
    #     UDP_IP = "192.168.1.10"  # escucha en cualquier interfaz
    #     UDP_PORT = 5005
    #     self.radar_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     self.radar_sock.bind((UDP_IP, UDP_PORT))
    #     self.colision = 0 
    #     while self.running:
    #         try:
    #             data, addr = self.radar_sock.recvfrom(1024)
    #             try:
    #                 radar_val = int.from_bytes(data, byteorder='little')
    #             except:
    #                 continue
                
    #             if radar_val == 1:
    #                 self.colision = 1
    #                 print("⚠️ Alerta recibida por Ethernet, COLISIÓN DETECTADA -> STOP")
    #                 return self.colision
    #             else:
    #                 self.colision = 0
    #                 print("✔️ Alerta recibida por Ethernet, LIBRE -> START")
    #                 return self.colision
    #         except Exception as e:
    #             print(f"UDP listener error: {e}")

    # -------------------- LED ------------------------
    def control_led(self, orden: str):
        # Envia una orden al ESP32 por serial
        # try:
        #     self.sensores = serial.Serial(self.sens_port, self.sens_baudrate, timeout=2)
        #     time.sleep(2)
        #     print("[SENSORS] Conectado al ESP32 en", self.sens_port)
        # except Exception as e:
        #     print(f"[SENSORS] ❌ Error abriendo puerto {self.sens_port}: {e}")
        #     return
        # while self.running:
        try:
            if self.sensores and self.sensores.is_open:
                self.sensores.write((orden + "\n").encode())
                print(f"[{time.strftime('%H:%M:%S')}][LED] Orden enviada al ESP32: {orden}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}][LED] ❌ Puerto de sensores no está abierto.")
        except Exception as e:
            print(f"[LED] ❌ Error enviando orden al ESP32: {e}")

    # -------------------- BBDD --------------------
    def sinc_BBDD_loop(self):
        """Sincroniza datos pendientes con la BBDD en la base."""
        while self.running:
            try:
                with get_db_session() as session:
                    payload = sincronizar_sensores_lora(session)
                self.send_message(0xFFFF, 0, 20, payload)
            except Exception as e:
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Error sincronizando BBDD: {e}")
            time.sleep(30)  # cada 30 segundos

    def sync_BBDD_loop(self):
        """Sincroniza datos pendientes con la BBDD local."""
        while self.running:
            print(f"[{time.strftime('%H:%M:%S')}] Iniiciando sincronización.")
            packets = self.sync.prepare_packets()
            for pkt in packets:
                json_string = pkt.to_json()  # Este string es lo que envías por LoRa
                print(f"[{time.strftime('%H:%M:%S')}] Enviando: {json_string}")
                self.send_message(0xFFFF, 0, 20, json_string)
            time.sleep(12)

    def process_packet_base(self, json):
        """Procesa un paquete de BBDD recibido desde un nodo."""
        print(json)
        return self.sync_base.process_packet(json)

    def ack_BBDD_packet(self, json):
        """Marca un paquete de BBDD como recibido."""
        self.sync.handle_ack(json)

    # -------------------- WiFi --------------------
    def listen_robot(self, host="0.0.0.0", port=6000, save_path="./"):
        """
        Hilo que escucha comandos enviados por el robot.
        Maneja fotos y vídeos enviados por TCP.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, port))
        s.listen(5)
        print(f"Estación base escuchando en {host}:{port}...")

        while self.running:
            conn, addr = s.accept()
            print(f"Conexión desde {addr}")
            try:
                # Primero leemos el header: tipo de dato (PHOTO / VIDEO)
                header = conn.recv(10).decode().strip()  # suponiendo header <=10 chars
                print(f"📩 Tipo de dato recibido: {header}")

                # Luego leemos el tamaño (4 bytes)
                size_bytes = conn.recv(4)
                size = int.from_bytes(size_bytes, byteorder="big")
                print(f"📦 Tamaño de datos: {size} bytes")

                # Recibimos los datos completos
                data = b""
                while len(data) < size:
                    packet = conn.recv(4096)
                    if not packet:
                        break
                    data += packet

                # Guardamos según tipo
                if header == "PHOTO":
                    filename = save_path + "foto_recibida.jpg"
                    with open(filename, "wb") as f:
                        f.write(data)
                    print(f"📸 Foto guardada en {filename}")

                elif header == "VIDEO":
                    filename = save_path + "video_recibido.h264"
                    with open(filename, "wb") as f:
                        f.write(data)
                    print(f"🎥 Vídeo guardado en {filename}")

                else:
                    print("⚠️ Tipo de dato desconocido")

            except Exception as e:
                print(f"❌ Error recibiendo datos: {e}")
            finally:
                conn.close()
        s.close()

    # -------------------- EJECUCIÓN --------------------
    def run(self):
        receive_th = threading.Thread(target=self.receive_loop, daemon=True).start()            
        # -------------------- ROBOT --------------------
        if self.robot_port and self.robot_baudrate:
            flag_robot = self.connect_robot()
        # -------------------- RADAR --------------------

        # if (self.ip_sock is not None) and (self.port_sock is not None):
        #     radar_th = threading.Thread(target=self.listen_udp_radar, daemon=True).start()
        # -------------------- SENSORES --------------------
        if self.sens_port and self.sens_baudrate:
            self.connect_sensors()
            sensor_th = threading.Thread(target=self.read_sensors_loop, daemon=True).start()
        # -------------------- BBDD --------------------
        if not self.is_base:
            # crear_tablas()
            # bbdd_th = threading.Thread(target=self.sinc_BBDD_loop, daemon=True).start()
            data_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "datos")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "robot_data.db")
            if os.path.exists(db_path):
                os.remove(db_path)
            print("Creando BBDD SQLite.")
            self.db = RobotDatabase(db_path)
            self.sync = NodeSyncManager(self.db)
            bbdd_th = threading.Thread(target=self.sync_BBDD_loop, daemon=True).start()
        else:
            # connect_mongo()
            print("Conectando a MongoDB.")
            self.db_base = BaseStationDatabase()
            self.sync_base = BaseStationSyncManager(db=self.db_base)
        # -------------------- MuMULTIMEDIA --------------------
        if self.is_base:
            wifi_th = threading.Thread(target=self.listen_robot, daemon=True).start()
        # -------------------- INFO PERIODICA --------------------
        if self.is_base:
            status_th = threading.Thread(target=self.periodic_status, daemon=True).start()

        # if platform.system() != "Windows":
            # self.imu_thread = threading.Thread(target=self._get_imu_loop_raspi, daemon=True)
        # else:
        #     self.imu_thread = threading.Thread(target=self._get_imu_loop_EB, daemon=True)
        print(f"[{time.strftime('%H:%M:%S')}] LoRaNode running... Ctrl+C to stop")
        # try:
        #     while True:
        #         # self.receive_loop()
        #         time.sleep(1)
        # except KeyboardInterrupt:
        #     self.stop()
    

    def stop(self):
        print(f"[{time.strftime('%H:%M:%S')}] Stopping LoRaNode...")
        self.running = False
        time.sleep(0.2)
        if self.robot and self.robot.is_open:
            self.robot.close()
            self.sensores.close()
        self.node.close()


# recibir orden de gui para activar movimiento automatico
# cuando se reciba la orden, mandar comando de hacia adelante cada 3 segundos minimo
# si flag de colision = 1 mandar girar a la derecha (o random)
# 
# importante que si esta el movimiento automatico activado no se puedan mandar comandos de movimiento
#

