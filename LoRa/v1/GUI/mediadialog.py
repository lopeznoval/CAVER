from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QDialog
)
from PyQt6.QtGui import QIntValidator

class MediaDialog(QDialog):
    def __init__(self, is_video=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración")

        layout = QVBoxLayout()

        # --- Duración solo si es video ---
        if is_video:
            self.duration_input = QLineEdit()
            self.duration_input.setPlaceholderText("Duración (segundos)")
            self.duration_input.setValidator(QIntValidator())
            layout.addWidget(QLabel("Duración del video (segundos):"))
            layout.addWidget(self.duration_input)
        else:
            self.duration_input = None  # No se usa

        # --- Calidad ---
        layout.addWidget(QLabel("Calidad:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Baja", "Media", "Alta"])
        layout.addWidget(self.quality_combo)

        # --- Botones ---
        btns = QHBoxLayout()
        btn_ok = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)

        layout.addLayout(btns)
        self.setLayout(layout)

    def get_values(self):
        duration = int(self.duration_input.text()) if self.duration_input else None
        quality = self.quality_combo.currentText()
        return duration, quality
