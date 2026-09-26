# Criterios vocales — primera propuesta para Marcos

26/09/2026. Objetivo: cantar melodías con tu propia voz y a una altura cómoda. Documento de coordinación: la implementación corresponde a **Crear app de canto**; la otra tarea de gamificación puede usar estos criterios. No son diagnóstico ni programa clínico.

## Evidencia y límites

- **Fuente institucional primaria:** el [NIDCD, Taking Care of Your Voice](https://www.nidcd.nih.gov/health/taking-care-your-voice) recomienda descanso vocal, evitar extremos y no cantar con voz ronca o cansada. Si aparece dolor, parar; si persisten molestias o cambios de voz, consultar a un profesional. Esto no determina qué notas te resultarán cómodas.
- **Fuente primaria del algoritmo:** [Alain de Cheveigné, anuncio de YIN (2002)](https://www.auditory.org/postings/2002/26.html), consultado mediante su texto indexado: YIN estima frecuencia fundamental (F0); el autor distingue expresamente esa estimación de un modelo de percepción de altura. Referencia original: de Cheveigné y Kawahara, *JASA* 111, 1917–1930, [DOI 10.1121/1.1458024](https://doi.org/10.1121/1.1458024). No se pudo consultar el artículo completo; no se atribuyen a él umbrales pedagógicos.
- **Evidencia local:** leídos `docs/context.md`, `README.md` y `src/audio/pitch.py`. El detector devuelve Hz o ausencia de estimación; no expone una probabilidad calibrada de acierto. Los tests sintéticos descritos no demuestran precisión equivalente con la voz real de Marcos. El README fija actualmente verde a ±15 cents. El contexto mezcla una configuración inicial de 2048 muestras con un estado actualizado de 4096: las métricas temporales deben usar la captura efectiva.

Los números y el recorrido siguientes son **decisiones provisionales de producto**, pendientes de probar contigo; no estándares clínicos ni resultados demostrados por esas fuentes.

## Tu voz, la altura y la canción

**Altura** es lo grave o agudo de una nota, relacionada con F0. **Timbre** es su cualidad sonora: dos personas pueden cantar la misma nota y sonar distintas. No necesitas copiar el color, aspereza o intensidad del cantante.

**Una octava** equivale a 12 semitonos: La3 = 440 Hz y La2 = 220 Hz, según la convención de Canto. Cantar toda la melodía una octava más grave conserva nombres de notas e intervalos y suele permitir mantener el acompañamiento original. **Transponer** desplaza todas las notas el mismo número de semitonos: bajar tres, por ejemplo, puede encajar mejor que bajar doce; requiere adaptar también el acompañamiento para mantener la relación armónica. Una octava es un caso particular de transposición y conserva las clases de altura.

Usaremos «zona cómoda de trabajo» para notas que puedas repetir con facilidad, no los extremos que alcances una vez. Empieza con un «mmm» o una vocal espontánea a volumen cómodo; observa la nota sin perseguirla. Prueba después pequeñas variaciones hacia arriba y abajo, con pausas, y marca «fácil / cuesta / incómodo». La app no debe inferir comodidad del afinador ni etiquetarte tenor, barítono, etc.

Para una canción, prueba una frase y sus puntos más graves, más agudos y más repetidos. Elige el desplazamiento por la comodidad de toda esa parte, no sólo por la primera nota. Transponer no reduce la amplitud de la melodía: si sigue siendo demasiado amplia, elige otra frase o una adaptación explícita de la melodía.

## Primer ejercicio: encontrar y repetir tu nota

1. Con auriculares y la canción pausada, emite una vocal cómoda durante aproximadamente un segundo, sin intentar alcanzar una referencia externa. Repite para encontrar una altura fácil. En la app actual, usa Libre para orientarte y selecciona manualmente una nota cercana sólo si sigue siendo cómoda; capturar tu frecuencia propia como objetivo queda propuesto para implementación.
2. Escucha la referencia y luego cántala **1–2 segundos**. Respira con normalidad y descansa **4–6 segundos**, o más si lo necesitas. Haz **tres intentos**; acabar antes también vale.
3. Propongo una zona inicial de **±50 cents respecto al objetivo fijo**, visible como margen de práctica. No recalcular el objetivo como «nota más cercana» mientras cantas: eso podría mostrar éxito en una nota equivocada. Permitir encontrar la nota antes de contar el tramo sostenido.
4. Preguntar «¿salió fácil?» tras el intento. Cuando repetir resulte cómodo, aumentar un poco la duración **o** reducir el margen, una cosa cada vez y sin progresión automática por puntuación.

La meta inicial es repetir con comodidad un sonido propio; no aguantar al máximo ni mantener una línea perfectamente inmóvil.

## Qué medir y qué no

Estas son propuestas técnicas derivadas del funcionamiento local, pendientes de validación con voz y micrófono reales.

| Señal o métrica | Uso razonable y límite |
|---|---|
| F0 y error frente a objetivo | En voz aislada y suficientemente periódica, calcular `1200 × log2(F0 / objetivo)`. Mostrar tendencia y mediana del error; conservar octavas, sin reducir el error a ±50 cents. No garantizar exactitud de laboratorio. |
| Estabilidad | Dispersión robusta del error en la parte sostenida, separada del error medio. Una nota puede ser estable y estar lejos del objetivo. No penalizar automáticamente vibrato o deslizamientos expresivos. |
| Tiempo dentro del margen | Contar sólo intervalos medidos válidos y mostrar también cuánto del intento pudo medirse. No presentar un porcentaje alto basado en unas pocas muestras como éxito completo. |
| Continuidad | «Tiempo con tono detectado», aproximado por bloques. Un hueco puede ser consonante, ruido, señal débil o fallo del detector; no demuestra corte respiratorio. No rellenar huecos como si fueran aciertos. |
| Respiración, apoyo, salud, tipo de voz, calidad del timbre | No se deducen de F0. Una duración corta no diagnostica falta de aire. El RMS local depende de ganancia y distancia y tampoco mide respiración. |

Usar «no evaluable» cuando falte señal suficiente. Ruido, acompañamiento, dos voces, saturación y errores de octava pueden invalidar la comparación. Un salto de octava sospechoso merece revisión, no una corrección automática hacia la nota objetivo. El umbral interno de YIN no equivale a confianza porcentual.

## Después: melodía adaptada y ritmo

Propuesta futura; la app aún no extrae ni puntúa la melodía de canciones.

- Construir y revisar una referencia de **una sola línea vocal**, especialmente en el dúo Rayden/Alice Wonder. No usar la mezcla como verdad de afinación. Aplicar el desplazamiento acordado a toda la referencia: `objetivo_nuevo = objetivo_original × 2^(semitonos/12)`.
- Evaluar por separado altura respecto a esa referencia e intervalos entre notas. Si se elige una octava distinta, fijarla antes del intento; no perdonar cualquier salto de octava nota por nota. El timbre y la similitud espectral al artista no forman parte de la nota.
- Para ritmo, empezar con entradas de vocales a un pulso lento. Comparar entradas y duraciones con tiempos de referencia tras calibrar latencia de reproducción/captura. YIN solo no detecta de forma fiable ataques de sílabas o consonantes: hará falta segmentación de audio y validación. Con bloques de 4096 muestras a 44,1 kHz, cada bloque dura unos 93 ms; no prometer precisión de milisegundos.
- Mostrar «antes / a tiempo / después» con margen ajustable, inicialmente amplio. Si se permite alineación temporal flexible para comparar afinación, mantener aparte el error temporal original para no ocultar fallos de ritmo.

## Acuerdo propuesto entre tareas

**Crear app de canto:** priorizar nota cómoda propia, margen inicial configurable, intentos cortos con pausas, cobertura de señal y respuesta de comodidad; dejar canción transpuesta y ritmo como siguiente fase. Validar con intentos reales escuchados, contrastando detección y percepción antes de usar puntuaciones.

**Gamificación:** premiar completar intentos cómodos y reconocer pausas; no premiar extremos, duración máxima, volumen ni parecido al cantante. No convertir señal no evaluable en fallo ni presentar métricas acústicas como salud vocal.

## Conversación con Marcos: ajuste de la propuesta

Marcos suele cantar acompañando canciones, no tararear por su cuenta. Recuerda dificultad con objetivos posiblemente Sol3 y La1; esas notas no están confirmadas. Explica, con cierta incertidumbre, que el sonido inicialmente salía cómodo, pero al no alcanzar el verde intentaba subir o bajar y terminaba apretando o haciendo esfuerzo físico. Es un relato subjetivo, no una medición ni un diagnóstico. No sabemos si intervenían la altura elegida, el margen de ±15 cents, la interpretación del indicador o un error de detección.

**Decisión provisional para implementación y gamificación:** evitar intentos abiertos de perseguir el verde. Separar emitir, descansar y recibir información. Empezar con un sonido propio cómodo de aproximadamente un segundo, sin flechas correctivas durante esa primera emisión; usar una frase familiar si ayuda a encontrarlo. Con señal suficiente, proponer esa altura como referencia y fijarla para el siguiente intento, sin mover el objetivo continuamente. Si Marcos indica esfuerzo, terminar el intento sin penalización y volver a elegir una altura cómoda tras descansar. La app no puede detectar tensión física a partir de YIN.

**Siguiente práctica propuesta:** emitir brevemente, descansar y repetir sólo si sigue resultando fácil. No sostener más tiempo ni aumentar volumen para lograr el verde. Valorar primero «salió cómodo» y después la cercanía a la referencia; no interpretar un indicador fuera de margen como una orden de esforzarse más.
