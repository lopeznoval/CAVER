#!/usr/bin/python3
import serial
import time

class LoRaReceiver:
    def __init__(self, port="/dev/ttyUSB1", baudrate=115200):
        """Initialize LoRa module in receive mode"""
        self.ser = serial.Serial(port, baudrate, timeout=None)  # Blocking read
        time.sleep(0.1)  # Wait for module initialization
        print(f"LoRa receiver listening on {port} [CTRL+C to stop]")

    def receive_messages(self):
        """Continuously monitor for incoming messages"""
        try:
            while True:
                if self.ser.in_waiting > 0:
                    # Read all available bytes
                    data = self.ser.read(self.ser.in_waiting)

                    # Minimum packet is 6 bytes (header) + payload
                    if len(data) >= 6:
                        # Parse header
                        from_addr = (data[3] << 8) | data[4]
                        freq = 850 + data[2]  # Base freq + offset

                        # Extract message (skip 6-byte header)
                        message = data[6:].decode('utf-8', errors='replace')

                        # Display
                        print(f"\n[From 0x{from_addr:04X} @ {freq}MHz] {message}")
                    else:
                        print("! Incomplete packet received")

                time.sleep(0.1)  # Prevent CPU overload

        except KeyboardInterrupt:
            print("\nStopping receiver...")

    def close(self):
        """Clean up resources"""
        self.ser.close()

if __name__ == "__main__":
    # Initialize - CHANGE PORT IF NEEDED
    receiver = LoRaReceiver("/dev/ttyUSB1")

    try:
        receiver.receive_messages()
    finally:
        receiver.close()
        print("Receiver stopped")
