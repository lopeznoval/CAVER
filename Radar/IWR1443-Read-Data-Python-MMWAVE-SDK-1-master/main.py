# main.py
import time
from iwr1443 import IWR1443


# --- Windows ---
# cli_port = 'COM19'
# data_port = 'COM18'
# config_file = r"C:\Users\paula\OneDrive\Escritorio\TELECO\2 Master\CAVER\Radar\IWR1443-Read-Data-Python-MMWAVE-SDK-1-master\1443config.cfg"

# --- Raspberry Pi ---
cli_port = '/dev/ttyACM0'
data_port = '/dev/ttyACM1'
config_file = '/home/pi/1443config.cfg'

# Configuración del radar
radar = IWR1443(
    cli_port_name=cli_port,
    data_port_name=data_port,
    config_file=config_file
)

# Inicialización
radar.serial_config()
radar.parse_config_file()

frameData = {}
currentIndex = 0

# Bucle principal
while True:
    try:
        dataOk = radar.update()
        if dataOk and radar.detObj:
            frameData[currentIndex] = radar.detObj
            currentIndex += 1
        time.sleep(0.033)  # Frecuencia de muestreo ~30Hz
    except KeyboardInterrupt:
        radar.CLIport.write(('sensorStop\n').encode())
        radar.CLIport.close()
        radar.Dataport.close()
        break
