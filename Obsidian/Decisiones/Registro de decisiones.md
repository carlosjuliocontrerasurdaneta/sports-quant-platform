---
tags: [decisiones, sqp]
creada: 2026-07-08
actualizada: 2026-08-16
---

# Registro de decisiones

Fuente canónica con formato completo (razón, alternativas, consecuencias): `.claude/memory/project-decisions.md`. Aquí, las decisiones **vigentes que definen el sistema**, agrupadas por tema. Al tomar una decisión nueva relevante: registrarla allí Y reflejarla aquí + [[Bitácora]].

## Rumbo (sacrosanto)

- **2026-08-16 — Enunciado ÚNICO y SACROSANTO del objetivo.** Texto íntegro en [[Objetivos y requisitos]]: estimar probabilidades **pregame** para **todos** los partidos, mercados (`h2h`, `spreads`, `totals`) y deportes, **con un único e innegociable fin: ganar dinero** mediante las apuestas de los picks propios. Por instrucción expresa del operador, **toda formulación anterior del objetivo queda derogada** —incluidas las dos redacciones previas del mismo día, el texto fundacional de las seis ligas y la directiva del 08-02—; lo que quede de ellas es registro histórico, no norma. No se re-litiga ni se matiza.
  - **"Pregame"** acota el acto de estimar: excluye el in-play, incluye el re-precio intradía anterior al `commence_time`.
  - **Consecuencia:** deja **sin efecto** la parte de la decisión de dirección del 2026-08-05 que redefinía el sistema como *"instrumento de medición barato"* con shadow mode indefinido. El sistema existe para generar picks que generen ganancias. El resto de aquella decisión (no abrir cuentas, no invertir en amplitud de modelado hasta tener una fuente de información nueva) sigue en pie como táctica, no como identidad del proyecto.
  - **No reactiva** `pick_mode: accuracy` (perdía por construcción, `f6c2130`) ni convierte al mercado en input del modelo. El fin se persigue **estimando bien**, no seleccionando eventos fáciles.

## Operación y riesgo

- **2026-08-17 — El GATE DE PREDICCIÓN sustituye al de CLV como regla de salida por mercado.** Criterio pre-registrado en `docs/research/2026-08-16-preregistro-regla-de-salida.md`, escrito antes de implementar. Un (liga, mercado) lleva stake real solo si **(1)** su modelo PURO bate al mercado en test de signo pareado fuera de muestra (n ≥ 300 no empatadas, p < 0,05) **y (2)** su EV a stake plano es positivo. `prediction_gate.enabled: true`, `clv_gate.enabled: false` — el de CLV se sigue calculando como evidencia pero ya no decide.
  - **Por qué:** el CLV mide rendimiento contra un mercado, no veracidad de la predicción, y dejó de ser métrica rectora el 08-15. Su gate llevaba vacío desde julio: una puerta que nadie puede cruzar equivale a no tener puerta.
  - **Fuera de muestra:** solo cuentan partidos posteriores al pre-registro. **El día de entrada en vigor niega todos los mercados** — es lo correcto, no un fallo: apostar por un hallazgo post-hoc es el error de KI-019.
  - **Precedencia:** pausa → mercado incompleto → edge implausible → shadow → predicción → CLV.
  - **Invariante vigente:** al menos una de las tres barreras (shadow, predicción, CLV) debe estar activa. Lo vigila `test_production_yaml_never_leaves_capital_unguarded`.

- **2026-08-16 — SHADOW MODE LEVANTADO** (`shadow_mode: false`), por decisión explícita del operador. Registrado aquí porque el test candado `test_production_yaml_never_leaves_capital_unguarded` lo exige antes de aceptar el cambio.
  - **Riesgo de capital el día del cambio: cero.** El gate de CLV por (liga, mercado) está cableado DEBAJO de shadow (`_zero_stake_flag`, `pipeline/daily.py:373`) y es default-deny; las 24 entradas de `data/bets/clv_gate.json` están en `allowed: false`. Verificado sobre el registro completo: 24 mercados a stake 0, **0 con stake real**.
  - **Lo que cambia:** el gate de CLV pasa a ser la barrera única, visible y vinculante; el flag de los reportes pasa de `shadow_mode` a `clv_gate`.
  - **⚠️ A vigilar:** un mercado pasa a llevar dinero real **automáticamente** cuando la auditoría diaria le escriba `allowed: true` (CLV mediano > 0, n ≥ 30). Ya no media aprobación humana. Para recuperarla: `clv_gate.enabled: false` + registro curado a mano, o volver a `shadow_mode: true`.
  - **Invariante que sustituye al candado viejo:** nunca pueden estar `shadow_mode: false` **y** `clv_gate.enabled: false` a la vez — eso dejaría la banca expuesta a todo candidato sobre `min_edge`. El test ahora vigila eso, no el flag.
  - **Incoherencia abierta:** la barrera que manda es de **CLV**, y el CLV dejó de ser métrica rectora el 2026-08-15. La regla de salida por mercado sigue siendo la vieja y no está alineada con el objetivo vigente.

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

- **Modelo principal de Claude Code** (2026-08-24): `claude-fable-5` autorizado por decisión humana explícita para la conversación principal, supersede `sonnet` (2026-08-18), que había superseduo `claude-opus-5` (2026-08-04) y este a `claude-fable-5` ese mismo día. **Solo cambia el modelo interactivo de `settings.json`**; el escalón de rutas (`model-routing.json default`) sigue en `sonnet` para trabajo normal ("Prefer Sonnet"), y los subagentes permanecen en Opus/Haiku. Candado de tres vías (`settings.json`, `MODEL_ROUTING.md`, literal del test) realineado a `claude-fable-5` en el mismo commit. El id previo `"Fable 5"` de `settings.json` era inválido; corregido a `claude-fable-5`.
- **Routing y loops de apoyo** (2026-08-04): el hook cubre los 13 loops cuantitativos; un solo loop conserva la propiedad de la tarea y los loops de apoyo anexan evidencia sin sobrescribir `current-task.md`.
- **Obsidian como segundo cerebro** (2026-07-08): esta bóveda es la fuente central de conocimiento; cada cambio relevante se refleja aquí (regla en `CLAUDE.md`). Ver [[Metodología de documentación]].
- **Skills de Claude Code consolidados** (2026-07-13): un solo meta-skill acotado a arquitectura; análisis por deporte → `quant-*`; multi-rol → `sports-analytical-system` solo explícito; operaciones sensibles con skill propio (`review-calibration`, `clv-shadow-exit`) para que promoción de calibradores y evaluación shadow-exit usen siempre los mismos criterios. Ver [[Bitácora/2026-07-13]].
