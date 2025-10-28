import sys
import LoRaNode_bis as LRN
from parameters import *

import tkinter as tk
from EB_RobotGUI import EB_RobotGUI, EB_RobotGUI_bis
from PyQt6.QtWidgets import QApplication
import os

if __name__ == "__main__":
    node = LRN.LoRaNode(SERIAL_PORT, NODE_ADDRESS, FREQUENCY, POWER, rssi=True, EB=1, robot_port=SERIAL_PORT_ROBOT, robot_baudrate=BAUDRATE_ROBOT)
    node.run()

    if node.is_base:
        # root = tk.Tk()
        # gui = EB_RobotGUI(root, node)
        # root.mainloop()
        base_path = os.path.dirname(os.path.abspath(__file__))
        app = QApplication(sys.argv)
        with open(os.path.join(base_path, "styles.qss"), "r") as f:
            qss = f.read()
        app.setStyleSheet(qss)
        gui = EB_RobotGUI_bis(node)
        gui.show()
        sys.exit(app.exec())
