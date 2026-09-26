// La versión web debe dar los MISMOS resultados que la lógica Python original.
// fixtures.json lo genera tests/web/make_fixtures.py ejecutando el código Python.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { detectPitch } from '../../app/js/pitch/yin.js';
import { hzToNote, noteName } from '../../app/js/pitch/notes.js';
import { LEVELS, placements } from '../../app/js/game/levels.js';
import { buildRound } from '../../app/js/game/noteRun.js';
import { ReferenceFinder } from '../../app/js/game/reference.js';

const fx = JSON.parse(readFileSync(new URL('./fixtures.json', import.meta.url), 'utf8'));
const SR = fx.sample_rate;

function signal(kind, freq, n) {
  const x = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const t = i / SR;
    if (kind === 'sine') x[i] = 0.5 * Math.sin(2 * Math.PI * freq * t);
    else for (let k = 1; k < 8; k++) x[i] += (0.5 / k) * Math.sin(2 * Math.PI * k * freq * t);
  }
  return x;
}

const cents = (a, b) => 1200 * Math.log2(a / b);

test('YIN da la misma frecuencia que el Python (≤0,01 cents)', () => {
  for (const c of fx.pitch) {
    const frame = c.kind === 'samples' ? Float64Array.from(c.samples) : signal(c.kind, c.freq, c.n);
    const got = detectPitch(frame, SR);
    if (c.expected === null) {
      assert.equal(got, null, `${c.kind} ${c.freq} n=${c.n}`);
    } else {
      assert.ok(got !== null, `${c.kind} ${c.freq} n=${c.n}: null`);
      assert.ok(Math.abs(cents(got, c.expected)) < 0.01, `${c.kind} ${c.freq} n=${c.n}: ${got} vs ${c.expected}`);
    }
  }
});

test('frecuencia → nota y cents idénticos', () => {
  for (const c of fx.notes) {
    const r = hzToNote(c.freq);
    assert.equal(r.label, c.label, String(c.freq));
    assert.equal(r.midi, c.midi);
    assert.ok(Math.abs(r.cents - c.cents) < 1e-9);
  }
  for (const [midi, name] of Object.entries(fx.names)) assert.equal(noteName(Number(midi)), name);
});

test('colocación de intentos por nivel idéntica', () => {
  const ranges = [[-2, 5], [-3, 6], [-5, 8], [0, 4]];
  for (const lv of LEVELS) {
    ranges.forEach(([lo, hi], i) => assert.deepEqual(placements(lv, lo, hi), fx.placements[lv.key][i], lv.key));
  }
});

test('búsqueda de nota idéntica', () => {
  const finder = new ReferenceFinder();
  let result = null;
  for (const [f, level, now, d] of fx.reference.feed) result = finder.feed(f, level, now, d);
  assert.ok(Math.abs(result - fx.reference.frequency) < 1e-9, `${result} vs ${fx.reference.frequency}`);
  assert.ok(Math.abs(finder.progress - fx.reference.progress) < 1e-9);
});

test('partida completa: mismos juicios, puntuación y resumen', () => {
  const g = fx.game;
  const lv = LEVELS[g.level];
  const run = buildRound(g.anchor, lv.pattern, g.starts, lv.noteLen, lv.tolerance);
  run.start(g.origin);
  for (const [stamp, step, f, level] of g.feed) {
    run.feed(stamp, step, f, level);
    run.update(stamp);
  }
  assert.deepEqual(run.sung.map((n) => n.judgement), g.judgements);
  run.sung.forEach((n, i) => assert.ok(Math.abs(n.hit - g.hits[i]) < 1e-6, `nota ${i}`));
  const s = run.summary();
  const e = g.summary;
  for (const k of ['notes', 'hits', 'misses', 'unclear', 'silent', 'stars', 'score', 'passed']) assert.equal(s[k], e[k], k);
  assert.equal(s.bestStreak, e.best_streak);
  assert.ok(Math.abs(s.inZone - e.in_zone) < 1e-9);
  assert.ok(Math.abs(s.tendency - e.tendency) < 1e-9);
  s.attemptScores.forEach((x, i) => assert.ok(Math.abs(x - e.attempt_scores[i]) < 1e-12));
});
