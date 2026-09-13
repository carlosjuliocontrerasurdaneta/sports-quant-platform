# Hallazgos — Auditoría integral 2026-09-10

Severidades e IDs según `.claude/skills/full-audit/references/evidence-findings.md`.
Estado de evidencia: `REPRODUCIDO` / `VERIFICADO_ESTÁTICAMENTE` / `INFERIDO` /
`NO_VERIFICABLE` / `DESCARTADO`. Sólo los dos primeros son **confirmados**.

Base: paquete `sports-quant-platform-local-optimization-20260910`, verificado
íntegro contra `BUILD_INFO.json` (654/654 hashes SHA-256, 0 divergencias) al
abrir y de nuevo antes de la Fase 4. **El árbol NO es un repositorio Git**
(`git rev-parse` → `fatal: not a git repository`), y es el **directorio de
producción**: las 5 tareas `SQP_*` del Programador apuntan aquí.

Suite de partida: **1929 passed, 1 failed, 1 skipped** (2.422,71 s), `ruff` y
`mypy` limpios. El fallo de partida se investigó y resultó ambiental (ver
AUD-MED-005).

> La ronda anterior (2026-09-08) se conserva completa en `audit/audit-20260908/`.
> `CLAUDE_CODE_REVIEW.md` y `QUANT_REVIEW.md` de este directorio pertenecen al
> ciclo 2026-09-06 y no se han reescrito.

---

## Incidente detectado durante la auditoría (fuera del catálogo de hallazgos)

**INC-20260910 — Producción sin `data/` ni `.env`, y run diario fallado.**
`SQP_Diario_Completo_Cdev` se ejecutó el 2026-09-10 a las 12:00:01 y devolvió
`Último resultado: 1`. Al abrir la auditoría, `data/` contenía **2 ficheros**,
ambos `.gitkeep`: sin históricos, sin modelos, sin calibradores, sin ledger, sin
`prediction_gate.json`. `.env` ausente. Hipótesis: el paquete se desplegó sobre
el directorio de producción y se llevó el estado no versionado, que es
precisamente lo que `.gitignore` excluye del ZIP. **Resuelto por el operador**
durante la sesión: restauró su copia (~2.900 ficheros y `.env`), verificado.
Relacionado con AUD-MED-019.

---

## Estado de los hallazgos

| ID | Sev. | Evidencia | Estado |
|---|---|---|---|
| AUD-HIGH-001 | HIGH | REPRODUCIDO | **corregido y validado conductualmente** |
| AUD-HIGH-002 | HIGH | REPRODUCIDO | **causa raíz ya corregida en código; cierre del ciclo NO EJECUTADO** (ver VALIDATION.md) |
| AUD-HIGH-003 | HIGH | VERIFICADO_ESTÁTICAMENTE | **corregido** (productor automático + candado) |
| AUD-HIGH-004 | HIGH | REPRODUCIDO | **corregido y verificado por mutación** |
| AUD-HIGH-005 | HIGH | REPRODUCIDO | **corregido** (código + test + dato contaminado retirado) |
| AUD-MED-001 | MEDIUM | REPRODUCIDO | **corregido** |
| AUD-MED-002 | MEDIUM | REPRODUCIDO | **corregido** |
| AUD-MED-003 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (documental) |
| AUD-MED-004 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (documental) |
| AUD-MED-005 | MEDIUM | REPRODUCIDO | **DESCARTADO tras Fase 4**: era ambiental (colisión de `--basetemp`) |
| AUD-MED-006 | MEDIUM | REPRODUCIDO | **reclasificado a AUD-HIGH-005** |
| AUD-MED-007 | MEDIUM | REPRODUCIDO | **documentado**; no corregible aquí (incompatibilidad numpy/3.14) |
| AUD-MED-008 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (cargador canónico único) |
| AUD-MED-009 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (2 skills alineadas) |
| AUD-MED-010 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (contrato declarado) |
| AUD-MED-011 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (4 tests nuevos) |
| AUD-MED-012 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (sidecar + rechazo + 3 tests) |
| AUD-MED-013 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** |
| AUD-MED-014 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** |
| AUD-MED-015 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **documentado** (restricción del ciclo) |
| AUD-MED-016 | MEDIUM | REPRODUCIDO | **corregido** (3 tests endurecidos) |
| AUD-MED-017 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (`shell=True` retirado ×2) |
| AUD-MED-018 | MEDIUM | VERIFICADO_ESTÁTICAMENTE | **corregido** (implementación canónica + 6 tests) |
| AUD-MED-019 | MEDIUM | REPRODUCIDO | **corregido** (documental; el incidente lo confirmó) |
| LOW (24) | LOW | VERIF./REPRODUCIDO | **corregidos**, salvo el pin de acciones de CI a SHA (requiere red) |

### Hallazgo nuevo, surgido durante la Fase 4

| ID | Sev. | Evidencia | Estado |
|---|---|---|---|
| AUD-MED-020 | MEDIUM | REPRODUCIDO | **corregido**: `snapshot_v2._run` heredaba `GIT_DIR`/`GIT_WORK_TREE` del entorno, así que el snapshot de la revisión cruzada podía tomarse del repositorio equivocado. Reproducido con `GIT_DIR` a ruta inexistente. |

## No verificables (sin cambio)

Estado del CI (sin `.git` ni remoto), `pip-audit` (requiere red), contenido de
`logs/` (regla `deny` de `settings.json`), aplicabilidad de `OPTIMIZATION.diff`,
explotabilidad real de AUD-MED-002 en producción, y toda métrica cuantitativa
viva (Brier, ECE, CLV, ROI): no se midió ninguna y ninguna se afirma.
