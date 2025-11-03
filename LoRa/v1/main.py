import sys
import LoRaNode_bis as LRN
from parameters import *
import time
import tkinter as tk

import os

if __name__ == "__main__":
    node = LRN.LoRaNode(SERIAL_PORT, NODE_ADDRESS, FREQUENCY, POWER, rssi=True, EB=EB, robot_port=SERIAL_PORT_ROBOT, robot_baudrate=BAUDRATE_ROBOT)
    node.run()

    if node.is_base:
        from EB_RobotGUI import EB_RobotGUI_bis
        from PyQt6.QtWidgets import QApplication #type: ignore
        base_path = os.path.dirname(os.path.abspath(__file__))
        print("GUI running (3)...")
        app = QApplication(sys.argv)
        try:
            with open(os.path.join(base_path, "styles.qss"), "r") as f:
                qss = f.read()
            app.setStyleSheet(qss)
        except FileNotFoundError:
            print("⚠️ Archivo styles.qss no encontrado. Continuando sin estilo.")
        print("GUI running (2)...")
        gui = EB_RobotGUI_bis(node)
        gui.show()
        print("GUI running (1)...")
        sys.exit(app.exec())
    else:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            node.stop()
