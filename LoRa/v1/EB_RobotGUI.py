from LoRaNode_bis import LoRaNode
import json, threading, time, requests
import sys
import json
import threading
import time
import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu, QSlider,
    QTextEdit, QLineEdit, QComboBox, QMessageBox, QGridLayout, QGroupBox, QFrame, QTabWidget, QSizePolicy, QListWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from LoRaNode_bis import LoRaNode


class EB_RobotGUI_bis(QWidget):

    message_received = pyqtSignal(str)

    def __init__(self, loranode: LoRaNode = None):
        super().__init__()
        self.loranode = loranode
        self.msg_id = 1
        self.feedback_running = False
        self.feedback_thread = None

        self.loranode.on_message = self._on_lora_message
        self.loranode.on_alert = self._on_general_log

        self.setWindowTitle("UGV02 Robot Control Dashboard " + loranode.addr.__str__())
        self.setGeometry(200, 100, 1200, 700)

        main_layout = QHBoxLayout(self)
        

        # === COLUMNA 1: Pestañas ===
        col1 = QVBoxLayout()
        tabs = QTabWidget()

        # ------------------ TAB 1: Movimiento ------------------
        tab_move = QWidget()
        move_layout = QGridLayout()

        self.btn_forward = QPushButton("↑")
        self.btn_left = QPushButton("←")
        self.btn_stop = QPushButton("Stop")
        self.btn_right = QPushButton("→")
        self.btn_backward = QPushButton("↓")

        buttons = [
            (self.btn_forward, 0, 1, "forward"),
            (self.btn_left, 1, 0, "left"),
            (self.btn_stop, 1, 1, "stop"),
            (self.btn_right, 1, 2, "right"),
            (self.btn_backward, 2, 1, "backward"),
        ]

        for btn, r, c, cmd in buttons:
            btn.setFixedSize(100, 35)
            btn.clicked.connect(lambda _, d=cmd: self.move_robot(d))
            move_layout.addWidget(btn, r, c)

        tab_move.setLayout(move_layout)
        tabs.addTab(tab_move, "🕹️ Movimiento")

        # # === Layout principal vertical ===
        # mv_layout = QVBoxLayout()

        # # === Layout de velocidad ===
        # speed_layout = QHBoxLayout()

        # self.speed_label = QLabel("Velocidad: 50 %")
        # self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.speed_label.setStyleSheet("font-weight: bold; color: #00aaff; font-size: 14px;")

        # self.speed_slider = QSlider(Qt.Horizontal)
        # self.speed_slider.setRange(0, 100)
        # self.speed_slider.setValue(50)
        # self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        # self.speed_slider.setTickInterval(10)
        # self.speed_slider.valueChanged.connect(lambda v: self.speed_label.setText(f"Velocidad: {v} %"))

        # speed_layout.addWidget(QLabel("0 %"))
        # speed_layout.addWidget(self.speed_slider)
        # speed_layout.addWidget(QLabel("100 %"))

        # mv_layout.addLayout(speed_layout)
        # mv_layout.addWidget(self.speed_label)

        # # === Layout de movimiento ===
        # move_layout = QGridLayout()

        # self.btn_forward = QPushButton("↑")
        # self.btn_left = QPushButton("←")
        # self.btn_stop = QPushButton("Stop")
        # self.btn_right = QPushButton("→")
        # self.btn_backward = QPushButton("↓")

        # buttons = [
        #     (self.btn_forward, 0, 1, "forward"),
        #     (self.btn_left, 1, 0, "left"),
        #     (self.btn_stop, 1, 1, "stop"),
        #     (self.btn_right, 1, 2, "right"),
        #     (self.btn_backward, 2, 1, "backward"),
        # ]

        # for btn, r, c, cmd in buttons:
        #     btn.setFixedSize(100, 35)
        #     btn.clicked.connect(lambda _, d=cmd: self.move_robot(d))
        #     move_layout.addWidget(btn, r, c)

        # mv_layout.addLayout(move_layout)

        # # === Asignar layout principal al tab ===
        # tab_move.setLayout(mv_layout)
        # tabs.addTab(tab_move, "🕹️ Movimiento")

        # ------------------ TAB 2: OLED ------------------
        tab_oled = QWidget()
        oled_layout = QGridLayout()

        oled_layout.addWidget(QLabel("Línea (0–3):"), 0, 0)
        self.line_entry = QLineEdit("0")
        self.line_entry.setFixedWidth(50)
        oled_layout.addWidget(self.line_entry, 0, 1)

        oled_layout.addWidget(QLabel("Texto:"), 1, 0)
        self.text_entry = QLineEdit()
        self.text_entry.setFixedWidth(180)
        oled_layout.addWidget(self.text_entry, 1, 1)

        self.btn_send_oled = QPushButton("Enviar a OLED")
        self.btn_send_oled.clicked.connect(self.send_oled)
        oled_layout.addWidget(self.btn_send_oled, 2, 0, 1, 2)

        self.btn_reset_oled = QPushButton("Restaurar OLED")
        self.btn_reset_oled.clicked.connect(lambda: self.send_cmd(json.dumps({"T": -3})))
        self.btn_reset_oled.setObjectName("danger")
        oled_layout.addWidget(self.btn_reset_oled, 3, 0, 1, 2)

        tab_oled.setLayout(oled_layout)
        tabs.addTab(tab_oled, "🖥️ OLED")

        # ------------------ TAB 3: Comandos ------------------
        tab_cmd = QWidget()
        cmd_layout = QGridLayout()

        self.btn_imu = QPushButton("IMU Data")
        self.btn_feedback = QPushButton("Chassis Feedback")
        self.btn_imu.clicked.connect(lambda: self.send_cmd(json.dumps({"T": 126})))
        self.btn_feedback.clicked.connect(lambda: self.send_cmd(json.dumps({"T": 130})))

        cmd_layout.addWidget(self.btn_imu, 0, 0)
        cmd_layout.addWidget(self.btn_feedback, 0, 1)

        self.btn_start_feedback = QPushButton("Start Feedback")
        self.btn_stop_feedback = QPushButton("Stop Feedback")
        self.btn_start_feedback.clicked.connect(self.start_feedback)
        self.btn_stop_feedback.clicked.connect(self.stop_feedback)
        self.btn_stop_feedback.setObjectName("danger")

        cmd_layout.addWidget(self.btn_start_feedback, 1, 0)
        cmd_layout.addWidget(self.btn_stop_feedback, 1, 1)

        tab_cmd.setLayout(cmd_layout)
        tabs.addTab(tab_cmd, "⚙️ Comandos")

        # ----------------------- TAB 4: Imagen -----------------------
        tab_video = QWidget()
        video_layout = QVBoxLayout()

        self.btn_take_photo = QPushButton("Tomar Foto 📸")
        self.btn_take_photo.clicked.connect(self.take_photo)
        video_layout.addWidget(self.btn_take_photo)

        # Placeholder para la imagen recibida
        self.photo_label = QLabel("Aquí se mostrará la foto")
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setFixedSize(400, 300)
        video_layout.addWidget(self.photo_label)

        tab_video.setLayout(video_layout)
        tabs.addTab(tab_video, "📹 Video")

        # ----------------------- TAB 5: Logs generales -----------------------
        tab_logs = QWidget()
        logs_layout = QVBoxLayout()

        # QTextEdit para mostrar todos los logs del nodo
        self.general_logs = QTextEdit()
        self.general_logs.setReadOnly(True)
        self.general_logs.setPlaceholderText("Aquí se mostrará todo lo que sucede en el nodo...")

        logs_layout.addWidget(self.general_logs)
        tab_logs.setLayout(logs_layout)

        # Añadir el tab al QTabWidget
        tabs.addTab(tab_logs, "📝 Logs")

        # ------------------ Añadir pestañas a la columna ------------------
        col1.addWidget(tabs)


        # === Layout principal para columnas 2 y 3 ===
        right_layout = QVBoxLayout()  

        # ------------------ FILA 1: Comandos LoRa & Lista de Reports ------------------
        # === Comandos LoRa ===
        lora_group = QGroupBox("📤 Configuración del comando")
        lora_layout = QGridLayout()

        lora_layout.addWidget(QLabel("Dest Node:"), 0, 0)
        self.dest_entry = QLineEdit("2")
        self.dest_entry.setFixedWidth(60)
        lora_layout.addWidget(self.dest_entry, 0, 1)

        lora_layout.addWidget(QLabel("Msg Type:"), 0, 3)
        # self.type_combo = QComboBox()
        # self.type_combo.addItems([str(i) for i in range(1, 31)])
        # lora_layout.addWidget(self.type_combo, 0, 3)

        self.type_button = QPushButton("Seleccionar tipo de mensaje")
        lora_layout.addWidget(self.type_button, 0, 4)

        # --- Menú principal
        menu = QMenu(self)

        self.grups = {
            "Respuestas (1–4)": {
                1: "Confirmación de recepción",
                2: "Error en transmisión",
                3: "Respuesta de estado",
                4: "Fin de comunicación"
            },
            "Consultas (5–9)": {
                5: "Petición de datos",
                6: "Solicitud de conexión",
                7: "Ping de latencia",
                8: "Consulta de estado",
                9: "Solicitud de versión"
            },
            "Robot (10–19)": {
                10: "FeedBack",
                11: "Movimiento",
                12: "Oled",
                13: "",
                14: "",
                15: "",
                19: ""
            },
            "Sensores (20–24)": {
                20: "Lectura de temperatura",
                21: "Lectura de presión",
                22: "Lectura de humedad",
                23: "Lectura de luz ambiental",
                24: "Lectura de proximidad"
            },
            "Cámara/Radar (25–30)": {
                25: "Captura de imagen",
                26: "Iniciar streaming",
                27: "Detección de movimiento",
                28: "Seguimiento de objetivo",
                30: "Reset del módulo"
            },
            "Relay Flag (31)": {
                31: "Activar/Desactivar relay flag"
            }
        }

        # --- Crear submenús dinámicamente
        for grupo, elementos in self.grups.items():
            submenu = QMenu(grupo, self)
            for num, desc in elementos.items():
                action = QAction(f"{num} - {desc}", self)
                action.setToolTip(desc)  #
                action.triggered.connect(lambda checked, n=num, d=desc: self.set_selected_type(n, d))
                submenu.addAction(action)
            menu.addMenu(submenu)

        self.type_button.setMenu(menu)
        self.selected_type = 0

        lora_layout.addWidget(QLabel("Relay Bit:"), 0, 6)
        self.relay_combo = QComboBox()
        self.relay_combo.addItems(["0", "1"])
        self.relay_combo.setCurrentText("1")
        lora_layout.addWidget(self.relay_combo, 0, 7)
        
        lora_group.setLayout(lora_layout)
        right_layout.addWidget(lora_group, 1)
                
        self.btn_send_cmd = QPushButton("Enviar Comando")
        self.btn_send_cmd.clicked.connect(self.send_cmd)
        lora_layout.addWidget(self.btn_send_cmd, 1, 0, 1, 8)  # Botón ocupa toda la fila

        # === Lista de pending_requests ===
        requests_group = QGroupBox("📋 Peticiones pendientes")
        requests_layout = QVBoxLayout()

        self.requests_list = QListWidget()
        requests_layout.addWidget(self.requests_list)

        requests_group.setLayout(requests_layout)
        right_layout.addWidget(requests_group)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_requests_list)
        self.timer.start(1000)

        # ------------------ FILA 2: Logs ------------------
        logs_layout = QHBoxLayout()  # Divide en dos columnas

        # Mensajes salientes
        out_group = QGroupBox("💬 Registro de Mensajes Salientes")
        out_layout = QVBoxLayout()
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        out_layout.addWidget(self.output)
        out_group.setLayout(out_layout)
        logs_layout.addWidget(out_group)

        # Mensajes entrantes
        in_group = QGroupBox("💬 Registro de Mensajes Entrantes")
        in_layout = QVBoxLayout()
        self.input = QTextEdit()
        self.input.setReadOnly(True)
        in_layout.addWidget(self.input)
        in_group.setLayout(in_layout)
        logs_layout.addWidget(in_group)

        # Añadir la fila de logs al layout principal de la derecha
        right_layout.addLayout(logs_layout, 1)

        # ------------------ Agregar columnas al layout principal ------------------
        main_layout.addLayout(col1, 1)        # Columna 1: Movimiento/OLED/Comandos
        main_layout.addLayout(right_layout, 2)  # Columna 2+3 reorganizada

    # ===================== FUNCIONES =====================

    def update_requests_list(self):
        """Actualiza la lista con los elementos de self.pending_requests"""
        self.requests_list.clear()
        for dest, msg_ids in self.loranode.pending_requests.items():
            # Convertimos la lista de msg_id a una cadena separada por comas
            msg_str = ", ".join(str(mid) for mid in msg_ids)
            self.requests_list.addItem(f"{dest}: {msg_str}")

    def set_selected_type(self, msg_type, desc):
        """Cuando el usuario selecciona un tipo de mensaje"""
        self.selected_type = msg_type
        self.append_general_log(f"[{time.strftime('%H:%M:%S')}] Tipo seleccionado: {self.selected_type}")
        self.type_button.setText(f"{msg_type} (📖 {desc})")
        if int(self.selected_type) < 4 or int(self.selected_type) > 9 or int(self.selected_type) != 31:
            self.btn_send_cmd.setEnabled(False)
        else:
            self.btn_send_cmd.setEnabled(True)

    def keyPressEvent(self, event):
        """Actuador de eventos del movimiento de flechas."""
        key_map = {
            Qt.Key.Key_Up: "forward",
            Qt.Key.Key_Down: "backward",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right",
            Qt.Key.Key_Space: "stop",
        }
        direction = key_map.get(event.key())
        if direction:
            self.move_robot(direction)

    def move_robot(self, direction):
        commands = {
            "forward": {"T": 1, "L": 0.5, "R": 0.5},
            "backward": {"T": 1, "L": -0.5, "R": -0.5},
            "left": {"T": 1, "L": -0.3, "R": 0.3},
            "right": {"T": 1, "L": 0.3, "R": -0.3},
            "stop": {"T": 1, "L": 0, "R": 0},
        }
        cmd = commands.get(direction)
        self.set_selected_type(11, self.grups["Robot (10–19)"][11])
        if cmd:
            self.send_cmd(json.dumps(cmd))

    def send_oled(self):
        try:
            line = int(self.line_entry.text())
            text = self.text_entry.text()
            cmd = {"T": 3, "lineNum": line, "Text": text}
            self.set_selected_type(12, self.grups["Robot (10–19)"][12])
            self.send_cmd(json.dumps(cmd))
        except ValueError:
            QMessageBox.critical(self, "Error", "El número de línea debe ser 0–3.")

    def send_cmd(self, cmd:str =None):
        if cmd is False or type(cmd) is not str:
            cmd = ""
        dest = int(self.dest_entry.text())
        msg_type = int(self.selected_type)
        relay = int(self.relay_combo.currentText())
        self.msg_id += 1
        if msg_type == 5:
            alert = "PING"
        elif msg_type == 6:
            alert = "STATUS"
        elif msg_type == 7:
            alert = "REBOOT"
        elif msg_type == 8:
            alert = "RELAY_FLAG"
        elif 9 < msg_type < 20:
            alert = "ROBOT"
        elif 19 < msg_type < 25:
            alert = "SENSOR"
        elif 24 < msg_type < 31:
            alert = "CAMERA/RADAR"

        self.append_general_log(f"[{time.strftime('%H:%M:%S')}] Sending command to {dest}: {alert}")
        self.loranode.send_message(dest, msg_type, self.msg_id, cmd, relay)
        self._append_output(f"[{time.strftime('%H:%M:%S')}] 📡 Enviado: {msg_type} to {dest}")
    
    def take_photo(self):
        dest = int(self.dest_entry.text())
        msg_type = 30
        relay = int(self.relay_combo.currentText())
        self.msg_id += 1
        self.append_general_log(f"[{time.strftime('%H:%M:%S')}] 📸 Comando enviado para tomar foto")
        self.loranode.send_message(dest, msg_type, self.msg_id, "", relay)
        self._append_output(f"[{time.strftime('%H:%M:%S')}] 📡 Enviado: {msg_type}")

    def start_feedback(self):
        if self.feedback_running:
            QMessageBox.information(self, "Info", "Auto feedback ya está activo.")
            return
        self.feedback_running = True
        self.send_cmd(json.dumps({"T": 131, "cmd": 1}))
        self.set_selected_type(10, self.grups["Robot (10–19)"][10])
        self.feedback_thread = threading.Thread(target=self._feedback_loop, daemon=True)
        self.feedback_thread.start()
        self._append_output(f"[{time.strftime('%H:%M:%S')}] ✅ Auto feedback iniciado.\n")

    def stop_feedback(self):
        if not self.feedback_running:
            QMessageBox.information(self, "Info", "Auto feedback no está activo.")
            return
        self.feedback_running = False
        self.send_cmd(json.dumps({"T": 131, "cmd": 0}))
        self.set_selected_type(10, self.grups["Robot (10–19)"][10])
        self._append_output(f"[{time.strftime('%H:%M:%S')}] 🛑 Auto feedback detenido.\n")

    def _feedback_loop(self):
        ip = "192.168.4.1"
        while self.feedback_running:
            if ip:
                try:
                    url = f"http://{ip}/js?json={json.dumps({'T':130})}"
                    r = requests.get(url, timeout=3)
                    self._append_output(f"[{time.strftime('%H:%M:%S')}] [Feedback] {r.text.strip()}\n")
                except Exception as e:
                    self._append_output(f"[{time.strftime('%H:%M:%S')}] ⚠️ Error feedback: {e}\n")
            time.sleep(1)

    def _append_output(self, text):
        """Añade texto al panel de mensajes salientes"""
        self.output.append(text)
        self.output.ensureCursorVisible()

    def _append_input(self, text):
        """Añade texto al panel de mensajes entrantes"""
        self.input.append(text)
        self.input.ensureCursorVisible()
    
    def append_general_log(self, text):
        """Añade texto al panel de logs generales"""
        self.general_logs.append(text)
        self.general_logs.ensureCursorVisible()

    def _on_lora_message(self, msg: str):
        """Manejador de mensajes entrantes desde LoRaNode"""
        self._append_input(msg)

    def _on_general_log(self, msg: str):
        """Manejador de mensajes entrantes desde LoRaNode"""
        self.append_general_log(msg)


