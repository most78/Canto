// Encontrar una nota propia y cómoda a partir de lecturas breves de voz.
// Port de legacy/src/game/reference.py: grupo de lecturas cercanas (±100 cents)
// con ≥0,3 s de voz y ≥3 bloques. Los silencios no suman y los cortes breves
// no reinician. Termina sola a los 4 s y explica por qué no encontró nada.

const GROUP_CENTS = 100;
const NEEDED_SECONDS = 0.3;
const NEEDED_BLOCKS = 3;
const TIME_LIMIT = 4.0;
const LOW_SIGNAL = 0.002;
const MAX_BLOCK = 0.15;

function median(values) {
  const s = [...values].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export class ReferenceFinder {
  constructor() { this.reset(); }

  reset() {
    this.samples = [];          // [instante, frecuencia, duración]
    this.started = null;
    this.seconds = 0;
    this.peak = 0;
    this.tones = 0;
    this.frequency = null;
    this.failed = null;         // [motivo, acción]
    this.progress = 0;
  }

  get searching() { return this.frequency === null && this.failed === null; }

  /** Añade un bloque analizado. Devuelve la frecuencia cuando la encuentra. */
  feed(frequency, level, now, duration) {
    if (!this.searching) return this.frequency;
    if (this.started === null) this.started = now;
    this.seconds += Math.max(0, duration);
    this.peak = Math.max(this.peak, level);
    if (now - this.started >= TIME_LIMIT) {
      this.fail();
      return null;
    }
    while (this.samples.length && now - this.samples[0][0] > 3) this.samples.shift();
    if (frequency != null) {
      this.tones += 1;
      this.samples.push([now, frequency, Math.min(MAX_BLOCK, Math.max(0, duration))]);
      if (this.samples.length > 100) this.samples.shift();
    }
    let best = [];
    let bestTime = 0;
    for (const [, candidate] of this.samples) {
      const group = this.samples.filter((s) => Math.abs(1200 * Math.log2(s[1] / candidate)) <= GROUP_CENTS);
      const time = group.reduce((acc, s) => acc + s[2], 0);
      if (time > bestTime) { best = group; bestTime = time; }
    }
    this.progress = Math.min(0.95, bestTime / NEEDED_SECONDS);
    if (best.length >= NEEDED_BLOCKS && bestTime >= NEEDED_SECONDS - 1e-3) {
      this.frequency = median(best.map((s) => s[1]));
      this.progress = 1;
    }
    return this.frequency;
  }

  fail() {
    if (this.seconds === 0) {
      this.failed = ['No han llegado datos del micrófono.', 'Elige otro dispositivo y vuelve a activarlo.'];
    } else if (this.peak < LOW_SIGNAL) {
      this.failed = ['La señal del micrófono llega muy baja.', 'Revisa el dispositivo y su nivel de entrada. No hace falta cantar más fuerte.'];
    } else if (this.tones === 0) {
      this.failed = ['Llega sonido, pero no distingo una nota.', 'Puede ser ruido de fondo. Prueba otro micrófono o acércate un poco.'];
    } else {
      this.failed = ['He oído notas, pero no una lo bastante parecida entre sí.', 'Descansa y prueba otra «u» tranquila de un segundo.'];
    }
  }

  diagnostic() {
    return `${this.seconds.toFixed(1)} s de audio analizado · ${this.tones} bloques con nota · señal máxima ${this.peak.toFixed(4)}`;
  }
}
