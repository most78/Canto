"""Niveles de escalas y su colocación dentro de tu rango cómodo.

Los patrones están en semitonos respecto a la primera nota (escala mayor).
Cada nivel cambia una sola cosa respecto al anterior: extensión, velocidad,
tipo de salto o margen de afinación. Son valores provisionales para ajustar
tras probarlos con voz real.
"""
from dataclasses import dataclass

from audio.pitch import hz_to_note


@dataclass(frozen=True)
class Level:
    key: str
    name: str
    description: str
    pattern: tuple
    note_len: float          # segundos por nota
    tolerance: int = 50      # cents

    @property
    def span(self):
        return max(self.pattern) - min(self.pattern)


LEVELS = (
    Level('tres', 'Tres escalones', 'Tres notas seguidas de la escala: sube y vuelve.', (0, 2, 4, 2, 0), .9),
    Level('cinco', 'Cinco hacia arriba', 'Cinco notas de la escala, subiendo.', (0, 2, 4, 5, 7), .85),
    Level('subebaja', 'Sube y baja', 'Cinco notas arriba y de vuelta, más ágil.', (0, 2, 4, 5, 7, 5, 4, 2, 0), .65),
    Level('arpegio', 'Arpegio', 'Saltos de acorde, como do–mi–sol.', (0, 4, 7, 4, 0), .85),
    Level('terceras', 'Terceras', 'Saltos de tercera que van subiendo.', (0, 4, 2, 5, 4, 7), .75),
    Level('precision', 'Más precisión', '«Sube y baja» con margen de ±35 cents.', (0, 2, 4, 5, 7, 5, 4, 2, 0), .65, 35),
    Level('octava', 'Octava', 'La escala completa, subiendo.', (0, 2, 4, 5, 7, 9, 11, 12), .6),
    Level('arpegio8', 'Arpegio de octava', 'Do–mi–sol–do agudo y vuelta, ±35 cents.', (0, 4, 7, 12, 7, 4, 0), .75, 35),
    Level('fino', 'Afinado fino', '«Sube y baja» rápido con ±25 cents.', (0, 2, 4, 5, 7, 5, 4, 2, 0), .5, 25),
)


def midi_frequency(midi):
    return 440 * 2 ** ((midi - 69) / 12)


def note_name(midi):
    """Nombre en español, convención franco-belga (La3 = 440 Hz)."""
    return hz_to_note(midi_frequency(midi)).label


def placements(level, lo, hi):
    """Inicios (semitonos respecto a tu nota) de los 3 intentos dentro de [lo, hi].

    Primer intento lo más cerca posible de tu nota; luego lo más agudo y lo
    más grave que cabe. Así se recorren los bordes de tu rango. Lista vacía si
    el nivel no cabe todavía.
    """
    first = lo - min(level.pattern)
    last = hi - max(level.pattern)
    if last < first:
        return []
    valid = list(range(first, last + 1))
    middle = min(valid, key=lambda s: (abs(s), s))
    return [middle, max(valid), min(valid)]
