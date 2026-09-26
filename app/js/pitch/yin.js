// Detección de frecuencia fundamental con YIN (de Cheveigné & Kawahara, 2002).
// Port 1:1 de legacy/src/audio/pitch.py: misma función diferencia (vía FFT),
// misma normalización acumulada (CMNDF), mismo umbral, mismo mínimo local e
// interpolación parabólica. Validado contra resultados del Python en tests/web.

import { fft } from './fft.js';

export const DEFAULT_FMIN = 70;        // Hz
export const DEFAULT_FMAX = 1100;      // Hz
export const DEFAULT_THRESHOLD = 0.15; // más bajo = más exigente
export const DEFAULT_MIN_RMS = 0.01;   // puerta de silencio por defecto

export function rms(frame) {
  if (!frame.length) return 0;
  let sum = 0;
  for (let i = 0; i < frame.length; i++) sum += frame[i] * frame[i];
  return Math.sqrt(sum / frame.length);
}

/**
 * Frecuencia fundamental (Hz) de un bloque mono, o null si no hay tono claro.
 * Lanza RangeError si el bloque es demasiado corto para `fmin`.
 */
export function yin(frame, sampleRate, { fmin = DEFAULT_FMIN, fmax = DEFAULT_FMAX, threshold = DEFAULT_THRESHOLD } = {}) {
  const n = frame.length;
  const x = new Float64Array(n);
  let mean = 0;
  for (let i = 0; i < n; i++) mean += frame[i];
  mean /= n || 1;
  for (let i = 0; i < n; i++) x[i] = frame[i] - mean;

  const tauMin = Math.max(2, Math.floor(sampleRate / fmax));
  const tauMax = Math.floor(sampleRate / fmin);
  const window = n - tauMax;
  if (window < tauMax) {
    throw new RangeError(`Bloque demasiado corto (${n} muestras) para fmin=${fmin} Hz a ${sampleRate} Hz; necesita al menos ${2 * tauMax}.`);
  }

  // 1) Función diferencia d(tau) = energía(0) + energía(tau) − 2·correlación(tau)
  const cum = new Float64Array(n + 1);
  for (let i = 0; i < n; i++) cum[i + 1] = cum[i] + x[i] * x[i];
  const energy = new Float64Array(tauMax + 1);
  for (let t = 0; t <= tauMax; t++) energy[t] = cum[window + t] - cum[t];

  const nfft = 1 << Math.ceil(Math.log2(n + window));
  const aRe = new Float64Array(nfft), aIm = new Float64Array(nfft);
  const bRe = new Float64Array(nfft), bIm = new Float64Array(nfft);
  aRe.set(x);
  bRe.set(x.subarray(0, window));
  fft(aRe, aIm);
  fft(bRe, bIm);
  for (let i = 0; i < nfft; i++) {       // A · conj(B)
    const r = aRe[i] * bRe[i] + aIm[i] * bIm[i];
    const im = aIm[i] * bRe[i] - aRe[i] * bIm[i];
    aRe[i] = r; aIm[i] = im;
  }
  fft(aRe, aIm, true);

  const diff = new Float64Array(tauMax + 1);
  for (let t = 0; t <= tauMax; t++) diff[t] = Math.max(energy[0] + energy[t] - 2 * aRe[t], 0);
  diff[0] = 0;

  // 2) Normalización acumulada (CMNDF): evita tau = 0 y reduce errores de octava.
  const cmndf = new Float64Array(tauMax + 1);
  cmndf[0] = 1;
  let running = 0;
  for (let t = 1; t <= tauMax; t++) {
    running += diff[t];
    cmndf[t] = running > 0 ? (diff[t] * t) / running : 1;
  }

  // 3) Primer tau bajo el umbral y descenso hasta su mínimo local.
  let tau = -1;
  for (let t = tauMin; t <= tauMax; t++) {
    if (cmndf[t] < threshold) { tau = t; break; }
  }
  if (tau < 0) return null;
  while (tau + 1 <= tauMax && cmndf[tau + 1] < cmndf[tau]) tau++;

  // 4) Interpolación parabólica para afinar por debajo de una muestra.
  let shift = 0;
  if (tau > 0 && tau < tauMax) {
    const a = diff[tau - 1], b = diff[tau], c = diff[tau + 1];
    const denom = a - 2 * b + c;
    if (denom > 0) shift = Math.min(1, Math.max(-1, (0.5 * (a - c)) / denom));
  }
  return sampleRate / (tau + shift);
}

/** Puerta de silencio + YIN: la función que usa la app. */
export function detectPitch(frame, sampleRate, { minRms = DEFAULT_MIN_RMS, ...options } = {}) {
  if (rms(frame) < minRms) return null;
  return yin(frame, sampleRate, options);
}
