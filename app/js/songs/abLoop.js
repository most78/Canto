// Repetición A–B de un fragmento. Port de legacy/src/ui/songs.py.
// Tiempos en segundos. El final B debe quedar al menos 1 s después de A.

export const MIN_SEGMENT = 1.0;

export function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export class ABLoop {
  constructor() { this.reset(); }

  reset() {
    this.a = 0;
    this.b = null;
    this.enabled = false;
  }

  /** Nuevo inicio A: borra el final y desactiva la repetición. */
  setA(position) {
    this.a = position;
    this.b = null;
    this.enabled = false;
    return `Inicio A: ${clock(this.a)} · marca el final al menos 1 segundo después.`;
  }

  /** Devuelve [ok, mensaje]. */
  setB(position) {
    if (position < this.a + MIN_SEGMENT) return [false, 'El final B debe estar al menos 1 segundo después del inicio A.'];
    this.b = position;
    return [true, `Fragmento: ${clock(this.a)} → ${clock(this.b)}`];
  }

  get ready() { return this.b !== null; }

  /** Al darle a reproducir fuera del fragmento, vuelve a A. */
  startPosition(position) {
    return this.enabled && this.ready && !(this.a <= position && position < this.b) ? this.a : null;
  }

  /** Durante la reproducción: si pasa de B, vuelve a A. */
  wrap(position) {
    return this.enabled && this.ready && position >= this.b ? this.a : null;
  }
}
