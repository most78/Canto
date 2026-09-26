import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from audio import output  # noqa: E402

APIS = [{'name': 'MME'}, {'name': 'Windows DirectSound'}, {'name': 'Windows WASAPI'}]
DEVICES = [
    {'name': 'Auriculares con micrófono (WH-1', 'hostapi': 0, 'max_output_channels': 0},
    {'name': 'Auriculares (WH-1000XM5)', 'hostapi': 0, 'max_output_channels': 2},
    {'name': 'Auriculares (WH-1000XM5)', 'hostapi': 1, 'max_output_channels': 2},
    {'name': 'Realtek Digital Output (Realtek USB Audio)', 'hostapi': 2, 'max_output_channels': 2},
    {'name': 'Auriculares (WH-1000XM5)', 'hostapi': 2, 'max_output_channels': 2},
]


def fake_query(device=None, kind=None):
    if kind == 'output' and device is None:
        return DEVICES[1]
    return DEVICES if device is None else DEVICES[device]


class OutputTests(unittest.TestCase):
    def test_prefers_wasapi_twin_of_default_output(self):
        with patch.object(output.sd, 'query_devices', side_effect=fake_query), \
                patch.object(output.sd, 'query_hostapis', return_value=APIS):
            self.assertEqual(output.pick_output_device(), 4)

    def test_falls_back_to_default_without_twin(self):
        devices = DEVICES[:4]
        with patch.object(output.sd, 'query_devices',
                          side_effect=lambda device=None, kind=None: DEVICES[1] if kind else devices), \
                patch.object(output.sd, 'query_hostapis', return_value=APIS):
            self.assertIsNone(output.pick_output_device())

    def test_tone_shape(self):
        self.assertEqual(output.make_tone(220, 1, 48000, 2).shape, (48000, 2))
        self.assertEqual(output.make_tone(220, 1, 16000).shape, (16000,))


if __name__ == '__main__':
    unittest.main()
