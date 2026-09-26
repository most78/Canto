// Dificultad del modo canción: TODOS los parámetros ajustables en un solo sitio.
// Valores iniciales para probar; ya desde «Inicial» hay reto (±50 cents y la mitad
// de la sílaba afinada, no basta con rozar la nota).

export const DIFFICULTIES = Object.freeze({
  inicial: Object.freeze({
    key: 'inicial', name: 'Inicial',
    tolerance: 50,          // cents: zona «afinado»
    hysteresis: 15,         // cents extra para salir de «afinado» (evita parpadeo en el borde)
    dwell: 0.09,            // s que debe persistir un cambio de color
    requiredFraction: 0.5,  // fracción de la sílaba afinada para darla por acertada
    minStreak: 0.25,        // fracción de la sílaba afinada SIN interrupción (estabilidad)
    early: 0.08,            // s de margen antes de la sílaba (timing)
    late: 0.2,              // s de margen después de su inicio para entrar
    lookahead: 4.0,         // s de letra futura visible
  }),
  intermedio: Object.freeze({
    key: 'intermedio', name: 'Intermedio',
    tolerance: 40, hysteresis: 12, dwell: 0.08, requiredFraction: 0.6, minStreak: 0.35,
    early: 0.06, late: 0.15, lookahead: 3.2,
  }),
  avanzado: Object.freeze({
    key: 'avanzado', name: 'Avanzado',
    tolerance: 30, hysteresis: 10, dwell: 0.07, requiredFraction: 0.7, minStreak: 0.45,
    early: 0.05, late: 0.1, lookahead: 2.6,
  }),
  reto: Object.freeze({
    key: 'reto', name: 'Reto',
    tolerance: 20, hysteresis: 8, dwell: 0.06, requiredFraction: 0.8, minStreak: 0.55,
    early: 0.04, late: 0.07, lookahead: 2.0,
  }),
});

export const ORDER = ['inicial', 'intermedio', 'avanzado', 'reto'];

export function difficulty(key = 'inicial', overrides = {}) {
  const base = DIFFICULTIES[key];
  if (!base) throw new Error(`Dificultad desconocida: ${key}`);
  return Object.freeze({ ...base, ...overrides });
}

/**
 * Sugerencia de progreso: subir cuando aciertas ≥80 % de las sílabas en las
 * dos últimas interpretaciones de ese nivel. Nunca cambia sola: sólo sugiere.
 */
export function suggestNext(key, recentHitRates) {
  const i = ORDER.indexOf(key);
  const last = recentHitRates.slice(-2);
  if (i < ORDER.length - 1 && last.length === 2 && last.every((r) => r >= 0.8)) return ORDER[i + 1];
  return null;
}
