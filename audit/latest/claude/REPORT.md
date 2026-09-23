# Diagnóstico independiente — Claude · ronda `audit-2026-09-23`

- **Auditor:** `claude` (Claude Code, `claude-opus-5-5`).
- **Base Git:** `main` @ `7bd565e19606a70b37f704ca44cdc41e168ba274`, árbol **limpio** al inicio.
- **Alcance:** auditoría integral — `src/sqp`, `scripts/`, `tests/` (como evidencia), `configs/`, BAT de producción, CI, `.claude/` (settings, hooks, routing, referencias).
- **Fecha (UTC):** 2026-09-23.
- **Contrato:** `.claude/automation/audit-workflow.md` (prompt generado `audits/prompts/auditoria-claude-code-opus-5.md`) y taxonomía de `AGENTS.md`.
- **Escrituras de esta fase:** solo `audit/latest/` (MANIFEST, `claude/`) y la copia de preservación `audit/audit-2026-09-22-r2/`. Las reproducciones corrieron en directorios temporales (`tempfile`) con `ROOT` redirigido; no se tocó ningún dato productivo.

## 1. Resumen

| Severidad | Confirmados | P0 | P1 | P2 | P3 |
|---|---:|---:|---:|---:|---:|
| CRITICAL | 0 | – | – | – | – |
| HIGH | 0 | – | – | – | – |
| MEDIUM | 3 | 0 | 0 | 3 | 0 |
| LOW | 2 | 0 | 0 | 0 | 2 |

- **Sin P0/P1.** Ningún hallazgo pone dinero en riesgo hoy: el gate de predicción está en default-deny (0 de 49 cortes habilitados, registro del 2026-09-22T15:15Z) y todos los stakes son 0.
- Los tres MEDIUM afectan la **integridad del rastro de picks y de la salida al operador**, no a las probabilidades del motor:
  - **CLAUDE-001:** con banca 0, la lista de candidatos desaparece entera. Reproducido.
  - **CLAUDE-002:** un pick desplazado sin marcador nunca se anula y sale del ledger sin veredicto. Reproducido.
  - **CLAUDE-003:** la lista diaria ordena y filtra con la probabilidad cruda que el propio sistema descartó. Verificado estáticamente y medido.
- Controles globales en HEAD:
  - `ruff check src scripts tests`: OK.
  - `mypy src`: OK, 106 ficheros.
  - CI remoto en `7bd565e`: **success**.
  - `sync_agent_instructions.py --check`: sincronizado.
  - `validate_claude_model_routing.py`: OK.
  - `pytest`: 2299 passed, 1 skipped.
- **No se emite PASS**: faltó la segunda opinión (MCP codex caído) y el barrido de `logs/` fue denegado por permisos (§9).

## 2. Preparación de la ronda y preservación

- `audit/latest/` contenía la ronda `audit-2026-09-22-r2`, en estado `DIAGNOSTICO Y CONSOLIDACION COMPLETADOS; REMEDIACION PENDIENTE DE AUTORIZACION` y sin `VERIFICATION.md`. Esa ronda **ya no está en diagnóstico**, así que este diagnóstico abre una ronda nueva y no se une a ella.
- Se copió íntegra a `audit/audit-2026-09-22-r2/`: **11/11 ficheros con sha256 idéntico**, verificado antes de escribir nada en `latest`. Hashes en `EVIDENCE.json`.
- El borrado de los entregables viejos de `latest` lo **denegó el clasificador de permisos**. Por eso siguen allí `FINDINGS.md`, `BACKLOG.md`, `CHANGES.md`, `VALIDATION.md`, `STATUS.md`, `openai/` e `history/`. Todos pertenecen a rondas anteriores y el `MANIFEST.json` nuevo los declara en `stale_in_latest`. Se reemplazaron `MANIFEST.json` y `claude/`.
- **Contaminación declarada (paso 2 del contrato):**
  - La memoria automática del harness inyectó al arranque titulares de rondas previas: índice `MEMORY.md` con KI-053…056, «ciclo audits 09-14», «producción restaurada», etc.
  - Durante el análisis principal no se leyeron `FINDINGS`, `STATUS` ni informes del otro auditor.
  - El `MANIFEST.json` de r2 se consultó solo en sus campos de identidad y estado (`round_id`, `status`, `stale_in_latest`).
  - La comparación histórica (§6) se hizo después de fijar las conclusiones.

## 3. Inventario y cobertura

| Componente | Criticidad | Método | Estado |
|---|---|---|---|
| `pipeline/daily.py` (run_league, gates, exposición, `_finalize`, archivo) | P0 | lectura completa + reproducción aislada | REVISADO → CLAUDE-001, CLAUDE-004 |
| `pipeline/probabilities.py` (consenso, no-vig, decisión, ajustes, ejecución) | P0 | lectura completa | REVISADO, sin hallazgos |
| `markets/edge.py`, `markets/vig.py`, `risk/kelly.py` | P0 | lectura | REVISADO, sin hallazgos |
| `settlement/settle.py`, `settlement/runner.py`, `scripts/settle_all.py` | P0 | lectura completa + reproducción aislada | REVISADO → CLAUDE-002; observación O-2 |
| `storage/served_store.py`, `storage/lock.py`, `storage/atomic.py` | P0 | lectura + medición de tiempos de lectura | REVISADO; D-1 descartado |
| `risk/prediction_gate.py` (diff 9fa276a..HEAD entero y pestillo) | P0 | lectura + estado persistido (agregado) | REVISADO → CLAUDE-005; observación O-1 |
| `risk/degradation.py`, `risk/bankroll.py` (diff reciente) | P0 | lectura | REVISADO, sin hallazgos nuevos |
| `calibration/calibrator.py` (train, gate, apply) | P0 | lectura parcial: train/apply/registry | PARCIAL: promoción y auto-promoción no leídas línea a línea |
| `config.py` (env vs yaml, validate) | P1 | lectura | REVISADO, sin hallazgos |
| `providers/odds_api.py` (clave, reintentos, caché, frescura) | P1 | lectura | REVISADO, sin hallazgos |
| `pipeline/revalidation.py` | P1 | lectura de ambos pases | REVISADO, sin hallazgos |
| `pipeline/cleanup.py` | P1 | lectura | REVISADO |
| `pipeline/team_totals_capture.py` | P2 | lectura parcial | PARCIAL; D-3 descartado |
| `backtesting/roi_engine.py` | P1 | lectura del bucle walk-forward | REVISADO: sin leakage; paridad de políticas documentada |
| `scripts/run_all.py` | P0 | lectura completa | REVISADO |
| `scripts/daily_picks.py`, `evaluation/tipster.py`, `audit/report.py` | P1 | lectura + medición sobre el stream vigente | REVISADO → CLAUDE-003; observación O-4 |
| `audit/html_report.py` (1599 líneas) | P2 | búsqueda dirigida: fuentes de probabilidad, ROI, lenguaje | PARCIAL |
| BAT: `DIARIO_COMPLETO`, `SETTLE_ALL`, `RUN_DIARIO_ALL` | P0 | inspección estática | REVISADO |
| CI (`.github/workflows/ci.yml`) y estado remoto | P1 | lectura + `gh run list` | REVISADO: verde en HEAD |
| `.claude/` settings, hooks, routing, referencias rotas | P2 | validadores de solo lectura + barrido de referencias | REVISADO; D-2 descartado |
| Secretos en ficheros versionados | P0 | barrido por patrones | REVISADO: sin fugas |
| Secretos en `logs/` y `data/output` | P0 | barrido por patrones | **NO VERIFICABLE** (permiso denegado) |
| `features/*`, `models/*`, adaptadores deportivos | P1 | **EXCLUIDO** por tiempo; solo el contrato temporal de `build_adjustment_context` | NO REVISADO en profundidad |
| `audit/clv*.py`, `evaluation/feature_shadow.py`, `intraday_scan.py`, `closing_capture.py` | P2 | no revisados | EXCLUIDO |

La cobertura **no es total**: las filas PARCIAL y EXCLUIDO no permiten afirmar ausencia de defectos en esas zonas.

## 4. Hallazgos confirmados

### CLAUDE-001 — Con banca 0 la lista de candidatos desaparece entera, contra lo que declara el código

- **Categoría:** lógica / integridad de salida. **Severidad:** MEDIUM. **Confianza:** HIGH. **Evidencia:** REPRODUCED. **Prioridad:** P2.
- **Archivo / línea:**
  - `src/sqp/pipeline/daily.py:897-901` y `:952-953`: la selección exige `stake > 0`.
  - `src/sqp/risk/kelly.py:30-31`: `bankroll <= 0 → (0, 0)`.
  - `src/sqp/risk/bankroll.py:384-395`: banca a 0 ante `LedgerIntegridadError`, con el comentario «la lista de picks se sigue generando entera».
- **Activación:** `apply_dynamic_bankroll` fija `settings.bankroll = 0`, ya sea por `LedgerIntegridadError` (ledger ilegible) o por un balance ≤ 0.
- **Problema:** en `pick_mode: edge` la **selección** de un candidato usa el stake de Kelly: `elif stake <= 0 and not suspect: continue`. Kelly devuelve 0 con banca 0 antes incluso de evaluar el edge. Por eso, con banca 0, ningún lado con edge suficiente llega a `candidates_*.csv`; solo sobreviven los *suspect* (edge > `max_plausible_edge`). Los gates, en cambio, conservan la fila y le quitan el dinero (`_zero_stake_flag`). La banca 0 no hace eso: borra la fila.
- **Evidencia concreta:**
  - Script `scratchpad/repro_bankroll0b.py`: `ROOT` en un temporal, modo demo `nba`, `calibration_enabled=False` y `max_plausible_edge=1.0`, esto último solo para que los lados con edge no queden como *suspect*.
  - Resultado: `bankroll=1000 → candidates=2` (stakes 4.09 y 3.61) y `bankroll=0 → candidates=0`.
- **Esperado:** mismo conjunto de candidatos, todos con stake 0 y un flag explícito (p. ej. `banca_no_verificable`). Es lo que promete el comentario de `bankroll.py` y lo que exige la regla «el gate quita el stake, nunca la lista».
- **Observado:** `candidates_<liga>.csv` sin filas; `_finalize` además borra el fichero vigente (`cand_path.unlink()`), tras archivarlo.
- **Causa raíz:** la selección por edge y el dimensionamiento están acoplados en una sola llamada (`kelly_fraction_stake`). La banca entra como condición de selección y no solo como tamaño.
- **Consecuencia:**
  - Los días con ledger ilegible, todas las ligas publican 0 candidatos. No quedan filas que liquidar en `settled_*.csv`, se pierde el KPI de picks y del dashboard, y la revalidación no tiene nada que revalidar.
  - La lista del operador **no** se pierde: `daily_picks.py` lee el stream servido, que se graba antes del filtrado. Ese es el control compensatorio que limita la severidad a MEDIUM.
- **Controles existentes:** default-deny del gate (no hay dinero en juego); stream servido intacto; log de error «BANCA NO VERIFICABLE».
- **Corrección mínima:** separar selección de dimensionamiento. Seleccionar con `adjusted_edge >= min_edge`, como hace Kelly internamente, con independencia de la banca. Dimensionar después y, si la banca es ≤ 0, registrar el candidato con stake 0 y un flag propio.
- **Pruebas necesarias:** `run_league` en demo con banca 0 debe producir el mismo número de candidatos que con banca > 0, todos con stake 0 y el flag. Añadir el caso con `LedgerIntegridadError` vía `apply_dynamic_bankroll`.
- **Criterio de aceptación:** conjunto de candidatos independiente de la banca; stake 0 y flag cuando la banca es ≤ 0.
- **Limitaciones:** hoy el ledger es legible y el balance positivo, así que no está activo. Frecuencia real no verificable.

### CLAUDE-002 — Un pick desplazado (`superseded`) cuyo partido no tiene marcador nunca se anula, y sale del ledger sin veredicto

- **Categoría:** liquidación / integridad del ledger. **Severidad:** MEDIUM. **Confianza:** HIGH. **Evidencia:** REPRODUCED (rama de anulación) y STATICALLY_VERIFIED (rama sin fallback histórico). **Prioridad:** P2.
- **Archivo / línea:**
  - `src/sqp/settlement/runner.py:673-676`: `_with_stale_voids(..., _prediction_start_times(league))`.
  - `:406-418`: `start_time` solo del `predictions_<liga>.csv` **vigente**.
  - `:44-110`: `superseded_candidates`, con ventana de 14 días.
  - `src/sqp/domain/models.py:56`: `BetCandidate` no guarda `start_time`.
- **Activación:** un pick deja la lista antes del partido (lo recupera `superseded_candidates` desde `archive/`) y además ocurre una de dos cosas:
  - (a) el partido se cancela o pospone y nunca entrega marcador;
  - (b) la liquidación no corre dentro de la ventana `--days-from 3`, por caída o por tareas no lanzadas.
- **Problema:**
  - La anulación por expiración necesita el `start_time` del evento, y solo lo busca en el `predictions` vigente. Un evento ya jugado o cancelado **no está** en el run vigente de The Odds API, así que para un pick desplazado `start_time` es siempre desconocido y `void_stale_candidates` lo deja «abierto».
  - En deportes de equipo tampoco hay fallback contra `data/historical/` para candidatos. Sí lo hay para el stream servido (`_grade_served_from_history`) y para candidatos de tenis (AUD-MED-004). Un pick con el marcador fuera de la ventana del feed no se gradúa nunca.
  - A los 14 días (`SUPERSEDED_LOOKBACK_DAYS`) el pick sale del escaneo **sin fila en `settled_*.csv`**.
- **Evidencia concreta:**
  - Script `scratchpad/repro_superseded.py`: `ROOT` temporal, payload de scores sano (un partido ajeno completado, `scores_trusted=True`), pick con partido de hace 5 días y sin marcador.
  - Control (el pick en el fichero vigente, con su `start_time`): `[{'result': 'void', 'flags': 'stale_void'}]`.
  - Caso desplazado: `[]`, sin fila liquidada.
- **Esperado:** un pick desplazado sin marcador recibe `void/stale_void` pasados `STALE_VOID_DAYS`, igual que uno vigente. Uno con marcador en `data/historical/` se gradúa por el mismo fallback que ya tienen el stream servido y el tenis.
- **Observado:** ni se anula ni se gradúa; desaparece del escaneo a los 14 días.
- **Causa raíz:** el `start_time` del pick no viaja con el candidato y se reconstruye desde un fichero que solo describe el run vigente. El fallback histórico de AUD-MED-004 se aplicó solo a la ruta de tenis.
- **Consecuencia:**
  - Hoy (stakes 0): unidades de pick sin veredicto. Es la clase de hueco que AUD-MED-003 (2026-09-13) quiso cerrar: «132 de 730 unidades nunca recibieron veredicto».
  - Con stake real: un pick apostado en un partido jugado fuera de ventana deja el ledger y la banca dinámica desalineados del dinero. Uno cancelado no afecta al saldo (pnl 0), pero no deja rastro.
- **Controles existentes:**
  - El guard M2 de `run_all` (`unsettled_completed_picks`) solo cubre picks del fichero **vigente**.
  - `pending_served` sí tiene fallback y anulación, así que la evidencia de calibración no se pierde por esta vía.
- **Corrección mínima:** tomar `start_time` para los desplazados de la fila archivada. Dos vías posibles:
  - añadir `start_time` a `BetCandidate` (compatible hacia atrás con default);
  - cruzar con `archive/predictions_<liga>_<dia>.csv`, como ya hace `_tennis_prediction_metadata`.
  - Y añadir para candidatos de equipo el fallback `history_scores_map`, que ya existe.
- **Pruebas necesarias:** caso desplazado sin marcador → `stale_void`; caso desplazado con marcador solo en `ResultsStore` → graduado; regresión: sin duplicados por `DEDUP_KEY`.
- **Criterio de aceptación:** ningún pick archivado dentro de la ventana termina fuera del ledger sin `win/loss/push/void`.
- **Limitaciones:** frecuencia real no medida: requeriría cruzar `archive/` con `settled_*` (datos productivos). No se hizo en esta fase.

### CLAUDE-003 — La lista diaria del operador ordena, filtra y calcula el «ROI esperado» con la probabilidad cruda que el sistema descartó

- **Categoría:** cuantitativo / salida al operador. **Severidad:** MEDIUM. **Confianza:** HIGH. **Evidencia:** STATICALLY_VERIFIED, con medición. **Prioridad:** P2.
- **Archivo / línea:**
  - `scripts/daily_picks.py:116`: `p = estimated_probability`.
  - `:122` y `:177`: `roi_esp = p*cuota-1`.
  - `:175-176`: comentario «Es el `estimated_edge` de siempre».
  - Instancia secundaria en `src/sqp/audit/report.py:265`: `mean_est_prob` sobre `estimated_probability` en el «chequeo de calibración».
- **Activación:** siempre que exista un calibrador **live** para (liga, mercado). Hoy hay 3: `mlb_spreads`, `mlb_totals`, `wnba_spreads`.
- **Problema:**
  - En el stream servido, `estimated_probability` es `p_used`, la mezcla cruda `0,5·p_adj + 0,5·no-vig`. En cambio, `calibrated_probability` (`p_decision`) es la que decide edge y stake, y `estimated_edge = p_decision·cuota − 1` (`daily.py:873-875`, `:916-919`).
  - El dashboard (`html_report.py:792`) y el tipster (`tipster.py:100-111`) se corrigieron a `labels.decision_prob` en la auditoría 2026-08-31 (A-01), cuyo docstring llama a la cruda «una probabilidad descartada por el sistema».
  - `daily_picks.py`, que genera las tres listas diarias de `DIARIO_COMPLETO.bat:lista` (incluida `--min-prob 0.60 --min-roi 0`), se quedó fuera de ese arreglo. Además su comentario afirma que `roi_esp` es el `estimated_edge`, lo que es falso para toda fila calibrada.
- **Evidencia concreta:** sobre los 846 picks vigentes del stream (agregado, sin volcar datos):
  - 4 filas con `|calibrada − estimada| > 0,005`, con un máximo de 0,0259.
  - Hoy 0 discrepancias de signo entre `roi_esp` y `estimated_edge`.
- **Esperado:** las tres listas y el chequeo de calibración usan la probabilidad canónica de decisión (`decision_prob`), como el dashboard y el tipster.
- **Observado:** ordenan y filtran con la cruda. Con más calibradores promovidos, el filtro `--min-prob 0.60` y el orden pueden incluir, excluir o reordenar picks distinto de como decidió el motor.
- **Causa raíz:** un arreglo por clase (A-01) aplicado a dos de tres consumidores. No hay un único lector canónico para la columna de probabilidad en los generadores de listas.
- **Consecuencia:** hoy es pequeña (4 filas); crece con cada promoción de calibrador. La cifra rotulada «ROI esperado» no coincide con el edge del motor para mercados calibrados.
- **Controles existentes:** ninguno sobre `daily_picks.py`. El tipster y el dashboard sí están bien.
- **Corrección mínima:** `p = decision_prob(d)` en `rank_picks`; corregir el comentario; en `report.py`, `mean_est_prob` con la misma función.
- **Pruebas necesarias:** frame con `calibrated_probability ≠ estimated_probability` → `prob_est`, `roi_esp`, el orden y `--min-prob` siguen a la calibrada; fallback por fila cuando la calibrada es NaN.
- **Criterio de aceptación:** `roi_esp == estimated_edge` (redondeo aparte) en toda fila servida.
- **Limitaciones:** la magnitud futura depende de promociones que decide el operador.

### CLAUDE-004 — Un segundo run el mismo día sobrescribe la copia de archivo del primero

- **Categoría:** preservación de datos. **Severidad:** LOW. **Confianza:** HIGH. **Evidencia:** STATICALLY_VERIFIED. **Prioridad:** P3.
- **Archivo / línea:** `src/sqp/pipeline/daily.py:421-428` (`archive_dir / f"{stem}_{day}{suffix}"`, con `day` tomado de `generated_at`).
- **Activación:** dos runs el mismo día UTC, algo que ya ocurrió (re-run tras el fallo del 2026-08-27).
- **Problema:**
  - Run 1 escribe F1. Run 2 archiva F1 como `candidates_x_D.csv` y escribe F2.
  - Al día siguiente, el run archiva F2 con el **mismo** nombre `candidates_x_D.csv` y pisa F1 (`shutil.copy2`).
  - Los picks de F1 ausentes de F2 dejan de existir en `archive/`, así que `superseded_candidates` no puede recuperarlos.
- **Esperado:** una copia por generación, sin pisar ninguna (sufijo con la hora de `generated_at`, o no sobrescribir si ya existe con contenido distinto).
- **Consecuencia:** picks mostrados en el primer run del día quedan fuera de la liquidación de desplazados. Hoy son stake 0; con stake real, un pick apostado del primer run no tendría veredicto.
- **Corrección mínima:** nombre de archivo con la marca completa de `generated_at`, adaptando `_ARCHIVE_DAY` en `runner.py` para que siga extrayendo el día.
- **Pruebas necesarias:** dos `_finalize` el mismo día más un tercero al día siguiente → las dos generaciones están en `archive/`; `superseded_candidates` las ve.
- **Criterio de aceptación:** ninguna generación archivada se pierde.
- **Limitaciones:** no se reprodujo (análisis estático directo); frecuencia no medida.

### CLAUDE-005 — El centinela `prediction_gate.blocked` no aparece en ningún control de salud, y `gate_status.py` lo describe como registro «ausente o ilegible»

- **Categoría:** observabilidad de un control. **Severidad:** LOW. **Confianza:** HIGH. **Evidencia:** STATICALLY_VERIFIED. **Prioridad:** P3.
- **Archivo / línea:**
  - `src/sqp/risk/prediction_gate.py:474-486` y `:683-689`: centinela nuevo del commit `4fa1673`.
  - `scripts/gate_status.py:137` y el render («registro ausente o ilegible»).
  - `grep` sin coincidencias de `blocked` en `src/sqp/monitoring/` y `scripts/health_check.py`.
- **Activación:** un `prediction_gate.json` ilegible o con forma inesperada. El escritor lanza cada día y el centinela persiste.
- **Problema:** mientras exista el centinela, el gate queda cerrado **indefinidamente**, que es la dirección segura. Lo único visible es un `warning` de `run_all` («No se pudo actualizar el gate») en `logs/run_diario.log`. `pipeline_health.json` sigue en su estado y `gate_status.py` atribuye la denegación a un registro ausente cuando el registro existe y se lee.
- **Esperado:** health en WARN/ERROR con el motivo y la ruta del centinela; `gate_status.py` distingue «centinela de bloqueo» de «registro ausente».
- **Consecuencia:** un corte que ganase su test de entrada no podría entrar hasta que alguien lea el log, y el diagnóstico apuntaría al sitio equivocado. No hay riesgo de dinero (falla cerrado).
- **Corrección mínima:** comprobación en `health_check`, más un mensaje específico en `gate_status.render` cuando exista `PREDICTION_GATE_BLOCK_FILENAME`.
- **Pruebas necesarias:** con el centinela presente, health reporta el motivo y `gate_status` muestra el mensaje específico.
- **Criterio de aceptación:** el centinela es visible en la salida de salud del día.
- **Limitaciones:** hoy no hay centinela en `data/bets/` (comprobado por listado).

## 5. Observaciones, no verificables y descartes

**Observaciones (no son defectos del contrato vigente):**

- **O-1 · Condición 2 del gate = EV autoestimado.** `ev_flat = mean(p_modelo·(cuota−1) − (1−p_modelo))` (`prediction_gate.py:243-244`) es el ROI **esperado según el propio modelo**, no el ROI realizado a stake plano. Coincide literalmente con el pre-registro (`docs/research/2026-08-16-preregistro-regla-de-salida.md`, «Condición 2»), así que no es un defecto. Aun así, no demuestra rentabilidad neta de vig: un modelo sobreconfiado la cumple por construcción. Cualquier cambio es una decisión del operador sobre un pre-registro.
- **O-2 · Aborto global por una liga.** `settle_all.py` devuelve 1 si **cualquier** liga que falla retiene picks comenzados, y `DIARIO_COMPLETO.bat` aborta entonces la generación de **todas** las ligas, pese a que `run_all.py` ya omite por liga (guard M2). Es conservador y está documentado como contrato («se ABORTA el run diario para no perder picks»). Contradecirlo es decisión del operador.
- **O-3 · Filas servidas pendientes fuera de ventana.** `pipeline_health.json` (2026-09-22T15:18Z) reporta `served_pending_expired_total` = brasileirao 35, chile 49, mlb 54, wnba 12. Son candidatas a `stale_void` en vez de graduarse. Causa **NOT_VERIFIABLE** sin leer datos productivos a nivel de fila.
- **O-4 · Poblaciones distintas en el chequeo de calibración.** En `audit/report.py:_segment_audit`, el «chequeo de calibración» compara `mean_est_edge` (todas las filas graduadas, casi todas con stake 0) con `realized_roi` (solo filas con stake). `n_staked` lo mitiga, pero el texto afirma que deberían aproximarse.

**No verificables:**

- **NV-1:** barrido de patrones de clave (`apiKey=`) en `logs/` y `data/output/`: permiso denegado. El código redacta la clave en excepciones (`odds_api.py:184-210`) y la clave de caché se calcula antes de añadir `apiKey`; no se pudo comprobar el histórico de logs.
- **NV-2:** segunda opinión OpenAI/Codex: el MCP `codex` falló al conectar (`CONNECTION_CLOSED`).

**Descartados (DISMISSED):**

- **D-1 · Lock sin latido.** `storage/lock.py` rompe un lock con más de 300 s sin latido. Las secciones críticas medidas son cortas: la lectura del mayor fichero de cuotas del mes (`odds_mlb_202609.csv`, 31 MB, 205.058 filas) tarda 2,2 s, y la red de `revalidate_pitchers` está fuera del lock. Sin escenario demostrable.
- **D-2 · Referencias rotas.** `.claude/agents/*` citan `.claude/loops/{backtest,refactor,release}.md`, que ya no existen, pero son notas históricas («antes …») tras la fusión `56edbcd`, no cargas.
- **D-3 · Push en team totals.** `team_totals_capture.tail_over` ignora la masa de push, pero `team_total_rows` solo admite líneas `.5` (`:103`).
- **D-4 · Secretos versionados.** Sin claves reales en ficheros versionados; solo placeholders de tests y texto de auditorías.
- **D-5 · Leakage del calibrador.** El split temporal agrupa por `event_id` y ordena por fecha del partido (`calibrator.py:468-495`).
- **D-6 · Leakage del backtest.** `roi_engine` usa un snapshot estrictamente previo al comienzo, features con `d < rd` y adaptador congelado por día.

## 6. Comparación histórica (tras fijar conclusiones)

Búsqueda dirigida en `audit/*/FINDINGS.md` e informes `claude`/`openai` archivados:

| ID | Estado histórico |
|---|---|
| CLAUDE-001 | **NUEVO**. La ronda 09-22 revisó Kelly con «banca ≤0 protegida», pero no el efecto de la banca 0 sobre la **selección**. |
| CLAUDE-002 | **NUEVO**. Deriva de AUD-MED-003 (09-13, superseded) y AUD-MED-004 (09-13, fallback de tenis), que no cubrieron la expiración ni el fallback de equipo. |
| CLAUDE-003 | **NUEVO**, persistencia de clase: A-01 (2026-08-31) corrigió dashboard y tipster, no `daily_picks.py`. |
| CLAUDE-004 | **NUEVO**. |
| CLAUDE-005 | **NUEVO**, sobre código de `4fa1673` (remediación r2, pendiente de verificación independiente). |

Los hallazgos de la ronda r2 no se reverifican aquí: su verificación independiente sigue **pendiente** y está preservada en `audit/audit-2026-09-22-r2/`.

## 7. Validaciones y comandos

| Comando | Resultado | Clasificación |
|---|---|---|
| `ruff check src scripts tests` | exit 0, «All checks passed!» | OK |
| `mypy src` | exit 0, «no issues found in 106 source files» | OK |
| `pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest` | exit 0, **2299 passed, 1 skipped** en 22 min 40 s | OK |
| `gh run list --limit 6` | HEAD `7bd565e`: **success**; `efe09bb`: cancelled (sustituido por el siguiente push) | OK |
| `python scripts/sync_agent_instructions.py --check` | exit 0, «synchronized» | OK |
| `python scripts/validate_claude_model_routing.py` | exit 0, «OK» | OK |
| `scratchpad/repro_bankroll0b.py` | `bankroll=1000 → 2`, `bankroll=0 → 0` candidatos | REPRODUCED (CLAUDE-001) |
| `scratchpad/repro_superseded.py` | control `void/stale_void`; desplazado `[]` | REPRODUCED (CLAUDE-002) |
| Medición de probabilidades del stream vigente (agregado) | 846 vigentes; 4 con \|Δ\| > 0,005; 0 discrepancias de signo | Evidencia de CLAUDE-003 |
| Estado del gate persistido (agregado) | 49 cortes, 0 habilitados, 0 pestillos, 0 tests de entrada gastados | contexto |

## 8. Plan priorizado

| Prioridad | ID | Cambio mínimo | Archivos | Autorización |
|---|---|---|---|---|
| P2 | CLAUDE-001 | Seleccionar por `adjusted_edge ≥ min_edge` con independencia de la banca; banca ≤ 0 → stake 0 con flag | `pipeline/daily.py` (+ test) | toca la ruta de selección de picks; conviene revisión humana |
| P2 | CLAUDE-002 | `start_time` en el candidato o cruce con `archive/predictions_*`; fallback `history_scores_map` para candidatos de equipo | `domain/models.py`, `settlement/runner.py`, `pipeline/daily.py` (+ tests) | cambia el esquema de `candidates_*.csv` (compatible con default) |
| P2 | CLAUDE-003 | `decision_prob` en `daily_picks.rank_picks` y `report._segment_audit` | `scripts/daily_picks.py`, `audit/report.py` (+ tests) | salida al operador |
| P3 | CLAUDE-004 | Archivo por generación completa | `pipeline/daily.py`, `settlement/runner.py` (`_ARCHIVE_DAY`) | — |
| P3 | CLAUDE-005 | Centinela visible en health y `gate_status` | `monitoring/health.py` o `scripts/health_check.py`, `scripts/gate_status.py` | — |

Riesgos residuales:

- Zonas PARCIAL y EXCLUIDO del §3: features, adaptadores, CLV, promoción del calibrador.
- La verificación independiente de la remediación r2 sigue pendiente.
- Falta la segunda opinión.

## 9. Limitaciones

- **Sin segunda opinión:** MCP `codex` caído en esta sesión. No se inventa informe OpenAI.
- **Permisos:**
  - Denegado el barrido de `logs/` y `data/output/` (NV-1).
  - Denegado el borrado de los entregables viejos de `latest` (declarados en `stale_in_latest`).
- **Contaminación de contexto** por la memoria automática del harness (§2).
- **Cobertura no total** (§3).
- Nada de este informe afirma rentabilidad. Las cifras de probabilidad son **estimadas**, y hit rate, ROI esperado y ROI realizado se tratan como magnitudes distintas.
