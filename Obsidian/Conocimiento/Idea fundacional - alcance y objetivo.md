---
tags: [conocimiento, origen, objetivo, alcance, calibracion, sqp]
creada: 2026-08-16
actualizada: 2026-08-16
---

# Idea fundacional — alcance y objetivo

> ⚠️ **DEROGADA COMO OBJETIVO (2026-08-16).** El objetivo del sistema es
> únicamente el enunciado sacrosanto de [[Objetivos y requisitos]]. Esta nota
> queda como **registro histórico del origen** y por su contraste contra el
> código; **no derivar de ella criterios, prioridades ni métricas rectoras**.

Texto fundacional de la **plataforma**, aportado por el operador el 2026-08-16
con la instrucción explícita de grabarlo *sobre piedra*. Complementa a
[[Prompt 191 - origen del modelo]]: aquel es el origen del **motor de MLB**;
este es el origen del **sistema completo** — qué ligas, qué mercados, qué se
optimiza y cómo debe auditarse a sí mismo.

Se transcribe íntegro y textual porque es **fuente**, no interpretación.

## Texto íntegro (operador, 2026-08-16)

> De la siguiente idea nació este proyecto:
>
> Diseñar un sistema cuantitativo profesional, modular, auditable y calibrado
> estadísticamente para MLB, NBA, NCAAB, NFL, NCAAF y NHL que permita determinar,
> con la mayor precisión posible y a partir de las estadísticas y métricas más
> relevantes para el análisis de cada juego, la probabilidad real de que un
> equipo gane el encuentro, la probabilidad real de que lo haga cubriendo un
> hándicap y la probabilidad real de que el total de anotaciones (totals)
> finalice por encima o por debajo de la línea establecida.
>
> El objetivo principal del proyecto es predecir con la mayor precisión posible
> cuál equipo ganará un partido, si lo hará cubriendo el hándicap y si el total
> de anotaciones superará o no la línea proyectada.
>
> Si bien métricas como el bankroll, el ROI y el edge son indicadores que el
> sistema debe calcular y evaluar, no constituyen el objetivo central. Lo que
> realmente se busca es obtener probabilidades objetivas y estadísticamente
> fundamentadas de acierto para los picks que el sistema genere en cada uno de
> esos tres mercados.
>
> Por ejemplo, si el sistema genera diez picks para una jornada, el objetivo es
> que alcance el mayor porcentaje de aciertos posible, idealmente 10 de 10. Sin
> embargo, además de generar predicciones, el sistema debe ser capaz de auditar
> automáticamente su propio desempeño. Al finalizar cada jornada, deberá revisar
> los resultados reales y elaborar una evaluación objetiva, indicando, por
> ejemplo, que de los diez picks generados, seis fueron acertados y cuatro
> resultaron incorrectos.
>
> A partir de esa evaluación, el sistema deberá identificar cuál de los tres
> mercados presenta la mayor tasa de acierto, analizar las causas de los picks
> fallidos y determinar si las pérdidas se debieron a una selección inadecuada de
> métricas, a parámetros incorrectamente configurados, a problemas de calibración
> del modelo o a cualquier otro factor identificable. El propósito es que el
> sistema mantenga un proceso continuo de autoevaluación, auditoría y
> recalibración, permitiéndole aprender de sus resultados y mejorar
> progresivamente la precisión de sus predicciones y la calidad de los picks que
> genera.

## Los cinco compromisos que fija

1. **Alcance:** seis ligas (MLB, NBA, NCAAB, NFL, NCAAF, NHL) y **tres mercados**
   (moneyline, hándicap, totals). No es un sistema de moneyline.
2. **El objetivo central es la precisión de la probabilidad**, no el dinero.
   Bankroll, ROI y edge se calculan y se evalúan, pero **no constituyen el
   objetivo**.
3. **Probabilidades objetivas y estadísticamente fundamentadas**, derivadas de
   las métricas relevantes de cada juego. Es la misma dirección que la corrección
   *predecir, no preciar* del 2026-08-15.
4. **Autoauditoría por jornada:** revisar resultados reales y emitir un balance
   objetivo de aciertos y fallos.
5. **Atribución de causa y recalibración continua:** qué mercado acierta más, y
   por qué falló lo que falló — métricas mal elegidas, parámetros mal
   configurados, miscalibración u otro factor identificable.

## Cómo convive con "ganar dinero es el fin" (2026-08-02)

> **CERRADO el mismo 2026-08-16 por el enunciado canónico y sacrosanto**
> ([[Objetivos y requisitos]]): estimar probabilidades es el **medio**, generar
> ganancias es el **único propósito**. Si esta nota y aquel enunciado parecen
> chocar, manda el enunciado. La tabla de abajo se conserva porque explica el
> matiz que sigue siendo cierto: lo que el sistema *optimiza* no es el dinero.

No hay contradicción si se separan los niveles, y conviene mantenerlos separados
de forma explícita:

| Nivel | Qué es | Cómo se mide |
|---|---|---|
| **Fin último** | Ganar dinero apostando (directiva 2026-08-02) | ROI realizado |
| **Objetivo del sistema** | Precisión de la probabilidad en los 3 mercados + autoauditoría | Brier, log loss, fiabilidad |

El dinero es la **consecuencia esperada** de la hipótesis fundacional
(probabilidades exactas → dinero), no la función que el sistema optimiza. De ahí
que las métricas rectoras sean contra la realidad y no contra el mercado — ver
[[Calibración]] y [[CLV y selección adversa]].

## Advertencia que forma parte de la piedra: "10 de 10" ≠ rentabilidad

El *"idealmente 10 de 10"* es la aspiración correcta **sobre la precisión**, pero
maximizar el porcentaje de aciertos **como criterio de selección** ya se
implementó y falló: `pick_mode: accuracy` (2026-07-28) elegía favoritos a cuotas
1.07–1.16, subía el hit rate y perdía dinero por construcción (breakeven 93,5 % a
cuota 1.07). Revertido por el propio operador el 2026-07-31 (`f6c2130`).

**Lectura correcta:** la precisión se persigue **estimando bien la probabilidad de
cada evento** (calibración), no **seleccionando los eventos fáciles**. Por eso el
hit rate se reporta siempre contra el breakeven por cuota, nunca absoluto.

## Estado de implementación al 2026-08-16

Verificado en código, no supuesto:

| Compromiso | Estado | Evidencia |
|---|---|---|
| 6 ligas, incl. NCAAB y NCAAF | **Cubierto** | `pipeline/budget.py:18`, `providers/odds_api.py`, `providers/espn_results.py` |
| 3 mercados | **Cubierto** | `pipeline/daily.py:554` pide `h2h,spreads,totals` |
| Balance de aciertos por jornada | **Cubierto** | `audit/patterns.py`, liquidación diaria |
| Mercado con mayor tasa de acierto | **Cubierto** | `pattern_breakdowns()` → `by_market` (moneyline/hándicap/totals) |
| Diagnóstico de miscalibración | **Parcial** | `audit/segments.py` compara `brier_model` vs `brier_market` por segmento |
| **Atribución de causa** (métricas vs parámetros vs calibración) | **Brecha abierta** | no existe como paso automático |

La última fila es lo que menos existe del texto fundacional, y es justamente el
mecanismo que lo haría un sistema que *aprende de sus resultados*.

## Cómo aplicarlo

Este texto manda sobre interpretaciones posteriores. Si una propuesta mejora el
ROI a costa de la precisión de la probabilidad, va **contra** la idea
fundacional. Y una medición negativa contra el mercado no juzga la predicción:
ver [[CLV y selección adversa]] y [[Prompt 191 - origen del modelo]].
