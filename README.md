# Canto

Aplicación personal para practicar canto con tu voz, en el navegador y en local.
Escuchas una frase al piano y la repites: una pista tipo Guitar Hero te muestra
la nota que toca cantar (violeta), si vas grave (cyan) o agudo (naranja) y cuándo
aciertas (verde). Guarda tu progreso, el mapa de tu voz y tu rango.

Todo funciona en tu PC: no hay servidor remoto, cuentas ni conexión a internet.
Tu voz no se graba ni se envía.

## Cómo arrancarla

Doble clic en **`start-canto.bat`**. Arranca un servidor local y abre el
navegador en <http://localhost:8765/>. Para apagarla, cierra la ventana negra.

Equivale a ejecutar, desde la carpeta del proyecto:

```powershell
python -m http.server 8765
```

y abrir `http://localhost:8765/`. Hace falta un servidor local (no basta con abrir
`index.html` a mano) para que el navegador permita el micrófono y cargue los
módulos y el audio. Funciona en Chrome o Edge.

Si tras actualizar Canto ves algo raro, recarga con **Ctrl+F5**.

Teclas: **Espacio**, acción principal (empezar, pausar o seguir, repetir);
**Esc**, pausa; **F11** o el botón «Pantalla completa».

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
start-canto.bat       arranque local
app/css/              diseño: tokens.css (colores, tipografía, espacio, radios), base, componentes, pantallas
app/js/
  main.js             arranque, navegación y teclado
  pitch/              notas (Hz → nota/cents), FFT y YIN
  audio/              AudioContext, micrófono (AudioWorklet) y piano muestreado
  game/               motor de rondas y puntuación, niveles, búsqueda de tu nota
  exercises/          lógica del ejercicio «Escalas» (sin DOM)
  state/              progreso (localStorage)
  songs/              biblioteca de canciones y repetición A–B
  ui/                 pantallas, pista en Canvas y mapa de voz
assets/piano/         14 muestras del Salamander Grand Piano (CC-BY, ver LEEME.md)
canciones/            tus canciones (local, fuera de Git)
tests/web/            tests en Node y fixtures generados con el Python original
legacy/               la versión anterior en Python/PySide6 (sólo referencia)
docs/                 contexto del proyecto y criterios
```

- El progreso se guarda en el navegador (`localStorage`). La primera vez se
  importa automáticamente el de la versión Python (`datos/progreso.json`).
- Las canciones se leen de la carpeta `canciones/`. También puedes abrir un
  archivo con «Abrir audio…».

## Cómo ejecutar los tests

Con Node.js (sin instalar nada más):

```powershell
npm test
```

Incluyen notas y cents, YIN, puntuación, niveles, progreso, búsqueda de nota,
canciones y el recorrido completo del ejercicio. Una parte compara la web con
resultados calculados por el código Python original. Para regenerar esos
resultados:

```powershell
.\.venv\Scripts\python.exe tests\web\make_fixtures.py
```
