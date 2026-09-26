// Puntuación del modo canción, relacionada siempre con la letra.
//
// Unidad jugable = una sílaba de una voz (con una o varias notas: melisma).
// Reglas (mismo espíritu que las rondas de escalas):
// - Sólo audio nuevo: cada instante cuenta una vez.
// - Cada bloque se compara con la nota que suena en ese instante (en un melisma,
//   cada nota con su propia altura). Sin suavizado: la evaluación es honesta.
// - El volumen sólo separa silencio de sonido; no multiplica puntos.
// - Una sílaba se da por ACERTADA (momento de celebración) cuando:
//     tiempo afinado / duración efectiva ≥ requiredFraction   Y
//     mejor tramo afinado continuo  / duración efectiva ≥ minStreak.
//   La duración efectiva descuenta `late` (margen para entrar). Rozar la nota
//   100 ms no basta.
// - Al terminar la sílaba (+`late`): 'hit', 'miss' (se cantó, pero no lo bastante
//   afinado) o 'silent' (casi no se cantó). Los errores no se castigan en pantalla.
//
// Tiempos en segundos de CANCIÓN (ya compensada la latencia por quien llama).

import { midiFloat } from '../pitch/notes.js';

export const SILENCE_RMS = 0.002;
export const PLAUSIBLE_CENTS = 1900;
export const STREAK_GAP = 0.06;    // un hueco breve (consonante) no rompe el tramo continuo

export function classifyBlock(frequency, level, target, tolerance) {
  if (level < SILENCE_RMS) return { kind: 'silence', error: null };
  if (frequency == null || frequency <= 0) return { kind: 'unclear', error: null };
  const error = (midiFloat(frequency) - target) * 100;
  if (Math.abs(error) > PLAUSIBLE_CENTS) return { kind: 'unclear', error: null };
  if (Math.abs(error) <= tolerance) return { kind: 'in', error };
  return { kind: error < 0 ? 'low' : 'high', error };
}

export class SongRun extends EventTarget {
  /**
   * @param units  unidades de parts.unitsFor (con transposición ya aplicada)
   * @param params dificultad (difficulty.js)
   * @param lineText función lineId → texto de la frase (para resultados humanos)
   */
  constructor(units, params, lineText = () => '') {
    super();
    this.params = params;
    this.lineText = lineText;
    this.units = units.map((u) => ({
      ...u,
      effective: Math.max(0.1, u.duration - Math.min(params.late, u.duration * 0.4)),
      correct: 0, voiced: 0, streak: 0, bestStreak: 0, lastIn: null,
      firstIn: null, errors: [], hit: false, judgement: null,
    }));
    this.countedUntil = -Infinity;
    this.combo = 0;
    this.bestCombo = 0;
    this.score = 0;
  }

  /** Nota objetivo que suena en `t` (o null). */
  targetAt(t) {
    for (const u of this.units) {
      if (t < u.start - this.params.early) break;
      if (t <= u.end) {
        for (const e of u.events) if (t >= e.start - this.params.early && t <= e.end) return { unit: u, event: e };
        // En un hueco dentro de un melisma se sigue la nota más cercana.
        const near = u.events.reduce((a, e) => (Math.abs(t - e.start) < Math.abs(t - a.start) ? e : a));
        return { unit: u, event: near };
      }
    }
    return null;
  }

  /** Unidad actual o próxima (para el renderer). */
  unitAt(t) {
    return this.units.find((u) => t <= u.end + this.params.late) ?? null;
  }

  /** Procesa un bloque que termina en `songTime` (s de canción). */
  feed(songTime, duration, frequency, level) {
    const end = songTime;
    const begin = Math.max(end - duration, this.countedUntil);
    if (end <= begin) return null;
    this.countedUntil = end;
    const mid = (begin + end) / 2;
    const found = this.targetAt(mid);
    if (!found || found.unit.judgement) return null;
    const { unit, event } = found;
    const span = end - begin;
    const block = classifyBlock(frequency, level, event.pitch, this.params.tolerance);
    if (block.kind === 'in' || block.kind === 'low' || block.kind === 'high') {
      unit.voiced += span;
      unit.errors.push([span, block.error]);
    }
    if (block.kind === 'in') {
      unit.correct += span;
      if (unit.firstIn === null) unit.firstIn = begin;
      unit.streak = unit.lastIn !== null && begin - unit.lastIn <= STREAK_GAP ? unit.streak + span : span;
      unit.lastIn = end;
      unit.bestStreak = Math.max(unit.bestStreak, unit.streak);
    }
    if (!unit.hit && this.consolidated(unit)) {
      unit.hit = true;
      this.dispatchEvent(new CustomEvent('hit', { detail: unit }));
    }
    return block;
  }

  consolidated(u) {
    return u.correct / u.effective >= this.params.requiredFraction - 1e-9
      && u.bestStreak / u.effective >= this.params.minStreak - 1e-9;
  }

  /** 0–1: cuánto falta para dar la sílaba por acertada (relleno verde progresivo). */
  progress(u) {
    return Math.min(1, u.correct / (u.effective * this.params.requiredFraction));
  }

  /** Cierra las sílabas terminadas. Devuelve las recién juzgadas. */
  update(songTime) {
    const judged = [];
    for (const u of this.units) {
      if (u.judgement || songTime < u.end + this.params.late) continue;
      if (u.hit) u.judgement = 'hit';
      else u.judgement = u.voiced >= 0.25 * u.effective ? 'miss' : 'silent';
      if (u.judgement === 'hit') {
        this.combo += 1;
        this.bestCombo = Math.max(this.bestCombo, this.combo);
        this.score += Math.round(1000 * Math.min(1, u.correct / u.effective));
      } else if (u.judgement === 'miss') {
        this.combo = 0;
      }
      judged.push(u);
    }
    return judged;
  }

  get finished() { return this.units.every((u) => u.judgement); }

  summary() {
    const units = this.units;
    const hits = units.filter((u) => u.judgement === 'hit').length;
    const voiced = units.reduce((s, u) => s + u.voiced, 0);
    const correct = units.reduce((s, u) => s + u.correct, 0);
    const onsets = units.filter((u) => u.judgement === 'hit' && u.firstIn !== null).map((u) => u.firstIn - u.start).sort((a, b) => a - b);
    const timing = onsets.length ? onsets[onsets.length >> 1] : null;
    // Frase que más costó: menor proporción de sílabas acertadas (mín. 2 sílabas).
    const byLine = new Map();
    for (const u of units) {
      if (!u.lineId) continue;
      const entry = byLine.get(u.lineId) ?? { lineId: u.lineId, total: 0, hits: 0, correct: 0, voiced: 0 };
      entry.total += 1;
      entry.hits += u.judgement === 'hit' ? 1 : 0;
      entry.correct += u.correct;
      entry.voiced += u.voiced;
      byLine.set(u.lineId, entry);
    }
    let hardest = null;
    for (const line of byLine.values()) {
      if (line.total < 2 || line.hits === line.total) continue;
      const rate = line.hits / line.total;
      const accuracy = line.voiced ? line.correct / line.voiced : 0;
      if (!hardest || rate < hardest.rate || (rate === hardest.rate && accuracy < hardest.accuracy)) {
        hardest = { lineId: line.lineId, rate, accuracy, text: this.lineText(line.lineId) };
      }
    }
    return {
      units: units.length,
      hits,
      misses: units.filter((u) => u.judgement === 'miss').length,
      silent: units.filter((u) => u.judgement === 'silent').length,
      hitRate: units.length ? hits / units.length : 0,
      pitchAccuracy: voiced > 0.2 ? correct / voiced : null,
      timing,                 // s (mediana): positivo = entras tarde
      bestCombo: this.bestCombo,
      score: this.score,
      hardest,
      difficulty: this.params.key,
    };
  }
}
