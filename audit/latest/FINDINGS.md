# FINDINGS — ronda `audit-2026-11-03`

Consolidación con **un solo auditor** (Claude). No hubo segunda opinión: el auditor OpenAI/Codex no estuvo disponible (MCP `codex` CONNECTION_CLOSED). Ningún hallazgo está confirmado por coincidencia entre auditores. Origen de todos: **exclusivo Claude (único auditor)**.

Base: `a5d186084e7bc5a42c055b420adcfa7a9a9b1ffe`. Informe fuente: `audit/latest/claude/REPORT.md` (hash en `MANIFEST.json`). El detalle completo de cada hallazgo (activación, esperado/observado, causa raíz, controles, pruebas y limitaciones) está en el informe fuente bajo el mismo número.

## Resumen

| Severidad | Confirmados |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 7 |
| LOW | 19 |
| **Total confirmados** | **26** |
| Inferidos / no verificables | 2 + lista §NV |
| Observaciones | 3 |

Prioridad: P1 = 1 (AUD-002) · P2 = 6 · P3 = 7 · P4 = 12.

## Tabla

| ID | Fuente | Sev. | Conf. | Evidencia | Prio. | Título | Archivo:línea |
|---|---|---|---|---|---|---|---|
| AUD-001 | CLAUDE-001 | MEDIUM | HIGH | REPRODUCED | P2 | La condición 2 del prediction gate (EV plano > 0) no puede cumplirse en mercados de 2 vías equilibrados | `src/sqp/risk/prediction_gate.py:306-336`; `src/sqp/pipeline/daily.py:995-1020` |
| AUD-002 | CLAUDE-002 | MEDIUM | HIGH | REPRODUCED | **P1** | El guard de árbol sucio deja días sin liquidar ni generar, sin reintento; se repetirá el 2026-11-03 | `DIARIO_COMPLETO.bat` (`:error_arbol`) |
| AUD-003 | CLAUDE-003 | MEDIUM | HIGH | REPRODUCED | P2 | `update_prediction_gate.py` escribe el registro con `--min-n`/`--alpha` no canónicos y gasta el test único | `scripts/update_prediction_gate.py:69-70,103-104`; `src/sqp/risk/prediction_gate.py:412,424,506-530` |
| AUD-004 | CLAUDE-004 | MEDIUM | HIGH | STATICALLY_VERIFIED | P2 | `validate_oos.py` descarta los parámetros de liga no tuneados en «frozen_train» y «family_default» | `scripts/validate_oos.py:79,81,262` |
| AUD-005 | CLAUDE-005 | MEDIUM (condicionado) | MEDIUM | STATICALLY_VERIFIED | P2 | Edge, Kelly y liquidación usan la mediana del consenso aunque la ejecución sea en Pinnacle | `src/sqp/pipeline/daily.py:933,961,979-983,1080`; `src/sqp/settlement/settle.py:149-153` |
| AUD-006 | CLAUDE-006 | MEDIUM | HIGH | REPRODUCED | P2 | `_append_log` borra el historial del log ante un error de parseo | `src/sqp/pipeline/revalidation.py:78` |
| AUD-007 | CLAUDE-007 | MEDIUM | HIGH | REPRODUCED | P2 | El health check no consigue leer las tareas programadas (timeout 30 s) | `src/sqp/monitoring/health.py:291` |
| AUD-008 | CLAUDE-008 | LOW | MEDIUM | STATICALLY_VERIFIED | P3 | Registro de calibración: read-modify-write sin lock; lectura fallida → `{}` | `src/sqp/calibration/calibrator.py:309-320,384-409` |
| AUD-009 | CLAUDE-009 | LOW | HIGH | STATICALLY_VERIFIED | P3 | El techo `K_REPREGISTRO` solo avisa; no bloquea cortes fuera del universo pre-registrado | `src/sqp/risk/prediction_gate.py:604-610` |
| AUD-010 | CLAUDE-010 | LOW | HIGH | REPRODUCED | P3 | El tipster clasifica B/A líneas que el motor de riesgo descarta | `src/sqp/evaluation/tipster.py:73-91,125` |
| AUD-011 | CLAUDE-011 | LOW | HIGH | STATICALLY_VERIFIED | P3 | `estimated_edge`/`min_edge` son EV condicionado a no-push | `src/sqp/pipeline/daily.py:961` |
| AUD-012 | CLAUDE-012 | LOW | MEDIUM | REPRODUCED | P3 | Backtest/walk-forward MLB usan el abridor almacenado, no el probable disponible | `src/sqp/backtesting/engine.py:76-79` (HEAD); `src/sqp/backtesting/roi_engine.py:451` |
| AUD-013 | CLAUDE-013 | LOW | MEDIUM | STATICALLY_VERIFIED | P3 | Gate intradía: cierre no posterior a la entrada y unidad no independiente | `scripts/research/intraday_gate_analysis.py:34-45`; `src/sqp/audit/intraday_gate.py:46,83-109` |
| AUD-014 | CLAUDE-014 | LOW | HIGH | STATICALLY_VERIFIED | P3 | Permisos: `gh pr merge` sin confirmación; deny de `.env` solo para Read | `.claude/settings.json` |
| AUD-015 | CLAUDE-015 | LOW | HIGH | REPRODUCED | P4 | Marcadores 0-0 de relleno en resultados NHL/NFL/NBA 2002-2004 | `src/sqp/providers/espn_results.py:216-221` |
| AUD-016 | CLAUDE-016 | LOW | MEDIUM | REPRODUCED | P4 | Snapshots de cuotas con filas exactamente duplicadas | `src/sqp/storage/odds_store.py:41-71` |
| AUD-017 | CLAUDE-017 | LOW | HIGH | STATICALLY_VERIFIED | P4 | Lectores JSON sin validación de raíz | `src/sqp/models/ml_train.py:81-90`; `src/sqp/storage/feature_store.py:167-170`; `src/sqp/evaluation/feature_shadow.py:299-303` |
| AUD-018 | CLAUDE-018 | LOW | MEDIUM | STATICALLY_VERIFIED | P4 | Lock: carrera al romper candado caducado | `src/sqp/storage/lock.py:72-120` |
| AUD-019 | CLAUDE-019 | LOW | MEDIUM | STATICALLY_VERIFIED | P4 | `_parse_events` aborta la liga tras pagar; créditos no descontados | `src/sqp/providers/odds_api.py:~237-270`; `src/sqp/pipeline/closing_capture.py:~150-160` |
| AUD-020 | CLAUDE-020 | LOW | HIGH | REPRODUCED | P4 | Calibración por cara sin renormalizar (`wnba_spreads` suma 1,0019) | `src/sqp/calibration/calibrator.py:1150-1157` |
| AUD-021 | CLAUDE-021 | LOW | MEDIUM | STATICALLY_VERIFIED | P4 | El gate excluye `half_win`/`half_loss` | `src/sqp/risk/prediction_gate.py:199` |
| AUD-022 | CLAUDE-022 | LOW | HIGH | STATICALLY_VERIFIED | P4 | Copias de `data/backups` en el historial del repo público | commit `18826e2` |
| AUD-023 | CLAUDE-023 | LOW | HIGH | STATICALLY_VERIFIED | P4 | `requirements.lock` sin hashes | `requirements.lock` |
| AUD-024 | CLAUDE-024 | LOW | HIGH | STATICALLY_VERIFIED | P4 | Acciones de GitHub fijadas por tag | `.github/workflows/ci.yml` |
| AUD-025 | CLAUDE-025 | LOW | MEDIUM | STATICALLY_VERIFIED | P4 | Agentes sin `tools:` y con `model: opus` fijo | `.claude/agents/*.md` |
| AUD-026 | CLAUDE-026 | LOW | HIGH | REPRODUCED | P4 | `american_to_decimal` acepta (−100, 100) | `src/sqp/markets/odds.py:22-27` |

## Puntos clave de los MEDIUM

- **AUD-001.** Reproducción sintética: 400 eventos, 400 victorias pareadas, p = 3,9e-121, `ev_flat = −0,0455` → `ev_no_positivo`. El código implementa fielmente el pre-registro del 2026-08-16; el defecto es del criterio y se corrige **solo** con re-pre-registro (Fable + operador). Conservador: no arriesga dinero, pero bloquea la salida del shadow y puede gastar el test único de un corte válido. Urgencia: `nhl|spreads` y `nhl|totals` estaban en n = 219 el 2026-11-01.
- **AUD-002.** Aborto real el 2026-11-02 12:04; árbol todavía sucio el 2026-11-03 10:01. El escape `SQP_SKIP_TREE_GUARD=1` existe pero no es la solución; la acción inmediata es del operador (el `git stash` está denegado al agente).
- **AUD-003.** Riesgo de gastar tests únicos por un uso manual del escritor; la ejecución diaria no lo activa.
- **AUD-004.** Solo afecta a la atribución del informe OOS mensual, no a producción.
- **AUD-005.** Latente: se activa el día que un corte salga `allowed: true`.
- **AUD-006.** Probabilidad baja; consecuencia: pérdida silenciosa de ≈16.000 filas del observatorio intradía.
- **AUD-007.** Monitorización degradada desde, al menos, el 2026-10-06.

## §NV — Inferidos y no verificables

- **NV-001 (CLAUDE-I01, INFERRED):** frescura de cuotas por respuesta, no por casa (`daily.py:779-786`).
- **NV-002 (CLAUDE-I02, INFERRED):** `OddsCache.put` no atómico (`providers/odds_cache.py:107-109`).
- No verificables: contenido de `.env`; barrido de secretos del historial por contenido; ejecución real de CI; CVEs de dependencias; `risk/degradation.py`, `risk/clv_gate.py`; liquidación de tenis; `models/` fip, park, team_scoring, blend, independent, ml_predict; recuperación desde backups; efecto en datos reales de AUD-001 y AUD-004.

## Observaciones (no defectos)

- OBS-001: el trabajo del portero NHL sin commit toca rutas del candado `fable_gate` sin FABLE-REVIEW de hoy (correcto mientras no se commitee).
- OBS-002: `.claude/CLAUDE.md` dice «12 skills quant» con bloque común; hay 19 con el bloque (sincronizado).
- OBS-003: tests de contrato y de hooks lentos frente al presupuesto del Stop hook; un timeout de 60 s en `test_audit_hooks.py` bajo carga (`ENVIRONMENTAL_FAILURE`).

## Descartes

Ver `claude/REPORT.md` §7: devig, liquidación de cuartos, Kelly, mecánica del gate, ausencia de lookahead, holdout de calibración, atomicidad de stores, secretos en ficheros versionados, deserialización segura, referencias de skills y orden liquidación → generación.

## Comparación histórica (con `audit-2026-10-18`)

- **Persistente en otra forma:** AUD-005 de la ronda anterior («la tarea diaria no reintenta», mitigado) → AUD-002 de esta ronda: la mitigación no cubre el aborto del guard.
- **Nuevo en otro consumidor:** el arreglo de AUD-009 anterior (CLV con cierre ≤ entrada) no se extendió al gate intradía (AUD-013).
- **Siguen corregidos** en lo revisado: AUD-003 (duplicados por `game_id` descartados al leer) y AUD-008 (líneas de cuarto previas al arreglo).
- **Sin regresión observada** en las áreas revisadas para el resto; no se revalidaron uno a uno.
- Todos los demás hallazgos de esta ronda son **nuevos**.

## Métricas

- Candidatos recibidos de especialistas: 31 (6 ODDS, 2 LEAK, 5 BT, 4 SEC, 6 OPS, 8 ARCH).
- Fusionados por causa raíz: SEC-02 + OPS-05 → AUD-014.
- Confirmados: 26. Inferidos: 2 (ODDS-05, ARCH-04). Pasados a observaciones: 2 (OPS-03, OPS-06).
- Revalidados por el coordinador contra el código: 6 de 7 MEDIUM (AUD-005 aceptado con la evidencia estática del especialista).
- Esta consolidación no autoriza ninguna corrección.
