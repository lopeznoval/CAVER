import sys
import LoRaNode_bis as LRN
from parameters import *
import time

import os

if __name__ == "__main__":
    node = None 

    try:
        node = LRN.LoRaNode(
            SERIAL_PORT,
            NODE_ADDRESS,
            FREQUENCY,
            POWER,
            rssi=True,
            EB=EB,
            robot_port=SERIAL_PORT_ROBOT,
            robot_baudrate=BAUDRATE_ROBOT,
            ip_sock=UDP_IP,
            port_sock=UDP_PORT,
            sens_port=SERIAL_PORT_SENS,
            sens_baudrate=BAUDRATE_SENS
        )
        node.run()
    except Exception as e:
        print(f"❌ Error initializing LoRaNode: {e}")

    if node is None or getattr(node, "is_base", False):
        try:
            from EB_RobotGUI import EB_RobotGUI_bis
            from PyQt6.QtWidgets import QApplication  # type: ignore+
            import os, sys

            base_path = os.path.dirname(os.path.abspath(__file__))
            print("🟢 Starting GUI...")

            app = QApplication(sys.argv)

            style_path = os.path.join(base_path, "styles.qss")
            if os.path.exists(style_path):
                with open(style_path, "r") as f:
                    qss = f.read()
                app.setStyleSheet(qss)
            else:
                print("⚠️ Archivo styles.qss no encontrado. Continuando sin estilo.")

            gui = EB_RobotGUI_bis(node)
            gui.show()
            sys.exit(app.exec())

        except Exception as e:
            print(f"❌ Error al iniciar la GUI: {e}")

    else:
        try:
            print("🟡 Nodo secundario activo. Esperando...")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("🛑 Interrupción detectada. Deteniendo nodo...")
            node.stop()
