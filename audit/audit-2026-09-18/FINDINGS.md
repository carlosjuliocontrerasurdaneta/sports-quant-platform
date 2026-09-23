# Hallazgos consolidados — ronda `audit-2026-09-18`

Consolidación realizada el 2026-09-18 (12:20 UTC) por el coordinador
(`claude-opus-5`, sesión principal), que es también el autor del diagnóstico
Claude. **Hubo segunda opinión**: el auditor OpenAI entregó
`openai/REPORT.md` (sha256 `a593000e…db863`) y `openai/EVIDENCE.json`
(`88219eca…57af`) antes de que Claude iniciara su diagnóstico; Claude no los
leyó hasta fijar sus conclusiones (`claude/REPORT.md` `42c3467d…d2ab`,
`claude/EVIDENCE.json` `5f438b9b…9343`). Ambos informes declaran la misma
ronda y la misma base. Esta consolidación **no autoriza correcciones**.

Base: `59521643440213f6a7982b10e71d349a8d8dd088` (`main`, sincronizado con
`origin/main`). Working tree al inicio: 25 entradas, todas bajo `audit/`
(preparación de ronda). Línea base de diagnóstico: los IDs y estados de esta
tabla no se reescriben en remediación/verificación; el seguimiento va en
`STATUS.md`.

## Métricas

- Confirmados: **7** (HIGH 0, MEDIUM 4, LOW 3). P0: 0. P1: 0. P2: 4. P3: 3.
- Origen: exclusivo OpenAI 3, exclusivo Claude 4, ambos 0, coincidencia
  parcial 0. Los dos auditores recorrieron rutas distintas (OpenAI: gate,
  robustez de registros, vistas; Claude: calibración, controles operativos,
  cuota, hooks) y sus conjuntos son disjuntos: la falta de coincidencia no
  invalida ninguno; cada exclusivo se revalidó contra el código en esta fase.
- Descartados: 4 (2 de cada informe). No verificables: 5. Observaciones: 9.
- Ampliación en consolidación: AUD-002 incluye un segundo lector con el mismo
  defecto (`risk/degradation.py`) no citado por ningún auditor y verificado
  aquí, con consecuencia mayor que la del caso original.
- Validaciones (unión): suite completa 2191 passed / 1 skipped (Claude);
  306 tests focalizados (OpenAI); ruff 0 y mypy 0 (ambos); CI remoto
  **success** en HEAD (Claude; OpenAI sin `gh`); tareas programadas con
  último rc 0x0 (Claude; OpenAI sin acceso WMI).
- Cobertura: Claude 11 REVISADA / 6 PARCIAL / 1 NO_APLICABLE / 1
  NO_VERIFICABLE; OpenAI 16 PARCIAL / 2 NO_VERIFICABLE / 1 EXCLUIDA / 1
  NO_APLICABLE. Las áreas NO_VERIFICABLE de OpenAI (CI, tareas) quedan
  REVISADA por Claude; las de Claude (`.env`, causa de días sin run) siguen
  abiertas.

## Tabla consolidada

| ID | Alias fuente | Origen | Severidad | Confianza | Evidencia | Prioridad | Título | Archivos |
|---|---|---|---|---|---|---|---|---|
| AUD-001 | OPENAI-001 | exclusivo OpenAI (revalidado Claude) | MEDIUM | HIGH | REPRODUCED (OpenAI) + STATICALLY_VERIFIED (Claude) | P2 | `scripts/gate_status.py` evalúa OTRA regla (hit rate vs 0,5 sobre `pick_history`, EV = p_est − 1/cuota) y anuncia «PASAN EL GATE» sin relación con el criterio canónico (test pareado modelo vs mercado por evento, ventana post-pre-registro, EV plano, pestillo) | `scripts/gate_status.py:41-86,100`; `.claude/skills/clv-shadow-exit/SKILL.md:61`; contrato en `src/sqp/risk/prediction_gate.py` (`_usable`, `_independent_units`, `_decide`, `_apply_latch`) |
| AUD-002 | OPENAI-002 (+ ampliación) | exclusivo OpenAI, ampliado en consolidación | MEDIUM | HIGH | REPRODUCED (OpenAI, en memoria) + STATICALLY_VERIFIED (Claude, ambos lectores) | P2 | Un registro JSON válido con raíz no objeto (`[]`, `null`, número) rompe el default-deny: `load_prediction_gate` lanza `AttributeError` (ningún run_league genera; día sin picks, rc 1) y `load_degradation_registry` tiene el mismo patrón, pero su fallback en `run_all.py` lo llama de nuevo FUERA del `try`, abortando el run completo antes de la primera liga | `src/sqp/risk/prediction_gate.py:544-547`; `src/sqp/pipeline/daily.py:641`; `src/sqp/risk/degradation.py` (`load_degradation_registry`); `scripts/run_all.py:190-194` |
| AUD-003 | CLAUDE-001 | exclusivo Claude | MEDIUM | HIGH | STATICALLY_VERIFIED | P2 | El registro live de calibración contiene la clave sandbox `mlb_h2h_pergame` (promovida el 2026-08-23 por `promote_calibrators(keys=None)`); producción resuelve `mlb_h2h` y sirve el moneyline MLB en crudo mientras `health_check` (`calibration=True`, mercado «h2h_pergame»), el dashboard («En produccion: 4») y `Tareas.md:104` («staged») dicen lo contrario | `data/models/calibration_methods.json`; `data/models/promotion_log.csv:102`; `data/models/staging/calibration_methods.json`; `src/sqp/calibration/pergame.py:20-23,54-57`; `src/sqp/calibration/calibrator.py:745-790,976-991`; `src/sqp/monitoring/health.py:80-103`; `src/sqp/audit/html_report.py:259-275`; `Obsidian/Tareas.md:104` |
| AUD-004 | CLAUDE-002 | exclusivo Claude | MEDIUM | HIGH | STATICALLY_VERIFIED (estado del sistema) | P2 | El historial del Programador de tareas está deshabilitado (`Microsoft-Windows-TaskScheduler/Operational` `IsEnabled=False`): los días sin run 11, 15 y 16-09 (sin cabecera en `run_diario.log`/`settle_all.log`/`diario_completo.log`) no tienen causa diagnosticable; solo persiste `LastRunTime`/`LastTaskResult` | registro de eventos del sistema; `scripts/set_tasks_unattended.ps1`; `src/sqp/monitoring/health.py:220-260` (`pipeline_liveness` detecta, no explica) |
| AUD-005 | OPENAI-003 | exclusivo OpenAI (revalidado Claude) | LOW | HIGH | STATICALLY_VERIFIED | P3 | El log del run diario anuncia «habilitados para stake real» desde `decided` (pre-pestillo) tras `write_prediction_gate`, que aplica `_apply_latch`; un corte con test agotado o pestillo se anunciaría habilitado con `allowed=false` persistido. Además `evaluate_markets` se ejecuta dos veces por run | `scripts/run_all.py:296-313`; `src/sqp/risk/prediction_gate.py:428-470` |
| AUD-006 | CLAUDE-003 | exclusivo Claude | LOW | HIGH | STATICALLY_VERIFIED | P3 | La captura de cierre pide `h2h,spreads,totals` (15 créditos) también en tenis, donde el run diario solo genera `h2h` (5 créditos): 22 capturas de tenis en el log = 330 créditos frente a 110 | `src/sqp/pipeline/closing_capture.py:118`; `src/sqp/providers/odds_api.py:288`; `src/sqp/pipeline/daily.py:704`; `src/sqp/pipeline/budget.py:33-38` |
| AUD-007 | CLAUDE-004 | exclusivo Claude | LOW | HIGH | REPRODUCED | P3 | `check-secrets.sh` (`_targets.py --with-git` en cada `Bash`) re-escanea todo el `git status` y `ASSIGNMENT` marca código fuente citado (`self.<clave> = <clave>` + CRLF escapado) como secreto: aviso idéntico en >15 comandos de la sesión y en las líneas del informe que lo citaban | `.claude/hooks/check-secrets.sh`; `.claude/hooks/_secret_literals.py:8-12`; `.claude/hooks/_targets.py` |

Detalle completo (activación, problema, evidencia, esperado, observado, causa
raíz, consecuencia, corrección mínima, pruebas, aceptación, limitaciones) en
`openai/REPORT.md` (OPENAI-001..003) y `claude/REPORT.md` (CLAUDE-001..004).
Severidad y confianza no se promediaron: cada ID conserva las del informe
fuente, revalidadas por el coordinador contra el código de HEAD.

## Revalidación en consolidación

- AUD-001: leído `scripts/gate_status.py` completo. Confirmado que usa
  `data/processed/pick_history.csv`, `estimated_probability`, `result==win`
  frente a 0,5 y `mean(p − 1/cuota)`, sin ventana `VALIDATION_START`, sin
  unidad por evento, sin pestillo, y que su docstring presenta esas
  condiciones como «Condiciones del gate». La skill `clv-shadow-exit` lo
  recomienda como «consulta rápida del estado». Confirmado.
- AUD-002: `load_prediction_gate` hace `json.loads(...).get("markets")` dentro
  de un `try` que solo captura `OSError`/`JSONDecodeError`; `isinstance` se
  comprueba sobre `markets`, no sobre la raíz. `load_degradation_registry`
  es idéntico. En `run_all.py`, el monitor de degradación corre en `try`, pero
  el `except` llama a `paused_from_registry(load_degradation_registry(...))`
  sin protección: la misma raíz no objeto aborta `main()` antes de la primera
  liga. `clv.load_clv_gate` sí comprueba `isinstance(payload, dict)`
  (patrón correcto a reutilizar). Activación solo por edición/recuperación
  manual: `atomic_write_json` siempre escribe un objeto. Confirmado y ampliado.
- AUD-003: verificado el registro live y el de staging, `promotion_log.csv:102`,
  el docstring de `pergame.py`, `calibration_key` y la salida real de
  `health_check.py` (`mlb … calibration=True`). Confirmado.
- AUD-004: `Get-WinEvent -ListLog` → `IsEnabled=False`; agregados de logs.
  Confirmado como estado del control; la causa de las ausencias queda
  NOT_VERIFIABLE.
- AUD-005: `run_all.py` calcula `ok` desde `decided.itertuples()` obtenido
  ANTES de `write_prediction_gate` (que recalcula y aplica el pestillo).
  Confirmado. Activación no presente hoy (0/48 habilitados).
- AUD-006 y AUD-007: evidencia propia de Claude (log agregado; reproducción en
  sesión). Confirmados.

## Agrupación por causa raíz

- **Vistas y mensajes que no leen el veredicto canónico persistido**: AUD-001
  (script paralelo), AUD-005 (log pre-pestillo). Misma lección; correcciones
  separadas porque el consumidor y la prueba discriminante difieren. En la
  misma familia, informativas: OBS-C4 (`health_check` reporta modelos ML sin
  consumidor) y la parte de vistas de AUD-003.
- **Validación sintáctica sin validación de tipo en lectores de registros**:
  AUD-002 (dos lectores; un tercero, `clv.py`, ya lo hace bien).
- **Promoción sin distinguir claves sandbox**: AUD-003.
- **Controles cuyo estado no se registra**: AUD-004.
- **Parámetros de captura no alineados con los de generación**: AUD-006.
- **Alarmas que se aprenden a ignorar**: AUD-007 (misma clase que
  `discovery-coverage.md` documenta para el CI rojo).

## Discrepancias y descartes

- Ninguna discrepancia de severidad entre auditores (conjuntos disjuntos).
- OpenAI DISMISSED: (1) la divergencia de `gate_status` NO es bypass del gate
  del pipeline (`daily` carga la implementación canónica) — coincide con la
  revalidación; (2) los 52 errores iniciales de pytest fueron
  ENVIRONMENTAL_FAILURE de `basetemp` (WinError 5) y desaparecieron en un
  directorio propio — Claude no encontró residuo en `.codex-tmp/pytest` con
  el nombre canónico (suite completa 2191 passed con ese basetemp); se
  atribuye a contención concurrente entre ambas sesiones, no se reabre AUD-004
  de la ronda anterior.
- Claude DISMISSED: (1) «secreto» en `openai/EVIDENCE.json:315` (código
  fuente citado; AUD-007); (2) coincidencias del detector en
  `tests/test_audit_hooks.py` y `tests/test_portable_setup.py` (fixtures).
- OpenAI INFERRED (no confirmado, sin severidad): `train_calibration` ordena
  grupos de evento por `date` (día) y puede repartir eventos del mismo día a
  ambos lados del corte. Claude verificó que la unidad es el evento y que la
  columna es la fecha del partido; el cutoff de *disponibilidad* dentro del
  mismo día no se reconstruyó. Queda como NV-4.

## No verificables

- NV-1 Causa de los días sin run 11/15/16-09 (AUD-004).
- NV-2 Contenido de `.env` (por diseño en ambos auditores).
- NV-3 Coste real de spreads/totals en torneos de tenis (AUD-006).
- NV-4 Cutoff intradía en la partición temporal de `train_calibration`
  (INFERRED de OpenAI).
- NV-5 Concurrencia completa lectura-modificación-escritura del registro del
  gate (OpenAI): las escrituras son atómicas, pero `write_prediction_gate`
  lee `previous` fuera de un lock; no se ensayó un intercalado.

## Observaciones informativas

- OBS-C1 Gate: 48 cortes con `K=41`; umbral de re-pre-registro 50; 6 cortes
  son torneos de tenis (n máx. 110). Dos torneos más disparan el aviso.
- OBS-C2 Disponibilidad del host: 0–28 capturas/día de 48 posibles; una
  instancia de `CAPTURE_CLOSE.bat` suspendida ~9 h (cabecera 17-09 23:30,
  primera línea Python 18-09 08:39); 881/1.578 liquidadas sin cierre (55,8 %).
- OBS-C3 `.claude/.tests-pending` persiste entre sesiones; el subconjunto
  `not slow` del hook Stop tarda 489,8 s frente a 600 s de timeout (margen 18 %).
- OBS-C4 `models/ml_predict.py` y `*_moneyline_model.joblib` sin consumidor en
  el camino de picks; `health_check` los reporta como presentes.
- OBS-C5 `apply_calibration` ejecuta `structural_defect` en cada llamada.
- OBS-C6 B-02 heredado: acciones del CI sin pin a SHA (persistente).
- OBS-O1 (OpenAI) Una fila sin `implied_probability_novig` interpretable en
  graded y en candidates (agregado), sin stake positivo en 182 candidatas.
- OBS-O2 (OpenAI) Timestamps de logs sin normalizar a UTC.
- OBS-O3 (OpenAI) Las pruebas emiten al logger de fichero real
  (`logs/sqp.log`) durante `pytest`.

## Comparación histórica (ronda `audit-2026-09-16`)

- AUD-001..AUD-007 de aquella ronda: `STATUS.md` los cerró como
  verificados-corregidos o por decisión; ningún auditor reabre ninguno.
  Claude confirmó en HEAD `realized_roi_parts` como definición única
  (ex-AUD-002), HEAD autoconsistente y sincronizado (ex-AUD-003), sin residuo
  en `.codex-tmp` con nombre canónico (ex-AUD-004), aviso sin cableado de
  `execution.books` (ex-AUD-005), `--with-git` solo en escrituras para el
  marcador de tests (ex-AUD-006). OpenAI: ex-AUD-002 favorable, resto
  NOT_VERIFIABLE como cierre (no revalidó todos los criterios).
- Heredado B-02: persistente. CL-02: cerrado.
- Los 7 IDs de esta ronda son **nuevos**. Antecedente de AUD-001: la ronda
  del 2026-09-09 (revisión cruzada de Codex) corrigió el alpha caducado en el
  docstring de `gate_status.py` sin cuestionar la regla paralela;
  `.claude/memory/project-decisions.md:282` menciona una divergencia
  histórica del script (leído incidentalmente por OpenAI, declarado).
- Adyacente de la ronda anterior (pricing Normal con líneas de cuarto,
  ≤0,32 pp): no revalidado por ningún auditor.

## Limitaciones

Dos auditores con rutas disjuntas; ninguno ejecutó el run real, backfills,
`pip-audit` local, BATs ni `codex review`. Datos operativos solo por
agregados. `.env` y `logs/` no legibles por vía directa. Claude escribió
incidentalmente `data/output/pipeline_health.json` al ejecutar
`health_check.py`; OpenAI emitió líneas de prueba a `logs/sqp.log`. La
auditoría no demuestra rentabilidad ni ventaja predictiva; el gate de
predicción sigue en default-deny (0/48) y nada de lo aquí consolidado debe
cambiar ese estado sin el criterio pre-registrado.
