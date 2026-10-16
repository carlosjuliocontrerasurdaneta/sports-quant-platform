# Diagnóstico independiente — Claude (pendiente de ronda)

- **Auditor:** `claude` (coordinador: `claude-opus-5-5`; revisiones por área: Fable (A), Opus (B, C), Sonnet (D); revalidación de cada candidato por el coordinador).
- **Fecha UTC:** inicio 2026-10-15T13:07:12Z · cierre 2026-10-15T14:40Z.
- **round_id:** **NO ASIGNADO.** Propuesto `audit-2026-10-15`, pendiente del coordinador (ver «Bloqueo de ronda»).
- **Base:** `main` en `65368c815530bf179c5780db78a9fe196996802d` (10 commits por delante de `origin/main`).
- **Alcance:** auditoría integral del repositorio: `src/sqp`, `scripts`, `tests`, `configs`, BAT, CI, dependencias y gobernanza del asistente en `.claude/`.
- **Resultado:** 0 CRITICAL · **2 HIGH** · 6 MEDIUM · 9 LOW confirmados. **P1: CLAUDE-001 y CLAUDE-002.** No es un PASS incondicional.

## Bloqueo de ronda y declaraciones previas

1. **Bloqueo de ronda.**
   - `audit/latest/MANIFEST.json` (sha256 `9d23b278…cb01ac`) sigue en la ronda `audit-2026-09-23`, ya cerrada, y no existe una copia preservada en `audit/audit-2026-09-23/`.
   - El auditor OpenAI estaba escribiendo hoy en `audit/latest/openai/pending-20261015T124425Z-openai/`: última escritura a las 13:01:47Z, seis minutos antes de empezar este diagnóstico. **No he leído su contenido**, solo nombres y mtimes.
   - Con un posible escritor activo, el contrato prohíbe archivar o reemplazar `latest`. Por eso este informe va en `audit/latest/claude/pending-20261015T130712Z-claude/`.
   - Siguen intactos `audit/latest/claude/REPORT.md` (`345cd9dd…cd79`) y `EVIDENCE.json` (`c5772664…51c9`), que pertenecen a la ronda `audit-2026-09-23`.
   - **Acción para el coordinador:** preservar `audit-2026-09-23`, inicializar la ronda nueva y mover ambos `pending-*` a sus rutas canónicas.
2. **Contaminación de contexto, declarada.**
   - Antes del diagnóstico, el contexto del coordinador ya contenía:
     - fragmentos de la ronda `audit-2026-09-23` (resumen del manifest; líneas de `FINDINGS.md` y `claude/REPORT.md` sobre el centinela `prediction_gate.blocked`);
     - el índice de memoria del proyecto, con historia de auditorías.
   - No leí informes de OpenAI ni la consolidación durante el análisis.
   - Mitigación: las cuatro revisiones por área arrancaron sin ese contexto y con prohibición expresa de leer `audit/`, `audits/`, `Obsidian/` y `.claude/memory/`. El coordinador solo revalidó contra código y datos.
   - La comparación con el histórico (paso 7) se hizo **después** de fijar las conclusiones.
3. **Cambios preexistentes excluidos (autoría propia).**
   - El working tree contiene la remediación sin commit de CLAUDE-005/H-2 de una ronda anterior (KI-073), hecha por este mismo agente:
     - `.claude/hooks/run-tests-on-stop.sh`, `.claude/hooks/_stop_tests.py`;
     - `pyproject.toml`;
     - 11 `tests/*.py` con `pytestmark = heavy`, `tests/test_stop_tests_hook.py`, `tests/test_claude_model_routing.py`;
     - `.claude/memory/*` y `Obsidian/Bitácora/2026-10-15.md`.
   - **Quedan fuera del alcance:** nadie puede auditar con independencia su propio trabajo. Necesitan verificación independiente.
   - La suite de base se ejecutó sobre el working tree con esos cambios. Solo añaden marcadores y pruebas: la colección crece de 3.171 a 3.205 sin perder ninguna.
4. **Efectos incidentales.**
   - La revisión del área B importó `sqp.logging_config` en reproducciones. Ese módulo añade un handler a `logs/sqp.log` si existe `logs/`, así que se añadieron ~6 líneas INFO/WARNING a `logs/sqp.log` entre las 13:20 y las 13:34Z. Después se usó `logging.disable`.
   - pytest creó `.codex-tmp/pytest-claude-{20261015,A,B,C,D}`, todos ignorados por git (`.gitignore:85`).
   - Ningún otro fichero se modificó.

## Alcance, inventario y cobertura

| Componente | Criticidad | Método | Estado |
|---|---|---|---|
| `markets/` (odds, vig, edge, settlement_math), `risk/kelly.py` | P0 | Lectura y tests | Revisado |
| `pipeline/probabilities.py`, `pipeline/daily.py` (probabilidad, edge, stake, cutoff) | P0 | Lectura, reproducción sintética y agregado del stream servido | Revisado → CLAUDE-001, CLAUDE-014 |
| `risk/prediction_gate.py`, `risk/degradation.py` | P0 | Lectura y reproducción del test de signo con el stream graduado | Revisado (impacto de CLAUDE-001) |
| `risk/bankroll.py` | P0 | Lectura parcial y tests | Parcial |
| `risk/clv_gate.py` | P1 | — | No verificado (desactivado: `configs/default.yaml:255`, `enabled: false`) |
| `models/distributions.py`, `models/elo.py`, `simulation/monte_carlo.py` | P0 | Lectura y tests | Revisado (elo parcial) |
| `calibration/calibrator.py` y los 3 calibradores vivos | P0 | Lectura y carga de los calibradores | Revisado. `data.py` y `pergame.py`: parcial |
| `settlement/settle.py`, `settlement/runner.py` | P0 | Lectura y tests | Revisado → CLAUDE-007 |
| `features/` (rest_form, builders) | P1 | Lectura de los cortes temporales | Parcial; sin leakage encontrado |
| `backtesting/roi_engine.py` | P1 | Lectura y tests | Revisado. `engine.py` y `tuning.py`: no verificados |
| `evaluation/tipster.py` | P2 | Lectura | Revisado. Resto de `evaluation/*`: no verificado |
| `providers/odds_api.py`, `odds_cache.py`, `espn_*`, `mlb_statsapi.py` | P0 | Lectura y reproducciones sin red | Revisado → CLAUDE-007, 010, 013 |
| `providers/nhl_api.py`, `synthetic.py`, `date_window.py` | P1 | Lectura parcial | Parcial |
| `storage/` (atomic, lock, stores, starters, goalies, schedule) | P0 | Lectura y reproducción (starters) | Revisado → CLAUDE-009; `feature_store`: parcial |
| `pipeline/` (closing_capture, revalidation, budget, team_totals_capture, intraday, cleanup) | P0 | Lectura y reproducción | Revisado → CLAUDE-006, 011, 012 |
| `pipeline/goalie_backfill.py`, `sports/adapters.py`, `nhl_goalie_matching.py` | P1 | — | No verificado |
| `monitoring/` (run_status, health) | P1 | Lectura | Revisado |
| `audit/` (report, html_report, clv, segments) | P2 | grep dirigido | Parcial |
| `scripts/` (cadena diaria: run_all, settle_all, daily_picks, capture_closing_odds, backfill_*) | P0 | Lectura | Revisado; resto de CLIs: parcial |
| 10 BAT (DIARIO_COMPLETO, SETTLE_ALL, RUN_DIARIO_ALL, CAPTURE_CLOSE, BACKFILL_ALL, …) | P0 | Lectura (ninguno ejecutado) | Revisado |
| Tareas `SQP_*` | P1 | `Get-ScheduledTask` (solo lectura) | 5 en Ready; Diario rc=0 el 2026-10-14 |
| CI (`.github/workflows/ci.yml`, runs 38256027979 y 38253559026) | P0 | `gh run view`; clon `--no-tags --depth 1` en `%TEMP%` | Revisado → CLAUDE-002, 003 |
| Dependencias (`pyproject.toml`, `requirements.lock`) | P1 | Comparación con el intérprete de producción | Coinciden; pip-audit no ejecutado (red) |
| Secretos | P0 | `.gitignore`, `git grep` y redacción en `odds_api.py` | Sin secretos versionados. `logs/` y `.env.example`: **no verificables** (permiso denegado) |
| Gobernanza (`settings.json`, hooks, skills, agentes, comandos, MODEL_ROUTING, prompts generados) | P0 | Lectura, `_targets.py`/`fable_gate._run` con entradas sintéticas, `sync_agent_instructions --check` | Revisado → CLAUDE-008, 015, 016 |
| Hooks `run-tests-on-stop.sh` y `_stop_tests.py` | — | — | **Excluidos** (autoría propia, sin commit) |

## Hallazgos confirmados

### CLAUDE-001 — NHL: el 1X2 a tiempo reglamentario de casas europeas se mezcla en el consenso y en el no-vig de un moneyline a 2 vías

- **Clasificación:** odds / no-vig / validez del gate · **HIGH** · confianza HIGH · **REPRODUCED** · **P1**
- **Dónde:**
  - `src/sqp/pipeline/probabilities.py:35-52`: `_consensus_lines` agrupa por (market, outcome, point) sin distinguir casas a 2 o 3 vías.
  - `src/sqp/pipeline/probabilities.py:110-131`: `_novig_probs` toma todas las claves h2h con `point=None`, incluida `Draw`, y solo exige `len(keys) >= 2`.
  - `src/sqp/providers/odds_api.py:65`: NHL tiene `three_way: False`.
  - No existe ningún filtro de `Draw` en la ingesta ni en el consenso.
- **Activación:** cualquier evento NHL en el que alguna casa cotice `Draw` dentro de `h2h`. Lo hacen unibet_fr, onexbet, unibet_uk, codere_it, winamax_fr y betclic_fr: 12.907 líneas `Draw` de 94.865 h2h NHL en 09–10/2026, en 119 de 384 eventos con snapshot previo al inicio (medición del área A).
- **Esperado:** en un moneyline NHL con prórroga, fair(home)+fair(away)=1, y el consenso solo con contratos equivalentes.
- **Observado:**
  - **Revalidación sintética del coordinador** (`scratchpad/repro_a1.py`, funciones de producción): con 2 casas a 2 vías y 1 casa con `Draw`, las claves del consenso son `['Away','Draw','Home']` y fair = `{'Home': 0.4608, 'Away': 0.383, 'Draw': 0.1562}`, así que home+away = **0.8438**. Solo con las casas a 2 vías: `{'Home': 0.5359, 'Away': 0.4641}`.
  - **Agregado del coordinador sobre `data/calibration/served_nhl.csv`:** 335 pares h2h (evento, generación); **320 suman < 0,95**, con mediana **0,8477**, en el rango `generated_at` 2026-09-23 → 2026-10-14.
  - Dato del área A: sesgo medio de fair(home) de −0,0733, y la mediana del precio de home sube +0,018 de media (máximo +0,080).
- **Causa raíz:** el h2h de esas casas es otro contrato (1X2 a 60′), pero se trata como el moneyline a 2 vías. `_novig_probs` acepta más desenlaces de los que tiene el mercado.
- **Consecuencias:**
  1. **Prediction gate (regla vinculante de stake real):** `d = (novig−y)² − (modelo−y)²` compara contra un mercado artificialmente peor. Test de signo `nhl|h2h`: wins 47/105 con el novig guardado frente a 41/105 con el novig renormalizado por evento (+6 a favor de abrir; reproducción del área A, con la referencia renormalizada como aproximación).
  2. `brier_market` inflado en el monitor de degradación.
  3. `p_decision` sesgado unos −3,7 pp y precio de consenso inflado. El ledger liquida a ese precio (`settle.py:161-164`), así que **el ROI realizado registrado de NHL h2h queda sobrestimado**.
  4. La revalidación usa el mismo consenso (inferido, misma fuente).
- **Controles existentes:** el gate es default-deny con `min_n=300` y hoy está cerrado (`n=105`, `muestra_insuficiente`). No hay daño monetario demostrado; la evidencia OOS se acumula contaminada desde 2026-09.
- **Corrección mínima:**
  - En ligas con `three_way=False`, excluir del grupo h2h del evento las casas que coticen `Draw`, en un único punto compartido por consenso, conteos, dispersión, `_execution_prices` y el snapshot de revalidación.
  - Que `_novig_probs` exija exactamente {home, away} en 2 vías.
  - Las filas ya guardadas en el stream y el gate requieren una decisión aparte del operador.
- **Pruebas necesarias:** `EventOdds` NHL con 2+1 casas: fair(home)+fair(away)=1 y la mediana ignora la casa a 3 vías. Regresión de `_novig_probs` con 3 claves en una liga no three_way.
- **Criterio de aceptación:** 0 pares NHL h2h con suma ≠ 1 (±1e-9) en filas nuevas; tests anteriores verdes.
- **Limitaciones:** el impacto exacto en el gate requiere recalcular el novig desde los snapshots crudos. Los totals NHL de esas casas no son concluyentes (mediana −0,003).
- **Histórico:** **NUEVO** (sin coincidencias de `Draw` ni de tres vías en hallazgos previos).

### CLAUDE-002 — CI de `main` en rojo permanente: dos tests dependen de tags que solo existen en local, y su aserción no discrimina

- **Clasificación:** CI / prueba dependiente del entorno · **HIGH** · confianza HIGH · **REPRODUCED** · **P1**
- **Dónde:**
  - `tests/research/test_measure_tier_a_gap.py`, en `test_git_tag_message_reads_the_real_tag` (`assert msg is not None` seguido de `parse(...) == 0.075`) y en `test_medir_mode_full_success_with_tz_sensitivity`.
  - `scripts/research/measure_tier_a_gap.py:174-183`: `_git` devuelve `""` cuando el tag no existe, no `None`.
  - `.github/workflows/ci.yml:34,91`: `actions/checkout@v4` sin `fetch-depth` ni tags.
- **Activación:** cualquier push.
- **Esperado:** el test valida el tag real o se salta explícitamente si falta.
- **Observado:**
  - Runs 38256027979 y 38253559026 (2026-10-12, sha d985ef8): **las 5 patas fallan** con `assert None == 0.075 ± 7.5e-08` (`2 failed, 3004 passed, 83 skipped` en 3.13 y 3.14; `2 failed, 3013 passed, 74 skipped` en Windows).
  - Coordinador: `git ls-remote --tags origin` no devuelve ningún `prereg*`, mientras que `git tag -l "prereg*"` en local da `prereg-peso-mercado-h` y `prereg-tier-a-t0`.
  - Área C: en un clon `--no-tags --depth 1` de 65368c8, **2 failed**; en el repositorio local, 2 passed.
- **Causa raíz:** tags sin push, checkout superficial sin tags, y un test que confunde ausencia con presencia (`""` no es `None`).
- **Consecuencia:** la puerta de CI está inutilizada. Todo push sale rojo, así que una regresión real no se distingue del ruido, y arrastra a CLAUDE-003.
- **Controles existentes:** el issue de alerta #4 de CI rojo está abierto; producción no depende de CI.
- **Corrección mínima:**
  - Empujar los tags (decisión del operador).
  - Añadir `fetch-depth: 0` a los dos jobs.
  - En el test: `pytest.skip` si `git rev-parse <tag>` falla, y `assert msg` en lugar de `is not None`.
- **Pruebas necesarias:** en un clon sin tags, *skip* y no *fail*; con tags, pasa.
- **Criterio de aceptación:** run de CI en verde en `main`.
- **Histórico:** **NUEVO**.

### CLAUDE-003 — pip-audit no se ejecuta en CI cuando falla pytest, y su versión no está fijada

- **Clasificación:** dependencias / CI · **MEDIUM** · HIGH · **REPRODUCED** · **P2**
- **Dónde:** `.github/workflows/ci.yml:80-83` (paso pip-audit dentro del job `test`, después de Pytest, sin `if: always()`; `pip install pip-audit` sin versión).
- **Observado (coordinador):** en `gh run view 38256027979 --json jobs`, el paso pip-audit sale `skipped` en 3.11, 3.12, 3.13 y 3.14. El job Windows no tiene ese paso.
- **Consecuencia:** el control documentado como «BLOCKING» (`ci.yml:75`) no corre en `main` desde el último verde (2026-09-26). Su estado es **NOT_VERIFIABLE** desde entonces.
- **Corrección mínima:** un job propio o `if: always()`, con la versión fijada.
- **Prueba:** un run con pytest en rojo sigue mostrando pip-audit ejecutado.
- **Histórico:** pip-audit aparece en rondas previas como puerta en verde. **NUEVO** en cuanto a que deja de ejecutarse.

### CLAUDE-004 — Los tags de pre-registro (anclas H/T0) existen solo en el clon de producción

- **Clasificación:** integridad de pre-registro · **MEDIUM** · HIGH · **STATICALLY_VERIFIED** · **P2**
- **Evidencia:**
  - `git ls-remote --tags origin` está vacío.
  - `prereg-tier-a-t0` (2026-10-02) y `prereg-peso-mercado-h` (2026-10-13, sobre 107e9b7, un commit que tampoco está en origin).
- **Consecuencia:**
  - Mientras no haya push, no existe prueba externa fechada de que el pre-registro precedió a los datos.
  - Perder este clon perdería la fecha del tagger y el `max_plausible_edge` registrado en el mensaje del tag. `resolve_h_t0` tiene respaldo por `git log` para H/T0, pero no para ese valor.
- **Corrección mínima:** empujar los tags (decisión del operador) y comprobar en el `--contar` mensual que el tag existe en origin.
- **Histórico:** **NUEVO**. Comparte la acción de push con CLAUDE-002, pero el impacto es distinto.

### CLAUDE-005 — `main` lleva 10 commits sin push, uno con código de producción, que se ejecuta sin validación externa

- **Clasificación:** operación / control de cambios · **MEDIUM** · HIGH · **STATICALLY_VERIFIED** · **P2**
- **Evidencia:**
  - `git rev-list --count origin/main..main` = 10.
  - Incluye 904af27, que toca `src/sqp/pipeline/daily.py` y `src/sqp/storage/served_store.py` y añade una columna al stream servido.
- **Consecuencia:** producción ejecuta el árbol local a las 12:00. La guarda de DIARIO solo detecta el árbol sucio o atrasado, no el adelantado. El código nuevo no pasa por CI, que además está rojo (CLAUDE-002).
- **Controles:** `tests/test_served_market_shrink.py` da 6 passed (clon del área C), y la suite completa local está verde salvo los fallos ambientales.
- **Corrección:** cerrar CLAUDE-002 y hacer push.
- **Histórico:** **NUEVO** (estado actual).

### CLAUDE-006 — `capture_close` siempre sale con rc=0: la captura de cierre, la revalidación y el guard de abridores fallan en verde

- **Clasificación:** observabilidad de controles / errores silenciados · **MEDIUM** · HIGH · **REPRODUCED** (área B) y **STATICALLY_VERIFIED** (coordinador) · **P2**
- **Dónde:**
  - `scripts/capture_closing_odds.py:55-56,89-90,106-107`: excepciones convertidas en `log.warning(...)`.
  - `:108`: `return 0` incondicional.
  - `src/sqp/pipeline/closing_capture.py:164-165`: `except Exception` por liga, sin ningún campo de fallo en el resumen.
  - `CAPTURE_CLOSE.bat:44`: solo registra el fallo con rc ≠ 0.
- **Activación:** un fallo persistente (401, clave revocada, `LockNoAdquiridoError` en la revalidación, esquema roto).
- **Esperado:** etapa `capture_close` FALLIDA en `logs/run_status/` y health check en ERROR, como promete `monitoring/run_status.py`.
- **Observado (área B):** un cliente falso con `HTTPError` 401 devuelve `{'captured': {}, 'credits_spent': 0, …}` y rc=0, con un solo WARNING.
- **Consecuencia:** cierres no capturados, que según `revalidation.py:150-165` son la única evidencia del gate de CLV, y revalidación de picks caducados que no se ejecuta, sin aviso durante días.
- **Controles comprobados:** `pipeline_liveness` solo mira `predictions_*.csv`, y el Programador de tareas ve 0. Ninguno lo detecta.
- **Corrección:** contar las ligas fallidas y las excepciones de revalidación y guard, y devolver rc=1 si fallan todas las ligas o si lanza la revalidación o el guard, sin abortar los pasos siguientes.
- **Pruebas:** cliente que lanza en todas las ligas → rc≠0; revalidación con `LockNoAdquiridoError` → rc≠0.
- **Histórico:** rondas previas citan `capture_closing_odds.py` por cadencia y suspensión (AUD-INF-002), no por el código de salida. **NUEVO**.

### CLAUDE-007 — Tenis: `ESPNTennisResultsProvider` salta ventanas fallidas sin registrarlo; el backfill sale rc=0 y la liquidación trata el payload parcial como fiable

- **Clasificación:** contrato de proveedor / estado persistido · **MEDIUM** · MEDIUM-HIGH · **REPRODUCED** (área B) y **STATICALLY_VERIFIED** (coordinador) · **P2**
- **Dónde:**
  - `src/sqp/providers/espn_tennis.py:149-151`: `log.warning(...); return []`, sin `failed_windows`.
  - Comparar con `espn_results.py:113-116,199`, que sí lo tiene (corrección de KI-060).
  - `src/sqp/settlement/runner.py:945`: `results_trusted = bool(usable)`.
- **Activación:** una de las 2–3 fechas consultadas falla (429, 5xx o SSL) y otra devuelve partidos.
- **Observado (área B):** la fecha 20261016 da 503 tres veces y la 20261009 un partido; resultado `rows 1, failed_windows attr: False`.
- **Consecuencia:** el refresco diario de tenis sale en verde con el histórico incompleto, y la anulación por expiración puede anular de forma **irreversible**, pasados 3 días, picks cuyos resultados estaban en la ventana fallida. Requiere que el fallo parcial persista varios días.
- **Corrección:** `failed_windows` en el proveedor de tenis, propagado a rc=1, y `results_trusted` exigiendo que no haya ventanas fallidas.
- **Pruebas:** sesión falsa con 503 en una ventana: `failed_windows` no vacío, rc=1 y ningún void.
- **Histórico:** **NUEVO** (la corrección de KI-060 no se trasladó a tenis).

### CLAUDE-008 — Los hooks PostToolUse de secretos, tests pendientes y revisión cruzada no se disparan con la herramienta PowerShell

- **Clasificación:** control que se cree activo · **MEDIUM** · HIGH · **STATICALLY_VERIFIED** · **P2**
- **Dónde:** `.claude/settings.json`, matchers `"Edit|Write|Bash"` (check-secrets, mark-tests-pending, mark-crossreview-pending). No incluyen `PowerShell`, aunque `fable_gate` (PreToolUse) sí usa `Bash|PowerShell`.
- **Activación:** editar código, configs o riesgo con PowerShell (`Set-Content`, `Out-File`, `>`). PowerShell es la shell primaria declarada en este entorno.
- **Observado:** el matcher filtra por nombre de herramienta. Según el área D, `_targets.py` alimentado con `tool_name: PowerShell` sí extrae la ruta, así que el bloqueo está solo en el matcher.
- **Controles:** `_targets.py --with-git` recoge los cambios en el siguiente Edit/Write/Bash, y los commits sensibles pasan por `fable_gate`. Una sesión que solo use PowerShell queda sin compensación.
- **Corrección:** matcher `Edit|Write|Bash|PowerShell` en esos tres hooks, más un test de contrato.
- **Limitación:** no reproducido con una llamada real del harness.
- **Histórico:** la ampliación a Bash está registrada (AUD-MED-002). **NUEVO** para PowerShell.

### CLAUDE-009 — `log_pitcher_confirmation` duplica filas cuando un abridor es None, y su read-modify-write no usa lock

- **LOW** · HIGH · REPRODUCED (área B: 3 llamadas idénticas añaden 2, 1 y 1 filas) · STATICALLY_VERIFIED (coordinador) · **P3**
- **Dónde:** `src/sqp/storage/starters.py:78-79` (`str(prev)` frente a `str(row)` compara `'nan'` con `'None'`); `:89`, `atomic_write_csv` sin `locked()`.
- **Consecuencia:** falsos cambios en el log que alimenta el pre-registro de timing de abridores. Hoy no lo consume ningún código del pipeline.
- **Corrección:** normalizar con `_norm_str`, como en `goalies.py`, y envolver la escritura en `locked(p)`.
- **Histórico:** la ausencia de lock en `starters.py` ya figura en la ronda `audit-2026-09-23` → **PERSISTENTE**; la duplicación por None/NaN es **NUEVA**.

### CLAUDE-010 — El presupuesto «total» de espera por conexión se crea por cliente, y el run diario crea un cliente por liga

- **LOW** · HIGH (estático), impacto inferido · STATICALLY_VERIFIED · **P3**
- **Dónde:** `src/sqp/providers/odds_api.py:43-47,101`, frente a `src/sqp/pipeline/daily.py:701` (`OddsAPIClient(...)` en `run_league`).
- **Consecuencia:** el comentario promete 180 s por run, pero en realidad son 180 s por liga. Un corte de red real puede alargar el run decenas de minutos.
- **Corrección:** compartir el presupuesto desde `run_all`.
- **Histórico:** **NUEVO**.

### CLAUDE-011 — La captura de cierre comprueba el gasto ya hecho, no el coste previsto, así que rebasa el tope diario

- **LOW** · HIGH · REPRODUCED (área B: `total 302 cap 300`) · STATICALLY_VERIFIED (coordinador, `closing_capture.py:133`) · **P3**
- **Consecuencia:** exceso acotado a un coste de liga por día (≤ 6 créditos).
- **Corrección:** estimar el coste antes de pedir, como `team_totals_capture.py:294-297`.
- **Histórico:** misma clase que una corrección previa en team_totals. **NUEVO** en closing.

### CLAUDE-012 — `_merge_results` descarta partidos reales de series MLB en días consecutivos

- **LOW** · HIGH · REPRODUCED (área B) · STATICALLY_VERIFIED (coordinador, `daily.py:120-131`) · **P3**
- **Consecuencia:** si el histórico va retrasado, los ratings pierden resultados recientes. La tolerancia de ±1 día casa solo por (día, local, visitante).
- **Control:** el paso 0.5 de DIARIO refresca 3 días antes del run, así que solo aplica si ese paso falla.
- **Corrección:** no descartar si el día exacto ya está consumido por otro reciente.
- **Histórico:** `_merge_results` aparece en una consolidación legacy. La identidad con este caso es **NOT_VERIFIABLE**, así que se registra como posible persistente.

### CLAUDE-013 — La caché de cuotas se escribe de forma no atómica y antes de persistir el snapshot

- **LOW** · MEDIUM · STATICALLY_VERIFIED · **P3**
- **Dónde:** `src/sqp/providers/odds_cache.py:83` (`write_text` directo) y `daily.py:762-765`.
- **Consecuencia:** si `append_snapshot` falla y se relanza dentro del TTL, ese snapshot nunca llega a `data/odds/`. Un JSON truncado provoca una nueva petición y gasta créditos.
- **Corrección:** `atomic_write_json` y escribir la caché después de persistir.
- **Histórico:** hubo un hallazgo previo en `odds_cache.py:81` sobre `mkdir`, que es distinto. **NUEVO**.

### CLAUDE-014 — Una probabilidad de modelo NaN se convierte en 0,99 en la capa de ajustes

- **LOW** (latente) · HIGH · REPRODUCED (área A) · STATICALLY_VERIFIED (coordinador, `probabilities.py:374`: `min(0.99, nan)` devuelve 0.99) · **P3**
- **Consecuencia:** la fila entraría al stream servido con `adjusted_probability=0.99`. Hoy no es alcanzable: `distributions._finite`, todos los coeficientes valen 0 y hay 0 NaN en el histórico.
- **Corrección:** excluir la selección (o lanzar) si `p_model` no es finito.
- **Histórico:** **NUEVO**.

### CLAUDE-015 — `MODEL_ROUTING.md:98` afirma como «hecho» una jerarquía con IDs no vigentes, fijada por un test

- **LOW** · HIGH · STATICALLY_VERIFIED · **P3**
- **Dónde:**
  - `.claude/automation/MODEL_ROUTING.md:98`: `claude-fable-5-1` > `claude-opus-5-5` > `claude-sonnet-5` > `claude-haiku-4-5`. Los IDs vigentes en este entorno son `claude-sonnet-5-5` y `claude-haiku-5-5`.
  - `tests/test_claude_model_routing.py:277` cementa esa cadena.
- **Consecuencia:** quien copie el ID para un despacho usaría el modelo equivocado. No hay uso operativo hoy (agentes y settings usan alias o `claude-opus-5-5`).
- **Corrección:** actualizar la línea y la aserción.
- **Limitación:** no verificado contra la documentación viva.
- **Histórico:** **NUEVO**.

### CLAUDE-016 — `crossreview-on-stop.sh` borra su centinela antes de comprobar si existe `codex`, y sin él sale en silencio

- **LOW** · HIGH · STATICALLY_VERIFIED (`.claude/hooks/crossreview-on-stop.sh:17-18`) · **P3**
- **Consecuencia:** sin `codex` en el PATH, la revisión cruzada del código de riesgo se pierde sin rastro. Las demás ramas de no-ejecución sí avisan.
- **Corrección:** comprobar `codex` antes del `rm`, o avisar y conservar el centinela.
- **Histórico:** **NUEVO**.

### CLAUDE-017 — El `basetemp` que prescribe el contrato de auditoría está dentro del repo y produce 3 falsos fallos

- **LOW** · HIGH · **REPRODUCED** · **P3**
- **Dónde:** `.claude/automation/audit-workflow.md` («usar pytest con `-p no:cacheprovider --basetemp=.codex-tmp/pytest`») y su prompt generado. Pruebas afectadas:
  - `tests/test_fable_gate.py::test_defense_in_depth_hard_blocks_with_an_explanatory_message_when_git_cannot_be_asked`
  - `tests/test_measure_tilt_nhl.py::test_git_head_returns_none_when_not_a_git_repo`
  - `tests/test_measure_tilt_nhl.py::test_git_status_porcelain_returns_none_when_not_a_git_repo`
- **Observado:**
  - Suite completa con `--basetemp=.codex-tmp/pytest-claude-20261015`: `3 failed, 3201 passed, 1 skipped in 3863.12s`, los 3 con `assert '' is None` o con rc 0 en lugar de 2.
  - Con el basetemp fuera del repo: `3 passed in 7.29s`.
  - Causa: `tmp_path` cae bajo un repositorio git, y las pruebas de «no es un repo» dejan de serlo.
- **Consecuencia:** cada auditoría que siga el contrato ve rojo ambiental y debe clasificarlo a mano; o, peor, lo toma por regresión.
- **Corrección:** basetemp fuera del árbol (p. ej. `%TEMP%`), o que esas pruebas fijen `GIT_CEILING_DIRECTORIES`.
- **Histórico:** rondas previas registran fallos ambientales de basetemp por WinError 5 (ACL), que es una causa distinta. **NUEVO**.

## Inferidos, no verificables y observaciones (no confirmados)

| Ref. | Descripción | Estado | Motivo |
|---|---|---|---|
| I-1 | `storage/lock.py:64,75,121`: carrera al romper un lock caducado (dos esperas, o titular > 300 s cuyo `finally` borra un lock ajeno) | INFERRED, MEDIUM | La lógica de la carrera es visible, pero la activación no está demostrada en el área |
| I-2 | `logging_config.py:79`: `RotatingFileHandler` por proceso, con solape CAPTURE_CLOSE/DIARIO; WinError 32 al rotar | INFERRED, LOW | No reproducido en concurrencia; stdout del BAT como compensación |
| I-3 | Calibración 1X2 por selección sin renormalizar (`probabilities.py:216-225`) | Observación (latente) | No hay calibradores h2h de fútbol vivos; los 3 vivos cumplen cal(p)+cal(1−p) ∈ [1,000; 1,002] |
| I-4 | Fútbol con prórroga (UCL/UWCL, playoffs MLS): ¿marcador a 90′ o a 120′ en `/scores`/ESPN? | NOT_VERIFIABLE | Requiere documentación del proveedor o muestras |
| I-5 | Barrido de secretos en `logs/` y `.env.example` | NOT_VERIFIABLE | Permiso denegado |
| I-6 | Estado de vulnerabilidades de `requirements.lock` desde 2026-09-26 | NOT_VERIFIABLE | pip-audit requiere red; ver CLAUDE-003 |
| O-1 | `fable-gate.json` no protege sus propios ficheros (`fable_gate.py`, `fable-gate.json`, `settings.json`) | Observación de política | No hay regla explícita que lo exija |
| O-2 | Los `deny` de `settings.json` solo cubren Read/Write/Edit; `PowerShell(Get-Content *)` está en `allow` | Observación | La regla de no cargar datos descansa en disciplina; no probado en ejecución real |
| O-3 | Agentes «de solo lectura» (`independent-code-reviewer`, `review-adjudicator`) sin `tools:` | Observación | Prohibición solo en el prompt; el protocolo V2 ata la ronda a un digest |
| O-4 | El aviso de intérprete por defecto de los BAT va a stdout, no a `:log` | Observación, LOW | Fallo más probablemente ruidoso |
| O-5 | El job `test-windows` usa 3.12 y producción 3.14 | Observación | Ya descartado como defecto en una consolidación legacy; sin regresión demostrada |
| O-6 | El rc de `purge_artifacts.py` no se comprueba en BACKFILL_ALL | Observación | Best-effort documentado |
| O-7 | `logs/fable_gate.log` contiene un único `fallo inesperado (ValueError('too many values to unpack …'))` | NOT_VERIFIABLE | No se reprodujo con 13 comandos sintéticos |

## Descartes relevantes

- Push y líneas enteras, cuartos asiáticos (pricing, liquidación, pnl, peso en calibración): coherentes.
- ROI realizado: numerador y denominador comparten filas; doble liquidación protegida (DEDUP_KEY, identidad y lock).
- Kelly: finitud, banca ≤ 0, `min_edge` y cap correctos. `ev_flat` del gate es EV esperado, no ROI, según el pre-registro.
- Leakage de features: `rest_form` corta en `< ref_date`, y el backtest congela el estado por día. ML no está en el camino de producción.
- Secuencia SETTLE→generación: correcta (abortar sin generar). La guarda de árbol sucio funciona y el estado sucio actual queda fuera de su pathspec.
- Secretos: `.env` ignorado; `apiKey` redactada en errores; el único literal parecido está en un fixture de test del detector.
- Timeouts HTTP en todos los proveedores; reintentos 429/5xx con `Retry-After`.
- Prompts generados sin deriva (`sync_agent_instructions --check`: synchronized); skills y agentes de `model-routing.json` existen.

## Validaciones y comandos

| Comando | rc | Resultado | Clasificación |
|---|---|---|---|
| `ruff check src scripts tests` | 0 | All checks passed | OK |
| `mypy src` | 0 | 113 ficheros sin errores | OK |
| `python scripts/sync_agent_instructions.py --check` | 0 | synchronized | OK |
| `PYTHONPATH=src python -m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest-claude-20261015` | 1 | **3 failed, 3201 passed, 1 skipped in 3863.12s** | 3 × ENVIRONMENTAL_FAILURE (CLAUDE-017) |
| Los mismos 3 tests con basetemp fuera del repo | 0 | 3 passed in 7.29s | Confirma la causa ambiental |
| `gh run list` / `gh run view 38256027979` | 0 | CI rojo en 5 patas; pip-audit `skipped` | PRE_EXISTING_FAILURE (CLAUDE-002/003) |
| `git ls-remote --tags origin` / `git tag -l prereg*` | 0 | 0 remotos / 2 locales | CLAUDE-002/004 |
| `scratchpad/repro_a1.py` (sintético más agregado de `served_nhl.csv`) | 0 / 1 → 0 | home+away 0.8438; 320/335 < 0,95 | CLAUDE-001 |
| Revisión A: 21 ficheros de tests del núcleo | 0 | 584 passed | OK |
| Revisión B: tests focalizados de proveedores y cierre | 0 | 18 passed | OK |
| Revisión D: tests de gobernanza | 0 | 224 passed (basetemp fuera del repo) | OK |
| Revisión C: clon `--no-tags --depth 1` | 1 | 2 failed (tier_a_gap) | CLAUDE-002 |

`tests_initial`: 3201 passed, 1 skipped y 3 ENVIRONMENTAL_FAILURE en el working tree (HEAD 65368c8 más los cambios sin commit declarados).

## Plan priorizado y criterios de aceptación

1. **P1 CLAUDE-001:** corregir el consenso y el no-vig en NHL; pruebas de 2+1 casas; el operador decide el tratamiento de las filas del stream y del gate desde 2026-09. Escalado según `MODEL_ROUTING`: es un cambio en los parámetros de la evidencia del gate y debe revisarlo Fable antes del commit. Aceptación: suma 1 en filas nuevas y test de regresión.
2. **P1 CLAUDE-002:** test robusto (skip y `assert msg`), `fetch-depth: 0` y push de tags (operador). Aceptación: CI verde en `main`.
3. **P2:**
   - CLAUDE-003: pip-audit `if: always()` y fijado.
   - CLAUDE-004 y CLAUDE-005: push de tags y de commits tras CLAUDE-002.
   - CLAUDE-006: rc≠0 en fallos totales de `capture_close`.
   - CLAUDE-007: `failed_windows` en tenis y `results_trusted`.
   - CLAUDE-008: matcher PowerShell más test.
4. **P3:** CLAUDE-009 a CLAUDE-017, cada uno con la prueba indicada en su ficha.

## Riesgos residuales y limitaciones

- Cobertura parcial: `clv_gate`, `backtesting/engine.py` y `tuning.py`, la mayor parte de `evaluation/*`, `calibration/data.py` y `pergame.py`, `sports/adapters.py`, `goalie_backfill.py`, la mayor parte de `html_report.py`, y los CLIs de `scripts/` fuera de la cadena diaria.
- Los LOW procedentes de reproducciones del área B y A se revalidaron por lectura de código, no repitiendo la reproducción.
- No hay segunda opinión disponible todavía: el informe OpenAI en `pending` no se leyó, como exige la independencia.
- Los cambios sin commit de KI-073 no tienen verificación independiente.
- El efecto incidental en `logs/sqp.log` queda declarado arriba.
- No se ejecutaron BAT, pipelines, APIs externas ni pip-audit.
- Este diagnóstico no afirma rentabilidad ni ausencia de defectos fuera de lo cubierto.
