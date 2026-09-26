"""Encontrar una nota propia y cómoda a partir de lecturas breves de voz.

Misma regla que el ejercicio anterior (ver docs/diseno-juegos.md): se busca un
grupo de lecturas cercanas entre sí (±100 cents), con al menos 0,3 s de voz
acumulada y 3 bloques. Los silencios no suman y los cortes breves no reinician.
La búsqueda termina sola a los 4 s y explica por qué no encontró nada.
"""
from __future__ import annotations

import math
import statistics
from collections import deque

GROUP_CENTS = 100
NEEDED_SECONDS = .3
NEEDED_BLOCKS = 3
TIME_LIMIT = 4.0
LOW_SIGNAL = .002


class ReferenceFinder:
    def __init__(self):
        self.reset()

    def reset(self):
        self.samples = deque(maxlen=100)
        self.started = None
        self.seconds = 0.0
        self.peak = 0.0
        self.tones = 0
        self.frequency = None
        self.failed = None
        self.progress = 0.0
        self.last_voiced = None

    @property
    def searching(self):
        return self.frequency is None and self.failed is None

    def feed(self, frequency, level, now, duration):
        """Añade un bloque analizado. Devuelve la frecuencia al encontrarla."""
        if not self.searching:
            return self.frequency
        if self.started is None:
            self.started = now
        self.seconds += max(0.0, duration)
        self.peak = max(self.peak, level)
        self.last_voiced = frequency
        if now - self.started >= TIME_LIMIT:
            self.fail()
            return None
        while self.samples and now - self.samples[0][0] > 3:
            self.samples.popleft()
        if frequency is not None:
            self.tones += 1
            self.samples.append((now, frequency, min(.15, max(0.0, duration))))
        best = []
        for _, candidate, _ in self.samples:
            group = [s for s in self.samples
                     if abs(1200 * math.log2(s[1] / candidate)) <= GROUP_CENTS]
            if sum(s[2] for s in group) > sum(s[2] for s in best):
                best = group
        voiced = sum(s[2] for s in best)
        self.progress = min(.95, voiced / NEEDED_SECONDS)
        if len(best) >= NEEDED_BLOCKS and voiced >= NEEDED_SECONDS - 1e-3:
            self.frequency = statistics.median(s[1] for s in best)
            self.progress = 1.0
        return self.frequency

    def fail(self):
        if self.seconds == 0:
            self.failed = ('No han llegado datos del micrófono.',
                           'Elige otro dispositivo y vuelve a activarlo.')
        elif self.peak < LOW_SIGNAL:
            self.failed = ('La señal del micrófono llega muy baja.',
                           'Revisa el dispositivo y su nivel de entrada. No hace falta cantar más fuerte.')
        elif self.tones == 0:
            self.failed = ('Llega sonido, pero no distingo una nota.',
                           'Puede ser ruido de fondo. Prueba otro micrófono o acércate un poco.')
        else:
            self.failed = ('He oído notas, pero no una lo bastante parecida entre sí.',
                           'Descansa y prueba otra «u» tranquila de un segundo.')

    def diagnostic(self):
        return (f'{self.seconds:.1f} s de audio analizado · {self.tones} bloques con nota · '
                f'señal máxima {self.peak:.4f}')
