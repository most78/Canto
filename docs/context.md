# Canto — Contexto del proyecto

## ESTADO ACTUAL (26/09/2026) · Canto es una app web local

Lee esto primero. Lo de más abajo es historial.

### Qué pidió Marcos

- Migrar Canto de Python/PySide6 a una **web local**: HTML, CSS y JS vanilla
  con Web Audio y Canvas, sin frameworks, backend, build ni dependencias.
  Se arranca con `start-canto.bat`, que ejecuta `python -m http.server 8765` y
  abre el navegador.
- Rediseño **tranquilo**: carbón neutro y cálido, con color sólo con
  significado:
  - violeta: objetivo;
  - verde: acierto;
  - cyan: estás grave, sube;
  - naranja: estás agudo, baja;
  - dorado: recompensa;
  - rosa: identidad y momentos especiales.
  «Canto está tranquilo cuando tú estás tranquilo y cobra vida cuando cantas.»
- **Sin pandas:** Marcos pidió quitarlos («no aportan nada»). Su especificación
  de la migración los mencionaba, pero se siguió la petición más reciente. La
  celebración de los aciertos es con partículas, ondas y halo.
- Conservar toda la funcionalidad. El Python queda en `legacy/` como
  referencia, hasta validar la web con su voz.

### Arquitectura web

| Carpeta | Qué hace | Port de (legacy/src) |
|---|---|---|
| `app/js/pitch/` | `notes.js` (Hz → nota/cents, franco-belga), `fft.js`, `yin.js` (YIN 1:1) | `audio/pitch.py` |
| `app/js/audio/` | `context.js` (un AudioContext = un reloj), `capture-worklet.js` + `mic.js` (ventana de 64 ms cada ~21 ms), `piano.js` (muestras calibradas con YIN, programadas en el reloj de audio) | `audio/capture.py`, `piano.py`, `output.py` |
| `app/js/game/` | `noteRun.js` (rondas, juicios, fases, pausa, silencios), `levels.js`, `reference.js` | `game/*.py` |
| `app/js/state/progress.js` | Progreso en `localStorage`, mismo formato; importa `datos/progreso.json` la primera vez | `game/progress.py` |
| `app/js/exercises/scales.js` | Lógica de la pantalla de práctica sin DOM | `ui/practice.py` |
| `app/js/songs/` | Biblioteca (lee el índice de `canciones/` que publica http.server) y A–B | `ui/songs.py` |
| `app/js/ui/` | Pantallas, pista en Canvas (`track.js`), mapa de voz, canciones | `ui/*.py` |
| `app/css/tokens.css` | Sistema de diseño: colores, tipografía, espacio, radios y estados | `ui/theme.py` |

Diferencias con Python, todas intencionadas:

- **Un solo reloj** para todo: `AudioContext.currentTime`. Micrófono, juego y
  piano comparten reloj, así que el piano suena alineado con las barras de
  escucha.
- **Análisis solapado**, con menos latencia: ventana de 64 ms cada 21 ms, en
  vez de bloques de 80 ms. Al motor sólo se le pasa como duración el audio
  nuevo, así que nada puntúa dos veces.
- La **cabecera se oculta durante la ronda**, y cambiar de pestaña o de
  sección pausa.
- **No se migraron** `firefly.py` ni `tuner_widget.py`: ya estaban sustituidos
  y sin uso.

### Cómo arrancar y probar

```powershell
.\start-canto.bat          # o: python serve.py  →  http://localhost:8765/
npm test                  # 39 tests JS (node --test, sin dependencias)
.\.venv\Scripts\python.exe tests\web\make_fixtures.py            # regenera los resultados de referencia del Python
.\.venv\Scripts\python.exe -m unittest discover -s legacy/tests   # 53 tests del legacy
```

### Verificado

- **Equivalencia con Python:** `tests/web/python-equivalence.test.mjs` compara
  con resultados generados por el código Python original. Coinciden:
  - YIN: 47 casos, ≤0,01 cents;
  - notas y cents, y la colocación de los niveles;
  - la búsqueda de nota;
  - una **partida completa con ruido y fallos**: juicios, tiempo acertado,
    puntos, racha y resumen.
- **Tests JS del resto:** reglas del motor, niveles, progreso e importación,
  canciones y A–B, y el recorrido completo del ejercicio (`session.test.mjs`).
- **En el navegador integrado de Claude:**
  - la app carga sin errores de consola;
  - se importó el progreso real (Do2, nivel 2);
  - piano cargado (14 muestras);
  - ronda completa con **voz simulada** inyectada por el mismo camino que el
    micrófono: fases, colores, partículas, pausa y resultado;
  - canciones: listado, reproducción y bucle A–B.
- **Micrófono real:** no se ha probado. El navegador integrado lo bloquea; sí
  se comprobó que la app muestra bien el aviso de permiso denegado.

### Pendiente de probar con Marcos (en Chrome o Edge)

- Micrófono real con los WH-1000XM5 y detección de su nota.
- Que el piano se oiga con el micro de los cascos abierto. Si no se oyera,
  Chrome permite elegir la salida (`AudioContext.setSinkId`) y se podría
  añadir un selector.
- La latencia percibida y lo justos que se sienten los juicios.
- La reproducción de la canción en su navegador. En la sesión, una prueba mía
  dejó el volumen del elemento a 0 en el navegador integrado; ya está
  corregido.

### Modo Canción V1: «la letra es la pista»

Petición de Marcos: cantar canciones siguiendo la letra. La letra comunica qué
cantar, cuándo, la altura relativa (posición vertical), la duración (ancho) y
el movimiento de la melodía (trayectoria). Sin nombres de nota, cents ni
pentagrama.

Qué se ve:

- La voz es una **línea continua** (no un punto): verde afinada, cyan por
  debajo, naranja por encima. El color tiene **histéresis**, así que no
  parpadea.
- No hay mensajes correctivos: la posición de la línea ya los dice.
- **Acierto consolidado:** el fondo verde se rellena mientras cantas bien y se
  completa al acertar la sílaba, con un destello breve.
- Los errores no se castigan.

Implementado:

- `app/js/songs/model.js`: formato `*.canto.json` (ver
  `docs/formato-cancion.md`). Letra en frases, palabras y sílabas; `voices[]`
  con notas que apuntan a sílabas; melismas (varias notas por sílaba);
  `expression` reservado.
- `parts.js`: una voz, «Voz A/B», o «Cántala entera» (en los solapes manda la
  prioridad explícita). Agrupa las notas en unidades por sílaba y aplica la
  transposición **explícita**.
- `difficulty.js`: Inicial, Intermedio, Avanzado y Reto. Todos los parámetros
  en un solo sitio: tolerancia, histéresis, permanencia, fracción requerida,
  estabilidad, márgenes de timing y anticipación. `suggestNext` sólo sugiere
  subir, nunca cambia solo.
- `feedback.js`: pitch visual (mediana de 3 y exponencial de τ = 50 ms) y
  estado con histéresis y permanencia. Separado de la puntuación.
- `songRun.js`: puntuación por sílaba con el pitch en bruto, fracción afinada
  y tramo continuo mínimo. Resumen: % de sílabas, afinación, timing (mediana),
  mejor racha y **la frase que más costó, con su texto**.
- `tessitura.js`: avisa de fragmentos fuera del rango cómodo; nunca cambia
  notas.
- `playback.js`: la canción suena en el reloj de audio (archivo decodificado o
  piano).
- `exercises/singSong.js`: compensación de latencia (salida + entrada estimada
  + media ventana + ajuste manual ± ms guardado).
- `catalog.js`: canciones incluidas y locales, con la lista de datos que faltan.
- `ui/lyricsTrack.js` y `ui/sing.js`: la interfaz.
- `serve.py`: `http.server` sin caché, que ahora usa `start-canto.bat`. El
  navegador se quedaba con módulos antiguos.
- **Canción de práctica** `assets/songs/brilla.canto.json`: melodía tradicional
  de dominio público, letra original de Canto, audio tocado por el piano, con
  un melisma.

Verificado:

- 60 tests JS en verde (21 nuevos del modo canción).
- En el navegador integrado, con voz simulada inyectada por el mismo camino
  que el micrófono:
  - sílabas acertadas en verde y línea cyan por debajo en la frase grave;
  - melisma dibujado;
  - resultado con «Este fragmento fue el que más te costó: «…»»;
  - la canción de Rayden muestra qué datos faltan.

**Falta para cantar la canción real de Rayden:** su `.canto.json` con letra,
tiempos por sílaba y melodía de cada voz. Opciones en
`docs/formato-cancion.md`: manual asistido, o automático con Demucs + Whisper
+ extracción de pitch (dependencias pesadas: pedir permiso).

### Siguiente paso

1. Sesión real con Marcos:
   - Escalas: ajustar las constantes de `app/js/game/noteRun.js`, `levels.js`
     y `mic.js`.
   - Canción: probar «Brilla» y ajustar `app/js/songs/difficulty.js` y la
     latencia.
2. Decidir con Marcos cómo crear los datos de su canción (opción A, B o C de
   `docs/formato-cancion.md`).
3. Cuando la web esté validada con su voz, **proponer borrar `legacy/`**
   (seguirá en el historial de Git). La rama `pyside-restyle-wip` guarda un
   rediseño de PySide6 interrumpido; también se puede borrar.

### Trabajo con Git (Claude Code y Codex)

- Repositorio privado <https://github.com/most78/Canto>, rama `main`.
- La identidad local del repo es `most78 <marcos.ostos@gmail.com>`; la global
  del PC es otra cuenta (NoMonoMad) y no se toca.
- La URL del remoto incluye el usuario (`https://most78@github.com/most78/Canto.git`).
  Sin él, el push da un 403.
- `canciones/`, `.venv/`, `.backup/` y `datos/` están en `.gitignore`.
  `assets/piano/` sí se sube, porque la licencia CC-BY lo permite con
  atribución.

---

## Historial

### Estado anterior: «Escalas» en PySide6

Lee esto primero. Lo de más abajo es historial y puede describir decisiones
ya sustituidas: el panda protagonista, los 3 s acumulados o «Pista de voz» con
una sola nota.

### Qué pidió Marcos y qué se decidió con él

- **Rediseño para pantalla grande.** Colorida y legible a distancia, con el
  juego como protagonista. El panda queda solo como decoración.
- **Juego tipo Guitar Hero cantando.** Primero se hizo con una sola nota
  («Pista de voz»). Después Marcos lo replanteó: la nota cómoda es solo el
  **punto de partida**, y el juego son **escalas dentro de su rango**, cada
  vez más difíciles. El reto está en que unas notas le salgan y otras no.
- **Decisiones tomadas con él:**
  - cada intento es **escucha y luego canta**: el piano no se puntúa nunca;
  - avance = **mapa de voz** por semitono + **niveles** (80 % en 2 de 3
    intentos) + **rango** que crece solo con acierto **y** comodidad
    declarada;
  - **piano real** con muestras Salamander descargadas con su permiso (el
    sintetizador de Windows y la síntesis aditiva no le gustaron);
  - la nota única se **sustituye** por las escalas;
  - **nombres de nota en cada barra** («do2, re4…»). Canta diciendo el nombre
    de la nota: así aprende cuál es.
- **Cascos:** usará siempre unos Sony WH-1000XM5 Bluetooth, también como
  micrófono. Con su micro abierto la salida MME enmudece y WASAPI sí suena
  (comprobado con él con pitidos). Por eso `audio/output.py` elige la versión
  WASAPI de la salida predeterminada.

### Qué hay implementado

- **`src/game/note_run.py`: motor genérico sin Qt.**
  - Cada `Note` lleva su semitono respecto a la nota base, su intento y si es
    `demo` (escucha).
  - `build_round()` monta 3 intentos: escucha (con cue para el piano y audio
    silenciado más 0,6 s de cola), «¡tu turno!» (1,6 s), canto y 3 s de
    descanso.
  - Mantiene las reglas anteriores: solo audio nuevo, sin volumen, silencio y
    ruido no son fallo, pausa, persistencia de 400 ms y octava = fallo.
  - `phase()` da la fase para textos y dibujo.
- **`src/game/levels.py`:** 9 niveles como datos (patrón en semitonos,
  duración por nota y margen). `placements()` coloca los 3 intentos dentro del
  rango: cerca de la nota, borde agudo y borde grave. `note_name()` da los
  nombres en español.
- **`src/game/progress.py`:** nota base (MIDI), rango `lo/hi`, niveles
  desbloqueados, historial y mapa de voz (media móvil, α 0,35). Se guarda en
  `datos/progreso.json`, que está en `.gitignore`. `grow_range()` amplía un
  borde si su nota tiene media ≥0,7 con n ≥3; solo se llama cuando Marcos
  responde «Sí» a «¿Te resultó cómodo?».
- **`src/audio/piano.py`:**
  - 14 MP3 de Salamander en `assets/piano/` (CC-BY; atribución en `LEEME.md`),
    descodificados con `QAudioDecoder` sin dependencias nuevas;
  - cada muestra se calibra con YIN y se reafina ±1,5 semitonos como máximo,
    con un error de ~1–2 cents;
  - `phrase()` monta la frase entera en un solo buffer.
- **`src/audio/output.py`:** elección de la salida WASAPI, reproducción del
  buffer y tono sintético de respaldo.
- **UI:**
  - `track.py`: eje con nombres de nota, barras de escucha y de turno con su
    nombre, recortes al carril y marcador de intentos;
  - `practice.py`: tarjetas de micro, nota y nivel; ronda; resultado con los
    intentos, el mapa de voz y la pregunta de comodidad;
  - `voicemap.py`: el mapa de voz;
  - las pantallas de contenido van dentro de un `QScrollArea`. Si el contenido
    pedía casi toda la altura, Windows no maximizaba la ventana.
- **Sin uso:** `firefly.py`, `tuner_widget.py` y la síntesis `make_tone`, que
  queda solo como respaldo.

### Cómo arrancar y probar

```powershell
.\iniciar.bat                                                # o: .\.venv\Scripts\python.exe src\main.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v   # 53 tests
.\.venv\Scripts\python.exe tests\smoke_ui.py                  # recorrido completo + capturas docs/preview-*.png
```

### Verificado

- **Por software:**
  - 53 tests unitarios y la prueba de humo del recorrido completo pasan;
  - revisé visualmente las capturas a 1920×1080;
  - la app real arranca en el PC de Marcos con el piano cargado por WASAPI
    (dispositivo 12, 48 kHz), la ventana se maximiza a 1920×1009 y el ancho
    mínimo es de 1068 px.
- **Con Marcos:** oye el piano en sus cascos con el micro de los cascos
  abierto y le gusta cómo suena.

### Pendiente de probar con la voz de Marcos

- Una ronda completa real: si detecta bien su nota de partida, si la bola
  sigue su voz y si los juicios se sienten justos. Hay 0,25 s de reacción por
  nota y las notas van ligadas.
- Si el micro de unos cascos Bluetooth en modo manos libres (16 kHz) detecta
  bien notas graves con YIN. Si falla, probar otro micro o suavizar lecturas
  en el motor.
- El ritmo de cada nivel (`note_len`), el rango inicial (−2/+5) y los
  umbrales de crecimiento.
- Si cantar diciendo el nombre de la nota (consonantes) provoca demasiadas
  lecturas «no te oigo claro».

### Siguiente paso propuesto

1. Sesión real con Marcos en los niveles 1–2. Ajustar las constantes de
   `levels.py`, `note_run.py` (REACTION, TURN_GAP, REST) y `progress.py`
   según lo observado.
2. Si hay saltos de octava o lecturas erráticas con el micro Bluetooth,
   suavizar en el motor, nunca en la vista.
3. Más adelante:
   - sesión guiada (calentamiento, niveles y descanso);
   - bajar de nivel si cuesta;
   - melodías de canciones con la misma pista, que ya admite cualquier lista
     de notas con nombre.

### Trabajo con Git (Claude Code y Codex)

- Repositorio privado <https://github.com/most78/Canto>, rama `main`.
- La identidad local del repo es `most78 <marcos.ostos@gmail.com>`. La global
  del PC es otra cuenta (NoMonoMad); no se toca.
- La URL del remoto incluye el usuario (`https://most78@github.com/most78/Canto.git`).
  Sin él, el gestor de credenciales usa NoMonoMad y el push da un 403.
- `canciones/`, `.venv/`, `.backup/` y `datos/` están en `.gitignore`.
  `assets/piano/` sí se sube, porque la licencia CC-BY lo permite con
  atribución.
- Uno implementa y el otro revisa sobre `git diff`. Haced commits pequeños y
  con mensaje en español.

## Corrección de captura bloqueada

El usuario no obtenía referencia ni sosteniendo varias vocales. Se identificó una incompatibilidad potencial entre bloques fijos de 4096 muestras y los límites temporales del capturador de referencia. Ahora la captura ajusta bloques a unos 80 ms según frecuencia del dispositivo; puerta RMS de la app 0,002. Referencia por grupo de lecturas cercanas (±100 cents alrededor de candidato, 0,3 s acumulados, al menos 3 bloques), con confirmación del usuario. Intento limitado a 4 s mediante temporizador independiente: diagnóstico de falta de datos/señal baja/sin tono/inconsistencia. 24 tests pasan incluyendo 8–192 kHz y señal suave sintética. Causa exacta en micro real todavía sin confirmar.


## Corrección posterior: El claro del panda

Integrado el diseño actualizado de `docs/diseno-juegos.md`: panda y bambú dibujados
con QPainter, animación independiente a 30 Hz y tres luciérnagas. Pestaña Ejercicios · Panda.
Mensajes estables (400 ms de persistencia, mínimo 2 segundos de lectura), confirmación
persistente y captura de nota con tolerancia a cortes breves. Margen actual ±50 cents.
La animación no suma puntos. Revisados render y prueba de temporizador real de Qt.
La interacción acústica con el micrófono del usuario sigue pendiente de prueba.

## Iteración anterior: pestañas y juego (26/09/2026)

La interfaz actual separa Canción y Ejercicios · Luciérnaga. `src/ui/firefly.py`
sustituye al afinador visible. Se retiró la barra de volumen, conservando la puerta
de silencio interna. El ejercicio captura una frecuencia propia estable, pide confirmar
comodidad y permite reunir 3 segundos acumulados con pausas libres. Margen provisional
de juego ±75 cents; no representa afinación precisa ni mide respiración. La asesoría
propone ±50 y repeticiones cortas para evolución futura. README.md describe el estado actual.
14 tests pasan, más smoke UI; pendiente validación del juego con voz real.

Tareas de colaboración creadas a petición del usuario:
- Canto · Asesor de práctica vocal: `01a0db1d-1c02-72d0-adea-a4da78eca122`, documento `docs/criterios-vocales.md`.
- Canto · Diseño de juegos vocales: `01a0db1d-2669-7f31-937e-791846cdee3e`, documento `docs/diseno-juegos.md`.
Ambas diseñan; esta tarea integra código. La transposición de canciones sigue pendiente.

## Objetivo
App de escritorio para aprender/mejorar el canto. No busca formar un cantante profesional, sino poder cantar en público con soltura: afinación, entonación, respiración y ritmo correctos.

## Visión a futuro (fuera del MVP)
Modo "canción completa": eliges un tema de tu biblioteca local de audio ya poseído legítimamente (`canciones/`), la app separa voz/instrumental (Demucs), sincroniza la letra por timestamps (alineación forzada, p. ej. Whisper con timestamps por palabra) y, mientras cantas, compara tu voz en vivo con la pista vocal original en varios KPIs: afinación (cents), ritmo (si entras cuando toca), sostenimiento/respiración (si aguantas la nota lo que dura el original) y dinámica (volumen relativo).

Primera canción de prueba: "El mejor de tus errores" (feat. Alice Wonder), de Rayden — en `canciones/`.

El audio siempre sale de archivos que Marcos ya posee legítimamente en local. Nada de scraping/descarga de Spotify, YouTube, etc. La búsqueda lee de esa biblioteca local aunque visualmente recuerde a Spotify. `canciones/` está en `.gitignore`: el audio nunca entra en el repo.

## Stack
- Python, misma línea que tracker.exe (mismo flujo con PyInstaller).
- UI: **PySide6** (binding oficial de Qt, LGPL → sin problemas al distribuir el .exe). Tkinter se queda corto para refrescar el medidor muchas veces por segundo.
- Captura: `sounddevice`.
- Pitch: **YIN implementado a mano con numpy** (sin `aubio`: menos dependencias y sus wheels para Windows dan guerra).

## Convenciones
- Nombres de nota en español (Do, Re, Mi…), octavas franco-belgas: **La3 = 440 Hz**, Do central = Do3.
- Cents: negativo = bajo/plano, positivo = alto/agudo. ±50 como máximo respecto a la nota más cercana.
- Audio por defecto: 44100 Hz, bloques de 2048 muestras (~46 ms). Rango de búsqueda 70–1100 Hz.

## Estado actualizado (26/09/2026)

Primera app de escritorio implementada. `iniciar.bat` abre `src/main.py` usando `.venv`.
Incluye biblioteca local, reproducción del M4A, búsqueda temporal, volumen, repetición A–B,
selector de micrófono y afinador. Dependencias instaladas únicamente en `.venv`.
Captura bloques de 4096 muestras a la frecuencia predeterminada del dispositivo.
Verificación: 11 tests de pitch y `tests/smoke_ui.py` (carga de canción y controles).
El usuario confirma entrada de sonido por su micrófono. No hay comparación con la voz original.
Se añadió nota objetivo manual, tono de referencia de 1,5 segundos y guía «sube/baja/en la nota».
El indicador usa diferencia absoluta frente al objetivo, incluidas las octavas; el modo libre es opcional.
La medición se suspende durante el tono de referencia para no evaluar ese sonido.

## MVP inicial: medidor de afinación en tiempo real
Escucha el micro y muestra la nota detectada (ej. "La3") y la desviación en cents. Independiente del modo canción completa.

| Paso | Qué | Archivo | Estado |
|---|---|---|---|
| 1 | Captura de micro en bloques continuos | `src/audio/capture.py` | implementado; pendiente prueba física |
| 2 | Detección de pitch (YIN) por bloque | `src/audio/pitch.py` | ✅ hecho + tests |
| 3 | Hz → nota + cents | `src/audio/pitch.py` | ✅ hecho + tests |
| 4 | UI con indicador de afinación y reproductor | `src/ui/tuner_widget.py`, `main_window.py`, `src/main.py` | implementado y comprobado |

Los pasos 2 y 3 se hicieron primero porque son lógica pura, testeable sin micro ni dependencias nuevas.

### Tests
```
python -m unittest discover -s tests -v
```
Solo requiere numpy. Usan señales sintéticas (senos y señales con armónicos de 82 a 988 Hz, silencio, ruido). Precisión exigida: ±3 cents.

## Fuera de alcance por ahora
Separación de voz (Demucs), sincronización de letra, modo canción completa.

## Reglas de trabajo
- Desarrollo progresivo y entendible; nada de generar la app de golpe.
- Claude Code y Codex trabajan sobre el mismo repo Git: uno implementa cada tarea, el otro revisa cuando tenga sentido (preferiblemente sobre `git diff`).
- Sin APIs de pago (OpenAI/Anthropic) sin autorización explícita.
- Pedir antes de instalar dependencias, tocar configuración global o cualquier acción con coste.
