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

        # if any(r < radar.STOP_DISTANCE_THRESHOLD for r in radar.detObj["range"]):

        if radar_collision_stop == 1:
            print("⚠️ Objeto detectado cerca, enviando alerta a Pi LoRaNode...")
            sock.sendto(b"1", (UDP_IP, UDP_PORT))
        elif radar_collision_stop == 0: 
            sock.sendto(b"0", (UDP_IP, UDP_PORT))

        # collisions_array = np.insert(collisions_array, 0, radar_collision_stop)
        # if collisions_array.size > 10:
        #     collisions_array = collisions_array[:-1]  # elimina el último
        
        # if np.sum(collisions_array) >= 6 and last_state != 1:
        #     last_state = 1
        #     print("⚠️ Objeto detectado cerca, enviando alerta a Pi LoRaNode...")
        #     sock.sendto(b"STOP_ROBOT", (UDP_IP, UDP_PORT))
        # elif np.sum(collisions_array) < 4 and last_state != 0: 
        #     last_state = 0
        #     sock.sendto(b"START_ROBOT", (UDP_IP, UDP_PORT))
                
        # sock.sendto(radar_collision_stop, (UDP_IP, UDP_PORT))


        time.sleep(0.033)  # ~30 Hz

    # Propuesta para detectar cambios de estado y enviar alerta solo al cambiar
    # last_state = None

    # while True:
    #     try:
    #         dataOk, radar_collision_stop = radar.update()
            
    #         if dataOk and radar.detObj:
    #             frameData[currentIndex] = radar.detObj
    #             currentIndex += 1

    #         # Si cambia el estado, enviamos alerta
    #         if radar_collision_stop != last_state:
    #             last_state = radar_collision_stop
                
    #             if radar_collision_stop == 1:
    #                 print("⚠️ Objeto cerca → STOP_ROBOT")
    #                 sock.sendto(b"STOP_ROBOT", (UDP_IP, UDP_PORT))
    #             else:
    #                 print("✔️ Camino libre → START_ROBOT")
    #                 sock.sendto(b"START_ROBOT", (UDP_IP, UDP_PORT))

    #         time.sleep(0.033)  # ~30 Hz loop
    except KeyboardInterrupt:
        radar.CLIport.write(('sensorStop\n').encode())
        radar.CLIport.close()
        radar.Dataport.close()
        sock.close()
        break



