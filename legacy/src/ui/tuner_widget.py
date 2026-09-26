import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from audio.pitch import hz_to_note


class PitchGauge(QWidget):
    def __init__(self):
        super().__init__()
        self.cents = None
        self.setMinimumHeight(46)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        left, width, y = 15, self.width() - 30, 22
        painter.setPen(QPen(QColor('#385057'), 6))
        painter.drawLine(left, y, left + width, y)
        center = left + width / 2
        painter.fillRect(int(center - width * .075), 10, int(width * .15), 24, QColor('#315b4d'))
        painter.setPen(QPen(QColor('#8bd8bc'), 2))
        painter.drawLine(int(center), 6, int(center), 38)
        if self.cents is not None:
            x = left + width * (max(-100, min(100, self.cents)) + 100) / 200
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor('#77e2b1' if abs(self.cents) <= 15 else '#f0bc76'))
            painter.drawEllipse(int(x) - 7, y - 7, 14, 14)


class TunerWidget(QWidget):
    reference_requested = Signal(float)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel('TU VOZ · PRACTICA UNA NOTA')
        title.setObjectName('eyebrow')
        layout.addWidget(title)
        row = QHBoxLayout()
        row.addWidget(QLabel('Nota objetivo'))
        self.target = QComboBox()
        self.target.addItem('Libre · nota más cercana', None)
        for midi in range(45, 82):
            frequency = 440 * 2 ** ((midi - 69) / 12)
            self.target.addItem(hz_to_note(frequency).label, frequency)
        self.target.setCurrentIndex(16)
        self.target.currentIndexChanged.connect(self.reset_target)
        row.addWidget(self.target, 1)
        self.listen = QPushButton('Escuchar nota')
        self.listen.clicked.connect(lambda: self.reference_requested.emit(self.target.currentData()))
        row.addWidget(self.listen)
        layout.addLayout(row)
        self.note = QLabel('—')
        self.note.setObjectName('note')
        self.note.setAlignment(Qt.AlignCenter)
        self.feedback = QLabel('Escucha la nota y después imítala con una «a»')
        self.feedback.setAlignment(Qt.AlignCenter)
        self.feedback.setStyleSheet('font-size: 20px; font-weight: 600;')
        self.detail = QLabel('Activa el micrófono para empezar')
        self.detail.setAlignment(Qt.AlignCenter)
        self.meter = PitchGauge()
        legend = QLabel('Más grave ←                    Objetivo                    → Más aguda')
        legend.setAlignment(Qt.AlignCenter)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setFormat('Volumen del micro (no afinación) · %p%')
        for widget in (self.note, self.feedback, self.detail, self.meter, legend, self.level):
            layout.addWidget(widget)

    def reset_target(self):
        self.listen.setEnabled(self.target.currentData() is not None)
        self.update_reading(None)

    def update_reading(self, frequency, volume=0):
        self.level.setValue(min(100, round(volume * 300)))
        if frequency is None:
            self.note.setText('—')
            self.note.setStyleSheet('color: #94aaa9')
            self.feedback.setText('Canta una «a» sostenida')
            self.detail.setText('Entra sonido, pero no hay una nota clara' if volume >= .01 else 'No llega suficiente voz · acércate al micrófono')
            self.meter.cents = None
            self.meter.update()
            return
        reading = hz_to_note(frequency)
        target = self.target.currentData()
        cents = 1200 * math.log2(frequency / target) if target else reading.cents
        self.note.setText(reading.label)
        if abs(cents) <= 15:
            message = 'En la nota · mantén la voz'
        else:
            message = 'Sube la voz · canta más agudo' if cents < 0 else 'Baja la voz · canta más grave'
        self.feedback.setText(message)
        reference = f'Objetivo: {self.target.currentText()}' if target else 'Referencia: nota más cercana (modo libre)'
        self.detail.setText(f'{reference}  ·  {cents:+.0f} cents  ·  100 cents = 1 semitono')
        self.meter.cents = cents
        self.meter.update()
        color = '#77e2b1' if abs(cents) <= 15 else '#f0bc76'
        self.note.setStyleSheet(f'color: {color}')
