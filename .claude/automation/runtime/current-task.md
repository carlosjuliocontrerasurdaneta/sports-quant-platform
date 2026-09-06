# Current Task

Status: closed
Result: PASS
Primary loop: `audit.md` → `bugfix.md`
Skills: `full-audit` (fases 0–3) → `audit-remediation` (fases 4–5) → `bugfix` (KI-032, KI-036)
Iteration: 1 / 1
Owner: sesión principal (`claude-opus-5`), sin delegación
Date: 2026-09-06

## Objective

Auditoría integral del repositorio y, tras aprobación explícita por lote,
corregir: los ocho confirmados del informe propio, **KI-032** (HIGH de la
auditoría independiente de Codex) y **KI-036** (opción (b)).

## Resultado

| | Inicio | Final |
|---|---:|---:|
| pytest | 1547 passed / 0 failed / 1 skipped | **1593 / 0 / 1** |
| ruff, mypy | exit 0 | exit 0 |
| CI de `main` | **ROJO** (75 runs previos + el del 2026-09-05) | **VERDE** (run 34060292683) |
| issue `ci-rojo` | #1 abierto | cerrado con causa raíz |

11 commits en `main`, todos empujados y con CI verde. 10 defectos corregidos:
8 del informe propio + KI-032 + KI-036. +46 tests.

`PASS` y no `DEGRADED`: todos los comandos requeridos terminaron en 0, las
validaciones específicas de cada hallazgo se ejecutaron, y los artefactos están
escritos y son legibles. Las limitaciones que hacían `DEGRADED` al informe
intermedio (`logs/` y `.env` excluidos, Dockerfile sin construir) siguen vigentes
pero pertenecen al **alcance de la auditoría**, no al de las correcciones
aprobadas, y están registradas en `audit/latest/BACKLOG.md` y `known-issues.md`.

## Escalado de modelo

**No se escaló a `claude-fable-5-1` ni se delegó en subagentes.** Las dos
decisiones dudosas, declaradas:

- **AUD-MED-002** (puerta de promoción de calibradores): toca un gate, pero no
  diseña criterio ni mueve umbral — `min_n_val` sigue en 30. Cierra un agujero
  del guard existente, con el fallo reproducido antes de tocar nada.
- **KI-032** (`bankroll.py`, ruta del dinero): la vía obvia habría contradicho
  una decisión registrada (`test_un_push_con_pnl_vacio_no_dispara_la_guarda`),
  que sí es clase de escalado. Se evitó yendo a la fuente: `settle.py:92` grada
  los cuatro estados con número, así que la discriminación correcta es por tipo
  de movimiento y la decisión registrada queda intacta. Sin conflicto, nada que
  escalar.

## Cambio de comportamiento en producción

**Entra en vigor en el run de las 15:00 UTC del 2026-09-07.** Con `src/`,
`scripts/`, `configs/` o algún `.bat` modificado sin commitear, `DIARIO_COMPLETO`
aborta antes de liquidar y el health check lo reporta como etapa `guard_arbol`.
Escape para recuperación: `set SQP_SKIP_TREE_GUARD=1`.

## Siguiente decisión del operador

1. **KI-033** — cinco hallazgos de Codex sin tocar, dos HIGH: pérdida de
   escrituras concurrentes en la liquidación, y el prediction gate contando
   varias líneas del mismo partido como ensayos independientes.
2. **KI-034** — autorizar la lectura de `logs/validate_oos.log`. La validación
   OOS lleva fallada desde el 2026-09-01 y no se reintenta hasta el 2026-10-01.
3. **KI-035** — el hook de revisión cruzada presenta errores de infraestructura
   bajo el encabezado de hallazgos.
4. **B-4** — ~205 MB de residuo ignorado por git, pendiente de autorización.
5. Dos ficheros sin commitear a propósito: `auditoria-integral-codex.md`
   (modificado por un Codex externo durante la sesión; prohibido commitearlo sin
   autorización expresa) y `audit/model_vs_market_20260906.md` (del operador).
   Los `model_vs_market_2026082*.md` anteriores sí están versionados.
