// Modelo de canción de Canto (*.canto.json). Independiente de cómo se dibuje.
//
// {
//   format: 'canto-song', version: 1, id,
//   metadata: { title, artist, license?, notes? },
//   audio: { kind: 'file', src, offset? } | { kind: 'piano', voice? },
//   lyrics: { lines: [ { id, words: [ { id, syllables: [ { id, text } ] } ] } ] },
//   voices: [ { id, name, priority?, events: [ { id, start, duration, pitch, syllable, expression? } ] } ]
// }
//
// - Tiempos en segundos desde el inicio del audio (tras `audio.offset`).
// - `pitch` en MIDI (69 = La3 = 440 Hz); admite decimales.
// - Melisma: varias notas consecutivas de una voz con la misma sílaba.
// - Silencio: hueco entre notas (no hace falta representarlo).
// - Varias voces pueden apuntar a las mismas sílabas (unísono) o a otras.
// - `expression` queda reservado (énfasis, ataques, vibrato, dinámica): V1 no lo usa.

export const FORMAT = 'canto-song';
export const VERSION = 1;

export class SongError extends Error {}

/** Valida y normaliza. Devuelve un objeto Song con índices para consultar la letra. */
export function loadSong(data) {
  const problems = [];
  if (data?.format !== FORMAT) problems.push(`format debe ser «${FORMAT}»`);
  if (data?.version !== VERSION) problems.push(`version debe ser ${VERSION}`);
  const lines = data?.lyrics?.lines ?? [];
  const voicesIn = data?.voices ?? [];
  if (!voicesIn.length) problems.push('falta al menos una voz en voices[]');

  const syllables = new Map();   // id → {id, text, wordId, lineId, index, first, last}
  const words = new Map();       // id → {id, text, lineId, syllableIds}
  const lineList = [];
  let order = 0;
  for (const line of lines) {
    const lineWords = [];
    for (const word of line.words ?? []) {
      const ids = [];
      (word.syllables ?? []).forEach((syl, i, all) => {
        if (syllables.has(syl.id)) problems.push(`sílaba repetida: ${syl.id}`);
        syllables.set(syl.id, { id: syl.id, text: syl.text ?? '', wordId: word.id, lineId: line.id,
          index: order++, first: i === 0, last: i === all.length - 1 });
        ids.push(syl.id);
      });
      const text = (word.syllables ?? []).map((s) => s.text).join('');
      words.set(word.id, { id: word.id, text, lineId: line.id, syllableIds: ids });
      lineWords.push(word.id);
    }
    lineList.push({ id: line.id, wordIds: lineWords, text: lineWords.map((w) => words.get(w).text).join(' ') });
  }

  const voices = voicesIn.map((voice, v) => {
    const events = (voice.events ?? []).map((e, i) => {
      if (!(e.duration > 0)) problems.push(`${voice.id}/${e.id ?? i}: duración no válida`);
      if (typeof e.pitch !== 'number') problems.push(`${voice.id}/${e.id ?? i}: falta pitch`);
      if (e.syllable != null && !syllables.has(e.syllable)) problems.push(`${voice.id}/${e.id ?? i}: sílaba desconocida ${e.syllable}`);
      return Object.freeze({ id: e.id ?? `${voice.id}-${i}`, voiceId: voice.id, start: e.start, duration: e.duration,
        end: e.start + e.duration, pitch: e.pitch, syllable: e.syllable ?? null, expression: e.expression ?? null });
    }).sort((a, b) => a.start - b.start);
    for (let i = 1; i < events.length; i++) {
      if (events[i].start < events[i - 1].end - 1e-6) problems.push(`${voice.id}: notas solapadas (${events[i - 1].id}, ${events[i].id})`);
    }
    return Object.freeze({ id: voice.id, name: voice.name ?? voice.id, priority: voice.priority ?? v + 1, events });
  });

  if (problems.length) throw new SongError(`Canción no válida: ${problems.join('; ')}`);
  return Object.freeze({
    id: data.id,
    metadata: { title: data.metadata?.title ?? data.id, artist: data.metadata?.artist ?? '', ...data.metadata },
    audio: { offset: 0, ...data.audio },
    voices,
    lines: lineList,
    syllable: (id) => syllables.get(id) ?? null,
    word: (id) => words.get(id) ?? null,
    line: (id) => lineList.find((l) => l.id === id) ?? null,
    voice: (id) => voices.find((v) => v.id === id) ?? null,
    get duration() { return Math.max(...voices.flatMap((v) => v.events.map((e) => e.end)), 0); },
  });
}
