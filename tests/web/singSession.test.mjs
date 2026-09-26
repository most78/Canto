// Controlador del modo canción (sin navegador) y catálogo de canciones.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { SingSession, INPUT_LATENCY_GUESS } from '../../app/js/exercises/singSong.js';
import { localEntries, MISSING_DATA } from '../../app/js/songs/catalog.js';
import { SongStats } from '../../app/js/state/songStats.js';
import { Progress } from '../../app/js/state/progress.js';
import { WINDOW_SECONDS } from '../../app/js/audio/mic.js';
import { midiFrequency } from '../../app/js/pitch/notes.js';

const BRILLA = JSON.parse(readFileSync(new URL('../../assets/songs/brilla.canto.json', import.meta.url), 'utf8'));

function memoryStorage() {
  const data = new Map();
  return { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => data.set(k, v) };
}

/** Reproductor falso: la canción empieza en el instante `t0` del reloj. */
class FakePlayer {
  constructor(clock) { this.clock = clock; this.playing = false; this.pausedAt = 0; this.t0 = 0; }
  async load() {}
  start(from = 0) { this.t0 = this.clock.t - from; this.playing = true; }
  pause(c) { this.pausedAt = c - this.t0; this.playing = false; return this.pausedAt; }
  resume() { this.start(this.pausedAt); }
  stop() { this.playing = false; }
  songTime(c) { return this.playing ? c - this.t0 : this.pausedAt; }
}

async function setup(outputLatency = 0.03) {
  const clock = { t: 500 };
  const storage = memoryStorage();
  const session = new SingSession({
    progress: Progress.load(memoryStorage()), stats: new SongStats(storage), player: new FakePlayer(clock),
    clock: () => clock.t, outputLatency: () => outputLatency, storage,
    fetcher: async () => ({ json: async () => BRILLA }),
  });
  await session.select({ id: 'builtin:brilla', title: 'Brilla', playable: true, dataUrl: 'x', source: 'builtin' });
  session.setMic(true);
  return { session, clock, storage };
}

/** Canta la canción entera como la oyes: la voz llega con la latencia simulada. */
function perform(session, clock, { cents = 5, latency, untilSong = Infinity } = {}) {
  const step = 0.0213;
  const units = session.units;
  while (session.screen === 'sing') {
    clock.t += step;
    const heard = clock.t - session.player.t0 - latency;   // lo que se oía cuando se cantó
    if (heard > untilSong) break;
    const target = units.flatMap((u) => u.events).find((e) => heard >= e.start && heard <= e.end);
    session.feed(clock.t, step, target ? midiFrequency(target.pitch + cents / 100) : null, target ? 0.05 : 0);
    session.tick();
    if (clock.t > 600) break;
  }
}

test('una sola voz: sin elegir parte; latencia = salida + entrada + media ventana + ajuste', async () => {
  const { session } = await setup(0.03);
  const view = session.pickView();
  assert.equal(view.parts.length, 1);
  assert.ok(view.canSing);
  assert.ok(Math.abs(session.latency - (0.03 + INPUT_LATENCY_GUESS + WINDOW_SECONDS / 2)) < 1e-9);
  session.nudgeLatency(20);
  assert.ok(Math.abs(session.pickView().adjustMs - 20) < 1e-9);
});

test('canción completa con latencia compensada: casi todo acertado, resultado y récord', async () => {
  const { session, clock } = await setup(0.03);
  await session.start();
  assert.equal(session.screen, 'sing');
  const hits = [];
  session.addEventListener('hit', (e) => hits.push(e.detail.text));
  perform(session, clock, { latency: session.latency });
  assert.equal(session.screen, 'results');
  const r = session.results;
  assert.ok(r.hitRate > 0.95, String(r.hitRate));
  assert.ok(hits.includes('mor'));                       // el melisma también se celebra
  assert.equal(r.newBest, true);
  assert.equal(r.hardest, null);
  assert.ok(session.trail.some((p) => p.state === 'in'));
});

test('sin compensar la latencia (voz 0,25 s tarde) se nota en el timing', async () => {
  const { session, clock } = await setup(0);
  await session.start();
  perform(session, clock, { latency: session.latency + 0.25 });
  assert.ok(session.results.timing > 0.2, String(session.results.timing));
});

test('pausa congela la canción; terminar antes no cuenta lo que no ha sonado', async () => {
  const { session, clock } = await setup(0);
  await session.start();
  perform(session, clock, { latency: session.latency, untilSong: 8 });
  session.togglePause();
  assert.equal(session.paused, true);
  const frozen = session.visualTime();
  clock.t += 3;
  assert.equal(session.visualTime(), frozen);
  session.togglePause();
  assert.equal(session.paused, false);
  session.stop();
  const r = session.results;
  assert.ok(r.units < 20, String(r.units));             // sólo las sílabas que ya sonaron
  assert.ok(r.hitRate > 0.8, String(r.hitRate));
});

test('sugiere subir de nivel tras dos interpretaciones muy buenas', async () => {
  const { session, clock } = await setup(0);
  for (let i = 0; i < 2; i++) {
    await session.start();
    perform(session, clock, { latency: session.latency });
  }
  assert.equal(session.results.suggestion, 'Intermedio');
  assert.equal(session.pickView().suggestion, 'Intermedio');
});

test('catálogo: detecta los datos que faltan para cantar una canción local', () => {
  const html = `<ul><li><a href="Rayden%20-%20Cancion.m4a">x</a></li>
    <li><a href="Otra.mp3">y</a></li><li><a href="Otra.canto.json">z</a></li></ul>`;
  const entries = localEntries(html);
  const rayden = entries.find((e) => e.title === 'Rayden - Cancion');
  assert.equal(rayden.playable, false);
  assert.deepEqual(rayden.missing, MISSING_DATA);
  assert.equal(rayden.expectedData, 'canciones/Rayden - Cancion.canto.json');
  const otra = entries.find((e) => e.title === 'Otra');
  assert.equal(otra.playable, true);
  assert.equal(otra.dataUrl, 'canciones/Otra.canto.json');
});
