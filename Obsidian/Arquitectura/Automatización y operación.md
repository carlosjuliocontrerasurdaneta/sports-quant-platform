---
tags: [operacion, scheduler, sqp]
creada: 2026-07-08
actualizada: 2026-09-09
---

# Automatización y operación

Producción vive en `C:\dev\3\sports-quant-platform` (repunte del scheduler 2026-07-14; antes `C:\dev\sports-quant-platform`, y antes OneDrive — las tareas legacy fueron eliminadas).

## Task Scheduler — 5 tareas (estado final 2026-07-08)

| Tarea | Frecuencia | Qué hace |
|---|---|---|
| `Diario_Completo` | diaria 11:00 | `DIARIO_COMPLETO.bat`: settle → run encadenado (orden obligatorio) |
| `Capture_Close` | **cada 30 min desde 07-14 PM** (antes cada hora; a los :00 y :30) | captura líneas de cierre → hace medible el CLV; desde 07-14 PM persiste el snapshot COMPLETO de la liga (no solo eventos con pick — el fetch ya estaba pagado) y encadena: pase de revalidación de precio (revoca picks cuyo edge desapareció), guard de abridores en béisbol (statsapi gratis) y observatorio de edge intradía (`intraday_edge_log.csv`, medición pura para decidir la #4 ofensiva). Gasto acotado por ligas-con-pick-inminente + cap diario 300 créditos + min_remaining 100. `revalidation:` e `intraday_scan:` en default.yaml, ver [[Bitácora/2026-07-14]] |
| `Backfill` | lunes 09:00 | resultados históricos (tenis incluido) |
| `Refresh_ML` | lunes 09:45 | reentreno/refresh de la ruta ML |
| `Validate_OOS` | mensual, día 1, 12:00 | validación out-of-sample |

**Reglas duras:**
- `StartWhenAvailable = True` en TODAS las tareas (recuperan ejecuciones perdidas).
- `DIARIO_COMPLETO.bat` es el **orquestador diario único** (restaurado 2026-07-08, commit `fa59ff2`); `LOOP_DIARIO.bat` quedó descartado definitivamente.
- Orden **settle → run** es obligatorio: el run diario sobrescribe `candidates_*.csv`, así que liquidar después perdería los picks pendientes.

## BATs del repo

`DIARIO_COMPLETO` (orquestador), `RUN_DIARIO_ALL`, `SETTLE_ALL`, `CAPTURE_CLOSE`, `BACKFILL_ALL`, `REFRESH_ML`, `VALIDATE_OOS`. Todos con chequeo de error por paso y rotación de logs (>5MB → `.1`).

## Comportamientos operativos a conocer

- Una liga con picks comenzados-pero-sin-liquidar se **auto-excluye** del run diario (evita doble exposición).
- Ante fallo transitorio de una liga, `run_all` archiva y limpia sus candidates (no muestra picks viejos como del día).
- Ligas fuera de temporada se omiten con WARNING (chequeo `/sports`, gratis); key inválido = ERROR.
- Guard de presupuesto de The Odds API en el run live; el gasto de créditos históricos siempre se autoriza a mano.
- Tests: `PYTHONPATH=src pytest tests/ -q`. CI en GitHub Actions (ruff + pytest, 3.11/3.12/3.13 + windows, pip-audit bloqueante).

## Revisión cruzada automática (Codex)

- Dos hooks en `.claude/settings.json`: `mark-crossreview-pending.sh` (`PostToolUse`, matcher `Edit|Write|Bash`) arma el centinela `.claude/.crossreview-pending`; `crossreview-on-stop.sh` (`Stop`) ejecuta `codex review` y devuelve `exit 2` — el turno no cierra hasta atender o **refutar** cada hallazgo.
- Ámbito vigilado, estrecho a propósito: `configs/`, `src/sqp/risk/`, `src/sqp/calibration/`. **Cada disparo es una llamada de pago**, por eso este hook no usa la red `--with-git` que sí usa `mark-tests-pending`.
- Alcance en cascada: `--uncommitted` (si queda algo sin commitear en el ámbito) → `--base <upstream>` → `--commit HEAD`. Las instrucciones del revisor viven en `AGENTS.md`, que Codex carga solo.
- Un fallo de entorno (cuota, 401, review interrumpida) **no** se presenta como hallazgos: encabezado distinto, `exit 0` y centinela repuesto para reintentarlo. Ver `KI-035`.
- Es la **Forma 3** de `docs/CLAUDE-CODEX-INTEGRATION.md`, la única que se activa sola. Las otras dos (flujo manual Opus→Codex y `/cross-review`) requieren invocación.

## Grafo de conocimiento del código (graphify)

- `graphify-out/` (gitignorado): grafo consultable del código (`graphify query/path/explain`), reporte y visualización HTML.
- Se auto-actualiza vía git hooks post-commit/post-checkout (AST local, sin costo de API).
- Exclusiones en `.graphifyignore` (`.claude/skills/`, `Obsidian/`). Paquete PyPI: `graphifyy` (con doble "y").
- Sección de uso para el asistente en `CLAUDE.md` raíz; hooks PreToolUse en `settings.local.json` (local por ruta de máquina).

Relacionado: [[Estado del proyecto]], [[Arquitectura/Arquitectura del sistema]].
