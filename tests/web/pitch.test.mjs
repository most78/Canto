// Port de legacy/tests/test_pitch.py y test_capture.py: señales sintéticas, sin micrófono.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { detectPitch, yin } from '../../app/js/pitch/yin.js';
import { hzToNote } from '../../app/js/pitch/notes.js';
import { fft } from '../../app/js/pitch/fft.js';

const SR = 44100;
const BLOCK = 2048;
const FREQS = [82.41, 110.0, 196.0, 261.63, 440.0, 659.26, 987.77];

const sine = (f, n = BLOCK, amp = 0.5, sr = SR) => Float64Array.from({ length: n }, (_, i) => amp * Math.sin(2 * Math.PI * f * i / sr));
const voiceLike = (f, n = BLOCK) => Float64Array.from({ length: n }, (_, i) => {
  let v = 0;
  for (let k = 1; k < 8; k++) v += (0.5 / k) * Math.sin(2 * Math.PI * k * f * i / SR);
  return v;
});
const cents = (a, b) => 1200 * Math.log2(a / b);

function seededNoise(n, sd, seed = 1) {
  let s = seed;
  const rand = () => ((s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296);
  return Float64Array.from({ length: n }, () => sd * Math.sqrt(-2 * Math.log(rand() + 1e-12)) * Math.cos(2 * Math.PI * rand()));
}

test('La3 = 440 Hz y Do central = Do3', () => {
  assert.equal(hzToNote(440).label, 'La3');
  assert.ok(Math.abs(hzToNote(440).cents) < 1e-9);
  assert.equal(hzToNote(261.6256).label, 'Do3');
});

test('agudo, plano y nota vecina', () => {
  assert.ok(Math.abs(hzToNote(440 * 2 ** (30 / 1200)).cents - 30) < 1e-6);
  const r = hzToNote(440 * 2 ** (70 / 1200));
  assert.equal(r.label, 'La#3');
  assert.ok(Math.abs(r.cents + 30) < 1e-6);
  assert.equal(hzToNote(246.94).label, 'Si2');
  assert.equal(hzToNote(261.63).label, 'Do3');
  assert.throws(() => hzToNote(0));
});

test('senos puros ±3 cents', () => {
  for (const f of FREQS) {
    const d = detectPitch(sine(f), SR);
    assert.ok(d && Math.abs(cents(d, f)) < 3, `${f}: ${d}`);
  }
});

test('señal con armónicos sin error de octava', () => {
  for (const f of FREQS) {
    const d = detectPitch(voiceLike(f), SR);
    assert.ok(d && Math.abs(cents(d, f)) < 3, `${f}: ${d}`);
  }
});

test('silencio y ruido blanco no dan nota', () => {
  assert.equal(detectPitch(new Float64Array(BLOCK), SR), null);
  assert.equal(detectPitch(seededNoise(BLOCK, 0.3), SR), null);
});

test('bloque demasiado corto', () => {
  assert.throws(() => yin(sine(440, 512), SR), RangeError);
});

test('señal suave (0,005) detectada con la puerta de la app y a varias frecuencias de muestreo', () => {
  for (const rate of [16000, 44100, 48000, 96000]) {
    const n = Math.round(rate * 0.064);
    const d = detectPitch(sine(180, n, 0.005, rate), rate, { minRms: 0.002 });
    assert.ok(d && Math.abs(d - 180) < 1, `${rate}: ${d}`);
  }
  assert.equal(detectPitch(seededNoise(3072, 0.004, 9), 48000, { minRms: 0.002 }), null);
});

test('FFT ida y vuelta', () => {
  const re = Float64Array.from({ length: 16 }, (_, i) => Math.sin(i));
  const im = new Float64Array(16);
  const copy = Float64Array.from(re);
  fft(re, im);
  fft(re, im, true);
  re.forEach((v, i) => assert.ok(Math.abs(v - copy[i]) < 1e-12));
});
