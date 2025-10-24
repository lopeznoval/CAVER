import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json, threading, time
from sx126x import sx126x  # Tu clase LoRa
import requests

# ==== Configuración LoRa ====
SERIAL_PORT = "COM4"        # puerto LoRa en Windows, en RPi "/dev/ttyUSB0"
FREQUENCY = 433
NODE_ADDRESS = 20            # dirección del PC
DEST_ADDRESS = 2             # dirección del robot
POWER = 0
RELAY_BIT = 1
TYPE_MSG = 1
ID_MSG = 0


class RobotGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("UGV02 Robot Control Panel")
        self.master.geometry("600x750")
        self.master.configure(bg="#f4f4f4")

        # --- Inicializar LoRa ---
        self.lora = sx126x(
            serial_num=SERIAL_PORT,
            freq=FREQUENCY,
            addr=NODE_ADDRESS,
            power=POWER,
            rssi=True
        )

        self.feedback_running = False
        self.feedback_thread = None

        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("TLabel", background="#f4f4f4", font=("Segoe UI", 10))

        main_frame = tk.Frame(master, bg="#f4f4f4")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- IP Entry ---
        # ttk.Label(main_frame, text="Robot IP Address:").pack(pady=(5, 3))
        # self.ip_entry = ttk.Entry(main_frame, width=30, font=("Consolas", 10))
        # self.ip_entry.insert(0, "192.168.4.1")
        # self.ip_entry.pack()

        # ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        # --- Movement Control ---
        ttk.Label(main_frame, text="🕹️ Movement Control", font=("Segoe UI", 11, "bold")).pack()
        move_frame = tk.Frame(main_frame, bg="#f4f4f4")
        move_frame.pack(pady=8)

        ttk.Button(move_frame, text="↑ Forward", width=14,
                   command=lambda: self.move_robot("forward")).grid(row=0, column=1, pady=3)
        ttk.Button(move_frame, text="← Left", width=14,
                   command=lambda: self.move_robot("left")).grid(row=1, column=0, padx=3)
        ttk.Button(move_frame, text="Stop", width=14,
                   command=lambda: self.move_robot("stop")).grid(row=1, column=1, pady=3)
        ttk.Button(move_frame, text="→ Right", width=14,
                   command=lambda: self.move_robot("right")).grid(row=1, column=2, padx=3)
        ttk.Button(move_frame, text="↓ Backward", width=14,
                   command=lambda: self.move_robot("backward")).grid(row=2, column=1, pady=3)

        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        # --- OLED Control ---
        ttk.Label(main_frame, text="🖥️ OLED Screen Control", font=("Segoe UI", 11, "bold")).pack()
        oled_frame = tk.Frame(main_frame, bg="#f4f4f4")
        oled_frame.pack(pady=5)

        tk.Label(oled_frame, text="Line (0–3):", bg="#f4f4f4").grid(row=0, column=0, padx=5)
        self.line_var = tk.StringVar(value="0")
        self.line_entry = ttk.Entry(oled_frame, width=5, textvariable=self.line_var)
        self.line_entry.grid(row=0, column=1, padx=5)

        tk.Label(oled_frame, text="Text:", bg="#f4f4f4").grid(row=1, column=0, padx=5, pady=3)
        self.text_entry = ttk.Entry(oled_frame, width=40)
        self.text_entry.grid(row=1, column=1, padx=5, pady=3)

        ttk.Button(main_frame, text="Send to OLED", width=20, command=self.send_oled).pack(pady=4)
        ttk.Button(main_frame, text="Restore OLED", width=20,
                   command=lambda: self.send_cmd({"T": -3})).pack(pady=2)

        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        # --- Retrieve Info ---
        ttk.Label(main_frame, text="📡 Retrieve Information", font=("Segoe UI", 11, "bold")).pack()
        info_frame = tk.Frame(main_frame, bg="#f4f4f4")
        info_frame.pack(pady=5)

        ttk.Button(info_frame, text="Get IMU Data", width=20,
                   command=lambda: self.send_cmd({"T": 126})).grid(row=0, column=0, padx=5, pady=3)
        ttk.Button(info_frame, text="Get Chassis Feedback", width=20,
                   command=lambda: self.send_cmd({"T": 130})).grid(row=0, column=1, padx=5, pady=3)

        ttk.Button(info_frame, text="Start Auto Feedback", width=20,
                   command=self.start_feedback).grid(row=1, column=0, padx=5, pady=3)
        ttk.Button(info_frame, text="Stop Auto Feedback", width=20,
                   command=self.stop_feedback).grid(row=1, column=1, padx=5, pady=3)

        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=10)

        # --- Response Log ---
        ttk.Label(main_frame, text="📄 Response Log", font=("Segoe UI", 11, "bold")).pack()
        log_frame = tk.Frame(main_frame, bg="#f4f4f4")
        log_frame.pack(fill="both", expand=True)

        self.output = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, font=("Consolas", 9), height=12
        )
        self.output.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Key bindings ---
        self.master.bind("<Up>", lambda e: self.move_robot("forward"))
        self.master.bind("<Down>", lambda e: self.move_robot("backward"))
        self.master.bind("<Left>", lambda e: self.move_robot("left"))
        self.master.bind("<Right>", lambda e: self.move_robot("right"))
        self.master.bind("<space>", lambda e: self.move_robot("stop"))

        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.listen_thread = threading.Thread(target=self.listen_lora, daemon=True)
        self.listen_thread.start()
        self.waiting_for_response = False
        

    # --- Movement logic ---
    def move_robot(self, direction):
        commands = {
            "forward": {"T": 1, "L": 0.5, "R": 0.5},
            "backward": {"T": 1, "L": -0.5, "R": -0.5},
            "left": {"T": 1, "L": -0.3, "R": 0.3},
            "right": {"T": 1, "L": 0.3, "R": -0.3},
            "stop": {"T": 1, "L": 0, "R": 0},
        }
        cmd = commands.get(direction)
        if cmd:
            self.send_cmd(cmd)

    # --- OLED ---
    def send_oled(self):
        try:
            line = int(self.line_var.get())
            text = self.text_entry.get()
            cmd = {"T": 3, "lineNum": line, "Text": text}
            self.send_cmd(cmd)
        except ValueError:
            messagebox.showerror("Error", "Line number must be 0–3.")

    # --- Send command ---
    def send_cmd(self, cmd):
        # Enviar por LoRa
        message = json.dumps(cmd)
        packet = bytes([
            DEST_ADDRESS >> 8,
            DEST_ADDRESS & 0xFF,
            NODE_ADDRESS >> 8,
            NODE_ADDRESS & 0xFF,
            RELAY_BIT | (TYPE_MSG & 0x7F),
            ID_MSG & 0xFF
        ]) + message.encode()
        self.lora.send(packet)
        self._append_output(f"📡 LoRa sent: {message}")

        if hasattr(self, "ip_entry"):
            ip = self.ip_entry.get().strip()
            if ip:
                threading.Thread(target=self._send_request, args=(ip, cmd), daemon=True).start()

        # Enviar por IP
        #ip = self.ip_entry.get().strip()
        #if ip:
            #threading.Thread(target=self._send_request, args=(ip, cmd), daemon=True).start()

    def _send_request(self, ip, cmd):
        try:
            url = f"http://{ip}/js?json={json.dumps(cmd)}"
            r = requests.get(url, timeout=3)
            self._append_output(f"> {cmd}\n{r.text}\n")
        except Exception as e:
            self._append_output(f"⚠️ Error HTTP: {e}\n")

    # --- Feedback ---
    def start_feedback(self):
        self.waiting_for_response = True
        if self.feedback_running:
            messagebox.showinfo("Info", "Auto feedback already running.")
            return
        self.feedback_running = True
        self.send_cmd({"T": 131, "cmd": 1})
        self.feedback_thread = threading.Thread(target=self._feedback_loop, daemon=True)
        self.feedback_thread.start()
        self._append_output("✅ Auto feedback started.\n")

    def stop_feedback(self):
        if not self.feedback_running:
            messagebox.showinfo("Info", "Auto feedback is not active.")
            return
        self.feedback_running = False
        self.send_cmd({"T": 131, "cmd": 0})
        self._append_output("🛑 Auto feedback stopped.\n")

    def _feedback_loop(self):
        """Solicita periódicamente feedback al robot vía LoRa."""
        self.waiting_for_response = True
        while self.feedback_running:
            try:
                # Enviar comando por LoRa para solicitar feedback
                self.send_cmd({"T": 130})
            except Exception as e:
                self._append_output(f"⚠️ Feedback error: {e}\n")
            time.sleep(1)
        # ip = self.ip_entry.get().strip()
        # while self.feedback_running:
        #     if ip:
        #         try:
        #             url = f"http://{ip}/js?json={json.dumps({'T':130})}"
        #             r = requests.get(url, timeout=3)
        #             self._append_output(f"[Feedback] {r.text.strip()}\n")
        #         except Exception as e:
        #             self._append_output(f"⚠️ Feedback error: {e}\n")
        #     time.sleep(1)

    def _append_output(self, text):
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)

    def on_close(self):
        self.feedback_running = False
        self.master.destroy()
        
    def listen_lora(self):
        """Escucha los mensajes que llegan por LoRa desde la Raspberry/Robot y reconstruye JSON completos."""
        buffer = ""  # almacena fragmentos de mensajes

        while True:
            if self.lora.ser.in_waiting > 0:
                data = self.lora.ser.read(self.lora.ser.in_waiting)
                if len(data) >= 8:
                    src = (data[2] << 8) | data[3]
                    body = data[6:]
                    try:
                        msg_part = body.decode('utf-8', errors='ignore')
                        buffer += msg_part  # acumulamos el fragmento recibido

                        # Mientras haya un JSON completo en el buffer
                        while "{" in buffer and "}" in buffer:
                            start = buffer.find("{")
                            end = buffer.find("}", start)
                            if end == -1:
                                break

                            # Extraer mensaje completo
                            complete_msg = buffer[start:end+1]
                            buffer = buffer[end+1:]

                            # Solo mostramos si se ha solicitado desde la GUI
                            if self.waiting_for_response:
                                print(f"From {src}: {complete_msg}")
                                self._append_output(f"From {src}: {complete_msg}")

                                # Si solo esperas una respuesta, puedes resetear la bandera:
                                self.waiting_for_response = False

                    except Exception as e:
                        print(f"Error decodificando: {e}")
                        self._append_output(f"Error decodificando: {e}")

            time.sleep(0.1)

if __name__ == "__main__":
    root = tk.Tk()
    app = RobotGUI(root)
    root.mainloop()
