import tkinter as tk
from tkinter import ttk, scrolledtext
import json, time
from sx126x import sx126x

# ==== Configuración LoRa ====
SERIAL_PORT = "COM4"        # puerto LoRa en Windows
FREQUENCY = 433
NODE_ADDRESS = 20            # dirección del PC
DEST_ADDRESS = 2            # dirección de la Raspberry
POWER = 0

# Mismo formato que el código que sí te funciona
RELAY_BIT = 1
TYPE_MSG = 1
ID_MSG = 0

class RobotGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("UGV02 LoRa Control Panel")
        self.master.geometry("600x750")
        self.master.configure(bg="#f4f4f4")

        # Inicializar LoRa (mismo que tu otro script)
        self.lora = sx126x(
            serial_num=SERIAL_PORT,
            freq=FREQUENCY,
            addr=NODE_ADDRESS,
            power=POWER,
            rssi=True
        )

        ttk.Label(master, text="Control del Robot (LoRa)", font=("Segoe UI", 12, "bold"), background="#f4f4f4").pack(pady=10)

        # Controles
        frame = tk.Frame(master, bg="#f4f4f4")
        frame.pack(pady=10)

        ttk.Button(frame, text="↑ Adelante", width=14, command=lambda: self.move_robot("forward")).grid(row=0, column=1, pady=3)
        ttk.Button(frame, text="← Izquierda", width=14, command=lambda: self.move_robot("left")).grid(row=1, column=0, padx=3)
        ttk.Button(frame, text="Stop", width=14, command=lambda: self.move_robot("stop")).grid(row=1, column=1, pady=3)
        ttk.Button(frame, text="→ Derecha", width=14, command=lambda: self.move_robot("right")).grid(row=1, column=2, padx=3)
        ttk.Button(frame, text="↓ Atrás", width=14, command=lambda: self.move_robot("backward")).grid(row=2, column=1, pady=3)

        ttk.Separator(master, orient='horizontal').pack(fill='x', pady=10)

        self.output = scrolledtext.ScrolledText(master, wrap=tk.WORD, font=("Consolas", 9), height=12)
        self.output.pack(fill="both", expand=True, padx=5, pady=5)

    def send_lora_command(self, cmd_dict):
        """Empaqueta y envía comando JSON por LoRa, usando el mismo formato que el script funcional"""
        message = json.dumps(cmd_dict)
        packet = bytes([
            DEST_ADDRESS >> 8,
            DEST_ADDRESS & 0xFF,
            NODE_ADDRESS >> 8,
            NODE_ADDRESS & 0xFF,
            RELAY_BIT | (TYPE_MSG & 0x7F),
            ID_MSG & 0xFF
        ]) + message.encode()

        self.lora.send(packet)
        self._log(f"📡 Sent LoRa: {message}")

    def move_robot(self, direction):
        """Define comandos del robot"""
        commands = {
            "forward": {"T": 1, "L": 0.5, "R": 0.5},
            "backward": {"T": 1, "L": -0.5, "R": -0.5},
            "left": {"T": 1, "L": -0.3, "R": 0.3},
            "right": {"T": 1, "L": 0.3, "R": -0.3},
            "stop": {"T": 1, "L": 0, "R": 0},
        }
        cmd = commands.get(direction)
        if cmd:
            self.send_lora_command(cmd)

    def _log(self, text):
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = RobotGUI(root)
    root.mainloop()
