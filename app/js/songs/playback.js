// Reproducción de la canción en el reloj del AudioContext (el mismo que el
// micrófono y la letra). Nada de timers JS para la sincronización.
//
// songTime(ctxTime) = segundos de canción que suenan en ese instante del reloj.
// La latencia de salida (lo que tarda en oírse) y la de entrada (lo que tarda
// tu voz en llegar) las compensa quien llama (exercises/singSong.js).

import { audioContext } from '../audio/context.js';
import { midiFrequency } from '../pitch/notes.js';

export class SongPlayer {
  constructor(piano) {
    this.piano = piano;
    this.song = null;
    this.buffer = null;
    this.source = null;
    this.gain = null;
    this.t0 = null;          // reloj de audio en el que empezó la canción (tiempo 0)
    this.pausedAt = 0;
    this.playing = false;
    this.volume = 0.8;
  }

  /** Prepara el audio: decodifica el archivo o usa el piano con las notas de la canción. */
  async load(song) {
    this.stop();
    this.song = song;
    this.buffer = null;
    if (song.audio.kind === 'file') {
      const response = await fetch(song.audio.src);
      if (!response.ok) throw new Error(`No se encontró el audio ${song.audio.src}`);
      this.buffer = await audioContext().decodeAudioData(await response.arrayBuffer());
    } else if (song.audio.kind === 'piano') {
      await this.piano.load();
    } else {
      throw new Error(`Tipo de audio desconocido: ${song.audio.kind}`);
    }
  }

  get duration() {
    if (this.buffer) return this.buffer.duration - (this.song.audio.offset ?? 0);
    return this.song ? this.song.duration + 1.5 : 0;
  }

  /** Empieza (o reanuda) en `from` segundos de canción. */
  start(from = 0) {
    const ctx = audioContext();
    this.stopSources();
    const when = ctx.currentTime + 0.08;
    this.t0 = when - from;
    if (this.buffer) {
      this.gain = ctx.createGain();
      this.gain.gain.value = this.volume;
      this.gain.connect(ctx.destination);
      this.source = ctx.createBufferSource();
      this.source.buffer = this.buffer;
      this.source.connect(this.gain);
      this.source.start(when, Math.max(0, from + (this.song.audio.offset ?? 0)));
    } else {
      // Canción de piano: se programan todas las notas de todas las voces.
      const notes = this.song.voices.flatMap((v) => v.events)
        .filter((e) => e.end > from)
        .map((e) => [Math.max(0, e.start - from), midiFrequency(e.pitch), e.end - Math.max(e.start, from)]);
      if (notes.length) this.piano.phrase(notes, when);
    }
    this.playing = true;
  }

  pause(ctxTime = audioContext().currentTime) {
    if (!this.playing) return this.pausedAt;
    this.pausedAt = Math.max(0, ctxTime - this.t0);
    this.stopSources();
    this.playing = false;
    return this.pausedAt;
  }

  resume() { this.start(this.pausedAt); }

  stop() {
    this.stopSources();
    this.playing = false;
    this.pausedAt = 0;
  }

  stopSources() {
    try { this.source?.stop(); } catch { /* ya parado */ }
    this.source?.disconnect();
    this.gain?.disconnect();
    this.source = this.gain = null;
    this.piano?.stopAll();
  }

  songTime(ctxTime) {
    return this.playing ? ctxTime - this.t0 : this.pausedAt;
  }
}
