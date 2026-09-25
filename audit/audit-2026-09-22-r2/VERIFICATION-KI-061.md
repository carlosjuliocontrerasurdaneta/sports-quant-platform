# Verificación independiente de KI-061 / REG-001 (commit `bd38c16`)

- **Fecha:** 2026-09-25T06:56Z.
- **Verificador:** subagente en `claude-fable-5-1`, sin el contexto de quien implementó y en modo solo lectura (no modificó el repositorio).
- **Base:** HEAD `a9170e5`. Los ficheros afectados no cambian entre `bd38c16` y HEAD.

**Veredicto: CORREGIDO CON PENDIENTES.** El defecto reportado está resuelto y reproducido. No hay regresiones. Quedan tres observaciones (OBS-001..003); ninguna es regresión, porque el código anterior tenía el mismo comportamiento o uno peor.

## Qué hace el cambio (leído en el código)

- `src/sqp/risk/degradation.py:212-241`. Con `RegistroEstadoIlegibleError`, el fallback sigue estos pasos:
  1. Reconstruye `previous` desde `degradation_log.csv` (`_previous_from_log`, líneas 273-283).
  2. Calcula `degradation_metrics(load_all_settled(...))`.
  3. Aplica `evaluate_pauses(metrics, previous, ...)` y devuelve `paused_from_registry(markets)`.
  4. No escribe nada.
  - Si fallan las métricas, devuelve las pausas del log (`exc3`, línea 238). Si falla el log, devuelve `{}` (líneas 221-224).
- `scripts/run_all.py:249-255`. El fallback recibe los mismos cinco umbrales que la ruta normal (líneas 226-232), todos de `Settings`, que se carga del bloque yaml `degradation_monitor` (`src/sqp/config.py:535-545`) y se valida en las líneas 410-416. `today=None` en las dos rutas.
- Quién llama: solo `run_all.py:249` en producción, y los tests. La firma añade únicamente kwargs keyword-only con default, así que es compatible. `_pauses_from_log` queda como código muerto, sin consecuencias.

## Evidencia reproducible

Se usaron datos sintéticos en directorios temporales: 40 perdidas con estimada 0,7 frente a implícita 0,5, y `min_n=30`. El código actual se comparó con el padre (`git show bd38c16^:src/sqp/risk/degradation.py`). La columna «¿Escribe?» compara el mtime y los bytes antes y después.

| Caso | Padre | Actual | ¿Escribe? |
|---|---|---|---|
| 1. JSON corrupto, `nba\|h2h` pausado en el log, `mlb\|totals` degradado hoy (el caso del hallazgo) | `{'nba':['h2h']}` | `{'mlb':['totals'],'nba':['h2h']}` | no |
| 2. JSON corrupto, sin log, mercado degradado | `{}` | `{'mlb':['totals']}` | no |
| 3. JSON corrupto, log sin las columnas esperadas | `{}` | `{}` | no |
| 4. JSON corrupto, log de 0 bytes | `{}` | `{}` | no |
| 5. Pausado en el log y recuperado hoy | pausado | reanudado (igual que el monitor normal) | no |
| 6. Pausado en el log con n < min_n | pausado | pausado | no |
| 7. `settled_*.csv` ilegible | pausas del log | pausas del log (`exc3`) | no |
| 8. Sin rastro en el log, ROI −0,10 (zona de histéresis) | `{}` | `{}`; el monitor normal con `paused=True` previo daría `{'mlb':['totals']}` | no |

- `pytest -q tests/test_degradation.py tests/test_registry_root_not_object.py`: 44 passed.
- Tests que mencionan `run_all` o `degradation`: 302 passed.
- `ruff check` sobre los tres ficheros: sin errores. `mypy src/sqp/risk/degradation.py`: sin incidencias.
- **Mutación.** Con el bloque de evaluación sustituido por `return paused_from_registry(previous)`, falla `test_fallback_con_registro_ilegible_pausa_un_mercado_que_se_degrada_ahora` (1 failed, 7 passed), así que el test nuevo detecta el defecto. `test_fallback_conserva_la_histeresis_del_log` pasa con el mutante: protege frente a `previous={}`, no frente a esta mutación.

## Observaciones

- **OBS-001 (P2, confianza alta), `degradation.py:231-237`: la histéresis se pierde mientras dura la corrupción.**
  - Una pausa que decide el fallback vive solo en memoria.
  - Si al día siguiente el registro sigue ilegible y el mercado está en la zona intermedia (`roi_pause ≤ roi_flat < roi_resume` y Brier dentro del margen), el fallback lo despausa. El monitor normal lo mantendría por `hysteresis_hold`. Reproducido en el caso 8.
  - Arreglarlo exige persistir estado, lo que choca con el contrato de «no escribir nada». Es una decisión de diseño.
  - → **KI-063.**
- **OBS-002 (P3, confianza alta), `degradation.py:219-224`: con el log también ilegible, no se evalúa el día.**
  - Con un log de 0 bytes (`EmptyDataError`) o sin columnas (`ValueError`), el fallback devuelve `{}` sin evaluar las métricas de hoy (casos 3 y 4).
  - Arreglo mínimo: tratar el log ilegible como `previous={}` y evaluar igualmente.
  - → **KI-064.**
- **OBS-003 (P3, confianza media), `degradation.py:273-283` y `349-350`: el fallback confía solo en el log.**
  - El registro se escribe antes que el log. Si `append_degradation_log` falla después de escribir el registro, esa pausa no llega al log, y un registro corrupto más tarde la trataría como un mercado nuevo.
  - Se deduce del orden de escritura; no se reprodujo de principio a fin.
  - → **KI-064** (misma familia).

## No verificado

- `scripts/run_all.py` completo con un registro corrupto (prohibido en solo lectura). El cableado se verificó leyendo el código y con llamadas directas.
- Los valores reales del bloque `degradation_monitor` del yaml de producción. Solo se comprobó que las dos rutas usan los mismos campos de `Settings`.
- `pytest -q` global y `mypy src` completo.
