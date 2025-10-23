import serial
import time

class sx126x:
        # Configuration registers
    cfg_reg = [0xC2, 0x00, 0x09, 0x00, 0x00, 0x00, 0x62, 0x00, 0x12, 0x43, 0x00, 0x00]

    # Frequency settings
    start_freq = 410
    offset_freq = 23  # 850 + 18 = 868MHz

    # UART baudrate definitions
    SX126X_UART_BAUDRATE_1200 = 0x00
    SX126X_UART_BAUDRATE_2400 = 0x20
    SX126X_UART_BAUDRATE_4800 = 0x40
    SX126X_UART_BAUDRATE_9600 = 0x60
    SX126X_UART_BAUDRATE_19200 = 0x80
    SX126X_UART_BAUDRATE_38400 = 0xA0
    SX126X_UART_BAUDRATE_57600 = 0xC0
    SX126X_UART_BAUDRATE_115200 = 0xE0

    # Package size definitions
    SX126X_PACKAGE_SIZE_240_BYTE = 0x00
    SX126X_PACKAGE_SIZE_128_BYTE = 0x40
    SX126X_PACKAGE_SIZE_64_BYTE = 0x80
    SX126X_PACKAGE_SIZE_32_BYTE = 0xC0

    # Power definitions
    SX126X_Power_22dBm = 0x00
    SX126X_Power_17dBm = 0x01
    SX126X_Power_13dBm = 0x02
    SX126X_Power_10dBm = 0x03

    def __init__(self, serial_num, freq, addr, power, rssi=False, air_speed=2400, net_id=0, buffer_size=240, crypt=0, relay=False, lbt=False, wor=False):
        self.serial_n = serial_num
        self.freq = freq
        self.addr = addr
        self.power = power
        self.rssi = rssi
        self.ser = serial.Serial(serial_num, baudrate=9600, timeout=0.1)
        self.ser.flushInput()

    def send_bytes(self, data):
        print(f"Sending bytes: {data}")
        self.ser.write(data)

    def receive_bytes(self):
        if self.ser.in_waiting > 0:
            print(f"Receiving bytes...")
            return self.ser.read(self.ser.in_waiting)
        return None

    def close(self):
        self.ser.close()
