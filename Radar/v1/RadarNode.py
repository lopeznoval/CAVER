import time
import socket
from iwr1443 import IWR1443

# --- Configuración Radar ---
cli_port = '/dev/ttyACM0'
data_port = '/dev/ttyACM1'
config_file = '/home/masterpi1/Desktop/CAVER/Radar/v1/1443config.cfg'

radar = IWR1443(
    cli_port_name=cli_port,
    data_port_name=data_port,
    config_file=config_file
)

radar.serial_config()
radar.parse_config_file()

# --- Configuración UDP para enviar alertas ---
UDP_IP = "192.168.1.10"  # IP de la Pi con LoRaNode
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

frameData = {}
currentIndex = 0

# --- Estado y contadores ---
state = "RUNNING"  # o "STOPPED", dependiendo de cómo arranque tu robot
count_ones = 0
count_zeros = 0
MIN_COUNT = 6      

while True:
    try:
        dataOk, radar_collision_stop = radar.update()
        if dataOk and radar.detObj:
            frameData[currentIndex] = radar.detObj
            currentIndex += 1

        # ---- LÓGICA DE FILTRADO DE 1s / 0s ----
        if radar_collision_stop == 1:
            count_ones += 1
            count_zeros = 0
        else:
            count_zeros += 1
            count_ones = 0

        # if any(r < radar.STOP_DISTANCE_THRESHOLD for r in radar.detObj["range"]):

        # if radar_collision_stop == 1:
        #     print("⚠️ Objeto detectado cerca, enviando alerta a Pi LoRaNode...")
        #     # sock.sendto(b"STOP_ROBOT", (UDP_IP, UDP_PORT))
        #     try:
        #         sock.sendto(b"1", (UDP_IP, UDP_PORT))
        #     except BlockingIOError:
        #         print("⚠️ Buffer lleno, mensaje no enviado.")

        # elif radar_collision_stop == 0: 
        #     # sock.sendto(b"START_ROBOT", (UDP_IP, UDP_PORT))
        #     try:
        #         sock.sendto(b"0", (UDP_IP, UDP_PORT))
        #     except BlockingIOError:
        #         print("⚠️ Buffer lleno, mensaje no enviado.")
                
        # # sock.sendto(radar_collision_stop, (UDP_IP, UDP_PORT))


        # time.sleep(0.033)  # ~30 Hz
        
        # ---- Enviar STOP cuando haya 6 unos seguidos ----
        if count_ones >= MIN_COUNT and state != "STOPPED":
            print("⚠️ Objeto detectado cerca (6 unos), enviando STOP...")
            try:
                sock.sendto(b"1", (UDP_IP, UDP_PORT))
            except BlockingIOError:
                print("⚠️ Buffer UDP lleno, STOP no enviado.")
            state = "STOPPED"

        # ---- Enviar START cuando haya 6 ceros seguidos ----
        if count_zeros >= MIN_COUNT and state != "RUNNING":
            print("🟢 Zona despejada (6 ceros), enviando START...")
            try:
                sock.sendto(b"0", (UDP_IP, UDP_PORT))
            except BlockingIOError:
                print("⚠️ Buffer UDP lleno, START no enviado.")
            state = "RUNNING"

        time.sleep(0.033)



    except KeyboardInterrupt:
        radar.CLIport.write(('sensorStop\n').encode())
        radar.CLIport.close()
        radar.Dataport.close()
        sock.close()
        break



