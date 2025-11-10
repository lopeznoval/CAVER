# clase IWR1443 

# Configura los puertos serie.
# Lee y parsea los datos binarios del radar.
# Devuelve las detecciones procesadas (x, y, rango, potencia, etc).


import serial
import time
import numpy as np

class IWR1443:
    def __init__(self, config_file, cli_port='COM19', data_port='COM18', buffer_size=2**15):
        self.config_file = config_file
        self.cli_port_name = cli_port
        self.data_port_name = data_port
        self.CLIport = None
        self.Dataport = None
        self.byteBuffer = np.zeros(buffer_size, dtype='uint8')
        self.byteBufferLength = 0
        self.configParameters = {}

        
    # ------------------------- CONFIGURACIÓN -------------------------
    def serial_config(self):
        """Configura los puertos serie y envía el archivo de configuración al radar."""
        self.CLIport = serial.Serial(self.cli_port_name, 115200, timeout=0.5)
        self.Dataport = serial.Serial(self.data_port_name, 921600, timeout=0.5)
        time.sleep(0.1)

        config_lines = [line.strip() for line in open(self.config_file)]
        print('\n---------- Enviando el archivo de configuración al radar ---------\n')
        for line in config_lines:
            self.CLIport.write((line + '\n').encode())
            print(line)
            time.sleep(0.01)
        print('\n-------------------------------------------------------------------\n')

        self.CLIport.write(('sensorStop\n').encode())
        time.sleep(0.05)
        self.CLIport.write(('sensorStart\n').encode())
        time.sleep(0.05)

        print(f"✅ Configuración enviada desde {self.config_file}")
        
    
    def parse_config_file(self):
        """Extrae todos los parámetros útiles del archivo de configuración del radar."""
        cfg_lines = [line.strip() for line in open(self.config_file)]
        
        # Diccionario donde guardaremos todos los parámetros
        config = {}

        # Valores por defecto
        numRxAnt, numTxAnt = 0, 0

        for line in cfg_lines:
            words = line.split()
            if not words or words[0].startswith('%'):
                continue  # ignorar comentarios o líneas vacías

            if words[0] == "channelCfg":
                rx_bin = int(words[1])
                tx_bin = int(words[2])
                numRxAnt = bin(rx_bin).count('1')
                numTxAnt = bin(tx_bin).count('1')
                config["numRxAnt"] = numRxAnt
                config["numTxAnt"] = numTxAnt

            elif words[0] == "profileCfg":
                config["startFreq"] = float(words[2])
                config["idleTime"] = float(words[3])
                config["rampEndTime"] = float(words[5])
                config["freqSlopeConst"] = float(words[8])
                config["numAdcSamples"] = int(words[10])
                config["digOutSampleRate"] = int(words[11])
                # redondear numAdcSamples a potencia de 2
                n = 1
                while n < config["numAdcSamples"]:
                    n *= 2
                config["numAdcSamplesRoundTo2"] = n

            elif words[0] == "frameCfg":
                config["chirpStartIdx"] = int(words[1])
                config["chirpEndIdx"] = int(words[2])
                config["numLoops"] = int(words[3])
                config["numFrames"] = int(words[4])
                config["framePeriodicity"] = int(words[5])

            elif words[0] == "cfarCfg":
                config["procDir"] = int(words[1])
                config["AvgMod"] = int(words[2])
                config["NoiseAvgWin"] = int(words[3])
                config["GuardLen"] = int(words[4])
                config["DivShift"] = int(words[5])
                config["CyclMod"] = int(words[6])
                config["TCLI"] = int(words[7])

            elif words[0] == "peakGrouping":
                config["scheme"] = int(words[1])
                config["range_dir"] = int(words[2])
                config["doppler_dir"] = int(words[3])
                config["start_rang_Idx"] = int(words[4])
                config["end_rang_Idx"] = int(words[5])

            elif words[0] == "clutterRemoval":
                config["clutterRemoval"] = int(words[1])

        # Calcular parámetros derivados
        numChirpsPerFrame = (config["chirpEndIdx"] - config["chirpStartIdx"] + 1) * config["numLoops"]
        config["numDopplerBins"] = numChirpsPerFrame / numTxAnt
        config["rangeIdxToMeters"] = (3e8 * config["digOutSampleRate"] * 1e3) / (2 * config["freqSlopeConst"] * 1e12 * config["numAdcSamplesRoundTo2"])
        config["dopplerResolutionMps"] = 3e8 / (2 * config["startFreq"] * 1e9 * (config["idleTime"] + config["rampEndTime"]) * 1e-6 * config["numDopplerBins"] * numTxAnt)
        config["maxRange"] = (300 * 0.9 * config["digOutSampleRate"]) / (2 * config["freqSlopeConst"] * 1e3)
        config["maxVelocity"] = 3e8 / (4 * config["startFreq"] * 1e9 * (config["idleTime"] + config["rampEndTime"]) * 1e-6 * numTxAnt)

        self.configParameters = config
        print(f"✅ Configuración del radar cargada con {numRxAnt} Rx y {numTxAnt} Tx")
        return config


    # ------------------------- LECTURA DE DATOS -------------------------
    def read_data(self):
        """Lee bytes del radar y actualiza el buffer sin desbordar."""
        # if self.Dataport.in_waiting == 0:
        #     print("if self.Dataport.in_waiting == 0:")
        #     print("[read_data] ❌ No hay datos esperando en el puerto serie.")
        #     return False

        readBuffer = self.Dataport.read(self.Dataport.in_waiting)
        while(readBuffer == b''):
            time.sleep(0.03)
            print("[read_data] ❌ No hay datos del radar esperando en el puerto serie.")
            readBuffer = self.Dataport.read(self.Dataport.in_waiting)
            # Reacivar radar
            self.CLIport.write(('sensorStop\n').encode())  
            time.sleep(0.03)
            self.CLIport.write(('sensorStart\n').encode())
            return False

        byteVec = np.frombuffer(readBuffer, dtype='uint8')

        # Evitar overflow del buffer
        if len(byteVec) + self.byteBufferLength > len(self.byteBuffer):
            print("[read_data] ⚠️ Overflow del buffer, recortando datos antiguos.")
            overflow = len(byteVec) + self.byteBufferLength - len(self.byteBuffer)
            self.byteBuffer[:self.byteBufferLength - overflow] = self.byteBuffer[overflow:self.byteBufferLength]
            self.byteBufferLength -= overflow

        self.byteBuffer[self.byteBufferLength:self.byteBufferLength + len(byteVec)] = byteVec
        self.byteBufferLength += len(byteVec)
        return True

    def parse_packets(self):
        """Busca paquetes completos en el buffer y devuelve detecciones."""
        magicWord = np.array([2,1,4,3,6,5,8,7], dtype='uint8')
        MMWDEMO_UART_MSG_DETECTED_POINTS = 1

        detObj = {}
        start = -1

        # Buscar magic word
        for loc in np.where(self.byteBuffer[:self.byteBufferLength] == magicWord[0])[0]:
            if loc + 8 <= self.byteBufferLength and np.all(self.byteBuffer[loc:loc+8] == magicWord):
                start = loc
                break

        if start == -1:
            print("if start == -1:")
            print("[parse_packets] ❌ No se encontró la magic word.")
            return False, {}

        # Ajustar buffer para empezar en el paquete
        if start > 0:
            self.byteBuffer[:self.byteBufferLength - start] = self.byteBuffer[start:self.byteBufferLength]
            self.byteBufferLength -= start

        if self.byteBufferLength < 16:
            print("if self.byteBufferLength < 16:")
            print("[parse_packets] ⚠️ Buffer demasiado pequeño (<16 bytes).")
            return False, {}

        word32 = np.array([1, 2**8, 2**16, 2**24], dtype='uint32')
        totalPacketLen = np.dot(self.byteBuffer[12:16], word32)

        if self.byteBufferLength < totalPacketLen:
            print("[parse_packets] ⏳ Esperando a recibir el paquete completo.")
            return False, {} # Esperar paquete completo

        # TLV header
        idX = 36
        tlv_type = np.dot(self.byteBuffer[idX:idX+4], word32)
        idX += 4
        tlv_length = np.dot(self.byteBuffer[idX:idX+4], word32)
        idX += 4

        if tlv_type != MMWDEMO_UART_MSG_DETECTED_POINTS:
            print(f"[parse_packets] ❌ TLV tipo desconocido ({tlv_type}).")
            return False, {}
        
        if tlv_type == MMWDEMO_UART_MSG_DETECTED_POINTS:
            word16 = np.array([1, 2**8], dtype='uint16')
            numObj = np.dot(self.byteBuffer[idX:idX+2], word16)
            idX += 2
            # xyzQFormat = 2 ** np.dot(self.byteBuffer[idX:idX+2], word16)
            xyzQFormat = np.dot(self.byteBuffer[idX:idX+2], word16)

            idX += 2

            x, y, z, peakVal, rangeIdx = [], [], [], [], []
            for _ in range(numObj):
                r = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2
                d = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2
                p = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2
                
                xx = self.to_int16(np.dot(self.byteBuffer[idX:idX+2], word16)); idX += 2
                yy = self.to_int16(np.dot(self.byteBuffer[idX:idX+2], word16)); idX += 2
                zz = self.to_int16(np.dot(self.byteBuffer[idX:idX+2], word16)); idX += 2

                # xx = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2
                # yy = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2
                # zz = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2

                rangeIdx.append(r)
                peakVal.append(p)
                # x.append(xx / xyzQFormat)
                # y.append(yy / xyzQFormat)
                # z.append(zz / xyzQFormat)
                # scale = 2**xyzQFormat
                # x.append(xx / scale)
                # y.append(yy / scale)
                # z.append(zz / scale)
                x.append(xx / (2 ** xyzQFormat))
                y.append(yy / (2 ** xyzQFormat))
                z.append(zz / (2 ** xyzQFormat))


            rangeVal = np.array(rangeIdx) * self.configParameters["rangeIdxToMeters"]
            detObj = {
                "numObj": numObj,
                "range": rangeVal,
                "x": np.array(x),
                "y": np.array(y),
                "z": np.array(z),
                "peakVal": np.array(peakVal)
            }

        # Limpiar buffer del paquete procesado
        if self.byteBufferLength > totalPacketLen:
            self.byteBuffer[:self.byteBufferLength - totalPacketLen] = self.byteBuffer[totalPacketLen:self.byteBufferLength]
        self.byteBufferLength -= totalPacketLen
        if self.byteBufferLength < 0:
            self.byteBufferLength = 0

        return True, detObj
    
    def to_int16(self, v):
        v = int(v) 
        return v - 65536 if v >= 32768 else v
    
    # ------------------------- LÓGICA DE COLISIÓN -------------------------
    def process_collision_logic(self, detObj, max_objects=3, stop_threshold=0.5, min_distance=0.1):
        """
        Filtra los N objetos más cercanos ignorando los que estén por debajo de min_distance.
        Devuelve:
        - radar_collision_stop: 1 si algún objeto está por debajo del umbral
        - filtered_detObj: diccionario con solo los N objetos más cercanos válidos
        """
        radar_collision_stop = 0
        filtered_detObj = {}

        if detObj and detObj.get("numObj", 0) > 0:
            # Filtrar objetos válidos (>= min_distance)
            valid_indices = np.where(detObj["range"] >= min_distance)[0]

            if len(valid_indices) > 0:
                ranges = detObj["range"][valid_indices]
                sorted_indices = valid_indices[np.argsort(ranges)]
                num_to_keep = min(len(sorted_indices), max_objects)
                closest_indices = sorted_indices[:num_to_keep]

                filtered_detObj = {
                    "numObj": num_to_keep,
                    "range": detObj["range"][closest_indices],
                    "x": detObj["x"][closest_indices],
                    "y": detObj["y"][closest_indices],
                    "z": detObj["z"][closest_indices],
                    "peakVal": detObj["peakVal"][closest_indices]
                }

                if np.any(filtered_detObj["range"] < stop_threshold):
                    radar_collision_stop = 1

        return radar_collision_stop, filtered_detObj

    # ------------------------- UPDATE -------------------------
    def update(self, max_objects=3, stop_threshold=0.5, min_distance=0.1):
        """
        Lee y parsea datos del radar, procesa la lógica de colisión
        y devuelve:
        - dataOk: si se recibieron datos válidos
        - radar_collision_stop: flag de colisión
        - filtered_detObj: objetos filtrados
        """
        dataOk = self.read_data()
        if not dataOk:
            return False, 0, {}

        dataOk, detObj = self.parse_packets()
        if not dataOk:
            return False, 0, {}

        radar_collision_stop, filtered_detObj = self.process_collision_logic(
            detObj, max_objects, stop_threshold, min_distance
        )

        # Imprime información de depuración
        if dataOk and filtered_detObj.get("numObj", 0) > 0:
            print(f"FLAG DE COLISIÓN: {radar_collision_stop}")
            for i in range(filtered_detObj['numObj']):
                print(f"  Obj {i}: X={filtered_detObj['x'][i]:.2f}, Y={filtered_detObj['y'][i]:.2f}, Z={filtered_detObj['z'][i]:.2f}, Dist={filtered_detObj['range'][i]:.2f} m")

        return dataOk, radar_collision_stop, filtered_detObj
