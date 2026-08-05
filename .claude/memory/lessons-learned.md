# Lessons Learned

## 2026-08-05 — Una corrección verificada en una rama del código no está verificada en las demás

El fix de M-01 (fallback histórico del stream servido, 2026-08-02) se dio por
cerrado con 10 tests y health check en OK. Tres días después se descubrió que
**la ruta de tenis nunca lo había recibido**: `_settle_tennis` no llamaba al
fallback, y la resolución de clave del histórico usaba el nombre de liga en vez
del tour. Justo la rama con la peculiaridad era la no probada. Mientras tanto el
sistema anulaba como `stale` filas cuyo resultado ya estaba descargado.

Regla: al cerrar un fix que atraviesa un dispatch (familia de deporte, tipo de
mercado, modo de ejecución), enumerar las ramas y probar cada una, o declarar
explícitamente cuáles quedan sin cubrir.

## 2026-08-05 — Declarar un estado no es medirlo

Tres afirmaciones falsas de estado en tres días: el `pick_mode` revertido el
07-31 sin documentar; "Suite completa verde" con 5 tests en rojo; "Ruff y Mypy no
instalados" con ambos instalados y limpios. La tercera vino acompañada de un
`Result: PASS` que violaba la regla explícita del propio `STATES.md`.

La regla existía y no se cumplía porque **nada la hacía cumplir**. La corrección
no fue escribir la regla otra vez, sino `pass_result_missing_evidence()`: un
PASS sin comandos ni artefactos ahora es un error de la comprobación de salud.

Regla: una norma de proceso sin verificación automática es una preferencia, no
un control. Si importa, tiene que fallar sola.

## 2026-08-05 — No cambiar el estadístico después de ver que el actual no aprueba

Con el gate intradía en n=29/30 y ambas medianas en +0.0000%, la tentación era
pasar el criterio a la media, que sí favorece al grupo intradía. El análisis lo
desaconsejó: la media intradía sola es ruido (P(>0)=0.65), sin tenis es negativa,
y la ventaja frente a los picks de las 11:00 cae a la mitad al quitar **una**
fila —que además tiene un CLV de −48.5%, imposible como resultado de apuesta.

El problema estructural de la mediana con 41% de empates es real y merece
solución, pero la solución honesta es pre-registrar un test que trate empates
ANTES de acumular más muestra, no adoptar el estadístico que aprueba hoy.
