# Archivos modificados — Auditoría 2026-07-29/30

58 archivos modificados, 3 creados, 17 eliminados (duplicados verificados).
`git diff --stat`: **484 inserciones, 142 eliminaciones**.

Nota: 25 agentes, `ORCHESTRATOR.md`, `decision-engine.md`, `route-task.md` y
`settings.json` ya venían modificados por una sesión previa (trabajo del router de
modelo, sin commitear). Se marcan con † los que esta auditoría además tocó.

## Código de producción (`src/`)

| Archivo | Cambio | Hallazgo |
|---|---|---|
| `src/sqp/audit/report.py` | Helper `has_flag()` (pertenencia por token en `flags`) y su uso en `rank_candidates` y `consolidated_report`, en lugar de `flags == "shadow_mode"`. | B-01 |
| `src/sqp/pipeline/cleanup.py` | `_actionable` distingue flags informativos (`accuracy_mode`) de flags bloqueantes, en lugar de exigir `flags == ""`. Dirección conservadora: retiene más archivos. | B-01 (clase) |
| `src/sqp/pipeline/daily.py` | (1) `_accuracy_selected` exige `price_decimal > 1.0`; (2) `if stake <= 0: continue` en la rama accuracy; (3) `_warn_if_uncalibrated_accuracy()` nueva + llamada en `run_league`; (4) 3 escrituras a `atomic_write_csv`; (5) import de `atomic_write_csv`. | B-05, B-06, Q-01, D-04, D-08 |
| `src/sqp/pipeline/probabilities.py` | `_consensus_lines` descarta cuotas `<= 1.0` antes de la mediana. | B-13 |
| `src/sqp/config.py` | (1) Helper `_env_flag()` tri-estado con WARNING; (2) los 8 flags booleanos y sus 8 guardas yaml migrados; (3) `odds_api_key` con `repr=False`. | B-08, S-13 |
| `src/sqp/storage/starters.py` | `save()` descarta filas sin ningún abridor antes del upsert, con log del conteo. Import de logger. | D-01 |
| `src/sqp/providers/odds_api.py` | (1) `429` añadido a `_RETRY_STATUS`; (2) `self.requests_last = None` al inicio de `_get`. | D-05, D-06 |
| `src/sqp/features/common.py` | `_write_state` usa `atomic_write_csv`. Import. | D-09 |
| `src/sqp/features/mlb.py` | Las 2 escrituras de estado usan `atomic_write_csv`. Import. | D-09 |

## Scripts

| Archivo | Cambio | Hallazgo |
|---|---|---|
| `scripts/run_all.py` | `settings.bankroll = max(0.0, bal)` en lugar de asignar una banca negativa. | B-06 |
| `scripts/validate_claude_model_routing.py` | `import json, re, sys` → imports separados (único E401 del repo). | K-016 |

## Pruebas

| Archivo | Cambio |
|---|---|
| `tests/test_audit_2026_07_29.py` | **Nuevo.** 25 pruebas de regresión, una por hallazgo corregido: B-01 (4), B-05 (2), B-06 (1), B-08 (5), B-13 (2), D-01 (3), D-06 (1), Q-01 (3), más helpers. |
| `tests/test_claude_model_routing.py` | `test_full_audit_routes_to_fable_orchestrator` → `..._to_orchestrator` (esperaba `fable`). 2 pruebas nuevas: modelo no disponible y existencia de loops/support_agents. |

## Configuración, CI y empaquetado

| Archivo | Cambio | Hallazgo |
|---|---|---|
| `.github/workflows/ci.yml` | Step `mypy src` en la pata 3.12. | S-5 |
| `pyproject.toml` | `[tool.ruff] target-version` `py310` → `py311`. | S-10 |
| `Makefile` | `install` con `-c requirements.lock`; targets `types` y `check`. | S-11 |
| `Dockerfile` | `useradd sqp` + `USER sqp` antes del CMD. | S-7 |
| `.gitignore` | `.claude/hooks/__pycache__/` añadido. | K-016 |
| `.claude/hooks/check-secrets.sh` | 4 patrones (comillas, sin comillas, dos puntos YAML, `sk-`/`Bearer`) y exclusiones ampliadas. Verificado por ejecución: 5/5 positivos, 0 falsos positivos. | S-9 |

## Claude Code

| Archivo | Cambio | Hallazgo |
|---|---|---|
| `.claude/loops/quant/STATES.md` | **Nuevo.** Definición exacta de `PASS`/`DEGRADED`/`BLOCKED`/`DONE` por condiciones observables + tabla de umbrales de muestra tomados del código (no inventados) + registro de evidencia obligatorio. | K-003 |
| `.claude/loops/quant/*.md` (14) | Regla común nueva: cerrar declarando estado según `STATES.md`. | K-003 |
| `.claude/loops/quant/01-daily-prediction.md` | Reescrito: precondiciones (orden crítico SETTLE→RUN), inputs, comandos (`DIARIO_COMPLETO.bat` en lugar de `RUN_DIARIO_ALL.bat`), artefactos, criterios de salida propios, gate de API paga y de `shadow_mode`. | K-001, K-002, K-003 |
| `.claude/loops/quant/03-postgame-settlement.md` | Precondiciones, artefactos, criterios de salida, gate de API paga. | K-002, K-003 |
| `.claude/loops/quant/04-daily-audit.md` | Hit rate y `gap` por banda como métrica principal; ROI/CLV degradados a secundarios con la advertencia de que ROI 0.0 bajo shadow no es equilibrio. Artefactos y criterios. | K-003, K-010, B-10 |
| 10 agentes † (`00-principal-orchestrator`, `ml-engineer`, `calibration-auditor`, `leakage-detector`, `backtest-reviewer`, `risk-manager`, `sports-quant-auditor`, `feature-engineer`, `backend-architect`, `odds-market-auditor`) | `model: fable` → `model: opus`. | K-004 |
| `.claude/automation/model-routing.json` | 5 rutas `"model": "fable"` → `"opus"`. | K-004 |
| `.claude/automation/MODEL_ROUTING.md` | Fuente única de la política de modelos; documenta por qué `fable` no se usa. | K-004, K-014 |
| `.claude/automation/decision-engine.md` † | La política de modelos ya no se repite: enlaza a `MODEL_ROUTING.md`. | K-014 |
| `.claude/ORCHESTRATOR.md` † | `shadow_mode`, `pick_mode`, `accuracy_threshold`, `bankroll` añadidos literalmente a los gates de aprobación; enlace a la fuente única de política de modelos. | K-009, K-014 |
| `.claude/automation/autonomy-policy.md` | Mismos gates literales añadidos a "Approval required". | K-009 |
| `.claude/automation/runtime/current-task.md` | Reseteado al estado real. **Retirada la autorización de commit/push del 2026-07-14 sin caducidad.** Corregido `407/407` → cifra real. | K-006 |
| `.claude/CLAUDE.md` | (1) `DIARIO_COMPLETO.bat` como orquestador diario con el orden crítico explícito; (2) hit rate añadido a la separación obligatoria de métricas. | K-001, K-020 |
| `.claude/rules/betting-output-rules.md` | Hit rate observado vs prometido; advertencia de que no es una afirmación de rentabilidad. | K-020 |
| `.claude/agents/risk/risk-manager.md` | Umbral de probabilidad y cumplimiento por banda para `pick_mode: accuracy`. | K-019 |
| `.claude/skills/memoria-persistente/SKILL.md` | Reescrito: `.claude/memory/` como almacén canónico; regla de caducidad de autorizaciones. | K-005, K-006 |
| `.claude/skills/memoria-persistente/*.md` (8) | Stubs vacíos → punteros explícitos al archivo canónico. | K-005 |

## Documentación

| Archivo | Cambio | Hallazgo |
|---|---|---|
| `README.md` | (1) `# 198 tests` eliminado (no actualizado: se desactualiza siempre); (2) sección "Modo precisión" con las 3 advertencias verificadas; (3) descripción de salidas corregida (dependía de `pick_mode`). | K-017, K-018 |
| `Obsidian/Bitácora/2026-07-30.md` | **Nuevo.** Entrada de bitácora de la auditoría. | K-024 |
| `audit/latest/*` | **Nuevos.** 8 entregables. | — |

## Eliminados

| Ruta | Motivo |
|---|---|
| `Obsidian/` — 17 archivos con nombre mojibake + 1 directorio vacío | Duplicados **byte-idénticos** (sha256) de archivos versionados con nombre correcto. Verificado con script auditable que solo borra si existe pareja versionada idéntica; los 5 archivos sin pareja (`.obsidian/`, config del editor) se conservaron. Cero pérdida de información. |
| `.claude/hooks/__pycache__/` | Bytecode generado por el test que carga el hook vía `importlib`. Ahora ignorado. |

## NO modificado deliberadamente

- **173 archivos que `ruff format --check` reformatearía.** El proyecto no usa
  `ruff format` (el `Makefile` solo hace `ruff check`, que pasa limpio). Reformatear
  sería un refactor cosmético masivo sin beneficio verificable.
- `configs/default.yaml`: **ningún** parámetro productivo de riesgo, umbral,
  bankroll ni `shadow_mode` fue tocado.
- `.claude/settings.json` deny de `.env.*` (S-14): relajar un control de secretos es
  la dirección equivocada; queda como decisión humana.
- `MODEL_ROUTER_INTEGRATION.json`, `.claude/settings.local.json.backup-audit-20260623`,
  `.claude/skills/superpowers-main/`: no los creé yo; se señalan en `BACKLOG.md` en
  lugar de borrarlos.
- Datos históricos: ningún archivo de `data/` fue modificado.
