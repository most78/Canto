// Micrófono → AudioWorklet → ventana deslizante → YIN → (marca, duración, Hz, nivel).
//
// Equivale a audio/capture.py + la lectura de main_window.py, con menos latencia:
// en vez de bloques independientes de 80 ms, se analiza una ventana de 64 ms cada
// ~21 ms. Al motor se le pasa como duración sólo el audio NUEVO (el salto), así
// que nada puntúa dos veces.

import { resumeAudio } from './context.js';
import { detectPitch, rms } from '../pitch/yin.js';

export const WINDOW_SECONDS = 0.064;  // ≥ 2 periodos de 70 Hz (mínimo de YIN)
export const HOP_SECONDS = 0.0213;    // cada cuánto llega una lectura nueva
export const MIN_RMS = 0.002;         // puerta de silencio suave; YIN rechaza lo que no tiene tono

// Sin cancelación de eco, supresión de ruido ni control de ganancia: alteran la altura.
const RAW = { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 };

let workletReady = null;

export class Microphone {
  constructor(onReading) {
    this.onReading = onReading;   // (stamp, duration, frequency|null, level)
    this.stream = null;
    this.node = null;
    this.source = null;
    this.sink = null;
    this.ring = null;
    this.filled = 0;
    this.sampleRate = 48000;
    this.onEnded = null;
  }

  get active() { return this.stream !== null; }

  /** Lista de entradas. Los nombres sólo aparecen tras dar permiso al micrófono. */
  static async devices() {
    const all = await navigator.mediaDevices.enumerateDevices();
    return all.filter((d) => d.kind === 'audioinput');
  }

  async start(deviceId = '') {
    this.stop();
    const ctx = await resumeAudio();
    workletReady ??= ctx.audioWorklet.addModule(new URL('./capture-worklet.js', import.meta.url));
    await workletReady;
    const audio = deviceId ? { ...RAW, deviceId: { exact: deviceId } } : RAW;
    this.stream = await navigator.mediaDevices.getUserMedia({ audio });
    this.sampleRate = ctx.sampleRate;
    const hop = Math.round(ctx.sampleRate * HOP_SECONDS);
    const size = Math.round(ctx.sampleRate * WINDOW_SECONDS);
    this.ring = new Float32Array(size);
    this.filled = 0;
    this.source = ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(ctx, 'canto-capture', { processorOptions: { hop } });
    this.node.port.onmessage = (event) => this.receive(event.data);
    // El nodo debe estar conectado al grafo para procesarse; sale en silencio.
    this.sink = ctx.createGain();
    this.sink.gain.value = 0;
    this.source.connect(this.node).connect(this.sink).connect(ctx.destination);
    for (const track of this.stream.getAudioTracks()) {
      track.addEventListener('ended', () => this.onEnded?.());
    }
    return this.stream.getAudioTracks()[0]?.label ?? '';
  }

  receive({ samples, end }) {
    const ring = this.ring;
    const n = samples.length;
    ring.copyWithin(0, n);                   // desplaza la ventana y añade lo nuevo
    ring.set(samples, ring.length - n);
    this.filled = Math.min(ring.length, this.filled + n);
    if (this.filled < ring.length) return;   // aún no hay una ventana completa
    let frequency = null;
    try {
      frequency = detectPitch(ring, this.sampleRate, { minRms: MIN_RMS });
    } catch {
      frequency = null;
    }
    this.onReading(end, n / this.sampleRate, frequency, rms(ring));
  }

  stop() {
    this.node?.port.close();
    this.source?.disconnect();
    this.node?.disconnect();
    this.sink?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = this.node = this.source = this.sink = null;
  }
}
