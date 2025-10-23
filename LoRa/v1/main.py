import LoRaNode_bis as LRN
from parameters import *

if __name__ == "__main__":
    node = LRN.LoRaNode(SERIAL_PORT, NODE_ADDRESS, FREQUENCY, POWER, rssi=True, EB=1, robot_port=SERIAL_PORT_ROBOT, robot_baudrate=BAUDRATE_ROBOT)
    node.run()

    