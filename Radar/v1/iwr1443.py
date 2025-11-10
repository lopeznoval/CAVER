import serial
import time
import numpy as np

class IWR1443:
    def __init__(self, cli_port_name, data_port_name, config_file,
                 max_objects=3, stop_threshold=0.5, min_distance=0.1):
        self.cli_port_name = cli_port_name
        self.data_port_name = data_port_name
        self.config_file = config_file
        
        self.MAX_OBJECTS_TO_CONSIDER = max_objects
        self.STOP_DISTANCE_THRESHOLD = stop_threshold
        self.MIN_DISTANCE = min_distance
        
        self.CLIport = None
        self.Dataport = None
        self.configParameters = None
        
        self.byteBuffer = np.zeros(2**15, dtype='uint8')
        self.byteBufferLength = 0
        self.detObj = {}

    # ------------------------------------------------------------------
    # Configuración de los puertos y envío del archivo cfg
    def serial_config(self):
        self.CLIport = serial.Serial(self.cli_port_name, 115200)
        self.Dataport = serial.Serial(self.data_port_name, 921600)

        with open(self.config_file) as f:
            config = [line.rstrip('\r\n') for line in f]

        for line in config:
            self.CLIport.write((line + '\n').encode())
            print(line)
            time.sleep(0.01)

        return self.CLIport, self.Dataport

    # ------------------------------------------------------------------
    # Parseo del archivo de configuración
    def parse_config_file(self):
        configParameters = {}
        with open(self.config_file) as f:
            config = [line.rstrip('\r\n') for line in f]

        for line in config:
            splitWords = line.split(" ")
            numRxAnt = 4
            numTxAnt = 3

            if "profileCfg" in splitWords[0]:
                startFreq = int(float(splitWords[2]))
                idleTime = int(splitWords[3])
                rampEndTime = float(splitWords[5])
                freqSlopeConst = float(splitWords[8])
                numAdcSamples = int(splitWords[10])
                numAdcSamplesRoundTo2 = 1
                while numAdcSamples > numAdcSamplesRoundTo2:
                    numAdcSamplesRoundTo2 *= 2
                digOutSampleRate = int(splitWords[11])
            elif "frameCfg" in splitWords[0]:
                chirpStartIdx = int(splitWords[1])
                chirpEndIdx = int(splitWords[2])
                numLoops = int(splitWords[3])
                numFrames = int(splitWords[4])
                framePeriodicity = int(splitWords[5])

        numChirpsPerFrame = (chirpEndIdx - chirpStartIdx + 1) * numLoops
        configParameters["numDopplerBins"] = numChirpsPerFrame / numTxAnt
        configParameters["numRangeBins"] = numAdcSamplesRoundTo2
        configParameters["rangeResolutionMeters"] = (3e8 * digOutSampleRate * 1e3) / \
            (2 * freqSlopeConst * 1e12 * numAdcSamples)
        configParameters["rangeIdxToMeters"] = (3e8 * digOutSampleRate * 1e3) / \
            (2 * freqSlopeConst * 1e12 * configParameters["numRangeBins"])
        configParameters["dopplerResolutionMps"] = 3e8 / \
            (2 * startFreq * 1e9 * (idleTime + rampEndTime) * 1e-6 * configParameters["numDopplerBins"] * numTxAnt)
        configParameters["maxRange"] = (300 * 0.9 * digOutSampleRate) / (2 * freqSlopeConst * 1e3)
        configParameters["maxVelocity"] = 3e8 / (4 * startFreq * 1e9 * (idleTime + rampEndTime) * 1e-6 * numTxAnt)

        self.configParameters = configParameters
        return configParameters

    # ------------------------------------------------------------------
    # Lectura y parseo de datos
    def read_and_parse_data(self):
        OBJ_STRUCT_SIZE_BYTES = 12
        maxBufferSize = 2**15
        MMWDEMO_UART_MSG_DETECTED_POINTS = 1
        magicWord = [2, 1, 4, 3, 6, 5, 8, 7]

        dataOK = 0
        frameNumber = 0
        detObj = {}

        readBuffer = self.Dataport.read(self.Dataport.in_waiting)
        byteVec = np.frombuffer(readBuffer, dtype='uint8')
        byteCount = len(byteVec)

        if byteCount > 0:
            print(f"Recibidos {byteCount} bytes!")

        # Añade los bytes al buffer
        if (self.byteBufferLength + byteCount) < maxBufferSize:
            self.byteBuffer[self.byteBufferLength:self.byteBufferLength + byteCount] = byteVec[:byteCount]
            self.byteBufferLength += byteCount

        magicOK = 0
        if self.byteBufferLength > 16:
            possibleLocs = np.where(self.byteBuffer == magicWord[0])[0]
            startIdx = []
            for loc in possibleLocs:
                check = self.byteBuffer[loc:loc+8]
                if np.all(check == magicWord):
                    startIdx.append(loc)

            if startIdx:
                if startIdx[0] > 0:
                    self.byteBuffer[:self.byteBufferLength-startIdx[0]] = self.byteBuffer[startIdx[0]:self.byteBufferLength]
                    self.byteBuffer[self.byteBufferLength-startIdx[0]:] = 0
                    self.byteBufferLength -= startIdx[0]
                if self.byteBufferLength < 0:
                    self.byteBufferLength = 0

                word = [1, 2**8, 2**16, 2**24]
                totalPacketLen = np.matmul(self.byteBuffer[12:16], word)

                if self.byteBufferLength >= totalPacketLen and self.byteBufferLength != 0:
                    magicOK = 1

        if magicOK:
            idX = 0
            word = [1, 2**8, 2**16, 2**24]
            idX += 8  # magicNumber
            idX += 4  # version
            totalPacketLen = np.matmul(self.byteBuffer[idX:idX+4], word)
            idX += 4
            idX += 4  # platform
            frameNumber = np.matmul(self.byteBuffer[idX:idX+4], word)
            idX += 4
            idX += 4  # timeCpuCycles
            numDetectedObj = np.matmul(self.byteBuffer[idX:idX+4], word)
            idX += 4
            numTLVs = np.matmul(self.byteBuffer[idX:idX+4], word)
            idX += 4

            for tlvIdx in range(numTLVs):
                tlv_type = np.matmul(self.byteBuffer[idX:idX+4], word)
                idX += 4
                tlv_length = np.matmul(self.byteBuffer[idX:idX+4], word)
                idX += 4

                if tlv_type == MMWDEMO_UART_MSG_DETECTED_POINTS:
                    word16 = [1, 2**8]
                    tlv_numObj = np.matmul(self.byteBuffer[idX:idX+2], word16)
                    idX += 2
                    tlv_xyzQFormat = 2**np.matmul(self.byteBuffer[idX:idX+2], word16)
                    idX += 2

                    # Inicializa arrays
                    rangeIdx = np.zeros(tlv_numObj, dtype='int32')
                    dopplerIdx = np.zeros(tlv_numObj, dtype='int32')
                    peakVal = np.zeros(tlv_numObj, dtype='int32')
                    x = np.zeros(tlv_numObj, dtype='int32')
                    y = np.zeros(tlv_numObj, dtype='int32')
                    z = np.zeros(tlv_numObj, dtype='int32')

                    for obj in range(tlv_numObj):
                        rangeIdx[obj] = np.matmul(self.byteBuffer[idX:idX+2], word16); idX += 2
                        dopplerIdx[obj] = np.matmul(self.byteBuffer[idX:idX+2], word16); idX += 2
                        peakVal[obj] = np.matmul(self.byteBuffer[idX:idX+2], word16); idX += 2
                        x[obj] = np.matmul(self.byteBuffer[idX:idX+2], word16); idX += 2
                        y[obj] = np.matmul(self.byteBuffer[idX:idX+2], word16); idX += 2
                        z[obj] = np.matmul(self.byteBuffer[idX:idX+2], word16); idX += 2

                    # Complemento a dos
                    rangeIdx[rangeIdx > 32767] -= 65536
                    dopplerIdx[dopplerIdx > 32767] -= 65536
                    peakVal[peakVal > 32767] -= 65536
                    x[x > 32767] -= 65536
                    y[y > 32767] -= 65536
                    z[z > 32767] -= 65536

                    x = x / tlv_xyzQFormat
                    y = y / tlv_xyzQFormat
                    z = z / tlv_xyzQFormat

                    rangeVal = rangeIdx * self.configParameters["rangeIdxToMeters"]
                    dopplerVal = dopplerIdx * self.configParameters["dopplerResolutionMps"]

                    detObj = {
                        "numObj": tlv_numObj,
                        "rangeIdx": rangeIdx, "range": rangeVal,
                        "dopplerIdx": dopplerIdx, "doppler": dopplerVal,
                        "peakVal": peakVal,
                        "x": x, "y": y, "z": z
                    }

                    dataOK = 1

            # Elimina datos ya procesados
            if idX > 0 and self.byteBufferLength > idX:
                shiftSize = totalPacketLen
                self.byteBuffer[:self.byteBufferLength - shiftSize] = self.byteBuffer[shiftSize:self.byteBufferLength]
                self.byteBuffer[self.byteBufferLength - shiftSize:] = 0
                self.byteBufferLength -= shiftSize
                if self.byteBufferLength < 0:
                    self.byteBufferLength = 0

        return dataOK, frameNumber, detObj

    # ------------------------------------------------------------------
    # Lógica de colisión
    def process_collision_logic(self, detObj):
        radar_collision_stop = 0
        filtered_detObj = {}

        if detObj and detObj["numObj"] > 0:
            # Filtra por distancia mínima
            valid_indices = np.where(detObj["range"] >= self.MIN_DISTANCE)[0]
            if len(valid_indices) > 0:
                ranges = detObj["range"][valid_indices]
                sorted_indices = valid_indices[np.argsort(ranges)]
                num_to_keep = min(len(sorted_indices), self.MAX_OBJECTS_TO_CONSIDER)
                closest_indices = sorted_indices[:num_to_keep]

                filtered_detObj = {
                    "numObj": num_to_keep,
                    "range": detObj["range"][closest_indices],
                    "doppler": detObj["doppler"][closest_indices],
                    "peakVal": detObj["peakVal"][closest_indices],
                    "x": detObj["x"][closest_indices],
                    "y": detObj["y"][closest_indices],
                    "z": detObj["z"][closest_indices]
                }

                if np.any(filtered_detObj["range"] < self.STOP_DISTANCE_THRESHOLD):
                    radar_collision_stop = 1

        return radar_collision_stop, filtered_detObj

    # ------------------------------------------------------------------
    # Actualiza los datos
    def update(self):
        dataOk, frameNumber, detObj_raw = self.read_and_parse_data()
        radar_collision_stop, filtered_detObj = self.process_collision_logic(detObj_raw)

        if dataOk:
            print(f"FLAG DE COLISIÓN: {radar_collision_stop}")
            if filtered_detObj and filtered_detObj["numObj"] > 0:
                self.detObj = filtered_detObj
                for i in range(filtered_detObj["numObj"]):
                    print(f"Obj {i}: X={filtered_detObj['x'][i]:.2f}, "
                          f"Y={filtered_detObj['y'][i]:.2f}, "
                          f"Z={filtered_detObj['z'][i]:.2f}, "
                          f"Distancia={filtered_detObj['range'][i]:.2f} m")
            else:
                self.detObj = {}

        else:
            print("Esperando datos del radar...")

        return dataOk, radar_collision_stop
