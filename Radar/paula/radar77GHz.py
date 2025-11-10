# clase IWR1443BOOST 

# Configura los puertos serie.
# Lee y parsea los datos binarios del radar.
# Devuelve las detecciones procesadas (x, y, rango, potencia, etc).


import serial
import time
import numpy as np

class radar77GHz:
    def __init__(self, config_file, cli_port='COM19', data_port='COM18', buffer_size=2**16):
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
        for line in config_lines:
            self.CLIport.write((line + '\n').encode())
            time.sleep(0.01)

        self.CLIport.write(('sensorStop\n').encode())
        time.sleep(0.05)
        self.CLIport.write(('sensorStart\n').encode())
        time.sleep(0.05)

        print(f"✅ Configuración enviada desde {self.config_file}")

    def parse_config_file(self):
        """Extrae parámetros útiles del archivo de configuración del radar."""
        cfg = [line.strip() for line in open(self.config_file)]
        # numRxAnt, numTxAnt = 4, 2


        for line in cfg:
            words = line.split()
            if "channelCfg" in words[0]:
                rx_bin = int(words[1])
                tx_bin = int(words[2])
                # Contar los bits activados (1) para Rx y Tx
                numRxAnt = bin(rx_bin).count('1')
                numTxAnt = bin(tx_bin).count('1')
                break  # ya tenemos lo necesario

        print(f"✅ Detectadas {numRxAnt} Rx y {numTxAnt} Tx")

        for line in cfg:
            words = line.split()
            if "profileCfg" in words[0]:
                startFreq = float(words[2])
                idleTime = float(words[3])
                rampEndTime = float(words[5])
                freqSlopeConst = float(words[8])
                numAdcSamples = int(words[10])
                digOutSampleRate = int(words[11])
                numAdcSamplesRoundTo2 = 1
                while numAdcSamples > numAdcSamplesRoundTo2:
                    numAdcSamplesRoundTo2 *= 2
            elif "frameCfg" in words[0]:
                chirpStartIdx = int(words[1])
                chirpEndIdx = int(words[2])
                numLoops = int(words[3])

        numChirpsPerFrame = (chirpEndIdx - chirpStartIdx + 1) * numLoops
        config = {
            "numDopplerBins": numChirpsPerFrame / numTxAnt,
            "numRangeBins": numAdcSamplesRoundTo2,
            "rangeIdxToMeters": (3e8 * digOutSampleRate * 1e3) / (2 * freqSlopeConst * 1e12 * numAdcSamplesRoundTo2),
            "dopplerResolutionMps": 3e8 / (2 * startFreq * 1e9 * (idleTime + rampEndTime) * 1e-6 * (numChirpsPerFrame / numTxAnt) * numTxAnt),
            "maxRange": (300 * 0.9 * digOutSampleRate) / (2 * freqSlopeConst * 1e3),
        }
        self.configParameters = config
        return config

    # ------------------------- LECTURA DE DATOS -------------------------
    def read_data(self):
        """Lee bytes del radar y actualiza el buffer sin desbordar."""
        if self.Dataport.in_waiting == 0:
            return False

        readBuffer = self.Dataport.read(self.Dataport.in_waiting)
        byteVec = np.frombuffer(readBuffer, dtype='uint8')

        # Evitar overflow del buffer
        if len(byteVec) + self.byteBufferLength > len(self.byteBuffer):
            overflow = len(byteVec) + self.byteBufferLength - len(self.byteBuffer)
            # Mover datos viejos a la izquierda
            self.byteBuffer[:self.byteBufferLength - overflow] = self.byteBuffer[overflow:self.byteBufferLength]
            self.byteBufferLength -= overflow

        self.byteBuffer[self.byteBufferLength:self.byteBufferLength + len(byteVec)] = byteVec
        self.byteBufferLength += len(byteVec)
        return True

    def parse_packets(self):
        """Busca paquetes completos y devuelve detecciones."""
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
            return False, {}

        # Ajustar buffer para empezar en el paquete
        if start > 0:
            self.byteBuffer[:self.byteBufferLength - start] = self.byteBuffer[start:self.byteBufferLength]
            self.byteBufferLength -= start

        if self.byteBufferLength < 16:
            return False, {}

        word32 = np.array([1, 2**8, 2**16, 2**24], dtype='uint32')
        totalPacketLen = np.dot(self.byteBuffer[12:16], word32)

        if self.byteBufferLength < totalPacketLen:
            return False, {}  # Esperar paquete completo

        # TLV header
        idX = 36
        tlv_type = np.dot(self.byteBuffer[idX:idX+4], word32)
        idX += 4
        tlv_length = np.dot(self.byteBuffer[idX:idX+4], word32)
        idX += 4

        if tlv_type == MMWDEMO_UART_MSG_DETECTED_POINTS:
            word16 = np.array([1, 2**8], dtype='uint16')
            numObj = np.dot(self.byteBuffer[idX:idX+2], word16)
            idX += 2
            xyzQFormat = 2 ** np.dot(self.byteBuffer[idX:idX+2], word16)
            idX += 2

            x, y, z, peakVal, rangeIdx = [], [], [], [], []
            for _ in range(numObj):
                r = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2
                d = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2
                p = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2
                xx = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2
                yy = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2
                zz = np.dot(self.byteBuffer[idX:idX+2], word16); idX += 2

                rangeIdx.append(r)
                peakVal.append(p)
                x.append(xx / xyzQFormat)
                y.append(yy / xyzQFormat)
                z.append(zz / xyzQFormat)

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

    # ------------------------- UPDATE -------------------------
    def update(self):
        """Lee y devuelve los datos listos para usar."""
        if not self.read_data():
            return False, [], [], [], []

        dataOK, detObj = self.parse_packets()
        if dataOK and detObj.get("numObj", 0) > 0:
            peakdB = 20 * np.log10(detObj["peakVal"])
            return True, detObj["x"], detObj["y"], detObj["range"], peakdB
        return False, [], [], [], []

    # ------------------------- STOP -------------------------
    def stop(self):
        if self.CLIport:
            self.CLIport.write(('sensorStop\n').encode())
            self.CLIport.close()
        if self.Dataport:
            self.Dataport.close()
        print("🛑 Radar detenido y puertos cerrados.")
