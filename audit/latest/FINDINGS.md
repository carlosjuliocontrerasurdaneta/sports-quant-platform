# FINDINGS — ronda `audit-2026-09-22-r2`

Consolidación con **un solo auditor** (Claude, `claude-opus-5-5`). **No hubo segunda opinión**: no hay auditor OpenAI en esta ronda y el MCP `codex` falló al conectar. El informe fuente es `audit/latest/claude/REPORT.md`; sus hashes están en `MANIFEST.json`. La ronda anterior (`audit-2026-09-22`) está preservada íntegra en `audit/audit-2026-09-22/` (11/11 sha256 idénticos).

Base: `main@9fa276a` con el árbol de trabajo **sucio**, que incluye la remediación sin commit de r22. Esta línea base no se reescribe en fases posteriores.

## Hallazgos confirmados

| ID | Origen | Sev. | Conf. | Evidencia | Prio | Resumen | Ubicación |
|---|---|---|---|---|---|---|---|
| `AUD-001` | CLAUDE-001 | HIGH | HIGH | `REPRODUCED` | **P0** | La guarda de árbol limpio abortará la ejecución de producción del **2026-09-23 12:00** antes de liquidar: 6 ficheros de código sin commit (remediación r22). Día sin liquidación ni picks | `DIARIO_COMPLETO.bat:60-74,296-308` |
| `AUD-002` | CLAUDE-002 | HIGH | HIGH | `REPRODUCED` | P1 | Los escritores del gate de predicción y del monitor de degradación tratan un registro ilegible como vacío: se reabren tests de entrada gastados, se desarman pestillos y el gate falla abierto hacia stake real | `risk/prediction_gate.py:456-458,573-590`; `risk/degradation.py:173-188,257-264` |
| `AUD-003` | CLAUDE-003 | MEDIUM | HIGH | `STATICALLY_VERIFIED` | P1 | La remediación de `AUD-001` (r22) contradice el pre-registro del 2026-09-04: hasta 50 cortes es tolerancia pre-registrada. El nuevo aviso ordena re-pre-registrar dentro de esa banda | `risk/prediction_gate.py:463-489`; `docs/research/2026-09-04-preregistro-multiplicidad-del-gate.md:124-127` |
| `AUD-004` | CLAUDE-004 | MEDIUM | HIGH | `REPRODUCED` | P1 | `.claude/skills/full-audit/` revertida hoy, sin commit, a `8952755` (2026-09-03): 3 pruebas de contrato en rojo y la skill desconectada de `audit-workflow.md` | `.claude/skills/full-audit/{SKILL.md,references/*}` |

Métricas: 4 confirmados (2 HIGH, 2 MEDIUM), 0 inferidos con entidad propia, 4 no verificables acotados, 6 descartes y 1 candidato de limpieza (`CLN-001`). Detalle completo, causa raíz, corrección mínima y criterios de aceptación: `claude/REPORT.md` §4.

## Revalidación de la ronda anterior (`audit-2026-09-22`)

| ID r22 | Estado | Nota |
|---|---|---|
| `AUD-007` | verificado-corregido (en el árbol, sin commit) | Suite 570 s frente al autoacotado de 1080 s |
| `AUD-001` | **reabierto (premisa)** | → `AUD-003` de esta ronda |
| `AUD-008` | persistente, fuera del repositorio | El MCP `codex` sigue caído |
| `AUD-002`, `AUD-003`, `AUD-004`, `AUD-005`, `AUD-006` | verificado-corregido (en el árbol, sin commit) | Ver `claude/REPORT.md` §8 |

`AUD-004` de r18 (KI-054, historial del Programador): **persistente**.

## Descartes

`OPTIMIZATION.diff`/`BUILD_INFO.json` (instantánea deliberada), grading de `team_totals` por fecha (correcto), rc 267014 de `Dashboard` (tarea interactiva terminada), fixtures del detector de secretos, 150 picks vencidos (estable) y lenguaje de las salidas (sin promesas de beneficio).

Consolidar no autoriza correcciones.
