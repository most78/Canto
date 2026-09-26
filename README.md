# Canto

Aplicación personal para practicar canto con tu voz, en el navegador y en local.

- **Escalas:** escuchas una frase al piano y la repites. Una pista tipo Guitar
  Hero te muestra la nota que toca cantar (violeta), si vas grave (cyan) o
  agudo (naranja) y cuándo aciertas (verde). Guarda tu progreso, el mapa de
  tu voz y tu rango.
- **Canciones:** la letra es la pista. Cada sílaba aparece a la altura de su
  nota y ocupa lo que dura; tu voz es una línea sobre esa trayectoria (verde
  afinada, cyan por debajo, naranja por encima). Una sílaba cantada bien el
  tiempo suficiente se ilumina con un fondo verde. Incluye una canción de
  práctica; tus canciones necesitan datos de letra y melodía
  (ver `docs/formato-cancion.md`).

Todo funciona en tu PC: no hay servidor remoto, cuentas ni conexión a internet.
Tu voz no se graba ni se envía.

## Cómo arrancarla

Doble clic en **`start-canto.bat`**. Arranca un servidor local y abre el
navegador en <http://localhost:8765/>. Para apagarla, cierra la ventana negra.

Equivale a ejecutar, desde la carpeta del proyecto:

```powershell
python serve.py
```

y abrir `http://localhost:8765/`. `serve.py` es `python -m http.server` con la
caché desactivada, para que el navegador cargue siempre la última versión del
código. Hace falta un servidor local (no basta con abrir `index.html` a mano)
para que el navegador permita el micrófono y cargue los módulos y el audio.
Funciona en Chrome o Edge.

Teclas: **Espacio**, acción principal (empezar, pausar o seguir, repetir);
**Esc**, pausa; **F11** o el botón «Pantalla completa».

En Canciones, **Latencia ±** ajusta a oído el desfase entre lo que oyes y tu
voz si notas que la línea llega tarde o pronto. Se guarda para la próxima vez.

## Cómo dar permiso al micrófono

1. En «Escalas», pulsa **Activar micrófono**.
2. El navegador pregunta si `localhost` puede usar el micrófono: pulsa
   **Permitir**.
3. Si lo denegaste antes, pulsa el icono a la izquierda de la dirección
   (candado o ajustes), pon **Micrófono → Permitir** y recarga la página.

Tras dar permiso, la lista muestra tus micrófonos por nombre. La app pide el
audio sin cancelación de eco, supresión de ruido ni control automático de
ganancia, porque alteran la altura.

Con cascos Bluetooth (unos Sony WH-1000XM5) usando su propio micrófono,
Windows los pasa a modo «manos libres» y el sonido baja de calidad. En la
versión Python la salida por MME enmudecía con el micro abierto; el navegador
usa la salida estándar de Windows (WASAPI), que sí sonaba en esa prueba. En la
versión web aún está pendiente de comprobar.

## Estructura del proyecto

```
index.html            la app (una página)
start-canto.bat       arranque local (serve.py: servidor sin caché)
app/css/              diseño: tokens.css (colores, tipografía, espacio, radios), base, componentes, pantallas
app/js/
  main.js             arranque, navegación y teclado
  pitch/              notas (Hz → nota/cents), FFT y YIN
  audio/              AudioContext, micrófono (AudioWorklet) y piano muestreado
  game/               motor de rondas y puntuación, niveles, búsqueda de tu nota
  exercises/          lógica de «Escalas» y del modo Canción (sin DOM)
  state/              progreso e historial de canciones (localStorage)
  songs/              modelo de canción, voces y partes, dificultad, feedback, puntuación,
                      tesitura, catálogo, reproducción, biblioteca y A–B
  ui/                 pantallas, pista de escalas, pista de letra (Canvas) y mapa de voz
assets/piano/         14 muestras del Salamander Grand Piano (CC-BY, ver LEEME.md)
assets/songs/         canciones incluidas (la de práctica)
canciones/            tus canciones (local, fuera de Git)
tests/web/            tests en Node y fixtures generados con el Python original
legacy/               la versión anterior en Python/PySide6 (sólo referencia)
docs/                 contexto del proyecto y criterios
```

- El progreso se guarda en el navegador (`localStorage`). La primera vez se
  importa automáticamente el de la versión Python (`datos/progreso.json`).
- Las canciones se leen de la carpeta `canciones/`. Para cantar una hace falta
  su `.canto.json` con letra, tiempos y melodía (`docs/formato-cancion.md`);
  sin él se puede escuchar y practicar A–B. También puedes abrir un archivo
  con «Abrir otro audio…».

## Cómo ejecutar los tests

Con Node.js (sin instalar nada más):

```powershell
npm test
```

Incluyen notas y cents, YIN, puntuación, niveles, progreso, búsqueda de nota,
canciones y el recorrido completo de Escalas. Del modo Canción cubren el
modelo de datos, voces y partes, melismas, la histéresis del color, el
acierto consolidado, la dificultad, la tesitura y los resultados ligados a la
letra. Una parte compara la web con
resultados calculados por el código Python original. Para regenerar esos
resultados:

```powershell
.\.venv\Scripts\python.exe tests\web\make_fixtures.py
```
