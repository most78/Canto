# Canto — Contexto del proyecto

## ESTADO ACTUAL (26/09/2026) · «Pista de voz» y rediseño general

Lee esto primero. Las secciones de más abajo son historial y pueden describir
decisiones ya sustituidas, como el panda protagonista, las luciérnagas o los
3 s acumulados.

### Qué pidió Marcos

Replantear el ejercicio de buscar y repetir una nota como un juego tipo Guitar
Hero controlado cantando, y rediseñar toda la app para pantalla grande:
colorida, legible a distancia y con el área de juego como protagonista. Los
pandas quedan como detalle decorativo. Esta petición sustituye las decisiones
de diseño anteriores que entren en conflicto con ella.

### Qué hay implementado

- **Motor puro** en `src/game/` (sin Qt, con tests):
  - `reference.py`: búsqueda de nota propia. Es la misma regla de antes,
    extraída de `firefly.py`: grupo de lecturas a ±100 cents, 0,3 s y 3
    bloques, límite de 4 s y diagnóstico del fallo.
  - `note_run.py`: secuencia de 5 notas (1–2 s) con 4 s de descanso y 4,5 s
    de entrada. Tiene reloj de juego con pausa, clasificación de cada bloque
    (hit, low, high, unclear, silence, muted) y juicio por nota.
  - Juicio por nota: ratio = acierto ÷ (duración − 0,25 s de reacción).
    Con ≥0,75 es perfecta, ≥0,45 muy bien y ≥0,15 bien. Si no, es fallo con
    dirección cuando hubo ≥25 % medido; «no te oí claro» cuando hubo ≥25 % de
    ruido; y si no, «sin cantar».
  - Los fallos rompen la racha; las notas sin medir no.
  - Resumen final: estrellas, tiempo en zona, tendencia (mediana ponderada en
    cents) y notas sin medir.
  - Referencia opcional antes de cada nota. El motor silencia su ventana más
    350 ms.
- **Captura** (`src/audio/capture.py`): cada bloque lleva la marca
  `time.monotonic()` del callback. `drain()` devuelve todos los bloques
  pendientes (cola de 16). Antes `latest()` descartaba bloques; se mantiene
  por compatibilidad.
- **Interfaz**:
  - `theme.py`: escala con `px()`, que depende de la altura de la pantalla.
  - `track.py`: la pista con QPainter y una animación de 60 fps que no puntúa.
  - `practice.py`: preparar (3 tarjetas), jugar y resultado.
  - `songs.py`: el reproductor rediseñado.
  - `main_window.py`: cabecera con navegación en pastillas, estado del micro y
    botón de pantalla completa. Lee el micro cada 30 ms y reproduce el tono con
    `sd.play`.
  - `panda.py`: la mascota.
  - `firefly.py` y `tuner_widget.py` ya no se usan; se conservan con sus tests.
- La copia del estado anterior está en `.backup/2026-09-26-antes-pista/`
  (fuera de Git) y en el primer commit del repositorio.

### Cómo arrancar y probar

```powershell
.\iniciar.bat                                            # o: .\.venv\Scripts\python.exe src\main.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v   # 43 tests
.\.venv\Scripts\python.exe tests\smoke_ui.py                  # recorrido completo + capturas docs/preview-*.png
```

### Verificado por software

- 43 tests unitarios pasan. Cubren la regla de puntuación:
  - el mismo resultado con bloques de 20 a 128 ms;
  - descansos que no suman y aguantar más que no suma;
  - volumen que no influye;
  - silencio y ruido que no son fallo;
  - una octava que es fallo;
  - bloques repetidos o antiguos que no suman;
  - pausa y referencia que no puntúan;
  - la persistencia de 400 ms en las indicaciones;
  - el objetivo fijo.
- La prueba de humo de la interfaz pasa: recorrido completo con reloj simulado.
- Revisé visualmente las capturas a 1920×1080 y abrí la app real en la
  pantalla de Marcos (1920×1080, escala 1,03): la ventana se maximiza y la
  página más ancha necesita unos 1363 px.

### Pendiente de probar con la voz de Marcos

- Si la búsqueda de nota funciona con su micrófono real, ya que las
  correcciones de captura anteriores siguen sin validar.
- Si la bola sigue su voz sin saltos molestos y la latencia se nota justa.
  Hay 0,25 s de margen de reacción y la marca de tiempo es la del callback,
  sin compensar la latencia de entrada.
- Si ±50 cents y los umbrales de juicio resultan justos y motivadores.
- Si el tono de referencia suena bien con sus auriculares. Si hay auriculares
  Bluetooth, la latencia de salida puede desalinear la escucha.
- Si 5 notas con 4 s de descanso es un buen ritmo.
- Si «Oírla antes de cada nota» (activado por defecto) ayuda o sobra.

### Siguiente paso propuesto

1. Sesión con la voz de Marcos. Anotar el diagnóstico de la búsqueda
   (segundos, bloques con nota, señal máxima) y cómo se sienten los juicios.
   Ajustar las constantes de `note_run.py` (TOLERANCE_CENTS, REACTION,
   duraciones y descanso) según lo observado. Todas están arriba del archivo.
2. Si hay saltos de octava de YIN con su voz, añadir suavizado de lecturas en
   el motor, no en la vista.
3. Sólo después: melodías de varias notas. `NoteRun` ya admite `durations`;
   habría que generalizar el objetivo a una lista de (inicio, fin, cents
   relativos) y dibujar cada barra a su altura. La pista ya tiene eje de
   semitonos.

### Trabajo con Git (Claude Code y Codex)

- Repositorio privado <https://github.com/most78/Canto>, rama `main`.
- La identidad local del repo es `most78 <marcos.ostos@gmail.com>`. La global
  del PC es otra cuenta (NoMonoMad); no se toca.
- La URL del remoto incluye el usuario (`https://most78@github.com/most78/Canto.git`).
  Sin él, el gestor de credenciales usa la cuenta NoMonoMad y el push da un 403.
- `canciones/`, `.venv/` y `.backup/` están en `.gitignore`.
- Uno implementa y el otro revisa sobre `git diff`. Haced commits pequeños y
  con mensaje en español.

---

## Historial

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
