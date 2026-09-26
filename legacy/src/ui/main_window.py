"""Ventana principal: cabecera con navegación y dos páginas (Escalas, Canciones)."""
from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from audio.capture import Microphone
from audio.output import device_format, pick_output_device, play_buffer, synth_phrase
from audio.piano import Piano
from audio.pitch import detect_pitch, rms
from game.progress import Progress
from ui import theme
from ui.panda import PandaBadge
from ui.practice import PracticePage, button, label, scrollable
from ui.songs import SongsPage
from ui.theme import px

MIN_RMS = .002        # puerta de silencio suave; YIN sigue rechazando lo que no tiene tono


class MainWindow(QMainWindow):
    def __init__(self, progress=None):
        super().__init__()
        self.setWindowTitle('Canto')
        self.resize(px(1500), px(940))
        self.mic = Microphone()
        # Con cascos Bluetooth la salida MME enmudece al abrir su micro: usamos WASAPI.
        self.tone_device = pick_output_device()
        self.piano, self.piano_error = None, None
        try:
            self.piano = Piano(device_format(self.tone_device)[0])
        except Exception as exc:          # sin muestras: tono sintético de respaldo
            self.piano_error = str(exc)
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
        self.nav_practice = button('Escalas', 'nav')
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
        self.practice = PracticePage(progress or Progress.load())
        self.songs_page = SongsPage(Path(__file__).resolve().parents[3] / 'canciones')
        self.pages.addWidget(self.practice)
        self.pages.addWidget(scrollable(self.songs_page))
        self.player = self.songs_page.player

        self.practice.devices.addItem('Micrófono predeterminado', None)
        try:
            for index, info in enumerate(sd.query_devices()):
                if info['max_input_channels'] > 0:
                    self.practice.devices.addItem(info['name'], index)
        except Exception:
            pass
        self.practice.mic_toggle_requested.connect(self.toggle_mic)
        self.practice.phrase_requested.connect(self.play_phrase)
        self.practice.songs_requested.connect(lambda: self.show_page(1))
        self.nav.idClicked.connect(self.show_page)
        if self.piano_error:
            self.practice.mic_status.setText(f'Piano no disponible ({self.piano_error}); se usará un tono simple.')

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

    # --- piano ----------------------------------------------------------
    def play_phrase(self, notes):
        """Toca [(desfase_s, frecuencia, duración_s)] al piano. El juego ya no puntúa ese tramo."""
        self.player.pause()
        error = None
        for device in dict.fromkeys((self.tone_device, None)):
            try:
                rate, channels = device_format(device)
                if self.piano is not None and self.piano.rate == rate:
                    buffer = self.piano.phrase(notes)
                else:
                    buffer = synth_phrase(notes, rate)
                play_buffer(buffer, rate, channels, device)
                return
            except Exception as exc:
                error = exc
        text = f'No se pudo reproducir el piano: {error}'
        self.practice.mic_status.setText(text)
        self.practice.show_message('toneerr', text, theme.ORANGE, force=True)

    def closeEvent(self, event):
        sd.stop()
        self.timer.stop()
        self.mic.stop()
        self.player.stop()
        event.accept()
