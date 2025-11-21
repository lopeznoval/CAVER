import json, threading, time, requests
import sys
import json
import threading
import time
import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu, QSlider,
    QTextEdit, QLineEdit, QComboBox, QMessageBox, QGridLayout, QGroupBox, QFrame, QTabWidget, 
    QSizePolicy, QListWidget, QCheckBox, QRadioButton, QButtonGroup, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QPainter, QColor, QFont

from GUI.aux_GUI import StatusIndicator, RobotStatusCard, RobotsPanel
from NodoLoRa.LoRaNode_bis import LoRaNode




class EB_RobotGUI_bis(QWidget):

    message_received = pyqtSignal(str)

    def __init__(self, loranode: LoRaNode = None):
        super().__init__()
        self.loranode = loranode
        self.msg_id = 1
        self.feedback_running = False
        self.feedback_thread = None

        
        if loranode is not None:
            self.loranode.on_message = self._on_lora_message
            self.loranode.on_alert = self._on_general_log
            self.loranode.on_position = self._on_refresh_position
            self.loranode.on_sensor = self._on_sensor_data


# -------------------- IMU inicio --------------------

        self.origin_set = False                 # Se indica si se ha tomado ref. inicial de posición
        self.origin = {"x":0, "y":0, "z":0}     # posición de referencia inicial
        self.position = {"x":0, "y":0, "z":0}   # posición actual estimada
        self.vx, self.vy, self.vz = 0,0,0       # velocidades actuales del robot en cada eje (x, y, z)
        self.last_imu = None                    # Guarda la última lectura recibida de la IMU
        self.imu_active = False                 # flag que indica si empezó la localización
        self._path_points = {"x": [0.0], "y": [0.0]}

# -------------------- IMU final --------------------


        if loranode is None:
            self.setWindowTitle("UGV02 Robot Control Dashboard: LoRaNode not initialized")
        else:
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
        tabs.addTab(tab_move, "🕹️")

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
        tabs.addTab(tab_oled, "🖥️")

        # ------------------ TAB 3: Comandos ------------------
        tab_cmd = QWidget()
        cmd_layout = QGridLayout()

        self.btn_imu = QPushButton("IMU Data")
        self.btn_feedback = QPushButton("Chassis Feedback")
        self.btn_imu.clicked.connect(lambda: (self.send_cmd(json.dumps({"T": 126})), self.set_selected_type(10, self.grups["Robot (10–19)"][10])))
        self.btn_feedback.clicked.connect(lambda: (self.send_cmd(json.dumps({"T": 130})), self.set_selected_type(10, self.grups["Robot (10–19)"][10])))

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
        tabs.addTab(tab_cmd, "⚙️")

        # ----------------------- TAB 4: Imagen -----------------------
        tab_video = QWidget()
        video_layout = QVBoxLayout()

        self.btn_take_photo = QPushButton("Capturar foto 📸")
        self.btn_take_photo.clicked.connect(self.take_photo)
        video_layout.addWidget(self.btn_take_photo)

        # Placeholder para la imagen recibida
        self.photo_label = QLabel("Aquí se mostrará la foto")
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setFixedSize(400, 300)
        video_layout.addWidget(self.photo_label)

        tab_video.setLayout(video_layout)
        tabs.addTab(tab_video, "📹")
    
        # ------------------ TAB 5: Posición ------------------
        tab_position = QWidget()
        pos_layout = QVBoxLayout()
        buttons_imu_layout = QHBoxLayout()

        # Checkbox para enviar posición por LoRa
        self.send_position_checkbox = QCheckBox("📡 Enviar posición al EB")
        self.send_position_checkbox.setChecked(True)
        pos_layout.addWidget(self.send_position_checkbox)

        self.btn_start_imu = QPushButton("▶️ Comenzar a trazar posición")
        self.btn_start_imu.clicked.connect(self._start_imu)
        buttons_imu_layout.addWidget(self.btn_start_imu)
        self.btn_stop_imu = QPushButton("⏹️ Parar trazado de posición")
        self.btn_stop_imu.clicked.connect(self._stop_imu)
        buttons_imu_layout.addWidget(self.btn_stop_imu)
        pos_layout.addLayout(buttons_imu_layout)


        # Botón para resetear posición
        self.btn_reset_position = QPushButton("🔄 Reset posición")
        self.btn_reset_position.clicked.connect(self.reset_position)
        pos_layout.addWidget(self.btn_reset_position)

        # --- Plot de trayectoria (usando pyqtgraph) ---
        import pyqtgraph as pg
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle("Trayectoria estimada del robot", color='b', size='12pt')
        self.plot_widget.setLabel('left', 'Z (m)')
        self.plot_widget.setLabel('bottom', 'X (m)')
        self.plot_widget.showGrid(x=True, y=True)

        self.path_curve = self.plot_widget.plot([], [], pen=pg.mkPen(color='r', width=2))

        pos_layout.addWidget(self.plot_widget)

        tab_position.setLayout(pos_layout)
        tabs.addTab(tab_position, "📍")

        # Timer para actualizar el gráfico cada 100 ms
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_position_plot)
        self.plot_timer.start(100)
        
        # ----------------------- TAB 6: Tomar datos de los sensores -----------------------
        tab_sensors = QWidget()
        sensors_layout = QVBoxLayout()
        
        self.btn_take_data = QPushButton("Medir temperatura y humedad 🌡️💧")
        self.btn_take_data.clicked.connect(self.take_data)
        sensors_layout.addWidget(self.btn_take_data)
        # Recuadro para mostrar la temperatura
        self.temp_label = QLabel("Temperatura en °C")
        self.temp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temp_label.setFixedSize(200, 50)
        self.temp_label.setStyleSheet("background-color: gray; border-radius: 8px;")
        sensors_layout.addWidget(self.temp_label)

        # Recuadro para mostrar la humedad
        self.hum_label = QLabel("Humedad en %")
        self.hum_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hum_label.setFixedSize(200, 50)
        self.hum_label.setStyleSheet("background-color: gray; border-radius: 8px;")
        sensors_layout.addWidget(self.hum_label)
        
        # Encender/Apagar/Modo automático del led
        self.luz_groupbox = QGroupBox("Control del LED")
        self.luz_groupbox.setFixedSize(250, 120)
        self.luz_groupbox.setStyleSheet("""
            QGroupBox {
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: 2px solid gray;
                border-radius: 8px;
                margin-top: 5px;
            }
        """)
        luz_layout = QVBoxLayout()
        # Estilo común para los botones de control del LED
        led_button_style = """
            QRadioButton {
                color: white;
                font-size: 14px;
            }
            QRadioButton::indicator {
                border: 2px solid #a35709; 
                height: 16px;
                width: 16px;
                border-radius: 10px;
            }
            QRadioButton::indicator:checked {
                background: qradialgradient(
                    cx:.5, cy:.5, radius: .7,
                    fx:.5, fy:.5,
                    stop:0 '#ff8303', 
                    stop:0.45 '#ff8303',
                    stop:0.5 transparent,
                    stop:1 transparent
                );
            }
        """
        #Boton para enceder el led
        self.btn_encender_led = QRadioButton("Encender LED 💡")
        self.btn_encender_led.setStyleSheet(led_button_style)
        luz_layout.addWidget(self.btn_encender_led)
        
        # Boton para apagar el led
        self.btn_apagar_led = QRadioButton("Apagar LED 💡")
        self.btn_apagar_led.setStyleSheet(led_button_style)
        luz_layout.addWidget(self.btn_apagar_led)
        
        # Boton para poner el modo automático el led
        self.btn_modoauto_led = QRadioButton("LED Modo Automático 💡")
        self.btn_modoauto_led.setStyleSheet(led_button_style)
        luz_layout.addWidget(self.btn_modoauto_led)
        
        self.LED_group = QButtonGroup(self)
        self.LED_group.addButton(self.btn_encender_led)
        self.LED_group.addButton(self.btn_apagar_led)
        self.LED_group.addButton(self.btn_modoauto_led)
        self.LED_group.buttonClicked.connect(self.control_led)

        self.luz_groupbox.setLayout(luz_layout)
        sensors_layout.addWidget(self.luz_groupbox) 

        # Aplicar el layout a la pestaña
        tab_sensors.setLayout(sensors_layout)

        # Añadir la pestaña al conjunto de tabs
        tabs.addTab(tab_sensors, "🌡️💡")

        # ----------------------- TAB 7: Logs generales -----------------------
        tab_logs = QWidget()
        logs_layout = QVBoxLayout()

        # QTextEdit para mostrar todos los logs del nodo
        self.general_logs = QTextEdit()
        self.general_logs.setReadOnly(True)
        self.general_logs.setPlaceholderText("Aquí se mostrará todo lo que sucede en el nodo...")

        logs_layout.addWidget(self.general_logs)
        tab_logs.setLayout(logs_layout)

        # Añadir el tab al QTabWidget
        tabs.addTab(tab_logs, "📝")

        # ------------------ TAB 8: Movimiento automático ------------------
        tab_radar = QWidget()
        buttons_mov_auto_layout = QHBoxLayout()

        self.btn_start_mov_aut = QPushButton("▶️ Comenzar movimiento automático")
        self.btn_start_mov_aut.clicked.connect(self._start_mov_auto)
        buttons_mov_auto_layout.addWidget(self.btn_start_mov_aut)
        self.btn_stop_mov_aut = QPushButton("⏹️ Parar movimiento autónomo")
        self.btn_stop_mov_aut.clicked.connect(self._stop_mov_auto)
        buttons_mov_auto_layout.addWidget(self.btn_stop_mov_aut)

        tab_radar.setLayout(buttons_mov_auto_layout)
        tabs.addTab(tab_radar, "Radar")


        # ------------------ Añadir pestañas a la columna ------------------
        col1.addWidget(tabs)


        # === Layout principal para columnas 2 y 3 ===
        right_layout = QVBoxLayout()  

        # ------------------ FILA 1: Comandos LoRa & Lista de Reports ------------------
        # === Comandos LoRa ===
        tabs_config = QTabWidget()
        lora_widget = QWidget()
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
                13: "IMU",
                14: "Movimiento autónomo",
                15: "",
                19: ""
            },
            "Sensores (20–24)": {
                20: "Encender led",
                21: "Lectura actual de temperatura y humedad",
                22: "Sincronizar sensores",
                23: "Apagar led",
                24: "Luz en modo automático"
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
        # right_layout.addWidget(lora_group, 1)
                
        self.btn_send_cmd = QPushButton("Enviar Comando")
        self.btn_send_cmd.clicked.connect(self.send_cmd)
        lora_layout.addWidget(self.btn_send_cmd, 1, 0, 1, 8)  # Botón ocupa toda la fila

        lora_widget.setLayout(lora_layout)
        tabs_config.addTab(lora_widget, "Configuración LoRa")

        # === Lista de pending_requests ===
        requests_group = QGroupBox("📋")
        requests_layout = QVBoxLayout()

        self.requests_list = QListWidget()
        requests_layout.addWidget(self.requests_list)

        requests_group.setLayout(requests_layout)
        tabs_config.addTab(requests_group, "Peticiones Pendientes")
        
        if loranode is not None:
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_requests_list)
            self.timer.start(500)

        # === Nodos Conectados ===
        self.panel = RobotsPanel()

        if self.loranode is not None:
            self.timer2 = QTimer()
            self.timer2.timeout.connect(self.refresh_connected_robots)
            self.timer2.start(5000)

        tabs_config.addTab(self.panel, "Nodos Conectados")



        right_layout.addWidget(tabs_config)
        
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
        """Actualiza la lista con estilo para cada request"""
        self.requests_list.clear()

        for dest, msg_ids in sorted(self.loranode.pending_requests.items()):
            msg_str = ", ".join(str(mid) for mid in sorted(msg_ids))
            text = f"Destino {dest}: {msg_str}"
            
            item = QListWidgetItem(text)
            
            # Fuente en negrita
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            
            # Color de fondo alterno según el destino
            if dest % 2 == 0:
                item.setBackground(QColor("#2e2e2e"))
                item.setForeground(QColor("#00ff00"))
            else:
                item.setBackground(QColor("#1e1e1e"))
                item.setForeground(QColor("#ffaa00"))

            self.requests_list.addItem(item)

    def set_selected_type(self, msg_type, desc):
        """Cuando el usuario selecciona un tipo de mensaje"""
        self.selected_type = msg_type
        self.append_general_log(f"[{time.strftime('%H:%M:%S')}] Tipo seleccionado: {self.selected_type}")
        self.type_button.setText(f"{msg_type} (📖 {desc})")
        if (int(self.selected_type) < 4 or int(self.selected_type) > 9) and int(self.selected_type) != 31:
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
        else:
            alert = "GENERAL"

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
        
    def take_data(self):
        # Envia una orden al nodo para obtener la temperatura y humedad
        dest = int(self.dest_entry.text())
        msg_type = 21
        relay = int(self.relay_combo.currentText())
        self.msg_id += 1
        # Comandos de solicitud
        self.append_general_log(f"[{time.strftime('%H:%M:%S')}] 🌡️ Solicitando datos de temperatura y humedad...")
        #Solicita los datos
        self.loranode.send_message(dest, msg_type, self.msg_id, " ", relay)
        self._append_output(f"[{time.strftime('%H:%M:%S')}] 📡 Enviado: Solicitud de información ambiental")

    def control_led(self, button):
        # Envia una orden al nodo para controlar el LED
        dest = int(self.dest_entry.text())
        relay = int(self.relay_combo.currentText())
        self.msg_id += 1
        if button == self.btn_encender_led:
            msg_type = 20  # Encender LED
            orden = "ON"
        elif button == self.btn_apagar_led:
            msg_type = 23  # Apagar LED
            orden = "OFF"
        elif button == self.btn_modoauto_led:
            msg_type = 24  # Modo automático LED
            orden = "AUTO"
        self.append_general_log(f"[{time.strftime('%H:%M:%S')}] Sending command to {dest}: {orden}")
        self.loranode.send_message(dest, msg_type, self.msg_id, " ", relay)
        self._append_output(f"[{time.strftime('%H:%M:%S')}] 📡 Enviado: {msg_type} to {dest}")

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

    def _start_imu(self):
        """Envía al robot la orden de comenzar a enviar datos IMU periódicamente."""
        print("""Envía al robot la orden de comenzar a enviar datos IMU periódicamente.""")
        self.imu_active = True
        self.selected_type = 13
        self.append_general_log("🛰️ Enviando comando: Comenzar IMU")
        self.send_cmd("1")

    def _stop_imu(self):
        """Envía al robot la orden de detener el envío de datos IMU."""        
        self.imu_active = False
        self.selected_type = 13  
        self.append_general_log("🛰️ Enviando comando: Detener IMU")
        self.send_cmd("0")

    def _start_mov_auto(self):
        """Envía al robot la orden de comenzar el movimiento autónomo."""
        self.set_selected_type(14, self.grups["Robot (10–19)"][14])
        self.append_general_log("🛰️ Enviando comando: Comenzar  movimiento autónomo")
        self.send_cmd("1")

    def _stop_mov_auto(self):
        """Envía al robot la orden de detener el movimiento autónomo."""        
        self.set_selected_type(14, self.grups["Robot (10–19)"][14])
        self.append_general_log("🛰️ Enviando comando: Detener movimiento autónomo")
        self.send_cmd("0")

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
                
    # -------------------- IMU inicio --------------------
    def _on_refresh_position (self, pos):
        try:
            x = pos.get("x", 0)
            y = pos.get("y", 0)
            z = pos.get("z", 0)

            # Establecer origen si aún no lo hay
            if self.imu_active and not self.origin_set:
                self.origin_set = True
                self.origin = {"x": 0, "y": 0, "z": 0}
                self.append_general_log("📍 Origen de posición IMU establecido")
                    
            # Actualizar posición relativa al origen
            if self.origin_set:
                self.position = {
                    "x": x - self.origin["x"],
                    "y": y - self.origin["y"],
                    "z": z - self.origin["z"]
                }

        except Exception as e:
            self.append_general_log(f"Error parseando IMU: {e}")
        
# -------------------- IMU final --------------------

    def _on_general_log(self, msg: str):
        """Manejador de mensajes entrantes desde LoRaNode"""
        self.append_general_log(msg)



    def update_position_plot(self):
        """Actualiza el gráfico de trayectoria en tiempo real."""
        x = self.position["x"]
        y = self.position["z"]  # proyección XZ
        self._path_points["x"].append(x)
        self._path_points["y"].append(y)    

        self.path_curve.setData(self._path_points["x"], self._path_points["y"])

    def reset_position(self):
        """Resetea posición y limpia el gráfico."""
        self.origin_set = False
        self.position = {"x": 0, "y": 0, "z": 0}
        self.vx, self.vy, self.vz = 0, 0, 0
        self._path_points = {"x": [0], "y": [0]}
        self.path_curve.clear()
        self.append_general_log("📍 Posición y trayectoria reseteadas.")

# -------------------- IMU final --------------------

# -------------------- Sensores ----------------------

    def _on_sensor_data(self, on_sensor_data):
        try:
            # Si llega como string JSON, decodificamos
            if isinstance(on_sensor_data, str):
                data = json.loads(on_sensor_data)
            else:
                data = on_sensor_data

            # Extraer datos (en español)
            temperatura = float(data.get("Temperatura", 0))
            humedad = float(data.get("Humedad", 0))
            timestamp = data.get("timestamp", "")

            # Mostrar en logs
            self.append_general_log(
                f"[{time.strftime('%H:%M:%S')}] 🌡️ Datos recibidos → Temp: {temperatura:.1f}°C, Hum: {humedad:.1f}% ({timestamp})"
            )

            # Actualizar etiquetas en la GUI
            self.temp_label.setText(f"Temperatura: {temperatura:.1f} °C")
            self.hum_label.setText(f"Humedad: {humedad:.1f} %")

            # --- Color según temperatura ---
            if temperatura < 15:
                color_temp = "lightblue"
            elif temperatura <= 25:
                color_temp = "lightgreen"
            else:
                color_temp = "lightcoral"  # rojo claro

            self.temp_label.setStyleSheet(
                f"background-color: {color_temp}; border-radius: 8px; font-weight: bold;"
            )

            # --- Color según humedad ---
            if humedad < 30:
                color_hum = "khaki"  # amarillento
            elif humedad <= 60:
                color_hum = "lightgreen"
            else:
                color_hum = "lightblue"

            self.hum_label.setStyleSheet(
                f"background-color: {color_hum}; border-radius: 8px; font-weight: bold;"
            )

        except Exception as e:
            self.append_general_log(f"[{time.strftime('%H:%M:%S')}] ⚠️ Error procesando datos del sensor: {e}")


# -------------------- Estados de Nodos Conectados ----------------------
    # def add_status(self, layout, label_text, indicator):
    #     h = QHBoxLayout()
    #     h.addWidget(QLabel(label_text))
    #     h.addStretch()
    #     h.addWidget(indicator)
    #     layout.addLayout(h)

    # def update_status(self, connected=False, radar=False, sensors=False):
    #     self.robot_status.set_active(connected)
    #     self.radar_status.set_active(radar)
    #     self.sensor_status.set_active(sensors)

    # def add_or_update_robot(self, robot_id, connected, radar, sensors):
    #     if robot_id not in self.robots:
    #         card = RobotStatusCard(robot_id)
    #         self.layout.addWidget(card)
    #         self.robots[robot_id] = card
    #     self.robots[robot_id].update_status(connected, radar, sensors)

    def refresh_connected_robots(self):
        with self.loranode.lock_nodes:
            node_data = {
                node_id: (
                    info["robot"],
                    info["radar"],
                    info["sensors"],
                    info["camera"]
                )
                for node_id, info in self.loranode.connected_nodes.items()
            }
            
        self.panel.sync_with_nodes(node_data)


