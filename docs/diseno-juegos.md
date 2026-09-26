# Canto: el claro del panda

> **Sustituido (26/09/2026).** Marcos pidió cambiar este juego por una pista
> tipo Guitar Hero en la que las notas avanzan hacia una línea AHORA, con eje
> vertical de altura. Después lo amplió a **«Escalas»**: escuchar una frase al
> piano y repetirla, con niveles, un mapa de la voz y un rango que crece con
> acierto y comodidad. El panda queda sólo como detalle decorativo. El estado actual está en `docs/context.md` y `README.md`.
> Siguen vigentes los principios de puntuación de este documento: objetivo
> fijo, sólo audio nuevo, silencio y ruido sin penalizar, sin premio por
> volumen ni por aguantar, y 400 ms antes de dar una indicación. La mecánica
> de «3 s acumulados» y la escena del claro ya no se usan.

Propuesta actualizada (26/09/2026): leídos `README.md`, `docs/context.md` y los criterios ya disponibles en `docs/criterios-vocales.md`. Marcos prefiere pandas, su animal totémico: serán protagonistas, acompañados por luciérnagas. Los parámetros siguen siendo provisionales y requieren prueba con él. Esta propuesta describe el juego, no acredita técnica vocal ni comodidad a partir del micrófono.

## Primera experiencia

Pestañas separadas: **Canciones** y **Ejercicio**. En Ejercicio, un panda pequeñito está sentado en un claro de bambú. Al acercarte a tu nota, aparecen luciérnagas y el claro se ilumina poco a poco. El panda parpadea y se mece suavemente; cuando respiras, espera tranquilo. Al completar la meta, saluda entre tres luciérnagas encendidas. No hay afinador, barra de volumen, ranking, vidas ni pérdida de luz. Una frase guía cada momento; la dirección se expresa con palabras y la luz recogida también con texto, sin depender solo del color.

El panda es un compañero, no una mascota que dependa de tu rendimiento: nunca pasa hambre, se entristece ni te pide seguir. Su tamaño no depende del volumen y no salta más alto al cantar más agudo. Estética sencilla y tierna, con pocos movimientos y sin sonidos de recompensa mientras se escucha el micrófono.

Meta inicial: **acumular 3 segundos cerca de una nota cómoda**, repartidos en intentos breves. Siguiendo los criterios vocales, invitar a sonidos de 1–2 segundos y pausas de 4–6 segundos o más, sin exigir una emisión continua de tres segundos. Ofrecer terminar tras tres intentos aunque no se haya reunido toda la luz. El juego trabaja encontrar y volver a una nota; esta primera versión no evalúa respiración, ritmo, timbre ni canto de canciones.

## Elegir la referencia desde tu voz

1. «Haz un sonido suave en una altura que te resulte fácil, con “mmm” o una vocal cómoda». Gesto pendiente de validación por la asesora.
2. Capturar un tramo breve de voz fiable y razonablemente estable (propuesta técnica: 0,5 segundos consecutivos con variación de ±50 cents respecto a su mediana). Usar su frecuencia mediana como objetivo, sin obligar a redondear a una nota musical.
3. Si no se obtiene una referencia: «Vamos a buscar otro sonido que te salga fácil». Permitir reintentar o salir, sin cuenta atrás ni nota de fracaso.
4. Preguntar «¿Ese sonido te resulta cómodo?» con **Sí, empezar** / **Buscar otro**. La app no puede inferir esfuerzo a partir de afinación o volumen.

El objetivo queda **fijo durante toda la ronda**. Nunca sigue a la voz ni cambia a la nota más cercana. «Buscar otro sonido» vuelve a preparación e inicia una ronda nueva. No se compara el timbre con el de nadie.

## Estados y mensajes

| Estado | Qué ocurre | Mensaje / salida |
|---|---|---|
| Preparación | Se busca referencia; no se puntúa. | «Busca un sonido fácil, a tu ritmo». |
| Confirmación | Se guarda la referencia propuesta. | «¿Te resulta cómodo?» |
| Ronda: cerca | Las luciérnagas iluminan el claro; suma tiempo. | «Por ahí, suave y cómodo». |
| Ronda: fuera | Conserva toda la luz; guía breve tras una desviación persistente. | «Prueba un poquito más agudo» / «Prueba un poquito más grave». |
| Ronda: silencio | Conserva luz; sin límite para volver. | «Respira; seguimos cuando quieras». |
| Ronda: lectura incierta | No suma ni ofrece dirección. | «No distingo bien la nota. Puedes volver a probar». |
| Pausa / micro desconectado | Detiene evaluación y conserva luz. | «En pausa» / «Revisa el micrófono para seguir». |
| Completado | Claro iluminado; el panda saluda brevemente. | «¡Has iluminado el claro! Puedes descansar o jugar otra vez». |

Controles permanentes: **Pausar**, **Buscar otro sonido**, **Terminar**. Una ronda no caduca. Tras unos 20 segundos activos sin completar, ofrecer «Puedes descansar o buscar un sonido más cómodo» sin reiniciar ni quitar progreso. No felicitar por cantar fuerte o aguantar más.

## Cuándo se recoge luz

- Tolerancia inicial propuesta: **±50 cents respecto al objetivo fijo**, incluida la diferencia de octava, alineada con los criterios vocales. Es una zona de aproximación generosa, no una afirmación de afinación exacta. No estrecharla automáticamente en esta versión.
- Sumar únicamente duración de audio nuevo con voz y pitch fiables dentro de esa zona. Silencio, ruido, lectura incierta y desviación suman cero; nunca restan. El volumen solo puede ayudar a validar señal, nunca multiplicar puntos.
- Progreso = `min(1, segundos válidos acumulados / 3)`. Contar tiempo de audio procesado, no fotogramas de animación ni número de callbacks. No contar dos veces bloques solapados ni prolongar la última lectura durante huecos o pausas.
- Suavizar visualmente el movimiento, pero puntuar con datos válidos. Mostrar una dirección solo si persiste unos 400 ms, para evitar órdenes contradictorias por fluctuaciones breves. Sin lectura fiable, ocultar esa dirección.
- Al alcanzar la meta, detener la puntuación. Sin rachas, bonos por continuidad, premios por intensidad ni recompensa adicional por prolongar el sonido.

## Alcance para integrar

Un solo minijuego, una referencia por ronda, un panda y tres luciérnagas. PySide6 puede dibujar el panda con círculos y elipses (cuerpo, orejas, manchas y patas), dos tallos de bambú y halos con `QPainter`; animación sencilla con `QTimer`. No requiere imágenes generadas, sprites ni nuevas dependencias. Reutilizar captura y YIN existentes. La tarea integradora debe comprobar cómo distinguir voz fiable de ruido: no convertir cualquier frecuencia devuelta por YIN en progreso.

Pausar la reproducción de canciones al comenzar la preparación y mantenerla pausada durante el ejercicio. No extraer melodía de la mezcla instrumental. No hacen falta tono de referencia, grabación, cuentas, historial, niveles ni selección manual de notas para esta iteración.

Comprobaciones de aceptación: tres segundos válidos completan igual a distintas tasas de refresco; el silencio conserva luz; una lectura antigua no suma; una octava distinta no cuenta como objetivo; la referencia permanece fija; el ruido no ofrece instrucciones de afinación. La asesora valida pedagogía y comodidad; **Crear app de canto** integra y verifica el comportamiento.

## Preferencia de Marcos y siguiente ajuste

Preferencia recibida: pandas, aunque sean pequeños. Propuesta elegida: **El claro del panda**, con las luciérnagas como luz del entorno. Empezar con un panda tranquilo y expresivo; el aspecto se puede ajustar después de ver la primera versión, sin cambiar las reglas del ejercicio.
