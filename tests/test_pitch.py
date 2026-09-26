"""Tests de src/audio/pitch.py con señales sintéticas (sin micrófono).

Ejecutar desde la raíz del repo:
    python -m unittest discover -s tests -v
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio.pitch import detect_pitch, hz_to_note  # noqa: E402

SR = 44100
BLOCK = 2048


def sine(freq, n=BLOCK, amp=0.5):
    t = np.arange(n) / SR
    return amp * np.sin(2 * np.pi * freq * t)


def voice_like(freq, n=BLOCK):
    """Fundamental + armónicos decrecientes: más parecido a una voz que un seno."""
    t = np.arange(n) / SR
    return sum((0.5 / k) * np.sin(2 * np.pi * k * freq * t) for k in range(1, 8))


def cents_between(f_detected, f_true):
    return 1200 * math.log2(f_detected / f_true)


class TestHzToNote(unittest.TestCase):
    def test_la_440(self):
        r = hz_to_note(440.0)
        self.assertEqual(r.label, "La3")
        self.assertAlmostEqual(r.cents, 0.0, places=6)

    def test_do_central(self):
        r = hz_to_note(261.6256)
        self.assertEqual(r.label, "Do3")
        self.assertAlmostEqual(r.cents, 0.0, delta=0.1)

    def test_agudo_y_plano(self):
        self.assertAlmostEqual(hz_to_note(440 * 2 ** (30 / 1200)).cents, 30.0, places=6)
        r = hz_to_note(440 * 2 ** (-30 / 1200))
        self.assertEqual(r.label, "La3")
        self.assertAlmostEqual(r.cents, -30.0, places=6)

    def test_redondea_a_la_nota_vecina(self):
        # 70 cents por encima de La3 está más cerca de La#3 (-30 cents)
        r = hz_to_note(440 * 2 ** (70 / 1200))
        self.assertEqual(r.label, "La#3")
        self.assertAlmostEqual(r.cents, -30.0, places=6)

    def test_cambio_de_octava_en_si_do(self):
        self.assertEqual(hz_to_note(246.94).label, "Si2")
        self.assertEqual(hz_to_note(261.63).label, "Do3")

    def test_frecuencia_invalida(self):
        with self.assertRaises(ValueError):
            hz_to_note(0)


class TestDetectPitch(unittest.TestCase):
    # Rango vocal típico, de grave a agudo
    FREQS = [82.41, 110.0, 196.0, 261.63, 440.0, 659.26, 987.77]

    def test_senos_puros(self):
        for f in self.FREQS:
            with self.subTest(f=f):
                detected = detect_pitch(sine(f), SR)
                self.assertIsNotNone(detected)
                self.assertLess(abs(cents_between(detected, f)), 3)

    def test_senal_con_armonicos_sin_error_de_octava(self):
        for f in self.FREQS:
            with self.subTest(f=f):
                detected = detect_pitch(voice_like(f), SR)
                self.assertIsNotNone(detected)
                self.assertLess(abs(cents_between(detected, f)), 3)

    def test_silencio(self):
        self.assertIsNone(detect_pitch(np.zeros(BLOCK), SR))

    def test_ruido_blanco(self):
        rng = np.random.default_rng(0)
        self.assertIsNone(detect_pitch(rng.normal(0, 0.3, BLOCK), SR))

    def test_bloque_demasiado_corto(self):
        with self.assertRaises(ValueError):
            detect_pitch(sine(440, n=512), SR)


if __name__ == "__main__":
    unittest.main()
