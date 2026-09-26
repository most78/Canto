# Canto — Contexto del proyecto

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
