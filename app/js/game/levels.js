// Niveles de escalas y su colocación dentro de tu rango cómodo.
// Port de legacy/src/game/levels.py. Patrones en semitonos respecto a la
// primera nota (escala mayor). Cada nivel cambia una sola cosa respecto al
// anterior: extensión, velocidad, tipo de salto o margen de afinación.

function level(key, name, description, pattern, noteLen, tolerance = 50) {
  return Object.freeze({
    key, name, description, pattern: Object.freeze(pattern), noteLen, tolerance,
    span: Math.max(...pattern) - Math.min(...pattern),
  });
}

export const LEVELS = Object.freeze([
  level('tres', 'Tres escalones', 'Tres notas seguidas de la escala: sube y vuelve.', [0, 2, 4, 2, 0], 0.9),
  level('cinco', 'Cinco hacia arriba', 'Cinco notas de la escala, subiendo.', [0, 2, 4, 5, 7], 0.85),
  level('subebaja', 'Sube y baja', 'Cinco notas arriba y de vuelta, más ágil.', [0, 2, 4, 5, 7, 5, 4, 2, 0], 0.65),
  level('arpegio', 'Arpegio', 'Saltos de acorde, como do–mi–sol.', [0, 4, 7, 4, 0], 0.85),
  level('terceras', 'Terceras', 'Saltos de tercera que van subiendo.', [0, 4, 2, 5, 4, 7], 0.75),
  level('precision', 'Más precisión', '«Sube y baja» con margen de ±35 cents.', [0, 2, 4, 5, 7, 5, 4, 2, 0], 0.65, 35),
  level('octava', 'Octava', 'La escala completa, subiendo.', [0, 2, 4, 5, 7, 9, 11, 12], 0.6),
  level('arpegio8', 'Arpegio de octava', 'Do–mi–sol–do agudo y vuelta, ±35 cents.', [0, 4, 7, 12, 7, 4, 0], 0.75, 35),
  level('fino', 'Afinado fino', '«Sube y baja» rápido con ±25 cents.', [0, 2, 4, 5, 7, 5, 4, 2, 0], 0.5, 25),
]);

/**
 * Inicios (semitonos respecto a tu nota) de los 3 intentos dentro de [lo, hi]:
 * primero lo más cerca de tu nota, luego lo más agudo y lo más grave que cabe.
 * Lista vacía si el nivel aún no cabe.
 */
export function placements(lvl, lo, hi) {
  const first = lo - Math.min(...lvl.pattern);
  const last = hi - Math.max(...lvl.pattern);
  if (last < first) return [];
  const valid = [];
  for (let s = first; s <= last; s++) valid.push(s);
  const middle = valid.reduce((best, s) => (Math.abs(s) < Math.abs(best) || (Math.abs(s) === Math.abs(best) && s < best) ? s : best));
  return [middle, Math.max(...valid), Math.min(...valid)];
}
