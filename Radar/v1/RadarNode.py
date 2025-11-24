import time
import socket
from iwr1443 import IWR1443
import numpy as np

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
# collisions_array = np.array([], dtype=int)
# last_state = 0

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

        if radar_collision_stop == 1:
            print("⚠️ Objeto detectado cerca, enviando alerta a Pi LoRaNode...")
            sock.sendto(b"1", (UDP_IP, UDP_PORT))
        elif radar_collision_stop == 0: 
            sock.sendto(b"0", (UDP_IP, UDP_PORT))

        time.sleep(0.033)  # ~30 Hz

    except KeyboardInterrupt:
        radar.CLIport.write(('sensorStop\n').encode())
        radar.CLIport.close()
        radar.Dataport.close()
        sock.close()
        break



