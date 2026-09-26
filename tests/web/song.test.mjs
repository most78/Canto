// Modo canción: modelo, partes/voces, melismas, feedback con histéresis,
// puntuación ligada a la letra, dificultad y tesitura. Sin UI.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { loadSong, SongError } from '../../app/js/songs/model.js';
import { partsFor, targetsFor, unitsFor, pitchRange } from '../../app/js/songs/parts.js';
import { difficulty, suggestNext, DIFFICULTIES } from '../../app/js/songs/difficulty.js';
import { VoiceFeedback } from '../../app/js/songs/feedback.js';
import { SongRun, classifyBlock } from '../../app/js/songs/songRun.js';
import { outOfRange } from '../../app/js/songs/tessitura.js';
import { midiFrequency } from '../../app/js/pitch/notes.js';

const hz = (midi, cents = 0) => midiFrequency(midi + cents / 100);

// Dueto mínimo: A canta «Hola», B canta «a·mor», al final cantan juntos «sí» (A arriba).
function duetData() {
  return {
    format: 'canto-song', version: 1, id: 'duo',
    metadata: { title: 'Dúo de prueba' },
    audio: { kind: 'piano' },
    lyrics: { lines: [
      { id: 'l1', words: [{ id: 'w1', syllables: [{ id: 's1', text: 'Ho' }, { id: 's2', text: 'la' }] }] },
      { id: 'l2', words: [{ id: 'w2', syllables: [{ id: 's3', text: 'a' }, { id: 's4', text: 'mor' }] }] },
      { id: 'l3', words: [{ id: 'w3', syllables: [{ id: 's5', text: 'sí' }] }] },
    ] },
    voices: [
      { id: 'A', name: 'Voz A', priority: 1, events: [
        { id: 'a1', start: 1, duration: 0.5, pitch: 60, syllable: 's1' },
        { id: 'a2', start: 1.6, duration: 0.5, pitch: 62, syllable: 's2' },
        { id: 'a3', start: 5, duration: 1, pitch: 67, syllable: 's5' },
      ] },
      { id: 'B', name: 'Voz B', priority: 2, events: [
        { id: 'b1', start: 3, duration: 0.4, pitch: 55, syllable: 's3' },
        { id: 'b2', start: 3.5, duration: 0.3, pitch: 57, syllable: 's4' },   // melisma «mor»
        { id: 'b3', start: 3.8, duration: 0.3, pitch: 59, syllable: 's4' },
        { id: 'b4', start: 3.1 + 2, duration: 1, pitch: 64, syllable: 's5' },  // a la vez que A
      ] },
    ],
  };
}

const brilla = () => loadSong(JSON.parse(readFileSync(new URL('../../assets/songs/brilla.canto.json', import.meta.url), 'utf8')));

/** Canta `unit` con desviación `cents` en bloques de `step` s (tiempo de canción). */
function sing(run, from, to, midi, cents = 0, step = 0.02, level = 0.05) {
  for (let t = from + step; t <= to + 1e-9; t += step) run.feed(t, step, midi === null ? null : hz(midi, cents), level);
}

test('modelo: letra, palabras, sílabas y validación', () => {
  const song = loadSong(duetData());
  assert.equal(song.word('w2').text, 'amor');
  assert.equal(song.syllable('s4').wordId, 'w2');
  assert.equal(song.syllable('s4').last, true);
  assert.equal(song.line('l2').text, 'amor');
  assert.equal(song.duration, 6.1);
  const bad = duetData();
  bad.voices[0].events[0].syllable = 'nope';
  assert.throws(() => loadSong(bad), SongError);
  const overlap = duetData();
  overlap.voices[0].events[1].start = 1.2;
  assert.throws(() => loadSong(overlap), /solapadas/);
});

test('una sola voz: sin opciones de dueto', () => {
  const song = brilla();
  assert.equal(partsFor(song).length, 1);
  assert.equal(targetsFor(song).length, 42);
});

test('varias voces: parte A, parte B y «cántala entera» con prioridad explícita', () => {
  const song = loadSong(duetData());
  assert.deepEqual(partsFor(song).map((p) => p.label), ['Voz A', 'Voz B', 'Cántala entera']);
  assert.deepEqual(targetsFor(song, { mode: 'voice', voiceId: 'A' }).map((e) => e.id), ['a1', 'a2', 'a3']);
  assert.deepEqual(targetsFor(song, { mode: 'voice', voiceId: 'B' }).map((e) => e.id), ['b1', 'b2', 'b3', 'b4']);
  // Entera: cuando sólo canta A → A; sólo B → B; juntas → la prioritaria (A).
  assert.deepEqual(targetsFor(song, { mode: 'full' }).map((e) => e.id), ['a1', 'a2', 'b1', 'b2', 'b3', 'a3']);
});

test('melisma: una sílaba, varias notas; la palabra se sigue leyendo entera', () => {
  const song = loadSong(duetData());
  const units = unitsFor(song, targetsFor(song, { mode: 'voice', voiceId: 'B' }));
  const mor = units.find((u) => u.text === 'mor');
  assert.deepEqual(mor.events.map((e) => e.pitch), [57, 59]);
  assert.equal(mor.start, 3.5);
  assert.ok(Math.abs(mor.end - 4.1) < 1e-9);
  assert.equal(song.word(mor.wordId).text, 'amor');
  const b = brilla();
  const melismas = unitsFor(b, targetsFor(b)).filter((u) => u.events.length > 1);
  assert.deepEqual(melismas.map((u) => [u.text, u.events.map((e) => e.pitch)]), [['mor', [50, 48]]]);
});

test('transposición explícita y extensión', () => {
  const song = loadSong(duetData());
  const units = unitsFor(song, targetsFor(song, { mode: 'voice', voiceId: 'A' }), -12);
  assert.deepEqual(units.map((u) => u.events[0].pitch), [48, 50, 55]);
  assert.deepEqual(pitchRange(units), [48, 55]);
});

test('clasificación por bloque: encima, debajo, afinado, silencio y ruido', () => {
  assert.equal(classifyBlock(hz(60, 20), 0.05, 60, 50).kind, 'in');
  assert.equal(classifyBlock(hz(60, -80), 0.05, 60, 50).kind, 'low');
  assert.equal(classifyBlock(hz(60, 80), 0.05, 60, 50).kind, 'high');
  assert.equal(classifyBlock(hz(60), 0.0005, 60, 50).kind, 'silence');
  assert.equal(classifyBlock(null, 0.05, 60, 50).kind, 'unclear');
  assert.equal(classifyBlock(hz(72), 0.05, 60, 50).kind, 'high');     // octava ≠ acierto
  assert.equal(classifyBlock(hz(60, 45), 0.05, 60, 30).kind, 'high'); // tolerancia más estricta
});

test('feedback visual: histéresis y permanencia evitan el parpadeo en el borde', () => {
  const fb = new VoiceFeedback({ tolerance: 50, hysteresis: 15, dwell: 0.09 });
  const states = [];
  // Cantamos oscilando alrededor del borde (45–58 cents) durante 1 s.
  for (let i = 0; i < 50; i++) {
    const cents = i % 2 ? 58 : 45;
    states.push(fb.push(i * 0.02, 60 + cents / 100, 60).state);
  }
  assert.ok(states.every((s) => s === 'in'), states.join(','));
  // Una subida clara y sostenida sí cambia a naranja, tras `dwell`.
  let last;
  for (let i = 0; i < 20; i++) last = fb.push(1 + i * 0.02, 61, 60);
  assert.equal(last.state, 'high');
  // Nueva nota objetivo: el color se recalcula en el acto.
  assert.equal(fb.push(1.5, 61, 61).state, 'in');
  // Sin voz un rato: la línea se corta.
  fb.push(1.52, null, 61);
  assert.equal(fb.push(1.8, null, 61).break, true);
});

test('feedback visual: una lectura suelta errónea (octava) no mueve la línea', () => {
  const fb = new VoiceFeedback({ tolerance: 50, hysteresis: 15, dwell: 0.09 });
  for (let i = 0; i < 5; i++) fb.push(i * 0.02, 60, 60);
  const spike = fb.push(0.1, 72, 60);
  assert.ok(Math.abs(spike.midi - 60) < 0.01, String(spike.midi));
  assert.equal(spike.state, 'in');
});

test('acierto consolidado: rozar la nota no basta; mantenerla sí', () => {
  const song = brilla();
  const units = unitsFor(song, targetsFor(song));
  const u = units[6];                       // «voz», nota larga
  const params = difficulty('inicial');
  const run = new SongRun(units, params);
  sing(run, u.start, u.start + 0.1, u.events[0].pitch);   // 100 ms afinado
  sing(run, u.start + 0.1, u.end, u.events[0].pitch, 150);
  assert.equal(run.units[6].hit, false);
  run.update(u.end + 1);
  assert.equal(run.units[6].judgement, 'miss');

  const run2 = new SongRun(units, params);
  let celebrated = null;
  run2.addEventListener('hit', (e) => { celebrated = e.detail.text; });
  sing(run2, u.start, u.end, u.events[0].pitch, 10);
  assert.equal(celebrated, 'voz');
  assert.ok(run2.progress(run2.units[6]) === 1);
});

test('estabilidad: afinado a trozos sin tramo continuo no consolida', () => {
  const song = brilla();
  const units = unitsFor(song, targetsFor(song));
  const u = units[6];
  const run = new SongRun(units, difficulty('avanzado'));
  const p = u.events[0].pitch;
  // Alterna 40 ms afinado / 40 ms desafinado: 50 % afinado pero nunca estable.
  for (let t = u.start; t < u.end; t += 0.08) {
    sing(run, t, t + 0.04, p, 0);
    sing(run, t + 0.04, t + 0.08, p, 90);
  }
  assert.equal(run.units[6].hit, false);
});

test('melisma: cada nota se evalúa con su propia altura', () => {
  const song = brilla();
  const units = unitsFor(song, targetsFor(song));
  const mor = units.find((x) => x.events.length > 1);
  const [re, doNote] = mor.events;
  const run = new SongRun(units, difficulty('inicial'));
  sing(run, re.start, re.end, re.pitch);
  sing(run, doNote.start, doNote.end, doNote.pitch);
  assert.equal(run.units[mor.index].hit, true);
  const flat = new SongRun(units, difficulty('inicial'));
  sing(flat, re.start, doNote.end, re.pitch);         // se queda en Re: la segunda nota falla
  flat.update(mor.end + 1);
  assert.equal(flat.units[mor.index].hit, false);
});

test('cada instante cuenta una vez; volumen no multiplica; silencio ≠ fallo', () => {
  const song = brilla();
  const units = unitsFor(song, targetsFor(song));
  const u = units[0];
  const run = new SongRun(units, difficulty('inicial'));
  run.feed(u.start + 0.3, 0.3, hz(u.events[0].pitch), 0.05);
  run.feed(u.start + 0.3, 0.3, hz(u.events[0].pitch), 0.05);
  assert.ok(Math.abs(run.units[0].correct - 0.3) < 1e-9);
  const loud = new SongRun(units, difficulty('inicial'));
  sing(loud, u.start, u.end, u.events[0].pitch, 0, 0.02, 0.9);
  const soft = new SongRun(units, difficulty('inicial'));
  sing(soft, u.start, u.end, u.events[0].pitch, 0, 0.02, 0.004);
  loud.update(u.end + 1); soft.update(u.end + 1);
  assert.equal(loud.score, soft.score);
  const quiet = new SongRun(units, difficulty('inicial'));
  sing(quiet, u.start, u.end, null, 0, 0.02, 0);
  quiet.update(u.end + 1);
  assert.equal(quiet.units[0].judgement, 'silent');
  assert.equal(quiet.combo, 0);
});

test('dificultad: más exigente con la misma interpretación', () => {
  const song = brilla();
  const units = unitsFor(song, targetsFor(song));
  const u = units[6];
  const results = {};
  for (const key of ['inicial', 'reto']) {
    const run = new SongRun(units, difficulty(key));
    sing(run, u.start, u.end, u.events[0].pitch, 35);   // 35 cents alto
    results[key] = run.units[6].hit;
  }
  assert.deepEqual(results, { inicial: true, reto: false });
  assert.ok(DIFFICULTIES.reto.lookahead < DIFFICULTIES.inicial.lookahead);
  assert.equal(difficulty('inicial', { tolerance: 45 }).tolerance, 45);
  assert.equal(suggestNext('inicial', [0.85, 0.9]), 'intermedio');
  assert.equal(suggestNext('inicial', [0.6, 0.9]), null);
  assert.equal(suggestNext('reto', [1, 1]), null);
});

test('resultado: afinación, timing, racha y la frase que más costó (con su texto)', () => {
  const song = brilla();
  const units = unitsFor(song, targetsFor(song));
  const run = new SongRun(units, difficulty('inicial'), (id) => song.line(id).text);
  for (const u of units) {
    const badLine = u.lineId === 'l3';
    for (const e of u.events) sing(run, e.start + 0.04, e.end, e.pitch, badLine ? -120 : 5);   // entra 40 ms tarde
  }
  run.update(song.duration + 1);
  const s = run.summary();
  const l3 = units.filter((u) => u.lineId === 'l3').length;
  assert.equal(s.hits, units.length - l3);
  assert.equal(s.misses, l3);
  assert.equal(s.hardest.text, 'sube despacio y ven');
  assert.ok(Math.abs(s.timing - 0.04) < 0.021, String(s.timing));
  assert.ok(s.pitchAccuracy > 0.8 && s.pitchAccuracy < 0.9, String(s.pitchAccuracy));
  assert.equal(s.bestCombo, units.filter((u) => ['l4', 'l5', 'l6'].includes(u.lineId)).length);
});

test('tesitura: informa de fragmentos fuera de rango sin cambiar notas', () => {
  const song = brilla();
  const units = unitsFor(song, targetsFor(song));
  const frags = outOfRange(units, { comfortableLow: 48, comfortableHigh: 55, reachableLow: null, reachableHigh: 56 });
  assert.deepEqual(frags.map((f) => [f.lineId, f.above, f.reachable]), [['l1', true, false], ['l5', true, false]]);
  assert.equal(units.find((u) => u.lineId === 'l1' && u.text === 've').events[0].pitch, 57);   // intacta
  assert.deepEqual(outOfRange(units, null), []);
});
