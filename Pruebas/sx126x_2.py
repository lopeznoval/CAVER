#!/usr/bin/python3
# -*- coding: UTF-8 -*-

import time
import serial

class sx126x:
    # Configuration registers
    cfg_reg = [0xC2, 0x00, 0x09, 0x00, 0x00, 0x00, 0x62, 0x00, 0x12, 0x43, 0x00, 0x00]

    # Frequency settings
    start_freq = 850
    offset_freq = 10  # 850 + 18 = 868MHz

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

    def __init__(self, serial_num, freq, addr, power, rssi=False, air_speed=2400,
                 net_id=0, buffer_size=240, crypt=0, relay=False, lbt=False, wor=False):
        self.serial_n = serial_num
        self.addr = addr
        self.freq = freq
        self.power = power
        self.rssi = rssi

        # Initialize serial connection
        self.ser = serial.Serial(
            port=serial_num,
            baudrate=9600,
            timeout=1,
            rtscts=False,
            dsrdtr=False
        )
        self.ser.flushInput()

    def send(self, data):
        """Send data through LoRa module"""
        self.ser.write(data)
        time.sleep(0.1)

    def receive(self):
        """Receive data from LoRa module"""
        if self.ser.in_waiting > 0:
            time.sleep(0.5)  # Wait for complete message
            r_buff = self.ser.read(self.ser.in_waiting)

            # Extract message components
            addr = (r_buff[0] << 8) + r_buff[1]
            freq = r_buff[2] + self.start_freq
            message = r_buff[3:-1].decode('utf-8', errors='ignore')

            print(f"Received from {addr} @ {freq}MHz: {message}")

            if self.rssi and len(r_buff) > 0:
                rssi = 256 - r_buff[-1]
                print(f"RSSI: -{rssi}dBm")

    def close(self):
        """Close serial connection"""
        self.ser.close()

    def get_channel_rssi(self):
        time.sleep(0.1)
        self.ser.flushInput()
        self.ser.write(bytes([0xC0,0xC1,0xC2,0xC3,0x00,0x02]))
        time.sleep(0.5)
        re_temp = bytes(5)
        if self.ser.inWaiting() > 0:
            time.sleep(0.1)
            re_temp = self.ser.read(self.ser.inWaiting())
        if re_temp[0] == 0xC1 and re_temp[1] == 0x00 and re_temp[2] == 0x02:
            print("the current noise rssi value: -{0}dBm".format(256-re_temp[3]),flush = True)
            # print("the last receive packet rssi value: -{0}dBm".format(256-re_temp[4]))
        else:
            # pass
            print("receive rssi value fail",flush = True)
            # print("receive rssi value fail: ",re_temp)
    def read_config_register(self):
        """Read the module's configuration registers"""
        try:
            # Command to read config (0xC1 followed by 0x00 0x09)
            read_cmd = bytes([0xC1, 0x00, 0x09])
            self.ser.flushInput()
            self.ser.write(read_cmd)
            time.sleep(0.2)

            if self.ser.inWaiting() >= 12:
                config = self.ser.read(12)
                return config
            return None
        except Exception as e:
            print(f"Error reading config: {e}")
            return None

    def get_current_settings(self):
        """Parse and display current module settings"""
        config = self.read_config_register()
        if not config or len(config) < 12:
            print("Failed to read configuration")
            return

        print("\n=== Current Module Configuration ===")

        # Address
        addr = (config[3] << 8) | config[4]
        print(f"Node Address: {addr}")

        # Network ID
        net_id = config[5]
        print(f"Network ID: {net_id}")

        # UART settings (Baudrate + Air Data Rate)
        uart_setting = config[6]
        baud_rate = {
            0x00: 1200,
            0x20: 2400,
            0x40: 4800,
            0x60: 9600,
            0x80: 19200,
            0xA0: 38400,
            0xC0: 57600,
            0xE0: 115200
        }.get(uart_setting & 0xE0, "Unknown")

        air_data_rate = {
            0x01: 1200,
            0x02: 2400,
            0x03: 4800,
            0x04: 9600,
            0x05: 19200,
            0x06: 38400,
            0x07: 62500
        }.get(uart_setting & 0x07, "Unknown")

        print(f"UART Baudrate: {baud_rate} bps")
        print(f"Air Data Rate: {air_data_rate} bps")

        # Frequency
        freq_offset = config[8]
        base_freq = 850 if self.freq > 850 else 410
        current_freq = base_freq + freq_offset
        print(f"Frequency: {current_freq}.125MHz")

        # Power
        power_setting = config[7] & 0x03
        power_levels = {
            0x00: "22dBm",
            0x01: "17dBm",
            0x02: "13dBm",
            0x03: "10dBm"
        }
        print(f"Transmit Power: {power_levels.get(power_setting, 'Unknown')}")

        # RSSI setting
        rssi_enabled = bool(config[9] & 0x80)
        print(f"RSSI Reporting: {'Enabled' if rssi_enabled else 'Disabled'}")

        # Crypt (if used)
        crypt = (config[10] << 8) | config[11]
        if crypt != 0:
            print(f"Crypt Key: {crypt:04X}")
