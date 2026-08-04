# Estados de salida de los Quant Loops

Fuente única de verdad para `PASS`, `DEGRADED`, `BLOCKED` y `DONE`. Todos los
loops de `.claude/loops/quant/` referencian este archivo en lugar de redefinir su
vocabulario.

Un loop debe cerrar declarando exactamente un resultado en
`.claude/automation/runtime/current-task.md`. El ciclo de vida de la tarea se
registra por separado como `Status: idle | active | closed`; el resultado se
registra como `Result: PASS | DEGRADED | BLOCKED | DONE`.

## Regla general

El resultado se decide por condiciones observables, no por juicio. Si no puede
determinarse a partir de un artefacto o de la salida de un comando, el resultado
es `BLOCKED`, nunca `PASS`.

| Resultado | Significado | Condición exacta |
|---|---|---|
| `PASS` | El objetivo de la iteración o del loop se cumplió y quedó evidencia verificable. | (a) Todos los comandos requeridos terminaron con código 0; (b) todas las validaciones requeridas se ejecutaron y ninguna falló; (c) los artefactos obligatorios se escribieron y son legibles. Una acción posterior opcional o sujeta a aprobación puede quedar registrada sin convertir este resultado en `BLOCKED`. |
| `DEGRADED` | El objetivo se cumplió con una limitación no crítica, acotada y registrada. | Se cumplen (a) y (c), pero una validación no aplica por muestra insuficiente o una fuente no crítica no estaba fresca. Exige nombrar la limitación y el `n` disponible. Nunca se usa para ocultar un fallo. |
| `BLOCKED` | El objetivo actual no puede completarse sin intervención. | Cualquiera de: comando requerido con código distinto de 0; artefacto obligatorio ausente o ilegible; validación crítica fallida; evidencia insuficiente para decidir; o una acción necesaria para completar el objetivo actual requiere aprobación humana. |
| `DONE` | La tarea finita asociada al loop quedó cerrada por completo. | Se cumplen las condiciones de `PASS`, `/verification-gate` fue ejecutado y aprobado, la documentación obligatoria está actualizada y no quedan ítems necesarios abiertos en `current-task.md`. Cualquier loop puede alcanzar `DONE` cuando el alcance de la tarea es finito; las ejecuciones recurrentes normalmente terminan en `PASS`, `DEGRADED` o `BLOCKED`. |

## Precedencia

1. `BLOCKED` prevalece si existe cualquier bloqueo necesario para completar el objetivo actual.
2. En ausencia de bloqueo, `DEGRADED` prevalece sobre `PASS` cuando queda una limitación no crítica.
3. `DONE` es una elevación de `PASS` que solo se declara después del cierre documental y del verification gate.
4. Una aprobación para una acción posterior no bloquea el loop ya completado; debe registrarse como siguiente decisión.

## Umbrales de muestra (definidos en el código, no aquí)

`DEGRADED` por muestra insuficiente se decide con los umbrales que ya viven en la
configuración y el código. No inventar umbrales nuevos en un loop:

| Ámbito | Umbral | Origen |
|---|---|---|
| Diagnóstico por segmento | `n >= 15` | `src/sqp/audit/segments.py` |
| Monitor de degradación | `degradation_monitor.min_n` (30) | `configs/default.yaml` |
| Gate de CLV | `clv_gate.min_n` (30) | `configs/default.yaml` |
| Promoción opcional de calibrador | `AUTO_PROMOTE_MIN_N_VAL` (30) eventos independientes | `src/sqp/calibration/calibrator.py` |
| Sintonización de ratings | 200 / 80 | `src/sqp/backtesting/tuning.py` |

Si un loop necesita un umbral que no existe en el código, la configuración o una
decisión humana registrada antes de evaluar, el resultado correcto es `BLOCKED`
con una propuesta de umbral; no se improvisa un número después de ver los datos.

## Registro de evidencia

`current-task.md` debe contener:

1. `Status` y `Result` como campos separados.
2. Loop primario, skill y subloops de apoyo, si aplica.
3. Comandos ejecutados y sus códigos de salida.
4. Rutas de los artefactos producidos o leídos.
5. Métricas observadas con su `n`.
6. La limitación concreta si el resultado es `DEGRADED`.
7. La acción necesaria y quién debe aprobarla si el resultado es `BLOCKED`.
8. Acciones posteriores opcionales o sujetas a aprobación bajo `Next decision`.

## Lenguaje obligatorio

Se aplican `.claude/rules/betting-output-rules.md` y `.claude/CLAUDE.md`: siempre
"probabilidad estimada"; separar probabilidad estimada, probabilidad implícita,
edge, hit rate observado frente a prometido, ROI esperado estimado y ROI
realizado. Un `PASS` nunca significa que el sistema sea rentable: significa que
el loop se ejecutó y dejó evidencia.
