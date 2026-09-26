"""Ejercicio inicial: una referencia cómoda y progreso sin penalizaciones."""
import math
import statistics
import time
from collections import deque

from PySide6.QtCore import Qt, Signal, QPointF, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout


class FireflyScene(QWidget):
    """La animación ambiental no puntúa: sólo los bloques nuevos de voz lo hacen."""
    def __init__(self):
        super().__init__()
        self.cents = None
        self.progress = 0
        self.capture_progress = 0
        self.mode = 'idle'
        self.phase = 0.0
        self.display_cents = 0.0
        self.display_progress = 0.0
        self.setMinimumHeight(250)
        self.animation = QTimer(self)
        self.animation.setInterval(33)
        self.animation.timeout.connect(self.animate)

    def showEvent(self, event):
        super().showEvent(event)
        self.animation.start()

    def hideEvent(self, event):
        self.animation.stop()
        super().hideEvent(event)

    def animate(self):
        self.phase += .033
        target = max(-400, min(400, self.cents)) if self.cents is not None else 0
        self.display_cents += (target - self.display_cents) * .12
        self.display_progress += (self.progress - self.display_progress) * .10
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor('#14272c'))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(72, 113, 71, int(15 + self.display_progress * 55)))
        p.drawEllipse(QRectF(w * .15, h * .15, w * .7, h * .85))
        # Bambú dibujado en la interfaz: no necesita archivos de imagen.
        for x in (w * .09, w * .15, w * .85, w * .91):
            p.setPen(QPen(QColor('#376456'), 7))
            p.drawLine(QPointF(x, h * .87), QPointF(x + 6, h * .12))
            for k in range(3):
                y = h * (.25 + k * .20)
                p.setPen(QPen(QColor('#67917a'), 2))
                p.drawLine(QPointF(x - 3, y), QPointF(x + 9, y))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor('#497c65'))
                p.drawEllipse(QRectF(x + 4, y - 12, 26, 8))
        p.save()
        p.translate(w * .5, h * .56 + math.sin(self.phase * 1.4) * 2)
        scale = min(1.15, h / 270)
        p.scale(scale, scale)
        p.rotate(math.sin(self.phase * .9) * 1.4)

        def oval(x, y, width, height, color):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(x, y, width, height))

        oval(-62, 62, 124, 16, '#10201f')
        oval(-48, -4, 96, 80, '#19242a')
        oval(-34, 7, 68, 58, '#e9ede1')
        oval(-53, 48, 35, 27, '#182329')
        oval(18, 48, 35, 27, '#182329')
        oval(-56, -60, 35, 35, '#182329')
        oval(21, -60, 35, 35, '#182329')
        oval(-52, -50, 104, 88, '#f5f2e7')
        oval(-35, -22, 27, 32, '#243039')
        oval(8, -22, 27, 32, '#243039')
        blink = self.phase % 4.8 > 4.60
        if blink:
            p.setPen(QPen(QColor('#f5f2e7'), 2))
            p.drawLine(-27, -5, -17, -5)
            p.drawLine(17, -5, 27, -5)
        else:
            oval(-26, -12, 10, 12, '#fcfff5')
            oval(16, -12, 10, 12, '#fcfff5')
            oval(-22, -9, 5, 7, '#152026')
            oval(17, -9, 5, 7, '#152026')
        oval(-8, 8, 16, 10, '#243039')
        p.setPen(QPen(QColor('#243039'), 2))
        p.drawArc(QRectF(-9, 13, 18, 13), 180 * 16, 180 * 16)
        oval(-41, 9, 14, 7, '#e5b8a8')
        oval(27, 9, 14, 7, '#e5b8a8')
        p.save()
        p.translate(42, 23)
        if self.mode == 'complete':
            p.rotate(-65 + math.sin(self.phase * 5) * 18)
        oval(-8, -9, 25, 40, '#182329')
        p.restore()
        oval(-56, 17, 26, 38, '#182329')
        p.restore()
        # Vuelan siempre; la luz ganada y el texto distinguen animación y progreso.
        for i in range(3):
            lit = self.progress >= (i + 1) / 3
            angle = self.phase * (.65 + i * .12) + i * 2.094
            x = w * .5 + math.cos(angle) * min(w * .25, 150)
            y = h * .48 + math.sin(angle) * h * .25
            if self.mode == 'playing':
                x += self.display_cents / 400 * min(w * .13, 80)
            radius = 7 if lit else 4
            for extra, alpha in ((17, 16), (8, 35), (0, 255 if lit else 105)):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255, 223, 128, alpha))
                p.drawEllipse(QPointF(x, y), radius + extra, radius + extra)
        p.setPen(QColor('#d7e9dc'))
        label = ('Buscando tu nota · ' + str(round(self.capture_progress * 100)) + '%'
                 if self.mode == 'calibrating' else
                 f'{min(3, int(self.progress * 3 + .0001))} / 3 luces reunidas')
        p.drawText(QRectF(0, h - 30, w, 25), Qt.AlignCenter, label)


class FireflyWidget(QWidget):
    reference_requested = Signal(float)

    def __init__(self):
        super().__init__()
        self.frequency = None
        self.calibrating = False
        self.samples = deque(maxlen=100)
        self.capture_seconds = 0.0
        self.capture_peak = 0.0
        self.capture_tones = 0
        self.capture_deadline = None
        self.elapsed = 0.0
        self.last_time = None
        self.was_close = False
        self.active = False
        self.confirmed = False
        self.message_key = None
        self.candidate_key = None
        self.candidate_since = 0.0
        self.message_since = float('-inf')
        layout = QVBoxLayout(self)
        title = QLabel('EL CLARO DEL PANDA')
        title.setObjectName('eyebrow')
        layout.addWidget(title)
        intro = QLabel('Un panda, tres luciérnagas y tu voz. Canta suave para iluminar el claro.')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.scene = FireflyScene()
        layout.addWidget(self.scene, 1)
        self.feedback = QLabel('Activa el micro y busca una nota cómoda')
        self.feedback.setAlignment(Qt.AlignCenter)
        self.feedback.setWordWrap(True)
        self.feedback.setMinimumHeight(54)
        self.feedback.setStyleSheet('font-size: 20px; font-weight: 600')
        layout.addWidget(self.feedback)
        self.detail = QLabel('Sin prisas. Puedes parar y respirar cuando quieras.')
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setWordWrap(True)
        self.detail.setMinimumHeight(38)
        layout.addWidget(self.detail)
        self.diagnostic = QLabel('')
        self.diagnostic.setWordWrap(True)
        self.diagnostic.setObjectName('muted')
        self.diagnostic.hide()
        layout.addWidget(self.diagnostic)
        self.capture_watch = QTimer(self)
        self.capture_watch.setSingleShot(True)
        self.capture_watch.timeout.connect(self.capture_failed)
        row = QHBoxLayout()
        self.choose = QPushButton('1 · Encontrar mi nota')
        self.choose.clicked.connect(self.begin)
        self.choose.setEnabled(False)
        self.listen = QPushButton('2 · Escuchar mi nota')
        self.listen.setEnabled(False)
        self.listen.clicked.connect(lambda: self.reference_requested.emit(self.frequency))
        row.addWidget(self.choose)
        row.addWidget(self.listen)
        self.confirm = QPushButton('Sí, es cómoda · jugar')
        self.confirm.setEnabled(False)
        self.confirm.clicked.connect(self.confirm_note)
        row.addWidget(self.confirm)
        layout.addLayout(row)
        help_text = QLabel('Reúne 3 segundos de luz, con las pausas que necesites. No pierdes lo ganado.\nEs una práctica de volver a tu nota, no una prueba de respiración ni de la canción.')
        help_text.setWordWrap(True)
        help_text.setObjectName('muted')
        layout.addWidget(help_text)

    def set_active(self, active):
        self.active = active
        self.choose.setEnabled(active)
        self.scene.mode = ('calibrating' if self.calibrating else 'playing' if self.confirmed else 'ready' if self.frequency else 'idle') if active else 'paused'
        if active and self.elapsed >= 3:
            self.scene.mode = 'complete'
        self.confirm.setEnabled(active and self.frequency is not None and not self.confirmed)
        self.last_time = None
        self.was_close = False
        if not active:
            self.capture_watch.stop()
            self.samples.clear()
            self.scene.cents = None
            self.scene.update()
            self.message('paused', 'En pausa · tu luz está guardada', 'Activa el micro en esta pestaña para continuar.', force=True)
        elif self.frequency is not None and not self.confirmed:
            self.message('confirm', '¿Esta nota te resulta cómoda?', 'Escúchala si quieres. Pulsa «Sí» para jugar o busca otra.', force=True)
        elif self.frequency is None and not self.calibrating:
            self.message('idle', 'Pulsa «Encontrar mi nota» para empezar', 'El panda y las luces se mueven mientras esperan. Aún no estamos puntuando.', force=True)
        elif self.elapsed >= 3:
            self.message('complete', '¡Has iluminado el claro!', 'Descansa o busca otra nota para volver a jugar.', force=True)
        elif self.confirmed:
            self.message('resume', 'Cuando quieras · vuelve a tu nota', 'Tu luz está guardada. Puedes hacer pausas.', force=True)
        elif self.calibrating:
            self.capture_deadline = None
            self.capture_watch.start(4000)
            self.message('capture', 'Canta una «mmm» o una «u» cómoda', 'Buscamos una nota tranquila, sin prisas.', force=True)

    def begin(self):
        self.capture_seconds = 0.0
        self.capture_peak = 0.0
        self.capture_tones = 0
        self.capture_deadline = None
        self.capture_watch.start(4000)
        self.diagnostic.hide()
        self.confirmed = False
        self.confirm.setEnabled(False)
        self.calibrating = True
        self.frequency = None
        self.samples.clear()
        self.elapsed = 0
        self.last_time = None
        self.was_close = False
        self.scene.progress = 0
        self.scene.capture_progress = 0
        self.scene.mode = 'calibrating'
        self.scene.cents = None
        self.scene.update()
        self.listen.setEnabled(False)
        self.message('capture', 'Haz una «u» cómoda durante un segundo', 'Después para y respira. La búsqueda termina sola en un máximo de 4 segundos.', force=True)

    def capture_failed(self):
        if not self.calibrating:
            return
        self.capture_watch.stop()
        self.calibrating = False
        self.scene.mode = 'idle'
        self.scene.capture_progress = 0
        if self.capture_seconds == 0:
            reason = 'No han llegado datos del micrófono.'
            action = 'Desactiva el micro, elige otro dispositivo y vuelve a activarlo.'
        elif self.capture_peak < .002:
            reason = 'La señal del micrófono llega demasiado baja.'
            action = 'Revisa el dispositivo seleccionado y su nivel de entrada. No necesitas cantar más fuerte.'
        elif self.capture_tones == 0:
            reason = 'Llega sonido, pero el detector no encuentra una nota.'
            action = 'Prueba otro micrófono si está disponible. No hace falta prolongar la vocal.'
        else:
            reason = 'He detectado notas, pero aún no una referencia consistente.'
            action = 'Descansa y, cuando quieras, prueba otra «u» de un segundo.'
        self.message('capture_failed', 'Paramos aquí · no sigas sosteniendo la voz', reason + ' ' + action, force=True)
        self.diagnostic.setText(f'Diagnóstico: {self.capture_seconds:.1f} s de audio analizado · {self.capture_tones} bloques con nota · señal máxima {self.capture_peak:.4f}.')
        self.diagnostic.show()

    def confirm_note(self):
        self.confirmed = True
        self.confirm.setEnabled(False)
        self.last_time = None
        self.was_close = False
        self.scene.mode = 'playing'
        self.message('start', 'Vuelve a tu nota para reunir luz', 'Haz sonidos cortos y descansa cuando quieras.', force=True)

    def message(self, key, title, detail, now=None, force=False):
        now = time.monotonic() if now is None else now
        if force:
            self.candidate_key = None
        elif key != self.candidate_key:
            self.candidate_key = key
            self.candidate_since = now
            return
        elif now - self.candidate_since < .4 or now - self.message_since < 2.0:
            return
        if force or key != self.message_key:
            self.message_key = key
            self.message_since = now
            self.feedback.setText(title)
            self.detail.setText(detail)

    def update_reading(self, frequency, volume=0, now=None, duration=.1):
        now = time.monotonic() if now is None else now
        delta = now - self.last_time if self.last_time is not None else 0
        self.last_time = now
        if not self.active:
            return
        # La confirmación y la victoria son estados persistentes; el silencio no los tapa.
        if self.frequency is not None and not self.confirmed:
            return
        if self.elapsed >= 3:
            return
        if self.calibrating:
            if self.capture_deadline is None:
                self.capture_deadline = now + 4
            self.capture_seconds += max(0, duration)
            self.capture_peak = max(self.capture_peak, volume)
            if now >= self.capture_deadline:
                self.capture_failed()
                return
            while self.samples and now - self.samples[0][0] > 3:
                self.samples.popleft()
            if frequency is not None:
                self.capture_tones += 1
                self.samples.append((now, frequency, min(.15, max(0, duration))))
            # Elegir un grupo consistente de lecturas, no exigir inmovilidad continua.
            # Los silencios no añaden tiempo y los saltos de octava no se mezclan.
            best = []
            for _, candidate, _ in self.samples:
                group = [sample for sample in self.samples
                         if abs(1200 * math.log2(sample[1] / candidate)) <= 100]
                if sum(v[2] for v in group) > sum(v[2] for v in best):
                    best = group
            voiced_time = sum(v[2] for v in best)
            self.scene.capture_progress = min(.95, voiced_time / .3)
            if len(best) >= 3 and voiced_time >= .299:
                self.frequency = statistics.median(sample[1] for sample in best)
                self.calibrating = False
                self.capture_watch.stop()
                self.scene.mode = 'ready'
                self.scene.capture_progress = 1
                self.listen.setEnabled(True)
                self.confirm.setEnabled(True)
                self.message('confirm', '¿Esta nota te resulta cómoda?',
                             'Pulsa «Sí, es cómoda · jugar». También puedes escucharla o buscar otra.', now, force=True)
            self.scene.update()
            return
        if self.frequency is None:
            return
        if frequency is None:
            self.was_close = False
            self.scene.cents = None
            self.message('rest', 'Respira · seguimos cuando quieras',
                         'Tu luz está guardada. Vuelve con una «u» suave cuando estés listo.', now)
            return
        cents = 1200 * math.log2(frequency / self.frequency)
        self.scene.cents = cents
        close = abs(cents) <= 50
        if close and self.was_close and 0 < delta <= .25:
            self.elapsed = min(3, self.elapsed + min(delta, duration))
        self.was_close = close
        self.scene.progress = self.elapsed / 3
        if self.elapsed >= 3:
            self.scene.mode = 'complete'
            self.message('complete', '¡Has iluminado el claro!',
                         'El panda te saluda. Descansa o busca otra nota para volver a jugar.', now, force=True)
        elif close:
            self.message('close', 'Por ahí · suave y cómodo',
                         'Las luciérnagas están reuniendo luz. Puedes hacer una pausa cuando quieras.', now)
        elif cents < 0:
            self.message('low', 'Prueba un poquito más agudo',
                         'No hace falta cantar más fuerte. El progreso que llevas se conserva.', now)
        else:
            self.message('high', 'Prueba un poquito más grave',
                         'No hace falta cantar más fuerte. El progreso que llevas se conserva.', now)
        self.scene.update()
