"""Comprobación de carga multimedia y controles, sin activar el micrófono."""
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from main import STYLE
from ui.main_window import MainWindow

app = QApplication([])
QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeuib.ttf")
app.setStyle("Fusion")
app.setStyleSheet(STYLE)
with patch("ui.main_window.sd.query_devices", return_value=[]):
    window = MainWindow()
window.show()
deadline = time.monotonic() + 15
while not window.player.duration() and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.02)
assert window.player.duration() > 0, window.player.errorString()
assert window.songs.count() >= 1
window.player.setPosition(10000)
window.set_a()
window.player.setPosition(10500)
window.set_b()
assert window.b is None
window.player.setPosition(15000)
window.set_b()
assert window.b == 15000 and window.loop.isEnabled()
window.select_song()
assert window.b is None and not window.loop.isEnabled()
assert window.tabs.count() == 2
window.tabs.setCurrentIndex(1)
window.tuner.set_active(True)
window.tuner.begin()
for i in range(12):
    window.tuner.update_reading(220, now=i * .1)
assert window.tuner.frequency == 220
assert not window.tuner.confirmed
window.tuner.confirm_note()
window.tuner.update_reading(220, now=2)
window.tuner.update_reading(220, now=2.1)
assert window.tuner.elapsed > 0
saved = window.tuner.elapsed
window.tuner.update_reading(None, now=2.2)
assert window.tuner.elapsed == saved
window.tuner.update_reading(440, now=2.3)
assert window.tuner.elapsed == saved
with patch("ui.main_window.sd.play") as playback:
    window.play_reference(220)
    assert playback.call_args.args[0].shape == (66150,)
    assert not window.tuner.active
    window.reference_timer.stop()
    window.finish_reference()
window.tuner.set_active(True)
window.tuner.begin()
window.status.setText("Audio y micrófono locales. Tu voz no se graba ni se envía.")
app.processEvents()
window.grab().save(str(Path(__file__).resolve().parents[1] / "docs" / "app-preview.png"))
print("OK: audio cargado, controles A/B y afinador. Duración comprobada.")
window.close()
