# Hallazgos consolidados — ronda `audit-2026-09-16`

Consolidación realizada el 2026-09-17 por el mismo agente que produjo el
diagnóstico Claude (`claude/REPORT.md`, `claude/EVIDENCE.json`). **No hubo
segunda opinión**: el auditor OpenAI no entregó `openai/REPORT.md`; dejó
únicamente `openai/reproduce.py` (sha256 `412b81d7…bf67`) con tres hipótesis
(`OPENAI-001..003`), que se trataron como `TOOL_DETECTED` y se revalidaron con
código propio. Esta consolidación no autoriza correcciones.

Base: `44e48f26045f734fc479a127a9eb35f776c6483c` + working tree sucio (57
entradas preexistentes). Línea base de diagnóstico: los IDs y estados de esta
tabla no se reescriben en remediación/verificación; el seguimiento va en
`STATUS.md`.

## Métricas

- Confirmados: 7 (HIGH 1, MEDIUM 4, LOW 2). P0: 0. P1: 2 (AUD-001, AUD-003).
- Descartados: 1 (OPENAI-003 como defecto de pipeline; reclasificado).
- No verificables: 3 (NV-1 logs, NV-2 `.env`, NV-3 suite `slow`).
- Observaciones informativas: 4 (OBS-1..4 en `claude/REPORT.md`).
- Cobertura: 12 áreas REVISADA, 6 REVISADA_PARCIALMENTE, 1 EXCLUIDA
  (Obsidian/docs), 1 NO_VERIFICABLE (`logs/`, `.env`). Matriz completa en
  `claude/REPORT.md`.
- Validaciones: suite rápida 1936 passed (basetemp propio), ruff 0, mypy 0,
  CI remoto verde (`a2ee66c`); comando canónico de pytest roto por residuo
  ambiental (AUD-004).

## Tabla consolidada

| ID | Alias fuente | Origen | Severidad | Confianza | Evidencia | Prioridad | Título | Archivos |
|---|---|---|---|---|---|---|---|---|
| AUD-001 | CLAUDE-001, OPENAI-001 | ambos (OpenAI sólo hipótesis en script) | HIGH | HIGH | REPRODUCED | P1 | Pricing de líneas de cuarto ignora la liquidación a medias: 7–13 pp de desviación, signo del EV invertido | `src/sqp/models/distributions.py:236-259`, `sports/adapters.py:107-123` |
| AUD-002 | CLAUDE-002, OPENAI-002 | ambos (ídem) | MEDIUM | HIGH | REPRODUCED | P2 | ROI realizado con tres definiciones incompatibles tras `half_win/half_loss` (backtests y dashboard) | `backtesting/roi_engine.py:411-430`, `audit/html_report.py:177-179`, `audit/report.py:276-280`, `settlement/runner.py:681` |
| AUD-003 | CLAUDE-003 | exclusivo Claude | MEDIUM | HIGH | REPRODUCED | P1 | HEAD no autoconsistente (depende de ficheros sin trackear; test roto) y divergente de `origin/main` (2 locales / 6 remotos) | commits `44e48f2`, `72d07d8`; `.claude/automation/{audit-workflow,loop-guardrails}.md`; `audits/prompts/*`; `tests/test_tennis_params.py` |
| AUD-004 | CLAUDE-004 | exclusivo Claude | MEDIUM | HIGH | REPRODUCED (ENVIRONMENTAL) | P2 | Residuo inaccesible `.codex-tmp/pytest/openai-20260916-retry` rompe `make test` / comando canónico | `.codex-tmp/pytest/` |
| AUD-005 | CLAUDE-005, OPENAI-003 (reclasificado) | coincidencia parcial | MEDIUM | HIGH | STATICALLY_VERIFIED | P2 | `execution.books` documentado como activable, nunca consumido por el pipeline (decisión registrada `9dfb4cc` no reflejada en el yaml) | `configs/default.yaml:150-163`, `pipeline/probabilities.py:368`, `pipeline/daily.py:890` |
| AUD-006 | CLAUDE-006 | exclusivo Claude | LOW | HIGH | REPRODUCED | P3 | Con árbol sucio, cualquier `Bash` de solo lectura arma el centinela de tests (suite completa en cada Stop) | `.claude/hooks/mark-tests-pending.sh`, `_targets.py` fuente 3 |
| AUD-007 | CLAUDE-007 | exclusivo Claude | LOW | HIGH | STATICALLY_VERIFIED | P3 | `feature_shadow.load_protocol` huella `ROOT` y `train` huella `--data-root` | `evaluation/feature_shadow.py:100,137,168` |

Detalle completo de cada hallazgo (activación, problema, evidencia, esperado,
observado, causa raíz, consecuencia, corrección mínima, pruebas, aceptación,
limitaciones): `claude/REPORT.md`, sección «Hallazgos confirmados», con los
IDs `CLAUDE-00n` ↔ `AUD-00n`.

## Agrupación por causa raíz

- **Contrato de liquidación a medias (AUD-MED-002, 2026-09-13) aplicado sólo en
  `settle.py`**: AUD-001 (pricing) y AUD-002 (ROI). Corregirlos por separado es
  legítimo (impacto y solución distintos), pero comparten el mismo origen y
  deben validarse juntos con un caso de línea de cuarto de extremo a extremo.
- **Presión del guard de árbol sobre el flujo de commits**: AUD-003.
- **Controles declarados sin estado/consumidor**: AUD-005 (config), AUD-006
  (hook con coste no medido).
- **Entorno de validación**: AUD-004.

## Discrepancias y descartes

- `OPENAI-003` afirmaba que el pipeline ignora `execution.books` como defecto.
  Verificado que es cierto y **deliberado** (`9dfb4cc`: «NO se cablea en
  daily.py»); se conserva sólo la contradicción entre yaml/`Settings` y el
  comportamiento (AUD-005). No se contradice la decisión registrada.
- No hubo discrepancias de severidad que promediar: un único informe fuente.

## Comparación histórica (ronda `audit-2026-09-13`)

Corregidos: AUD-HIGH-001 (con nuevo riesgo AUD-003), AUD-HIGH-002, AUD-MED-005,
B-01. Parciales: AUD-MED-002 (→ AUD-001/AUD-002), AUD-MED-007 (→ AUD-006).
Persistentes: B-02 (acciones CI sin pin), CL-02 (`wnba_totals_calibration_iso.joblib`).
Resuelto por diseño: B-08. Regresiones formales (`REG-`): ninguna emitida; la
verificación de aquella ronda no se ejecutó (`not_available`).

## Limitaciones

Un solo auditor; `logs/` y `.env` no verificables por permisos; suite `slow`,
`pip-audit`, BATs y `codex review` no ejecutados; áreas parciales declaradas
en la matriz. La auditoría no demuestra rentabilidad ni ventaja predictiva.
