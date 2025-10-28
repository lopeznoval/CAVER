import sys
import json
import threading
import time
import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QLineEdit, QComboBox, QMessageBox, QGridLayout, QGroupBox, QFrame, QTabWidget, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from LoRaNode_bis import LoRaNode


# ---------- CAMARA ----------
from PyQt6.QtGui import QPixmap
import base64


# ---------- CAMARA ----------


class EB_RobotGUI_bis(QWidget):

    message_received = pyqtSignal(str)

    def __init__(self, loranode: LoRaNode = None):
        super().__init__()
        self.loranode = loranode
        self.msg_id = 0
        self.feedback_running = False
        self.feedback_thread = None

        self.loranode.on_message = self._on_lora_message

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


        # ---------- CAMARA ----------
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
        # ---------- CAMARA ----------


        # ------------------ Añadir pestañas a la columna ------------------
        col1.addWidget(tabs)


        # === Layout principal para columnas 2 y 3 ===
        right_layout = QVBoxLayout()  # Contendrá la fila de comandos y la fila de logs

        # ------------------ FILA 1: Comandos LoRa ------------------
        lora_group = QGroupBox("📤 Comando LoRa")
        lora_layout = QGridLayout()

        lora_layout.addWidget(QLabel("Dest Node:"), 0, 0)
        self.dest_entry = QLineEdit("2")
        self.dest_entry.setFixedWidth(60)
        lora_layout.addWidget(self.dest_entry, 0, 1)

        lora_layout.addWidget(QLabel("Msg Type:"), 0, 2)
        self.type_combo = QComboBox()
        self.type_combo.addItems([str(i) for i in range(1, 31)])
        lora_layout.addWidget(self.type_combo, 0, 3)

        lora_layout.addWidget(QLabel("Relay Bit:"), 0, 4)
        self.relay_combo = QComboBox()
        self.relay_combo.addItems(["0", "1"])
        self.relay_combo.setCurrentText("1")
        lora_layout.addWidget(self.relay_combo, 0, 5)

        self.btn_send_cmd = QPushButton("Enviar Comando")
        self.btn_send_cmd.clicked.connect(self.send_cmd)
        #lora_layout.addWidget(self.btn_send_cmd, 1, 0, 1, 6)  # Botón ocupa toda la fila

        lora_group.setLayout(lora_layout)
        right_layout.addWidget(lora_group, 1)

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

    def keyPressEvent(self, event):
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
        if cmd:
            self.send_cmd(json.dumps(cmd))

    def send_oled(self):
        try:
            line = int(self.line_entry.text())
            text = self.text_entry.text()
            cmd = {"T": 3, "lineNum": line, "Text": text}
            self.send_cmd(json.dumps(cmd))
        except ValueError:
            QMessageBox.critical(self, "Error", "El número de línea debe ser 0–3.")

    def send_cmd(self, cmd=None):
        if cmd is None:
            cmd = "Null"
        dest = int(self.dest_entry.text())
        msg_type = int(self.type_combo.currentText())
        relay = int(self.relay_combo.currentText())
        self.msg_id += 1
        print("Sending command:", cmd)
        self.loranode.send_message(dest, msg_type, self.msg_id, cmd, relay)
        self._append_output(f"📡 Enviado: {cmd}")

    def start_feedback(self):
        if self.feedback_running:
            QMessageBox.information(self, "Info", "Auto feedback ya está activo.")
            return
        self.feedback_running = True
        self.send_cmd(json.dumps({"T": 131, "cmd": 1}))
        self.feedback_thread = threading.Thread(target=self._feedback_loop, daemon=True)
        self.feedback_thread.start()
        self._append_output("✅ Auto feedback iniciado.\n")

    def stop_feedback(self):
        if not self.feedback_running:
            QMessageBox.information(self, "Info", "Auto feedback no está activo.")
            return
        self.feedback_running = False
        self.send_cmd(json.dumps({"T": 131, "cmd": 0}))
        self._append_output("🛑 Auto feedback detenido.\n")

    def _feedback_loop(self):
        ip = "192.168.4.1"
        while self.feedback_running:
            if ip:
                try:
                    url = f"http://{ip}/js?json={json.dumps({'T':130})}"
                    r = requests.get(url, timeout=3)
                    self._append_output(f"[Feedback] {r.text.strip()}\n")
                except Exception as e:
                    self._append_output(f"⚠️ Error feedback: {e}\n")
            time.sleep(1)

    def _append_output(self, text):
        self.output.append(text)
        self.output.ensureCursorVisible()

    def _append_input(self, text):
        """Añade texto al panel de mensajes entrantes"""
        self.input.append(text)
        self.input.ensureCursorVisible()

    def _on_lora_message(self, msg: str):
        self._append_input(msg)

    # ---------- CAMERA ----------

        # Intentamos decodificar si es imagen
        try:
            data = json.loads(msg)
            if data.get("T") == 201 and "image" in data:  # T:201 indica foto
                img_data = base64.b64decode(data["image"])
                image = QImage.fromData(img_data)
                pixmap = QPixmap.fromImage(image)
                self.photo_label.setPixmap(pixmap.scaled(
                    self.photo_label.width(), self.photo_label.height(),
                    Qt.AspectRatioMode.KeepAspectRatio
                ))
                self._append_output("🖼️ Foto recibida y mostrada")
        except Exception:
            pass  # no es imagen, ignoramos

    # ---------- CAMERA ----------


    # ---------- CAMERA ----------
    def take_photo(self):
        # Envía un comando LoRa indicando a la Pi que tome una foto
        cmd = {"T": 200, "action": "capture_photo"}  # T:200 es un ejemplo para "foto"
        self.send_cmd(json.dumps(cmd))
        self._append_output("📸 Comando enviado para tomar foto")
    # ---------- CAMERA ----------
