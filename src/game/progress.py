"""Progreso guardado en disco: tu nota, tu rango, niveles y mapa de tu voz.

- Mapa de tu voz: para cada nota (MIDI absoluto) una media móvil de lo que la
  aciertas (0–1) y cuántas veces se ha medido. Las notas sin señal clara o sin
  cantar no entran: no son fallos.
- Niveles: se supera uno con ≥80 % de notas en 2 de los 3 intentos; entonces
  se desbloquea el siguiente.
- Rango: empieza en [-2, +5] semitonos respecto a tu nota. Sólo crece un
  semitono por un borde cuando esa nota se acierta bien (media ≥ 0,7 en ≥ 3
  mediciones) Y respondes que la ronda te resultó cómoda.
"""
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from game.levels import LEVELS

DEFAULT_PATH = Path(__file__).resolve().parents[2] / 'datos' / 'progreso.json'
START_LO, START_HI = -2, 5
EMA_ALPHA = .35
GROW_EMA = .7
GROW_SAMPLES = 3


@dataclass
class Progress:
    anchor_midi: int = None
    lo: int = START_LO
    hi: int = START_HI
    unlocked: int = 0
    history: dict = field(default_factory=dict)   # nivel -> [[puntuaciones de intentos], …]
    notes: dict = field(default_factory=dict)     # 'midi' -> {'ema': x, 'n': k}
    path: str = None

    @classmethod
    def load(cls, path=DEFAULT_PATH):
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            data.pop('path', None)
            progress = cls(**data)
        except (OSError, ValueError, TypeError):
            progress = cls()
        progress.path = str(path)
        return progress

    def save(self):
        if not self.path:
            return
        path = Path(self.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data.pop('path')
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')

    # --- nota base y rango ---------------------------------------------
    def set_anchor(self, midi):
        """Nueva nota base: el rango conserva sus notas absolutas."""
        if self.anchor_midi is not None:
            delta = midi - self.anchor_midi
            self.lo -= delta
            self.hi -= delta
        self.anchor_midi = midi
        self.lo = min(self.lo, 0)
        self.hi = max(self.hi, max(LEVELS[0].pattern))

    def range_midi(self):
        return self.anchor_midi + self.lo, self.anchor_midi + self.hi

    def stat(self, midi):
        return self.notes.get(str(midi))

    # --- resultados ----------------------------------------------------
    def record_round(self, level_index, summary, note_results):
        """note_results: [(midi, ratio 0–1)] de notas medidas. Devuelve si desbloquea."""
        key = LEVELS[level_index].key
        self.history.setdefault(key, []).append([round(s, 3) for s in summary['attempt_scores']])
        self.history[key] = self.history[key][-10:]
        for midi, ratio in note_results:
            entry = self.notes.setdefault(str(midi), {'ema': ratio, 'n': 0})
            if entry['n']:
                entry['ema'] = entry['ema'] * (1 - EMA_ALPHA) + ratio * EMA_ALPHA
            entry['n'] += 1
            entry['ema'] = round(entry['ema'], 4)
        unlocked_new = False
        if summary['passed'] and level_index == self.unlocked and self.unlocked < len(LEVELS) - 1:
            self.unlocked += 1
            unlocked_new = True
        self.save()
        return unlocked_new

    def grow_range(self):
        """Tras una ronda cómoda: amplía cada borde que se acierte bien.

        Devuelve [(lado, midi_nuevo)], lado = 'agudo' | 'grave'.
        """
        grown = []
        low, high = self.range_midi()
        for side, midi in (('agudo', high), ('grave', low)):
            entry = self.stat(midi)
            if entry and entry['n'] >= GROW_SAMPLES and entry['ema'] >= GROW_EMA:
                if side == 'agudo':
                    self.hi += 1
                    grown.append((side, high + 1))
                else:
                    self.lo -= 1
                    grown.append((side, low - 1))
        if grown:
            self.save()
        return grown
