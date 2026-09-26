// Port de legacy/tests/test_note_run.py: reglas de rondas, niveles, progreso y búsqueda de nota.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { LEVELS, placements } from '../../app/js/game/levels.js';
import { HITS, Note, NoteRun, buildRound, classify } from '../../app/js/game/noteRun.js';
import { ReferenceFinder } from '../../app/js/game/reference.js';
import { noteName } from '../../app/js/pitch/notes.js';
import { Progress, importLegacyProgress } from '../../app/js/state/progress.js';

const ANCHOR = 220;
const VOICE = 0.05;
const O = 100;

const freq = (semitones, c = 0) => ANCHOR * 2 ** ((semitones * 100 + c) / 1200);

function sing(run, t0, t1, frequency, level = VOICE, step = 0.08) {
  for (let t = t0 + step; t <= t1 + 1e-9; t += step) run.feed(O + t, step, frequency, level);
}
const singNote = (run, note, c = 0, level = VOICE, step = 0.08) => sing(run, note.start, note.end, freq(note.semitone, c), level, step);
const finish = (run) => run.update(O + run.end + 1);

function newRound(pattern = [0, 2, 4, 2, 0], starts = [0, 1, -1], noteLen = 0.9) {
  const run = buildRound(ANCHOR, pattern, starts, noteLen);
  run.start(O);
  return run;
}

function single(duration = 1.5) {
  const run = new NoteRun(ANCHOR, [new Note(1, 1 + duration, 0)]);
  run.start(O);
  return run;
}

function memoryStorage() {
  const data = new Map();
  return { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => data.set(k, v) };
}

test('clasificación de lecturas', () => {
  assert.equal(classify(ANCHOR, 0, ANCHOR)[0], 'silence');
  assert.equal(classify(null, VOICE, ANCHOR)[0], 'unclear');
  assert.equal(classify(freq(0, 40), VOICE, ANCHOR)[0], 'hit');
  assert.equal(classify(freq(2, 30), VOICE, ANCHOR, 200)[0], 'hit');
  assert.equal(classify(freq(2, -80), VOICE, ANCHOR, 200)[0], 'low');
  assert.equal(classify(freq(0, 80), VOICE, ANCHOR)[0], 'high');
  assert.equal(classify(ANCHOR * 2, VOICE, ANCHOR)[0], 'high');      // octava ≠ acierto
  assert.equal(classify(ANCHOR * 4, VOICE, ANCHOR)[0], 'unclear');
  const [kind, c] = classify(freq(3), VOICE, ANCHOR, null);
  assert.equal(kind, 'free');
  assert.ok(Math.abs(c - 300) < 1e-9);
});

test('el volumen nunca multiplica', () => {
  for (const level of [0.003, 0.05, 0.9]) assert.deepEqual(classify(ANCHOR, level, ANCHOR), ['hit', 0]);
});

test('estructura: escuchar y luego cantar', () => {
  const run = newRound();
  const demo = run.notes.filter((n) => n.demo);
  assert.equal(demo.length, 15);
  assert.equal(run.sung.length, 15);
  assert.equal(run.cues.length, 3);
  for (let a = 0; a < 3; a++) {
    const d = demo.filter((n) => n.attempt === a);
    const s = run.sung.filter((n) => n.attempt === a);
    assert.deepEqual(d.map((n) => n.semitone), s.map((n) => n.semitone));
    assert.ok(d[d.length - 1].end < s[0].start);
  }
  assert.deepEqual(run.sung.filter((n) => n.attempt === 1).map((n) => n.semitone), [1, 3, 5, 3, 1]);
});

test('ronda perfecta con cualquier tamaño de bloque', () => {
  for (const step of [0.02, 0.05, 0.08, 0.128]) {
    const run = newRound();
    for (const note of run.sung) singNote(run, note, 0, VOICE, step);
    finish(run);
    assert.ok(run.sung.every((n) => n.judgement === 'perfect'), String(step));
    const s = run.summary();
    assert.deepEqual([s.hits, s.stars, s.passed], [15, 3, true]);
    assert.equal(run.state, 'finished');
  }
});

test('cantar durante la escucha no puntúa (y cubre la cola del piano)', () => {
  const run = newRound();
  const demo = run.notes.filter((n) => n.demo && n.attempt === 0);
  for (const note of demo) sing(run, note.start, note.end, freq(note.semitone));
  assert.equal(run.sung.reduce((s, n) => s + n.hit, 0), 0);
  assert.equal(run.live.kind, 'muted');
  const run2 = newRound();
  const d2 = run2.notes.filter((n) => n.demo && n.attempt === 0);
  assert.equal(run2.feed(O + d2[d2.length - 1].end + 0.5, 0.08, ANCHOR, VOICE).kind, 'muted');
});

test('cada nota tiene su propio objetivo', () => {
  const run = newRound();
  const first = run.sung.filter((n) => n.attempt === 0);
  for (const note of first) sing(run, note.start, note.end, ANCHOR);
  finish(run);
  assert.deepEqual(first.map((n) => HITS.has(n.judgement)), [true, false, false, false, true]);
  assert.equal(first[1].judgement, 'miss_low');
});

test('descansos no suman y aguantar más no añade', () => {
  const run = newRound();
  const [a, b] = [run.sung[4], run.sung[5]];
  sing(run, a.start, b.start - 3, freq(a.semitone));
  assert.ok(Math.abs(a.hit - a.duration) < 1e-6);
  assert.equal(b.hit, 0);
});

test('cantar más fuerte no da más puntos', () => {
  const scores = [0.004, 0.5].map((level) => {
    const run = newRound();
    singNote(run, run.sung[0], 0, level);
    finish(run);
    return run.score;
  });
  assert.equal(scores[0], scores[1]);
});

test('silencio y ruido no son fallos', () => {
  const run = newRound();
  singNote(run, run.sung[0], 0, 0);
  sing(run, run.sung[1].start, run.sung[1].end, null, 0.2);
  finish(run);
  assert.equal(run.sung[0].judgement, 'silent');
  assert.equal(run.sung[1].judgement, 'unclear');
  const s = run.summary();
  assert.equal(s.misses, 0);
  assert.equal(s.stars, null);
});

test('superar = 80 % en 2 de 3 intentos', () => {
  const run = newRound();
  for (const note of run.sung) {
    const wrong = note.attempt === 2 || (note.attempt === 1 && note === run.sung[5]);
    singNote(run, note, wrong ? -150 : 0);
  }
  finish(run);
  const s = run.summary();
  assert.deepEqual(s.attemptScores.map((x) => Math.round(x * 100) / 100), [1, 0.8, 0]);
  assert.equal(s.passed, true);
  assert.equal(s.stars, 2);
  const run2 = newRound();
  for (const note of run2.sung) singNote(run2, note, note.attempt === 0 ? 0 : -150);
  finish(run2);
  assert.equal(run2.summary().passed, false);
});

test('cada bloque cuenta una vez; la pausa congela y descarta audio viejo', () => {
  const run = single();
  const note = run.sung[0];
  const stamp = O + note.start + 0.5;
  run.feed(stamp, 0.5, ANCHOR, VOICE);
  run.feed(stamp, 0.5, ANCHOR, VOICE);
  run.feed(stamp - 0.2, 0.08, ANCHOR, VOICE);
  assert.ok(Math.abs(note.hit - 0.5) < 1e-9);

  const r2 = single();
  const n2 = r2.sung[0];
  r2.pause(O + n2.start);
  assert.equal(r2.feed(O + n2.start + 0.1, 0.08, ANCHOR, VOICE), null);
  r2.resume(200);
  assert.ok(Math.abs(r2.time(200) - n2.start) < 1e-9);
  r2.feed(200.02, 0.5, ANCHOR, VOICE);
  assert.ok(Math.abs(n2.hit - 0.02) < 1e-6);
});

test('las frases del piano se consumen una sola vez', () => {
  const run = newRound();
  const cue = run.dueCues(O + 1.0);
  assert.equal(cue.length, 1);
  assert.deepEqual(cue[0].notes.map(([, k]) => k), [0, 2, 4, 2, 0]);
  assert.deepEqual(run.dueCues(O + 1.1), []);
});

test('indicaciones: persistencia de 400 ms y datos recientes', () => {
  const run = single();
  run.feed(O + 1.0, 0.08, freq(0, -120), VOICE);
  assert.equal(run.hint(O + 1.0), null);
  for (let i = 1; i < 6; i++) run.feed(O + 1.0 + i * 0.08, 0.08, freq(0, -120), VOICE);
  assert.equal(run.hint(O + 1.4), 'low');
  assert.equal(run.hint(O + 3.5), 'silence');
  assert.equal(run.currentReading(O + 3.5), null);
});

test('fases de la ronda', () => {
  const run = newRound();
  const demo0 = run.notes.find((n) => n.demo);
  assert.equal(run.phase(O + 0.2)[0], 'intro');
  assert.deepEqual(run.phase(O + demo0.start + 0.1), ['listen', 0]);
  assert.deepEqual(run.phase(O + run.sung[0].start - 0.8), ['turn', 0]);
  assert.deepEqual(run.phase(O + run.sung[0].start + 0.1), ['sing', 0]);
  assert.equal(run.phase(O + run.sung[4].end + 1)[0], 'rest');
});

test('niveles y nombres de nota', () => {
  assert.deepEqual(placements(LEVELS[0], -2, 5), [0, 1, -2]);
  assert.deepEqual(placements(LEVELS[1], -2, 5), [-2, -2, -2]);
  assert.deepEqual(placements(LEVELS[6], -2, 5), []);
  assert.equal(noteName(69), 'La3');
  assert.equal(noteName(57), 'La2');
  assert.equal(noteName(61), 'Do#3');
});

test('progreso: guarda, carga, desbloquea y amplía rango', () => {
  const storage = memoryStorage();
  const p = Progress.load(storage);
  p.setAnchor(57);
  p.recordRound(0, { attemptScores: [1, 0.8, 0.6], passed: true }, [[57, 1], [59, 0.5]]);
  const q = Progress.load(storage);
  assert.deepEqual([q.anchor_midi, q.unlocked], [57, 1]);
  assert.deepEqual(q.stat(59), { ema: 0.5, n: 1 });

  const r = Progress.load(memoryStorage());
  r.setAnchor(57);
  const high = 57 + r.hi;
  assert.deepEqual(r.growRange(), []);
  for (let i = 0; i < 3; i++) r.recordRound(0, { attemptScores: [1], passed: false }, [[high, 0.9]]);
  assert.deepEqual(r.growRange(), [['agudo', high + 1]]);
  assert.equal(r.hi, 6);
  assert.equal(r.recordRound(0, { attemptScores: [0.2], passed: false }, []), false);

  const s = Progress.load(memoryStorage());
  s.setAnchor(57);
  const before = s.rangeMidi();
  s.setAnchor(58);
  assert.deepEqual(s.rangeMidi(), before);
  s.setAnchor(62);
  assert.ok(s.hi >= 4);
});

test('importa el progreso de la versión Python sólo si no hay progreso web', async () => {
  const legacy = { anchor_midi: 57, lo: -3, hi: 6, unlocked: 2, history: {}, notes: { 57: { ema: 0.9, n: 4 } } };
  const fetcher = async () => ({ ok: true, json: async () => legacy });
  const p = Progress.load(memoryStorage());
  assert.equal(await importLegacyProgress(p, fetcher), true);
  assert.deepEqual([p.anchor_midi, p.hi, p.unlocked], [57, 6, 2]);
  assert.equal(await importLegacyProgress(p, fetcher), false);
});

test('búsqueda de nota: grupo consistente y fallos explicados', () => {
  const finder = new ReferenceFinder();
  [220, 222, null, null, 219, 220].forEach((f, i) => finder.feed(f, VOICE, i * 0.1, 0.08));
  assert.ok(Math.abs(finder.frequency - 220) < 1);
  for (const [level, reason] of [[0, 'muy baja'], [0.05, 'no distingo']]) {
    const fnd = new ReferenceFinder();
    for (let i = 0; i < 45; i++) fnd.feed(null, level, i * 0.1, 0.08);
    assert.equal(fnd.frequency, null);
    assert.ok(fnd.failed[0].includes(reason));
  }
});
