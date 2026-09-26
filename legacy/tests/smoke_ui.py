"""Recorrido completo de la interfaz sin micrófono ni sonido, con reloj simulado.

Guarda capturas a 1920×1080 en docs/ para revisar el diseño:
    .\\.venv\\Scripts\\python.exe tests/smoke_ui.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui import theme  # noqa: E402

app = QApplication([])
for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf', 'seguibl.ttf', 'seguisym.ttf', 'segmdl2.ttf'):
    QFontDatabase.addApplicationFont(f'C:/Windows/Fonts/{name}')
app.setStyle('Fusion')
theme._scale = 1.0          # como una pantalla 1080p
app.setStyleSheet(theme.stylesheet())

from game.levels import LEVELS  # noqa: E402
from game.progress import Progress  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

OUTPUT = {'name': 'Salida simulada', 'hostapi': 0, 'default_samplerate': 48000, 'max_output_channels': 2}


def fake_devices(device=None, kind=None):
    return OUTPUT if kind == 'output' or device is not None else []


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


clock = Clock()
SHOTS = ROOT / 'docs'
played = []
tmp = tempfile.TemporaryDirectory()


def shot(name):
    window.practice.track.tick()
    app.processEvents()
    window.grab().save(str(SHOTS / name))


with patch('ui.main_window.sd.query_devices', side_effect=fake_devices), \
        patch('audio.output.sd.query_devices', side_effect=fake_devices), \
        patch('audio.output.sd.query_hostapis', return_value=[{'name': 'MME'}]):
    window = MainWindow(Progress.load(Path(tmp.name) / 'progreso.json'))
assert window.piano is not None, window.piano_error
window.practice.clock = clock
window.practice.track.clock = clock
window.resize(1920, 1080)
window.show()
app.processEvents()

# --- Canciones: la carga del M4A y los controles A/B siguen funcionando.
songs = window.songs_page
deadline = time.monotonic() + 15
while not songs.player.duration() and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(.02)
if songs.songs.count():
    assert songs.player.duration() > 0, songs.player.errorString()
    songs.player.setPosition(10000)
    songs.set_a()
    songs.player.setPosition(10500)
    songs.set_b()
    assert songs.b is None
    songs.player.setPosition(15000)
    songs.set_b()
    assert songs.b == 15000 and songs.loop.isEnabled()
window.show_page(1)
shot('preview-canciones.png')
window.show_page(0)

practice = window.practice
patcher_play = patch('ui.main_window.play_buffer', side_effect=lambda buf, rate, ch, dev: played.append((len(buf), rate)))
patcher_fmt = patch('ui.main_window.device_format', return_value=(48000, 2))
patcher_play.start()
patcher_fmt.start()

# --- Preparar: micro simulado, buscar nota (214 Hz → La2), elegir nivel.
practice.set_mic(True, 'Escuchando (simulado).')
assert practice.find_button.isEnabled() and not practice.start_button.isEnabled()
practice.start_finding()
for f in [214, 215, None, 213, 214, 214]:
    clock.t += .08
    practice.feed(clock.t, .08, f, .03)
assert practice.anchor_midi == 57, practice.anchor_midi     # ajustada a La2 (220 Hz)
assert practice.start_button.isEnabled()
assert not practice.level_buttons[1].isEnabled()           # nivel 2 aún bloqueado
shot('preview-preparar.png')

# --- Ronda del nivel 1: escuchar y cantar.
practice.start_run()
run = practice.run
A = practice.frequency


def advance_to(song_time, semitone=None, cents=0, level=.03, silent=False):
    while run.state == 'running' and run.time(clock.t) < song_time - 1e-9:
        clock.t += .08
        frequency = None if semitone is None else A * 2 ** ((semitone * 100 + cents) / 1200)
        practice.feed(clock.t, .08, frequency, 0 if silent else level)
        practice.tick()


def sing_attempt(attempt, wrong=(), silent=()):
    for i, note in enumerate(n for n in run.sung if n.attempt == attempt):
        advance_to(note.start, silent=True)
        if i in silent:
            advance_to(note.end, silent=True)
        else:
            advance_to(note.end, note.semitone, -160 if i in wrong else 0)


demo0 = [n for n in run.notes if n.demo and n.attempt == 0]
advance_to(demo0[2].start + .3, 0)
assert played, 'el piano debe sonar al empezar la escucha'
assert run.live.kind == 'muted' and sum(n.hit for n in run.sung) == 0
shot('preview-escucha.png')
advance_to(run.sung[0].start - .7, silent=True)
shot('preview-tu-turno.png')
first = [n for n in run.sung if n.attempt == 0]
advance_to(first[1].start + .5, 0)
advance_to(first[1].start + .5, first[1].semitone)
sing_attempt(0)
shot('preview-jugando.png')

# Intento 2: una nota grave (80 %). Intento 3: grave y silencio.
second = [n for n in run.sung if n.attempt == 1]
for i, note in enumerate(second):
    advance_to(note.start, silent=True)
    if i == 2:
        advance_to(note.start + .5, note.semitone, -160)
        shot('preview-grave.png')
    advance_to(note.end, note.semitone, -160 if i == 2 else 0)

practice.toggle_pause()
frozen = run.time(clock.t)
clock.t += 5
practice.feed(clock.t, .08, A, .03)
assert run.time(clock.t) == frozen
shot('preview-pausa.png')
practice.toggle_pause()

sing_attempt(2, wrong=(1, 2), silent=(4,))
advance_to(run.end + .1, silent=True)
assert practice.stack.currentWidget() is practice.results_page
summary = run.summary()
assert [round(x, 2) for x in summary['attempt_scores']] == [1.0, .8, .4], summary
assert summary['passed'] and practice.progress.unlocked == 1
assert practice.next_button.isEnabled()
practice.answer_comfort(True)
shot('preview-resultado.png')

# El progreso se guarda y el nivel 2 queda disponible.
saved = Progress.load(Path(tmp.name) / 'progreso.json')
assert saved.anchor_midi == 57 and saved.unlocked == 1 and saved.notes
practice.next_level()
assert practice.level_index == 1 and practice.level_buttons[1].isEnabled()
assert LEVELS[1].name in practice.level_text.text()

patcher_play.stop()
patcher_fmt.stop()
print('OK: canciones, nota, nivel, escucha, turno, partida, pausa, resultado y progreso.', summary['attempt_scores'])
window.close()
