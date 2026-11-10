# Auditoría de los prompts deportivos: informe ejecutivo

**Fecha:** 2026-11-10.

**Alcance:** los 21 prompts de `C:\dev\Prompts` (familia `PROMPT_191_*`), contrastados con `sports-quant-platform` en `main` @ `d982fd0`.

**Encargo:** el del operador del 2026-11-10, con 14 puntos y 10 entregables. Este fichero es el entregable 10.

## Etiquetas

Cada hallazgo lleva una de estas cuatro etiquetas:

- **[COMPROBADO]**: tiene cita `fichero:línea`.
- **[INFERENCIA]**: razonamiento técnico.
- **[HIPÓTESIS]**: no comprobado.
- **[RECOMENDACIÓN]**.

## Cómo se hizo

- **Fase 1:** seis agentes Sonnet en paralelo, uno por familia de deporte. Cada uno leyó completos sus prompts y el código relevante, y escribió un informe por prompt y otro por familia.
- **Fase 2:** dos revisiones Fable (`claude-fable-5-1`) verificaron contra el código lo que se elevó a hallazgo transversal y escribieron los documentos 04 a 10. Sonnet escribió el inventario y la matriz.
- **Lo que no se ejecutó:**
  - ningún script de medición;
  - ningún pre-registro: «el modelo manda», el portero NHL y los demás siguen sin mirar;
  - ningún cambio de código ni de configuración.
- **Lo que no se pudo verificar:**
  - `.env`: lectura denegada, así que no se sabe si `MARKET_SHRINK` tiene un override en producción;
  - el reglamento 2026 que citan los prompts.

## Hallazgos principales

### Los prompts

1. **[COMPROBADO] Los 21 prompts son independientes del mercado.**
   - Todos congelan las probabilidades antes de consultar cuotas.
   - Las líneas de hándicap y total solo se usan como umbral a evaluar, que es legítimo.
   - Quedan tres matices de redacción que conviene cerrar:
     - cláusulas condicionales en Serie A:21 y Ligue 1:19;
     - no se prohíbe explícitamente optimizar hiperparámetros contra el mercado (EPL:27, MLB:14);
     - LaLiga:152 habla de «mercado de fichajes».

   Detalle en [07](07-independencia-del-mercado.md).

2. **[COMPROBADO] Los prompts son especificaciones metodológicas sólidas, pero no ejecutables.**
   - Comparten la misma estructura de unas 21 fases, aunque no un texto común: entre dos prompts coinciden como mucho unas 11 líneas.
   - Casi todos los coeficientes quedan «a estimar» y no hay umbrales numéricos para declarar un modelo VALIDADO.
   - Como cada prompt tiene más de 100 grados de libertad, hay un riesgo alto de sobreajuste si se implementan tal cual (riesgo R8 en [05](05-informe-de-riesgos.md)).

3. **[COMPROBADO] Hay defectos concretos.** La lista completa está en los informes individuales, en [04](04-auditoria-matematica.md) y en los informes de familia.
   - **MLB v2:** fija `NB_k = 0,15`, que da poca dispersión frente al 3,8 medido por la plataforma, y su `HomeAdj` subestima la localía.
   - **WTA:154:** la fórmula es tautológica.
   - **Bundesliga:** conserva restos de los prompts de hockey y de QB.
   - **Masa truncada:** la tolerancia varía de 1e-4 a 1e-6 según el prompt.
   - **NCAAB:** etiqueta mal el punto de equilibrio con push.

4. **[COMPROBADO] Hay dos líneas de versiones sin reconciliar.**
   - Los 21 prompts de `C:\dev\Prompts` son v1.0, salvo el de MLB, que es v2.0.
   - `docs/prompts/`, que está en el repositorio, tiene seis motores v3 distintos.

   Detalle en [01](01-inventario.md).

### La plataforma

5. **[COMPROBADO] La plataforma estima sin el mercado, pero decide con él** (riesgo R1, crítico).
   - **Estimación:** adaptadores, features, calibradores y el tuning por resultados no leen cuotas, y la probabilidad pura se guarda en `model_probability`.
   - **Decisión:** la probabilidad que selecciona, dimensiona y se muestra es `(1−s)·cal(p) + s·fair` con `market_shrink: 0.5` (`configs/default.yaml:17`, `src/sqp/pipeline/probabilities.py:303-306`). El stake se recorta además según la distancia entre modelo y mercado (`uncertainty_penalty: 0.35`).
   - Esto incumple el principio del operador en la capa de decisión y publicación.

6. **[COMPROBADO] Tres parámetros de junio de 2026 se eligieron por el ROI realizado sobre cuotas** (riesgo R2, crítico).
   - `park_bound: 0.10` en MLB (`configs/leagues/ratings.yaml:25-30`). Es el único de los tres que entra en la probabilidad del modelo, a través de λ.
   - `max_plausible_edge` y `uncertainty_penalty`, que solo afectan a la decisión.
   - Los parámetros activados desde septiembre (descanso NBA, tilt NHL, abridor MLB) se eligieron por log loss frente a resultados, con pre-registro. La práctica ya cambió; los de junio son herencia.

7. **[COMPROBADO] El monitor de degradación mide la mezcla, no el modelo** (R4). Compara la probabilidad mezclada con el mercado y pausa según el ROI realizado.

8. **[COMPROBADO] La plataforma implementa una parte pequeña de lo que piden los prompts.**
   - Fútbol: Poisson/Dixon-Coles.
   - Baloncesto y fútbol americano: Elo con margen y total modelados como dos Normales independientes, sin distribución conjunta, sin key numbers, sin prórroga y sin empate en la NFL.
   - Tenis: Elo escalar, sin superficie ni cadena de Markov.
   - Faltan xG, ritmo y eficiencia, lesiones, EPA, el bullpen y las eliminatorias de UCL/UWCL.
   - Hay piezas parciales en MLB (abridor y parque) y en NHL (portero, inactivo).

   Detalle en [03](03-matriz-comparativa.md).

9. **[INFERENCIA] Posible doble localía en el fútbol.** Se suma `elo_home_adv` y además `home_scoring_bonus 0,15` en λ local. El arreglo a suma cero ya fue rechazado por su pre-registro del 08-24; el problema sigue abierto como pregunta de modelo.

10. **[COMPROBADO] Cumplir el principio tiene un coste medido** (R9).
    - El modelo puro aporta información condicional ≈ 0 frente al consenso.
    - Con `market_shrink 0`, el ROI de la selección cayó de −3,02 % a −10,85 % en la medición del 08-26.
    - Esto no invalida el principio: indica que la mejora tiene que venir del modelo deportivo, no de la mezcla.

## Decisiones recomendadas

Lo que se puede hacer ya, sin tocar configuración ni pre-registros:

1. **[RECOMENDACIÓN] Candados automáticos del principio** (P1, P2, P8 y P9 de [09](09-principios-fundamentales.md); §5 de [06](06-arquitectura-recomendada.md)):
   - un test de fronteras de importación: la capa deportiva no puede importar `providers.odds_api`, `storage.odds_store`, `markets.*` ni `risk.*`;
   - un test de columnas: ninguna columna de mercado puede entrar en la estimación ni en la calibración;
   - un test de que `model_probability` es independiente de `fair`;
   - un test de que ningún override de `ratings.yaml` se justifica por ROI.
2. **[RECOMENDACIÓN] Congelar y versionar la probabilidad pura.** Añadir `prediction_id` (SHA-256), `frozen_at`, `model_version` y `params_hash` al stream servido, sin cambiar ninguna probabilidad, y separar `estimate_league` (sin cuotas) de `price_league` con una prueba de identidad byte a byte.
3. **[RECOMENDACIÓN] Aplicar el protocolo de validación sin cuotas** de [10](10-protocolo-de-validacion.md):
   - walk-forward con corte as-of sobre el registro congelado;
   - log loss, Brier y ECE;
   - MAE, RMSE y CRPS de marcador, que hoy faltan;
   - baselines independientes;
   - el mercado al final y solo como evaluación externa.
4. **[RECOMENDACIÓN] Añadir una columna paralela `brier_model_puro`** en el registro de degradación, solo como medición.
5. **[RECOMENDACIÓN] Cerrar los tres matices de redacción de los prompts** y reconciliar las dos líneas de versiones (v1.0/v2.0 y v3).

Lo que necesita una decisión del operador:

6. **Cumplir el principio en producción** (`market_shrink` y `uncertainty_penalty`).
   - Depende de la medición pre-registrada «el modelo manda» (`docs/research/2026-08-26-preregistro-el-modelo-manda.md`). Se ejecuta una sola vez, cuando haya unos 3.402 eventos, hacia finales de noviembre de 2026, y no se debe mirar antes.
   - Después de esa medición, también depende del pre-registro de peso del mercado por segmento, hacia marzo de 2027.
   - Ninguna de estas auditorías cambia la configuración.
7. **Volver a validar `park_bound` por log loss frente a resultados.** Es la única contaminación de mercado dentro del modelo; necesita su propio pre-registro.
8. **Fuentes de datos nuevas para los escalones avanzados:**
   - box scores de ESPN para ritmo y eficiencia;
   - saque y resto en tenis;
   - EPA en NCAAF sin CFBD;
   - xG y alineaciones en fútbol.

## Próximos pasos de modelo (pre-registrables)

Están en [08](08-plan-de-optimizacion.md). Cada escalón exige una mejora empírica según el protocolo 10.

1. **Distribución conjunta de margen y total** (Normal bivariante o bootstrap de residuos), con σ por mercado, en baloncesto y fútbol americano.
   - Ataca la sobreconfianza en 14 de 24 cortes, que incluye los seis spreads.
   - Solo se acepta si mejora los tres mercados a la vez.
2. **Ritmo × eficiencia para los totales de baloncesto,** empezando por `wnba/totals`. Ese corte ordena al revés, tiene el peor Brier y ya está en pausa.
3. **Fuerza ofensiva y defensiva log-lineal con decaimiento en fútbol,** como challenger del Elo más `home_scoring_bonus`.
   - Antes: `tune_ratings.py` de `dc_rho` y `elo_home_adv` en las 8 ligas que heredan el default de su familia.

## Documentos

| # | Entregable | Fichero |
|---|---|---|
| 1 | Inventario | [01-inventario.md](01-inventario.md) |
| 2 | Informes individuales (21) y de familia (6) | [individual/](individual/), [familias/](familias/) |
| 3 | Matriz comparativa | [03-matriz-comparativa.md](03-matriz-comparativa.md) |
| 4 | Auditoría matemática | [04-auditoria-matematica.md](04-auditoria-matematica.md) |
| 5 | Informe de riesgos | [05-informe-de-riesgos.md](05-informe-de-riesgos.md) |
| 6 | Arquitectura recomendada | [06-arquitectura-recomendada.md](06-arquitectura-recomendada.md) |
| — | Independencia del mercado (§7 del encargo) | [07-independencia-del-mercado.md](07-independencia-del-mercado.md) |
| 7 | Plan de optimización | [08-plan-de-optimizacion.md](08-plan-de-optimizacion.md) |
| 9 | Principios fundamentales | [09-principios-fundamentales.md](09-principios-fundamentales.md) |
| 8 | Protocolo de validación | [10-protocolo-de-validacion.md](10-protocolo-de-validacion.md) |
| 10 | Informe ejecutivo | este fichero |

## Discrepancias entre fases, ya resueltas

- **`scoring_half_life_days` de WNBA.** En la fase 1 se señaló como elegido «contra el mercado». La fase 2 verificó que `tune_market_param` puntúa sobre una línea de referencia fija con el resultado del marcador, sin medir el rendimiento frente al mercado vivo. No cuenta como optimización contra cuotas en el sentido de R2, pero queda como matiz en [05](05-informe-de-riesgos.md).
- **`uncertainty_penalty`.** Algunos informes de la fase 1 la describen como «solo desinfla el edge». Lo exacto es que reduce el stake en función del desacuerdo con el mercado: es decisión, no estimación (R1).
