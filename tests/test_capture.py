import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from audio.capture import Microphone
from audio.pitch import detect_pitch
import numpy as np


class CaptureTests(TestCase):
    def test_block_duration_for_common_device_rates(self):
        for rate in (8000, 16000, 44100, 48000, 96000, 192000):
            with patch('audio.capture.sd.query_devices', return_value={'default_samplerate': rate}), patch('audio.capture.sd.InputStream', return_value=MagicMock()) as stream:
                mic = Microphone()
                mic.start()
                block = stream.call_args.kwargs['blocksize']
                self.assertLessEqual(block / rate, .1)
                tone = .005 * np.sin(2 * np.pi * 180 * np.arange(block) / rate)
                frequency = detect_pitch(tone, rate, min_rms=.002)
                self.assertIsNotNone(frequency)
                self.assertAlmostEqual(frequency, 180, delta=1)
                mic.stop()

    def test_quiet_noise_still_rejected(self):
        frame = np.random.default_rng(4).normal(0, .004, 3840)
        self.assertIsNone(detect_pitch(frame, 48000, min_rms=.002))
