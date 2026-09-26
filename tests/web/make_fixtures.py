"""Genera tests/web/fixtures.json ejecutando la lógica ORIGINAL de Python.

Los tests JS (node --test tests/web) comparan la versión web con estos
resultados: YIN, frecuencia → nota/cents, búsqueda de nota y una partida
completa simulada (juicios, puntuación y resumen).

    python tests/web/make_fixtures.py
"""
import json
import math
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT / 'legacy' / 'src', ROOT / 'src'):
    if (candidate / 'audio' / 'pitch.py').exists():
        sys.path.insert(0, str(candidate))
        break

from audio.pitch import detect_pitch, hz_to_note  # noqa: E402
from game.levels import LEVELS, note_name, placements  # noqa: E402
from game.note_run import build_round  # noqa: E402
from game.reference import ReferenceFinder  # noqa: E402

SR = 48000


def signal(kind, freq, n, amp=.5):
    t = np.arange(n) / SR
    if kind == 'sine':
        return amp * np.sin(2 * np.pi * freq * t)
    if kind == 'voice':
        return sum((.5 / k) * np.sin(2 * np.pi * k * freq * t) for k in range(1, 8))
    raise ValueError(kind)


def pitch_cases():
    cases = []
    for n in (2048, 3072, 3840):
        for kind in ('sine', 'voice'):
            for f in (82.41, 110.0, 146.83, 196.0, 261.63, 440.0, 659.26, 987.77):
                if n == 2048 and f < 100:
                    continue
                x = signal(kind, f, n)
                cases.append({'kind': kind, 'freq': f, 'n': n, 'expected': detect_pitch(x, SR)})
    rng = np.random.default_rng(7)
    noise = rng.normal(0, .3, 3072)
    cases.append({'kind': 'samples', 'samples': [round(v, 9) for v in noise.tolist()], 'n': 3072,
                  'expected': detect_pitch(noise, SR)})
    return cases


def note_cases():
    freqs = [27.5, 55, 82.41, 110, 123.47, 196, 220, 246.94, 261.63, 440, 440 * 2 ** (30 / 1200),
             440 * 2 ** (70 / 1200), 523.25, 987.77, 1046.5]
    out = []
    for f in freqs:
        r = hz_to_note(f)
        out.append({'freq': f, 'label': r.label, 'midi': r.midi, 'cents': r.cents})
    names = {m: note_name(m) for m in range(33, 85)}
    return out, names


def reference_case():
    rng = random.Random(3)
    feed = []
    t = 0.0
    for i in range(60):
        t += .021
        voiced = 10 <= i < 40 and rng.random() > .15
        f = 214 * 2 ** (rng.uniform(-20, 20) / 1200) if voiced else None
        feed.append([f, .03 if voiced else .001, t, .021])
    finder = ReferenceFinder()
    result = None
    for f, level, now, d in feed:
        result = finder.feed(f, level, now, d)
    return {'feed': feed, 'frequency': result, 'progress': finder.progress}


def game_case():
    level = LEVELS[2]
    starts = placements(level, -2, 5)
    anchor = 220.0
    run = build_round(anchor, level.pattern, starts, level.note_len, level.tolerance)
    origin = 50.0
    run.start(origin)
    rng = random.Random(11)
    feed = []
    t = 0.0
    step = .021
    while t < run.end + .5:
        t += step
        ref = run.reference_note(t)
        roll = rng.random()
        if ref is None or roll < .1:
            f, level_ = None, .0005
        elif roll < .18:
            f, level_ = None, .05                     # ruido sin nota
        else:
            error = rng.choice([0, 0, 0, 10, -30, 80, -120, 1200])
            f, level_ = anchor * 2 ** ((ref.target + error) / 1200), rng.uniform(.004, .3)
        stamp = origin + t
        feed.append([stamp, step, f, level_])
        run.feed(stamp, step, f, level_)
        run.update(stamp)
    s = run.summary()
    return {
        'level': 2, 'starts': starts, 'anchor': anchor, 'origin': origin, 'feed': feed,
        'judgements': [n.judgement for n in run.sung],
        'hits': [round(n.hit, 9) for n in run.sung],
        'summary': {k: s[k] for k in ('notes', 'hits', 'misses', 'unclear', 'silent', 'in_zone',
                                      'tendency', 'stars', 'score', 'best_streak', 'attempt_scores', 'passed')},
    }


def main():
    notes, names = note_cases()
    data = {
        'sample_rate': SR,
        'pitch': pitch_cases(),
        'notes': notes,
        'names': names,
        'placements': {lv.key: [placements(lv, lo, hi) for lo, hi in ((-2, 5), (-3, 6), (-5, 8), (0, 4))]
                       for lv in LEVELS},
        'reference': reference_case(),
        'game': game_case(),
    }
    path = Path(__file__).with_name('fixtures.json')
    path.write_text(json.dumps(data), encoding='utf-8')
    print(f'OK: {path} ({len(data["pitch"])} casos de pitch)')


if __name__ == '__main__':
    main()
