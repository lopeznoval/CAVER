from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtCore import Qt, QSize


class StatusIndicator(QFrame):
    """Pequeño círculo rojo o verde para estado ON/OFF"""
    def __init__(self, color_off="#d9534f", color_on="#5cb85c", parent=None):
        super().__init__(parent)
        self.color_off = color_off
        self.color_on = color_on
        self.active = False
        self.setFixedSize(QSize(14, 14))

    def set_active(self, state: bool):
        self.active = state
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.color_on if self.active else self.color_off)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = min(self.width(), self.height()) / 2
        painter.drawEllipse(0, 0, self.width(), self.height())


class RobotStatusCard(QFrame):
    """Una tarjeta con información de un robot"""
    def __init__(self, robot_id, parent=None):
        super().__init__(parent)
        self.robot_id = robot_id

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-radius: 10px;
                padding: 10px;
                color: #f0f0f0;
            }
        """)

        layout = QVBoxLayout(self)
        title = QLabel(f"🤖 Robot {robot_id}")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #00aaff;")
        layout.addWidget(title)

        # Estados
        self.robot_status = StatusIndicator()
        self.radar_status = StatusIndicator()
        self.sensor_status = StatusIndicator()
        self.camera_status = StatusIndicator()

        self.add_status(layout, "Robot conectado", self.robot_status)
        self.add_status(layout, "Radar conectado", self.radar_status)
        self.add_status(layout, "Sensores conectados", self.sensor_status)
        self.add_status(layout, "Cámara conectada", self.camera_status)

        layout.addStretch()

    def add_status(self, layout, label_text, indicator):
        h = QHBoxLayout()
        h.addWidget(QLabel(label_text))
        h.addStretch()
        h.addWidget(indicator)
        layout.addLayout(h)

    def update_status(self, robot=False, radar=False, sensors=False, camera=False):
        self.robot_status.set_active(robot)
        self.radar_status.set_active(radar)
        self.sensor_status.set_active(sensors)
        self.camera_status.set_active(camera)


class RobotsPanel(QWidget):
    """Panel que muestra todos los robots conectados"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.robots = {}

    def add_or_update_robot(self, node_id, robot, radar, sensors, camera):
        if node_id not in self.robots:
            card = RobotStatusCard(node_id)
            self.layout.addWidget(card)
            self.robots[node_id] = card
        self.robots[node_id].update_status(robot, radar, sensors, camera)
