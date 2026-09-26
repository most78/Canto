# Canto

App local de escritorio para practicar canto con tu propia voz.

## Abrir

Cierra la versión anterior y haz doble clic en `iniciar.bat`.

Preparación inicial si no existe el entorno:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/main.py
```

## Canción

Tu archivo de Rayden y Alice Wonder aparece en la biblioteca local. Puedes reproducir, buscar un punto, ajustar volumen y repetir un fragmento con A y B (mínimo un segundo). La canción todavía no se transpone ni se puntúa. No se extraen letras ni melodía de la mezcla.

## Ejercicios · Panda

1. Usa auriculares, abre esta pestaña y activa el micrófono. La canción se pausa.
2. Pulsa **Encontrar mi nota**. Haz una «u» cómoda de aproximadamente un segundo y después para. No hace falta sostenerla hasta quedarte sin aire.
3. La app reúne unos 0,3 segundos de lecturas cercanas, permitiendo pequeños cortes, y propone su frecuencia mediana sin redondearla a otra nota. Confirma si es cómoda o vuelve a buscar otra. La app no puede inferir comodidad física.
4. Puedes escuchar tu nota y volver a ella. Ilumina el claro del panda para reunir **3 segundos acumulados de luz**. Puedes respirar entre intentos; no se pierde progreso.
5. Cambiar de pestaña o desactivar el micro pausa la evaluación. Buscar otra nota inicia una ronda nueva.

No hay barra de volumen: la entrada sigue analizándose internamente para descartar silencio. Los avisos de señal aparecen discretamente en el texto del ejercicio. No se graba ni se envía la voz.

El margen inicial es ±50 cents, siguiendo el diseño actualizado y la asesoría. Es una aproximación de práctica, no una acreditación de afinación precisa. El objetivo permanece fijo durante la ronda. Se cuenta como máximo la duración de cada bloque nuevo evaluado, sin rellenar pausas. No se mide respiración, salud vocal o parecido al timbre original. La fiabilidad con voz real y auriculares Bluetooth necesita validación práctica.

## Coordinación

- **Crear app de canto**: implementación e integración.
- **Canto · Asesor de práctica vocal**: criterios y ejercicios en `docs/criterios-vocales.md`.
- **Canto · Diseño de juegos vocales**: experiencia didáctica en `docs/diseno-juegos.md`.

Son propuestas vivas. La implementación actual prioriza la referencia propia confirmada como cómoda y pausas libres; no implementa aún todo el diseño, como descansos guiados o dificultad configurable. El panda parpadea y se mece; las luciérnagas vuelan. La animación ambiental no suma puntos. Las instrucciones de afinación requieren 400 ms de persistencia y permanecen al menos 2 segundos; la confirmación de comodidad no desaparece con el silencio.

## Verificar

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests/smoke_ui.py
```

La prueba de interfaz simula dispositivos y salida del tono: verifica lógica y carga del M4A sin abrir el micro ni emitir sonido.

La búsqueda de referencia se detiene a los 4 segundos. Si falla, distingue falta de datos, señal baja, sonido sin tono y notas inconsistentes; muestra un diagnóstico textual sin guardar audio. La captura usa bloques de unos 80 ms ajustados a la frecuencia del dispositivo, en vez de 4096 muestras fijas. La app usa una puerta de silencio RMS de 0,002 para admitir señales suaves; YIN sigue rechazando señales sin periodicidad suficiente. Estos cambios requieren comprobación con el micro real.
