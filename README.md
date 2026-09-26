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

## Pista de voz (ejercicio principal)

Un juego inspirado en Guitar Hero, controlado cantando:

- **Eje vertical = altura.** Arriba, más agudo (zona naranja); abajo, más grave
  (zona azul). Las líneas son semitonos. La franja violeta del centro es **tu
  nota** (±50 cents), con su nombre a la izquierda.
- **Eje horizontal = tiempo.** Las notas son barras que avanzan de derecha a
  izquierda. Canta mientras la barra cruza la línea **AHORA**.
- **La bola es tu voz** y la estela, lo que acabas de cantar. Verde: en tu
  nota. Azul con flecha ▲: estás grave, sube. Naranja con flecha ▼: estás
  agudo, baja.
- Entre notas aparece «respira»: ahí no se puntúa nada.

Recorrido:

1. **Micrófono.** Actívalo y usa auriculares.
2. **Encuentra tu nota.** Haz una «u» cómoda de un segundo y para. La app busca
   un grupo de lecturas parecidas y propone su frecuencia (por ejemplo, La2).
   Puedes escucharla.
3. **¿Te resulta cómoda?** Sólo tú lo sabes. Si no, busca otra. La nota queda
   **fija** durante toda la partida.
4. **Partida.** Primero escuchas tu nota (no puntúa) y hay una cuenta atrás.
   Después llegan 5 notas de 1–2 s con 4 s para respirar entre ellas.
   - Opcionalmente, oyes la referencia antes de cada nota.
   - La barra se pinta de dorado en los tramos que aciertas.
   - Al acabar cada nota aparece su valoración: ¡Perfecta!, ¡Muy bien!, Bien,
     Un poco grave/aguda, No te oí claro o Sin cantar.
5. **Resultado.** Muestra:
   - estrellas y notas acertadas;
   - porcentaje del tiempo cantado que estuvo en tu nota;
   - tendencia grave o aguda en cents;
   - notas sin medir, que **no cuentan como fallo**;
   - la pregunta «¿Te resultó cómodo?». Si respondes «Me costó», te lleva a
     buscar otra nota.

Teclas: **Espacio** pausa o sigue (en preparar, empieza; en el resultado, repite).
**Esc** pausa o sale de pantalla completa. **F11** activa o quita la pantalla completa.

Reglas de puntuación (en `src/game/note_run.py`):

- Sólo puntúa audio nuevo dentro de la ventana de cada nota. Cada instante de
  audio se cuenta una vez. Cantar en los descansos no suma y aguantar más de
  lo que dura la barra tampoco.
- El volumen sólo separa silencio de sonido: **cantar más fuerte no da más puntos**.
- No puntúan el silencio, el sonido sin nota clara (ruido), los bloques
  capturados antes de una pausa ni el tiempo en que suena la referencia (más
  350 ms de cola).
- Si no hay señal fiable, la pista dice «no te oigo claro», no «desafinado».
  Si dejan de llegar datos del micro, lo avisa.
- Una octava de diferencia no cuenta como acierto. Lecturas a más de 19
  semitonos se tratan como dudosas.
- La animación (bola suavizada, partículas, panda) es independiente de la
  puntuación.

Es una aproximación de práctica, no una medida de laboratorio. No se mide
respiración, salud vocal ni timbre. No se graba ni se envía la voz.

## Canciones

Biblioteca local de `canciones/` (no se sube al repositorio). Permite
reproducir, buscar un punto, ajustar el volumen y repetir un fragmento A–B
(mínimo un segundo). Al entrar en Pista de voz la canción se pausa. Todavía no
se transpone, no se extrae la melodía y no se puntúan canciones.

## Verificar

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests/smoke_ui.py
```

- Los tests unitarios (43) cubren la detección de altura (YIN), la captura y
  el motor de puntuación y de búsqueda de nota. También siguen los tests del
  ejercicio anterior (`firefly.py`).
- `smoke_ui.py` recorre toda la interfaz con un reloj simulado y lecturas
  sintéticas: Canciones y A–B, buscar nota, cuenta atrás, partida, pausa y
  resultado. No abre el micro ni emite sonido. Guarda capturas a 1920×1080 en
  `docs/preview-*.png`.

## Estructura

| Carpeta / archivo | Qué hace |
|---|---|
| `src/audio/` | Captura (`capture.py`, bloques de unos 80 ms con marca de tiempo) y YIN (`pitch.py`). |
| `src/game/` | Lógica pura sin Qt: `reference.py` (buscar tu nota) y `note_run.py` (secuencia y puntuación). |
| `src/ui/theme.py` | Paleta, escala y hoja de estilos. |
| `src/ui/track.py` | La pista dibujada con QPainter (sólo lee el estado del juego). |
| `src/ui/practice.py` | Pantallas de preparar, jugar y resultado. |
| `src/ui/songs.py` | Reproductor y A–B. |
| `src/ui/main_window.py` | Cabecera, navegación, micrófono y tono de referencia. |
| `src/ui/panda.py` | Mascota decorativa. |
| `src/ui/firefly.py`, `tuner_widget.py` | Ejercicios anteriores. Ya no se usan; se conservan como referencia. |

Coordinación y criterios: `docs/context.md`, `docs/diseno-juegos.md` y `docs/criterios-vocales.md`.
