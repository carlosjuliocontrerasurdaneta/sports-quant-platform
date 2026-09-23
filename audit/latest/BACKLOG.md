# Backlog de remediación · ronda `audit-2026-09-23`

- **Fuente:** `FINDINGS.md` de esta misma ronda. Base: `7bd565e`.
- **Estado:** ningún elemento está autorizado. Consolidar no autoriza correcciones: cada fila necesita la autorización del operador, por ID o por grupo, a través de la skill `audit-remediation`.
- **Regla transversal:** ningún cambio toca umbrales, pre-registros, el registro productivo del gate ni datos productivos (`settled_*`, stores). La reconciliación de datos ya persistidos es una tarea separada y con autorización propia.

## Orden recomendado

| Orden | ID | Prio. | Sev. | Cambio mínimo | Archivos | Pruebas | Criterio de aceptación | Depende de | Riesgo del cambio | Autorización pendiente |
|---:|---|---|---|---|---|---|---|---|---|---|
| 1 | AUD-002 | P1 | HIGH | Lock compartido (`storage/lock.locked`) sobre la transacción de actualización y de liberación del gate. El pestillo se aplica al estado releído dentro del lock. | `src/sqp/risk/prediction_gate.py` (+ `tests/`) | Dos escritores con barrera y decisiones opuestas; actualización concurrente con liberación | Sin liberación humana, `latched=true` no pasa a `false` | — | Medio: gate rector; debe fallar cerrado ante timeout del lock | Sí: control de riesgo (escala por clase según `MODEL_ROUTING.md`) |
| 2 | AUD-001 | P1 | HIGH | Mover la actualización del gate antes del bucle de ligas, fuera de `if not args.no_report`. Un fallo → default-deny en ese run. | `scripts/run_all.py` (+ test de integración) | Autorizado ayer / falla hoy; `--no-report`; fallo de actualización | Ningún candidato nuevo con stake > 0 en un mercado denegado por la evaluación vigente | AUD-002 (misma transacción) | Medio: cambia el orden del run diario; se valida con demo y tests | Sí: control de riesgo |
| 3 | AUD-003 | P1 | HIGH | `history_scores_map` para candidatos de equipo pendientes antes de `_with_stale_voids`. El feed tiene prioridad; los ambiguos se rechazan. | `src/sqp/settlement/runner.py` (+ tests) | Candidato y servido del mismo evento: win/loss, three-way, doubleheader ambiguo, feed sano ajeno, idempotencia | Sin `stale_void` si hay un resultado histórico inequívoco | AUD-009 recomendable (fuente del fallback) | Medio: liquidación irreversible, hace falta idempotencia | Sí. Medir y reconciliar los voids ya persistidos es aparte |
| 4 | AUD-004 | P2 | MEDIUM | Obtener `start_time` para los desplazados: columna con default en `BetCandidate`, o cruce con `archive/predictions_*` | `src/sqp/domain/models.py`, `src/sqp/settlement/runner.py`, `src/sqp/pipeline/daily.py` (+ tests) | Desplazado sin marcador → `stale_void`; sin duplicados por `DEDUP_KEY` | Ningún pick archivado sale del escaneo sin veredicto | Junto con AUD-003 | Bajo o medio: esquema de `candidates_*.csv` compatible | Sí: cambia un contrato persistido |
| 5 | AUD-012 | P3 | LOW | Nombre de archivo por `generated_at` completo; ajustar `_ARCHIVE_DAY` | `src/sqp/pipeline/daily.py`, `src/sqp/settlement/runner.py` (+ test) | Dos runs el mismo día y uno al día siguiente → ambos archivados y vistos por `superseded_candidates` | No se pierde ninguna generación | Junto con AUD-004 | Bajo | Sí: cambia la convención de `archive/` |
| 6 | AUD-009 | P2 | MEDIUM | `locked(p)` alrededor de lectura, merge y escritura en los tres stores; fetch fuera del lock | `src/sqp/storage/results_store.py`, `starters.py`, `starter_fip.py` (+ tests) | Dos escritores con barrera por store; timeout | La unión de escrituras completadas se conserva | — | Bajo | Sí |
| 7 | AUD-010 | P2 | MEDIUM | `_get_with_retry` y validación del boxscore; ninguna fila vacía ante error | `src/sqp/providers/mlb_statsapi.py` (+ test) | 429/500 JSON, timeout, payload inválido, boxscore válido | Un fallo del proveedor preserva los datos previos | — | Bajo | Sí |
| 8 | AUD-005 | P2 | MEDIUM | Separar selección (`adjusted_edge >= min_edge`) de dimensionamiento; banca ≤ 0 → stake 0 con flag | `src/sqp/pipeline/daily.py` (+ test) | Demo con banca 0 frente a banca > 0; caso `LedgerIntegridadError` | El conjunto de candidatos no depende de la banca | — | Medio: ruta de selección de picks; conviene revisión humana | Sí |
| 9 | AUD-006 | P2 | MEDIUM | `decision_prob` en `rank_picks` y en `report._segment_audit`; corregir el comentario | `scripts/daily_picks.py`, `src/sqp/audit/report.py` (+ tests) | Calibrada ≠ estimada; fallback NaN por fila | `roi_esp == estimated_edge` en toda fila servida | — | Bajo | Sí: salida al operador |
| 10 | AUD-007 | P2 | MEDIUM | Medias con target direccional y peso 0,5 en fit y métricas, o exclusión explícita de cuartos en entrenamiento **y** aplicación | `src/sqp/calibration/calibrator.py` (+ tests) | 60/20/20, espejo `half_win`, spreads/totals, holdout ponderado, regresión en enteros y medios | Fit y métricas = contrato `win_units/(win+loss units)` | — | Medio: afecta a candidatos futuros de calibración; no a los live ya promovidos | Sí: parámetros de modelo (escala por clase) |
| 11 | AUD-008 | P2 | MEDIUM | ROI con la semántica de `realized_roi_parts`; acierto binario definido aparte | `src/sqp/evaluation/edge_information.py` (+ tests) | Ambas medias; mezcla win/loss/push/void; comparación con el ledger | ROI y denominadores idénticos al ledger | Recomendado junto con AUD-007 | Bajo en código; puede cambiar cifras publicadas | Sí: cifras publicables. Recalcular experimentos es aparte |
| 12 | AUD-011 | P2 | MEDIUM | Evaluar `rc != 0` antes de la salida vacía; definir `(0, '')`; conservar el marcador | `.claude/hooks/crossreview-on-stop.sh` (+ `tests/` de hooks) | `(7,'')`, error con texto, veredicto válido, `(0,'')` | Una revisión fallida no pierde el marcador en silencio | — | Bajo | Sí |
| 13 | AUD-013 | P3 | LOW | Comprobar el centinela en health; mensaje específico en `gate_status` | `scripts/health_check.py` o `src/sqp/monitoring/`, `scripts/gate_status.py` (+ tests) | Con centinela presente | El centinela se ve en la salud del día | — | Bajo | Sí |
| 14 | AUD-014 | P3 | LOW | Unidades parciales en MC, o rechazo explícito de cuartos | `src/sqp/simulation/monte_carlo.py` (+ tests) | Ambos lados .25/.75 frente al analítico; casos enteros y medios | Coinciden dentro del error MC | — | Bajo | Sí |

## Grupos inequívocos para autorizar

- **G-GATE:** AUD-002 y AUD-001, en ese orden. Son los P1 del control rector de stake real.
- **G-LIQ:** AUD-003, AUD-004 y AUD-012. Garantía de veredicto por pick; mismos ficheros de liquidación.
- **G-DATOS:** AUD-009 y AUD-010. Integridad de los stores históricos.
- **G-CUARTOS:** AUD-007, AUD-008 y AUD-014. Semántica asiática de cuarto.
- **G-SALIDA:** AUD-005, AUD-006 y AUD-013. Salida al operador y observabilidad.
- **G-HOOK:** AUD-011.

## Tareas no de código (autorización aparte)

- Medir cuántos `stale_void` de candidatos en `settled_*` tienen resultado en `data/historical/` (AUD-003) y cuántos picks archivados no tienen fila liquidada (AUD-004). Solo agregados, sin modificar datos.
- Recalcular con el ROI canónico los informes o experimentos que usan `edge_information` (AUD-008), si la medición anterior muestra medias en su muestra.
- Verificación independiente pendiente de la ronda r2 (`audit/audit-2026-09-22-r2/`).
- Cubrir las zonas sin revisar: `html_report.py`, CLV, `closing_capture`, adaptadores y features concretas.
