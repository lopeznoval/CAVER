# LoRaNode organizado
import io
import json
import queue
import time
import threading
from requests import session
import serial
from BBDD.lora_bridge import procesar_paquete_lora
from BBDDv1.registro_datos import registrar_lectura
from BBDDv1.database_SQLite import *
from BBDDv1.sincronizar_robot import sincronizar_sensores_lora
from sx126x_bis import sx126x
from parameters import *
import platform
import base64
import math
import socket

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
        self.sens_port = None
        self.sens_baudrate = None
        self.last_temp = None
        self.last_hum = None

        self.radar_sock = None
        self.ip_sock = ip_sock
        self.port_sock = port_sock

        if self.is_base:
            self.lock_nodes = threading.Lock()
            self.connected_nodes = {}
            self.node_timers = {}

        if platform.system() == "Linux":
            from picamera2 import PiCamera2 # type: ignore
            self.camera = PiCamera2()
            self.stream = io.BytesIO()
        else:
            self.camera = None
            self.stream = None

        self.on_alert = lambda alrt: print(f"⚠️ [ALERT] {alrt}")
        self.on_message = lambda msg: print(f"💬 [MESSAGE] {msg}")
        self.on_bytes = lambda data: print(f"📦 [BYTES] {data}")
        self.on_position = lambda pos: print(f"{pos}")
        self.on_sensor = lambda sensor: print(f"{sensor}")

    # -------------------- MENSAJES --------------------
    def pack_message(self, addr_dest:int, msg_type: int, msg_id: int, message: str, relay_flag: int =0) -> bytes:
        offset_freq = self.freq - 410 # assuming base freq is 410MHz
        header = bytes([
            (addr_dest >> 8) & 0xFF, addr_dest & 0xFF,
            (self.addr >> 8) & 0xFF, self.addr & 0xFF,
            (offset_freq & 0xFF),
            (relay_flag << 7) | (msg_type & 0x7F),
            msg_id & 0xFF
        ])
        print(f"Message size: {len(message.encode())} / Total size: {len(header) + len(message.encode())} bytes")
        if len(header) + len(message.encode()) > 255:
            raise ValueError("⚠️ Message too long to pack in just a LoRa packet.")
        return header + message.encode()

    def unpack_message(self, r_buff: bytes) -> tuple:
        if len(r_buff) < 7:
            print(f"⚠️ Paquete recibido demasiado corto: len={len(r_buff)} -> {r_buff}")
            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Paquete recibido demasiado corto")
            return None
        
        addr_dest = (r_buff[0] << 8) + r_buff[1]
        addr_sender = (r_buff[2] << 8) + r_buff[3]
        freq = r_buff[4]
        msg_type = r_buff[5] & 0x7F
        relay_flag = r_buff[5] >> 7
        msg_id = r_buff[6]
        message = r_buff[7:].decode(errors='ignore')

        print(f"Unpacked message: from {addr_sender} to {addr_dest}, type {msg_type}, id {msg_id}, relay {relay_flag}, msg: {message}")
        
        return addr_sender, addr_dest, msg_type, msg_id, relay_flag, message

    # -------------------- HILOS --------------------
    def periodic_status(self):
        while self.running:
            self.send_message(0xFFFF, 5, 0, "", 0)
            print(f"[{time.strftime('%H:%M:%S')}] PING enviado")
            time.sleep(30) # intervalos de 30 segundos entre envío y envío

    def send_message(self, addr_dest: int, msg_type: int, msg_id: int, message: str, relay_flag: int = 0, callback=None):
        data = self.pack_message(addr_dest, msg_type, msg_id, message, relay_flag)
        self.node.send_bytes(data)
        if self.is_base and addr_dest != 0xFFFF:
            self.add_pending(addr_dest, msg_id)

    def receive_loop(self):
        while self.running:
            msg = self.node.receive_bytes()
            if not msg:
                time.sleep(0.05)
                continue
            print("hay mensaje")
            threading.Thread(target=self.processing_loop, args=(msg,), daemon=True).start()

    def processing_loop(self, msg):
            try:
                addr_sender, addr_dest, msg_type, msg_id, relay_flag, message = self.unpack_message(msg)
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
                    self.on_message(f"[{time.strftime('%H:%M:%S')}] Received from {addr_sender} to {addr_dest}: {message} -SE DESCARTA-")
                    self.on_alert(f"[{time.strftime('%H:%M:%S')}] Received message not for this node (dest: {addr_dest}), discarding.")
                return            
            # -------------------- HANDLER DE TIPOS --------------------
            self.on_message(f"[{time.strftime('%H:%M:%S')}] Received from {addr_sender} to {addr_dest}: {message} -SE ACEPTA-")
            
            try: 
                # Mensajes tipo 0 -son los enviados por el robot directamente-, por lo que aquí se describe la lógica de recepción de datos
                if msg_type == 0:
                    if msg_id == 63: #imu
                        self.imu_pos(message)
                    elif msg_id == 69: 
                        if self.is_base:
                            resp = procesar_paquete_lora(message)
                            self.send_message(addr_sender, 4, msg_id, resp)
                
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
                    if msg_type == 13: # pedir o parar datos imu
                        if "1" in message:
                            print("llego el 1 para empezar")
                            if getattr(self, "imu_thread", None) and self.imu_thread.is_alive():
                                self.on_alert("⚠️ IMU loop ya estaba activo.")
                            else:
                                self.stop_imu_flag = False
                                self.imu_dest = addr_sender
                                self.imu_thread = threading.Thread(target=self._get_imu_loop_raspi, daemon=True)
                                self.imu_thread.start()
                                self.on_alert("🟢 IMU loop activado por EB.")
                        elif "0" in message:
                            self.stop_imu_flag = True
                            self.on_alert("🔴 IMU loop detenido por EB.")
                        else:
                            self.on_alert(f"⚠️ Comando IMU desconocido: {message}") 
                    
                    if msg_type == 14:
                        if "1" in message:
                            self.mov_aut_thread = threading.Thread(target=self._move_robot_loop, daemon=True)
                            self.mov_aut_thread.start()
                        elif "0" in message:
                            self.on_alert("🔴 IMU loop detenido por EB.")
                            self.mov_aut_thread.stop()
                        else: 
                            self.on_alert(f"⚠️ Comando movimiento autónomo desconocido: {message}") 


                    if self.robot.is_open and self.robot:
                        resp = self.send_to_robot(message)
                        self.send_message(addr_sender, 3, msg_id, resp)
                    else:
                        self.send_message(addr_sender, 3, msg_id, "Error: CAVER is not defined in this node.")
                    

                elif 19 < msg_type < 25:  # Comando para los sensores y BBDD
                    if msg_type == 21:  # Lectura temperatura y humedad
                        if self.on_sensor is None:
                            self.connect_sensors()
                            sensor_th = threading.Thread(target=self.read_sensors_loop, daemon=True)
                            sensor_th.start()
                        self.send_message(addr_sender, 4, msg_id, f"Temp: {self.temp:.1f}°C, Hum: {self.hum:.1f}%")
                    if msg_type == 22:  # Realizar lectura mandada por la EB
                        self.read_sensors_once()
                        self.send_message(addr_sender, 4, msg_id, f"Temp: {self.temp:.1f}°C, Hum: {self.hum:.1f}%")
                    if msg_type == 22:  # Sincronizar sensores pendientes
                        with get_db_session() as session:
                            sincronizar_sensores_lora(self, session)

                elif 24 < msg_type < 31:  # Comandos para cámara y radar
                    if msg_type == 30:  # Tomar foto
                            img_b64 = self.stream_recording()
                            self.send_message(addr_sender, 4, msg_id, img_b64)
                            print(f"[{time.strftime('%H:%M:%S')}] Foto enviada a {addr_sender}")

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
            print(f"Connected to robot on {self.robot_port}")
            self.robot.flushInput()
            self.robot_listener = threading.Thread(target=self.receive_from_robot)
            self.robot_listener.daemon = True
            self.robot_listener.start()
        except serial.SerialException as e:
            print(f"Failed to connect to robot: {e}")

    def receive_from_robot(self):
        while self.robot:
            data = self.robot.readline().decode('utf-8')
            if data:
                try:
                    print(f"Received from robot: {data}")
                    self.response_queue.put(data)  # Guarda cada respuesta
                except Exception as e:
                    print(f"Error reading: {e}")


    def send_to_robot(self, command: str) -> str:
        """Envía un comando al robot y devuelve la respuesta."""
        if self.running and self.robot and self.robot.is_open:
            self.robot.reset_input_buffer()
            self.robot.write((command + "\r\n").encode('utf-8'))
            print("Enviando comando al robot.")  
            try:
                response = self.response_queue.get(timeout=5)
                return response
            except queue.Empty:
                return "OK"
        else:
            return "OK"
        
    def _get_imu_loop_raspi(self): # IMU
        while not getattr(self, "stop_imu_flag", False):
            try:
                imu_data = self.send_to_robot("{\"T\":126}")
                if imu_data:
                    self.send_message(self.imu_dest, 0, 63, imu_data)
                time.sleep(10)
                # time.sleep(40)
            except Exception as e:
                self.on_alert(f"Error en IMU loop: {e}")
                time.sleep(2)
        self.on_alert("IMU loop finalizado.")
    
    def _move_robot_loop(self): # Movimiento autonomo
        while True:
            try:
                commands = {
                    "forward": {"T": 1, "L": 0.5, "R": 0.5},
                        "backward": {"T": 1, "L": -0.5, "R": -0.5},
                        "left": {"T": 1, "L": -0.3, "R": 0.3},
                        "right": {"T": 1, "L": 0.3, "R": -0.3},
                        "stop": {"T": 1, "L": 0, "R": 0},
                    }
                
                self.send_to_robot(0, 0, json.dumps({"T": 1, "L": 0.5, "R": 0.5}))
                if self.colision == 1:
                    direction = "right"
                    cmd = commands.get(direction)
                    json.dumps(cmd)
                    self.send_to_robot(0, 0, cmd)
                time.sleep(3)
            except Exception as e:
                self.on_alert(f"Error en movimiento autonomo loop: {e}")
                time.sleep(2)

    # ------------------------------ IMU ------------------------------
    #  Se asume respuesta asi:
    # {"T":1002, "r":-89.04126934, "p":-0.895245861, "ax":-0.156085625, "ay":-9.987277031, "az":0.167132765, 
    # "gx":0.00786881, "gy":0.0033449, "gz":0.00259476, "mx":1.261048317, "my":-14.89113426, "mz":118.1274872, "temp":30.20118523}
    
    def imu_pos(self, imudata):
        """
        Calcula posición y orientación estimada a partir de ax, ay, az, gx, gy, gz.
        """        
        dt = 0.05  # periodo 50 ms
        alpha = 0.98  # peso del giroscopio

        # --- Decodificar JSON ---
        if isinstance(imudata, str):
            try:
                imudata = json.loads(imudata)
            except json.JSONDecodeError:
                self.on_alert("⚠️ IMU data inválida (no es JSON).")
                return

        # --- Inicializar variables persistentes ---
        if not hasattr(self, "vx"): 
            self.vx, self.vy, self.vz = 0.0, 0.0, 0.0
        if not hasattr(self, "x"): 
            self.x, self.y, self.z = 0.0, 0.0, 0.0
        if not hasattr(self, "roll"): 
            self.roll, self.pitch = 0.0, 0.0
                
        # === Lecturas crudas ===
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
        if not hasattr(self, "roll"):
            self.roll, self.pitch = 0.0, 0.0
        self.roll = alpha * (self.roll + gx * dt * 180 / math.pi) + (1 - alpha) * roll_acc
        self.pitch = alpha * (self.pitch + gy * dt * 180 / math.pi) + (1 - alpha) * pitch_acc

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
        self.on_position(position)

        # --- Detectar vuelco ---
        ROLLOVER_THRESHOLD = 60  # grados, ajustar según necesidad
        if abs(self.roll) > ROLLOVER_THRESHOLD or abs(self.pitch) > ROLLOVER_THRESHOLD:
            self.on_alert(f"⚠️ ¡Posible vuelco detectado! Roll: {self.roll:.1f}°, Pitch: {self.pitch:.1f}°")

                     
    # -------------------- VÍDEO --------------------
    def stream_recording(self):
        if self.camera is not None:
            self.stream.seek(0)
            self.stream.truncate()
            self.camera.capture(self.stream, format='jpeg')

            # Convertir a Base64
            img_b64 = base64.b64encode(self.stream.getvalue()).decode('utf-8')
            self.stream.truncate(0)

            return img_b64
        else:
            return None
        
    # -------------------- SENSORES --------------------
    def connect_sensors(self):
        try:
            self.sensores = serial.Serial(self.sens_port, self.sens_baudrate, timeout=2)
            time.sleep(2)
            print("[SENSORS] Conectado al ESP32 en", self.sens_port)
        except Exception as e:
            print(f"[SENSORS] ❌ Error abriendo puerto {self.sens_port}: {e}")
            return
        
    def read_sensors_loop(self):
        """Lee datos de temperatura y humedad del ESP32 conectado por serie."""
        while self.running:
            try:
                line = self.sensores.readline().decode('utf-8', errors='ignore').strip()
                if line and line.startswith("H") and "T" in line:
                    parts = line.split()
                    self.hum = float(parts[0].split(':')[1].replace('%', ''))
                    self.temp = float(parts[1].split(':')[1].replace('°C', ''))

                    print(f"[SENSORS] Temp={self.temp:.1f}°C | Hum={self.hum:.1f}%")

                    with get_db_session() as session:
                        registrar_lectura(self.temp, self.hum, session)

            except Exception as e:
                print(f"[SENSORS] Error leyendo ESP32: {e}")
            
            time.sleep(120)

    def read_sensors_once(self):
        """Lee datos de temperatura y humedad del ESP32 conectado por serie una vez."""
        if self.running:
            try:
                line = self.sensores.readline().decode('utf-8', errors='ignore').strip()
                if line and line.startswith("H") and "T" in line:
                    parts = line.split()
                    self.hum = float(parts[0].split(':')[1].replace('%', ''))
                    self.temp = float(parts[1].split(':')[1].replace('°C', ''))

                    print(f"[SENSORS] Temp={self.temp:.1f}°C | Hum={self.hum:.1f}%")

                    with get_db_session() as session:
                        registrar_lectura(self.temp, self.hum, session)

            except Exception as e:
                print(f"[SENSORS] Error leyendo ESP32: {e}")

    # -------------------- RADAR ------------------------
    def listen_udp_radar(self):
        self.radar_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.radar_sock.bind((self.ip_sock, self.port_sock))
        while self.running:
            try:
                data, addr = self.radar_sock.recvfrom(1024)
                if data.decode() == "STOP_ROBOT":
                    self.colision = 1
                    print("⚠️ Alerta recibida por Ethernet, deteniendo robot")
                    # command = "{\"T\": 1, \"L\": 0, \"R\": 0}"
                    # resp = self.send_to_robot(0, 0, command)
            except Exception as e:
                print(f"UDP listener error: {e}")

    # -------------------- BBDD --------------------
    def sinc_BBDD_loop(self):
        """Función para sincronizar datos de sensores con la base de datos."""
        while self.running:
            print("--- Iniciando ciclo de sincronización dual ---")
            with get_db_session() as session:
                packet_str = sincronizar_sensores_lora(session) 
                self.send_message(0xFFFF, 0, 69, packet_str)
                
            print("--- Ciclo de sincronización finalizado ---")
            time.sleep(60)  # Esperar 60 segundos antes del siguiente ciclo

    
    
    # -------------------- EJECUCIÓN --------------------
    def run(self):
        receive_th = threading.Thread(target=self.receive_loop, daemon=True).start()
        # -------------------- ROBOT --------------------
        if self.robot_port and self.robot_baudrate:
            self.connect_robot()
        # -------------------- RADAR --------------------
        if (self.ip_sock is not None) and (self.port_sock is not None):
            radar_th = threading.Thread(target=self.listen_udp_radar, daemon=True).start()
        # -------------------- SENSORES --------------------
        if self.sens_port and self.sens_baudrate:
            self.connect_sensors()
            sensor_th = threading.Thread(target=self.read_sensors_loop, daemon=True).start()
        # -------------------- BBDD --------------------
        if not self.is_base:
            crear_tablas()
            bbdd_th = threading.Thread(target=self.sinc_BBDD_loop, daemon=True).start()
        # -------------------- INFO PERIODICA --------------------
        if self.is_base:
            status_th = threading.Thread(target=self.periodic_status, daemon=True).start()

        # if platform.system() != "Windows":
            # self.imu_thread = threading.Thread(target=self._get_imu_loop_raspi, daemon=True)
        # else:
        #     self.imu_thread = threading.Thread(target=self._get_imu_loop_EB, daemon=True)
        print("LoRaNode running... Ctrl+C to stop")
        # try:
        #     while True:
        #         # self.receive_loop()
        #         time.sleep(1)
        # except KeyboardInterrupt:
        #     self.stop()
    

    def stop(self):
        print("Stopping LoRaNode...")
        self.running = False
        time.sleep(0.2)
        if self.robot and self.robot.is_open:
            self.robot.close()
        self.node.close()


# recibir orden de gui para activar movimiento automatico
# cuando se reciba la orden, mandar comando de hacia adelante cada 3 segundos minimo
# si flag de colision = 1 mandar girar a la derecha (o random)
# 
# importante que si esta el movimiento automatico activado no se puedan mandar comandos de movimiento
#

