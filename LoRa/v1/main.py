import LoRaNode_bis as LRN

if __name__ == "__main__":
    node = LRN.LoRaNode("COM3", 1, 410, 0, True, 1)
    node.run()

    