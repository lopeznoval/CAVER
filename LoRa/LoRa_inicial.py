#!/usr/bin/python3

import time
import threading
from sx126x import sx126x

# Configuration
#SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_PORT = "COM3"

FREQUENCY = 433          # MHz
NODE_ADDRESS = 20        # Your node address
NODE_ADDRESS_DEST = 1    # Destination address
RELAY_BIT = 1            # Relay flag
TYPE_MSG = 1             # Message type
ID_MSG = 0               # Message ID
POWER = 0                # dBm
MESSAGE_INTERVAL = 6     # seconds

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
        """Send automatic messages every 10 seconds"""
        message_count = 0
        while self.running:
            message = f"Auto-message #{message_count} from node {NODE_ADDRESS} Prueba"
            data = bytes([
                NODE_ADDRESS_DEST >> 8,         # Sender address high
                NODE_ADDRESS_DEST & 0xFF,       # Sender address low
                NODE_ADDRESS >> 8,              # Sender address high
                NODE_ADDRESS & 0xFF,            # Sender address low
                RELAY_BIT | (TYPE_MSG & 0x7F),                # Message type
                ID_MSG & 0xFF                   # Message ID
            ]) + message.encode()

            print(f"Transmited: {data}")
            self.node.send(data)
            print(f"[{time.strftime('%H:%M:%S')}] Sent: {message}")
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
