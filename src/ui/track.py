"""Pista de voz: las notas avanzan de derecha a izquierda hacia la línea «AHORA».

Eje vertical = altura (arriba agudo, abajo grave), relativo a tu nota fija.
Eje horizontal = tiempo. La bola en la línea es tu voz; la estela, lo que acabas
de cantar. Esta vista sólo LEE el estado de `NoteRun`: animar no puntúa.
"""
import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from game.note_run import HITS, JUDGEMENT_TEXT, CUE_LENGTH
from ui import theme
from ui.theme import color, font, px

RANGE = 700          # cents visibles por encima y por debajo de tu nota
LOOKAHEAD = 5.5      # segundos visibles por delante de la línea
HIT_FRACTION = .26   # posición de la línea «AHORA» dentro del carril

KIND_COLOR = {'hit': theme.GREEN, 'low': theme.CYAN, 'high': theme.ORANGE}


class TrackView(QWidget):
    def __init__(self, clock=time.monotonic):
        super().__init__()
        self.clock = clock
        self.run = None
        self.target_label = ''
        self.display_cents = None
        self.popups = []
        self.particles = []
        self.last_tick = None
        self.setMinimumHeight(px(420))
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)

    def set_run(self, run, target_label):
        self.run = run
        self.target_label = target_label
        self.display_cents = None
        self.popups.clear()
        self.particles.clear()
        self.update()

    def add_judgement(self, index, judgement):
        self.popups.append((index, judgement, self.clock()))

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    # --- animación (independiente de la puntuación) ---------------------
    def tick(self):
        now = self.clock()
        dt = min(.1, now - self.last_tick) if self.last_tick else .016
        self.last_tick = now
        reading = self.run.current_reading(now) if self.run else None
        if reading is not None and reading.cents is not None:
            target = max(-RANGE, min(RANGE, reading.cents))
            if self.display_cents is None:
                self.display_cents = target
            self.display_cents += (target - self.display_cents) * min(1, dt * 16)
            if reading.kind == 'hit' and self.run.active_note(now) is not None:
                g = self.geometry_info()
                for _ in range(2):
                    self.particles.append([g['hitx'], self.y_of(g, self.display_cents),
                                           random.uniform(-260, -80), random.uniform(-160, 160), 0.0])
        for part in self.particles:
            part[0] += part[2] * dt * theme.px(1)
            part[1] += part[3] * dt * theme.px(1)
            part[4] += dt
        self.particles = [q for q in self.particles if q[4] < .6]
        self.popups = [q for q in self.popups if now - q[2] < 1.6]
        self.update()

    # --- geometría ------------------------------------------------------
    def geometry_info(self):
        w, h = self.width(), self.height()
        hud = px(78)
        ax = px(190)
        top, bottom = hud + px(8), h - px(40)
        hitx = ax + (w - ax) * HIT_FRACTION
        return {
            'w': w, 'h': h, 'hud': hud, 'ax': ax, 'top': top, 'bottom': bottom,
            'cy': (top + bottom) / 2, 'cpp': (bottom - top) / (2 * RANGE + 120),
            'hitx': hitx, 'pps': (w - hitx) / LOOKAHEAD,
        }

    @staticmethod
    def y_of(g, cents):
        return g['cy'] - max(-RANGE - 40, min(RANGE + 40, cents)) * g['cpp']

    @staticmethod
    def x_of(g, song_time, t):
        return g['hitx'] + (song_time - t) * g['pps']

    # --- dibujo ---------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = self.geometry_info()
        bg = QLinearGradient(0, 0, 0, g['h'])
        bg.setColorAt(0, color('#221a4d'))
        bg.setColorAt(1, color('#0e0a22'))
        p.fillRect(self.rect(), bg)
        if self.run is None:
            return
        now = self.clock()
        t = self.run.time(now)
        tol = self.run.tolerance
        self.draw_lane(p, g, tol)
        self.draw_rests(p, g, t)
        self.draw_notes(p, g, t, tol)
        self.draw_trail(p, g, t)
        self.draw_hit_line(p, g, now)
        self.draw_voice(p, g, now)
        self.draw_axis(p, g, tol)
        self.draw_hud(p, g, now)
        self.draw_countdown(p, g, t)
        self.draw_popups(p, g, now, tol)
        if self.run.state == 'paused':
            p.fillRect(self.rect(), color(theme.BG_DEEP, 190))
            p.setPen(color(theme.TEXT))
            p.setFont(font(64, QFont.Black))
            p.drawText(QRectF(0, g['cy'] - px(90), g['w'], px(90)), Qt.AlignCenter, 'En pausa')
            p.setFont(font(28))
            p.setPen(color(theme.MUTED))
            p.drawText(QRectF(0, g['cy'] + px(10), g['w'], px(60)), Qt.AlignCenter,
                       'Pulsa «Seguir» o la barra espaciadora. El tiempo está detenido.')

    def draw_lane(self, p, g, tol):
        ax, w, top, bottom = g['ax'], g['w'], g['top'], g['bottom']
        # Mitad superior cálida (agudo), inferior fría (grave).
        p.fillRect(QRectF(ax, top, w - ax, g['cy'] - top), color(theme.ORANGE, 12))
        p.fillRect(QRectF(ax, g['cy'], w - ax, bottom - g['cy']), color(theme.CYAN, 12))
        for k in range(-7, 8):
            if k == 0:
                continue
            y = self.y_of(g, k * 100)
            p.setPen(QPen(color(theme.TEXT, 34 if k % 2 == 0 else 18), px(1)))
            p.drawLine(QPointF(ax, y), QPointF(w, y))
        band = QRectF(ax, self.y_of(g, tol), w - ax, self.y_of(g, -tol) - self.y_of(g, tol))
        p.fillRect(band, color(theme.VIOLET, 46))
        p.setPen(QPen(color(theme.VIOLET, 150), px(2), Qt.DashLine))
        p.drawLine(QPointF(ax, g['cy']), QPointF(w, g['cy']))

    def draw_rests(self, p, g, t):
        notes = self.run.notes
        p.setFont(font(22, QFont.DemiBold))
        for a, b in zip(notes, notes[1:]):
            mid = (a.end + b.start) / 2
            x = self.x_of(g, mid, t)
            if g['ax'] + px(60) < x < g['w'] - px(60):
                breathe = .5 + .5 * math.sin(self.clock() * 2.2)
                y = g['cy'] + px(70)
                p.setPen(color(theme.MUTED, 170))
                p.drawText(QRectF(x - px(90), y, px(180), px(36)), Qt.AlignCenter, 'respira')
                p.setPen(Qt.NoPen)
                p.setBrush(color(theme.CYAN, 60 + int(60 * breathe)))
                r = px(10) + px(8) * breathe
                p.drawEllipse(QPointF(x, g['cy'] + px(48)), r, r)

    def draw_notes(self, p, g, t, tol):
        y0, y1 = self.y_of(g, tol + 10), self.y_of(g, -tol - 10)
        for note in self.run.notes:
            x0, x1 = self.x_of(g, note.start, t), self.x_of(g, note.end, t)
            if x1 < g['ax'] or x0 > g['w']:
                continue
            rect = QRectF(x0, y0, x1 - x0, y1 - y0)
            path = QPainterPath()
            path.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
            active = note.judgement is None and note.start <= t <= note.end
            j = note.judgement
            if j in HITS:
                p.fillPath(path, color(theme.GOLD))
            elif j and j.startswith('miss'):
                p.fillPath(path, color('#5d548f'))
            elif j in ('unclear', 'silent'):
                p.setPen(QPen(color(theme.DIM), px(3), Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)
            else:
                grad = QLinearGradient(x0, 0, x1, 0)
                grad.setColorAt(0, color(theme.VIOLET))
                grad.setColorAt(1, color(theme.PINK))
                if active:
                    p.setPen(QPen(color(theme.PINK, 90), px(16)))
                    p.drawPath(path)
                p.fillPath(path, grad)
                if note.hit_spans:
                    p.save()
                    p.setClipPath(path)
                    for a, b in note.hit_spans:
                        xa, xb = self.x_of(g, a, t), self.x_of(g, b, t)
                        p.fillRect(QRectF(xa, y0, xb - xa, y1 - y0), color(theme.GOLD))
                    p.restore()
                p.setPen(QPen(color(theme.TEXT, 230 if active else 120), px(3)))
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)

    def draw_trail(self, p, g, t):
        prev = None
        for r in self.run.trail:
            if r.time < t - 2.2:
                prev = None
                continue
            pitched = r.cents is not None
            if pitched and prev is not None and r.time - prev.time < .3:
                p.setPen(QPen(color(KIND_COLOR[r.kind], 200), px(9), Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(self.x_of(g, prev.time, t), self.y_of(g, prev.cents)),
                           QPointF(self.x_of(g, r.time, t), self.y_of(g, r.cents)))
            prev = r if pitched else None

    def draw_hit_line(self, p, g, now):
        x = g['hitx']
        reading = self.run.current_reading(now)
        if reading and reading.kind == 'hit' and self.run.active_note(now) is not None:
            p.setPen(QPen(color(theme.GREEN, 70), px(26)))
            p.drawLine(QPointF(x, g['top']), QPointF(x, g['bottom']))
        p.setPen(QPen(color(theme.TEXT, 220), px(4)))
        p.drawLine(QPointF(x, g['top']), QPointF(x, g['bottom']))
        p.setFont(font(20, QFont.Black))
        p.setPen(color(theme.TEXT))
        p.drawText(QRectF(x - px(80), g['bottom'] + px(4), px(160), px(32)), Qt.AlignCenter, 'AHORA')

    def draw_voice(self, p, g, now):
        for x, y, _, _, age in self.particles:
            p.setPen(Qt.NoPen)
            p.setBrush(color(theme.GOLD, int(220 * (1 - age / .6))))
            p.drawEllipse(QPointF(x, y), px(5), px(5))
        reading = self.run.current_reading(now)
        x = g['hitx']
        if reading is None:
            return
        if reading.kind in ('unclear', 'muted'):
            if reading.kind == 'unclear' and self.run.active_note(now) is None:
                return      # fuera de una nota no molestamos con avisos
            text = 'no te oigo claro' if reading.kind == 'unclear' else 'suena la referencia'
            p.setFont(font(22, QFont.Bold))
            width = px(260)
            rect = QRectF(x - width / 2, g['bottom'] - px(60), width, px(46))
            p.setPen(Qt.NoPen)
            p.setBrush(color(theme.SURFACE_2, 235))
            p.drawRoundedRect(rect, px(23), px(23))
            p.setPen(color(theme.MUTED))
            p.drawText(rect, Qt.AlignCenter, text)
            return
        if reading.cents is None or self.display_cents is None:
            return
        y = self.y_of(g, self.display_cents)
        c = KIND_COLOR[reading.kind]
        for extra, alpha in ((px(20), 50), (px(10), 90)):
            p.setPen(Qt.NoPen)
            p.setBrush(color(c, alpha))
            p.drawEllipse(QPointF(x, y), px(20) + extra, px(20) + extra)
        p.setBrush(color(c))
        p.setPen(QPen(color(theme.TEXT), px(3)))
        p.drawEllipse(QPointF(x, y), px(20), px(20))
        if reading.kind in ('low', 'high'):
            # Flecha hacia tu nota: si estás grave apunta arriba y viceversa.
            up = reading.kind == 'low'
            d = -1 if up else 1
            tip = y + d * px(78)
            base = y + d * px(36)
            p.setBrush(color(c))
            p.setPen(Qt.NoPen)
            p.drawPolygon(QPolygonF([QPointF(x, tip), QPointF(x - px(20), base), QPointF(x + px(20), base)]))
            if abs(reading.cents) > RANGE:
                p.setFont(font(20, QFont.Bold))
                p.setPen(color(c))
                label = 'muy grave' if up else 'muy agudo'
                p.drawText(QRectF(x + px(30), y - px(18), px(200), px(36)), Qt.AlignVCenter, label)

    def draw_axis(self, p, g, tol):
        ax = g['ax']
        p.fillRect(QRectF(0, g['top'] - px(8), ax, g['bottom'] - g['top'] + px(16)), color(theme.BG_DEEP, 235))
        p.setPen(QPen(color(theme.LINE), px(2)))
        p.drawLine(QPointF(ax, g['top']), QPointF(ax, g['bottom']))
        p.setFont(font(16))
        for k in (-6, -4, -2, 2, 4, 6):
            y = self.y_of(g, k * 100)
            p.setPen(color(theme.DIM))
            p.drawText(QRectF(ax - px(56), y - px(12), px(48), px(24)), Qt.AlignRight | Qt.AlignVCenter, f'{k:+d}'.replace('-', '−'))
        p.setFont(font(24, QFont.Black))
        p.setPen(color(theme.ORANGE))
        p.drawText(QRectF(px(8), self.y_of(g, 620) - px(20), ax - px(60), px(60)), Qt.AlignLeft | Qt.AlignVCenter, '▲ AGUDO')
        p.setPen(color(theme.CYAN))
        p.drawText(QRectF(px(8), self.y_of(g, -620) - px(40), ax - px(60), px(60)), Qt.AlignLeft | Qt.AlignVCenter, '▼ GRAVE')
        p.setFont(font(15, QFont.Bold))
        p.setPen(color(theme.MUTED))
        p.drawText(QRectF(px(8), self.y_of(g, -330), ax - px(60), px(60)), Qt.AlignLeft | Qt.TextWordWrap, 'semitonos')
        band = QRectF(px(8), self.y_of(g, tol) - px(26), ax - px(16), self.y_of(g, -tol) - self.y_of(g, tol) + px(52))
        p.setPen(Qt.NoPen)
        p.setBrush(color(theme.VIOLET, 70))
        p.drawRoundedRect(band, px(16), px(16))
        p.setFont(font(15, QFont.Black))
        p.setPen(color(theme.GOLD))
        p.drawText(QRectF(band.left(), band.top() + px(4), band.width(), px(22)), Qt.AlignCenter, 'TU NOTA')
        p.setFont(font(30, QFont.Black))
        p.setPen(color(theme.TEXT))
        p.drawText(QRectF(band.left(), band.top() + px(22), band.width(), band.height() - px(24)), Qt.AlignCenter, self.target_label)

    def draw_hud(self, p, g, now):
        run = self.run
        p.fillRect(QRectF(0, 0, g['w'], g['hud']), color(theme.BG_DEEP, 200))
        n = len(run.notes)
        current = run.active_note(now)
        if current is None:
            upcoming = run.next_note(now)
            current = upcoming if upcoming is not None else n - 1
        p.setFont(font(24, QFont.Bold))
        p.setPen(color(theme.TEXT))
        p.drawText(QRectF(px(24), 0, px(220), g['hud']), Qt.AlignVCenter, f'Nota {current + 1} de {n}')
        r = px(14)
        for i, note in enumerate(run.notes):
            cx = px(260) + i * px(44)
            j = note.judgement
            fill = theme.GOLD if j in HITS else '#5d548f' if j and j.startswith('miss') else None
            style = Qt.DotLine if j in ('unclear', 'silent') else Qt.SolidLine
            p.setPen(QPen(color(theme.PINK if i == current and not j else theme.DIM if j else theme.LINE), px(3), style))
            p.setBrush(color(fill) if fill else Qt.NoBrush)
            p.drawEllipse(QPointF(cx, g['hud'] / 2), r, r)
        p.setFont(font(40, QFont.Black))
        p.setPen(color(theme.GOLD))
        p.drawText(QRectF(0, 0, g['w'], g['hud']), Qt.AlignCenter, f'{run.score:,}'.replace(',', '.'))
        if run.streak >= 2:
            p.setFont(font(26, QFont.Black))
            p.setPen(color(theme.PINK))
            p.drawText(QRectF(0, 0, g['w'] - px(24), g['hud']), Qt.AlignRight | Qt.AlignVCenter, f'racha ×{run.streak}')

    def draw_countdown(self, p, g, t):
        first = self.run.notes[0]
        area = QRectF(g['hitx'] + px(40), g['top'] + px(20), g['w'] - g['hitx'] - px(80), px(130))
        if t < first.start:
            if t < .4 + CUE_LENGTH + .3:
                text, size, c = 'Escucha tu nota…', 52, theme.TEXT
            elif first.start - t <= 3:
                text, size, c = str(math.ceil(first.start - t)), 96, theme.GOLD
            else:
                text, size, c = 'Prepárate', 52, theme.TEXT
            p.setFont(font(size, QFont.Black))
            p.setPen(color(c))
            p.drawText(area, Qt.AlignCenter, text)
            return
        nxt = self.run.next_note(self.clock())
        if nxt is not None:
            wait = self.run.notes[nxt].start - t
            if 0 < wait <= 2:
                p.setPen(Qt.NoPen)
                p.setBrush(color(theme.PINK))
                center = QPointF(g['hitx'], g['top'] + px(44))
                p.drawEllipse(center, px(34), px(34))
                p.setFont(font(36, QFont.Black))
                p.setPen(color(theme.TEXT))
                p.drawText(QRectF(center.x() - px(34), center.y() - px(34), px(68), px(68)), Qt.AlignCenter, str(math.ceil(wait)))

    def draw_popups(self, p, g, now, tol):
        for index, judgement, born in self.popups:
            age = now - born
            alpha = int(255 * max(0, 1 - age / 1.6))
            rise = px(60) * min(1, age / .5)
            c = (theme.GOLD if judgement in HITS else theme.MUTED if judgement in ('unclear', 'silent')
                 else theme.CYAN if judgement == 'miss_low' else theme.ORANGE)
            p.setFont(font(44, QFont.Black))
            p.setPen(color(c, alpha))
            p.drawText(QRectF(g['ax'], self.y_of(g, tol) - px(130) - rise, g['hitx'] - g['ax'] + px(260), px(70)),
                       Qt.AlignCenter, JUDGEMENT_TEXT[judgement])
