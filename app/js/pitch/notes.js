// Frecuencia ↔ nota. Nombres en español, octavas franco-belgas: La3 = 440 Hz,
// Do central = Do3. Cents: negativo = grave, positivo = agudo.
// Port directo de hz_to_note / note_name del Canto Python (legacy/).

export const NOTE_NAMES = ['Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#', 'La', 'La#', 'Si'];
const MIDI_OCTAVE_OFFSET = 2; // MIDI 69 → 69 // 12 - 2 = 3 → La3

export function midiFloat(frequency, a4 = 440) {
  return 69 + 12 * Math.log2(frequency / a4);
}

export function midiFrequency(midi) {
  return 440 * 2 ** ((midi - 69) / 12);
}

export function centsBetween(frequency, reference) {
  return 1200 * Math.log2(frequency / reference);
}

/** Nota más cercana a una frecuencia y desviación en cents (−50…+50). */
export function hzToNote(frequency, a4 = 440) {
  if (!(frequency > 0)) throw new RangeError('La frecuencia debe ser positiva');
  const m = midiFloat(frequency, a4);
  const midi = Math.floor(m + 0.5);
  const cents = (m - midi) * 100;
  const name = NOTE_NAMES[((midi % 12) + 12) % 12];
  const octave = Math.floor(midi / 12) - MIDI_OCTAVE_OFFSET;
  return { frequency, midi, name, octave, cents, label: `${name}${octave}` };
}

/** Nombre de una nota MIDI entera, p. ej. 57 → «La2». */
export function noteName(midi) {
  return hzToNote(midiFrequency(midi)).label;
}

export function nearestMidi(frequency) {
  return Math.round(midiFloat(frequency));
}
