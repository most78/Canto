// Puntuación de una ronda de «Escalas»: escuchar una frase al piano y cantarla.
// Port 1:1 de legacy/src/game/note_run.py (mismas constantes y reglas).
//
// Una ronda tiene 3 intentos. En cada uno:
//   1. ESCUCHA: el piano toca la frase. Esas notas («demo») no puntúan y el
//      audio de ese tramo, más una cola, se ignora.
//   2. TU TURNO: las mismas notas llegan a la línea AHORA y se cantan.
//   3. RESPIRA: descanso antes del siguiente intento.
//
// Reglas:
// - Cada nota tiene un objetivo fijo: semitonos respecto a tu nota base.
// - Sólo puntúa audio nuevo: cada instante se cuenta una vez y sólo dentro de la
//   ventana de una nota cantada. Cantar en escucha o descanso no suma.
// - Silencio, sonido sin nota clara y bloques antiguos (anteriores a una pausa)
//   no suman ni cuentan como fallo.
// - El volumen sólo separa silencio de sonido; nunca multiplica puntos.
// - Aguantar más de lo que dura la barra no suma.
//
// El reloj es el de la Web Audio API (AudioContext.currentTime): los bloques del
// micrófono llegan con la marca de ese mismo reloj y el piano se programa en él.

import { centsBetween } from '../pitch/notes.js';

export const TOLERANCE_CENTS = 50;   // zona de acierto por defecto
export const PLAUSIBLE_CENTS = 1900; // más lejos = lectura dudosa
export const SILENCE_RMS = 0.002;    // puerta de silencio de la captura
export const REACTION = 0.25;        // margen para llegar a cada nota
export const JUDGE_DELAY = 0.35;     // espera a bloques tardíos antes de juzgar
export const HINT_PERSISTENCE = 0.4; // una indicación de dirección debe mantenerse 400 ms
export const STALE_AFTER = 0.3;      // sin bloques nuevos = no hay lectura
export const MUTE_TAIL = 0.6;        // apagado del piano + eco + latencia tras la escucha

export const LEAD = 1.0;             // antes de la primera escucha
export const TURN_GAP = 1.6;         // entre escuchar y cantar: «¡tu turno!»
export const REST = 3.0;             // descanso entre intentos
export const PASS_SCORE = 0.8;       // un intento vale con el 80 % de sus notas
export const PASSES_NEEDED = 2;      // … en 2 de los 3 intentos

export const HITS = new Set(['perfect', 'great', 'ok']);
export const JUDGEMENT_TEXT = {
  perfect: '¡Perfecta!',
  great: '¡Muy bien!',
  ok: 'Bien',
  miss_low: 'Grave',
  miss_high: 'Aguda',
  unclear: 'No te oí claro',
  silent: 'Sin cantar',
};

/** Mediana ponderada por segundos de pares [peso, valor]; null sin datos. */
export function weightedMedian(pairs) {
  const sorted = pairs.filter(([w]) => w > 0).map(([w, c]) => [c, w]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const total = sorted.reduce((s, [, w]) => s + w, 0);
  if (total <= 0) return null;
  let acc = 0;
  for (const [c, w] of sorted) {
    acc += w;
    if (acc >= total / 2) return c;
  }
  return null;
}

export class Note {
  constructor(start, end, semitone = 0, attempt = 0, demo = false) {
    this.start = start;
    this.end = end;
    this.semitone = semitone;   // respecto a la nota base
    this.attempt = attempt;
    this.demo = demo;           // la toca el piano: no se puntúa
    this.hit = 0;
    this.low = 0;
    this.high = 0;
    this.unclear = 0;
    this.errors = [];           // [segundos, cents respecto al objetivo]
    this.hitSpans = [];         // tramos acertados, para dibujarlos
    this.judgement = null;
  }

  get target() { return this.semitone * 100; }
  get duration() { return this.end - this.start; }
  /** Fracción acertada de la nota, descontando el margen de reacción. */
  get ratio() { return Math.min(1, this.hit / Math.max(0.1, this.duration - REACTION)); }
  get measured() { return this.hit + this.low + this.high; }
  get points() { return HITS.has(this.judgement) ? Math.round(1000 * this.ratio) : 0; }

  judge() {
    const d = this.duration;
    if (this.ratio >= 0.75) this.judgement = 'perfect';
    else if (this.ratio >= 0.45) this.judgement = 'great';
    else if (this.ratio >= 0.15) this.judgement = 'ok';
    else if (this.measured >= 0.25 * d) this.judgement = this.low >= this.high ? 'miss_low' : 'miss_high';
    else if (this.unclear >= 0.25 * d) this.judgement = 'unclear';
    else this.judgement = 'silent';
    return this.judgement;
  }
}

/**
 * Tipo de lectura y cents respecto a la nota base.
 * Con targetCents === null no hay nota que cantar: la voz se muestra ('free') sin juzgarla.
 */
export function classify(frequency, level, anchor, targetCents = 0, tolerance = TOLERANCE_CENTS) {
  if (level < SILENCE_RMS) return ['silence', null];
  if (frequency == null || frequency <= 0) return ['unclear', null];
  const cents = centsBetween(frequency, anchor);
  if (targetCents === null) return Math.abs(cents) <= PLAUSIBLE_CENTS ? ['free', cents] : ['unclear', null];
  const error = cents - targetCents;
  if (Math.abs(error) > PLAUSIBLE_CENTS) return ['unclear', null];
  if (Math.abs(error) <= tolerance) return ['hit', cents];
  return [error < 0 ? 'low' : 'high', cents];
}

export class NoteRun {
  constructor(anchor, notes, tolerance = TOLERANCE_CENTS, cues = [], end = null) {
    this.anchor = anchor;
    this.tolerance = tolerance;
    this.notes = [...notes];
    this.sung = this.notes.filter((n) => !n.demo);
    this.end = end ?? Math.max(...this.notes.map((n) => n.end)) + 1.5;
    this.cues = [...cues].sort((a, b) => a.time - b.time); // {time, notes, muteUntil, attempt}
    this.muted = this.cues.map((c) => [c.time, c.muteUntil + MUTE_TAIL]);
    this.state = 'ready';
    this.origin = null;
    this.pausedTime = 0;
    this.countedUntil = 0;
    this.trail = [];            // lecturas recientes (máx. 240)
    this.live = null;
    this.hintKind = null;
    this.hintSince = 0;
    this.streak = 0;
    this.bestStreak = 0;
    this.events = [];
  }

  // --- reloj -----------------------------------------------------------
  start(now) { this.origin = now; this.state = 'running'; }

  time(now) {
    if (this.state === 'ready') return 0;
    if (this.state === 'paused' || this.state === 'finished' || this.state === 'stopped') return this.pausedTime;
    return now - this.origin;
  }

  pause(now) {
    if (this.state !== 'running') return;
    this.pausedTime = this.time(now);
    this.state = 'paused';
    this.live = null;
  }

  resume(now) {
    if (this.state !== 'paused') return;
    this.origin = now - this.pausedTime;
    // Todo lo capturado antes de reanudar queda descartado.
    this.countedUntil = Math.max(this.countedUntil, this.pausedTime);
    this.state = 'running';
  }

  stop(now) {
    if (this.state !== 'running' && this.state !== 'paused') return;
    this.pausedTime = this.time(now);
    this.state = 'stopped';
  }

  /** No puntuar audio entre esos instantes de juego (referencia sonando). */
  mute(start, end) { this.muted.push([start, end + MUTE_TAIL]); }

  /** Devuelve y consume las frases de piano que tocan antes de `now`. */
  dueCues(now) {
    if (this.state !== 'running') return [];
    const t = this.time(now);
    const due = this.cues.filter((c) => c.time <= t);
    this.cues = this.cues.filter((c) => c.time > t);
    return due;
  }

  // --- objetivo en cada momento ---------------------------------------
  /** Nota cantada con la que comparar la voz ahora (o null). */
  referenceNote(t) {
    for (const note of this.sung) if (note.start - REACTION <= t && t <= note.end) return note;
    return this.sung.find((n) => n.start - t > 0 && n.start - t <= 1.2) ?? null;
  }

  // --- audio -----------------------------------------------------------
  /** Procesa un bloque que terminó en el instante `stamp` (reloj de audio). */
  feed(stamp, duration, frequency, level) {
    if (this.state !== 'running') return null;
    const end = this.time(stamp);
    const begin = Math.max(end - Math.max(0, duration), this.countedUntil);
    if (end <= begin) return null;          // bloque antiguo o repetido
    this.countedUntil = end;
    let reading;
    if (this.muted.some(([ms, me]) => begin < me && end > ms)) {
      reading = { time: end, kind: 'muted', cents: null };
    } else {
      const ref = this.referenceNote(end);
      const [kind, cents] = classify(frequency, level, this.anchor, ref ? ref.target : null, this.tolerance);
      reading = { time: end, kind, cents };
      for (const note of this.sung) {
        if (note.judgement !== null) continue;
        const overlap = Math.min(end, note.end) - Math.max(begin, note.start);
        if (overlap <= 1e-6) continue;
        const [k, c] = classify(frequency, level, this.anchor, note.target, this.tolerance);
        if (k === 'hit' || k === 'low' || k === 'high') {
          note[k] += overlap;
          note.errors.push([overlap, c - note.target]);
        } else if (k === 'unclear') {
          note.unclear += overlap;
        }
        if (k === 'hit') {
          const a = Math.max(begin, note.start), b = Math.min(end, note.end);
          const last = note.hitSpans[note.hitSpans.length - 1];
          if (last && a - last[1] < 0.05) last[1] = b;
          else note.hitSpans.push([a, b]);
        }
      }
    }
    this.live = reading;
    this.trail.push(reading);
    if (this.trail.length > 240) this.trail.shift();
    if (reading.kind !== this.hintKind) {
      this.hintKind = reading.kind;
      this.hintSince = end;
    }
    return reading;
  }

  /** Juzga las notas cuya ventana ha terminado. Devuelve eventos nuevos [índice, juicio]. */
  update(now) {
    if (this.state !== 'running') return [];
    const t = this.time(now);
    const fresh = [];
    this.notes.forEach((note, i) => {
      if (!note.demo && note.judgement === null && t >= note.end + JUDGE_DELAY) {
        const result = note.judge();
        if (HITS.has(result)) {
          this.streak += 1;
          this.bestStreak = Math.max(this.bestStreak, this.streak);
        } else if (result.startsWith('miss')) {
          this.streak = 0;
        }
        fresh.push([i, result]);
      }
    });
    if (t >= this.end) {
      this.pausedTime = t;
      this.state = 'finished';
    }
    this.events.push(...fresh);
    return fresh;
  }

  // --- lectura para la interfaz ---------------------------------------
  /** Última lectura si es reciente; null si no hay datos nuevos. */
  currentReading(now) {
    if (this.live === null || this.state !== 'running') return null;
    if (this.time(now) - this.live.time > STALE_AFTER) return null;
    return this.live;
  }

  /** Indicación estable (≥400 ms) para el texto guía. */
  hint(now) {
    const reading = this.currentReading(now);
    if (reading === null) return 'silence';
    if (reading.time - this.hintSince < HINT_PERSISTENCE && (reading.kind === 'low' || reading.kind === 'high')) return null;
    return reading.kind;
  }

  /** Índice de la nota CANTADA activa (con margen de reacción) o null. */
  activeNote(now) {
    const t = this.time(now);
    const i = this.notes.findIndex((n) => !n.demo && n.start - REACTION <= t && t <= n.end);
    return i < 0 ? null : i;
  }

  nextNote(now) {
    const t = this.time(now);
    const i = this.notes.findIndex((n) => !n.demo && n.start > t);
    return i < 0 ? null : i;
  }

  /** [fase, intento]: intro | listen | turn | sing | rest | end. */
  phase(now) {
    const t = this.time(now);
    for (const a of this.attempts) {
      const demo = this.notes.filter((n) => n.attempt === a && n.demo);
      const sung = this.sung.filter((n) => n.attempt === a);
      if (demo.length && demo[0].start - 0.3 <= t && t <= demo[demo.length - 1].end + 0.2) return ['listen', a];
      if (demo.length && demo[demo.length - 1].end + 0.2 < t && t < sung[0].start - REACTION) return ['turn', a];
      if (sung[0].start - REACTION <= t && t <= sung[sung.length - 1].end) return ['sing', a];
    }
    if (t < Math.min(...this.notes.map((n) => n.start))) return ['intro', 0];
    if (t > Math.max(...this.notes.map((n) => n.end))) return ['end', this.attempts[this.attempts.length - 1]];
    const done = this.notes.filter((n) => n.end < t).map((n) => n.attempt);
    return ['rest', done.length ? Math.max(...done) : 0];
  }

  get attempts() { return [...new Set(this.sung.map((n) => n.attempt))].sort((a, b) => a - b); }
  get score() { return this.sung.reduce((s, n) => s + n.points, 0); }

  attemptScore(attempt) {
    const notes = this.sung.filter((n) => n.attempt === attempt);
    return notes.length ? notes.filter((n) => HITS.has(n.judgement)).length / notes.length : 0;
  }

  summary() {
    const judged = this.sung.filter((n) => n.judgement);
    const hits = judged.filter((n) => HITS.has(n.judgement)).length;
    const misses = judged.filter((n) => n.judgement.startsWith('miss')).length;
    const unclear = judged.filter((n) => n.judgement === 'unclear').length;
    const silent = judged.filter((n) => n.judgement === 'silent').length;
    const measured = this.sung.reduce((s, n) => s + n.measured, 0);
    const inZone = measured > 0.2 ? this.sung.reduce((s, n) => s + n.hit, 0) / measured : null;
    const tendency = weightedMedian(this.sung.flatMap((n) => n.errors));
    const attemptScores = this.attempts.map((a) => this.attemptScore(a));
    const passes = attemptScores.filter((s) => s >= PASS_SCORE - 1e-9).length;
    let stars = null;
    if (hits + misses > 0) stars = passes >= 3 ? 3 : passes >= PASSES_NEEDED ? 2 : hits ? 1 : 0;
    return {
      notes: this.sung.length, hits, misses, unclear, silent, inZone, tendency, stars,
      score: this.score, bestStreak: this.bestStreak, attemptScores, passed: passes >= PASSES_NEEDED,
    };
  }
}

/**
 * Crea una ronda: para cada inicio (semitonos), escucha + canto del patrón.
 * Cada cue lleva las notas para el piano como [desfase_s, semitono, duración_s].
 */
export function buildRound(anchor, pattern, starts, noteLen, tolerance = TOLERANCE_CENTS,
  { lead = LEAD, turnGap = TURN_GAP, rest = REST } = {}) {
  const notes = [];
  const cues = [];
  let t = lead;
  starts.forEach((base, attempt) => {
    const semis = pattern.map((p) => base + p);
    const demoStart = t;
    for (const k of semis) {
      notes.push(new Note(t, t + noteLen * 0.92, k, attempt, true));
      t += noteLen;
    }
    cues.push({ time: demoStart, muteUntil: t, attempt, notes: semis.map((k, i) => [i * noteLen, k, noteLen * 0.92]) });
    t += turnGap;
    for (const k of semis) {
      notes.push(new Note(t, t + noteLen * 0.92, k, attempt));
      t += noteLen;
    }
    t += rest;
  });
  return new NoteRun(anchor, notes, tolerance, cues, t - rest + 1.2);
}
