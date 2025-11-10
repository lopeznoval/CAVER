import serial
import time
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtWidgets

# Change the configuration file name
# configFileName = '1443config.cfg'
configFileName = r"C:\Users\paula\OneDrive\Escritorio\TELECO\2 Master\CAVER\Radar\IWR1443-Read-Data-Python-MMWAVE-SDK-1-master\1443config.cfg"

CLIport = {}
Dataport = {}
byteBuffer = np.zeros(2**15,dtype = 'uint8')
byteBufferLength = 0

# --- Configuración del Freno de Colisión ---
# Límite de objetos a procesar (los N más cercanos)
MAX_OBJECTS_TO_CONSIDER = 3 
# Distancia (en metros) que activa el flag de parada
STOP_DISTANCE_THRESHOLD = 0.5

# ------------------------------------------------------------------

# Function to configure the serial ports and send the data from
# the configuration file to the radar
def serialConfig(configFileName):
    
    global CLIport
    global Dataport
    # Open the serial ports for the configuration and the data ports
    
    # Raspberry pi
    #CLIport = serial.Serial('/dev/ttyACM0', 115200)
    #Dataport = serial.Serial('/dev/ttyACM1', 921600)
    
    # Windows
    CLIport = serial.Serial('COM19', 115200)
    Dataport = serial.Serial('COM18', 921600)

    # Read the configuration file and send it to the board
    config = [line.rstrip('\r\n') for line in open(configFileName)]
    for i in config:
        CLIport.write((i+'\n').encode())
        print(i)
        time.sleep(0.01)
        
    return CLIport, Dataport

# ------------------------------------------------------------------

# Function to parse the data inside the configuration file
def parseConfigFile(configFileName):
    configParameters = {} # Initialize an empty dictionary to store the configuration parameters
    
    # Read the configuration file and send it to the board
    config = [line.rstrip('\r\n') for line in open(configFileName)]
    for i in config:
        
        # Split the line
        splitWords = i.split(" ")
        
        # Hard code the number of antennas, change if other configuration is used
        numRxAnt = 4
        numTxAnt = 3
        
        # Get the information about the profile configuration
        if "profileCfg" in splitWords[0]:
            startFreq = int(float(splitWords[2]))
            idleTime = int(splitWords[3])
            rampEndTime = float(splitWords[5])
            freqSlopeConst = float(splitWords[8])
            numAdcSamples = int(splitWords[10])
            numAdcSamplesRoundTo2 = 1;
            
            while numAdcSamples > numAdcSamplesRoundTo2:
                numAdcSamplesRoundTo2 = numAdcSamplesRoundTo2 * 2;
                
            digOutSampleRate = int(splitWords[11]);
            
        # Get the information about the frame configuration    
        elif "frameCfg" in splitWords[0]:
            
            chirpStartIdx = int(splitWords[1]);
            chirpEndIdx = int(splitWords[2]);
            numLoops = int(splitWords[3]);
            numFrames = int(splitWords[4]);
            framePeriodicity = int(splitWords[5]);

            
    # Combine the read data to obtain the configuration parameters           
    numChirpsPerFrame = (chirpEndIdx - chirpStartIdx + 1) * numLoops
    configParameters["numDopplerBins"] = numChirpsPerFrame / numTxAnt
    configParameters["numRangeBins"] = numAdcSamplesRoundTo2
    configParameters["rangeResolutionMeters"] = (3e8 * digOutSampleRate * 1e3) / (2 * freqSlopeConst * 1e12 * numAdcSamples)
    configParameters["rangeIdxToMeters"] = (3e8 * digOutSampleRate * 1e3) / (2 * freqSlopeConst * 1e12 * configParameters["numRangeBins"])
    configParameters["dopplerResolutionMps"] = 3e8 / (2 * startFreq * 1e9 * (idleTime + rampEndTime) * 1e-6 * configParameters["numDopplerBins"] * numTxAnt)
    configParameters["maxRange"] = (300 * 0.9 * digOutSampleRate)/(2 * freqSlopeConst * 1e3)
    configParameters["maxVelocity"] = 3e8 / (4 * startFreq * 1e9 * (idleTime + rampEndTime) * 1e-6 * numTxAnt)
    
    return configParameters
   
# ------------------------------------------------------------------

# Funtion to read and parse the incoming data
def readAndParseData14xx(Dataport, configParameters):
    global byteBuffer, byteBufferLength
    
    # Constants
    OBJ_STRUCT_SIZE_BYTES = 12
    BYTE_VEC_ACC_MAX_SIZE = 2**15
    MMWDEMO_UART_MSG_DETECTED_POINTS = 1
    MMWDEMO_UART_MSG_RANGE_PROFILE   = 2
    maxBufferSize = 2**15
    magicWord = [2, 1, 4, 3, 6, 5, 8, 7]
    
    # Initialize variables
    magicOK = 0 # Checks if magic number has been read
    dataOK = 0 # Checks if the data has been read correctly
    frameNumber = 0
    detObj = {}
    
    readBuffer = Dataport.read(Dataport.in_waiting)
    byteVec = np.frombuffer(readBuffer, dtype = 'uint8')
    byteCount = len(byteVec)

    if byteCount > 0:
        print(f"Recibidos {byteCount} bytes!")
    
    # Check that the buffer is not full, and then add the data to the buffer
    if (byteBufferLength + byteCount) < maxBufferSize:
        byteBuffer[byteBufferLength:byteBufferLength + byteCount] = byteVec[:byteCount]
        byteBufferLength = byteBufferLength + byteCount
        
    # Check that the buffer has some data
    if byteBufferLength > 16:
        
        # Check for all possible locations of the magic word
        possibleLocs = np.where(byteBuffer == magicWord[0])[0]

        # Confirm that is the beginning of the magic word and store the index in startIdx
        startIdx = []
        for loc in possibleLocs:
            check = byteBuffer[loc:loc+8]
            if np.all(check == magicWord):
                startIdx.append(loc)
               
        # Check that startIdx is not empty
        if startIdx:
            
            # Remove the data before the first start index
            if startIdx[0] > 0 and startIdx[0] < byteBufferLength:
                byteBuffer[:byteBufferLength-startIdx[0]] = byteBuffer[startIdx[0]:byteBufferLength]
                byteBuffer[byteBufferLength-startIdx[0]:] = np.zeros(len(byteBuffer[byteBufferLength-startIdx[0]:]),dtype = 'uint8')
                byteBufferLength = byteBufferLength - startIdx[0]
                
            # Check that there have no errors with the byte buffer length
            if byteBufferLength < 0:
                byteBufferLength = 0
                
            # word array to convert 4 bytes to a 32 bit number
            word = [1, 2**8, 2**16, 2**24]
            
            # Read the total packet length
            totalPacketLen = np.matmul(byteBuffer[12:12+4],word)
            
            # Check that all the packet has been read
            if (byteBufferLength >= totalPacketLen) and (byteBufferLength != 0):
                magicOK = 1
    
    # If magicOK is equal to 1 then process the message
    if magicOK:
        # word array to convert 4 bytes to a 32 bit number
        word = [1, 2**8, 2**16, 2**24]
        
        # Initialize the pointer index
        idX = 0
        
        # Read the header
        magicNumber = byteBuffer[idX:idX+8]
        idX += 8
        version = format(np.matmul(byteBuffer[idX:idX+4],word),'x')
        idX += 4
        totalPacketLen = np.matmul(byteBuffer[idX:idX+4],word)
        idX += 4
        platform = format(np.matmul(byteBuffer[idX:idX+4],word),'x')
        idX += 4
        frameNumber = np.matmul(byteBuffer[idX:idX+4],word)
        idX += 4
        timeCpuCycles = np.matmul(byteBuffer[idX:idX+4],word)
        idX += 4
        numDetectedObj = np.matmul(byteBuffer[idX:idX+4],word)
        idX += 4
        numTLVs = np.matmul(byteBuffer[idX:idX+4],word)
        idX += 4
        
        # UNCOMMENT IN CASE OF SDK 2
        #subFrameNumber = np.matmul(byteBuffer[idX:idX+4],word)
        #idX += 4
        
        # Read the TLV messages
        for tlvIdx in range(numTLVs):
            
            # word array to convert 4 bytes to a 32 bit number
            word = [1, 2**8, 2**16, 2**24]

            # Check the header of the TLV message
            tlv_type = np.matmul(byteBuffer[idX:idX+4],word)
            idX += 4
            tlv_length = np.matmul(byteBuffer[idX:idX+4],word)
            idX += 4
            
            # Read the data depending on the TLV message
            if tlv_type == MMWDEMO_UART_MSG_DETECTED_POINTS:
                            
                # word array to convert 4 bytes to a 16 bit number
                word = [1, 2**8]
                tlv_numObj = np.matmul(byteBuffer[idX:idX+2],word)
                idX += 2
                tlv_xyzQFormat = 2**np.matmul(byteBuffer[idX:idX+2],word)
                idX += 2
                
                # # Initialize the arrays
                # rangeIdx = np.zeros(tlv_numObj,dtype = 'int16')
                # dopplerIdx = np.zeros(tlv_numObj,dtype = 'int16')
                # peakVal = np.zeros(tlv_numObj,dtype = 'int16')
                # x = np.zeros(tlv_numObj,dtype = 'int16')
                # y = np.zeros(tlv_numObj,dtype = 'int16')
                # z = np.zeros(tlv_numObj,dtype = 'int16')
                
                # for objectNum in range(tlv_numObj):
                    
                #     # Read the data for each object
                #     rangeIdx[objectNum] =  np.matmul(byteBuffer[idX:idX+2],word)
                #     idX += 2
                #     dopplerIdx[objectNum] = np.matmul(byteBuffer[idX:idX+2],word)
                #     idX += 2
                #     peakVal[objectNum] = np.matmul(byteBuffer[idX:idX+2],word)
                #     idX += 2
                #     x[objectNum] = np.matmul(byteBuffer[idX:idX+2],word)
                #     idX += 2
                #     y[objectNum] = np.matmul(byteBuffer[idX:idX+2],word)
                #     idX += 2
                #     z[objectNum] = np.matmul(byteBuffer[idX:idX+2],word)
                #     idX += 2

                

                # # Make the necessary corrections and calculate the rest of the data
                # rangeVal = rangeIdx * configParameters["rangeIdxToMeters"]
                # dopplerIdx[dopplerIdx > (configParameters["numDopplerBins"]/2 - 1)] = dopplerIdx[dopplerIdx > (configParameters["numDopplerBins"]/2 - 1)] - 65535
                # dopplerVal = dopplerIdx * configParameters["dopplerResolutionMps"]
                # #x[x > 32767] = x[x > 32767] - 65536
                # #y[y > 32767] = y[y > 32767] - 65536
                # #z[z > 32767] = z[z > 32767] - 65536
                # x = x / tlv_xyzQFormat
                # y = y / tlv_xyzQFormat
                # z = z / tlv_xyzQFormat

                # # Aplica complemento a dos para int16
                # rangeIdx[rangeIdx > 32767] -= 65536
                # dopplerIdx[dopplerIdx > 32767] -= 65536
                # peakVal[peakVal > 32767] -= 65536
                # x[x > 32767] -= 65536
                # y[y > 32767] -= 65536
                # z[z > 32767] -= 65536


                # Inicializa arrays como int32 para evitar overflow
                rangeIdx = np.zeros(tlv_numObj, dtype='int32')
                dopplerIdx = np.zeros(tlv_numObj, dtype='int32')
                peakVal = np.zeros(tlv_numObj, dtype='int32')
                x = np.zeros(tlv_numObj, dtype='int32')
                y = np.zeros(tlv_numObj, dtype='int32')
                z = np.zeros(tlv_numObj, dtype='int32')

                # Lee los datos
                for objectNum in range(tlv_numObj):
                    rangeIdx[objectNum] = np.matmul(byteBuffer[idX:idX+2], word)
                    idX += 2
                    dopplerIdx[objectNum] = np.matmul(byteBuffer[idX:idX+2], word)
                    idX += 2
                    peakVal[objectNum] = np.matmul(byteBuffer[idX:idX+2], word)
                    idX += 2
                    x[objectNum] = np.matmul(byteBuffer[idX:idX+2], word)
                    idX += 2
                    y[objectNum] = np.matmul(byteBuffer[idX:idX+2], word)
                    idX += 2
                    z[objectNum] = np.matmul(byteBuffer[idX:idX+2], word)
                    idX += 2

                # Aplica complemento a dos
                rangeIdx[rangeIdx > 32767] -= 65536
                dopplerIdx[dopplerIdx > 32767] -= 65536
                peakVal[peakVal > 32767] -= 65536
                x[x > 32767] -= 65536
                y[y > 32767] -= 65536
                z[z > 32767] -= 65536

                # Convierte a float usando el Q-format
                x = x / tlv_xyzQFormat
                y = y / tlv_xyzQFormat
                z = z / tlv_xyzQFormat

                # Calcula doppler y rango
                rangeVal = rangeIdx * configParameters["rangeIdxToMeters"]
                dopplerVal = dopplerIdx * configParameters["dopplerResolutionMps"]


                # Store the data in the detObj dictionary
                detObj = {"numObj": tlv_numObj, "rangeIdx": rangeIdx, "range": rangeVal, "dopplerIdx": dopplerIdx, \
                          "doppler": dopplerVal, "peakVal": peakVal, "x": x, "y": y, "z": z}
                
                dataOK = 1             
        
  
        # Remove already processed data
        if idX > 0 and byteBufferLength > idX:
            shiftSize = totalPacketLen
               
            byteBuffer[:byteBufferLength - shiftSize] = byteBuffer[shiftSize:byteBufferLength]
            byteBuffer[byteBufferLength - shiftSize:] = np.zeros(len(byteBuffer[byteBufferLength - shiftSize:]),dtype = 'uint8')
            byteBufferLength = byteBufferLength - shiftSize
            
            # Check that there are no errors with the buffer length
            if byteBufferLength < 0:
                byteBufferLength = 0
                

    return dataOK, frameNumber, detObj

# ------------------------------------------------------------------

# Funtion to process collision avoidance logic
def process_collision_logic(detObj, max_objects, stop_threshold):
    """
    Procesa la lógica de colisión.
    1. Filtra los N (max_objects) objetos más cercanos.
    2. Comprueba si alguno de ellos está por debajo del umbral (stop_threshold).
    Devuelve el flag (1=STOP, 0=GO) y un diccionario con los objetos filtrados.
    """
    
    # Flag por defecto: 0 (GO)
    radar_collision_stop = 0
    
    # Diccionario para los objetos filtrados
    filtered_detObj = {}
    
    # Comprueba si se ha detectado algún objeto
    if detObj and detObj["numObj"] > 0:
        
        # --- 1. Filtrar los N objetos más cercanos ---
        
        # Obtiene el array de distancias (rangos)
        ranges = detObj["range"]
        
        # Obtiene los *índices* que ordenarían el array de rangos (de menor a mayor)
        sorted_indices = np.argsort(ranges)
        
        # Coge solo los N primeros índices (los más cercanos)
        # Limita por si se detectan menos objetos que MAX_OBJECTS_TO_CONSIDER
        num_to_keep = min(detObj["numObj"], max_objects)
        closest_indices = sorted_indices[:num_to_keep]
        
        # --- 2. Crear el nuevo diccionario de objetos filtrado ---
        filtered_detObj["numObj"] = num_to_keep
        filtered_detObj["range"] = detObj["range"][closest_indices]
        filtered_detObj["doppler"] = detObj["doppler"][closest_indices]
        filtered_detObj["peakVal"] = detObj["peakVal"][closest_indices]
        filtered_detObj["x"] = detObj["x"][closest_indices]
        filtered_detObj["y"] = detObj["y"][closest_indices]
        filtered_detObj["z"] = detObj["z"][closest_indices]

        # --- 3. Comprobar el umbral de parada ---
        
        # Comprueba si CUALQUIERA (np.any) de los rangos filtrados es menor que el umbral
        if np.any(filtered_detObj["range"] < stop_threshold):
            radar_collision_stop = 1 # ¡STOP!
            
    else:
        # Si no hay objetos, el flag es 0 (GO)
        radar_collision_stop = 0
        
    return radar_collision_stop, filtered_detObj

# ------------------------------------------------------------------

# ------------------------------------------------------------------

# Funtion to update the data and display in the plot
# Funtion to update the data and display in the plot
def update():
     
    dataOk = 0
    global detObj
    x = []
    y = []
    
    # 1. Lee y decodifica los datos brutos del radar
    dataOk, frameNumber, detObj_raw = readAndParseData14xx(Dataport, configParameters)
    
    # 2. Procesa la lógica de colisión
    radar_collision_stop, filtered_detObj = process_collision_logic(detObj_raw, MAX_OBJECTS_TO_CONSIDER, STOP_DISTANCE_THRESHOLD)
    
    # --- Modificación Aquí ---
    
    # Imprime el flag en la consola en cada trama
    if dataOk:
        print(f"FLAG DE COLISIÓN: {radar_collision_stop}")

        # 3. Actualiza la gráfica (comentado) Y AHORA IMPRIME LOS PUNTOS
        if filtered_detObj and filtered_detObj["numObj"] > 0:
            # Pasa los datos filtrados a la variable global 'detObj'
            # para que el bucle MAIN los pueda guardar
            detObj = filtered_detObj 
            
            print(f"--- Detectados {filtered_detObj['numObj']} objetos (los {MAX_OBJECTS_TO_CONSIDER} más cercanos) ---")
            for i in range(filtered_detObj['numObj']):
                x_val = filtered_detObj['x'][i]
                y_val = filtered_detObj['y'][i]
                z_val = filtered_detObj['z'][i]
                r_val = filtered_detObj['range'][i]
                print(f"  Obj {i}: (X={x_val:.2f}, Y={y_val:.2f}, Z={z_val:.2f}) m | Distancia: {r_val:.2f} m")

            x = -filtered_detObj["x"]
            y = filtered_detObj["y"]
            
            # s.setData(x,y)
            # app.processEvents()
        
        # Si dataOk pero no hay objetos (o se filtraron todos)
        elif dataOk: 
            detObj = {} # Limpia el detObj global
            # s.setData([],[]) # Limpia la gráfica
            # app.processEvents()
            
    else:
        # Si dataOk es 0, imprime esto para saber que el script sigue corriendo
        print("Esperando datos del radar...") 
        
    return dataOk


# -------------------------    MAIN   -----------------------------------------  

# Configurate the serial port
CLIport, Dataport = serialConfig(configFileName)

# Get the configuration parameters from the configuration file
configParameters = parseConfigFile(configFileName)

# # START QtAPPfor the plot
# app = QtWidgets.QApplication([])

# # Set the plot 
# pg.setConfigOption('background','w')
# win = pg.GraphicsLayoutWidget()      # 1. Cambia GraphicsWindow por GraphicsLayoutWidget
# win.setWindowTitle('2D scatter plot') # 2. Establece el título de la ventana de esta forma
# win.show()                          # 3. Añade esta línea para mostrar la ventana
# p = win.addPlot()                   # 4. Esta línea se mantiene igual
# p.setXRange(-0.5,0.5)
# p.setYRange(0,1.5)
# p.setLabel('left', text = 'Y position (m)')
# p.setLabel('bottom', text= 'X position (m)')
# s = p.plot([],[],pen=None,symbol='o')
    
   
# Main loop 
detObj = {}  
frameData = {}    
currentIndex = 0
while True:
    try:
        # Update the data and check if the data is okay
        dataOk = update()
        
        if dataOk:
            # Store the current frame into frameData
            if detObj:
                frameData[currentIndex] = detObj
                currentIndex += 1
        
        time.sleep(0.033) # Sampling frequency of 30 Hz
        
    # Stop the program and close everything if Ctrl + c is pressed
    except KeyboardInterrupt:
        CLIport.write(('sensorStop\n').encode())
        CLIport.close()
        Dataport.close()
        # win.close()
        break
        
    
