from pathlib import Path

import sounddevice as sd
import numpy as np
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QSlider, QVBoxLayout, QWidget, QTabWidget,
)

from audio.capture import Microphone
from audio.pitch import detect_pitch, rms
from ui.firefly import FireflyWidget


def clock(ms):
    seconds = max(0, ms // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Canto · Tu espacio de práctica")
        self.resize(900, 740)
        self.mic = Microphone()
        self.a = 0
        self.b = None
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.output.setVolume(0.5)
        self.player.setAudioOutput(self.output)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(10)
        brand = QLabel("canto / estudio de voz")
        brand.setObjectName("eyebrow")
        heading = QLabel("Haz tuya la canción.")
        heading.setObjectName("heading")
        layout.addWidget(brand)
        layout.addWidget(heading)
        layout.addWidget(QLabel("Escucha, repite un fragmento y encuentra tu nota. Usa auriculares."))
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        song_page = QWidget()
        song_layout = QVBoxLayout(song_page)
        self.tabs.addTab(song_page, "Canción")
        self.songs = QComboBox()
        self.songs.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.songs.setMinimumContentsLength(25)
        folder = Path(__file__).resolve().parents[2] / "canciones"
        for path in sorted(folder.glob("*")):
            if path.suffix.lower() in {".m4a", ".mp3", ".wav", ".flac", ".ogg"}:
                self.songs.addItem(path.stem, str(path))
        row = QHBoxLayout()
        row.addWidget(self.songs, 1)
        load = QPushButton("Abrir audio…")
        load.clicked.connect(self.open_audio)
        row.addWidget(load)
        song_layout.addLayout(row)
        self.position = QSlider(Qt.Horizontal)
        self.position.setRange(0, 0)
        self.position.sliderMoved.connect(self.player.setPosition)
        song_layout.addWidget(self.position)
        self.time = QLabel("0:00 / 0:00")
        song_layout.addWidget(self.time)
        controls = QHBoxLayout()
        self.play = QPushButton("Reproducir")
        self.play.clicked.connect(self.toggle_play)
        controls.addWidget(self.play)
        self.mark_a = QPushButton("Marcar inicio A")
        self.mark_a.clicked.connect(self.set_a)
        controls.addWidget(self.mark_a)
        self.mark_b = QPushButton("Marcar final B")
        self.mark_b.clicked.connect(self.set_b)
        controls.addWidget(self.mark_b)
        self.loop = QCheckBox("Repetir A–B")
        self.loop.setEnabled(False)
        controls.addWidget(self.loop)
        song_layout.addLayout(controls)
        self.segment = QLabel("Elige un inicio y un final para practicar por partes.")
        song_layout.addWidget(self.segment)
        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("Volumen de canción"))
        volume = QSlider(Qt.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(50)
        volume.valueChanged.connect(lambda v: self.output.setVolume(v / 100))
        volume_row.addWidget(volume)
        song_layout.addLayout(volume_row)
        self.tuner = FireflyWidget()
        self.tuner.reference_requested.connect(self.play_reference)
        self.reference_timer = QTimer(self)
        self.reference_timer.setSingleShot(True)
        self.reference_timer.timeout.connect(self.finish_reference)
        song_layout.addStretch()
        song_hint = QLabel("Escucha y practica por fragmentos. La adaptación de tonalidad y la evaluación de la melodía llegarán después.")
        song_hint.setWordWrap(True)
        song_layout.addWidget(song_hint)
        self.tabs.addTab(self.tuner, "Ejercicios · Panda")
        mic_row = QHBoxLayout()
        self.devices = QComboBox()
        self.devices.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.devices.setMinimumContentsLength(25)
        self.devices.addItem("Micrófono predeterminado", None)
        try:
            for index, info in enumerate(sd.query_devices()):
                if info["max_input_channels"] > 0:
                    self.devices.addItem(info["name"], index)
        except Exception:
            pass
        mic_row.addWidget(self.devices, 1)
        self.mic_button = QPushButton("Activar micrófono")
        self.mic_button.clicked.connect(self.toggle_mic)
        mic_row.addWidget(self.mic_button)
        layout.addLayout(mic_row)
        self.status = QLabel("Audio y micrófono locales. Tu voz no se graba ni se envía.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        note = QLabel("Canta con tu voz. El ejercicio parte de una nota cómoda; la canción aún no se evalúa.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        self.player.positionChanged.connect(self.on_position)
        self.player.durationChanged.connect(lambda d: self.position.setRange(0, d))
        self.player.playbackStateChanged.connect(lambda s: self.play.setText(
            "Pausar" if s == QMediaPlayer.PlayingState else "Reproducir"))
        self.player.errorOccurred.connect(lambda *args: self.status.setText(
            "No se pudo reproducir el audio: " + self.player.errorString()))
        self.songs.currentIndexChanged.connect(self.select_song)
        self.timer = QTimer(self)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self.read_mic)
        self.tabs.currentChanged.connect(self.change_tab)
        self.select_song()

    def select_song(self, *_):
        self.player.stop()
        self.a, self.b = 0, None
        self.loop.setChecked(False)
        self.loop.setEnabled(False)
        self.segment.setText("Elige un inicio y un final para practicar por partes.")
        if self.songs.currentData():
            self.player.setSource(QUrl.fromLocalFile(self.songs.currentData()))

    def open_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir canción", "", "Audio (*.m4a *.mp3 *.wav *.flac *.ogg)")
        if path:
            self.songs.addItem(Path(path).stem, path)
            self.songs.setCurrentIndex(self.songs.count() - 1)

    def toggle_play(self):
        if self.reference_timer.isActive():
            self.reference_timer.stop()
            sd.stop()
            self.finish_reference()
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
        self.segment.setText(f"Inicio A: {clock(self.a)} · marca el final al menos 1 segundo después.")

    def set_b(self):
        position = self.player.position()
        if position < self.a + 1000:
            self.status.setText("El final B debe estar al menos 1 segundo después del inicio A.")
            return
        self.b = position
        self.loop.setEnabled(True)
        self.segment.setText(f"Fragmento: {clock(self.a)} → {clock(self.b)}")

    def on_position(self, position):
        if not self.position.isSliderDown():
            self.position.setValue(position)
        self.time.setText(f"{clock(position)} / {clock(self.player.duration())}")
        if self.loop.isChecked() and self.b is not None and position >= self.b:
            self.player.setPosition(self.a)
            self.player.play()

    def toggle_mic(self):
        if self.mic.stream is not None:
            self.timer.stop()
            self.mic.stop()
            self.devices.setEnabled(True)
            self.mic_button.setText("Activar micrófono")
            self.tuner.set_active(False)
            self.tuner.detail.setText("Micrófono desactivado")
            return
        try:
            self.mic.start(self.devices.currentData())
        except Exception as exc:
            self.status.setText(f"No se pudo abrir el micrófono. Revisa el dispositivo y los permisos: {exc}")
            return
        self.devices.setEnabled(False)
        self.mic_button.setText("Desactivar micrófono")
        self.status.setText("Escuchando · usa auriculares para que la canción no entre en el micrófono.")
        self.tuner.set_active(self.tabs.currentIndex() == 1)
        self.timer.start()

    def read_mic(self):
        frame = self.mic.latest()
        if self.reference_timer.isActive():
            return
        if frame is not None:
            self.tuner.update_reading(detect_pitch(frame, self.mic.sample_rate, min_rms=.002), rms(frame), duration=len(frame) / self.mic.sample_rate)
        if self.mic.status:
            self.status.setText("Aviso de entrada: " + self.mic.status)
            self.mic.status = ""

    def play_reference(self, frequency):
        self.player.pause()
        sample_rate = 44100
        t = np.arange(int(sample_rate * 1.5)) / sample_rate
        envelope = np.minimum(1, t / .03) * np.minimum(1, (1.5 - t) / .08)
        tone = (0.15 * np.sin(2 * np.pi * frequency * t) * envelope).astype("float32")
        try:
            sd.play(tone, sample_rate)
        except Exception as exc:
            self.status.setText(f"No se pudo reproducir la nota: {exc}")
            return
        self.tuner.listen.setEnabled(False)
        self.tuner.choose.setEnabled(False)
        self.tuner.set_active(False)
        self.tuner.update_reading(None)
        self.tuner.message('listen', 'Escucha… después te toca a ti',
                           'La medición se reanuda al terminar el sonido.', force=True)
        self.reference_timer.start(1750)

    def finish_reference(self):
        self.mic.latest()
        self.tuner.set_active(self.mic.stream is not None and self.tabs.currentIndex() == 1)
        self.tuner.listen.setEnabled(self.tuner.frequency is not None)
        if self.tuner.confirmed:
            self.tuner.message('return', 'Tu turno · vuelve a tu nota',
                               'Canta una «u» cómoda, sin forzar.' if self.mic.stream else 'Activa el micrófono para empezar.', force=True)

    def change_tab(self, index):
        if self.reference_timer.isActive():
            self.reference_timer.stop()
            sd.stop()
            self.finish_reference()
        if index == 1:
            self.player.pause()
        self.mic.latest()
        self.tuner.set_active(index == 1 and self.mic.stream is not None)

    def closeEvent(self, event):
        self.reference_timer.stop()
        sd.stop()
        self.timer.stop()
        self.mic.stop()
        self.player.stop()
        event.accept()
