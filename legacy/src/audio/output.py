"""Tono de referencia por la salida adecuada.

Con cascos Bluetooth (probado con Sony WH-1000XM5), al abrir su micrófono la
salida predeterminada por MME se queda muda, pero la misma salida por WASAPI
sigue sonando. Por eso buscamos la versión WASAPI de la salida predeterminada
y usamos su frecuencia de muestreo propia.
"""
import numpy as np
import sounddevice as sd


def _clean(name):
    # MME recorta los nombres a 31 caracteres: comparamos por prefijo.
    return name.strip().lower()


def pick_output_device():
    """Índice del dispositivo de salida a usar (None = el predeterminado)."""
    try:
        return _pick(sd.query_devices(kind='output'), sd.query_hostapis(), sd.query_devices())
    except Exception:
        return None


def _pick(default, apis, devices):
    wasapi = next((i for i, api in enumerate(apis) if 'wasapi' in api['name'].lower()), None)
    if wasapi is None:
        return None
    if default['hostapi'] == wasapi:
        return None
    base = _clean(default['name'])
    for index, info in enumerate(devices):
        if info['hostapi'] == wasapi and info['max_output_channels'] > 0:
            name = _clean(info['name'])
            if name.startswith(base) or base.startswith(name):
                return index
    return None


def make_tone(frequency, seconds, rate, channels=1, volume=.3):
    """Nota tipo piano (síntesis aditiva): misma frecuencia, sonido más agradable.

    Armónicos con ligera inarmonicidad de cuerda, los agudos se apagan antes,
    dos «cuerdas» casi al unísono y un golpe de macillo muy breve.
    """
    t = np.arange(int(rate * seconds)) / rate
    wave = np.zeros_like(t)
    inharmonicity = .00005    # pequeña: la altura percibida no se desplaza
    for k in range(1, 13):
        fk = k * frequency * np.sqrt(1 + inharmonicity * k * k)
        if fk >= rate / 2 * .9:
            break
        amp = (1 / k ** 1.1) * (1.4 if k in (2, 3) and frequency < 200 else 1)
        decay = 1.8 / (1 + .55 * (k - 1))
        for detune in (-.7, .7):     # cents: dos cuerdas casi iguales
            f = fk * 2 ** (detune / 1200)
            wave += amp * np.exp(-t / decay) * np.sin(2 * np.pi * f * t + k)
    hammer = np.random.default_rng(1).normal(0, 1, t.size) * np.exp(-t / .004) * .15
    wave += np.convolve(hammer, np.ones(8) / 8, mode='same')
    envelope = np.minimum(1, t / .004) * np.clip((seconds - t) / .15, 0, 1)
    wave *= envelope
    wave *= volume / (np.max(np.abs(wave)) or 1)
    tone = wave.astype('float32')
    return np.column_stack([tone] * channels) if channels > 1 else tone


def device_format(device=None):
    """(frecuencia de muestreo, canales) de una salida."""
    info = sd.query_devices(device, 'output')
    return int(info['default_samplerate']), min(2, int(info['max_output_channels'])) or 1


def play_buffer(mono, rate, channels, device=None):
    """Reproduce un buffer mono sin bloquear (lo duplica si la salida es estéreo)."""
    data = np.column_stack([mono] * channels) if channels > 1 else mono
    sd.play(np.ascontiguousarray(data, np.float32), rate, device=device)


def synth_phrase(notes, rate):
    """Respaldo sin muestras de piano: [(desfase_s, frecuencia, duración_s)] → buffer."""
    end = max(start + seconds for start, _, seconds in notes)
    out = np.zeros(int(rate * end) + 1, np.float32)
    for start, frequency, seconds in notes:
        x = make_tone(frequency, seconds, rate)
        i = int(rate * start)
        out[i:i + len(x)] += x[:len(out) - i]
    return out
