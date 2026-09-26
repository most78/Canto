import os
from pathlib import Path
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from ui.firefly import FireflyWidget

app = QApplication.instance() or QApplication([])


class FireflyTests(unittest.TestCase):
    def make_game(self):
        game = FireflyWidget()
        self.addCleanup(game.close)
        game.set_active(True)
        game.begin()
        for i in range(10):
            game.update_reading(220, now=i * .1)
        self.assertEqual(game.frequency, 220)
        return game

    def test_requires_comfort_confirmation(self):
        game = self.make_game()
        for i in range(40):
            game.update_reading(220, now=1 + i * .1)
        self.assertEqual(game.elapsed, 0)

    def test_silence_octave_and_pause_keep_progress(self):
        game = self.make_game()
        game.confirm_note()
        game.update_reading(220, now=2)
        game.update_reading(220, now=2.1)
        saved = game.elapsed
        game.update_reading(None, now=2.2)
        game.update_reading(440, now=2.3)
        game.set_active(False)
        game.update_reading(220, now=2.4)
        self.assertEqual(game.elapsed, saved)
        self.assertEqual(game.frequency, 220)

    def test_only_new_audio_time_counts(self):
        for step in (.05, .1):
            game = self.make_game()
            game.confirm_note()
            for i in range(round(3 / step) + 2):
                game.update_reading(220, now=2 + i * step, duration=step)
            self.assertEqual(game.elapsed, 3)
        game = self.make_game()
        game.confirm_note()
        game.update_reading(220, now=2)
        game.update_reading(220, now=2)
        game.update_reading(220, now=20)
        self.assertEqual(game.elapsed, 0)
        game.update_reading(220, now=20.2, duration=.05)
        self.assertAlmostEqual(game.elapsed, .05)

    def test_confirmation_survives_silence(self):
        game = self.make_game()
        text = game.feedback.text()
        for i in range(30):
            game.update_reading(None, now=2 + i * .1)
        self.assertEqual(game.feedback.text(), text)
        self.assertTrue(game.confirm.isEnabled())

    def test_messages_require_persistence_and_reading_time(self):
        game = self.make_game()
        game.message('initial', 'Lee esto', 'Sin cambios rápidos', now=0, force=True)
        for i in range(20):
            game.message('low' if i % 2 else 'high', 'No debe aparecer', '', now=i * .1)
        self.assertEqual(game.feedback.text(), 'Lee esto')
        game.message('low', 'Más agudo', 'Con calma', now=2)
        game.message('low', 'Más agudo', 'Con calma', now=2.5)
        self.assertEqual(game.feedback.text(), 'Más agudo')
        game.message('high', 'Más grave', '', now=2.6)
        game.message('high', 'Más grave', '', now=3.1)
        self.assertEqual(game.feedback.text(), 'Más agudo')
        game.message('high', 'Más grave', '', now=4.6)
        self.assertEqual(game.feedback.text(), 'Más grave')

    def test_animation_moves_without_awarding_light(self):
        game = self.make_game()
        phase = game.scene.phase
        for _ in range(30):
            game.scene.animate()
        self.assertGreater(game.scene.phase, phase)
        self.assertEqual(game.elapsed, 0)
        self.assertEqual(game.scene.progress, 0)

    def test_visible_scene_runs_animation_timer(self):
        game = self.make_game()
        game.show()
        app.processEvents()
        phase = game.scene.phase
        QTest.qWait(150)
        self.assertGreater(game.scene.phase, phase)
        self.assertEqual(game.elapsed, 0)
        game.hide()
        self.assertFalse(game.scene.animation.isActive())

    def test_calibration_tolerates_one_short_gap(self):
        game = FireflyWidget()
        self.addCleanup(game.close)
        game.set_active(True)
        game.begin()
        for i in range(8):
            game.update_reading(None if i == 3 else 220, now=i * .1)
        self.assertEqual(game.frequency, 220)

    def test_capture_accepts_short_separated_sounds(self):
        game = FireflyWidget()
        self.addCleanup(game.close)
        game.set_active(True)
        game.begin()
        for i, f in enumerate([220, 222, None, None, None, None, 219, 220]):
            game.update_reading(f, volume=.005, now=i * .1, duration=.08)
        self.assertIsNotNone(game.frequency)
        self.assertFalse(game.calibrating)

    def test_capture_time_is_independent_of_callback_rate(self):
        for duration in (.04, .08, .128, .256):
            game = FireflyWidget()
            self.addCleanup(game.close)
            game.set_active(True)
            game.begin()
            for i in range(20):
                game.update_reading(180, now=i * duration, duration=duration)
            self.assertEqual(game.frequency, 180)

    def test_capture_stops_and_explains_failure(self):
        for volume, reason in [(0, 'demasiado baja'), (.05, 'Llega sonido')]:
            game = FireflyWidget()
            self.addCleanup(game.close)
            game.set_active(True)
            game.begin()
            for i in range(42):
                game.update_reading(None, volume=volume, now=i * .1)
            self.assertFalse(game.calibrating)
            self.assertIsNone(game.frequency)
            self.assertIn(reason, game.detail.text())
        game.begin()
        game.capture_failed()
        self.assertIn('No han llegado datos', game.detail.text())
