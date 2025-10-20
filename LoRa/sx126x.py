#!/usr/bin/python3
# -*- coding: UTF-8 -*-

import time
import serial

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
           #freq, addr, power, rssi=False, air_speed=2400,
                 #net_id=0, buffer_size=240, crypt=0, relay=False, lbt=False, wor=False):
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


        #self.ser =serial.Serial('COM13', 115200, timeout=1)
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
            print(f"Received: {r_buff}")
            # Extract message components
            addr = (r_buff[3] << 8) + r_buff[4]
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

    # def receive(self):
    #     """Receive data from LoRa module"""
    #     if self.ser.in_waiting > 0:
    #         time.sleep(0.5)
    #         r_buff = self.ser.read(self.ser.in_waiting)

    #         if len(r_buff) < 8:  # demasiado corto
    #             print("Received too short packet")
    #             return

    #         # Separar CRC recibido
    #         data, recv_crc_bytes = r_buff[:-2], r_buff[-2:]
    #         recv_crc = int.from_bytes(recv_crc_bytes, 'big')
    #         calc_crc = crc16_ccitt(data)

    #         if recv_crc != calc_crc:
    #             print(f"⚠️ CRC ERROR: received {recv_crc:04X}, expected {calc_crc:04X}")
    #             return

    #         print(f"✅ CRC OK ({calc_crc:04X})")

    #         addr = (data[3] << 8) + data[4]
    #         freq = data[2] + self.start_freq
    #         message = data[6:].decode('utf-8', errors='ignore')

    #         print(f"Received from {addr} @ {freq}MHz: {message}")

    #         if self.rssi and len(r_buff) > 0:
    #             rssi = 256 - r_buff[-3]
    #             print(f"RSSI: -{rssi}dBm")

    
def crc16_ccitt(data: bytes, poly=0x1021, init=0xFFFF) -> int:
    crc = init
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFFFF  # Mantenerlo en 16 bits
    return crc

