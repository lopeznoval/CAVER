import LoRaNode_bis as LRN
from parameters import *

import tkinter as tk
from EB_RobotGUI import EB_RobotGUI

if __name__ == "__main__":
    node = LRN.LoRaNode(SERIAL_PORT, NODE_ADDRESS, FREQUENCY, POWER, rssi=True, EB=1, robot_port=SERIAL_PORT_ROBOT, robot_baudrate=BAUDRATE_ROBOT)
    node.run()

    if node.is_base:
        root = tk.Tk()
        gui = EB_RobotGUI(root, node)
        root.mainloop()
