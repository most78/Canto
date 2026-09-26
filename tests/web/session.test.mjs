// Recorrido completo del ejercicio «Escalas» sin navegador (equivale a la
// antigua prueba de humo de PySide6): nota → nivel → ronda → pausa → resultado.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { ScalesSession } from '../../app/js/exercises/scales.js';
import { Progress } from '../../app/js/state/progress.js';
import { LEVELS } from '../../app/js/game/levels.js';

function memoryStorage() {
  const data = new Map();
  return { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => data.set(k, v) };
}

function setup() {
  const clock = { t: 1000 };
  const played = [];
  const piano = { phrase: (notes, when) => played.push({ notes, when }), stopAll: () => played.push('stop') };
  const storage = memoryStorage();
  const session = new ScalesSession({ progress: Progress.load(storage), piano, clock: () => clock.t });
  return { session, clock, played, storage };
}

test('recorrido completo: nota, ronda, pausa, resultado y progreso', () => {
  const { session, clock, played, storage } = setup();
  const events = [];
  for (const type of ['screen', 'judgement', 'results']) session.addEventListener(type, (e) => events.push([type, e.detail]));

  session.setMic(true, 'simulado');
  assert.equal(session.setupView().canStart, false);
  session.startFinding();
  for (const f of [214, 215, null, 213, 214, 214, 214, 214, 214, 214, 214, 214, 214, 214, 214, 214, 214]) {
    clock.t += 0.0213;
    session.feed(clock.t, 0.0213, f, 0.03);
  }
  assert.equal(session.anchorMidi, 57);                 // 214 Hz → La2
  const view = session.setupView();
  assert.equal(view.noteLabel, 'La2');
  assert.ok(view.canStart);
  assert.deepEqual(view.preview, ['La2', 'Si2', 'Do#3', 'Si2', 'La2']);
  assert.equal(view.levels[1].unlocked, false);

  session.startRun();
  const run = session.run;
  assert.equal(session.screen, 'play');
  const A = session.frequency;
  const step = 0.0213;
  const advance = (target, semitone = null, cents = 0, level = 0.03) => {
    while (run.state === 'running' && run.time(clock.t) < target - 1e-9) {
      clock.t += step;
      const f = semitone === null ? null : A * 2 ** ((semitone * 100 + cents) / 1200);
      session.feed(clock.t, step, f, semitone === null ? 0 : level);
      session.tick();
    }
  };

  // Escucha: el piano se programa alineado con la barra y ese audio no puntúa.
  const demo0 = run.notes.filter((n) => n.demo && n.attempt === 0);
  advance(demo0[1].start, 0);
  assert.ok(played.some((p) => p.notes && Math.abs(p.when - (run.origin + demo0[0].start)) < 1e-9));
  assert.equal(run.live.kind, 'muted');
  assert.equal(run.sung.reduce((s, n) => s + n.hit, 0), 0);

  const singAttempt = (a, wrong = []) => run.sung.filter((n) => n.attempt === a).forEach((n, i) => {
    advance(n.start);
    advance(n.end, n.semitone, wrong.includes(i) ? -160 : 0);
  });
  singAttempt(0);
  assert.equal(session.message.tone !== undefined, true);
  singAttempt(1, [2]);

  // Pausa: el tiempo se congela, el piano se calla y el audio no suma.
  session.togglePause();
  const frozen = run.time(clock.t);
  clock.t += 5;
  session.feed(clock.t, step, A, 0.03);
  assert.equal(run.time(clock.t), frozen);
  assert.equal(played.at(-1), 'stop');
  assert.equal(session.message.key, 'paused');
  session.togglePause();

  singAttempt(2, [1, 2, 4]);
  advance(run.end + 0.1);
  assert.equal(session.screen, 'results');
  const r = session.results;
  assert.deepEqual(r.attempts.map((a) => Math.round(a.score * 100)), [100, 80, 40]);
  assert.equal(r.passed, true);
  assert.equal(r.stars, 2);
  assert.ok(r.unlocked);
  assert.equal(session.progress.unlocked, 1);
  assert.ok(events.some(([type]) => type === 'judgement'));

  session.answerComfort(true);
  assert.ok(r.comfortAnswered && r.comfortNote);
  session.answerComfort(false);                             // sólo se responde una vez
  assert.ok(!r.comfortNote.startsWith('Gracias'));

  // Progreso guardado y siguiente nivel disponible.
  const saved = Progress.load(storage);
  assert.equal(saved.anchor_midi, 57);
  assert.equal(saved.unlocked, 1);
  session.nextLevel();
  assert.equal(session.levelIndex, 1);
  assert.equal(session.screen, 'setup');
  assert.ok(session.setupView().levelDescription.includes(LEVELS[1].description));
});

test('sin datos del micro se avisa; ocultar la página pausa', () => {
  const { session, clock } = setup();
  session.progress.setAnchor(57);
  session.setMic(true);
  session.startRun();
  clock.t += 2;
  session.tick();
  assert.equal(session.message.key, 'nodata');
  session.setVisible(false);
  assert.equal(session.run.state, 'paused');
  assert.equal(session.escapeAction(), false);
});

test('Escuchar mi nota silencia la búsqueda mientras suena', () => {
  const { session, clock, played } = setup();
  session.progress.setAnchor(57);
  session.setMic(true);
  session.listen();
  assert.equal(played.length, 1);
  session.startFinding();
  session.feed(clock.t + 0.1, 0.02, 220, 0.03);             // suena el piano: se ignora
  assert.equal(session.finder.tones, 0);
});
