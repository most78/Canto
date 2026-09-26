// Feedback VISUAL de la voz en el modo canción: la línea y su color.
//
// Se separan tres cosas:
//   - pitch instantáneo: lo que devuelve YIN en cada bloque (puede saltar);
//   - pitch visual: mediana de 3 + suavizado exponencial (τ corto: sin retraso molesto);
//   - estado de color con HISTÉRESIS: para salir de «afinado» hay que alejarse
//     `tolerance + hysteresis` cents, y cualquier cambio de color debe persistir
//     `dwell` segundos. Así la línea no parpadea verde/cyan/naranja en el borde.
// La puntuación (songRun.js) NO usa este suavizado: evalúa cada bloque en bruto.

export const SMOOTHING_TAU = 0.05;   // s
export const GAP_BREAK = 0.12;       // s sin voz → la línea se corta

export class VoiceFeedback {
  constructor({ tolerance, hysteresis, dwell }) {
    this.tolerance = tolerance;
    this.hysteresis = hysteresis;
    this.dwell = dwell;
    this.reset();
  }

  reset() {
    this.raw = [];            // últimas lecturas brutas (MIDI) para la mediana
    this.smoothed = null;
    this.lastTime = null;
    this.state = 'none';      // 'in' | 'low' | 'high' | 'none' (sin objetivo)
    this.pending = null;
    this.pendingSince = 0;
    this.target = null;
  }

  /** Clasificación sin memoria: la usa también el test de histéresis. */
  classify(errorCents, current) {
    const limit = current === 'in' ? this.tolerance + this.hysteresis : this.tolerance;
    if (Math.abs(errorCents) <= limit) return 'in';
    return errorCents < 0 ? 'low' : 'high';
  }

  /**
   * Nueva lectura. `midi` = pitch cantado (null si no hay voz fiable),
   * `target` = nota objetivo en MIDI (null si ahora no toca cantar).
   * Devuelve {time, midi (visual), state, break}.
   */
  push(time, midi, target) {
    if (midi === null) {
      if (this.lastTime !== null && time - this.lastTime > GAP_BREAK) {
        this.raw = [];
        this.smoothed = null;
      }
      return { time, midi: null, state: this.state, break: true };
    }
    this.raw.push(midi);
    if (this.raw.length > 3) this.raw.shift();
    const median = [...this.raw].sort((a, b) => a - b)[this.raw.length >> 1];
    if (this.smoothed === null) {
      this.smoothed = median;
    } else {
      const dt = Math.max(0, time - (this.lastTime ?? time));
      this.smoothed += (median - this.smoothed) * (1 - Math.exp(-dt / SMOOTHING_TAU));
    }
    this.lastTime = time;

    if (target === null) {
      this.state = 'none';
      this.pending = null;
    } else {
      const error = (this.smoothed - target) * 100;
      if (target !== this.target || this.state === 'none') {
        // Nueva nota objetivo: el color se decide ya, sin arrastrar el anterior.
        this.state = this.classify(error, null);
        this.pending = null;
      } else {
        const candidate = this.classify(error, this.state);
        if (candidate === this.state) {
          this.pending = null;
        } else if (candidate !== this.pending) {
          this.pending = candidate;
          this.pendingSince = time;
        } else if (time - this.pendingSince >= this.dwell) {
          this.state = candidate;
          this.pending = null;
        }
      }
    }
    this.target = target;
    return { time, midi: this.smoothed, state: this.state, break: false };
  }
}
