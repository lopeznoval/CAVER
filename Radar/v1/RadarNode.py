import time
import socket
from iwr1443 import IWR1443

# --- Configuración Radar ---
cli_port = '/dev/ttyACM0'
data_port = '/dev/ttyACM1'
config_file = '/home/pi/1443config.cfg'

radar = IWR1443(
    cli_port_name=cli_port,
    data_port_name=data_port,
    config_file=config_file
)

radar.serial_config()
radar.parse_config_file()

# --- Configuración UDP para enviar alertas ---
UDP_IP = "192.168.1.100"  # IP de la Pi con LoRaNode
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

frameData = {}
currentIndex = 0

while True:
    try:
        dataOk, radar_collision_stop = radar.update()
        if dataOk and radar.detObj:
            frameData[currentIndex] = radar.detObj
            currentIndex += 1

        # if any(r < radar.STOP_DISTANCE_THRESHOLD for r in radar.detObj["range"]):

        if radar_collision_stop == 1:
            print("⚠️ Objeto detectado cerca, enviando alerta a Pi LoRaNode...")
            sock.sendto(b"STOP_ROBOT", (UDP_IP, UDP_PORT))

        time.sleep(0.033)  # ~30 Hz
    except KeyboardInterrupt:
        radar.CLIport.write(('sensorStop\n').encode())
        radar.CLIport.close()
        radar.Dataport.close()
        break
