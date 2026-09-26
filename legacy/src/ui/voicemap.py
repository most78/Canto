"""Mapa de tu voz: una casilla por semitono, coloreada según cuánto la aciertas."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from game.levels import note_name
from ui import theme
from ui.theme import color, font, px


def stat_color(entry):
    if not entry:
        return theme.SURFACE_2
    ema = entry['ema']
    return theme.GOLD if ema >= .8 else theme.GREEN if ema >= .6 else theme.ORANGE if ema >= .35 else '#c2566f'


class VoiceMap(QWidget):
    def __init__(self):
        super().__init__()
        self.progress = None
        self.highlight = set()       # notas de la última ronda
        self.setMinimumHeight(px(150))

    def set_progress(self, progress, highlight=()):
        self.progress = progress
        self.highlight = set(highlight)
        self.update()

    def paintEvent(self, event):
        if not self.progress or self.progress.anchor_midi is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        low, high = self.progress.range_midi()
        tested = [int(k) for k in self.progress.notes]
        first = min([low - 2] + tested)
        last = max([high + 2] + tested)
        count = last - first + 1
        w, h = self.width(), self.height()
        cell = min(px(64), (w - px(8)) / count)
        left = (w - cell * count) / 2
        top, box = px(26), px(56)
        p.setFont(font(15, QFont.Bold))
        p.setPen(color(theme.MUTED))
        p.drawText(QRectF(0, 0, w, px(22)), Qt.AlignLeft | Qt.AlignVCenter,
                   'Rango cómodo actual (marco dorado) · ▲ = tu nota base')
        for i, midi in enumerate(range(first, last + 1)):
            x = left + i * cell
            entry = self.progress.stat(midi)
            inside = low <= midi <= high
            rect = QRectF(x + px(3), top, cell - px(6), box)
            p.setPen(Qt.NoPen)
            fill = color(stat_color(entry), 255 if inside or entry else 90)
            p.setBrush(fill)
            p.drawRoundedRect(rect, px(10), px(10))
            if midi in self.highlight:
                p.setPen(QPen(color(theme.TEXT), px(3)))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(rect, px(10), px(10))
            if entry:
                p.setFont(font(15, QFont.Black))
                p.setPen(color(theme.INK))
                p.drawText(rect, Qt.AlignCenter, f'{round(entry["ema"] * 100)}')
            p.setFont(font(14 if cell < px(56) else 16, QFont.Bold))
            p.setPen(color(theme.TEXT if inside else theme.DIM))
            p.drawText(QRectF(x, top + box + px(4), cell, px(24)), Qt.AlignCenter, note_name(midi))
            if midi == self.progress.anchor_midi:
                p.setPen(color(theme.PINK))
                p.drawText(QRectF(x, top + box + px(26), cell, px(22)), Qt.AlignCenter, '▲')
        # Marco del rango actual.
        x0 = left + (low - first) * cell
        x1 = left + (high - first + 1) * cell
        p.setPen(QPen(color(theme.GOLD), px(3)))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(x0, top - px(5), x1 - x0, box + px(10)), px(14), px(14))
        p.end()
