#!/usr/bin/python3

import time
import threading
from sx126x import sx126x

# Configuration
#SERIAL_PORT = "/dev/ttyUSB0"
# SERIAL_PORT = "COM13"
SERIAL_PORT = "COM4"

# FREQUENCY = 868       # MHz
FREQUENCY = 433       # MHz
NODE_ADDRESS = 11      # Your node address
POWER = 0            # dBm
MESSAGE_INTERVAL = 10 # seconds

class LoRaNode:
    def __init__(self):
        self.running = True
        self.node = sx126x(
            serial_num=SERIAL_PORT,
            addr=NODE_ADDRESS,
            freq=FREQUENCY,
            power=POWER,
            rssi=True
        )

    def periodic_send(self):
        """Send automatic messages every 10 seconds"""
        message_count = 0
        while self.running:
            message = f"Auto-message #{message_count} from node {NODE_ADDRESS} Prueba "
            data = bytes([
                0xFF, 0xFF,             # Broadcast address
                self.node.offset_freq,  # Frequency offset
                NODE_ADDRESS >> 8,      # Sender address high
                NODE_ADDRESS & 0xFF,    # Sender address low
                self.node.offset_freq    # Sender frequency offset
            ]) + message.encode()

            # data = bytes([
            #     NODE_ADDRESS >> 8,      # From address high
            #     NODE_ADDRESS & 0xFF,    # From address low
            #     self.node.offset_freq   # Frequency offset
            # ]) + message.encode()


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
