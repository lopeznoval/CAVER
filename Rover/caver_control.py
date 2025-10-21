import sys
import math
import json
import requests
import serial
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtGui import QPainter, QBrush
from PySide6.QtCore import Qt, QPointF, QTimer

class JoystickWidget(QWidget):
    def __init__(self, serial_port):
        super().__init__()
        self.setFixedSize(300, 300)
        self.center = QPointF(150, 150)
        self.stick_pos = QPointF(self.center)
        self.radius = 100

        if flag == 1:
            # Serial / USB
            self.ser = serial.Serial(serial_port, 115200)  # ajusta velocidad

        self.timer = QTimer()
        self.timer.timeout.connect(self.send_json_command)
        self.timer.start(50)  # cada 50 ms

    def paintEvent(self, event):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.setBrush(QBrush(Qt.lightGray))
        qp.drawEllipse(self.center, self.radius, self.radius)
        qp.setBrush(QBrush(Qt.blue))
        qp.drawEllipse(self.stick_pos, 15, 15)

    def mouseMoveEvent(self, event):
        delta = event.position() - self.center
        dist = math.hypot(delta.x(), delta.y())
        if dist > self.radius:
            # limitar al borde del círculo
            angle = math.atan2(delta.y(), delta.x())
            dist = self.radius
            x = self.center.x() + dist * math.cos(angle)
            y = self.center.y() + dist * math.sin(angle)
            self.stick_pos = QPointF(x, y)
        else:
            self.stick_pos = event.position()
        self.update()

    def mouseReleaseEvent(self, event):
        self.stick_pos = QPointF(self.center)
        self.update()

    def send_json_command(self):
        dx = self.stick_pos.x() - self.center.x()
        dy = self.center.y() - self.stick_pos.y()  # invertir Y
        # calcular velocidad y dirección
        dist = math.hypot(dx, dy)
        if dist < 5:
            # STOP: ruedas a cero
            left = 0
            right = 0
        else:
            # calcular ángulo y velocidad
            angle = math.atan2(dy, dx)  # en radianes
            # convertimos en una velocidad entre -100 y +100, por ejemplo
            speed = int((dist / self.radius) * 100)
            # cálculo diferencial (simplificado)
            # Aquí solo un esquema: ruedas = función de ángulo y speed
            left = speed * (math.cos(angle) + math.sin(angle))
            right = speed * (math.cos(angle) - math.sin(angle))
            # asegúrate de normalizar left, right al rango aceptado por UGV02

        # construir el JSON
        cmd = {
            "T": 1,
            "L": float(left/100),
            "R": float(right/100)
        }
        s = json.dumps(cmd)
        # enviar con terminador si hace falta, por ejemplo "\n"
        if flag == 1:
            self.ser.write((s + "\n").encode('utf-8'))
        else:
            url = "http://" + ip_addr + "/js?json=" + json.dumps(cmd)
            print(url)
            response = requests.get(url)
            content = response.text
            print(content)

class MainWindow(QWidget):
    def __init__(self, serial_port):
        super().__init__()
        layout = QVBoxLayout()
        self.joystick = JoystickWidget(serial_port)
        layout.addWidget(self.joystick)
        self.setLayout(layout)
        self.setWindowTitle("UGV02 Control por JSON")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    flag = 0                    # 1 para USB, 0 para HTTP
    port = "COM7"               # Cambia al puerto correcto
    ip_addr = "192.168.4.1"   # Cambia a la dirección IP correcta
    window = MainWindow(port)
    window.show()
    sys.exit(app.exec())
