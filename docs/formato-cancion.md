# Formato de canción de Canto (`*.canto.json`)

El modo Canción lee la letra, los tiempos y la melodía de un archivo JSON. Es
independiente de cómo se dibuje: el renderer (`app/js/ui/lyricsTrack.js`) sólo
lo consume. Validación y normalización: `app/js/songs/model.js`.

```jsonc
{
  "format": "canto-song",
  "version": 1,
  "id": "mi-cancion",
  "metadata": { "title": "…", "artist": "…", "license": "…", "notes": "…" },
  "audio": { "kind": "file", "src": "canciones/Mi canción.m4a", "offset": 0.0 },
  // o { "kind": "piano" }: Canto toca la melodía de las voces con su piano
  "lyrics": {
    "lines": [
      { "id": "l1", "words": [
        { "id": "l1w1", "syllables": [ { "id": "s1", "text": "Can" }, { "id": "s2", "text": "ta" } ] }
      ] }
    ]
  },
  "voices": [
    { "id": "A", "name": "Voz A", "priority": 1, "events": [
      { "id": "e1", "start": 12.40, "duration": 0.35, "pitch": 55, "syllable": "s1" },
      { "id": "e2", "start": 12.80, "duration": 0.30, "pitch": 57, "syllable": "s2" }
    ] }
  ]
}
```

- **Tiempos** en segundos desde el inicio del audio (después de `offset`).
- **`pitch`** en MIDI: 69 = La3 = 440 Hz, 60 = Do3 en la convención de Canto.
  Admite decimales.
- **Melisma:** varias notas seguidas de una voz con la misma `syllable`, por
  ejemplo «lo-o-o-ove» = 4 notas → 1 sílaba. En pantalla se sigue leyendo la
  palabra entera; la trayectoria dibuja el recorrido.
- **Silencios:** son los huecos entre notas; no hace falta representarlos.
- **Varias voces:** cada una tiene sus `events`. Pueden apuntar a las mismas
  sílabas (unísono) o a otras. `priority` decide qué línea se canta en
  «Cántala entera» cuando suenan a la vez (menor = manda); es una regla
  explícita, sin armonización automática.
- **`expression`** (opcional en cada nota) queda reservado para énfasis,
  ataques, vibrato y dinámica. La V1 no lo usa.
- **Notas solapadas** dentro de una misma voz no se admiten: dan un error de
  validación.

## Dónde van los archivos

| Canción | Datos |
|---|---|
| Incluida (práctica) | `assets/songs/<id>.canto.json` + entrada en `assets/songs/index.json` |
| Tuya, local | `canciones/<mismo nombre que el audio>.canto.json` (fuera de Git: contiene la letra) |

## Qué falta para cantar «El mejor de tus errores»

En el proyecto sólo está el audio mezclado (`.m4a`: voces e instrumental
juntos). No hay letra, ni tiempos, ni melodía. Canto no se inventa esos datos.
Hay que crear
`canciones/Rayden - El mejor de tus errores ft. Alice Wonder (Videoclip Oficial) (128kbit_AAC).canto.json`
con:

1. **La letra**, separada en frases, palabras y sílabas. Sin descargarla de
   ningún servicio: o la escribes tú, o se transcribe en local desde tu propio
   audio (opción B).
2. **Los tiempos** de cada sílaba (inicio y duración), sincronizados con este
   audio.
3. **La melodía de cada voz** (Rayden y Alice Wonder): la nota de cada sílaba
   y las de cada melisma.

Formas de conseguirlo (ninguna está hecha todavía):

- **A. Manual asistido, sin dependencias nuevas.** Una herramienta en Canto
  para marcar sílabas «al vuelo» mientras suena la canción (tiempos) y ajustar
  la nota de cada una escuchándola al piano. Es lento, pero exacto y
  controlado.
- **B. Automático en local, con dependencias pesadas que habría que
  instalar** (necesita tu permiso):
  1. separar la voz de la mezcla con Demucs (PyTorch);
  2. transcribir y alinear la letra por palabra con Whisper;
  3. extraer la melodía de la voz aislada con YIN o pYIN y dividirla por
     sílabas.

  El resultado necesitaría revisión a mano, sobre todo en el dueto (qué voz
  canta cada parte).
- **C. Mixta.** Automático para una primera versión y corrección a mano en
  Canto.

Mientras tanto, la canción se puede escuchar y practicar por fragmentos (A–B)
en la misma pantalla.
