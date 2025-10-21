#!/usr/bin/python3
# -*- coding: UTF-8 -*-

import time
import sys
from sx126x import sx126x

class LoRaReceiver:
    def __init__(self):
        # Configuration - CHANGE THESE TO MATCH YOUR SETUP
        self.SERIAL_PORT = "/dev/ttyUSB1"  # e.g., "/dev/ttyS0" for Raspberry Pi
        #FREQUENCY = 410            # MHz (850-930 or 410-493)
        #self.NODE_ADDRESS = 0              # Receiver address (0-65535)
        #self.POWER = 0                    # dBm (10, 13, 17, or 22)

        # Initialize LoRa module
        self.node = sx126x(
            serial_num=self.SERIAL_PORT,
         #   freq=self.FREQUENCY,
         #   addr=self.NODE_ADDRESS,
         #   power=self.POWER,
         #   rssi=True  # Enable RSSI reporting
        )

        print(f"LoRa Receiver Initialized:")
        print(f"  Port: {self.SERIAL_PORT}")
        #print(f"  Frequency: {self.FREQUENCY}MHz")
        #print(f"  Node Address: {self.NODE_ADDRESS}")
        # print(f"  Power: {self.POWER}dBm")
        print("\nListening for messages... (Press Ctrl+C to stop)\n")

    def run(self):
        # self.node.get_current_settings()
        try:
            while True:
                # Check for incoming messages
                if self.node.ser.inWaiting() > 0:
                    time.sleep(0.5)  # Wait for complete message
                    r_buff = self.node.ser.read(self.node.ser.inWaiting())

                    # Extract message components
                    addr = (r_buff[0] << 8) + r_buff[1]
                    freq = r_buff[2] + self.node.start_freq
                    message = r_buff[3:-1].decode('utf-8', errors='ignore')

                    # Print message details
                    print("\n=== Received Message ===")
                    print(f"From Node: {addr}")
                    print(f"Frequency: {freq}.125MHz")
                    print(f"Message: {message}")

                    # Print RSSI if enabled
                    #if self.node.rssi and len(r_buff) > 0:
                    rssi = 256 - r_buff[-1]
                    print(f"Packet RSSI: -{rssi}dBm")
                    self.node.get_channel_rssi()

                time.sleep(0.1)  # Small delay to reduce CPU usage

        except KeyboardInterrupt:
            print("\nStopping receiver...")
        finally:
            self.node.close()

if __name__ == "__main__":
     receiver = LoRaReceiver()
     receiver.run()
