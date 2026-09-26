// Canciones: lectura del índice de la carpeta y repetición A–B (port de songs.py).
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { parseListing, listSongs } from '../../app/js/songs/library.js';
import { ABLoop, clock } from '../../app/js/songs/abLoop.js';
import { attackIndex } from '../../app/js/audio/piano.js';

// Índice tal como lo genera `python -m http.server`.
const LISTING = `<!DOCTYPE HTML><html><body><h1>Directory listing for /canciones/</h1><ul>
<li><a href="Rayden%20-%20El%20mejor%20de%20tus%20errores%20(128kbit_AAC).m4a">Rayden - El mejor de tus errores (128kbit_AAC).m4a</a></li>
<li><a href="notas.txt">notas.txt</a></li>
<li><a href="Abba%20-%20Waterloo.MP3">Abba - Waterloo.MP3</a></li>
<li><a href="subcarpeta/">subcarpeta/</a></li>
<li><a href="../">../</a></li>
</ul></body></html>`;

test('lee los audios del índice de la carpeta, ordenados', () => {
  const songs = parseListing(LISTING);
  assert.deepEqual(songs.map((s) => s.name), ['Abba - Waterloo', 'Rayden - El mejor de tus errores (128kbit_AAC)']);
  assert.equal(songs[1].url, 'canciones/Rayden%20-%20El%20mejor%20de%20tus%20errores%20(128kbit_AAC).m4a');
});

test('sin servidor o sin carpeta: lista vacía', async () => {
  assert.deepEqual(await listSongs(async () => ({ ok: false })), []);
  assert.deepEqual(await listSongs(async () => { throw new Error('offline'); }), []);
});

test('reloj m:ss', () => {
  assert.equal(clock(0), '0:00');
  assert.equal(clock(209.58), '3:29');
  assert.equal(clock(NaN), '0:00');
});

test('A–B: B al menos 1 s después de A; repetir vuelve a A', () => {
  const loop = new ABLoop();
  loop.setA(10);
  assert.equal(loop.setB(10.5)[0], false);
  assert.equal(loop.ready, false);
  const [ok, text] = loop.setB(15);
  assert.ok(ok);
  assert.equal(text, 'Fragmento: 0:10 → 0:15');
  assert.equal(loop.wrap(16), null);          // repetición desactivada
  loop.enabled = true;
  assert.equal(loop.wrap(15.01), 10);
  assert.equal(loop.startPosition(20), 10);   // reproducir fuera del fragmento
  assert.equal(loop.startPosition(12), null);
  loop.setA(30);                              // nuevo A borra B y desactiva
  assert.equal(loop.enabled, false);
  assert.equal(loop.ready, false);
});

test('piano: se salta el silencio inicial del MP3 como en Python', () => {
  const data = new Float32Array(48000);
  for (let i = 2400; i < data.length; i++) data[i] = Math.sin(i / 10) * 0.5;
  assert.equal(attackIndex(data, 0.5, 48000), 2400 - 96);   // 2 ms antes del ataque
});
