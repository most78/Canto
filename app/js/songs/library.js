// Biblioteca local de canciones (carpeta canciones/, fuera de Git).
// El servidor local (python -m http.server) publica un índice HTML de la
// carpeta; aquí lo leemos para listar los audios sin necesitar backend.

export const AUDIO_EXTENSIONS = ['.m4a', '.mp3', '.wav', '.flac', '.ogg'];
export const FOLDER = 'canciones/';

/** Extrae los audios de un índice HTML de directorio → [{name, url}] ordenado. */
export function parseListing(html, base = FOLDER) {
  const songs = [];
  for (const match of html.matchAll(/href="([^"?#]+)"/gi)) {
    const href = match[1];
    if (href.includes('/') && !href.startsWith(base)) continue;   // sólo entradas de esta carpeta
    const file = decodeURIComponent(href.split('/').pop());
    const dot = file.lastIndexOf('.');
    if (dot < 0 || !AUDIO_EXTENSIONS.includes(file.slice(dot).toLowerCase())) continue;
    songs.push({ name: file.slice(0, dot), url: base + encodeURIComponent(file) });
  }
  songs.sort((a, b) => a.name.localeCompare(b.name, 'es'));
  return songs.filter((s, i) => i === 0 || s.url !== songs[i - 1].url);
}

export async function listSongs(fetcher = globalThis.fetch) {
  try {
    const response = await fetcher(FOLDER, { cache: 'no-store' });
    if (!response.ok) return [];
    return parseListing(await response.text());
  } catch {
    return [];
  }
}
