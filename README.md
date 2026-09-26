# Canto

App local de escritorio (Python + PySide6) para practicar canto con tu propia voz.
Diseñada para una pantalla grande: se abre maximizada, la tipografía se escala
con la altura de la pantalla y **F11** activa la pantalla completa.

Código: repositorio privado <https://github.com/most78/Canto> (rama `main`).

## Abrir

Haz doble clic en `iniciar.bat`.

Preparación inicial si no existe el entorno:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/main.py
```

## Escalas (juego principal)

Juego tipo Guitar Hero controlado cantando: **escuchas una frase al piano y la repites**.

- **Eje vertical = altura.** Cada línea es un semitono con su nombre (La2,
  Si2, Do#3…), en la convención franco-belga (La3 = 440 Hz). Arriba es más
  agudo y abajo más grave.
- **Eje horizontal = tiempo.** Las barras avanzan hacia la línea **AHORA**:
  - las **translúcidas** son la ESCUCHA: el piano las toca y no puntúan;
  - las **rosas** son TU TURNO: canta la nota que pone cada una mientras cruza
    la línea.
- **La bola es tu voz** y la estela, lo que acabas de cantar. En verde estás
  en la nota; en azul con flecha ▲, estás grave (sube); en naranja con flecha
  ▼, estás agudo (baja).
- Se recomienda cantar diciendo el nombre de cada nota (la, si, do…), para
  aprender cómo se llama lo que cantas. También vale una vocal.

Recorrido:

1. **Micrófono.** Actívalo. Probado con cascos Bluetooth Sony WH-1000XM5
   usando su micrófono: el piano sale por WASAPI, porque la salida MME enmudece
   al abrir el micro de unos cascos Bluetooth.
2. **Tu nota de partida.** Haz una «u» o un «do» cómodo de un segundo. La app
   la ajusta al semitono más cercano (por ejemplo, 214 Hz → La2) y la guarda
   para la próxima vez. Las escalas se colocan alrededor de ella.
3. **Elige nivel** entre los desbloqueados:

| Nivel | Qué es | Margen |
|---|---|---|
| 1 Tres escalones | 1‑2‑3‑2‑1 de la escala mayor | ±50 cents |
| 2 Cinco hacia arriba | 1‑2‑3‑4‑5 | ±50 |
| 3 Sube y baja | 1…5…1, más ágil | ±50 |
| 4 Arpegio | 1‑3‑5‑3‑1 | ±50 |
| 5 Terceras | saltos de tercera | ±50 |
| 6 Más precisión | como el 3 | ±35 |
| 7 Octava | escala completa | ±50 |
| 8 Arpegio de octava | 1‑3‑5‑8‑5‑3‑1 | ±35 |
| 9 Afinado fino | como el 3, rápido | ±25 |

4. **Ronda = 3 intentos.** Cada intento sigue el mismo orden: escuchar,
   cantar y respirar. El primer intento va alrededor de tu nota, el segundo lo
   más agudo que cabe en tu rango y el tercero lo más grave.
5. **Resultado:**
   - cada nota acertada o fallada, por intento;
   - % del tiempo cantado dentro de la nota y tendencia grave o aguda;
   - el **mapa de tu voz**: el % de acierto de cada semitono, con tu rango
     actual marcado;
   - la pregunta **«¿Te resultó cómodo?»**.

### Cómo se mide el avance

- **Superar un nivel:** ≥80 % de notas acertadas en 2 de los 3 intentos.
  Desbloquea el siguiente.
- **Mapa de tu voz:** una media móvil del acierto de cada nota. Las notas sin
  señal clara o sin cantar no cuentan.
- **Rango de trabajo:** empieza en tu nota −2 / +5 semitonos. Solo crece un
  semitono por un borde cuando esa nota se acierta bien (media ≥0,7 en ≥3
  mediciones) **y** respondes que la ronda fue cómoda. Los niveles que no
  caben en tu rango (como la octava) esperan a que crezca.
- Se guarda en `datos/progreso.json` (local, fuera de Git).

### Reglas de puntuación (`src/game/note_run.py`)

- Solo puntúa audio nuevo dentro de la ventana de cada nota cantada, y cada
  instante cuenta una vez.
- No suman: la escucha (más 0,6 s de cola), los descansos ni aguantar más de
  lo que dura la barra.
- **Cantar más fuerte no da más puntos**: el volumen solo separa silencio de
  sonido.
- El silencio y el ruido no son fallo. Si no hay señal fiable, la pista dice
  «no te oigo claro»; si dejan de llegar datos del micro, lo avisa.
- Una octava de diferencia no cuenta como acierto.
- Hay 0,25 s de margen para llegar a cada nota.
- La animación es independiente de la puntuación.

Es una aproximación de práctica, no una medida de laboratorio. No se mide
respiración, salud vocal ni timbre. No se graba ni se envía la voz.

## Canciones

Biblioteca local de `canciones/` (no se sube al repositorio). Permite
reproducir, buscar un punto, ajustar el volumen y repetir un fragmento A–B.
Al entrar en Escalas la canción se pausa. Todavía no se transpone ni se puntúa.

## Piano

El piano es Salamander Grand Piano (CC-BY 3.0, Alexander Holm): 14 muestras
en `assets/piano/` (ver `LEEME.md` allí). Se descodifica con Qt, sin
dependencias nuevas. Cada muestra se calibra con el mismo detector de altura y
se reafina a la frecuencia exacta; el error medido es de unos 1–2 cents. Si
faltaran las muestras, se usa un tono sintético.

## Verificar

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests/smoke_ui.py
```

- **Tests unitarios (53):** detección de altura (YIN), captura, salida de
  audio, motor de rondas, niveles, progreso y búsqueda de nota.
- **`smoke_ui.py`:** recorre toda la interfaz con reloj simulado y lecturas
  sintéticas: canciones, nota, nivel, escucha, turno, fallos, pausa,
  resultado y progreso guardado. Carga el piano, pero no emite sonido ni abre
  el micro. Guarda capturas a 1920×1080 en `docs/preview-*.png`.

## Estructura

| Carpeta / archivo | Qué hace |
|---|---|
| `src/audio/` | `capture.py` (bloques de unos 80 ms con marca de tiempo), `pitch.py` (YIN), `piano.py` (muestras), `output.py` (salida WASAPI). |
| `src/game/` | Lógica pura sin Qt: `reference.py` (tu nota), `note_run.py` (ronda y puntuación), `levels.py`, `progress.py`. |
| `src/ui/theme.py` | Paleta, escala y hoja de estilos. |
| `src/ui/track.py` | La pista con QPainter (solo lee el estado del juego). |
| `src/ui/practice.py` | Preparar, jugar y resultado. |
| `src/ui/voicemap.py` | Mapa de tu voz. |
| `src/ui/songs.py`, `main_window.py`, `panda.py` | Reproductor, ventana principal y mascota decorativa. |
| `src/ui/firefly.py`, `tuner_widget.py` | Ejercicios anteriores. Ya no se usan; se conservan como referencia. |

Coordinación y criterios: `docs/context.md`, `docs/diseno-juegos.md` y `docs/criterios-vocales.md`.
