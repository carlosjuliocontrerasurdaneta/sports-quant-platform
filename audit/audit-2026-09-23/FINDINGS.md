# Consolidación independiente · ronda `audit-2026-09-23`

- **Fase:** consolidación. Contrato: `audits/prompts/auditoria-consolidacion.md` (fuente `.claude/automation/audit-workflow.md`), con la taxonomía de `AGENTS.md`.
- **Consolidador:** Claude Code (`claude-opus-5-5`), 2026-09-23T18:48Z. Esta fase **no autoriza ninguna corrección**.
- **Base Git:** `main` @ `7bd565e19606a70b37f704ca44cdc41e168ba274`. Es la misma base de los dos informes fuente. `git diff HEAD -- src scripts configs tests .claude *.bat` sale vacío: el código no cambió entre los diagnósticos y esta consolidación.
- **Árbol de trabajo al consolidar:** solo había cambios en entregables de auditoría: `audit/latest/{MANIFEST.json, claude/*, openai/*}` modificados y `audit/audit-2026-09-22-r2/` sin seguimiento. No había cambios de código.

## 1. Fuentes

| Auditor | Ruta | SHA-256 | Ronda y base declaradas | IDs |
|---|---|---|---|---|
| Claude | `audit/latest/claude/REPORT.md` | `345cd9ddd6b80fe0f846545857dfc93a1fee9911bdbe900ee0d6ab41a149cd79` | audit-2026-09-23 · 7bd565e | CLAUDE-001…005 |
| Claude | `audit/latest/claude/EVIDENCE.json` | `c57726644d637a8c93343273d791a74cc5ddf04e7e4899f40688300d578551c9` | ídem | — |
| OpenAI | `audit/latest/openai/REPORT.md` | `83956da78b83ed1bca53c136ba30871cec65d07ab3d59ac430d68ee0b6256542` | audit-2026-09-23 · 7bd565e | OPENAI-001…009 |
| OpenAI | `audit/latest/openai/EVIDENCE.json` | `85f08bbd2e4940df614b5ad788ff13e5cb7a8bae6e997693354221288b8907d3` | ídem | — |

- **Independencia declarada:** OpenAI no leyó el informe Claude y congeló sus conclusiones a las 2026-09-23T11:08:01Z. Claude no tenía informe OpenAI de esta ronda cuando hizo su diagnóstico: su NV-2 («sin segunda opinión») quedó **superado** por el diagnóstico posterior de OpenAI.
- **Contaminación declarada por las fuentes:**
  - Claude: la memoria automática del harness le inyectó titulares de rondas anteriores.
  - OpenAI: su diagnóstico añadió unos 5 mensajes a `logs/sqp.log` al importar el logger real. Es una escritura incidental fuera de su subdirectorio, declarada por el auditor. No se revierte aquí.

## 2. Método

- Se leyeron ambos informes completos.
- Cada uno de los 14 hallazgos fuente se contrastó con el código de `7bd565e`, leyendo las líneas citadas. Todos se sostienen estáticamente.
- En esta fase **no se volvieron a ejecutar** los arneses de reproducción. La etiqueta REPRODUCED es la del auditor de origen, y el consolidador añade la verificación estática. No se ejecutaron tests: el código no cambió desde las validaciones de las fuentes (§6).
- La severidad y la confianza no se promedian. Si hay discrepancia, se razona con el impacto alcanzable y los controles compensatorios (§4).
- Se agrupa por causa raíz. Solo se separan hallazgos con impacto o corrección materialmente distintos.

## 3. Resumen

| Severidad | Confirmados | P1 | P2 | P3 |
|---|---:|---:|---:|---:|
| CRITICAL | 0 | – | – | – |
| HIGH | 3 | 3 | – | – |
| MEDIUM | 8 | – | 8 | – |
| LOW | 3 | – | – | 3 |
| **Total** | **14** | 3 | 8 | 3 |

- **P0:** ninguno.
- **Estado del dinero hoy:** el registro del gate de predicción (2026-09-22T15:15Z) tiene 49 cortes y **0 autorizados**, así que todo stake es 0. Nada de lo siguiente ha causado pérdida económica demostrada. Los tres HIGH describen fallos del control que decide el primer stake real, o del ledger que lo contabiliza. Tienen que estar cerrados **antes** de que cualquier corte pueda abrirse (el pre-registro «el modelo manda» se mide hacia el 2026-11-17).

| ID | Sev. | Prio. | Título | Origen | Alias fuente |
|---|---|---|---|---|---|
| AUD-001 | HIGH | P1 | El gate de predicción se actualiza después de generar los picks que debía autorizar | exclusivo OpenAI | OPENAI-001 |
| AUD-002 | HIGH | P1 | Dos actualizaciones solapadas del gate pueden desarmar el pestillo sin liberación humana | exclusivo OpenAI | OPENAI-002 |
| AUD-003 | HIGH | P1 | Los candidatos de deportes de equipo no usan el fallback histórico: se anulan o quedan sin veredicto aunque el resultado exista | coincidencia parcial | OPENAI-003, CLAUDE-002 (parte b) |
| AUD-004 | MEDIUM | P2 | Un pick desplazado (`superseded`) no tiene `start_time`: nunca se anula por expiración y sale del escaneo sin veredicto | exclusivo Claude | CLAUDE-002 (parte a) |
| AUD-005 | MEDIUM | P2 | Con banca 0 la lista de candidatos desaparece entera | exclusivo Claude | CLAUDE-001 |
| AUD-006 | MEDIUM | P2 | `daily_picks.py` ordena, filtra y calcula el «ROI esperado» con la probabilidad cruda descartada | exclusivo Claude | CLAUDE-003 |
| AUD-007 | MEDIUM | P2 | El calibrador excluye las medias liquidaciones y aprende un objetivo distinto del precio en líneas de cuarto | exclusivo OpenAI | OPENAI-004 |
| AUD-008 | MEDIUM | P2 | `edge_information` elimina medias liquidaciones del ROI realizado y puede invertir su signo | exclusivo OpenAI | OPENAI-005 |
| AUD-009 | MEDIUM | P2 | `ResultsStore`, `StartersStore` y `StarterFIPStore` pierden escrituras concurrentes | exclusivo OpenAI | OPENAI-006 |
| AUD-010 | MEDIUM | P2 | Un HTTP de error en el boxscore MLB borra FIP históricos válidos | exclusivo OpenAI | OPENAI-007 |
| AUD-011 | MEDIUM | P2 | El hook de revisión cruzada descarta en silencio una revisión fallida sin salida | exclusivo OpenAI | OPENAI-008 |
| AUD-012 | LOW | P3 | Un segundo run el mismo día pisa la copia de archivo del primero | exclusivo Claude | CLAUDE-004 |
| AUD-013 | LOW | P3 | El centinela `prediction_gate.blocked` no aparece en salud y `gate_status` lo describe mal | exclusivo Claude | CLAUDE-005 |
| AUD-014 | LOW | P3 | `simulate_poisson_game` trata las líneas de cuarto como apuestas binarias | exclusivo OpenAI | OPENAI-009 |

**Relaciones de causa** (se mantienen separadas porque su corrección es distinta):

- AUD-002 y AUD-009 comparten la clase «lectura-modificación-escritura sin exclusión: `atomic_write_*` protege el fichero, no la transacción».
- AUD-007, AUD-008 y AUD-014 comparten la clase «semántica asiática de cuarto proyectada a binario».
- AUD-003, AUD-004 y AUD-012 afectan a la misma garantía: todo pick archivado termina con un veredicto.

## 4. Discrepancias entre auditores y resolución

| Tema | Claude | OpenAI | Resolución |
|---|---|---|---|
| Severidad del hueco de liquidación de candidatos (AUD-003) | MEDIUM/P2 (CLAUDE-002): con stake 0 solo se pierden unidades de pick | HIGH/P1 (OPENAI-003): void con pnl 0 en lugar de loss | **HIGH/P1**. La anulación es **irreversible**: `DEDUP_KEY` no incluye `result` (comentario en `runner.py`, «Voiding is FINAL»), así que una graduación correcta posterior se descarta. Con stake real, el ledger y la banca dinámica quedan mal para siempre. El default-deny reduce la frecuencia actual, no el impacto alcanzable. La severidad no se rebaja por frecuencia. |
| Mecanismo de CLAUDE-002 | Dos causas: falta `start_time` en los desplazados y falta fallback histórico en equipos | Solo la segunda | Se **divide** CLAUDE-002: la parte (b) se une a OPENAI-003 en AUD-003 y la parte (a) queda como AUD-004. Tienen corrección e impacto distintos: anular mal un pick frente a no dar veredicto. |
| Estado del CI remoto | `gh run list`: **success** en 7bd565e | NOT_VERIFIABLE (`gh` ausente en su entorno) | Vale la evidencia de Claude: el CI en HEAD estaba verde cuando se consultó. La ausencia de `gh` en el entorno OpenAI es ENVIRONMENTAL_FAILURE, no una discrepancia de producto. |
| Suite completa | 2299 passed, 1 skipped | 844 focalizados; suite completa no ejecutada | Sin contradicción. Ninguno de los 14 escenarios está cubierto por la suite: ambos auditores reproducen fallos con la suite en verde. |
| Remediación de r2 | No revalidada: queda pendiente de verificación independiente | Revalida AUD-001…004 de r2 como corregidos, con límites declarados | Es la afirmación de **un** auditor, no una fase de verificación. La ronda r2 sigue **sin `VERIFICATION.md`** y su cierre formal queda pendiente. |
| El gate con EV autoestimado (O-1) | Observación: coincide con el pre-registro | Evita confundir EV esperado con ROI realizado | Coinciden: es una observación, no un defecto. |

Ningún hallazgo se descartó como falso positivo en la consolidación.

## 5. Hallazgos consolidados

> Evidencia en todos: **REPRODUCED** por el auditor de origen salvo que se diga otra cosa, más **STATICALLY_VERIFIED** por el consolidador en 7bd565e. Confianza: HIGH en los 14.

### AUD-001 — El gate de predicción se actualiza después de generar los picks que debía autorizar
- **Origen:** exclusivo OpenAI (OPENAI-001). **Categoría:** riesgo / orden de ejecución. **Severidad:** HIGH. **Prioridad:** P1.
- **Archivo / línea:**
  - `scripts/run_all.py:209-210`: bucle `run_league` de todas las ligas.
  - `:239`: `if not args.no_report:`.
  - Bloque `write_prediction_gate` dentro de ese `if` (≈`:305-315`).
  - `src/sqp/pipeline/daily.py:651`: `load_prediction_gate` lee el registro anterior.
- **Activación:**
  - Un corte autorizado deja de cumplir la regla de salida con los resultados que `SETTLE_ALL` acaba de liquidar. Hoy genera con la autorización de ayer.
  - Además, `--no-report` omite la actualización.
  - Un fallo de la actualización antes de leer el estado previo (p. ej. dentro de `evaluate_markets`) deja el registro anterior sin centinela. Ese registro se sigue consumiendo en los runs siguientes.
- **Problema:** la salida diaria que exige el pre-registro («vigilancia continua para salir») llega un run tarde. El control está subordinado a un flag de presentación.
- **Evidencia concreta:** arnés de OpenAI con `run_all.main` y `run_league` reales, proveedores sintéticos y ROOT aislado. Resultado: 4 candidatos con stake > 0 (total 13,56); al terminar, los tres mercados NBA quedan `allowed=false, latched=true`; exit 0. El consolidador confirmó el orden en el código.
- **Esperado:** el veredicto actualizado con lo liquidado se aplica **antes** de dimensionar. Un fallo conserva la denegación.
- **Observado:** el registro final queda cerrado, pero los picks del día ya se publicaron con stake contra la autorización vencida.
- **Causa raíz:** el control de riesgo se actualiza después de su consumidor y depende de `--no-report`.
- **Consecuencia:** exposición real durante al menos un run en un mercado que ya perdió la autorización. El cierre posterior no revoca esos candidatos.
- **Controles existentes:** pestillo (arma el cierre), límites de exposición y pausas. `RUN_DIARIO_ALL.bat` no pasa `--no-report`. Hoy hay 0 cortes autorizados.
- **Corrección mínima:** actualizar el gate tras cargar lo liquidado y antes del bucle de ligas, sin depender de `--no-report`. Si falla, default-deny para ese run: no reutilizar la autorización anterior.
- **Pruebas necesarias:**
  - integración «autorizado ayer / falla hoy» → stake 0 hoy;
  - camino `--no-report`;
  - fallo de la actualización → default-deny;
  - el informe coincide con el registro.
- **Criterio de aceptación:** ningún candidato nuevo tiene stake > 0 en un mercado denegado por la evaluación vigente.
- **Limitaciones:** frecuencia productiva no medible hoy (0 autorizados). Umbrales y pre-registro intactos.

### AUD-002 — Dos actualizaciones solapadas del gate pueden desarmar el pestillo sin liberación humana
- **Origen:** exclusivo OpenAI (OPENAI-002). **Categoría:** concurrencia / autorización. **Severidad:** HIGH. **Prioridad:** P1.
- **Archivo / línea:**
  - `src/sqp/risk/prediction_gate.py:448-520`: `write_prediction_gate` lee el estado previo, aplica `_apply_latch` y reescribe, sin lock.
  - `:570+`: `release_prediction_gate_latch`, lectura y escritura sin lock.
  - `scripts/update_prediction_gate.py:103`.
  - `scripts/run_all.py` (bloque del gate).
- **Activación:** dos escritores leen el mismo estado abierto. El que arma el pestillo escribe primero y el otro, con la evaluación anterior, escribe después. Caso típico: `update_prediction_gate.py` o `--release` manual mientras corre el run programado.
- **Evidencia concreta:** intercalado de OpenAI con dos hilos y funciones reales:
  - B escribe `allowed=false, latched=true, p=0,522`.
  - A reescribe después `allowed=true, latched=false, p=8,4e-12`.
  - No hubo ninguna llamada de liberación.
- **Esperado:** un pestillo armado solo se desarma con liberación humana.
- **Observado:** el pestillo se borra y el mercado se reabre automáticamente.
- **Causa raíz:** lectura-modificación-escritura sin exclusión mutua. `atomic_write_json` es atómico por fichero, no por transacción. Es la misma clase que AUD-009.
- **Consecuencia:** se rompe la regla de no reentrada del pre-registro y puede volver a haber stake tras una salida obligatoria. El log conserva un cierre que ya no existe.
- **Controles existentes:** temporales únicos y fsync, centinela de lectura ilegible, `_apply_latch`. Ninguno cubre dos lecturas válidas concurrentes.
- **Corrección mínima:** un lock compartido (`storage/lock.py`) alrededor de la transacción completa de actualización y de liberación, incluido el historial. Evaluar fuera del lock y aplicar el pestillo sobre el estado **releído** dentro del lock.
- **Pruebas necesarias:** dos escritores con barrera y decisiones opuestas; actualización concurrente con liberación. El pestillo y el rastro se conservan.
- **Criterio de aceptación:** ningún escritor que leyó un estado anterior puede sustituir `latched=true` por `false` sin liberación humana.
- **Limitaciones:** carrera demostrada en un solo proceso; su frecuencia real no es medible.

### AUD-003 — Los candidatos de deportes de equipo no usan el fallback histórico
- **Origen:** coincidencia parcial: OPENAI-003 y la parte (b) de CLAUDE-002. **Categoría:** integridad financiera / liquidación. **Severidad:** HIGH (Claude: MEDIUM; ver §4). **Prioridad:** P1.
- **Archivo / línea:**
  - `src/sqp/settlement/runner.py:673-676`: `settle_candidates` y `_with_stale_voids` solo con `scores` del feed.
  - `:663-668`: `_grade_served_from_history` gradúa solo el stream servido.
  - `:211`: `history_scores_map` existe.
  - `settle.py:20`: `STALE_VOID_DAYS = 3`.
- **Activación:** candidato de equipo fuera de la ventana `--days-from 3` del feed, con el resultado ya en `ResultsStore` y un feed sano con otros partidos (`scores_trusted`).
- **Evidencia concreta:** `fetch_and_settle` real en ROOT temporal (OpenAI), WNBA, stake 100, resultado histórico 70-80. El candidato queda `void / pnl 0 / stale_void` y el mismo evento servido queda `loss`.
- **Esperado:** el candidato se gradúa con el resultado histórico inequívoco, igual que el stream servido y los candidatos de tenis (AUD-MED-004).
- **Observado:** si su `start_time` es conocido, se anula; si no lo es, ver AUD-004.
- **Causa raíz:** el fallback histórico se aplicó al stream servido y al tenis, pero no a los candidatos de equipo.
- **Consecuencia:** la anulación es **final** (`DEDUP_KEY` sin `result`). Con stake real, el ledger y la banca omiten la pérdida o la ganancia. Hoy (stake 0) desaparece un win/loss del rastro de candidatos. Si ese rastro alimenta el hit rate rector, este queda sesgado; ese uso **no se verificó** en esta fase.
- **Controles existentes:** guard de payload vacío (`scores_trusted`), fallback en servidos y tenis, guard M2 de `run_all`. Ninguno cubre este caso.
- **Corrección mínima:** antes de `_with_stale_voids`, intentar `history_scores_map` para los candidatos pendientes. Priorizar el feed y rechazar emparejamientos ambiguos, como ya hace el servido.
- **Pruebas necesarias:** candidato y servido del mismo evento antiguo: win/loss, three-way, doubleheader ambiguo, feed sano ajeno, segunda pasada idempotente.
- **Criterio de aceptación:** no hay `stale_void` cuando existe un resultado histórico inequívoco.
- **Limitaciones:** **NOT_VERIFIABLE** cuántos `stale_void` productivos ya existen con resultado histórico disponible. Medirlo exige cruzar `settled_*` con `data/historical/` y conviene hacerlo antes de decidir cualquier reconciliación, que necesita autorización aparte.

### AUD-004 — Un pick desplazado no tiene `start_time`: nunca se anula por expiración y sale sin veredicto
- **Origen:** exclusivo Claude (parte a de CLAUDE-002). **Categoría:** liquidación / integridad del ledger. **Severidad:** MEDIUM. **Prioridad:** P2.
- **Archivo / línea:**
  - `src/sqp/settlement/runner.py:406-418`: `_prediction_start_times` solo lee el `predictions_<liga>.csv` vigente.
  - `:44-110`: `superseded_candidates`.
  - `:34`: `SUPERSEDED_LOOKBACK_DAYS = 14`.
  - `src/sqp/domain/models.py:56`: `BetCandidate` sin `start_time`.
- **Activación:** un pick deja la lista antes del partido y el partido se cancela sin marcador, o la liquidación no corre dentro de la ventana del feed.
- **Evidencia concreta:** `scratchpad/repro_superseded.py` de Claude. Control con el pick en el fichero vigente: `void/stale_void`. Pick desplazado: `[]`, sin fila liquidada.
- **Esperado:** `stale_void` pasados `STALE_VOID_DAYS`, igual que un pick vigente.
- **Observado:** el pick queda abierto y a los 14 días sale del escaneo sin fila en `settled_*`.
- **Causa raíz:** el `start_time` no viaja con el candidato y se reconstruye desde un fichero que solo describe el run vigente.
- **Consecuencia:** unidades de pick sin veredicto, la clase de hueco que AUD-MED-003 quiso cerrar. Con stake real, un partido jugado fuera de ventana tampoco se gradúa, salvo que AUD-003 quede corregido.
- **Controles existentes:** el guard M2 cubre solo el fichero vigente; el stream servido tiene su propio fallback.
- **Corrección mínima:** `start_time` en el candidato (columna nueva con default) o cruce con `archive/predictions_<liga>_<día>.csv`, como `_tennis_prediction_metadata`.
- **Pruebas necesarias:** desplazado sin marcador → `stale_void`; sin duplicados por `DEDUP_KEY`.
- **Criterio de aceptación:** ningún pick archivado dentro de la ventana sale del escaneo sin veredicto.
- **Dependencias:** conviene hacerlo junto con AUD-003 (mismo fichero y mismas pruebas) y con AUD-012.
- **Limitaciones:** frecuencia real no medida.

### AUD-005 — Con banca 0 la lista de candidatos desaparece entera
- **Origen:** exclusivo Claude (CLAUDE-001). **Categoría:** lógica / integridad de salida. **Severidad:** MEDIUM. **Prioridad:** P2.
- **Archivo / línea:**
  - `src/sqp/pipeline/daily.py:897-901`: `kelly_fraction_stake(..., settings.bankroll, ...)`.
  - `:952-953`: `elif stake <= 0 and not suspect: continue`.
  - `src/sqp/risk/kelly.py:30-31`: `bankroll <= 0 → (0, 0)`.
  - `src/sqp/risk/bankroll.py:384-395`: banca a 0 ante `LedgerIntegridadError`, con el comentario «la lista se sigue generando entera».
- **Activación:** ledger ilegible o balance ≤ 0 → `settings.bankroll = 0`.
- **Evidencia concreta:** `scratchpad/repro_bankroll0b.py` de Claude, en demo NBA: banca 1000 → 2 candidatos; banca 0 → 0 candidatos. El consolidador confirmó en código que la selección depende del stake.
- **Esperado:** mismo conjunto de candidatos, con stake 0 y un flag propio.
- **Observado:** `candidates_*.csv` sin filas; `_finalize` borra el fichero vigente tras archivarlo.
- **Causa raíz:** selección y dimensionamiento acoplados en `kelly_fraction_stake`.
- **Consecuencia:** un día sin candidatos en todas las ligas. Se pierden la liquidación de picks, el KPI y la revalidación.
- **Controles existentes:** el stream servido se graba antes del filtrado, así que `daily_picks.py` conserva la lista del operador; log «BANCA NO VERIFICABLE»; default-deny.
- **Corrección mínima:** seleccionar por `adjusted_edge >= min_edge` con independencia de la banca; dimensionar después; banca ≤ 0 → stake 0 con flag.
- **Pruebas necesarias:** demo con banca 0 → mismo número de candidatos que con banca > 0, todos con stake 0 y flag; caso `LedgerIntegridadError`.
- **Criterio de aceptación:** el conjunto de candidatos no depende de la banca.
- **Limitaciones:** no está activo hoy (ledger legible, balance > 0).

### AUD-006 — `daily_picks.py` usa la probabilidad cruda que el sistema descartó
- **Origen:** exclusivo Claude (CLAUDE-003). **Categoría:** cuantitativo / salida al operador. **Severidad:** MEDIUM. **Prioridad:** P2. **Evidencia:** STATICALLY_VERIFIED con medición agregada (Claude) y confirmación estática del consolidador.
- **Archivo / línea:**
  - `scripts/daily_picks.py:116`: `p = estimated_probability`.
  - `:122` y `:177`: `roi_esp = p·cuota − 1`.
  - `:175-176`: comentario falso («Es el `estimated_edge`»).
  - Instancia secundaria en `src/sqp/audit/report.py:265`: `mean_est_prob`.
- **Activación:** existe un calibrador live para (liga, mercado). Hoy son 3: `mlb_spreads`, `mlb_totals`, `wnba_spreads`.
- **Evidencia concreta:** 846 picks vigentes; 4 con |calibrada − estimada| > 0,005 (máximo 0,0259); 0 discrepancias de signo hoy.
- **Esperado:** `decision_prob`, como el dashboard y el tipster desde A-01 (2026-08-31).
- **Observado:** orden, filtro `--min-prob 0.60` y «ROI esperado» calculados sobre la probabilidad cruda.
- **Causa raíz:** el arreglo A-01 se aplicó a 2 de 3 consumidores.
- **Consecuencia:** la cifra rotulada «ROI esperado» no es el edge del motor en mercados calibrados, y la diferencia crece con cada promoción de calibrador. Confunde probabilidad estimada y decisión, que las reglas de salida exigen separar.
- **Controles existentes:** ninguno sobre este script.
- **Corrección mínima:** `decision_prob` en `rank_picks` y en `report._segment_audit`; corregir el comentario.
- **Pruebas necesarias:** frame con calibrada ≠ estimada; fallback por fila si la calibrada es NaN.
- **Criterio de aceptación:** `roi_esp == estimated_edge` (redondeo aparte) en toda fila servida.

### AUD-007 — El calibrador excluye las medias liquidaciones en líneas de cuarto
- **Origen:** exclusivo OpenAI (OPENAI-004). **Categoría:** cuantitativo / calibración. **Severidad:** MEDIUM. **Prioridad:** P2.
- **Archivo / línea:**
  - `src/sqp/calibration/calibrator.py:656`: `hist[hist["result"].isin(["win","loss"])]`.
  - Contrato: `markets/settlement_math.py:29`, `models/distributions.py:285`.
- **Activación:** entrenar un (liga, mercado) con líneas x.25/x.75 y resultados `half_win`/`half_loss`.
- **Evidencia concreta:** 100 eventos Over 2,25 (60 win, 20 loss, 20 half_loss) llegan al fit como 80 filas con media 0,75. El objetivo contractual es 0,6667.
- **Esperado:** medias con target direccional y peso 0,5 en el fit y en las métricas, o exclusión explícita de los cuartos también al aplicar el calibrador.
- **Observado:** selección de la muestra según el resultado, con un objetivo sesgado.
- **Causa raíz:** filtro binario heredado, sin ponderación. Misma clase que AUD-008 y AUD-014.
- **Consecuencia:** calibradores entrenados y evaluados contra un objetivo distinto del precio. El servicio calibra por (liga, mercado) sin distinguir la línea.
- **Controles existentes:** split por evento, mínimos, ECE/Brier, staging y promoción supervisada; ninguno corrige el target.
- **Pruebas necesarias:** 60/20/20, espejo `half_win`, spreads y totals, holdout ponderado; regresión en líneas enteras y medias.
- **Criterio de aceptación:** el fit y las métricas reproducen el contrato `win_units/(win_units+loss_units)`.
- **Limitaciones:** en los datos actuales hay 14 medias liquidaciones entre 30.921 filas graduadas (agregado de OpenAI). No se acredita ningún calibrador promovido afectado.

### AUD-008 — `edge_information` elimina medias liquidaciones del ROI realizado
- **Origen:** exclusivo OpenAI (OPENAI-005). **Categoría:** cuantitativo / evaluación. **Severidad:** MEDIUM. **Prioridad:** P2.
- **Archivo / línea:**
  - `src/sqp/evaluation/edge_information.py:101` (filtro win/loss) y `:117` (`_roi` binario).
  - Consumidores: `scripts/model_vs_market_report.py:138` y `scripts/research/measure_price_floor_preregistration.py:125`.
  - Contrato: `settlement/settle.py:133` (`realized_roi_parts`).
- **Evidencia concreta:** 1 win y 10 `half_loss` a cuota 2 → `roi_flat = +1,0` sobre n = 1. El ROI canónico es −0,364 sobre 11.
- **Esperado:** el ROI realizado de cada subconjunto coincide con `realized_roi_parts`. El acierto binario se define aparte.
- **Causa raíz:** una misma proyección binaria sirve al hit rate y al ROI, y excluye filas según el resultado.
- **Consecuencia:** escaleras de edge e informes model-vs-market pueden presentar como favorable una política perdedora.
- **Controles existentes:** dedup por pick, finitud y bootstrap por evento; todos operan después del filtro.
- **Pruebas necesarias:** fixtures con ambas medias y con mezcla win/loss/push/void; comparación contra `realized_roi_parts` a stake unitario.
- **Criterio de aceptación:** ROI y denominadores idénticos al ledger canónico.
- **Limitaciones:** **NOT_VERIFIABLE** si alguna conclusión registrada cambia. Por ejemplo, el suelo de precio no adoptado del 2026-09-19. Con 14 medias en todo el histórico el efecto agregado probablemente es pequeño, pero no se recalculó.

### AUD-009 — Tres stores históricos pierden escrituras concurrentes
- **Origen:** exclusivo OpenAI (OPENAI-006). **Categoría:** concurrencia / integridad de datos. **Severidad:** MEDIUM. **Prioridad:** P2.
- **Archivo / línea:** `src/sqp/storage/results_store.py:57-74`, `starters.py:101-138`, `starter_fip.py:24-42`. Leen, fusionan y hacen `atomic_write_csv` sin `locked()`.
- **Activación:** dos backfills del mismo store y liga solapados, por ejemplo manual y `SQP_Backfill`.
- **Evidencia concreta:** intercalado A-prepara / B-persiste / A-persiste: `['seed','A','B']` termina como `['seed','A']` en los tres stores.
- **Esperado:** la unión de todas las escrituras completadas.
- **Causa raíz:** la misma que AUD-002.
- **Consecuencia:** se pierden resultados, abridores o FIP de los que dependen modelos y liquidación, incluido el fallback de AUD-003. Hay que reingerir.
- **Controles existentes:** temporales únicos, fsync y dedup. No evitan actualizaciones perdidas.
- **Corrección mínima:** `locked(p)` alrededor de lectura, merge y escritura, con los fetch fuera del lock.
- **Pruebas necesarias:** dos escritores con barrera por store; timeout seguro.
- **Criterio de aceptación:** ninguna escritura completada de claves distintas desaparece.
- **Limitaciones:** frecuencia real no medida.

### AUD-010 — Un HTTP de error en el boxscore MLB borra FIP históricos válidos
- **Origen:** exclusivo OpenAI (OPENAI-007). **Categoría:** proveedor / integridad de datos. **Severidad:** MEDIUM. **Prioridad:** P2.
- **Archivo / línea:**
  - `src/sqp/providers/mlb_statsapi.py:123`: `self.session.get(...).json()` sin `raise_for_status` ni `_get_with_retry`, que sí usa `schedule` en la línea 112.
  - `src/sqp/storage/starter_fip.py:37`: `keep="last"`.
- **Evidencia concreta:** boxscore 500 `{"message": ...}` → fila con FIP `None` que sustituye 3,2/4,1 por NaN.
- **Esperado:** rechazar o reintentar la respuesta y preservar la fila previa.
- **Causa raíz:** no se valida el estado HTTP ni la forma del payload, y el upsert es incondicional.
- **Consecuencia:** un fallo transitorio destruye datos históricos.
- **Controles existentes:** `pitcher_bound = 0.0` en producción limita el impacto inmediato en picks, no la pérdida de datos.
- **Corrección mínima:** `_get_with_retry` y validar el boxscore antes de emitir fila.
- **Pruebas necesarias:** reingestión con datos previos ante 429/500 JSON, timeout, payload inválido y boxscore válido.
- **Criterio de aceptación:** un fallo del proveedor preserva los datos previos.

### AUD-011 — El hook de revisión cruzada descarta en silencio una revisión fallida sin salida
- **Origen:** exclusivo OpenAI (OPENAI-008). **Categoría:** operación / control de revisión. **Severidad:** MEDIUM. **Prioridad:** P2.
- **Archivo / línea:**
  - `.claude/hooks/crossreview-on-stop.sh:17`: el marcador se borra primero.
  - `:96-98`: `[ -z "$out" ] && exit 0` va antes de evaluar `rc`.
  - `:116`: el marcador solo se restaura en la rama de fallo con texto.
  - Cableado en `Stop` en `.claude/settings.json` (verificado).
- **Evidencia concreta:** codex devuelve rc = 7 sin salida → hook exit 0, sin salida, sin marcador.
- **Esperado:** avisar y conservar el marcador.
- **Causa raíz:** se comprueba la salida vacía antes que el código de salida.
- **Consecuencia:** un cambio de riesgo se queda sin revisión cruzada y sin reintento. Es relevante mientras el MCP/CLI de Codex falla de forma intermitente (KI-055/056).
- **Corrección mínima:** evaluar `rc != 0` primero y definir el contrato del caso `(0, '')`.
- **Pruebas necesarias:** `(7,'')`, error con texto, veredicto válido y `(0,'')`.
- **Criterio de aceptación:** una revisión fallida nunca pierde el marcador en silencio.

### AUD-012 — Un segundo run el mismo día pisa la copia de archivo del primero
- **Origen:** exclusivo Claude (CLAUDE-004). **Categoría:** preservación de datos. **Severidad:** LOW. **Prioridad:** P3. **Evidencia:** STATICALLY_VERIFIED (Claude y consolidador); no reproducido.
- **Archivo / línea:** `src/sqp/pipeline/daily.py:421-428`: nombre `{stem}_{día}` y `shutil.copy2` sobre ese nombre.
- **Activación:** dos runs el mismo día UTC. Ya ocurrió el 2026-08-27.
- **Consecuencia:** la primera generación desaparece de `archive/` y `superseded_candidates` no la ve (AUD-004).
- **Corrección mínima:** nombre de archivo con la marca completa de `generated_at`, adaptando `_ARCHIVE_DAY` en `runner.py`.
- **Pruebas necesarias:** dos `_finalize` el mismo día y un tercero al día siguiente → ambas generaciones en `archive/`.
- **Criterio de aceptación:** no se pierde ninguna generación archivada.

### AUD-013 — El centinela `prediction_gate.blocked` es invisible en salud y `gate_status` lo describe mal
- **Origen:** exclusivo Claude (CLAUDE-005). **Categoría:** observabilidad de un control. **Severidad:** LOW. **Prioridad:** P3. **Evidencia:** STATICALLY_VERIFIED. `grep` sin coincidencias en `src/sqp/monitoring/`, `scripts/health_check.py` y `scripts/gate_status.py`.
- **Archivo / línea:** `src/sqp/risk/prediction_gate.py:474-486`, `scripts/gate_status.py:137`.
- **Consecuencia:** el fallo es seguro (cierre indefinido), pero el diagnóstico apunta a «registro ausente» y health no avisa.
- **Corrección mínima:** comprobación en health y mensaje específico en `gate_status.render`.
- **Pruebas necesarias:** con el centinela presente, health da el motivo y `gate_status` muestra el mensaje.
- **Criterio de aceptación:** el centinela aparece en la salida de salud del día.
- **Limitaciones:** hoy no hay centinela.

### AUD-014 — `simulate_poisson_game` trata las líneas de cuarto como binarias
- **Origen:** exclusivo OpenAI (OPENAI-009). **Categoría:** matemáticas / API de simulación. **Severidad:** LOW. **Prioridad:** P3.
- **Archivo / línea:** `src/sqp/simulation/monte_carlo.py:53-58`.
- **Evidencia concreta:** λ = 1,5/1,0, total 2,25, 500.000 simulaciones con seed 42: MC 0,4565 frente a 0,5233 analítico.
- **Consecuencia:** API y oráculo de contraste incorrectos en cuartos. Solo tiene consumidores en tests y API (`grep`: ninguno en el pipeline productivo), de ahí LOW.
- **Corrección mínima:** semántica de unidades de `settlement_math`, o rechazar los cuartos explícitamente.
- **Pruebas necesarias:** ambos lados de .25/.75 dentro del error MC; casos enteros y medios.
- **Criterio de aceptación:** simulación y analítico coinciden dentro del error muestral.

## 6. Validaciones y cobertura

| Validación | Fuente | Resultado | Clasificación |
|---|---|---|---|
| `ruff check src scripts tests` | ambos | exit 0 | OK |
| `mypy src` | ambos | exit 0, 106 ficheros | OK |
| `pytest` suite completa | Claude | 2299 passed, 1 skipped (22 min 40 s) | OK |
| `pytest` focalizado | OpenAI | 844 passed, en seis grupos; 45 errores de setup iniciales por WinError 5 en `.codex-tmp/pytest`, repetidos con basetemp nuevo | OK tras ENVIRONMENTAL_FAILURE declarado |
| CI remoto en 7bd565e | Claude (`gh run list`) | success | OK. En el entorno OpenAI: NOT_VERIFIABLE |
| sync de instrucciones y routing | ambos | exit 0 | OK |
| `pip check` | OpenAI | exit 0 | OK |
| Tareas programadas | OpenAI | 4 principales rc 0; `Dashboard` rc 267014 | observación (O-6) |
| Reproducciones | Claude 2 / OpenAI 8 | fallos del producto observados con la suite en verde | la suite no cubre estos casos |
| Consolidador | — | `git diff HEAD` vacío en código; 14/14 confirmados estáticamente; sin tests nuevos | — |

**Cobertura combinada:**

- Revisado por al menos un auditor: pipeline diario, gates de riesgo, Kelly y banca, liquidación, stores y locks, calibración (Claude parcial, OpenAI completa), backtests, proveedores, BAT, CI, hooks y routing, secretos versionados.
- Cobertura parcial o sin revisar por ninguno: `audit/html_report.py` completo, `audit/clv*.py`, `closing_capture.py`, adaptadores deportivos y features concretas (`rest_form`, `weather`, `park`, `starters`, solo por interfaz), UI y scripts de investigación.
- **NOT_VERIFIABLE:**
  - secretos en `logs/` y `data/output/` (permiso denegado a Claude);
  - vulnerabilidades actuales de dependencias;
  - contratos vivos de proveedores;
  - disponibilidad temporal exacta dentro del día de las features históricas (OpenAI: INFERRED, sin leakage confirmado);
  - impacto económico real.

## 7. Observaciones (no son defectos)

- **O-1 (Claude):** la condición 2 del gate es un EV autoestimado. Coincide con el pre-registro; cambiarla es decisión del operador.
- **O-2 (Claude):** una sola liga con picks retenidos aborta la generación de todas. Es conservador y está documentado.
- **O-3 (Claude):** `served_pending_expired_total` = brasileirao 35, chile 49, mlb 54, wnba 12. Causa NOT_VERIFIABLE. Encaja con la clase AUD-003/004, pero no se estableció el vínculo.
- **O-4 (Claude):** en el chequeo de calibración de `report.py` se comparan poblaciones distintas.
- **O-5 (OpenAI, INFERRED):** un registro con `allowed: "false"` (cadena) se evalúa como verdadero. No se conoce ningún productor legítimo; es endurecimiento, no defecto.
- **O-6 (OpenAI):** la tarea `Dashboard` terminó con rc 267014. Foto puntual, sin análisis de causa.
- **O-7 (OpenAI, NOT_VERIFIABLE):** tratamiento de las medias liquidaciones en el test de signo del gate. El pre-registro es binario y no se inventa una regla.

## 8. Descartes (DISMISSED) conservados

- **Claude:**
  - D-1: lock sin latido (secciones críticas ≤ 2,2 s).
  - D-2: referencias rotas en `.claude/agents` (notas históricas).
  - D-3: push en team totals (solo líneas .5).
  - D-4: secretos versionados.
  - D-5: leakage del calibrador (split por `event_id`).
  - D-6: leakage de `roi_engine`.
- **OpenAI:**
  - pérdida concurrente en `_persist_settled`: el lock la cubre;
  - anulación masiva por payload vacío: la bloquea `scores_trusted`;
  - red bajo `OFFLINE_MODE`;
  - temporales fijos en `atomic`;
  - leakage intradía en builders y backtests;
  - contaminación entre lados en el split;
  - test demo sin aislamiento;
  - exposición de literales del detector;
  - desincronización de prompts.

El consolidador no encontró contradicción entre estos descartes y ningún hallazgo confirmado.

## 9. Comparación histórica

- Ninguno de los 14 hallazgos repite un ID abierto de r2 (`audit/audit-2026-09-22-r2/FINDINGS.md`, sha256 `2105cdbf…2f19`) ni de la ronda 09-18.
- Persistencias de clase:
  - AUD-006 es un resto de A-01 (2026-08-31).
  - AUD-003 y AUD-004 son restos de AUD-MED-003 y AUD-MED-004 (2026-09-13).
  - AUD-002 es la carrera que la ronda 09-18 dejó como NOT_VERIFIABLE y que ahora está reproducida.
  - AUD-013 recae sobre código de la remediación r2 (`4fa1673`).
- **La ronda r2 sigue sin verificación independiente.** La revalidación que hace OpenAI de sus AUD-001…004 es evidencia secundaria, no su cierre.
- **Métricas de esta ronda:**
  - 14 hallazgos fuente (Claude 5, OpenAI 9) → 14 consolidados: 1 fusión parcial, CLAUDE-002(b) con OPENAI-003, y 1 división, CLAUDE-002(a).
  - 1 coincidencia parcial, 13 exclusivos, 0 falsos positivos, 0 degradados a no verificable.
  - Descartes conservados: 6 de Claude y 9 de OpenAI.
  - No se evalúa a los auditores por su número de hallazgos.

## 10. Limitaciones de la consolidación

- Los arneses de reproducción no se volvieron a ejecutar. La evidencia REPRODUCED es la de origen y la confirmación estática es del consolidador.
- La severidad de AUD-003 se eleva respecto a Claude por irreversibilidad. El volumen productivo de anulaciones indebidas ya persistidas es NOT_VERIFIABLE sin leer datos a nivel de fila.
- `CHANGES.md`, `VALIDATION.md` y `STATUS.md` de `latest` pertenecen a r2: se verificó que son idénticos, por sha256, a `audit/audit-2026-09-22-r2/`. Esta fase no los reescribe. Los sustituirán las fases de remediación y verificación de esta ronda.
- Nada de este documento afirma rentabilidad. Las probabilidades son estimadas; hit rate, ROI esperado y ROI realizado se tratan como magnitudes distintas.
