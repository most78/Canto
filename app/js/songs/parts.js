// Qué canta el jugador: selección de notas objetivo según la parte elegida y
// agrupación en UNIDADES jugables (una sílaba de una voz, con 1 o varias notas).
//
// Partes:
//   { mode: 'voice', voiceId }  → sólo esa voz (en un dueto, cuando canta la otra, escuchas).
//   { mode: 'full' }            → «Cántala entera»: si canta una voz, esa; si cantan varias a
//                                  la vez, la de mayor prioridad (priority más baja). Sin
//                                  armonización automática: la regla es explícita y simple.
//   'harmony' queda para el futuro.

export function partsFor(song) {
  if (song.voices.length === 1) return [{ mode: 'voice', voiceId: song.voices[0].id, label: song.voices[0].name }];
  return [
    ...song.voices.map((v) => ({ mode: 'voice', voiceId: v.id, label: v.name })),
    { mode: 'full', label: 'Cántala entera' },
  ];
}

/** Notas que debe cantar el jugador, ordenadas y sin solapes. */
export function targetsFor(song, part = partsFor(song)[0]) {
  if (part.mode === 'voice') return [...song.voice(part.voiceId).events];
  if (part.mode !== 'full') throw new Error(`Parte no soportada todavía: ${part.mode}`);
  const all = song.voices.flatMap((v) => v.events.map((e) => ({ e, priority: v.priority })))
    .sort((a, b) => a.e.start - b.e.start || a.priority - b.priority);
  const chosen = [];
  for (const { e, priority } of all) {
    const clash = chosen.findIndex((c) => e.start < c.e.end - 1e-6 && c.e.start < e.end - 1e-6);
    if (clash < 0) chosen.push({ e, priority });
    else if (priority < chosen[clash].priority) chosen[clash] = { e, priority };   // manda la prioritaria
  }
  return chosen.map((c) => c.e).sort((a, b) => a.start - b.start);
}

/**
 * Agrupa notas consecutivas de la misma voz y sílaba (melisma) en unidades.
 * Una nota sin sílaba es su propia unidad.
 */
export function unitsFor(song, targets, transpose = 0) {
  const units = [];
  for (const e of targets) {
    const last = units[units.length - 1];
    const same = last && e.syllable !== null && last.syllableId === e.syllable && last.voiceId === e.voiceId
      && e.start - last.end < 0.25;
    const note = { ...e, pitch: e.pitch + transpose };
    if (same) {
      last.events.push(note);
      last.end = e.end;
    } else {
      const syl = e.syllable ? song.syllable(e.syllable) : null;
      units.push({
        index: units.length, voiceId: e.voiceId, syllableId: e.syllable,
        text: syl?.text ?? '·', wordId: syl?.wordId ?? null, lineId: syl?.lineId ?? null,
        firstOfWord: syl?.first ?? true, lastOfWord: syl?.last ?? true,
        start: e.start, end: e.end, events: [note],
      });
    }
  }
  for (const u of units) u.duration = u.end - u.start;
  return units;
}

/** Extensión (MIDI) de las notas objetivo. */
export function pitchRange(units) {
  const pitches = units.flatMap((u) => u.events.map((e) => e.pitch));
  return pitches.length ? [Math.min(...pitches), Math.max(...pitches)] : [60, 60];
}
