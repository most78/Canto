// Modo Canción: elegir → cantar → resultado. Lógica sin DOM.
//
// Sincronización (todo en el reloj del AudioContext):
//   - Lo que OYES en el instante c es la canción en  player.songTime(c − latenciaSalida).
//   - Tu voz del bloque que termina en c corresponde a lo que oías antes:
//       songTimeVoz = player.songTime(c − latencia),   con
//       latencia = salida + entrada + media ventana de análisis (+ ajuste manual).
//   El ajuste manual (± ms) se guarda en localStorage para calibrar a oído.
//
// Eventos: 'change', 'screen', 'hit' (detail: unidad), 'results'.

import { loadSong } from '../songs/model.js';
import { partsFor, targetsFor, unitsFor } from '../songs/parts.js';
import { difficulty, suggestNext, ORDER, DIFFICULTIES } from '../songs/difficulty.js';
import { VoiceFeedback } from '../songs/feedback.js';
import { SongRun, SILENCE_RMS } from '../songs/songRun.js';
import { outOfRange, rangeFromProgress } from '../songs/tessitura.js';
import { midiFloat, noteName } from '../pitch/notes.js';
import { WINDOW_SECONDS } from '../audio/mic.js';

export const INPUT_LATENCY_GUESS = 0.02;   // s: tarjeta/driver de entrada (estimación)
export const TRAIL_SECONDS = 8;            // cuánta línea de voz se conserva
const LATENCY_KEY = 'canto.latencia.ajuste';

export class SingSession extends EventTarget {
  constructor({ progress, stats, player, clock, outputLatency = () => 0, storage = globalThis.localStorage ?? null, fetcher = (...args) => fetch(...args) }) {
    super();
    this.progress = progress;
    this.stats = stats;
    this.player = player;
    this.clock = clock;
    this.outputLatency = outputLatency;
    this.storage = storage;
    this.fetcher = fetcher;
    this.screen = 'pick';
    this.entry = null;
    this.song = null;
    this.error = '';
    this.partIndex = 0;
    this.level = 'inicial';
    this.transpose = 0;
    this.adjust = Number(storage?.getItem?.(LATENCY_KEY) ?? 0) || 0;
    this.run = null;
    this.feedback = null;
    this.units = [];
    this.trail = [];           // puntos de la línea de voz {time, midi, state, break}
    this.flashes = [];         // aciertos recientes para la celebración visual
    this.results = null;
    this.visible = true;
    this.micOn = false;
  }

  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }

  setScreen(screen) {
    if (this.screen === screen) return;
    this.screen = screen;
    this.emit('screen', screen);
  }

  // ---------------------------------------------------------------- elegir
  async select(entry) {
    this.entry = entry;
    this.song = null;
    this.error = '';
    this.partIndex = 0;
    this.transpose = 0;
    if (entry?.playable) {
      try {
        this.song = loadSong(await (await this.fetcher(entry.dataUrl, { cache: 'no-store' })).json());
      } catch (error) {
        this.error = error.message;
      }
    }
    this.emit('change');
  }

  get parts() { return this.song ? partsFor(this.song) : []; }
  get part() { return this.parts[this.partIndex] ?? null; }
  get params() { return difficulty(this.level); }
  get latency() { return this.outputLatency() + INPUT_LATENCY_GUESS + WINDOW_SECONDS / 2 + this.adjust; }

  setPart(i) { this.partIndex = i; this.emit('change'); }
  setLevel(key) { if (DIFFICULTIES[key]) this.level = key; this.emit('change'); }
  setTranspose(semitones) { this.transpose = semitones; this.emit('change'); }
  setMic(on) { this.micOn = on; this.emit('change'); }

  nudgeLatency(ms) {
    this.adjust = Math.round((this.adjust + ms / 1000) * 1000) / 1000;
    try { this.storage?.setItem(LATENCY_KEY, String(this.adjust)); } catch { /* sin almacenamiento */ }
    this.emit('change');
  }

  /** Lo que la pantalla de elegir necesita mostrar. */
  pickView() {
    const song = this.song;
    const units = song ? unitsFor(song, targetsFor(song, this.part), this.transpose) : [];
    const range = rangeFromProgress(this.progress);
    const fragments = outOfRange(units, range);
    const suggestion = song ? suggestNext(this.level, this.stats.recent(song.id, this.level)) : null;
    return {
      entry: this.entry,
      song,
      error: this.error,
      parts: this.parts.map((p, i) => ({ label: p.label, selected: i === this.partIndex })),
      levels: ORDER.map((k) => ({ key: k, name: DIFFICULTIES[k].name, selected: k === this.level })),
      transpose: this.transpose,
      adjustMs: Math.round(this.adjust * 1000),
      outOfRange: fragments.map((f) => ({ text: f.lineId ? song.line(f.lineId).text : '', above: f.above, below: f.below })),
      rangeLabel: range ? `${noteName(range.comfortableLow)} – ${noteName(range.comfortableHigh)}` : null,
      suggestion: suggestion ? DIFFICULTIES[suggestion].name : null,
      canSing: !!song && this.micOn,
    };
  }

  // ---------------------------------------------------------------- cantar
  async start() {
    if (!this.song || !this.micOn) return;
    const song = this.song;
    this.units = unitsFor(song, targetsFor(song, this.part), this.transpose);
    this.run = new SongRun(this.units, this.params, (id) => song.line(id)?.text ?? '');
    this.run.addEventListener('hit', (e) => {
      this.flashes.push({ unit: e.detail, at: this.visualTime() });
      this.emit('hit', e.detail);
    });
    this.feedback = new VoiceFeedback(this.params);
    this.trail = [];
    this.flashes = [];
    this.results = null;
    await this.player.load(song);
    this.player.start(0);
    this.setScreen('sing');
  }

  get paused() { return this.screen === 'sing' && !this.player.playing; }

  togglePause() {
    if (this.screen !== 'sing') return;
    if (this.player.playing) this.player.pause(this.clock());
    else if (this.micOn) {
      this.feedback.reset();
      this.trail.push({ time: this.player.pausedAt, midi: null, state: 'none', break: true });
      this.player.resume();
    }
    this.emit('change');
  }

  setVisible(visible) {
    this.visible = visible;
    if (!visible && this.screen === 'sing' && this.player.playing) this.togglePause();
  }

  /** Tiempo de canción que estás oyendo ahora (para dibujar). */
  visualTime() { return this.player.songTime(this.clock() - this.outputLatency()); }

  /** Bloque del micrófono (marca en el reloj de audio). */
  feed(stamp, duration, frequency, level) {
    if (this.screen !== 'sing' || !this.player.playing || !this.visible) return;
    const t = this.player.songTime(stamp - this.latency);
    if (t < 0) return;
    const voiced = frequency != null && level >= SILENCE_RMS;
    const target = this.run.targetAt(t);
    const point = this.feedback.push(t, voiced ? midiFloat(frequency) : null, target ? target.event.pitch : null);
    this.trail.push(point);
    while (this.trail.length && this.trail[0].time < t - TRAIL_SECONDS) this.trail.shift();
    this.run.feed(t, duration, frequency, level);
  }

  /** Cada fotograma: cierra sílabas y detecta el final. */
  tick() {
    if (this.screen !== 'sing' || !this.player.playing) return;
    const t = this.player.songTime(this.clock() - this.latency);
    this.run.update(t);
    this.flashes = this.flashes.filter((f) => this.visualTime() - f.at < 1.2);
    if (this.run.finished && t > this.song.duration + 0.8) this.finish();
  }

  stop() {
    if (this.screen !== 'sing') return;
    // Terminar antes: sólo cuenta lo que ya ha sonado; lo que no llegó no es un fallo.
    const t = this.player.songTime(this.clock() - this.latency);
    this.run.units = this.run.units.filter((u) => u.start <= t);
    this.run.update(Infinity);
    this.finish();
  }

  finish() {
    this.player.stop();
    const summary = this.run.summary();
    const { newBest, recent } = this.stats.record(this.song.id, this.level, summary);
    const next = suggestNext(this.level, recent);
    this.results = { ...summary, newBest, suggestion: next ? DIFFICULTIES[next].name : null, levelName: this.params.name, title: this.song.metadata.title };
    this.setScreen('results');
    this.emit('results', this.results);
  }

  backToPick() {
    this.player.stop();
    this.setScreen('pick');
    this.emit('change');
  }
}
