"""Detección de pitch (YIN) y conversión de frecuencia a nota musical.

Este módulo no sabe nada de micrófonos ni de interfaz: recibe un bloque de
muestras (array de numpy) y devuelve números. Así se puede probar con señales
sintéticas, sin hardware.

Referencia del algoritmo: de Cheveigné & Kawahara (2002),
"YIN, a fundamental frequency estimator for speech and music".
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# Rango de búsqueda: cubre desde voces graves hasta sopranos agudas.
DEFAULT_FMIN = 70.0     # Hz
DEFAULT_FMAX = 1100.0   # Hz

# Umbral de YIN: cuanto más bajo, más exigente para aceptar que hay tono.
DEFAULT_THRESHOLD = 0.15

# Por debajo de este volumen (RMS) consideramos que hay silencio.
DEFAULT_MIN_RMS = 0.01

# Nomenclatura española. Octavas en convención franco-belga (la habitual en
# España): el La de 440 Hz es La3 y el Do central es Do3.
NOTE_NAMES = ("Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si")
_MIDI_OCTAVE_OFFSET = 2  # MIDI 69 -> 69 // 12 - 2 = 3 -> La3


# ---------------------------------------------------------------------------
# 1) Frecuencia fundamental
# ---------------------------------------------------------------------------

def rms(frame: np.ndarray) -> float:
    """Volumen medio (raíz cuadrática media) del bloque."""
    x = np.asarray(frame, dtype=np.float64)
    return float(np.sqrt(np.mean(x * x))) if x.size else 0.0


def yin(
    frame: np.ndarray,
    sample_rate: int,
    fmin: float = DEFAULT_FMIN,
    fmax: float = DEFAULT_FMAX,
    threshold: float = DEFAULT_THRESHOLD,
) -> float | None:
    """Estima la frecuencia fundamental (Hz) de un bloque de audio mono.

    Devuelve None si no encuentra un tono claro (ruido, consonantes, etc.).

    Idea: una señal periódica se parece a sí misma desplazada un periodo.
    Probamos desplazamientos (tau) y buscamos el primero en el que la señal
    y su copia desplazada casi coinciden.
    """
    x = np.asarray(frame, dtype=np.float64)
    x = x - x.mean()

    tau_min = max(2, int(sample_rate / fmax))   # periodo más corto que buscamos
    tau_max = int(sample_rate / fmin)           # periodo más largo que buscamos
    window = len(x) - tau_max                   # trozo que comparamos
    if window < tau_max:
        raise ValueError(
            f"Bloque demasiado corto ({len(x)} muestras) para fmin={fmin} Hz "
            f"a {sample_rate} Hz; necesita al menos {2 * tau_max}."
        )

    # Paso 1 — función diferencia:
    #   d(tau) = suma de (x[j] - x[j + tau])^2  para j en la ventana
    # Se desarrolla como energía(0) + energía(tau) - 2 * correlación(tau),
    # y la correlación se calcula con FFT para que sea rápido.
    squares_cumsum = np.concatenate(([0.0], np.cumsum(x * x)))
    energy = squares_cumsum[window:window + tau_max + 1] - squares_cumsum[:tau_max + 1]

    n_fft = 1 << int(math.ceil(math.log2(len(x) + window)))
    spectrum = np.fft.rfft(x, n_fft) * np.conj(np.fft.rfft(x[:window], n_fft))
    correlation = np.fft.irfft(spectrum, n_fft)[:tau_max + 1]

    diff = np.maximum(energy[0] + energy - 2.0 * correlation, 0.0)
    diff[0] = 0.0

    # Paso 2 — normalización acumulada (CMNDF): divide cada valor por la media
    # de los anteriores. Evita elegir tau=0 y reduce errores de octava.
    cmndf = np.ones_like(diff)
    running_sum = np.cumsum(diff[1:])
    taus = np.arange(1, tau_max + 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cmndf[1:] = np.where(running_sum > 0, diff[1:] * taus / running_sum, 1.0)

    # Paso 3 — primer tau por debajo del umbral, y bajamos hasta su mínimo local.
    below = np.nonzero(cmndf[tau_min:] < threshold)[0]
    if below.size == 0:
        return None
    tau = tau_min + int(below[0])
    while tau + 1 <= tau_max and cmndf[tau + 1] < cmndf[tau]:
        tau += 1

    # Paso 4 — interpolación parabólica para afinar por debajo de una muestra
    # (sin esto el error llega a varios cents en notas agudas).
    shift = 0.0
    if 0 < tau < tau_max:
        a, b, c = diff[tau - 1], diff[tau], diff[tau + 1]
        denom = a - 2.0 * b + c
        if denom > 0:
            shift = float(np.clip(0.5 * (a - c) / denom, -1.0, 1.0))

    return sample_rate / (tau + shift)


def detect_pitch(
    frame: np.ndarray,
    sample_rate: int,
    min_rms: float = DEFAULT_MIN_RMS,
    **yin_kwargs,
) -> float | None:
    """Puerta de silencio + YIN. Es la función que usará la app."""
    if rms(frame) < min_rms:
        return None
    return yin(frame, sample_rate, **yin_kwargs)


# ---------------------------------------------------------------------------
# 2) Frecuencia -> nota + cents
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NoteReading:
    frequency: float  # Hz detectados
    midi: int         # número de nota MIDI más cercana (69 = La3 = 440 Hz)
    name: str         # "La", "Do#", ...
    octave: int       # convención franco-belga
    cents: float      # -50..+50. Negativo = bajo (plano), positivo = alto

    @property
    def label(self) -> str:
        return f"{self.name}{self.octave}"


def hz_to_note(frequency: float, a4: float = 440.0) -> NoteReading:
    """Convierte Hz en la nota más cercana y cuánto te desvías de ella.

    Un semitono = 100 cents; una octava = 1200 cents.
    """
    if frequency <= 0:
        raise ValueError("La frecuencia debe ser positiva")
    midi_float = 69 + 12 * math.log2(frequency / a4)
    midi = int(math.floor(midi_float + 0.5))
    cents = (midi_float - midi) * 100
    return NoteReading(
        frequency=frequency,
        midi=midi,
        name=NOTE_NAMES[midi % 12],
        octave=midi // 12 - _MIDI_OCTAVE_OFFSET,
        cents=cents,
    )
