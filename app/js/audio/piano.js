// Piano muestreado: Salamander Grand Piano (CC-BY 3.0, Alexander Holm).
// Ver assets/piano/LEEME.md. Port de audio/piano.py:
// - cada muestra se CALIBRA con el mismo YIN que evalúa la voz (su afinación
//   real puede desviarse unos cents del valor nominal);
// - se toca la muestra más cercana reafinada (playbackRate, ≤ ±1,5 semitonos)
//   a la frecuencia exacta pedida;
// - las frases se programan en el reloj del AudioContext, alineadas con las
//   barras de escucha de la pista.

import { audioContext } from './context.js';
import { detectPitch } from '../pitch/yin.js';
import { midiFloat, midiFrequency } from '../pitch/notes.js';

const FOLDER = new URL('../../../assets/piano/', import.meta.url);
const FILES = ['A1', 'C2', 'Ds2', 'Fs2', 'A2', 'C3', 'Ds3', 'Fs3', 'A3', 'C4', 'Ds4', 'Fs4', 'A4', 'C5'];
const NAMES = { C: 0, Cs: 1, Ds: 3, E: 4, F: 5, Fs: 6, G: 7, A: 9 };
export const RELEASE = 0.25;     // apagado suave al soltar la tecla
const VELOCITY = 0.8;
const VOLUME = 0.5;

/** 'Ds3' → 51 (notación científica inglesa, A4 = 69). */
export function midiOfSample(name) {
  return 12 * (Number(name.slice(-1)) + 1) + NAMES[name.slice(0, -1)];
}

/** Primera muestra por encima del 1 % del pico, menos 2 ms (igual que decode() en Python). */
export function attackIndex(data, peak, rate) {
  const limit = 0.01 * peak;
  let i = 0;
  while (i < data.length && Math.abs(data[i]) <= limit) i++;
  return Math.max(0, i - Math.round(rate * 0.002));
}

/** Frecuencia real de una muestra, medida con YIN entre 0,15 s y 0,9 s. */
export function calibrate(samples, rate, midi) {
  const nominal = midiFrequency(midi);
  const block = Math.round(rate * 0.08);
  const readings = [];
  for (let start = 0.15; start < 0.9; start += 0.08) {
    const i = Math.round(rate * start);
    if (i + block > samples.length) break;
    const f = detectPitch(samples.subarray(i, i + block), rate);
    if (f && Math.abs(1200 * Math.log2(f / nominal)) < 30) readings.push(f);
  }
  if (!readings.length) return nominal;
  readings.sort((a, b) => a - b);
  const m = readings.length >> 1;
  return readings.length % 2 ? readings[m] : (readings[m - 1] + readings[m]) / 2;
}

export class Piano {
  constructor() {
    this.samples = new Map();   // midi -> {buffer, tuning, gain}
    this.voices = new Set();
    this.ready = null;
    this.error = null;
    this.output = null;
  }

  load() {
    this.ready ??= (async () => {
      const ctx = audioContext();
      this.output = ctx.createGain();
      this.output.gain.value = VOLUME;
      this.output.connect(ctx.destination);
      await Promise.all(FILES.map(async (name) => {
        const response = await fetch(new URL(`${name}.mp3`, FOLDER));
        if (!response.ok) throw new Error(`No se pudo cargar ${name}.mp3`);
        const buffer = await ctx.decodeAudioData(await response.arrayBuffer());
        const data = buffer.getChannelData(0);
        let peak = 0;
        for (let i = 0; i < data.length; i++) peak = Math.max(peak, Math.abs(data[i]));
        // Como en Python: se salta el silencio inicial del MP3 (retardo del codificador).
        const onset = attackIndex(data, peak, buffer.sampleRate);
        const midi = midiOfSample(name);
        this.samples.set(midi, {
          buffer,
          offset: onset / buffer.sampleRate,
          tuning: calibrate(data.subarray(onset), buffer.sampleRate, midi),
          gain: 1 / (peak || 1),
        });
      }));
    })().catch((error) => { this.error = error; throw error; });
    return this.ready;
  }

  /** Programa una nota: suena `seconds` desde `when` y se apaga en RELEASE s. */
  note(frequency, when, seconds) {
    const ctx = audioContext();
    const m = midiFloat(frequency);
    let key = null;
    for (const k of this.samples.keys()) if (key === null || Math.abs(k - m) < Math.abs(key - m)) key = k;
    if (key === null) return this.fallback(frequency, when, seconds);
    const sample = this.samples.get(key);
    const source = ctx.createBufferSource();
    source.buffer = sample.buffer;
    source.playbackRate.value = frequency / sample.tuning;
    const gain = ctx.createGain();
    const level = VELOCITY * sample.gain;
    gain.gain.setValueAtTime(level, when);
    gain.gain.setValueAtTime(level, when + seconds);
    gain.gain.linearRampToValueAtTime(0, when + seconds + RELEASE);
    source.connect(gain).connect(this.output);
    source.start(when, sample.offset);
    source.stop(when + seconds + RELEASE + 0.05);
    this.track(source);
  }

  /** Tono simple si faltaran las muestras (equivale a la síntesis de respaldo de Python). */
  fallback(frequency, when, seconds) {
    const ctx = audioContext();
    const osc = ctx.createOscillator();
    osc.frequency.value = frequency;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, when);
    gain.gain.linearRampToValueAtTime(0.25, when + 0.02);
    gain.gain.setValueAtTime(0.25, when + seconds);
    gain.gain.linearRampToValueAtTime(0, when + seconds + 0.15);
    osc.connect(gain).connect(this.output ?? ctx.destination);
    osc.start(when);
    osc.stop(when + seconds + 0.2);
    this.track(osc);
  }

  track(node) {
    this.voices.add(node);
    node.onended = () => this.voices.delete(node);
  }

  /** notes = [[desfase_s, frecuencia, duración_s]] a partir de `when` (reloj de audio). */
  phrase(notes, when = audioContext().currentTime + 0.03) {
    for (const [offset, frequency, seconds] of notes) this.note(frequency, when + offset, seconds);
    const end = Math.max(...notes.map(([o, , s]) => o + s)) + RELEASE;
    return when + end;
  }

  stopAll() {
    for (const node of this.voices) {
      try { node.stop(); } catch { /* ya parado */ }
    }
    this.voices.clear();
  }
}
