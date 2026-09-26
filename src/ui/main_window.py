"""Ventana principal: cabecera con navegación y dos páginas (Pista de voz, Canciones)."""
from pathlib import Path

import numpy as np
import sounddevice as sd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from audio.capture import Microphone
from audio.pitch import detect_pitch, rms
from ui import theme
from ui.panda import PandaBadge
from ui.practice import PracticePage, button, label
from ui.songs import SongsPage
from ui.theme import px

MIN_RMS = .002        # puerta de silencio suave; YIN sigue rechazando lo que no tiene tono


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Canto')
        self.resize(px(1500), px(940))
        self.mic = Microphone()
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName('header')
        bar = QHBoxLayout(header)
        bar.setContentsMargins(px(28), px(10), px(28), px(10))
        bar.setSpacing(px(14))
        bar.addWidget(PandaBadge(44))
        bar.addWidget(label('canto', 'brand', wrap=False))
        bar.addSpacing(px(30))
        self.nav = QButtonGroup(self)
        self.nav_practice = button('Pista de voz', 'nav')
        self.nav_songs = button('Canciones', 'nav')
        for i, b in enumerate((self.nav_practice, self.nav_songs)):
            b.setCheckable(True)
            self.nav.addButton(b, i)
            bar.addWidget(b)
        bar.addStretch()
        self.mic_pill = label('', 'pill', wrap=False)
        bar.addWidget(self.mic_pill)
        self.full = button('Pantalla completa')
        self.full.clicked.connect(self.toggle_fullscreen)
        bar.addWidget(self.full)
        layout.addWidget(header)

        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.practice = PracticePage()
        self.songs_page = SongsPage(Path(__file__).resolve().parents[2] / 'canciones')
        self.pages.addWidget(self.practice)
        self.pages.addWidget(self.songs_page)
        self.player = self.songs_page.player

        self.practice.devices.addItem('Micrófono predeterminado', None)
        try:
            for index, info in enumerate(sd.query_devices()):
                if info['max_input_channels'] > 0:
                    self.practice.devices.addItem(info['name'], index)
        except Exception:
            pass
        self.practice.mic_toggle_requested.connect(self.toggle_mic)
        self.practice.tone_requested.connect(self.play_tone)
        self.practice.songs_requested.connect(lambda: self.show_page(1))
        self.nav.idClicked.connect(self.show_page)

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.read_mic)
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.space)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.escape)
        QShortcut(QKeySequence(Qt.Key_F11), self, activated=self.toggle_fullscreen)
        self.update_mic_pill()
        self.show_page(0)

    # --- navegación -----------------------------------------------------
    def show_page(self, index):
        self.nav.button(index).setChecked(True)
        self.pages.setCurrentIndex(index)
        if index == 0:
            self.player.pause()     # la canción nunca suena mientras se practica
        self.mic.drain()
        self.practice.set_page_visible(index == 0)

    def space(self):
        if self.pages.currentIndex() == 0:
            self.practice.primary_action()
        else:
            self.songs_page.toggle_play()

    def escape(self):
        if self.practice.escape_action():
            return
        if self.isFullScreen():
            self.toggle_fullscreen()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized()
            self.full.setText('Pantalla completa')
        else:
            self.showFullScreen()
            self.full.setText('Salir de pantalla completa')

    # --- micrófono ------------------------------------------------------
    def update_mic_pill(self):
        on = self.mic.stream is not None
        dot = theme.GREEN if on else theme.DIM
        self.mic_pill.setText(f'<span style="color:{dot}">●</span> Micro {"activo" if on else "apagado"}')

    def toggle_mic(self):
        if self.mic.stream is not None:
            self.timer.stop()
            self.mic.stop()
            self.practice.set_mic(False, 'Micrófono desactivado.')
            self.update_mic_pill()
            return
        try:
            self.mic.start(self.practice.devices.currentData())
        except Exception as exc:
            self.practice.set_mic(False, f'No se pudo abrir el micrófono. Revisa el dispositivo y los permisos: {exc}')
            return
        self.practice.set_mic(True, 'Escuchando. Tu voz no se graba ni se envía.')
        self.update_mic_pill()
        self.timer.start()

    def read_mic(self):
        for stamp, frame in self.mic.drain():
            try:
                frequency = detect_pitch(frame, self.mic.sample_rate, min_rms=MIN_RMS)
            except ValueError:
                frequency = None
            self.practice.feed(stamp, len(frame) / self.mic.sample_rate, frequency, rms(frame))
        self.practice.tick()
        if self.mic.status:
            self.practice.mic_status.setText('Aviso de entrada: ' + self.mic.status)
            self.mic.status = ''

    # --- referencia -----------------------------------------------------
    def play_tone(self, frequency, seconds):
        """Tono suave de referencia. El juego ya ha excluido este tiempo de la puntuación."""
        self.player.pause()
        rate = 44100
        t = np.arange(int(rate * seconds)) / rate
        envelope = np.minimum(1, t / .03) * np.minimum(1, (seconds - t) / .12)
        wave = np.sin(2 * np.pi * frequency * t) + .25 * np.sin(4 * np.pi * frequency * t)
        tone = (.12 * wave * envelope).astype('float32')
        try:
            sd.play(tone, rate)
        except Exception as exc:
            self.practice.mic_status.setText(f'No se pudo reproducir la nota: {exc}')

    def closeEvent(self, event):
        sd.stop()
        self.timer.stop()
        self.mic.stop()
        self.player.stop()
        event.accept()
