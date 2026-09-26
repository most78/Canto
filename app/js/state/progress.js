// Progreso del jugador: tu nota, tu rango, niveles y mapa de tu voz.
// Port de legacy/src/game/progress.py. Mismo formato de datos (JSON), guardado
// en localStorage. La primera vez se importa datos/progreso.json de la versión
// Python si existe, para no perder lo ya jugado.
//
// - Mapa de tu voz: por nota (MIDI absoluto), media móvil del acierto (0–1) y
//   cuántas veces se ha medido. Sin señal clara o sin cantar no cuenta.
// - Niveles: ≥80 % de notas en 2 de 3 intentos desbloquea el siguiente.
// - Rango: empieza en [-2, +5] semitonos respecto a tu nota; sólo crece un
//   semitono por un borde si esa nota se acierta bien (media ≥0,7 en ≥3
//   mediciones) Y respondes que la ronda fue cómoda.

import { LEVELS } from '../game/levels.js';

export const STORAGE_KEY = 'canto.progreso';
export const START_LO = -2;
export const START_HI = 5;
const EMA_ALPHA = 0.35;
const GROW_EMA = 0.7;
const GROW_SAMPLES = 3;
const FIELDS = ['anchor_midi', 'lo', 'hi', 'unlocked', 'history', 'notes'];

const round4 = (x) => Math.round(x * 1e4) / 1e4;

export class Progress {
  constructor(data = {}, storage = null) {
    this.anchor_midi = data.anchor_midi ?? null;
    this.lo = data.lo ?? START_LO;
    this.hi = data.hi ?? START_HI;
    this.unlocked = data.unlocked ?? 0;
    this.history = data.history ?? {};   // nivel -> [[puntuaciones de intentos], …]
    this.notes = data.notes ?? {};       // 'midi' -> {ema, n}
    this.storage = storage;
  }

  /** Carga de `storage` (localStorage por defecto). */
  static load(storage = globalThis.localStorage ?? null) {
    let data = {};
    try {
      const raw = storage?.getItem(STORAGE_KEY);
      if (raw) data = JSON.parse(raw);
    } catch { data = {}; }
    return new Progress(data, storage);
  }

  get isEmpty() { return this.anchor_midi === null && !Object.keys(this.notes).length; }

  toJSON() {
    return Object.fromEntries(FIELDS.map((k) => [k, this[k]]));
  }

  /** Sustituye los datos (p. ej. importados del progreso de la versión Python). */
  replace(data) {
    const fresh = new Progress(data, this.storage);
    for (const k of FIELDS) this[k] = fresh[k];
    this.save();
  }

  save() {
    try { this.storage?.setItem(STORAGE_KEY, JSON.stringify(this.toJSON())); } catch { /* sin almacenamiento */ }
  }

  // --- nota base y rango ---------------------------------------------
  /** Nueva nota base: el rango conserva sus notas absolutas. */
  setAnchor(midi) {
    if (this.anchor_midi !== null) {
      const delta = midi - this.anchor_midi;
      this.lo -= delta;
      this.hi -= delta;
    }
    this.anchor_midi = midi;
    this.lo = Math.min(this.lo, 0);
    this.hi = Math.max(this.hi, Math.max(...LEVELS[0].pattern));
  }

  rangeMidi() { return [this.anchor_midi + this.lo, this.anchor_midi + this.hi]; }

  stat(midi) { return this.notes[String(midi)] ?? null; }

  // --- resultados ----------------------------------------------------
  /** noteResults: [[midi, ratio 0–1]] de notas medidas. Devuelve si desbloquea un nivel. */
  recordRound(levelIndex, summary, noteResults) {
    const key = LEVELS[levelIndex].key;
    const list = (this.history[key] ??= []);
    list.push(summary.attemptScores.map((s) => Math.round(s * 1000) / 1000));
    this.history[key] = list.slice(-10);
    for (const [midi, ratio] of noteResults) {
      const id = String(midi);
      const entry = (this.notes[id] ??= { ema: ratio, n: 0 });
      if (entry.n) entry.ema = entry.ema * (1 - EMA_ALPHA) + ratio * EMA_ALPHA;
      entry.n += 1;
      entry.ema = round4(entry.ema);
    }
    let unlockedNew = false;
    if (summary.passed && levelIndex === this.unlocked && this.unlocked < LEVELS.length - 1) {
      this.unlocked += 1;
      unlockedNew = true;
    }
    this.save();
    return unlockedNew;
  }

  /** Tras una ronda cómoda: amplía cada borde que se acierte bien. → [[lado, midi]]. */
  growRange() {
    const grown = [];
    const [low, high] = this.rangeMidi();
    for (const [side, midi] of [['agudo', high], ['grave', low]]) {
      const entry = this.stat(midi);
      if (entry && entry.n >= GROW_SAMPLES && entry.ema >= GROW_EMA) {
        if (side === 'agudo') { this.hi += 1; grown.push([side, high + 1]); }
        else { this.lo -= 1; grown.push([side, low - 1]); }
      }
    }
    if (grown.length) this.save();
    return grown;
  }
}

/** Si no hay progreso web, intenta importar el de la versión Python (datos/progreso.json). */
export async function importLegacyProgress(progress, fetcher = globalThis.fetch) {
  if (!progress.isEmpty || !fetcher) return false;
  try {
    const response = await fetcher('datos/progreso.json', { cache: 'no-store' });
    if (!response.ok) return false;
    progress.replace(await response.json());
    return true;
  } catch {
    return false;
  }
}
