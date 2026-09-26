// Tesitura: detecta fragmentos de una canción fuera de tu rango.
// Sólo INFORMA. Nunca cambia notas en silencio: una nota distinta puede cambiar
// la armonía, así que cualquier adaptación (transponer) debe ser explícita.
//
// range = { comfortableLow, comfortableHigh, reachableLow?, reachableHigh? } (MIDI)

export function rangeFromProgress(progress) {
  if (!progress || progress.anchor_midi === null) return null;
  const [low, high] = progress.rangeMidi();
  return { comfortableLow: low, comfortableHigh: high, reachableLow: null, reachableHigh: null };
}

/** Fragmentos (por frase) con notas fuera del rango cómodo. */
export function outOfRange(units, range) {
  if (!range) return [];
  const fragments = new Map();
  for (const u of units) {
    for (const e of u.events) {
      const below = e.pitch < range.comfortableLow - 0.5;
      const above = e.pitch > range.comfortableHigh + 0.5;
      if (!below && !above) continue;
      const key = u.lineId ?? `u${u.index}`;
      const f = fragments.get(key) ?? { lineId: u.lineId, lowest: e.pitch, highest: e.pitch, above: false, below: false, reachable: true, units: new Set() };
      f.lowest = Math.min(f.lowest, e.pitch);
      f.highest = Math.max(f.highest, e.pitch);
      f.above ||= above;
      f.below ||= below;
      if ((range.reachableLow != null && e.pitch < range.reachableLow - 0.5)
        || (range.reachableHigh != null && e.pitch > range.reachableHigh + 0.5)) f.reachable = false;
      f.units.add(u.index);
      fragments.set(key, f);
    }
  }
  return [...fragments.values()].map((f) => ({ ...f, units: [...f.units] }));
}
