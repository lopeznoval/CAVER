# LoRaNode organizado
import time
import threading
import serial
from sx126x_bis import sx126x
from parameters import *

class LoRaNode:
    def __init__(self, ser_port, addr, freq=433, pw=0, rssi=True, EB=0, robot_port=None, robot_baudrate=None):  # EB = 1 si es estación base
        self.running = True
        self.node = sx126x(serial_num=ser_port, freq=freq,
                           addr=addr, power=pw, rssi=rssi)
        print(f"LoRaNode initialized on {ser_port} with address {addr}, freq {freq}MHz, power {pw}dBm")
        self.pending_requests = {}                                  # msg_id -> callback/event
        self.lock = threading.Lock()
        self.robot = None
        self.EB = EB  # External Board reference

        self.addr = addr
        self.freq = freq
        self.power = pw

        self.robot_port = robot_port
        self.robot_baudrate = robot_baudrate

    # -------------------- SERIAL ROBOT --------------------
    def connect_robot(self):
        try:
            self.robot = serial.Serial(self.robot_port, self.robot_baudrate, timeout=1)
            print(f"Connected to robot on {self.robot_port}")
            self.robot_listener = threading.Thread(target=self.receive_from_robot)
            self.robot_listener.daemon = True
            self.robot_listener.start()
        except serial.SerialException as e:
            print(f"Failed to connect to robot: {e}")

    def receive_from_robot(self):
        while self.running and self.robot and self.robot.is_open:
            data = self.robot.readline().decode('utf-8').strip()
            if data:
                print(f"Received from robot: {data}")

    def send_to_robot(self, command):
        if self.robot and self.robot.is_open:
            self.robot.write(command.encode())

    # -------------------- MENSAJES --------------------
    def pack_message(self, addr_dest, msg_type, msg_id, message, relay_flag=0):
        offset_freq = self.freq - 410 # assuming base freq is 410MHz
        header = bytes([
            (addr_dest >> 8) & 0xFF, addr_dest & 0xFF,
            (self.addr >> 8) & 0xFF, self.addr & 0xFF,
            (offset_freq & 0xFF),
            (relay_flag << 7) | (msg_type & 0x7F),
            msg_id & 0xFF
        ])
        return header + message.encode()

    def unpack_message(self, r_buff):
        addr_dest = (r_buff[0] << 8) + r_buff[1]
        addr_sender = (r_buff[2] << 8) + r_buff[3]
        freq = r_buff[4]
        msg_type = r_buff[5] & 0x7F
        relay_flag = r_buff[5] >> 7
        msg_id = r_buff[6]
        message = r_buff[7:].decode(errors='ignore')
        return addr_sender, addr_dest, msg_type, msg_id, relay_flag, message

    # -------------------- HILOS --------------------
    def periodic_send(self, node_address=0xFFFF, msg_type=TYPE_MSG, msg_id=ID_MSG):
        count = 0
        while self.running:
            msg = f"Auto-message #{count} from {self.addr}"
            data = self.pack_message(node_address, msg_type, msg_id, msg)
            self.node.send_bytes(data)
            print(f"[{time.strftime('%H:%M:%S')}] Sent: {msg}")
            count += 1
            time.sleep(6) # intervalos de 6 segundos entre envío y envío

    def send_message(self, addr_dest, msg_type, msg_id, message, relay_flag=0, callback=None):
        data = self.pack_message(addr_dest, msg_type, msg_id, message, relay_flag)
        self.node.send_bytes(data)
        if callback:
            with self.lock:
                self.pending_requests[msg_id] = callback

    def receive_loop(self):
        while self.running:
            msg = self.node.receive_bytes()
            if not msg:
                time.sleep(0.05)
                continue            # salgo del loop si no hay mensaje
            addr_sender, addr_dest, msg_type, msg_id, relay_flag, message = self.unpack_message(msg)
            print(f"[{time.strftime('%H:%M:%S')}] Received from {addr_sender}: {message}")
            if addr_dest != self.addr:
                continue            # No es para este nodo (hay que poner la lógica del relay aquí)
            # -------------------- HANDLER DE TIPOS --------------------
            if msg_type == 1:  # Respuesta
                with self.lock:
                    if msg_id in self.pending_requests:
                        callback = self.pending_requests.pop(msg_id)
                        callback(message)           
            elif msg_type == 6:  # Comando de orden al robot
                self.send_to_robot(message)
                # Enviar ACK
                ack = self.pack_message(addr_sender, 1, msg_id, "OK")
                self.node.send(ack)


    # -------------------- EJECUCIÓN --------------------
    def run(self):
        if self.robot_port and self.robot_baudrate:
            self.connect_robot()
        threading.Thread(target=self.periodic_send, daemon=True).start()
        threading.Thread(target=self.receive_loop, daemon=True).start()
        print("LoRaNode running... Ctrl+C to stop")
        try:
            while True:
                if self.EB:
                    # Estación base puede hacer otras tareas
                    pass
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        print("Stopping LoRaNode...")
        self.running = False
        time.sleep(0.2)
        if self.robot and self.robot.is_open:
            self.robot.close()
        self.node.close()
