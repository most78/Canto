"""Piano muestreado (Salamander Grand Piano, CC-BY; ver assets/piano/LEEME.md).

Descodifica los MP3 con QAudioDecoder, que ya incluye PySide6, y reafina la
muestra más cercana (≤ ±1,5 semitonos) a la frecuencia exacta pedida. Así la
referencia suena a piano de verdad y coincide con tu nota aunque no caiga
justo en un semitono.
"""
import math
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat

FOLDER = Path(__file__).resolve().parents[2] / 'assets' / 'piano'
_NAMES = {'C': 0, 'Cs': 1, 'Ds': 3, 'E': 4, 'F': 5, 'Fs': 6, 'G': 7, 'A': 9}
RELEASE = .25        # apagado suave al soltar la tecla


def midi_of(name):
    """'Ds3' → 51 (notación científica inglesa, A4 = 69)."""
    letter, octave = name[:-1], int(name[-1])
    return 12 * (octave + 1) + _NAMES[letter]


def midi_float(frequency):
    return 69 + 12 * math.log2(frequency / 440)


def decode(path, rate):
    """MP3 → float32 mono a `rate` Hz. Necesita una QApplication creada."""
    decoder = QAudioDecoder()
    wanted = QAudioFormat()
    wanted.setSampleRate(rate)
    wanted.setChannelCount(1)
    wanted.setSampleFormat(QAudioFormat.Float)
    decoder.setAudioFormat(wanted)
    chunks = []
    loop = QEventLoop()
    state = {'rate': rate, 'error': None}

    def ready():
        buffer = decoder.read()
        fmt = buffer.format()
        state['rate'] = fmt.sampleRate()
        data = bytes(buffer.constData())
        kind = fmt.sampleFormat()
        if kind == QAudioFormat.Float:
            x = np.frombuffer(data, np.float32)
        elif kind == QAudioFormat.Int16:
            x = np.frombuffer(data, np.int16) / 32768
        elif kind == QAudioFormat.Int32:
            x = np.frombuffer(data, np.int32) / 2 ** 31
        else:
            x = (np.frombuffer(data, np.uint8).astype(np.float32) - 128) / 128
        channels = max(1, fmt.channelCount())
        if channels > 1:
            x = x[:len(x) // channels * channels].reshape(-1, channels).mean(axis=1)
        chunks.append(np.asarray(x, np.float32))

    def failed(*_):
        state['error'] = decoder.errorString()
        loop.quit()

    decoder.bufferReady.connect(ready)
    decoder.finished.connect(loop.quit)
    decoder.error.connect(failed)
    decoder.setSource(QUrl.fromLocalFile(str(path)))
    decoder.start()
    QTimer.singleShot(10000, loop.quit)
    loop.exec()
    decoder.stop()
    if state['error'] or not chunks:
        raise RuntimeError(f'No se pudo leer {path.name}: {state["error"] or "sin datos"}')
    x = np.concatenate(chunks)
    if state['rate'] != rate:
        positions = np.arange(int(len(x) * rate / state['rate'])) * state['rate'] / rate
        x = np.interp(positions, np.arange(len(x)), x).astype(np.float32)
    start = int(np.argmax(np.abs(x) > .01 * np.max(np.abs(x))))   # sin silencio inicial
    return x[max(0, start - int(rate * .002)):]


class Piano:
    def __init__(self, rate=48000, folder=FOLDER):
        self.rate = rate
        self.samples = {}
        self.tuning = {}     # frecuencia real medida de cada muestra
        for path in sorted(Path(folder).glob('*.mp3')):
            key = midi_of(path.stem)
            self.samples[key] = decode(path, rate)
            self.tuning[key] = self.measure(self.samples[key], key)
        if not self.samples:
            raise RuntimeError(f'No hay muestras de piano en {folder}')

    def measure(self, sample, key):
        """Calibra la muestra con el mismo YIN que evalúa la voz."""
        from audio.pitch import detect_pitch
        nominal = 440 * 2 ** ((key - 69) / 12)
        block = int(self.rate * .08)
        readings = []
        for start in np.arange(.15, .9, .08):
            i = int(self.rate * start)
            f = detect_pitch(sample[i:i + block], self.rate)
            if f and abs(1200 * math.log2(f / nominal)) < 30:
                readings.append(f)
        return float(np.median(readings)) if readings else nominal

    def note(self, frequency, seconds, velocity=.8):
        """Una nota reafinada: suena `seconds` y luego se apaga en RELEASE s."""
        m = midi_float(frequency)
        key = min(self.samples, key=lambda k: abs(k - m))
        sample = self.samples[key]
        ratio = frequency / self.tuning[key]
        n = int(self.rate * (seconds + RELEASE))
        positions = np.arange(n) * ratio
        positions = positions[positions < len(sample) - 1]
        x = np.interp(positions, np.arange(len(sample)), sample)
        t = np.arange(len(x)) / self.rate
        x *= np.clip(1 - (t - seconds) / RELEASE, 0, 1)
        return (velocity * x).astype(np.float32)

    def phrase(self, notes, volume=.5):
        """notes = [(inicio_s, frecuencia, duración_s)] → un único buffer mono."""
        end = max(start + seconds for start, _, seconds in notes) + RELEASE
        out = np.zeros(int(self.rate * end) + 1, np.float32)
        for start, frequency, seconds in notes:
            x = self.note(frequency, seconds)
            i = int(self.rate * start)
            out[i:i + len(x)] += x[:len(out) - i]
        peak = float(np.max(np.abs(out))) or 1
        return out * (volume / peak)
