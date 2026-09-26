"""Panda mascota: sólo decoración. No reacciona a la voz ni a la puntuación en vivo."""
import math

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ui import theme


def draw_panda(p, cx, cy, size, phase=0.0, waving=False):
    """Dibuja un panda de ~`size` px de alto centrado en (cx, cy)."""
    p.save()
    p.translate(cx, cy + math.sin(phase * 1.4) * size * .01)
    k = size / 150
    p.scale(k, k)
    p.rotate(math.sin(phase * .9) * 2)

    def oval(x, y, w, h, c):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(c))
        p.drawEllipse(QRectF(x, y, w, h))

    dark, fur = '#1b1730', '#fbf8f0'
    oval(-48, 2, 96, 72, dark)
    oval(-32, 12, 64, 54, fur)
    oval(-52, 50, 34, 24, dark)
    oval(18, 50, 34, 24, dark)
    oval(-56, -62, 36, 36, dark)
    oval(20, -62, 36, 36, dark)
    oval(-54, -52, 108, 90, fur)
    oval(-36, -24, 28, 32, dark)
    oval(8, -24, 28, 32, dark)
    if phase % 4.8 > 4.62:
        p.setPen(QPen(QColor(fur), 3))
        p.drawLine(-27, -7, -16, -7)
        p.drawLine(16, -7, 27, -7)
    else:
        oval(-26, -14, 11, 13, '#ffffff')
        oval(15, -14, 11, 13, '#ffffff')
        oval(-22, -10, 6, 8, dark)
        oval(17, -10, 6, 8, dark)
    oval(-8, 6, 16, 10, dark)
    p.setPen(QPen(QColor(dark), 3))
    p.drawArc(QRectF(-9, 11, 18, 13), 200 * 16, 140 * 16)
    oval(-44, 8, 15, 8, '#ff9ec4')
    oval(29, 8, 15, 8, '#ff9ec4')
    p.save()
    p.translate(42, 20)
    if waving:
        p.rotate(-70 + math.sin(phase * 6) * 20)
    oval(-9, -8, 24, 40, dark)
    p.restore()
    oval(-58, 16, 26, 38, dark)
    p.restore()


class PandaBadge(QWidget):
    """Panda pequeño animado para cabecera y pantalla de resultados."""

    def __init__(self, size=64, waving=False):
        super().__init__()
        self.size = size
        self.waving = waving
        self.phase = 0.0
        self.setFixedSize(theme.px(size * 1.25), theme.px(size * 1.15))
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.tick)

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def tick(self):
        self.phase += .04
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        draw_panda(p, self.width() / 2, self.height() / 2 + theme.px(self.size) * .05,
                   theme.px(self.size), self.phase, self.waving)
