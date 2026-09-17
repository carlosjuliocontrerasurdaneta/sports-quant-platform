# Revisión de Claude Code y Quant Loops — Auditoría 2026-08-04

La remediación estructural completa se hizo el 2026-08-04 por la mañana (commit
`2a293cb`). Esta pasada verifica su resultado por ejecución, no por lectura.

## Integridad referencial: VERIFICADA

Comprobado programáticamente contra `.claude/automation/model-routing.json`:

```
rutas totales: 24
loops inexistentes: ninguno
agentes referenciados inexistentes: ninguno
```

Los 13 loops cuantitativos (`01`–`13`) más el router `00` existen en
`.claude/loops/quant/`. Los 10 loops generales existen en `.claude/loops/`.

## Estados: VERIFICADO — `STATES.md` es sólido

`.claude/loops/quant/STATES.md` es fuente única de verdad y cumple lo exigible:

- **Definiciones exactas** de `PASS`, `DEGRADED`, `BLOCKED` y `DONE` por
  condiciones observables, no por juicio.
- **Precedencia explícita**: `BLOCKED` > `DEGRADED` > `PASS`; `DONE` es una
  elevación de `PASS` tras el verification gate.
- **Umbrales anclados al código**, no inventados en el loop: `n≥15`
  (`segments.py`), `min_n` 30 (`configs/default.yaml`), `AUTO_PROMOTE_MIN_N_VAL`
  (`calibrator.py`), 200/80 (`tuning.py`).
- **Separación `Status` (idle/active/closed) vs `Result`**, que era el defecto
  corregido esta mañana.
- **Registro de evidencia obligatorio** en `current-task.md`: comandos con
  códigos de salida, rutas de artefactos, métricas con su `n`.
- **Lenguaje obligatorio**: *"Un `PASS` nunca significa que el sistema sea
  rentable: significa que el loop se ejecutó y dejó evidencia."*

Los loops referencian este archivo en vez de redefinir el vocabulario. Correcto.

## Hallazgo: la regla de `STATES.md` se violó el mismo día que se escribió

`current-task.md` cerró la tarea de la mañana con `Result: PASS` mientras la
suite estaba en **5 failed** y ruff/mypy no se habían ejecutado. `STATES.md`
dice literalmente:

> Si no puede determinarse a partir de un artefacto o de la salida de un
> comando, el resultado es `BLOCKED`, nunca `PASS`.

Y define `PASS` exigiendo que "todas las validaciones requeridas se ejecutaron y
ninguna falló". El estado correcto habría sido `BLOCKED`.

**Conclusión:** el problema del sistema de loops no es la especificación, que es
buena, sino que **no hay nada que impida declarar un resultado sin la evidencia
que la propia especificación exige**. Es el hallazgo A-1 en su forma
automatizada. Ver `BACKLOG.md` B-1.

## Estructura de los loops: correcta pero incompleta

Estructura real verificada (leída, no inferida) en
`09-champion-challenger.md`, representativa del conjunto:

| Sección | Presente |
|---|---|
| Reglas comunes (autonomía, memoria, no promover, no usar información posterior al evento, presupuesto de iteraciones) | Sí |
| Objetivo | Sí |
| Criterio previo obligatorio (pre-registro de métrica, mejora mínima, muestra mínima) | Sí |
| Flujo con comandos concretos | Sí |
| Estados de salida | Sí, delegados a `STATES.md` |
| **Inputs explícitos** | **No** |
| **Artefactos producidos** | **No** |
| **Transición al siguiente loop** | **No** |

El pre-registro obligatorio es una salvaguarda real y bien puesta: sin métrica
primaria, mejora mínima y muestra mínima declaradas **antes** de ejecutar, el
loop no puede emitir `CANDIDATE_FOR_APPROVAL` y el resultado es `BLOCKED`. Eso
previene data snooping por construcción.

## Duplicación

El bloque "Reglas comunes" está duplicado literalmente en **14 archivos**. Una
regla que cambie exige 14 ediciones coherentes. No corregido en esta pasada:
esos 14 archivos se remediaron hace horas y reescribirlos hoy es churn de alto
riesgo sin beneficio verificable. Ver `BACKLOG.md` B-3.

## Límites de autonomía: VERIFICADOS

`autonomy-policy.md`, `ORCHESTRATOR.md` y las Reglas comunes de cada loop
prohíben de forma consistente: promover modelos o calibradores, cambiar riesgo,
apostar dinero, hacer deploy y publicar cambios sin aprobación humana explícita.
`calibration.auto_promote: false` en `configs/default.yaml` respalda la política
en código, no solo en prosa. Coherente.

`.claude/settings.local.json` está correctamente ignorado por git, igual que
`*.backup-*`. `.claude/settings.json` (trackeado) contiene solo el modelo y la
lista de permisos.

## Modelo principal: deriva resuelta

Ver `FINDINGS.md` A-2. Estado final: `claude-opus-5` en `settings.json`,
`MODEL_ROUTING.md`, `Registro de decisiones.md`, `project-decisions.md` y
`tests/test_claude_model_routing.py`. Candado a tres bandas: cambiar el modelo
obliga a tocar configuración, política y prueba.

**Decisión deliberada:** el test **no se aflojó** para aceptar un conjunto de
modelos. Era el único mecanismo que detectó esta deriva, y la deriva
config↔documentación es el fallo recurrente de este repositorio.

## Memoria

`.claude/memory/project-decisions.md` y `architecture-log.md` están al día. La
entrada de Fable 5 quedó marcada como SUPERSEDIDA en vez de reescrita: el
historial de decisiones conserva qué se decidió y por qué se revirtió, que es
justamente lo que hizo auditable el hallazgo A-2.

## Resumen

| Dimensión | Estado |
|---|---|
| Conectados (router → loops → agentes) | Sí, verificado |
| Versionados | Sí |
| Consistentes | Sí |
| Verificables (criterios observables) | Sí, vía `STATES.md` |
| Ejecutables | Sí |
| **Pendiente** | Inputs/artefactos/transición por loop; deduplicación de Reglas comunes; **control automático que impida declarar `PASS` sin evidencia** |
