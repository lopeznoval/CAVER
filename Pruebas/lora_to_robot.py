#!/usr/bin/python3
# -*- coding: UTF-8 -*-

import time
import serial
import json
from sx126x import sx126x

# Configuración LoRa
SERIAL_PORT_LORA = "/dev/ttyAMA10"
FREQUENCY = 433
NODE_ADDRESS = 2     # Dirección de la Raspberry
POWER = 0

# Configuración del robot (conexión por cable)
SERIAL_PORT_ROBOT = "/dev/ttyACM0"  # o /dev/ttyUSB1 según tu conexión
BAUDRATE_ROBOT = 115200

def main():
    lora = sx126x(serial_num=SERIAL_PORT_LORA, freq=FREQUENCY, addr=NODE_ADDRESS, power=POWER, rssi=True)
    robot = serial.Serial(SERIAL_PORT_ROBOT, BAUDRATE_ROBOT, timeout=1)

    print(f"Listening on LoRa {NODE_ADDRESS} @ {FREQUENCY}MHz")

    while True:
        print(f"In waiting: {lora.ser.in_waiting}")

        if lora.ser.in_waiting > 0:
            time.sleep(0.5)
            data = lora.ser.read(lora.ser.in_waiting)
            if len(data) < 8:
                continue

            dest = (data[0] << 8) | data[1]
            src  = (data[2] << 8) | data[3]
            msg_type = data[4]
            msg_id = data[5]
            body = data[6:]

            if dest != NODE_ADDRESS:
                continue  # mensaje no es para esta Raspi

            try:
                cmd = json.loads(body.decode('utf-8'))
                print(f"📥 From {src} → CMD: {cmd}")
                robot.write((json.dumps(cmd) + "\n").encode())
            except Exception as e:
                print(f"⚠️ Error decoding JSON: {e}")

        time.sleep(0.1)

if __name__ == "__main__":
    main()
