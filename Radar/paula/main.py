
from IWR1443 import IWR1443
import time

# Crear instancia
# CONFIG_FILE = r"C:\Users\paula\OneDrive\Escritorio\TELECO\2 Master\CAVER\Radar\paula\configuracionCAVER.cfg"
CONFIG_FILE = r"C:\Users\paula\OneDrive\Escritorio\TELECO\2 Master\CAVER\Radar\paula\configuracionCAVER2.cfg"
# CONFIG_FILE = r"C:\Users\paula\OneDrive\Escritorio\TELECO\2 Master\CAVER\Radar\IWR1443-Read-Data-Python-MMWAVE-SDK-1-master\1443config.cfg"

radar = IWR1443(CONFIG_FILE, cli_port='COM19', data_port='COM18')

# Configurar el radar
radar.serial_config()

# Parsear archivo de configuración
radar.parse_config_file()

print("Iniciando lectura continua...")

try:
    while True:
        # Leer datos del puerto serie
        if radar.read_data():
            # Parsear los paquetes si hay datos
            success, detections = radar.parse_packets()
            if success:
                print(f"Objetos detectados: {detections['numObj']}")
                print("X:", detections['x'])
                print("Y:", detections['y'])
                print("Z:", detections['z'])
        time.sleep(0.01)  # pequeña pausa para no saturar la CPU

except KeyboardInterrupt:
    print("Detención del radar por teclado")
