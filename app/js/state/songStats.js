// Historial del modo canción por canción y dificultad (localStorage).
// Sirve para sugerir subir de dificultad (difficulty.suggestNext) y recordar récords.

export const STORAGE_KEY = 'canto.canciones';

export class SongStats {
  constructor(storage = globalThis.localStorage ?? null) {
    this.storage = storage;
    try { this.data = JSON.parse(storage?.getItem(STORAGE_KEY) ?? '{}'); } catch { this.data = {}; }
  }

  entry(songId, level) {
    this.data[songId] ??= {};
    return (this.data[songId][level] ??= { recent: [], best: 0, bestCombo: 0 });
  }

  record(songId, level, summary) {
    const e = this.entry(songId, level);
    e.recent = [...e.recent, Math.round(summary.hitRate * 1000) / 1000].slice(-5);
    const newBest = summary.score > e.best;
    e.best = Math.max(e.best, summary.score);
    e.bestCombo = Math.max(e.bestCombo, summary.bestCombo);
    try { this.storage?.setItem(STORAGE_KEY, JSON.stringify(this.data)); } catch { /* sin almacenamiento */ }
    return { newBest, recent: e.recent };
  }

  recent(songId, level) { return this.data[songId]?.[level]?.recent ?? []; }
}
