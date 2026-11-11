# 07 — Veredicto de independencia del mercado (fase 2)

Fecha: 2026-11-10. Escalón Fable. Mecanismo por mecanismo, en los 21 prompts y en la plataforma, con una de tres clasificaciones por mecanismo:

- **ENTRADA PROHIBIDA**: cuotas, probabilidades implícitas, consensos, movimientos o ajustes hacia el mercado dentro de la generación, calibración, selección de variables u optimización de probabilidades.
- **UMBRAL LEGÍTIMO**: una línea del mercado usada solo como el punto `t` en `P(X > t)` sobre una distribución que no depende del mercado.
- **COMPARACIÓN POSTERIOR**: evaluación, filtro de stake o métrica calculada después de congelar la probabilidad, sin modificarla.

Etiquetas de evidencia: [COMPROBADO] [INFERENCIA] [HIPÓTESIS] [RECOMENDACIÓN].

**Marco vinculante.** Cumplir el principio en producción es una decisión del operador y depende de la medición pre-registrada «el modelo manda» (`docs/research/2026-08-26-preregistro-el-modelo-manda.md`): una sola medición al alcanzar ≥ 3.402 eventos graduados (líneas 154-158; disparo estimado hacia el 2026-11-24, línea 138; `--medir` una sola vez con T1 fijado por addendum, líneas 328-329), con dos puertas (Brier y ROI, líneas 173-188) y, si pasa, `market_shrink → 0` solo en el segmento que pase y en shadow 30 días (líneas 190-194). Después, el pre-registro por segmento (`docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.md`) ajusta `s_k` solo tras T0 = resultado de MM y mide a N = 3.300 (líneas 43-52, 210-220; ≈ 2027-03-21); «Nada se activa con este documento» (línea 25). **Este informe no recomienda tocar `configs/` ahora ni mirar ningún resultado antes de esas fechas.**

## 1. Los 21 prompts

### 1.1 Veredicto

[COMPROBADO] **Los 21 prompts son independientes del mercado**: ninguna mención a cuotas, líneas, consenso, cierre o CLV es ENTRADA PROHIBIDA; todos congelan la probabilidad antes de consultar el mercado y todos usan las líneas solo como umbral. Verificado en esta fase sobre los prompts de referencia de cada familia (MLB:14, 54, 177-178; NHL:6, 36, 432-449, 592; NBA:19, 248-249, 251, 277; NFL:24, 62, 319, 446; EPL:27, 272; ATP:37, 317, 342) y, para el resto, sobre las tablas de la fase 1 (sección 7 de cada informe individual), que no contradicen lo verificado.

### 1.2 Mecanismos (resumen de los 21)

| Mecanismo del prompt | Clasificación | Citas representativas |
|---|---|---|
| Regla de independencia («la cuota jamás es entrada») | Regla de independencia | NHL:6; ATP:37; NFL:24; EPL:27; MLB:14; NBA:19; SERIE_A:21; LIGUE_1:19 |
| Congelación (hash, `prediction_id`, «no ajustar para acercarse a cuotas») antes del mercado | Congelación explícita | MLB:178; ATP:317; NBA:249; NFL:319; NHL:432-449; EPL:272-274 |
| Líneas de hándicap/total/puck line/run line como `t` en `P(X > t)` | UMBRAL LEGÍTIMO | NHL:389-405 y 394 («línea teórica, etiquetada sin cuota»); MLB:147-165; NBA:229, 239; NFL:315; EPL:246-262; ATP:296-299 |
| De-vig, EV, break-even con push, edge de precio | COMPARACIÓN POSTERIOR | MLB:181-195; NHL:456-467; NBA:253-277; NFL:329-345; EPL:276-288; ATP:321-333 |
| CLV solo con cierre observado | COMPARACIÓN POSTERIOR | NBA:277; MLB:202; NHL:465; ATP:331 |
| Benchmark de mercado sin vig en backtest | COMPARACIÓN POSTERIOR (con la ambigüedad de §1.3) | MLB:261; NFL:361; NBA:305-306; EPL:27 |
| Fallback «solo ranking/odds/H2H ⇒ NO CALCULADO» | Regla de independencia (las odds no son base suficiente) | ATP:430 |
| «Ninguna cuota utilizada para ajustar ratings del pronóstico congelado» / «La fuente de los odds no alimenta las variables deportivas previas» | Regla de independencia | NFL:446; NHL:592 |
| ROI y CLV como «medidas económicas secundarias» | COMPARACIÓN POSTERIOR | NHL:609 |

### 1.3 Matices que conviene cerrar (sin cambiar el veredicto)

- [COMPROBADO] **Cláusulas condicionales:** SERIE_A:21 («cuando operas en el modo independiente aquí especificado») y LIGUE_1:19 («ni calibrarlas durante la ejecución») dejan abierto un modo o un momento en que el mercado sí calibraría. [RECOMENDACIÓN] Hacerlas incondicionales.
- [COMPROBADO] **Benchmark en validación sin cerrar la optimización:** EPL:27 y MLB:14 separan el benchmark del «entrenamiento», pero no prohíben elegir hiperparámetros, calibradores o umbrales por métricas contra el mercado (ROI, CLV). Es la puerta por la que entró R2 en la plataforma. [RECOMENDACIÓN] Añadir en los 21: «ningún hiperparámetro, calibrador ni umbral se selecciona por métricas calculadas contra cuotas».
- [COMPROBADO] LALIGA:152 usa «mercado de fichajes»; cambiar a «ventana de traspasos».
- [COMPROBADO] WNBA:43 nombra «cuota de cierre» como información posterior al `as_of` que no debe usarse: correcto y coherente con el principio.

## 2. La plataforma, mecanismo por mecanismo

| # | Mecanismo | Clasificación | Evidencia | Qué haría falta para cumplir el principio sin romper los pre-registros |
|---|---|---|---|---|
| M1 | `market_shrink 0,5`: `p_used = (1−s)·p_adj + s·fair`, `p_decision = (1−s)·cal(p_adj) + s·fair` | **ENTRADA PROHIBIDA** en la probabilidad de decisión, servida (`estimated_probability`, `calibrated_probability`) y publicada (tipster) | `configs/default.yaml:17`; `src/sqp/pipeline/probabilities.py:303-305`; `src/sqp/pipeline/daily.py:969-970, 974, 1033-1034`; `src/sqp/evaluation/tipster.py:132-136` | Es exactamente lo que mide MM. Nada antes del resultado. Si MM PASA: `s → 0` en el segmento que pase, shadow 30 días (`preregistro-el-modelo-manda.md:190-194`). Si FALLA o PEOR: `s` sigue y el ajuste por segmento es la vía (`peso-mercado:273-276`). La precondición técnica ya está cumplida: `market_shrink` se persiste por fila (`daily.py:1040-1042`) |
| M2 | `model_probability` / `adjusted_probability` persistidas antes de la mezcla; `cal()` se aplica a la creencia pre-blend | **Congelación existente** (cumple el principio a nivel de estimación) | `daily.py:1031-1032, 1126`; `probabilities.py:277-283, 299-302` | Nada. Es el ancla que permite reconstruir `p_cal = 2·calibrated − fair` en MM (`preregistro-el-modelo-manda.md:60-66`) |
| M3 | `uncertainty_penalty 0,35` (+ `anomaly_edge_gap`, `low_book_penalty`, `min_books_for_consensus`): el edge se deflacta por `|p − fair|` y la penalización se pliega en `effective_probability` que alimenta Kelly y la elegibilidad | **ENTRADA PROHIBIDA** en la probabilidad de stake (capa de decisión, no de estimación) | `default.yaml:18-30`; `src/sqp/markets/edge.py:70-72, 90`; `daily.py:982-1017` | No está en el alcance de MM (que mide Brier/ROI de `p_cal`), pero la segunda puerta de MM compara ROI de `s=0` frente a `s=0,5` con el resto de la política fija (`preregistro-el-modelo-manda.md:173-188`). Cambiarlo antes alteraría esa comparación: diferir. Separar conceptualmente «incertidumbre del modelo» de «desacuerdo con el mercado» en el nombre y en los informes es documentación, no cambio de política |
| M4 | `line_movement_penalty`, `line_velocity_penalty`, `books_spread_penalty` (todos 0,0) | **ENTRADA PROHIBIDA LATENTE** (estructura cableada, inerte) | `default.yaml:31-50`; `daily.py:979-996` | Nada ahora. Su activación exigiría pre-registro propio; el principio del operador los descarta como entrada |
| M5 | `spread_line` / `total_line` tomadas del consenso (línea más frecuente) y pasadas al adaptador | **UMBRAL LEGÍTIMO** | `probabilities.py:240-247`; `adapters.py:63-72, 146-153` | Nada |
| M6 | Features aditivas `totals_tendency` y `over_under_rate` referenciadas a la línea (`point`) — coeficientes 0 | **UMBRAL LEGÍTIMO** (la línea es referencia, no media) | `default.yaml:55-60, 112-116` | Nada; activación solo con pre-registro |
| M7 | `min_edge 0,02`, `max_plausible_edge 0,075`, Kelly sobre el precio, `stake_price` al menor entre mediana y ejecución | **COMPARACIÓN POSTERIOR** (selección y tamaño del stake dependen del precio por definición; no modifican `model_probability`) | `default.yaml:4, 16`; `daily.py:997-1006, 1053` | Nada. La **elección** de `max_plausible_edge` por ROI es R2 de `05-informe-de-riesgos.md`, no un uso del mercado en tiempo de ejecución |
| M8 | Calibradores: entrenados sobre `adjusted_probability` frente a resultado, stream servido ∪ liquidadas; `implied_probability_novig` viaja sin usarse | **LEGÍTIMO** (no mercado) | `src/sqp/calibration/data.py:12-19, 31-34, 69, 207-227`; `calibrator.py:714-740` | Nada. [RECOMENDACIÓN, candado] test que falle si alguna columna de mercado entra en las features del calibrador (ver `09`, P9) |
| M9 | `prediction_gate`: modelo PURO frente a no-vig, test de signo pareado + `ev_lado_modelo`, Bonferroni K = 69, fuera de muestra | **COMPARACIÓN POSTERIOR** (gate de stake, no toca probabilidades) | `src/sqp/risk/prediction_gate.py:10-33`; `default.yaml:262-284` | Nada. Es la encarnación operativa de «el mercado compara después»: solo lleva stake lo que bate al mercado con `model_probability` |
| M10 | `degradation_monitor`: pausa si Brier(`estimated_probability`) > Brier(mercado) + 0,01 o ROI plano < −0,15 | **COMPARACIÓN POSTERIOR**, pero sobre la **mezcla** (contiene mercado) y con retroalimentación de ROI realizado sobre qué se publica con stake | `src/sqp/risk/degradation.py:71-72, 96-98, 123-132`; `default.yaml:285-303` | No altera probabilidades ni filas servidas (los pausados siguen estimándose, `default.yaml:214-219`), luego no afecta a MM. [RECOMENDACIÓN, diferida y de medición] añadir `brier_model` sobre `model_probability` como columna paralela del registro; decidir después si la regla de pausa debe leerla |
| M11 | `clv_gate` (desactivado) y auditoría CLV | **COMPARACIÓN POSTERIOR** | `default.yaml:249-261` | Nada |
| M12 | `revalidation` (segundo pase: revoca picks cuyo edge actual < `min_edge` con consenso fresco; solo baja stakes) | **COMPARACIÓN POSTERIOR** | `default.yaml:305-316` | Nada |
| M13 | `intraday_scan` (observatorio de edge, «medición pura») | **COMPARACIÓN POSTERIOR** | `default.yaml:318-324` | Nada |
| M14 | `execution.books: [pinnacle]` (precio de ejecución; benchmark no-vig siempre sobre el consenso completo) | **COMPARACIÓN POSTERIOR** | `default.yaml:150-172` | Nada |
| M15 | `park_bound 0,10` elegido por ROI realizado sobre cuotas (parámetro que entra en λ) | **ENTRADA PROHIBIDA en la optimización** (selección de un parámetro del modelo contra el mercado) | `configs/leagues/ratings.yaml:25-30`; `adapters.py:190-221`; `roi_engine.py:12-13` | Re-validar por log loss/Brier frente a resultados en walk-forward es un cambio de régimen MLB: addendum en MM antes de medir (`preregistro-el-modelo-manda.md:256-272`). Diferir a después del resultado de MM. El operador decide si el valor se conserva «por orden» mientras tanto, como ya hizo con `pitcher_bound` (`ratings.yaml:17-21`) |
| M16 | `max_plausible_edge` y `uncertainty_penalty` elegidos por ROI sobre cuotas | **ENTRADA PROHIBIDA en la optimización** de la capa de decisión (no de la estimación) | `default.yaml:11-26` | Misma cautela que M3: forman parte de la política que la segunda puerta de MM compara. Diferir |
| M17 | `tune_market_param` (WNBA `scoring_half_life_days 60`): rejilla puntuada por log loss de `P(total > t)` con `t` = línea fija y resultado del marcador | **UMBRAL LEGÍTIMO** (la línea es umbral de evaluación; el objetivo es el resultado deportivo) | `src/sqp/backtesting/tuning.py:201-268` («not an estimate of live market performance»); `registry.py:56-78` | Nada. Matiz: el umbral elegido es la mediana de la línea servida (177,5) y el diagnóstico se formuló «contra la línea»; con otro `t` el argmin podría variar [HIPÓTESIS]. Corrige la lectura de la fase 1 (individual WNBA §9), que lo clasificó como ENTRADA PROHIBIDA |
| M18 | `avg_total 171` (WNBA) justificado con total observado 170,9 y, como contraste, línea media 175,1 | **COMPARACIÓN POSTERIOR** (diagnóstico); el valor es el dato deportivo | `registry.py:56-60` | Nada |
| M19 | Tuning por resultados: `tune_home_advantage`, `tune_dc_rho`, descanso NBA, tilt NHL, abridor MLB, portero NHL, `elo_k` tenis | **LEGÍTIMO** (log loss frente a resultados) | `tuning.py:150-193, 271-279`; `ratings.yaml:17-23, 34-50`; `registry.py:48-52` | Nada |
| M20 | Adaptadores, Elo, tasas de equipo, parque, abridor, portero, descanso, clima: sin columnas de cuotas | **LEGÍTIMO** | grep `implied|novig|price_decimal|odds` sin resultados en `src/sqp/features/*.py`, `models/ml_train.py`, `ml_predict.py`, `park.py`, `starters.py`, `team_scoring.py`; `blend.py` peso 0 | Nada |
| M21 | `pick_mode: accuracy` (inactivo): selección por `p_decision ≥ 0,70` | Consumiría la ENTRADA de M1 si se reactivara | `default.yaml:174-200`; `daily.py:1055-1059` | Nada (revertido 2026-07-31 por el operador) |

## 3. Veredicto

**Prompts:** independientes del mercado, los 21, con tres matices de redacción (condicionales en Serie A y Ligue 1; ausencia de prohibición explícita de optimizar hiperparámetros contra el mercado; «mercado de fichajes»).

**Plataforma:** la capa de **estimación** es independiente (M2, M5, M8, M17-M20: ningún adaptador, feature, calibrador ni tuning por resultados lee cuotas, y la probabilidad pura se congela en `model_probability`); la capa de **decisión y publicación** no lo es (M1 y M3: la probabilidad que selecciona, dimensiona y se muestra es 50 % mercado, y la de stake incorpora la distancia al mercado); y en la **optimización histórica** hay tres parámetros elegidos por ROI sobre cuotas (M15 en el modelo, M16 en la decisión).

**En una frase:** la plataforma estima sin el mercado, decide con él y, en tres parámetros heredados de junio de 2026, se optimizó contra él; la vigencia de ese diseño la decide el operador a la luz de la medición pre-registrada «el modelo manda» (una sola vez, ≈ finales de noviembre de 2026), y nada de lo anterior debe cambiarse ni mirarse antes.

## 4. Qué puede hacerse ya sin tocar `configs/` ni los pre-registros

[RECOMENDACIÓN] Todas son documentación, candados de test o columnas de medición, y ninguna altera probabilidades servidas, stakes ni las poblaciones de MM y peso-mercado:

1. Cerrar los tres matices de redacción en los prompts (§1.3).
2. Candados automáticos de `09-principios-fundamentales.md` (P1, P2, P8, P9): tests que fallan si una columna de mercado entra en estimación o calibración, si `model_probability` deja de ser independiente de `fair`, o si un override de `ratings.yaml` se justifica por ROI.
3. Columna paralela `brier_model_puro` en el registro de degradación (M10) como medición.
4. Renombrar en documentación lo que `uncertainty_penalty` mide realmente (desacuerdo con el mercado), sin cambiar su valor.
5. Registrar en MM, como addendum «antes de ejecutar», este informe como lectura previa, sin cambiar criterio alguno (los addenda existentes son el precedente: `preregistro-el-modelo-manda.md:256-272`).

**Estado al 2026-11-11:**
- **(1) Hecho.** Los 21 prompts de `C:\dev\Prompts` llevan la frase «Ningún hiperparámetro, calibrador ni umbral se selecciona por métricas calculadas contra cuotas (ROI, CLV o distancia al consenso)» en su regla de independencia. Además:
  - SERIE_A:21 pierde la condición «cuando operas en el modo independiente aquí especificado»;
  - LIGUE_1:19 pierde «durante la ejecución»;
  - LALIGA:152 dice «ventana de traspasos».

  Esa carpeta no está bajo git; los originales están en `C:\dev\Prompts\_respaldo_2026-11-11\`.
- **(2) Hecho** en `tests/test_market_independence.py`.
- **(3) Hecho:** `brier_model_pure` en `src/sqp/risk/degradation.py`, solo como medición.
- **(4) Sin cambios:** el comentario de `configs/default.yaml:18-25` ya describe la penalización como función del desacuerdo entre modelo y mercado.
- **(5)** Addendum de MM del 2026-11-11.
