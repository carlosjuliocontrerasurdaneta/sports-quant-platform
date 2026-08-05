# Backlog — Auditoría 2026-08-04

Lo que no se corrigió, por qué, y qué hace falta para cerrarlo.
Esfuerzo: S (< 1 h) · M (1–4 h) · L (> 4 h).

## Requiere decisión humana

### B-0 · Liquidar las 54 filas servidas pendientes
- **Prioridad:** alta · **Esfuerzo:** S · **Riesgo:** bajo
- **Dependencia:** cuota del API de The Odds API (el settle la consume).
- chile 42, tennis_atp_canadian_open 12. Health check en WARN.
- Es la misma clase que M-01 (cerrado el 08-02) pero son instancias nuevas: el
  fallback desde `data/historical/` no las cubre. **No puedo confirmar** si es
  falta de backfill o ausencia de vendor de resultados para esas ligas sin
  ejecutar el backfill.
- **Criterio de aceptación:** `scripts/health_check.py` → OK (0/0), o las filas
  anuladas con flag explícito y la razón registrada.
- **Decisión necesaria:** autorizar backfill (gratis) y settle (consume cuota).

### B-2 · Borrar `claude-loops-remediation-20260804.patch`
- **Prioridad:** baja · **Esfuerzo:** S · **Riesgo:** bajo
- Verificado residuo: `git apply --check` falla en todos los hunks porque ya
  está aplicado; su contenido está en el commit `2a293cb`.
- **No lo borré**: es untracked, por tanto irrecuperable con git, y no lo creé.
  Mitigado añadiendo `*.patch` a `.gitignore`.
- **Decisión necesaria:** confirmar el borrado.

### B-9 · Commit de esta auditoría
- **Prioridad:** alta · **Esfuerzo:** S
- 14 archivos modificados + los 7 entregables regenerados. Sin autorización de
  commit vigente.
- **Decisión necesaria:** autorizar `git commit` (y si procede, push).

## Alta prioridad

### B-1 · Control automático que impida declarar un resultado sin evidencia
- **Prioridad:** alta · **Esfuerzo:** M · **Riesgo:** bajo
- **Causa que lo motiva:** tres afirmaciones falsas de estado en tres días
  (`pick_mode` 07-31 sin documentar, "suite verde" y "ruff/mypy no instalados"
  el 08-04). `current-task.md` cerró en `PASS` violando la regla explícita de
  `STATES.md`. La regla existe; nada la hace cumplir.
- **Propuesta:** un test o hook que valide `current-task.md` cuando
  `Result: PASS` — exigir al menos un comando con su código de salida y una ruta
  de artefacto, según los 8 puntos del "Registro de evidencia" de `STATES.md`.
- **Criterio de aceptación:** un `current-task.md` con `Result: PASS` y sin
  bloque de comandos ejecutados hace fallar la suite.
- **Por qué no se hizo ahora:** es una funcionalidad nueva, no una corrección;
  merece diseño propio y no debe mezclarse con las correcciones de esta pasada.

## Media prioridad

### B-3 · Deduplicar "Reglas comunes" de los 14 loops
- **Prioridad:** media · **Esfuerzo:** M · **Riesgo:** medio
- Bloque idéntico repetido en 14 archivos; cambiar una regla exige 14 ediciones
  coherentes.
- **Propuesta:** extraer a `.claude/loops/COMMON_RULES.md` y que cada loop lo
  referencie, igual que ya hacen con `STATES.md`.
- **Por qué no se hizo ahora:** los 14 archivos se remediaron el mismo día
  (`2a293cb`); reescribirlos horas después es churn de alto riesgo. Conviene
  dejar asentada la remediación anterior.

### B-4 · Completar la estructura de los loops
- **Prioridad:** media · **Esfuerzo:** L · **Riesgo:** bajo
- Falta en todos: **inputs explícitos**, **artefactos producidos** y
  **transición al siguiente loop**. Lo demás (propósito, precondiciones vía
  criterio previo, comandos, validaciones, estados, evidencia, stop conditions,
  acciones que requieren aprobación) ya está.
- **Criterio de aceptación:** cada loop declara qué lee, qué escribe y a qué
  loop entrega.
- **Dependencia:** hacerlo después de B-3, para no editar dos veces.

### B-5 · Guard de cuotas degeneradas `price_decimal = 1.0`
- **Prioridad:** media · **Esfuerzo:** S · **Riesgo:** bajo
- Heredado de la auditoría 07-24. Snapshots históricos con precio 1.0 (visibles
  por los warnings de vig M-16). Decidir si el guard va en ingestión
  (`odds_api._parse_events`) o en lectura (`load_closing_odds`).
- **Criterio de aceptación:** líneas con precio ≤ 1.0 descartadas con log, y un
  test que lo demuestre.

## Baja prioridad

### B-6 · `ruff format` como estándar del proyecto
- **Prioridad:** baja · **Esfuerzo:** S (aplicar) · **Riesgo:** medio (diff masivo)
- `ruff format --check .` reformatearía 192 de 209 archivos. El CI no lo
  ejecuta, así que hoy no es un estándar.
- **Decisión necesaria:** o se adopta (y entonces se aplica en un commit propio
  aislado, y se añade al CI), o se documenta explícitamente que no se usa.
  El estado actual —herramienta disponible, no adoptada, no documentada— es el
  peor de los tres.

### B-7 · `pip-audit` local
- **Prioridad:** baja · **Esfuerzo:** S · **Riesgo:** bajo
- El CI lo ejecuta de forma bloqueante contra `requirements.lock`; localmente no
  se ejecutó en esta pasada. No puedo confirmar el estado de vulnerabilidades
  desde esta sesión.

### B-8 · Perf: `load_closing_odds` concatena todos los meses
- **Prioridad:** baja · **Esfuerzo:** M · **Riesgo:** bajo
- Heredado de la auditoría 07-12. Filtrar por rango de meses relevante cuando el
  histórico crezca.

## Fuera del alcance del repositorio

- **Verificar las 6 tareas del Task Scheduler de Windows.** No puedo confirmarlo
  desde el repositorio; requiere inspección del sistema operativo.
- **Auditar el contenido de `data/`, `historical/`, `logs/`, `exports/`.**
  Bloqueado por regla permanente del proyecto y por permisos `deny`.
