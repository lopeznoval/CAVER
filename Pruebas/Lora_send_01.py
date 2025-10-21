#!/usr/bin/python3
import serial
import time

class LoRaSender:
    def __init__(self, port="/dev/ttyUSB0", baudrate=115200):
        """Initialize LoRa module"""
        self.ser = serial.Serial(port, baudrate, timeout=1)
        time.sleep(0.1)  # Wait for module initialization
        print(f"LoRa module connected on {port}")

    def send_message(self, message, target_address=0xFFFF):
        """Send a text message to specified address (default: broadcast)"""
        try:
            # Message format: [To Addr High, To Addr Low, Freq Offset, From Addr High, From Addr Low, Freq Offset] + Message
            packet = bytes([
                target_address >> 8,    # To address high
                target_address & 0xFF,  # To address low
                18,                    # Frequency offset (868MHz - 850MHz base)
                0xFF,                  # From address high (you can change this)
                0xFF,                  # From address low
                18                     # Same freq offset
            ]) + message.encode('utf-8')

            self.ser.write(packet)
            print(f"Message sent to 0x{target_address:04X}")
            return True
        except Exception as e:
            print(f"Error sending: {e}")
            return False

    def close(self):
        """Clean up serial connection"""
        self.ser.close()

def main():
    # Initialize - CHANGE PORT IF NEEDED
    lora = LoRaSender("/dev/ttyUSB0")

    try:
        while True:
            # Get user input
            message = input("\nEnter message to send (or 'quit' to exit): ")
            if message.lower() == 'quit':
                break

            # Send message
            lora.send_message(message)

    except KeyboardInterrupt:
        print("\nUser interrupted")
    finally:
        lora.close()
        print("LoRa connection closed")

if __name__ == "__main__":
    main()
