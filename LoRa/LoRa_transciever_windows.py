#!/usr/bin/python3

import time
import threading
from sx126x import sx126x, crc16_ccitt  

# Configuration
#SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_PORT = "COM3"

FREQUENCY = 433       # MHz
NODE_ADDRESS = 23      # Your node address
POWER = 0            # dBm
MESSAGE_INTERVAL = 6 # seconds

class LoRaNode:
    def __init__(self):
        self.running = True
        self.node = sx126x(
            serial_num=SERIAL_PORT,
            freq=FREQUENCY,
            addr=NODE_ADDRESS,
            power=POWER,
            rssi=True
        )

    def periodic_send(self):
        message_count = 0
        while self.running:
            message = f"Auto-message #{message_count} from node {NODE_ADDRESS}"
            payload = message.encode()

            # Construir paquete base
            packet = bytes([
                0xFF, 0xFF,             # Broadcast
                self.node.offset_freq,  # Frecuencia
                NODE_ADDRESS >> 8,      # Dirección alta
                NODE_ADDRESS & 0xFF,    # Dirección baja
                self.node.offset_freq   # Offset
            ]) + payload

            # Calcular y añadir CRC
            crc = crc16_ccitt(packet)
            packet += crc.to_bytes(2, 'big')

            print(f"Transmitting: {packet}")
            self.node.send(packet)
            print(f"[{time.strftime('%H:%M:%S')}] Sent: {message} (CRC={crc:04X})")

            message_count += 1
            time.sleep(MESSAGE_INTERVAL)

    def run(self):
        print(f"Starting LoRa node {NODE_ADDRESS} @ {FREQUENCY}MHz")
        print(f"Auto-sending every {MESSAGE_INTERVAL} seconds")
        print("Press Ctrl+C to stop\n")

        # Start sending thread
        send_thread = threading.Thread(target=self.periodic_send)
        send_thread.daemon = True
        send_thread.start()

        # Main receive loop
        try:
            while True:
                self.node.receive()
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopping...")
            self.running = False
            send_thread.join()
            self.node.close()

if __name__ == "__main__":
    node = LoRaNode()
    node.run()
