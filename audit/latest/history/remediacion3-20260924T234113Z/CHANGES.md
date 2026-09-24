# Remediación autorizada · ronda `audit-2026-09-23`

- **Fase:** remediación. Contrato: `audits/prompts/corregir-auditoria.md` (skill `audit-remediation`).
- **Implementador:** Claude Code (`claude-opus-5-5`), 2026-09-23.
- **Revisión independiente previa al cierre:** subagente `independent-code-reviewer` despachado en `fable`, por la regla 1 de `MODEL_ROUTING.md`; ver §3. No sustituye a la fase de verificación independiente.
- **Fuente:** `audit/latest/FINDINGS.md` y `BACKLOG.md` de esta ronda. Son la línea base; no se modifican.
- **Alcance autorizado:** la orden del operador fue «Lee y ejecuta íntegramente las instrucciones de corregir-auditoria.md». Se interpretó como **todos los confirmados** (AUD-001…AUD-014), la única lectura de «íntegramente» que no deja IDs sin tratar. No incluye umbrales, pre-registros, el registro productivo del gate, datos de `data/`, commits ni despliegue.
- **Base Git:** `main` @ `7bd565e`. Al empezar no había cambios de código, solo entregables de auditoría. **Nada se ha commiteado.**

## 1. Resultado por ID

| ID | Sev. | Estado inicial | Estado final | Prueba discriminante (falla en HEAD → pasa ahora) |
|---|---|---|---|---|
| AUD-001 | HIGH | confirmado | **implementado, pendiente de verificación** | `test_orchestrator_safety.py`: 3 tests nuevos; `test_live_gate_integration.py::test_gate_not_revalidated_…` |
| AUD-002 | HIGH | confirmado | **implementado, pendiente de verificación** | `test_prediction_gate.py::test_una_actualizacion_solapada_…`, `::test_la_liberacion_espera_…` |
| AUD-003 | HIGH | confirmado | **BLOQUEADO** (§2) | fallback revertido; tests de regresión FABLE-001 |
| AUD-004 | MEDIUM | confirmado | **implementado, pendiente de verificación** | `test_candidate_history_fallback.py::test_desplazado_sin_marcador_…` |
| AUD-005 | MEDIUM | confirmado | **implementado, pendiente de verificación** | `test_live_gate_integration.py::test_banca_cero_…` (ramas edge y accuracy) |
| AUD-006 | MEDIUM | confirmado | **implementado, pendiente de verificación** | `test_daily_picks.py::TestProbabilidadDeDecision`, `test_breakeven.py::test_mean_est_prob_…` |
| AUD-007 | MEDIUM | confirmado | **implementado, pendiente de verificación** | `test_calibrator.py`: 4 tests nuevos + 1 contraprueba |
| AUD-008 | MEDIUM | confirmado | **implementado, pendiente de verificación** | `test_edge_information.py`: 2 tests nuevos + 2 contrapruebas |
| AUD-009 | MEDIUM | confirmado | **implementado, pendiente de verificación** | `test_store_concurrency.py` (3 stores) |
| AUD-010 | MEDIUM | confirmado | **implementado, pendiente de verificación** | `test_fip_boxscore_errors.py` (4 casos + contraprueba) |
| AUD-011 | MEDIUM | confirmado | **implementado, pendiente de verificación** | `test_audit_hooks.py::test_crossreview_*` (2 + 2 contrapruebas) |
| AUD-012 | LOW | confirmado | **implementado, pendiente de verificación** | `test_candidate_history_fallback.py::test_dos_generaciones_…` |
| AUD-013 | LOW | confirmado | **implementado, pendiente de verificación** | `test_gate_block_visibility.py` + comprobación de comportamiento en HEAD (VALIDATION §3) |
| AUD-014 | LOW | confirmado | **implementado, pendiente de verificación** | `test_monte_carlo.py`: 7 tests de cuartos + contraprueba |

Los 14 se revalidaron contra `7bd565e` antes de tocar nada (confirmación estática en la consolidación y reproducción con test discriminante aquí). Ninguno resultó falso positivo ni estaba ya corregido.

## 2. Detalle por ID

### AUD-001 — Gate revalidado antes de generar
- **Causa:** `write_prediction_gate` corría al final de `run_all`, dentro de `if not args.no_report`, así que los picks del día salían con la autorización de ayer.
- **Archivos:** `scripts/run_all.py`, `src/sqp/pipeline/daily.py`, `scripts/run_daily.py`.
- **Cambio:**
  - Nuevo `_refresh_prediction_gate(bets_dir) -> bool`, que nunca lanza, llamado en live **antes** del bucle de ligas y fuera de `--no-report`.
  - Si falla, `run_league(..., gate_deny_all=True)` genera en default-deny, con log de error por liga.
  - Parámetro keyword-only con default `False`: compatible con los llamadores existentes.
  - `run_daily.py` (manual y demo, fuera de producción) no revalida el gate; ahora su aviso de `--mode live` lo dice (FABLE-003).
- **Tests:** `test_orchestrator_safety.py` (orden gate → run_league con `--no-report`, fallo → `gate_deny_all=True`, el helper nunca lanza). El test live previo ahora sustituye el helper para no tocar el registro productivo.
- **Aceptación:** ningún candidato nuevo con stake > 0 en un mercado denegado por la evaluación vigente. Cubierto por los tests de orden y de default-deny.
- **Residual:** `run_daily.py` sigue sin revalidar (documentado). Los BAT no cambian: `DIARIO_COMPLETO` encadena SETTLE → `run_all --mode live`.

### AUD-002 — Transacción del pestillo bajo lock
- **Archivos:** `src/sqp/risk/prediction_gate.py`.
- **Cambio:**
  - `write_prediction_gate` evalúa fuera del lock y delega en `_persist_under_lock`, bajo `locked(bets_dir/prediction_gate.json)`: leer estado previo, centinela, `_apply_latch`, escribir registro y rastro, retirar centinela.
  - `release_prediction_gate_latch` usa el mismo lock (`_release_under_lock`).
  - `LockNoAdquiridoError` sale sin escribir y `run_all` lo trata como default-deny.
- **Tests:**
  - Dos escritores con barrera: B arma el pestillo y A escribe después con su evaluación vieja. En HEAD, `latched` acaba en False.
  - Liberación concurrente con un escritor: en HEAD devuelve False.
- **Aceptación:** sin liberación humana, ningún escritor con estado viejo puede sustituir `latched=true`. Cumplido.
- **Residual:** ninguno conocido. Fable confirmó que no hay reentrada del lock (no reentrante) en ningún llamador.

### AUD-003 — BLOQUEADO
- **Intento:** fallback `history_scores_map` de `ResultsStore` para candidatos de equipo antes de `_with_stale_voids`.
- **Por qué se revirtió (FABLE-001, CRITICAL, reproducido por Fable y por el implementador):**
  - A la hora de liquidar, `cands` contiene picks **aún no jugados**.
  - En una serie MLB (mismo local y visitante en días consecutivos), el pick del juego 2 de hoy se emparejaba por (local, visitante) ± 1 día con el juego 1 de ayer. Salía `loss`, pnl −100, **de forma irreversible**, porque `DEDUP_KEY` no lleva `result`.
  - Cualquier regla de fechas que lo acote sería un umbral inventado sobre una operación irreversible. Además, el problema de fondo, la identidad de un partido entre proveedores, ya figura como **abierto** (AUD-002 de la remediación 2026-09-14, «proximidad de fechas y equipos no prueba identidad»).
- **Estado del código:** sin fallback histórico para candidatos. Fuera de la ventana del feed rige la política de expiración de siempre. El comentario en `runner.py` lo explica.
- **Tests que fijan el estado seguro:**
  - `test_un_pick_sin_jugar_no_se_liquida_con_el_partido_anterior_de_la_serie` (regresión de FABLE-001);
  - `test_candidato_jugado_fuera_de_ventana_no_se_gradua_desde_el_historico`.
- **Qué falta para desbloquear:** una decisión del operador sobre la identidad de eventos entre The Odds API y los vendors de resultados. Por ejemplo, persistir en el candidato un identificador del vendor, o exigir fecha local exacta con zona horaria por liga. Después, un test de serie, uno de aplazado y uno de doubleheader.
- **Impacto mientras siga bloqueado:** un candidato con marcador solo en el histórico sigue anulándose por expiración (el hallazgo original). Con el gate en default-deny (0/49), el stake es 0.

### AUD-004 — `start_time` para picks desplazados
- **Archivos:** `src/sqp/settlement/runner.py`.
- **Cambio:**
  - `_tennis_prediction_metadata` pasa a llamarse `_prediction_metadata`; el cuerpo no cambia (predictions vigente + `archive/predictions_*` dentro del lookback).
  - `fetch_and_settle` toma `start_times` de ahí, además de `_prediction_start_times`, para todos los candidatos.
  - Envoltorio best-effort `_candidate_metadata`.
- **Efecto:** un desplazado sin marcador expira como `void/stale_void` a los `STALE_VOID_DAYS`, igual que uno vigente. Es la política del 2026-07-12, no una regla nueva.
- **Medición FABLE-002** (solo lectura, 2026-09-23, script `scratchpad/medir_fable002.py`):
  - 85 desplazados sin liquidar (mls 6, ncaaf 71, nfl 7, uwcl 1);
  - **0 expirarían** en la primera pasada;
  - 84 son partidos futuros;
  - 0 sin `start_time`.
- **Residual:** anular es irreversible. Si se desbloquea AUD-003, los voids ya persistidos no se regradúan.

### AUD-005 — Banca 0 conserva la lista
- **Archivos:** `src/sqp/pipeline/daily.py`.
- **Cambio:**
  - Con banca ≤ 0 (o NaN), la elegibilidad se decide con la fracción de Kelly calculada con banca unitaria, que no depende de la banca.
  - La fila se conserva a stake 0 con flag `bankroll_zero`, en las ramas edge y accuracy.
  - Con banca > 0 la selección es idéntica a la anterior.
- **Contrato persistido:** flag nuevo `bankroll_zero` en `candidates_*.csv`. Fable verificó que `cleanup._actionable` y `report.rank_candidates` lo tratan como no accionable.

### AUD-006 — Probabilidad de decisión en la lista diaria
- **Archivos:** `scripts/daily_picks.py`, `src/sqp/audit/report.py`.
- **Cambio:** `rank_picks` usa `labels.decision_prob` (calibrada, con fallback por fila a la estimada). `_segment_audit.mean_est_prob` usa la misma. El nombre de columna `prob_est` no cambia.
- **Aceptación:** `roi_esp == estimated_edge` en filas calibradas. Cubierto por los tests.

### AUD-007 — Medias liquidaciones en el calibrador
- **Archivos:** `src/sqp/calibration/calibrator.py`.
- **Cambio:**
  - `train_market_calibrators` incluye `half_win` y `half_loss`, con target direccional y peso 0,5. Push y void siguen fuera.
  - `train_calibration(weight_col=...)`: `sample_weight` en la isotónica, NLL ponderada en `BetaCalibrator.fit(weights=...)`, ECE, Brier y el resto del informe ponderados (`_weighted_ece`, `_val_metrics`).
  - **Si todos los pesos son 1, la ruta es exactamente la anterior.** Lo fija un test de igualdad bit a bit de métricas y mapas.
- **Alcance:** afecta a los **candidatos** a calibrador que se entrenen a partir de ahora (staging). No cambia ningún calibrador live ni promueve nada.
- **Contexto:** OpenAI midió 14 medias liquidaciones en 30.921 filas graduadas; el efecto real será pequeño.

### AUD-008 — ROI canónico en `edge_information`
- **Archivos:** `src/sqp/evaluation/edge_information.py`, `scripts/research/measure_price_floor_preregistration.py`.
- **Cambio:**
  - `prepare` incluye las medias con P&L parcial (`0,5·(cuota−1)` y `−0,5`, como `settle.settle_candidates`).
  - `_won` es NaN para las medias, así que el hit rate binario no cambia.
  - El script del pre-registro del suelo de precio fija su muestra win/loss para que la medición del 2026-09-19 siga siendo reproducible (FABLE-004).
- **Aceptación:** la media de `_roi` a stake 1 coincide con `realized_roi_parts` (test).
- **Residual:** los informes `model_vs_market` generados a partir de ahora incluyen las medias. No se recalcularon informes pasados.

### AUD-009 — Stores históricos bajo lock
- **Archivos:** `src/sqp/storage/results_store.py`, `starters.py`, `starter_fip.py`.
- **Cambio:** leer, fusionar y escribir dentro de `locked(p)`. `mkdir` va antes. La red sigue fuera, porque la hacen los llamadores.
- **Residual:** `storage.starters.log_pitcher_confirmation` tiene el mismo patrón de read-modify-write sin lock. Ningún auditor lo reportó y **no se tocó**; es candidato a la próxima ronda.
- **Contrato:** ficheros `*.csv.lock` transitorios en `data/historical/`. Ningún glob los recoge.

### AUD-010 — Boxscore MLB validado
- **Archivos:** `src/sqp/providers/mlb_statsapi.py`.
- **Cambio:** `_get_with_retry` (estado HTTP y reintentos) más validación de `teams.home/away` antes de emitir fila. Un fallo del proveedor ya no produce una fila vacía que borre FIP.

### AUD-011 — Hook de revisión cruzada
- **Archivos:** `.claude/hooks/crossreview-on-stop.sh`.
- **Cambio:** la salida vacía ya no sale con éxito antes de mirar `rc`. `rc ≠ 0` o salida vacía (con cualquier `rc`) cuentan como revisión NO ejecutada: aviso y marcador restaurado. Un veredicto con texto sigue bloqueando (exit 2).

### AUD-012 — Archivo por generación
- **Archivos:** `src/sqp/pipeline/daily.py` (`_archive_existing`), `src/sqp/settlement/runner.py` (`_ARCHIVE_DAY`).
- **Cambio:** si el hueco `_<día>.csv` guarda **otra** generación (contenido distinto), la copia va a `_<día>_<HHMMSS>.csv` (hora UTC de `generated_at`, o del mtime). Re-archivar la misma generación sigue siendo idempotente.
- **Contrato persistido:** nombre nuevo solo en caso de colisión. Consumidores comprobados por Fable: `_ARCHIVE_DAY` y la purga, que usa el mtime.

### AUD-013 — Centinela visible
- **Archivos:** `src/sqp/risk/prediction_gate.py` (`prediction_gate_block`), `src/sqp/monitoring/health.py`, `scripts/gate_status.py`.
- **Cambio:** aviso WARN en health con motivo y ruta. `gate_status` muestra «CENTINELA DE BLOQUEO» en vez de «registro ausente o ilegible».

### AUD-014 — Monte Carlo con líneas de cuarto
- **Archivos:** `src/sqp/simulation/monte_carlo.py`.
- **Cambio:** para `is_quarter_line`, `_quarter_decision` calcula `win_units/(win_units+loss_units)` sobre las dos líneas adyacentes. Las líneas enteras y medias no cambian de ruta.

## 3. Revisión independiente (Fable)

- **Veredicto inicial:** «NO APTO tal cual» por FABLE-001. El resto de los AUD, correctos.

| Hallazgo | Sev. | Tratamiento |
|---|---|---|
| FABLE-001 | CRITICAL | Reproducido. Fallback revertido y AUD-003 **BLOQUEADO**. Test de regresión añadido. La reproducción de Fable pasa ahora |
| FABLE-002 | MEDIUM | Medido (§2, AUD-004): 0 anulaciones en la primera pasada a fecha 2026-09-23 |
| FABLE-003 | LOW | Documentado en el aviso de `run_daily.py` |
| FABLE-004 | LOW | Muestra del pre-registro congelada en su script |
| FABLE-005 | LOW | Informe de validación ponderado completo |

- Tras estos cambios **no se volvió a despachar a Fable**. La verificación independiente de la fase siguiente debe revisar los cambios posteriores a su informe (`runner.py`, `run_daily.py`, `measure_price_floor_preregistration.py`, `calibrator.py` en FABLE-005).

## 4. Incidencias de la sesión

- **Autofix del hook PostToolUse:** `ruff check --fix` quitó dos veces un import añadido antes de su primer uso (`prediction_gate.py`, `run_all.py`). Se restauró en ambos casos y ruff lo verificó.
- **Finales de línea:**
  - Varios ficheros reescritos con Python quedaron en CRLF; se devolvieron a LF, como declara `.gitattributes` (`eol=lf`).
  - Esa normalización tocó por error tres entregables de los auditores: `claude/EVIDENCE.json`, `claude/REPORT.md` y `openai/EVIDENCE.json`. Se **restauraron byte a byte** (CRLF uniforme, conversión inversa exacta) y sus sha256 coinciden otra vez con el manifest.
- **Detector de secretos:** `check-secrets.sh` avisa en cada Bash de literales de prueba **preexistentes** en `tests/test_audit_hooks.py` (líneas 29 a 132, placeholders de sus propios tests). No hay secretos reales ni líneas nuevas implicadas.
- **Logs:** los imports de `sqp` en el script de medición de solo lectura y en los arneses pueden haber añadido líneas a `logs/sqp.log`. No se leyó ni se modificó a mano.

## 5. Riesgos residuales

- **AUD-003 bloqueado:** los candidatos fuera de la ventana del feed se siguen anulando por expiración aunque su resultado exista.
- **Nada commiteado.** Según la memoria del proyecto, el guard KI-036 **aborta el run diario de las 12:00** si hay código sin commitear en `src/`, `scripts/`, `configs/` o `*.bat`. Hace falta decidir el commit, o aceptar ese aborto, antes de la próxima ejecución programada.
- **Pendiente de verificación independiente** (`audits/prompts/verificar-remediacion.md`). Nada de lo anterior declara el proyecto libre de errores.

## 6. Remediación 2 (2026-09-24): identidad exacta de eventos (AUD-003 y KI-058)

- **Autorización:** el operador pidió elegir la mejor opción para la identidad de eventos entre proveedores y aplicarla (bloqueo de AUD-003, KI-057).
- **Versión previa de estos entregables:** `history/remediacion2-20260924T204629Z/`.

**Medición previa** (solo lectura, filas servidas graduadas por el feed como verdad):

- **ESPN** guarda la fecha UTC del inicio. Coincide en el mismo día UTC, con 7 excepciones de unos 617.
- **MLB Stats API** guarda la fecha oficial local, que coincide con la fecha en `America/New_York`: 655 coinciden, 0 no coinciden, 13 doubleheaders y 24 sin resultado.
- La tolerancia de ±1 día sobraba y era la que producía los errores.

**Cambio** (`src/sqp/settlement/runner.py`):

- `expected_result_date(league, start_time)` y `exact_history_scores_map`. Un resultado del histórico solo se usa si cumple todo esto:
  - mismo par ordenado;
  - fecha exacta del vendor;
  - resultado único;
  - partido ya empezado;
  - sin otro evento del par ese día en nuestros registros;
  - sin resultado del par en el día anterior ni en el siguiente (back-to-back);
  - en MLB, además, fuera de la franja 03:00Z–10:00Z.
- Se aplica a **candidatos de ligas ESPN** (AUD-003) y al **stream servido de ligas ESPN** (KI-058).
- **MLB queda fuera del fallback histórico**, en candidatos y en el stream servido, hasta persistir la identidad de calendario (KI-059).
- `history_scores_map` (±1) ya no se usa en ningún camino que liquide.

**Revisión independiente (Fable), tres rondas:**

| Ronda | Veredicto | Motivo o resultado |
|---|---|---|
| R2 | NO APTO | FABLE-R2-001 (HIGH, reproducido): doubleheader MLB con un juego aplazado, el histórico guarda solo el jugado. FABLE-R2-002: series MLB en Asia |
| R3 | NO APTO | FABLE-R3-001: el stream servido de MLB aún podía graduar con el otro juego; la guarda cubría 4 de 10 doubleheaders medidos. R3-003: back-to-back en ESPN |
| v3 | **APTO para commit** | 593 eventos ESPN graduables con 0 contradicciones frente al feed. Pérdida de evidencia: 7 eventos por R3-002 y 4 de WNBA por la guarda de adyacencia |

**Tests:** `tests/settlement/test_candidate_history_fallback.py`, 16 tests, 8 de ellos fallan en `6676e9a`. Cubren ESPN exacto, aplazado, inicio futuro, serie FABLE-001, doubleheader MLB, fecha ET nocturna, doubleheader en nuestros registros, Tokio, back-to-back e integración del stream servido en ESPN y en MLB.

**Efecto medido sobre datos reales (2026-09-24):**

- 3 candidatos pendientes ya empezados, 0 graduables.
- 0 `stale_void` persistidos con resultado exacto, así que no hay nada histórico que reconciliar.

**Estado:**

- **AUD-003: IMPLEMENTADO PARCIAL**, pendiente de verificación independiente. Resuelto para las ligas ESPN; MLB sigue la política de expiración (KI-059).
- **KI-058:** resuelto para ESPN; MLB queda excluido del fallback.
