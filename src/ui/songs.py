"""Página «Canciones»: biblioteca local, reproducción y repetición A–B."""
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QSlider, QVBoxLayout, QWidget,
)

from ui.practice import button, card, label
from ui.theme import px

# Glifos de Segoe MDL2 Assets (incluida en Windows 10/11): no se ven como emoji.
PLAY, PAUSE = chr(0xE768), chr(0xE769)
AUDIO = {'.m4a', '.mp3', '.wav', '.flac', '.ogg'}


def clock(ms):
    seconds = max(0, ms // 1000)
    return f'{seconds // 60}:{seconds % 60:02d}'


class SongsPage(QWidget):
    def __init__(self, folder):
        super().__init__()
        self.a = 0
        self.b = None
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.output.setVolume(.5)
        self.player.setAudioOutput(self.output)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(px(56), px(36), px(56), px(36))
        layout.setSpacing(px(22))
        layout.addWidget(label('CANCIONES', 'eyebrow'))
        layout.addWidget(label('Escucha y practica por fragmentos', 'display'))
        layout.addWidget(label('Tu biblioteca local. La adaptación de tonalidad y la puntuación de canciones llegarán después.', 'lead'))

        frame, c = card()
        c.setSpacing(px(20))
        row = QHBoxLayout()
        self.songs = QComboBox()
        self.songs.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.songs.setMinimumContentsLength(10)
        for path in sorted(Path(folder).glob('*')):
            if path.suffix.lower() in AUDIO:
                self.songs.addItem(path.stem, str(path))
        row.addWidget(self.songs, 1)
        load = button('Abrir audio…')
        load.clicked.connect(self.open_audio)
        row.addWidget(load)
        c.addLayout(row)

        self.title = label('', 'h1')
        c.addWidget(self.title)
        transport = QHBoxLayout()
        transport.setSpacing(px(24))
        self.play = button(PLAY, 'round')
        self.play.clicked.connect(self.toggle_play)
        transport.addWidget(self.play)
        bar = QVBoxLayout()
        self.position = QSlider(Qt.Horizontal)
        self.position.setRange(0, 0)
        self.position.sliderMoved.connect(self.player.setPosition)
        bar.addWidget(self.position)
        self.time = label('0:00 / 0:00', 'h2', wrap=False)
        bar.addWidget(self.time)
        transport.addLayout(bar, 1)
        c.addLayout(transport)

        loop_row = QHBoxLayout()
        loop_row.setSpacing(px(16))
        self.mark_a = button('Marcar inicio A')
        self.mark_a.clicked.connect(self.set_a)
        loop_row.addWidget(self.mark_a)
        self.mark_b = button('Marcar final B')
        self.mark_b.clicked.connect(self.set_b)
        loop_row.addWidget(self.mark_b)
        self.loop = QCheckBox('Repetir A–B')
        self.loop.setEnabled(False)
        loop_row.addWidget(self.loop)
        loop_row.addStretch()
        loop_row.addWidget(label('Volumen', 'muted', wrap=False))
        volume = QSlider(Qt.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(50)
        volume.setMinimumWidth(px(140))
        volume.valueChanged.connect(lambda v: self.output.setVolume(v / 100))
        loop_row.addWidget(volume)
        c.addLayout(loop_row)
        self.segment = label('Elige un inicio y un final para practicar por partes.', 'lead')
        c.addWidget(self.segment)
        self.status = label('', 'muted')
        c.addWidget(self.status)
        layout.addWidget(frame)
        layout.addStretch()

        self.player.positionChanged.connect(self.on_position)
        self.player.durationChanged.connect(lambda d: self.position.setRange(0, d))
        self.player.playbackStateChanged.connect(lambda s: self.play.setText(
            PAUSE if s == QMediaPlayer.PlayingState else PLAY))
        self.player.errorOccurred.connect(lambda *args: self.status.setText(
            'No se pudo reproducir el audio: ' + self.player.errorString()))
        self.songs.currentIndexChanged.connect(self.select_song)
        self.select_song()

    def select_song(self, *_):
        self.player.stop()
        self.a, self.b = 0, None
        self.loop.setChecked(False)
        self.loop.setEnabled(False)
        self.segment.setText('Elige un inicio y un final para practicar por partes.')
        self.title.setText(self.songs.currentText() or 'Añade audio a la carpeta «canciones»')
        if self.songs.currentData():
            self.player.setSource(QUrl.fromLocalFile(self.songs.currentData()))

    def open_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Abrir canción', '', 'Audio (*.m4a *.mp3 *.wav *.flac *.ogg)')
        if path:
            self.songs.addItem(Path(path).stem, path)
            self.songs.setCurrentIndex(self.songs.count() - 1)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            if self.loop.isChecked() and self.b is not None and not self.a <= self.player.position() < self.b:
                self.player.setPosition(self.a)
            self.player.play()

    def set_a(self):
        self.a = self.player.position()
        self.b = None
        self.loop.setChecked(False)
        self.loop.setEnabled(False)
        self.segment.setText(f'Inicio A: {clock(self.a)} · marca el final al menos 1 segundo después.')

    def set_b(self):
        position = self.player.position()
        if position < self.a + 1000:
            self.status.setText('El final B debe estar al menos 1 segundo después del inicio A.')
            return
        self.b = position
        self.loop.setEnabled(True)
        self.segment.setText(f'Fragmento: {clock(self.a)} → {clock(self.b)}')

    def on_position(self, position):
        if not self.position.isSliderDown():
            self.position.setValue(position)
        self.time.setText(f'{clock(position)} / {clock(self.player.duration())}')
        if self.loop.isChecked() and self.b is not None and position >= self.b:
            self.player.setPosition(self.a)
            self.player.play()
