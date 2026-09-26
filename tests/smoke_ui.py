"""Recorrido completo de la interfaz sin micrófono ni sonido, con reloj simulado.

Guarda capturas a 1920×1080 en docs/ para revisar el diseño:
    .\\.venv\\Scripts\\python.exe tests/smoke_ui.py
"""
import os
import sys
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
for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf', 'seguibl.ttf', 'seguiemj.ttf', 'seguisym.ttf'):
    QFontDatabase.addApplicationFont(f'C:/Windows/Fonts/{name}')
app.setStyle('Fusion')
theme._scale = 1.0          # como una pantalla 1080p
app.setStyleSheet(theme.stylesheet())

from ui.main_window import MainWindow  # noqa: E402


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


clock = Clock()
SHOTS = ROOT / 'docs'


def shot(name):
    window.practice.track.tick()
    app.processEvents()
    window.grab().save(str(SHOTS / name))


with patch('ui.main_window.sd.query_devices', return_value=[]):
    window = MainWindow()
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

# --- Preparar: micro simulado, buscar nota, confirmar.
practice = window.practice
tones = []
practice.tone_requested.connect(lambda f, s: tones.append((round(f), s)))
practice.set_mic(True, 'Escuchando (simulado).')
assert practice.find_button.isEnabled() and not practice.start_button.isEnabled()
practice.start_finding()
for i, f in enumerate([220, 221, None, 219, 220, 220]):
    clock.t += .08
    practice.feed(clock.t, .08, f, .03)
assert practice.frequency is not None and abs(practice.frequency - 220) < 2
assert practice.start_button.isEnabled()
shot('preview-preparar.png')

# --- Jugar: la referencia inicial suena y no puntúa.
practice.start_run()
run = practice.run
assert run.target == practice.frequency


def advance_to(song_time, frequency=None, level=.03):
    while run.state == 'running' and run.time(clock.t) < song_time - 1e-9:
        clock.t += .08
        practice.feed(clock.t, .08, frequency, level)
        practice.tick()


advance_to(1.0, practice.frequency)
assert tones and tones[0][0] == 220, tones
assert run.live.kind == 'muted' and sum(n.hit for n in run.notes) == 0
advance_to(run.notes[0].start - .9)
shot('preview-cuenta-atras.png')

# Nota 1 acertada, nota 2 grave, nota 3 sin señal clara.
advance_to(run.notes[0].end + .5, 220)
advance_to(run.notes[1].start)
advance_to(run.notes[1].start + .9, 220 * 2 ** (-160 / 1200))
shot('preview-grave.png')
advance_to(run.notes[1].end + .5, 220 * 2 ** (-160 / 1200))
advance_to(run.notes[2].start)
advance_to(run.notes[2].end + .5, None, .2)
advance_to(run.notes[3].start)
advance_to(run.notes[3].start + 1.2, 221)
shot('preview-jugando.png')
assert run.notes[0].judgement == 'perfect'
assert run.notes[1].judgement == 'miss_low'
assert run.notes[2].judgement == 'unclear'

# Pausa: el tiempo se congela y no suma.
practice.toggle_pause()
frozen = run.time(clock.t)
clock.t += 5
practice.feed(clock.t, .08, 221, .03)
assert run.time(clock.t) == frozen
shot('preview-pausa.png')
practice.toggle_pause()

advance_to(run.end + .1, None, 0)
assert practice.stack.currentWidget() is practice.results_page
summary = run.summary()
assert summary['hits'] == 2 and summary['misses'] == 1 and summary['unclear'] == 1, summary
shot('preview-resultado.png')

print('OK: canciones, preparar, cuenta atrás, partida, pausa y resultado.', summary)
window.close()
