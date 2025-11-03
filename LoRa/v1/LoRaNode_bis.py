# LoRaNode organizado
import io
import json
import time
import threading
import serial
from sx126x_bis import sx126x
from parameters import *
import platform
import base64

class LoRaNode:
    def __init__(self, ser_port, addr, freq=433, pw=0, rssi=True, EB=0, robot_port=None, robot_baudrate=None):  # EB = 1 si es estación base
        self.running = True
        self.node = sx126x(serial_num=ser_port, freq=freq,
                           addr=addr, power=pw, rssi=rssi)
        print(f"LoRaNode initialized on {ser_port} with address {addr}, freq {freq}MHz, power {pw}dBm")
        self.pending_requests = {}                                  # msg_id -> callback/event
        self.lock = threading.Lock()
        self.robot = None
        self.is_base = EB  # External Board reference
        self.is_relay = False

        self.addr = addr
        self.freq = freq
        self.power = pw

        self.robot_port = robot_port
        self.robot_baudrate = robot_baudrate

        self.on_alert = lambda alrt: print(f"⚠️ [ALERT] {alrt}")
        self.on_message = lambda msg: print(f"💬 [MESSAGE] {msg}")
        self.on_bytes = lambda data: print(f"📦 [BYTES] {data}")

        # if platform.system() == "Linux":
        #     from picamera2 import PiCamera2 # type: ignore
        #     self.camera = PiCamera2()
        #     self.stream = io.BytesIO()
        # else:
        #     self.camera = None
        #     self.stream = None

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
    def periodic_send(self, node_address: int = 0xFFFF, msg_type: int = TYPE_MSG, msg_id: int = ID_MSG):
        count = 0
        while self.running:
            msg = f"Auto-message #{count} from {self.addr}"
            data = self.pack_message(node_address, msg_type, msg_id, msg)
            self.node.send_bytes(data)
            print(f"[{time.strftime('%H:%M:%S')}] Sent: {msg}, con data: {data}")
            count += 1
            time.sleep(6) # intervalos de 6 segundos entre envío y envío

    def send_message(self, addr_dest: int, msg_type: int, msg_id: int, message: str, relay_flag: int = 0, callback=None):
        data = self.pack_message(addr_dest, msg_type, msg_id, message, relay_flag)
        self.node.send_bytes(data)
        if self.is_base:
            self.add_pending(addr_dest, msg_id)

    def receive_loop(self):
        while self.running:
            msg = self.node.receive_bytes()
            if not msg:
                time.sleep(0.05)
                continue            # salgo del loop si no hay mensaje
            try:
                addr_sender, addr_dest, msg_type, msg_id, relay_flag, message = self.unpack_message(msg)
            except Exception as e:
                print(f"Error unpacking message: {e}")
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Error unpacking message")
                continue
            print(f"[{time.strftime('%H:%M:%S')}] Received from {addr_sender}: {message}")
            
            if addr_dest != self.addr and addr_dest != 0xFFFF:
                if self.is_relay:
                    print(f"Relaying message from {addr_sender} to {addr_dest}")
                    self.on_alert(f"[{time.strftime('%H:%M:%S')}] Relaying message from {addr_sender} to {addr_dest}")
                    self.send_message(addr_dest, msg_type, msg_id, message)
                else:
                    self.on_message(f"[{time.strftime('%H:%M:%S')}] Received from {addr_sender} to {addr_dest}: {message} -SE DESCARTA-")
                    self.on_alert(f"[{time.strftime('%H:%M:%S')}] Received message not for this node (dest: {addr_dest}), discarding.")
                continue            
            # -------------------- HANDLER DE TIPOS --------------------
            self.on_message(f"[{time.strftime('%H:%M:%S')}] Received from {addr_sender} to {addr_dest}: {message} -SE ACEPTA-")
            
            try:    
                if 1 < msg_type < 5:  # Respuesta
                    with self.lock:
                        rm = self.remove_pending(addr_sender, msg_id)
                        if not rm:
                            self.on_alert(f"[{time.strftime('%H:%M:%S')}] Received response of msg_id {msg_id} from {addr_sender} to {addr_dest}")
                            continue
                    self.on_alert(f"[{time.strftime('%H:%M:%S')}] Received response of msg_id {msg_id} from {addr_sender} : {msg}")
                    continue

                elif 4 < msg_type < 10:  # Comandos generales
                    if msg_type == 5:  # Ping
                        resp = "PONG"
                        self.send_message(addr_sender, 2, msg_id, resp)
                    elif msg_type == 6:  # Status
                        status = f"Node {self.addr} OK. Freq: {self.freq} MHz, Power: {self.power} dBm"
                        self.send_message(addr_sender, 2, msg_id, status)
                    elif msg_type == 7:  # Stop
                        self.stop()
                        resp = "Node stopping..."
                        self.send_message(addr_sender, 2, msg_id, resp)
                    elif msg_type == 8: # Relay mode activation
                        self.send_message(addr_sender, 2, msg_id, str(self.is_relay))
                    elif msg_type == 9: # Check RSSI
                        ...

                elif 9 < msg_type < 20:  # Comandos hacia el robot
                    if self.robot.is_open and self.robot:
                        self.send_to_robot(addr_dest, msg_id, message) # resp = 
                        self.send_message(addr_sender, 3, msg_id, "OK")
                    else:
                        self.send_message(addr_sender, 3, msg_id, "Error: CAVER is not defined in this node.")

                elif 19 < msg_type < 25:  # Comando para los sensores
                    ...

                elif 24 < msg_type < 31:  # Comandos para cámara y radar
                    if msg_type == 30:  # Tomar foto
                            img_b64 = self.stream_recording()
                            data = self.pack_message(addr_sender, 31, msg_id, img_b64)
                            self.node.send_bytes(data)
                            print(f"[{time.strftime('%H:%M:%S')}] Foto enviada a {addr_sender}")

                elif msg_type == 31:
                    print("Relay mode set to: ", relay_flag)
                    self.is_relay = bool(relay_flag)
                    self.node.send_bytes(self.pack_message(addr_sender, 1, msg_id, "OK")) 

            except Exception as e:
                self.on_alert(f"Error processing message: {e}")

            finally:
                self.on_alert(f"[{time.strftime('%H:%M:%S')}] Finished processing message.")
                time.sleep(0.1)

    # ------------------- PENDING REQUESTS -----------------

    def add_pending(self, addr_dest: int, msg_id: int):
        with self.lock:
            self.pending_requests.setdefault(addr_dest, []).append(msg_id)
        self.on_alert(f"[{time.strftime('%H:%M:%S')}] Added pending request: {msg_id} to {addr_dest}")

    def remove_pending(self, addr_dest: int, msg_id: int) -> bool:
        with self.lock:
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

    # -------------------- SERIAL ROBOT --------------------
    def connect_robot(self):
        try:
            self.robot = serial.Serial(self.robot_port, self.robot_baudrate, timeout=1, dsrdtr=None)
            self.robot.setRTS(False)
            self.robot.setDTR(False)
            print(f"Connected to robot on {self.robot_port}")
            # self.robot_listener = threading.Thread(target=self.receive_from_robot)
            # self.robot_listener.daemon = True
            # self.robot_listener.start()
        except serial.SerialException as e:
            print(f"Failed to connect to robot: {e}")

    def receive_from_robot(self):
        while self.running and self.robot and self.robot.is_open:
            data = self.robot.readline().decode('utf-8').strip()
            if data:
                print(f"Received from robot: {data}")

    def send_to_robot(self, addres_dest, msg_id, command: str) -> str:
        """Envía un comando al robot y devuelve la respuesta."""
        if self.running and self.robot and self.robot.is_open:
            self.robot.reset_input_buffer()
            self.robot.write((command + "\n").encode('utf-8'))
            print("Enviando comando al robot.")
            time.sleep(0.1)  
            response = self.robot.readline().decode('utf-8') #.strip()
            if response:
                try:
                    return response
                except json.JSONDecodeError:
                    print("Error decoding JSON from robot response.")
            else:
                print("No response from robot.")  

                     
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
        self.sensores = serial.Serial('/dev/ttyUSB0', 115200, timeout=2)  # Ajusta el puerto
        time.sleep(2)  # Espera a que el puerto inicialice
        print("Connected to sensors on /dev/ttyUSB0.\n")

    # -------------------- RADAR ------------------------
    def connect_radar(self):
        # self.CLIport = serial.Serial('COM6', 115200)
        # self.Dataport = serial.Serial('COM7', 921600)
        print("Connected to radar on COM6 and COM7.\n")

    # -------------------- EJECUCIÓN --------------------
    def run(self):
        if self.robot_port and self.robot_baudrate:
            self.connect_robot()
        # threading.Thread(target=self.periodic_send, daemon=True).start()
        threading.Thread(target=self.receive_loop, daemon=True).start()
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
