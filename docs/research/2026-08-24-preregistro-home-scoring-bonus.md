# Pre-registro — corrección del sesgo de reparto del `home_scoring_bonus` (MLB)

**Fecha:** 2026-08-24. Escrito y commiteado **antes** de medir ningún candidato.
Deriva de la Fase 0 del pre-registro de mercados derivados
(`2026-08-24-preregistro-mercados-derivados.md`), que aprobó la marginal de
team_totals pero marcó un sesgo local sistemático.

## Hipótesis y su uso

La Fase 0 midió, walk-forward sobre 9.068 partidos MLB, que la marginal por equipo
sobreestima los Over del **local** en `+0.018 … +0.024` en las cuatro líneas y
subestima levemente los del **visitante** (`−0.012 … −0.019` en las altas). Es un
sesgo de **reparto** (demasiada λ en el local, poca en el visitante), no de nivel.

`home_scoring_bonus` (MLB = 0.10) suma λ **solo** al local
(`adapters.py:103`), así que es el sospechoso directo del sesgo de reparto.

**Uso de la decisión:** mejorar la marginal por equipo como prerrequisito de la
Fase 1 de team_totals. El cambio, si se aprueba, afecta también a los mercados
principales (h2h/spreads/totals), por lo que se mide su impacto ahí como
guardarraíl.

## Baseline y candidatos (frontera de configuración reversible)

Todos se miden con override de config vía CLI; el YAML/registry no se toca hasta
que haya aprobación. Baseline = producción actual.

| Id | λ_home | λ_away | efecto |
|---|---|---|---|
| **C0** baseline | `avg·(0.5+tilt) + 0.10` | `avg·(0.5−tilt)` | reparto sesgado, total +0.10 |
| **C1** suma cero | `… + 0.05` | `… − 0.05` | conserva la brecha, baja el total |
| **C2a** bonus 0.05 | `… + 0.05` | `…` | baja λ_home, total +0.05 |
| **C2b** bonus 0.00 | `… + 0.00` | `…` | sin bonus, total sin inflar |

C1 conserva la brecha local-visitante (corrige nivel, no reparto): predicción
explícita = **no** corrige el sesgo de reparto y empeora el visitante. C2a/C2b
atacan el reparto bajando λ_home sin tocar al visitante.

## Métrica primaria y umbral (fijados antes de medir)

- **Primaria:** `max` sobre los 8 cortes `(lado, línea)` de `|sesgo|` en
  team_totals, walk-forward, `n ≥ 300`. Baseline = **0.024**.
- **Mejora mínima aceptable:** `max|sesgo| ≤ 0.015` **y** reducción del sesgo del
  lado local a `|·| ≤ 0.010` en las cuatro líneas.
- **Guardarraíl de calibración:** ECE agregado `≤ 0.05`; skill sobre base-rate
  conservado (Brier motor `≤` base-rate en los 8 cortes).

## Guardarraíles de los mercados principales (no deben regresar)

Medidos con el arnés walk-forward existente (`walk_forward_backtest`) sobre MLB:

- **h2h:** Brier no empeora más de `+0.0010`.
- **spreads** (líneas ±1.5): Brier no empeora más de `+0.0010`.
- **totals** (7.5/8.5/9.5): Brier no empeora más de `+0.0010` **y** el `|sesgo|`
  de totals no aumenta (el 08-18 midió MLB 7.5 con sesgo total `+0.194`
  sobreestimando; bajar el bonus debería **reducirlo**, no agravarlo).

## Regla de decisión (fijada antes de medir)

- **CANDIDATO_PARA_APROBACIÓN** si un candidato cumple la métrica primaria y su
  umbral **y** ningún guardarraíl se excede. No se despliega: se propone.
- **RECHAZAR** en caso contrario; se mantiene C0 y se registra.
- **Ninguna promoción sin aprobación humana explícita.** Además, el working-tree
  de `main` es producción y la ventana del gate de predicción (2026-08-17) está
  abierta: desplegar dentro de la ventana mezclaría dos versiones del modelo en
  una validación pre-registrada (patrón KI-019). Por eso, aunque un candidato
  gane, la implementación en producción queda condicionada a decisión explícita
  sobre el momento (dentro vs. tras la ventana).

## Incertidumbre

`n ≈ 9.068` observaciones por corte de team_totals y `≈ 8.837` de mercado
completo. A ese `n`, `SE(sesgo) ≈ √(p(1−p)/n) ≈ 0.005`; diferencias de sesgo
`≥ 0.005` entre candidatos son distinguibles del ruido. Se reporta el sesgo
directo por corte, no un único agregado que oculte el patrón de reparto.

## Lo que NO promete

Reducir el sesgo de la marginal no crea edge en team_totals; es un prerrequisito
de calidad para que la Fase 1 mida edge sobre una probabilidad fiable. Tampoco se
promete mejora en los mercados principales: el objetivo ahí es **no regresar**.
