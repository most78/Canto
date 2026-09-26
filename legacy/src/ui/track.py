"""Pista de voz: las notas avanzan de derecha a izquierda hacia la línea «AHORA».

Eje vertical = altura: cada línea es un semitono con su nombre (La2, Si2…).
Eje horizontal = tiempo. Primero pasan las barras de ESCUCHA (el piano las
toca; no puntúan) y después las de TU TURNO, con el nombre de cada nota. La
bola en la línea es tu voz; la estela, lo que acabas de cantar.
Esta vista sólo LEE el estado de `NoteRun`: animar no puntúa.
"""
import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from game.levels import note_name
from game.note_run import HITS, JUDGEMENT_TEXT
from ui import theme
from ui.theme import color, font, px

LOOKAHEAD = 5.5      # segundos visibles por delante de la línea
HIT_FRACTION = .26   # posición de la línea «AHORA» dentro del carril
MARGIN_CENTS = 350   # aire por encima y por debajo de la frase

KIND_COLOR = {'hit': theme.GREEN, 'low': theme.CYAN, 'high': theme.ORANGE, 'free': theme.VIOLET}


class TrackView(QWidget):
    def __init__(self, clock=time.monotonic):
        super().__init__()
        self.clock = clock
        self.run = None
        self.anchor_midi = 57
        self.level_name = ''
        self.center = 0.0
        self.half = 700.0
        self.display_cents = None
        self.popups = []
        self.particles = []
        self.last_tick = None
        self.setMinimumHeight(px(420))
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)

    def set_run(self, run, anchor_midi, level_name=''):
        self.run = run
        self.anchor_midi = anchor_midi
        self.level_name = level_name
        semis = [n.semitone for n in run.notes]
        lo, hi = min(semis) * 100, max(semis) * 100
        self.center = (lo + hi) / 2
        self.half = max(650, (hi - lo) / 2 + MARGIN_CENTS)
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
            target = max(self.center - self.half, min(self.center + self.half, reading.cents))
            if self.display_cents is None:
                self.display_cents = target
            self.display_cents += (target - self.display_cents) * min(1, dt * 16)
            if reading.kind == 'hit' and self.run.active_note(now) is not None:
                g = self.geometry_info()
                for _ in range(2):
                    self.particles.append([g['hitx'], self.y_of(g, self.display_cents),
                                           random.uniform(-260, -80), random.uniform(-160, 160), 0.0])
        for part in self.particles:
            part[0] += part[2] * dt * px(1)
            part[1] += part[3] * dt * px(1)
            part[4] += dt
        self.particles = [q for q in self.particles if q[4] < .6]
        self.popups = [q for q in self.popups if now - q[2] < 1.6]
        self.update()

    # --- geometría ------------------------------------------------------
    def geometry_info(self):
        w, h = self.width(), self.height()
        hud = px(78)
        ax = px(170)
        top, bottom = hud + px(8), h - px(40)
        hitx = ax + (w - ax) * HIT_FRACTION
        return {
            'w': w, 'h': h, 'hud': hud, 'ax': ax, 'top': top, 'bottom': bottom,
            'cy': (top + bottom) / 2, 'cpp': (bottom - top) / (2 * self.half),
            'hitx': hitx, 'pps': (w - hitx) / LOOKAHEAD,
        }

    def y_of(self, g, cents):
        c = max(self.center - self.half - 40, min(self.center + self.half + 40, cents))
        return g['cy'] - (c - self.center) * g['cpp']

    @staticmethod
    def x_of(g, song_time, t):
        return g['hitx'] + (song_time - t) * g['pps']

    def name(self, semitone):
        return note_name(self.anchor_midi + semitone)

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
        self.draw_lane(p, g)
        p.save()
        p.setClipRect(QRectF(g['ax'], 0, g['w'] - g['ax'], g['h']))   # nada asoma bajo el eje
        self.draw_labels(p, g, t)
        self.draw_notes(p, g, t)
        self.draw_trail(p, g, t)
        self.draw_hit_line(p, g, now)
        self.draw_voice(p, g, now)
        self.draw_popups(p, g, now)
        p.restore()
        self.draw_axis(p, g)
        self.draw_hud(p, g, now)
        self.draw_phase(p, g, now)
        if self.run.state == 'paused':
            p.fillRect(self.rect(), color(theme.BG_DEEP, 190))
            p.setPen(color(theme.TEXT))
            p.setFont(font(64, QFont.Black))
            p.drawText(QRectF(0, g['cy'] - px(90), g['w'], px(90)), Qt.AlignCenter, 'En pausa')
            p.setFont(font(28))
            p.setPen(color(theme.MUTED))
            p.drawText(QRectF(0, g['cy'] + px(10), g['w'], px(60)), Qt.AlignCenter,
                       'Pulsa «Seguir» o la barra espaciadora. El tiempo está detenido.')

    def semitones_visible(self):
        lo = math.ceil((self.center - self.half) / 100)
        hi = math.floor((self.center + self.half) / 100)
        return range(lo, hi + 1)

    def draw_lane(self, p, g):
        ax, w = g['ax'], g['w']
        used = {n.semitone for n in self.run.notes}
        for k in self.semitones_visible():
            y = self.y_of(g, k * 100)
            if k in used:
                p.fillRect(QRectF(ax, y - px(2), w - ax, px(4)), color(theme.VIOLET, 60))
            p.setPen(QPen(color(theme.TEXT, 40 if k in used else 16), px(1)))
            p.drawLine(QPointF(ax, y), QPointF(w, y))

    def draw_labels(self, p, g, t):
        """«ESCUCHA», «TU TURNO» y «respira» sobre cada tramo de la ronda."""
        p.setFont(font(20, QFont.Black))
        top = g['top'] + px(6)
        for a in self.run.attempts:
            demo = [n for n in self.run.notes if n.attempt == a and n.demo]
            sung = [n for n in self.run.sung if n.attempt == a]
            for group, text, colour in ((demo, 'ESCUCHA', theme.MUTED), (sung, 'TU TURNO', theme.PINK)):
                if not group:
                    continue
                x0, x1 = self.x_of(g, group[0].start, t), self.x_of(g, group[-1].end, t)
                if x1 < g['ax'] or x0 > g['w']:
                    continue
                p.setPen(QPen(color(colour, 120), px(2)))
                p.drawLine(QPointF(max(x0, g['ax']), top + px(30)), QPointF(x1, top + px(30)))
                p.setPen(color(colour))
                p.drawText(QRectF(max(x0, g['ax'] + px(6)), top, px(260), px(28)), Qt.AlignLeft | Qt.AlignVCenter, text)
            nxt = [n for n in self.run.notes if n.attempt == a + 1]
            if sung and nxt:
                mid = (sung[-1].end + nxt[0].start) / 2
                x = self.x_of(g, mid, t)
                if g['ax'] + px(60) < x < g['w'] - px(60):
                    p.setPen(color(theme.CYAN, 200))
                    p.setFont(font(24, QFont.Bold))
                    p.drawText(QRectF(x - px(100), g['cy'] - px(20), px(200), px(40)), Qt.AlignCenter, 'respira')
                    p.setFont(font(20, QFont.Black))

    def draw_notes(self, p, g, t):
        min_h = px(38)
        for note in self.run.notes:
            x0, x1 = self.x_of(g, note.start, t), self.x_of(g, note.end, t)
            if x1 < g['ax'] or x0 > g['w']:
                continue
            yc = self.y_of(g, note.target)
            half = max(min_h / 2, self.run.tolerance * g['cpp'])
            rect = QRectF(x0, yc - half, x1 - x0, 2 * half)
            path = QPainterPath()
            path.addRoundedRect(rect, half, half)
            label_colour = theme.INK
            if note.demo:
                playing = note.start <= t <= note.end
                p.fillPath(path, color(theme.VIOLET, 170 if playing else 70))
                if playing:
                    p.setPen(QPen(color(theme.VIOLET, 110), px(14)))
                    p.drawPath(path)
                p.setPen(QPen(color(theme.TEXT, 150), px(2), Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawPath(path)
                label_colour = theme.TEXT
            else:
                j = note.judgement
                active = j is None and note.start <= t <= note.end
                if j in HITS:
                    p.fillPath(path, color(theme.GOLD))
                elif j and j.startswith('miss'):
                    p.fillPath(path, color('#5d548f'))
                    label_colour = theme.TEXT
                elif j in ('unclear', 'silent'):
                    p.setPen(QPen(color(theme.DIM), px(3), Qt.DashLine))
                    p.setBrush(Qt.NoBrush)
                    p.drawPath(path)
                    label_colour = theme.DIM
                else:
                    grad = QLinearGradient(x0, 0, x1, 0)
                    grad.setColorAt(0, color(theme.PINK))
                    grad.setColorAt(1, color('#ff8fc0'))
                    if active:
                        p.setPen(QPen(color(theme.PINK, 90), px(16)))
                        p.drawPath(path)
                    p.fillPath(path, grad)
                    if note.hit_spans:
                        p.save()
                        p.setClipPath(path)
                        for a, b in note.hit_spans:
                            xa, xb = self.x_of(g, a, t), self.x_of(g, b, t)
                            p.fillRect(QRectF(xa, rect.top(), xb - xa, rect.height()), color(theme.GOLD))
                        p.restore()
                    p.setPen(QPen(color(theme.TEXT, 230 if active else 120), px(3)))
                    p.setBrush(Qt.NoBrush)
                    p.drawPath(path)
            p.setFont(font(22, QFont.Black))
            p.setPen(color(label_colour))
            label = self.name(note.semitone)
            if rect.width() > px(64):
                p.drawText(rect, Qt.AlignCenter, label)
            else:
                p.setPen(color(theme.TEXT))
                p.drawText(QRectF(x0 - px(30), rect.top() - px(30), rect.width() + px(60), px(28)), Qt.AlignCenter, label)

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
            if reading.kind == 'muted':
                return      # durante la escucha no mostramos nada del micro
            p.setFont(font(22, QFont.Bold))
            width = px(260)
            rect = QRectF(x - width / 2, g['bottom'] - px(60), width, px(46))
            p.setPen(Qt.NoPen)
            p.setBrush(color(theme.SURFACE_2, 235))
            p.drawRoundedRect(rect, px(23), px(23))
            p.setPen(color(theme.MUTED))
            p.drawText(rect, Qt.AlignCenter, 'no te oigo claro')
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
            # Flecha hacia la nota: si estás grave apunta arriba y viceversa.
            up = reading.kind == 'low'
            d = -1 if up else 1
            tip = y + d * px(78)
            base = y + d * px(36)
            p.setBrush(color(c))
            p.setPen(Qt.NoPen)
            p.drawPolygon(QPolygonF([QPointF(x, tip), QPointF(x - px(20), base), QPointF(x + px(20), base)]))

    def draw_axis(self, p, g):
        ax = g['ax']
        p.fillRect(QRectF(0, g['top'] - px(8), ax, g['bottom'] - g['top'] + px(16)), color(theme.BG_DEEP, 235))
        p.setPen(QPen(color(theme.LINE), px(2)))
        p.drawLine(QPointF(ax, g['top']), QPointF(ax, g['bottom']))
        used = {n.semitone for n in self.run.notes}
        visible = list(self.semitones_visible())
        step = 1 if len(visible) <= 18 else 2
        for k in visible:
            if k not in used and k % step:
                continue
            y = self.y_of(g, k * 100)
            strong = k in used
            p.setFont(font(20 if strong else 15, QFont.Black if strong else QFont.Normal))
            p.setPen(color(theme.TEXT if strong else theme.DIM))
            p.drawText(QRectF(px(40), y - px(14), ax - px(52), px(28)), Qt.AlignRight | Qt.AlignVCenter, self.name(k))
            if k == 0:
                p.setFont(font(13, QFont.Black))
                p.setPen(color(theme.PINK))
                p.drawText(QRectF(px(4), y - px(12), px(40), px(24)), Qt.AlignLeft | Qt.AlignVCenter, 'TU')
        p.setFont(font(18, QFont.Black))
        p.setPen(color(theme.ORANGE))
        p.drawText(QRectF(px(8), g['top'], ax - px(16), px(30)), Qt.AlignLeft | Qt.AlignVCenter, '▲ agudo')
        p.setPen(color(theme.CYAN))
        p.drawText(QRectF(px(8), g['bottom'] - px(30), ax - px(16), px(30)), Qt.AlignLeft | Qt.AlignVCenter, '▼ grave')

    def draw_hud(self, p, g, now):
        run = self.run
        p.fillRect(QRectF(0, 0, g['w'], g['hud']), color(theme.BG_DEEP, 200))
        phase, attempt = run.phase(now)
        p.setFont(font(24, QFont.Bold))
        p.setPen(color(theme.TEXT))
        p.drawText(QRectF(px(24), 0, px(260), g['hud']), Qt.AlignVCenter,
                   f'Intento {attempt + 1} de {len(run.attempts)}')
        r = px(15)
        for i in run.attempts:
            cx = px(280) + i * px(46)
            notes = [n for n in run.sung if n.attempt == i]
            done = all(n.judgement for n in notes)
            score = run.attempt_score(i)
            fill = (theme.GOLD if done and score >= .8 else '#5d548f' if done else None)
            p.setPen(QPen(color(theme.PINK if i == attempt and not done else theme.LINE), px(3)))
            p.setBrush(color(fill) if fill else Qt.NoBrush)
            p.drawEllipse(QPointF(cx, g['hud'] / 2), r, r)
        p.setFont(font(40, QFont.Black))
        p.setPen(color(theme.GOLD))
        p.drawText(QRectF(0, 0, g['w'], g['hud']), Qt.AlignCenter, f'{run.score:,}'.replace(',', '.'))
        p.setFont(font(22, QFont.Bold))
        p.setPen(color(theme.MUTED))
        right = self.level_name + (f'   ·   racha ×{run.streak}' if run.streak >= 2 else '')
        p.drawText(QRectF(0, 0, g['w'] - px(24), g['hud']), Qt.AlignRight | Qt.AlignVCenter, right)

    def draw_phase(self, p, g, now):
        phase, attempt = self.run.phase(now)
        t = self.run.time(now)
        area = QRectF(g['hitx'] + px(40), g['bottom'] - px(150), g['w'] - g['hitx'] - px(80), px(120))
        if phase == 'intro':
            text, size, c = 'Primero escucha al piano', 44, theme.TEXT
        elif phase == 'turn':
            first = next(n for n in self.run.sung if n.attempt == attempt)
            text, size, c = f'¡Tu turno!  {math.ceil(first.start - t)}', 56, theme.PINK
        else:
            return
        p.setFont(font(size, QFont.Black))
        p.setPen(color(c))
        p.drawText(area, Qt.AlignCenter, text)

    def draw_popups(self, p, g, now):
        for index, judgement, born in self.popups:
            note = self.run.notes[index]
            age = now - born
            alpha = int(255 * max(0, 1 - age / 1.6))
            rise = px(60) * min(1, age / .5)
            c = (theme.GOLD if judgement in HITS else theme.MUTED if judgement in ('unclear', 'silent')
                 else theme.CYAN if judgement == 'miss_low' else theme.ORANGE)
            # Encima de su propia barra, que ya ha pasado la línea: no tapa las siguientes.
            t = self.run.time(now)
            xc = (self.x_of(g, note.start, t) + self.x_of(g, note.end, t)) / 2
            y = self.y_of(g, note.target) - px(78) - rise
            p.setFont(font(28, QFont.Black))
            p.setPen(color(c, alpha))
            p.drawText(QRectF(xc - px(130), y, px(260), px(44)), Qt.AlignCenter, JUDGEMENT_TEXT[judgement])
