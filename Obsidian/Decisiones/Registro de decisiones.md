---
tags: [decisiones, sqp]
creada: 2026-07-08
actualizada: 2026-08-04
---

# Registro de decisiones

Fuente canónica con formato completo (razón, alternativas, consecuencias): `.claude/memory/project-decisions.md`. Aquí, las decisiones **vigentes que definen el sistema**, agrupadas por tema. Al tomar una decisión nueva relevante: registrarla allí Y reflejarla aquí + [[Bitácora]].

## Operación y riesgo

- **SHADOW MODE global** (2026-07-03, `fe9ef84`): picks stake-0 hasta que CLV mediano positivo + gate de Brier lo levanten. La decisión más importante vigente.
- **Gate de CLV por (liga, mercado)** (2026-07-08, `bc27252`): salida del shadow es POR MERCADO, default-deny, ≥30 apuestas con CLV mediano > 0. Ver [[Conocimiento/CLV y selección adversa]].
- **Exposición en dos capas** (2026-06-28): cap diario por liga + cap global; escalado proporcional (no re-selección).
- **Banca dinámica por ledger** (2026-06-22): balance = inicial + PnL de `settled_*.csv` + ajustes manuales; sin store paralelo.
- **DIARIO_COMPLETO.bat orquestador único** (2026-07-08, `fa59ff2`): tras el incidente de borrado de BATs; orden settle→run obligatorio.

## Modelado

- **Disciplina OOS para activar cualquier cosa** (transversal): señales, parámetros y calibradores solo ON si baten al baseline fuera de muestra. Ver [[Conocimiento/Señales por deporte]].
- **Penalización de EV por desacuerdo modelo-mercado** (2026-06-21): `p_eff = p − penalty/d` alimenta edge y Kelly; validada OOS (ROI −0.74%→+0.37%, mitad de exposición). Es control de daños load-bearing, NO tocar a la ligera.
- **max_plausible_edge 0.075** (2026-06-22): edges crudos >7.5% son sobreconfianza marcada, no oportunidad.
- **Config sobre código**: overrides por liga en `ratings.yaml`; borrar el YAML = rollback.

## Calibración

- **Train ≠ promote** (2026-06-30; reafirmado 2026-08-04): staging automático y promoción humana por defecto (`auto_promote: false`). La función automática queda disponible solo como opt-in aprobado. Ver [[Conocimiento/Calibración]].
- **Entrenar sobre distribución de servicio** (2026-07-01, `d39f975`): `settled_*.csv`, no pick_history anclado a cierre.
- **Método por grupo `auto`** (2026-06-23): cada (liga, mercado) usa su mejor calibrador validado OOS.

## Datos

- **Raw preservado, append-only, game_id en la clave** (2026-06-12): doubleheaders preservados; dato faltante = fila excluida, nunca inventada.
- **Escritura atómica + unión de columnas** en settled/odds (2026-06-21/07-01): auto-sana esquemas viejos, nunca desalinea.
- **ESPN como vendor de resultados** (gratis, no oficial): parsers defensivos; slugs solo verificados empíricamente.

## Documentación

- **Modelo principal de Claude Code** (2026-08-04): `claude-fable-5` autorizado por decisión humana para la conversación principal; los subagentes permanecen en Opus/Haiku y se prueban por separado.
- **Routing y loops de apoyo** (2026-08-04): el hook cubre los 13 loops cuantitativos; un solo loop conserva la propiedad de la tarea y los loops de apoyo anexan evidencia sin sobrescribir `current-task.md`.
- **Obsidian como segundo cerebro** (2026-07-08): esta bóveda es la fuente central de conocimiento; cada cambio relevante se refleja aquí (regla en `CLAUDE.md`). Ver [[Metodología de documentación]].
- **Skills de Claude Code consolidados** (2026-07-13): un solo meta-skill acotado a arquitectura; análisis por deporte → `quant-*`; multi-rol → `sports-analytical-system` solo explícito; operaciones sensibles con skill propio (`review-calibration`, `clv-shadow-exit`) para que promoción de calibradores y evaluación shadow-exit usen siempre los mismos criterios. Ver [[Bitácora/2026-07-13]].
