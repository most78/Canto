// Un único AudioContext para toda la app: su reloj (currentTime) es el reloj del
// juego, de las marcas del micrófono y de la programación del piano.

let ctx = null;

export function audioContext() {
  if (!ctx) ctx = new AudioContext({ latencyHint: 'interactive' });
  return ctx;
}

/** Los navegadores exigen un gesto del usuario para que el audio arranque. */
export async function resumeAudio() {
  const c = audioContext();
  if (c.state !== 'running') await c.resume();
  return c;
}

export const now = () => audioContext().currentTime;
