# Resumen ejecutivo — Auditoría integral 2026-08-02

Auditoría solicitada por el operador el 2026-08-02. Sustituye el contenido de
`audit/latest/` de la auditoría anterior (2026-07-29/30, conservada en el
historial git). Alcance: código, configuración, dependencias, seguridad,
operación, documentación, `.claude`/Quant Loops. `data/`, `historical/`,
`logs/` y `exports/` NO se escanearon (regla permanente del proyecto); la
dimensión de datos se auditó a nivel de código, esquemas y health check.

Commit base: `1dba6b0` · Rama: `main` · Python 3.14.4 · Sin commit realizado.

## Estado general

**BUENO, con una brecha documental significativa (corregida en esta sesión).**
La línea base ya era verde en todas las puertas técnicas: 581 tests, ruff
limpio, mypy limpio (88 archivos), pip check limpio, compileall limpio. La
auditoría anterior (2026-07-29/31, 24 correcciones) dejó el código en buen
estado; los 10 commits posteriores llevan cada uno tests propios y validación
registrada en el mensaje.

## Hallazgo principal

El revert de `pick_mode: accuracy` → `edge` (commit `f6c2130`, 2026-07-31,
decisión del operador) **no se propagó a ninguna documentación**: README,
`Obsidian/Estado del proyecto.md`, `Tareas.md`, la bitácora y la memoria del
asistente seguían afirmando que el modo precisión estaba activo en producción.
Cualquier lector (humano o agente) habría operado sobre un estado falso del
sistema. **Corregido**: 5 documentos sincronizados con la realidad
(`configs/default.yaml` línea 72: `mode: edge`).

## Directiva estratégica registrada

Durante la sesión el operador fijó el objetivo rector definitivo, textual:
**"El fin del sistema es ganar dinero, eso escríbelo sobre piedra. Es
sacrosanto."** Registrado en `.claude/memory/project-decisions.md`,
`Obsidian/Estado del proyecto.md`, la bitácora del día y la memoria persistente
del asistente. Supersede el pivot a hit rate del 2026-07-27. Nota de honestidad
obligatoria: es el objetivo, no un logro — no hay edge demostrado a la fecha
(shadow activo, gate de CLV vacío, OOS −5.32% en la regla edge/Kelly).

## Mejoras realizadas (8 correcciones, 1 de código)

1. `src/sqp/models/ml_train.py` (`_register`): un `registry.json` corrupto se
   descartaba y sobrescribía en silencio; ahora se respalda como
   `registry.json.corrupt-<ts>` y se loggea WARNING. Test TDD (rojo→verde).
2. `README.md`: modo precisión reetiquetado "disponible, NO activo (revertido
   2026-07-31)", con la razón económica y las columnas de breakeven.
3. `Obsidian/Estado del proyecto.md`: snapshot 2026-08-02, modo EDGE activo,
   objetivo sacrosanto al frente.
4. `Obsidian/Tareas.md`: 2 tareas del modo precisión marcadas obsoletas, revert
   registrado en completadas, tarea nueva por las filas sin liquidar.
5. `Obsidian/Bitácora/2026-08-02.md`: creada (auditoría + directiva).
6. `.claude/memory/roadmap.md`: enlaces muertos a docs eliminados retirados.
7. `.claude/automation/runtime/current-task.md`: tarea zombi "in-progress"
   desde el 07-29 cerrada; estado real registrado.
8. `.github/workflows/ci.yml`: comentario obsoleto (">=3.10" → ">=3.11").

## Riesgos principales vigentes

- **87 filas servidas pendientes de liquidar fuera de la ventana de scores**
  (health check WARN: brasileirao 73, mlb 12, tenis 2). Sin backfill+settle no
  se gradúan nunca y sesgan la muestra de auditoría (supervivencia). Requiere
  decisión del operador (settle consume cuota del API). Comandos en BACKLOG.md.
- **Sin ventaja predictiva demostrada**: sistema ≈ break-even u OOS negativo;
  gate de CLV vacío. La calidad del software no es validez predictiva.

## Preparación

- **Shadow: PREPARADO** (ya opera así; medición completa: CLV con filtro de
  frescura, monitor de degradación, diagnóstico por segmentos, breakeven por
  cuota desde `f6c2130`).
- **Dinero real: NO PREPARADO.** Ningún (liga, mercado) pasa el gate de salida
  (mediana CLV > 0 con n≥30, allow-list default-deny).

## Conclusión

El repositorio queda verificado en verde (VALIDATION.md), con la documentación
re-sincronizada con la realidad operativa y el objetivo rector grabado en
piedra. No se realizó ninguna acción que requiriera autorización: sin commit,
sin push, sin cambios de riesgo/modo/umbrales/bankroll, shadow intacto.
