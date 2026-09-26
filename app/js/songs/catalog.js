// Catálogo de canciones para cantar:
// - incluidas en assets/songs/ (index.json), p. ej. la canción de práctica;
// - locales en canciones/: por cada audio se busca «<mismo nombre>.canto.json».
// Si una canción local no tiene datos, se dice exactamente qué falta.
// No se descarga nada de fuera: sólo archivos del proyecto.

import { AUDIO_EXTENSIONS, FOLDER, parseListing } from './library.js';

export const BUILTIN = 'assets/songs/';
export const DATA_SUFFIX = '.canto.json';

export const MISSING_DATA = [
  'La letra en texto, separada en palabras y sílabas.',
  'Cuándo empieza y cuánto dura cada sílaba (sincronizada con este audio).',
  'La melodía de cada voz: la nota de cada sílaba (y las de cada melisma).',
];

/** Entradas locales a partir del índice HTML de canciones/. */
export function localEntries(html) {
  const files = [...html.matchAll(/href="([^"?#]+)"/gi)].map((m) => decodeURIComponent(m[1]));
  const data = new Set(files.filter((f) => f.toLowerCase().endsWith(DATA_SUFFIX)));
  return parseListing(html).map((audio) => {
    const file = decodeURIComponent(audio.url.slice(FOLDER.length));
    const base = file.slice(0, file.lastIndexOf('.'));
    const dataFile = `${base}${DATA_SUFFIX}`;
    const has = data.has(dataFile);
    return {
      id: `local:${base}`, title: audio.name, source: 'local', audioUrl: audio.url,
      dataUrl: has ? FOLDER + encodeURIComponent(dataFile) : null,
      playable: has, missing: has ? [] : MISSING_DATA, expectedData: `canciones/${dataFile}`,
    };
  });
}

export async function loadCatalog(fetcher = globalThis.fetch) {
  const entries = [];
  try {
    const index = await (await fetcher(`${BUILTIN}index.json`, { cache: 'no-store' })).json();
    for (const file of index.songs) {
      const data = await (await fetcher(BUILTIN + file, { cache: 'no-store' })).json();
      entries.push({ id: `builtin:${data.id}`, title: data.metadata?.title ?? data.id, subtitle: data.metadata?.artist ?? '',
        source: 'builtin', audioUrl: null, dataUrl: BUILTIN + file, playable: true, missing: [] });
    }
  } catch { /* sin canciones incluidas */ }
  try {
    const response = await fetcher(FOLDER, { cache: 'no-store' });
    if (response.ok) entries.push(...localEntries(await response.text()));
  } catch { /* sin carpeta local */ }
  return entries;
}

export { AUDIO_EXTENSIONS };
