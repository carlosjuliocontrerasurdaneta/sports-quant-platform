# Estados de salida de los Quant Loops

Fuente única de verdad para `PASS`, `DEGRADED`, `BLOCKED` y `DONE`. Todos los
loops de `.claude/loops/quant/` referencian este archivo en lugar de redefinir su
propio vocabulario (auditoría 2026-07-29, K-003: los 14 loops usaban cinco
vocabularios distintos y ninguno definía los cuatro estados).

Un loop **debe** cerrar declarando exactamente uno de estos estados, con la
evidencia que lo justifica, en `.claude/automation/runtime/current-task.md`.

## Regla general

El estado se decide por condiciones **observables**, no por juicio. Si el estado
no puede determinarse a partir de un artefacto o de la salida de un comando, el
estado es `BLOCKED`, nunca `PASS`.

| Estado | Significado | Condición exacta |
|---|---|---|
| `PASS` | El objetivo del loop se cumplió y quedó evidencia verificable. | (a) Todos los comandos del loop terminaron con código de salida 0; **y** (b) todas las validaciones del loop se ejecutaron y ninguna falló; **y** (c) los artefactos que el loop declara se escribieron y son legibles; **y** (d) ninguna acción quedó pendiente de aprobación humana. |
| `DEGRADED` | El objetivo se cumplió parcialmente con una limitación acotada, identificada y registrada. | Se cumple (a) y (c), pero una validación no aplica por **muestra insuficiente** o una fuente no crítica no estaba fresca. Exige nombrar la limitación y el `n` disponible. Nunca se usa para ocultar un fallo. |
| `BLOCKED` | El loop no puede continuar sin intervención. | Cualquiera de: comando con código de salida ≠ 0; artefacto declarado ausente o ilegible; validación crítica fallida; evidencia insuficiente para decidir; o la siguiente acción requiere aprobación humana (ver `.claude/automation/autonomy-policy.md`). |
| `DONE` | El trabajo asociado a la tarea se cerró por completo, no solo esta iteración. | `PASS` **y** `/verification-gate` ejecutado y aprobado **y** documentación actualizada (bitácora Obsidian del día) **y** sin ítems abiertos en `current-task.md`. Un loop periódico (01–04, 06, 07, 13) termina en `PASS`/`DEGRADED`/`BLOCKED`; solo un loop de trabajo cerrado (08, 09, 10, 12) llega a `DONE`. |

## Umbrales de muestra (definidos en el código, no aquí)

`DEGRADED` por muestra insuficiente se decide con los umbrales que ya viven en la
configuración y el código. No inventar umbrales nuevos en un loop:

| Ámbito | Umbral | Origen |
|---|---|---|
| Diagnóstico por segmento | `n >= 15` | `src/sqp/audit/segments.py` |
| Monitor de degradación | `degradation_min_n` (30) | `configs/default.yaml` |
| Gate de CLV | `clv_gate_min_n` (30) | `configs/default.yaml` |
| Auto-promoción de calibrador | `AUTO_PROMOTE_MIN_N_VAL` (30) eventos independientes | `src/sqp/calibration/calibrator.py` |
| Sintonización de ratings | 200 / 80 | `src/sqp/backtesting/tuning.py` |

Si un loop necesita un umbral que no existe en el código, el estado correcto es
`BLOCKED` con una propuesta de umbral, no un `PASS` con un número improvisado.

## Registro de evidencia

Para cada estado, `current-task.md` debe contener:

1. Comandos ejecutados y su código de salida.
2. Rutas de los artefactos producidos o leídos.
3. Métricas observadas con su `n` (nunca una métrica sin tamaño de muestra).
4. La limitación concreta, si el estado es `DEGRADED`.
5. La acción bloqueante y quién debe aprobarla, si el estado es `BLOCKED`.

## Lenguaje obligatorio

Se aplican `.claude/rules/betting-output-rules.md` y `.claude/CLAUDE.md`: siempre
"probabilidad estimada"; separar probabilidad estimada, probabilidad implícita,
edge, hit rate observado vs. prometido, ROI esperado estimado y ROI realizado.
Un `PASS` **nunca** significa que el sistema sea rentable: significa que el loop
se ejecutó y dejó evidencia.
