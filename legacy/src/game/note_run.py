"""Puntuación de una ronda de «Escalas»: escuchar una frase al piano y cantarla.

Una ronda tiene 3 intentos. En cada uno:
  1. ESCUCHA: el piano toca la frase. Esas barras («demo») no puntúan y el
     audio de ese tramo, más una cola, se ignora.
  2. TU TURNO: las mismas notas llegan a la línea AHORA y se cantan.
  3. RESPIRA: descanso antes del siguiente intento.

Reglas (ver docs/diseno-juegos.md):
- Cada nota tiene un objetivo fijo: semitonos respecto a tu nota base.
- Sólo puntúa audio nuevo: cada instante se cuenta una vez y sólo dentro de la
  ventana de una nota cantada. Cantar en escucha o descanso no suma.
- Silencio, sonido sin nota clara y bloques antiguos (anteriores a una pausa)
  no suman ni cuentan como fallo.
- El volumen sólo separa silencio de sonido; nunca multiplica puntos.
- Aguantar más de lo que dura la barra no suma.

El tiempo de juego avanza con el reloj monotónico y se congela en pausa. Cada
bloque del micrófono llega con la marca monotónica de cuando terminó.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

TOLERANCE_CENTS = 50        # zona de acierto por defecto alrededor de cada nota
PLAUSIBLE_CENTS = 1900      # más lejos que esto lo tratamos como lectura dudosa
SILENCE_RMS = .002          # misma puerta de silencio que la captura
REACTION = .25              # margen para llegar a cada nota
JUDGE_DELAY = .35           # espera a bloques tardíos antes de juzgar
HINT_PERSISTENCE = .4       # una indicación de dirección debe mantenerse 400 ms
STALE_AFTER = .3            # sin bloques nuevos en este tiempo = no hay lectura
MUTE_TAIL = .6              # apagado del piano + eco + latencia tras la escucha

LEAD = 1.0                  # antes de la primera escucha
TURN_GAP = 1.6              # entre escuchar y cantar: «¡tu turno!»
REST = 3.0                  # descanso entre intentos
PASS_SCORE = .8             # un intento vale si aciertas el 80 % de sus notas
PASSES_NEEDED = 2           # … en 2 de los 3 intentos

HITS = ('perfect', 'great', 'ok')
JUDGEMENT_TEXT = {
    'perfect': '¡Perfecta!',
    'great': '¡Muy bien!',
    'ok': 'Bien',
    'miss_low': 'Grave',
    'miss_high': 'Aguda',
    'unclear': 'No te oí claro',
    'silent': 'Sin cantar',
}


def cents_between(frequency, reference):
    return 1200 * math.log2(frequency / reference)


def weighted_median(pairs):
    """Mediana de valores ponderada por segundos; None sin datos."""
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
    semitone: int = 0            # respecto a la nota base
    attempt: int = 0
    demo: bool = False           # la toca el piano: no se puntúa
    hit: float = 0.0
    low: float = 0.0
    high: float = 0.0
    unclear: float = 0.0
    errors: list = field(default_factory=list)      # (segundos, cents respecto al objetivo)
    hit_spans: list = field(default_factory=list)   # tramos acertados, para dibujarlos
    judgement: str | None = None

    @property
    def target(self):
        return self.semitone * 100

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
    time: float          # tiempo de juego al final del bloque
    kind: str            # hit | low | high | free | unclear | silence | muted
    cents: float | None  # respecto a la nota base (posición en el eje)


def classify(frequency, level, anchor, target_cents=0, tolerance=TOLERANCE_CENTS):
    """Tipo de lectura y cents respecto a la nota base.

    Con `target_cents=None` no hay nota que cantar: la voz se muestra ('free')
    sin juzgarla.
    """
    if level < SILENCE_RMS:
        return 'silence', None
    if frequency is None or frequency <= 0:
        return 'unclear', None
    cents = cents_between(frequency, anchor)
    if target_cents is None:
        return ('free', cents) if abs(cents) <= PLAUSIBLE_CENTS else ('unclear', None)
    error = cents - target_cents
    if abs(error) > PLAUSIBLE_CENTS:
        return 'unclear', None
    if abs(error) <= tolerance:
        return 'hit', cents
    return ('low' if error < 0 else 'high'), cents


class NoteRun:
    """Motor genérico: notas con objetivo propio, escuchas silenciadas y reloj con pausa."""

    def __init__(self, anchor, notes, tolerance=TOLERANCE_CENTS, cues=(), end=None):
        self.anchor = float(anchor)
        self.tolerance = tolerance
        self.notes = list(notes)
        self.sung = [n for n in self.notes if not n.demo]
        self.end = end if end is not None else max(n.end for n in self.notes) + 1.5
        self.cues = sorted(cues, key=lambda c: c['time'])   # {'time', 'notes', 'mute_until'}
        self.muted = [(c['time'], c['mute_until'] + MUTE_TAIL) for c in self.cues]
        self.state = 'ready'
        self.origin = None
        self.paused_time = 0.0
        self.counted_until = 0.0
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
        if self.state == 'ready':
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
        """Devuelve y consume las frases de piano que toca reproducir."""
        if self.state != 'running':
            return []
        t = self.time(now)
        due = [c for c in self.cues if c['time'] <= t]
        self.cues = [c for c in self.cues if c['time'] > t]
        return due

    # --- objetivo en cada momento ---------------------------------------
    def reference_note(self, t):
        """Nota cantada con la que comparar la voz ahora (o None)."""
        for note in self.sung:
            if note.start - REACTION <= t <= note.end:
                return note
        upcoming = [n for n in self.sung if 0 < n.start - t <= 1.2]
        return upcoming[0] if upcoming else None

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
            ref = self.reference_note(end)
            kind, cents = classify(frequency, level, self.anchor,
                                   ref.target if ref else None, self.tolerance)
            reading = Reading(end, kind, cents)
            for note in self.sung:
                if note.judgement is not None:
                    continue
                overlap = min(end, note.end) - max(begin, note.start)
                if overlap <= 1e-6:
                    continue
                k, c = classify(frequency, level, self.anchor, note.target, self.tolerance)
                if k in ('hit', 'low', 'high'):
                    setattr(note, k, getattr(note, k) + overlap)
                    note.errors.append((overlap, c - note.target))
                elif k == 'unclear':
                    note.unclear += overlap
                if k == 'hit':
                    a, b = max(begin, note.start), min(end, note.end)
                    if note.hit_spans and a - note.hit_spans[-1][1] < .05:
                        note.hit_spans[-1] = (note.hit_spans[-1][0], b)
                    else:
                        note.hit_spans.append((a, b))
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
            if not note.demo and note.judgement is None and t >= note.end + JUDGE_DELAY:
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
        """Índice de la nota CANTADA activa (con margen de reacción) o None."""
        t = self.time(now)
        for i, note in enumerate(self.notes):
            if not note.demo and note.start - REACTION <= t <= note.end:
                return i
        return None

    def next_note(self, now):
        t = self.time(now)
        for i, note in enumerate(self.notes):
            if not note.demo and note.start > t:
                return i
        return None

    def phase(self, now):
        """(fase, intento): intro | listen | turn | sing | rest | end."""
        t = self.time(now)
        for a in self.attempts:
            demo = [n for n in self.notes if n.attempt == a and n.demo]
            sung = [n for n in self.sung if n.attempt == a]
            if demo and demo[0].start - .3 <= t <= demo[-1].end + .2:
                return 'listen', a
            if demo and demo[-1].end + .2 < t < sung[0].start - REACTION:
                return 'turn', a
            if sung[0].start - REACTION <= t <= sung[-1].end:
                return 'sing', a
        if t < min(n.start for n in self.notes):
            return 'intro', 0
        if t > max(n.end for n in self.notes):
            return 'end', self.attempts[-1]
        return 'rest', max((n.attempt for n in self.notes if n.end < t), default=0)

    @property
    def attempts(self):
        return sorted({n.attempt for n in self.sung})

    @property
    def score(self):
        return sum(n.points for n in self.sung)

    def attempt_score(self, attempt):
        notes = [n for n in self.sung if n.attempt == attempt]
        return sum(n.judgement in HITS for n in notes) / len(notes) if notes else 0.0

    def summary(self):
        judged = [n for n in self.sung if n.judgement]
        hits = sum(n.judgement in HITS for n in judged)
        misses = sum(n.judgement.startswith('miss') for n in judged)
        unclear = sum(n.judgement == 'unclear' for n in judged)
        silent = sum(n.judgement == 'silent' for n in judged)
        measured = sum(n.measured for n in self.sung)
        in_zone = sum(n.hit for n in self.sung) / measured if measured > .2 else None
        tendency = weighted_median([pair for n in self.sung for pair in n.errors])
        scores = [self.attempt_score(a) for a in self.attempts]
        passes = sum(s >= PASS_SCORE - 1e-9 for s in scores)
        if hits + misses == 0:
            stars = None
        else:
            stars = 3 if passes >= 3 else 2 if passes >= PASSES_NEEDED else 1 if hits else 0
        return {
            'notes': len(self.sung), 'hits': hits, 'misses': misses,
            'unclear': unclear, 'silent': silent, 'in_zone': in_zone,
            'tendency': tendency, 'stars': stars, 'score': self.score,
            'best_streak': self.best_streak, 'attempt_scores': scores,
            'passed': passes >= PASSES_NEEDED,
        }


def build_round(anchor, pattern, starts, note_len, tolerance=TOLERANCE_CENTS,
                lead=LEAD, turn_gap=TURN_GAP, rest=REST):
    """Crea una ronda: para cada inicio (semitonos), escucha + canto del patrón.

    Cada cue lleva las notas para el piano como (desfase_s, semitono, duración_s).
    """
    notes, cues = [], []
    t = lead
    for attempt, base in enumerate(starts):
        semis = [base + p for p in pattern]
        demo_start = t
        for k in semis:
            notes.append(Note(t, t + note_len * .92, k, attempt, demo=True))
            t += note_len
        demo_end = t
        cues.append({'time': demo_start, 'mute_until': demo_end, 'attempt': attempt,
                     'notes': [(i * note_len, k, note_len * .92) for i, k in enumerate(semis)]})
        t += turn_gap
        for k in semis:
            notes.append(Note(t, t + note_len * .92, k, attempt))
            t += note_len
        t += rest
    return NoteRun(anchor, notes, tolerance, cues, end=t - rest + 1.2)
