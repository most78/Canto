"""Puntuación de «Pista de voz»: una nota propia repetida en una secuencia corta.

Reglas (ver docs/diseno-juegos.md):
- El objetivo es fijo durante todo el intento.
- Sólo puntúa audio nuevo: cada instante de audio se cuenta una vez, y sólo la
  parte que cae dentro de la ventana de una nota. Cantar en los descansos no suma.
- Silencio, sonido sin nota clara y bloques antiguos (anteriores a una pausa) no
  suman. Tampoco el audio que coincide con la referencia reproducida por la app.
- El volumen sólo separa silencio de sonido; nunca multiplica puntos.
- La nota dura lo que dice la secuencia: aguantar más no suma más.

El tiempo del juego («song time») avanza con el reloj monotónico y se congela en
pausa. Cada bloque de micrófono llega con la marca monotónica de cuando terminó.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

TOLERANCE_CENTS = 50        # zona de acierto alrededor del objetivo fijo
PLAUSIBLE_CENTS = 1900      # más lejos que esto lo tratamos como lectura dudosa
SILENCE_RMS = .002          # misma puerta de silencio que la captura
REACTION = .25              # margen para encontrar la nota al empezar cada barra
JUDGE_DELAY = .35           # espera a bloques tardíos antes de juzgar una nota
HINT_PERSISTENCE = .4       # una indicación de dirección debe mantenerse 400 ms
STALE_AFTER = .3            # sin bloques nuevos en este tiempo = no hay lectura

DEFAULT_DURATIONS = (1.0, 1.5, 1.5, 2.0, 1.5)
DEFAULT_LEAD = 4.5          # escuchar la referencia y cuenta atrás
DEFAULT_REST = 4.0          # descanso para respirar entre notas
CUE_LENGTH = 1.0            # duración del tono de referencia
MUTE_TAIL = .35             # eco y latencia tras el tono

HITS = ('perfect', 'great', 'ok')
JUDGEMENT_TEXT = {
    'perfect': '¡Perfecta!',
    'great': '¡Muy bien!',
    'ok': 'Bien',
    'miss_low': 'Un poco grave',
    'miss_high': 'Un poco aguda',
    'unclear': 'No te oí claro',
    'silent': 'Sin cantar',
}


def cents_between(frequency, target):
    return 1200 * math.log2(frequency / target)


def weighted_median(pairs):
    """Mediana de cents ponderada por segundos medidos; None sin datos."""
    pairs = sorted((c, w) for w, c in pairs if w > 0)
    total = sum(w for _, w in pairs)
    if total <= 0:
        return None
    acc = 0.0
    for c, w in pairs:
        acc += w
        if acc >= total / 2:
            return c


@dataclass
class Note:
    start: float
    end: float
    hit: float = 0.0
    low: float = 0.0
    high: float = 0.0
    unclear: float = 0.0
    cents: list = field(default_factory=list)   # (segundos, cents) medidos
    judgement: str | None = None

    @property
    def duration(self):
        return self.end - self.start

    @property
    def ratio(self):
        """Fracción acertada de la nota, descontando el margen de reacción."""
        return min(1.0, self.hit / max(.1, self.duration - REACTION))

    @property
    def measured(self):
        return self.hit + self.low + self.high

    @property
    def points(self):
        return round(1000 * self.ratio) if self.judgement in HITS else 0

    def judge(self):
        d = self.duration
        if self.ratio >= .75:
            self.judgement = 'perfect'
        elif self.ratio >= .45:
            self.judgement = 'great'
        elif self.ratio >= .15:
            self.judgement = 'ok'
        elif self.measured >= .25 * d:
            self.judgement = 'miss_low' if self.low >= self.high else 'miss_high'
        elif self.unclear >= .25 * d:
            self.judgement = 'unclear'
        else:
            self.judgement = 'silent'
        return self.judgement


@dataclass(frozen=True)
class Reading:
    time: float          # song time al final del bloque
    kind: str            # hit | low | high | unclear | silence | muted
    cents: float | None


def classify(frequency, level, target, tolerance=TOLERANCE_CENTS):
    if level < SILENCE_RMS:
        return 'silence', None
    if frequency is None or frequency <= 0:
        return 'unclear', None
    cents = cents_between(frequency, target)
    if abs(cents) > PLAUSIBLE_CENTS:
        return 'unclear', None
    if abs(cents) <= tolerance:
        return 'hit', cents
    return ('low' if cents < 0 else 'high'), cents


class NoteRun:
    def __init__(self, target, durations=DEFAULT_DURATIONS, lead=DEFAULT_LEAD,
                 rest=DEFAULT_REST, tolerance=TOLERANCE_CENTS, guide=False):
        self.target = float(target)
        self.tolerance = tolerance
        self.notes = []
        t = lead
        for d in durations:
            self.notes.append(Note(t, t + d))
            t += d + rest
        self.end = self.notes[-1].end + 1.5
        # Referencia: siempre al principio; con guía, también antes de cada nota.
        self.cues = [.4]
        if guide:
            self.cues += [n.start - 2.6 for n in self.notes[1:]]
        self.state = 'ready'
        self.origin = None
        self.paused_time = 0.0
        self.counted_until = 0.0
        self.muted = []
        self.trail = deque(maxlen=240)
        self.live = None
        self.hint_kind = None
        self.hint_since = 0.0
        self.streak = 0
        self.best_streak = 0
        self.events = []

    # --- reloj -----------------------------------------------------------
    def start(self, now):
        self.origin = now
        self.state = 'running'

    def time(self, now):
        if self.state in ('ready',):
            return 0.0
        if self.state in ('paused', 'finished', 'stopped'):
            return self.paused_time
        return now - self.origin

    def pause(self, now):
        if self.state == 'running':
            self.paused_time = self.time(now)
            self.state = 'paused'
            self.live = None

    def resume(self, now):
        if self.state == 'paused':
            self.origin = now - self.paused_time
            # Todo lo capturado antes de reanudar queda descartado.
            self.counted_until = max(self.counted_until, self.paused_time)
            self.state = 'running'

    def stop(self, now):
        if self.state in ('running', 'paused'):
            self.paused_time = self.time(now)
            self.state = 'stopped'

    def mute(self, start, end):
        """No puntuar audio entre esos instantes de juego (referencia sonando)."""
        self.muted.append((start, end + MUTE_TAIL))

    def due_cues(self, now):
        """Devuelve y consume las referencias que toca reproducir."""
        if self.state != 'running':
            return []
        t = self.time(now)
        due = [c for c in self.cues if c <= t]
        self.cues = [c for c in self.cues if c > t]
        for c in due:
            self.mute(c, c + CUE_LENGTH)
        return due

    # --- audio -----------------------------------------------------------
    def feed(self, stamp, duration, frequency, level):
        """Procesa un bloque que terminó en el instante monotónico `stamp`."""
        if self.state != 'running':
            return None
        end = self.time(stamp)
        begin = max(end - max(0.0, duration), self.counted_until)
        if end <= begin:
            return None          # bloque antiguo o repetido
        self.counted_until = end
        if any(begin < m_end and end > m_start for m_start, m_end in self.muted):
            reading = Reading(end, 'muted', None)
        else:
            kind, cents = classify(frequency, level, self.target, self.tolerance)
            reading = Reading(end, kind, cents)
            for note in self.notes:
                if note.judgement is not None:
                    continue
                overlap = min(end, note.end) - max(begin, note.start)
                if overlap <= 1e-6:
                    continue
                if kind in ('hit', 'low', 'high'):
                    setattr(note, kind, getattr(note, kind) + overlap)
                    note.cents.append((overlap, cents))
                elif kind == 'unclear':
                    note.unclear += overlap
        self.live = reading
        self.trail.append(reading)
        if reading.kind != self.hint_kind:
            self.hint_kind = reading.kind
            self.hint_since = end
        return reading

    def update(self, now):
        """Juzga las notas cuya ventana ha terminado. Devuelve eventos nuevos."""
        if self.state != 'running':
            return []
        t = self.time(now)
        new = []
        for i, note in enumerate(self.notes):
            if note.judgement is None and t >= note.end + JUDGE_DELAY:
                result = note.judge()
                if result in HITS:
                    self.streak += 1
                    self.best_streak = max(self.best_streak, self.streak)
                elif result.startswith('miss'):
                    self.streak = 0
                new.append((i, result))
        if t >= self.end:
            self.paused_time = t
            self.state = 'finished'
        self.events += new
        return new

    # --- lectura para la interfaz ---------------------------------------
    def current_reading(self, now):
        """Última lectura si es reciente; None si no hay datos nuevos."""
        if self.live is None or self.state != 'running':
            return None
        if self.time(now) - self.live.time > STALE_AFTER:
            return None
        return self.live

    def hint(self, now):
        """Indicación estable (≥400 ms) para el texto guía."""
        reading = self.current_reading(now)
        if reading is None:
            return 'silence'
        if reading.time - self.hint_since < HINT_PERSISTENCE and reading.kind in ('low', 'high'):
            return None
        return reading.kind

    def active_note(self, now):
        t = self.time(now)
        for i, note in enumerate(self.notes):
            if note.start - REACTION <= t <= note.end:
                return i
        return None

    def next_note(self, now):
        t = self.time(now)
        for i, note in enumerate(self.notes):
            if note.start > t:
                return i
        return None

    @property
    def score(self):
        return sum(n.points for n in self.notes)

    @property
    def max_score(self):
        return 1000 * len(self.notes)

    def summary(self):
        judged = [n for n in self.notes if n.judgement]
        hits = sum(n.judgement in HITS for n in judged)
        misses = sum(n.judgement.startswith('miss') for n in judged)
        unclear = sum(n.judgement == 'unclear' for n in judged)
        silent = sum(n.judgement == 'silent' for n in judged)
        measured = sum(n.measured for n in self.notes)
        in_zone = sum(n.hit for n in self.notes) / measured if measured > .2 else None
        tendency = weighted_median([(w, c) for n in self.notes for w, c in n.cents])
        measurable = hits + misses
        if measurable == 0:
            stars = None
        else:
            share = hits / len(self.notes)
            stars = 3 if share >= .8 else 2 if share >= .5 else 1 if hits else 0
        return {
            'notes': len(self.notes), 'hits': hits, 'misses': misses,
            'unclear': unclear, 'silent': silent, 'in_zone': in_zone,
            'tendency': tendency, 'stars': stars, 'score': self.score,
            'best_streak': self.best_streak,
        }
