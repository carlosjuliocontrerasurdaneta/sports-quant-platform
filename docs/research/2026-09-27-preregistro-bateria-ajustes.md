# Pre-registro — batería de los ajustes aditivos de la capa de features

**Fecha:** 2026-09-27. Escrito **antes** de calcular ninguna relación entre los
ajustes y los resultados. Lo consultado es:

- el código y la documentación;
- la **distribución de las features** en el histórico (sección 13). Las features
  se construyen con los marcadores de partidos **anteriores** (día UTC
  estrictamente anterior). **Ninguna feature se ha emparejado con el desenlace
  del partido para el que se calcula.**

Orden del operador (2026-09-26): «Sí, añade la batería a la cola», con estas
condiciones:

- un solo pre-registro con corrección de Holm;
- descarte razonado por escrito, **antes** de medir, de los ajustes redundantes;
- los mismos criterios que los precedentes: walk-forward, margen
  `IMPROVEMENT_MARGIN = 0.002` (`src/sqp/backtesting/tuning.py:38`) y control de
  intercepto.

Código de referencia: `main` en `f9658ce`. Datos: filas con `date ≤ 2026-09-26`.

Sigue los precedentes, con sus enmiendas y resultados:

- `2026-09-26-preregistro-clima-mlb.md` (E1–E13), con su resultado;
- `2026-09-26-preregistro-descanso-basket.md` (enmiendas, contraste de `--pre` y
  nota de re-ejecución), con su resultado;
- `2026-09-26-preregistro-portero-nhl.md`.

Incorpora desde el principio lo que exigieron las revisiones de Fable: control
de intercepto, criterio sobre los afectados, particiones temporales, bootstrap
por días, paridad con el motor, ejecución única con regla de re-ejecución,
potencia calculada antes y ningún umbral sin origen.

---

## 1. Qué se mide y dónde vive

`src/sqp/pipeline/probabilities.py::adjust_model_probability` (l. 314) suma a
`p_model` diez términos aditivos en **puntos de probabilidad**. El resultado se
acota a [0,01; 0,99]. Las features salen de `build_adjustment_context`, a partir
de `src/sqp/features/rest_form.py`. Todos los coeficientes valen 0
(`configs/default.yaml`, l. 43-116).

Cinco hechos del código condicionan todo el diseño:

1. **La capa vive fuera del adaptador.** `walk_forward_backtest`
   (`backtesting/engine.py`) **no** la aplica: evalúa `adapter.estimate` a secas.
   Solo la aplican `daily.run_league` (l. 871-897) y
   `roi_engine.backtest_league` (l. 358-373), las dos a través de las mismas
   funciones (AUD-MED-006). La sección 7 decide con qué se mide.
2. **Los coeficientes son globales.** `RiskConfig` los lee de
   `configs/default.yaml` (`config.py:475-494`), sin override por liga ni por
   variable de entorno. Si hoy se pone uno distinto de 0, actúa en **todas** las
   ligas servidas: 23 ligas de seis familias, más los torneos de tenis. No existe
   ningún mecanismo para activarlo en una sola liga (sección 15).
3. **Entra antes de la calibración y del shrink.** `_decision_probability`
   calibra `adjusted_probability` y después mezcla con el no-vig:
   `p_decision = (1 − s)·cal(p_adj) + s·fair`, con `market_shrink = 0,5`. Los
   calibradores se reentrenan sobre la columna `adjusted_probability`
   (`probabilities.py:205-214`).
4. **El prediction gate no la ve.** El test de signo y `ev_flat` usan
   `model_probability`, el modelo **puro** (`risk/prediction_gate.py:12`,
   l. 253-255). «El modelo manda» sí la ve: evalúa `p_cal`, que sale de
   `calibrated_probability` (sección 17).
5. **Un mismo coeficiente mueve dos mercados.** `recent_form_coef`,
   `home_away_form_coef` y `margin_coef` actúan con el mismo valor en h2h y en
   spreads. `h2h_coef` actúa solo en h2h. `totals_tendency_coef` y
   `over_under_rate_coef` actúan solo en totales.

**La pregunta.** Para cada ajuste que sobrevive al descarte (sección 2), y en
cada liga que decide (sección 5): ¿sumar el término, con la forma funcional y la
ventana `n` que el código y la configuración ya fijan, mejora la probabilidad
del modelo frente al resultado, por encima de un simple desplazamiento
constante?

**Esto no mide ventaja sobre el mercado.** Ningún resultado de este documento
es una afirmación de rentabilidad. Aquí se distinguen probabilidad estimada,
probabilidad implícita, edge, hit rate observado, ROI esperado y ROI realizado,
y **solo se mide la primera** frente al resultado.

## 2. Descarte razonado, antes de medir

El orquestador propuso descartar los ajustes 1, 5, 6 y 7. Se evalúa cada
argumento contra el código. **El descarte se mantiene en los cuatro, pero en 6
y 7 por una razón distinta y más fuerte que la propuesta.** En 1, el argumento
propuesto solo vale para una parte de las familias.

### 2.1 `rest_days_coef` (1): DESCARTADO

- **«Duplica el `RestModel`»: cierto solo en parte.** `RestModel` vive en
  `NormalMarginAdapter` (`sports/adapters.py:38-55`), así que cubre basket y
  fútbol americano. En la NBA ya está activo (`rest_points_per_day 0.795`,
  `configs/leagues/ratings.yaml`), y activar `rest_days_coef` contaría el
  descanso dos veces. Pero `PoissonAdapter`, que usan NHL, MLB y fútbol, **no
  tiene ningún mecanismo de descanso**. En esas ligas el argumento de la
  duplicación no vale.
- **Lo que sí descarta el ajuste en todas las ligas es su forma funcional.**
  `rest_form_p_adjustment` multiplica `(r_home − r_away)` sin acotar
  (`rest_form.py:163-164`). `team_rest_days` devuelve días naturales sin tope ni
  corte de temporada. En el primer partido de cada temporada, la diferencia
  llega a decenas de días (sección 1 del pre-registro del descanso). Cualquier
  coeficiente estimado quedaría dominado por esos casos extremos. Medir una forma
  así es gastar un test en una especificación defectuosa por construcción.
- **Consecuencia.** `rest_days_coef` sigue en 0. El descanso en NHL (donde el
  pre-registro del portero documenta el confusor de los back-to-backs) y en MLB
  sigue **sin medir**. Si se quiere medir, se hace con un pre-registro propio y
  con una forma acotada dentro del `PoissonAdapter`, como el `RestModel`
  (**decisión del operador**, sección 18).

### 2.2 `streak_coef` (5): DESCARTADO

- Se midió el 2026-09-01 y se apagó por orden del operador (comentario de
  `configs/default.yaml`, l. 61-92, y Bitácora del 2026-09-01). La medición usó
  **este mismo histórico**. Volver a medirlo aquí sería validar sobre la muestra
  del descubrimiento, que es justo lo que el propio comentario prohíbe
  («validar sobre ella es KI-019»).
- La forma programada no tiene ventana ni cota: `team_streak` recorre todo el
  historial y devuelve un entero sin acotar, que llegó a d = 37 en la NBA
  (KI-024). Una racha con ventana sería **otra** forma funcional, con su propio
  pre-registro y otra muestra.

### 2.3 `off_def_h2h_coef` (6): DESCARTADO, porque es el ajuste 9 reparametrizado

- **«Duplica las tasas de ataque y defensa del adaptador»: no es exacto.**
  `TeamScoringRates` solo alimenta la **escala del total**:
  `NormalMarginAdapter.estimate` usa `scoring.expected_total` para `mu_total`, y
  `PoissonAdapter._rates` lo usa para `avg`. El **reparto** entre local y
  visitante (moneyline y spreads) sale solo del Elo: `rating_diff` y
  `expected_home_win`. Las tasas de ataque y defensa no tocan el lado del
  partido.
- **La razón real es una identidad algebraica.** Anotado más concedido por el
  local, menos lo mismo del visitante:

      expected_margin = (s_h + c_a − s_a − c_h)/2 = ((s_h − c_h) − (s_a − c_a))/2
                      = (margin_home − margin_away)/2

  Con `off_def_n = margin_n = 10` (`default.yaml`), el término 6 es exactamente
  `(off_def_h2h_coef/2) · x₉`. Es la misma hipótesis que el ajuste 9 con otro
  coeficiente. **Comprobado en los datos:** max |x₉/2 − x₆| ≤ 2,1·10⁻¹⁴ en todas
  las ligas (sección 13). Medir los dos contaría una sola hipótesis dos veces en
  la familia de Holm.
- Si el ajuste 9 se activara, el 6 tendría que seguir en 0 para no contar dos
  veces la misma señal.

### 2.4 `off_def_totals_coef` (7): DESCARTADO, porque es el ajuste 4 exacto

- La identidad es la misma:
  `expected_total = (s_h + c_a + s_a + c_h)/2 = (avg_total_home + avg_total_away)/2`.
  Con `off_def_n = totals_tendency_n = 10`, el término 7 es **idéntico** al 4,
  con otro nombre de coeficiente. Comprobado: max |x₄ − x₇| ≤ 5,7·10⁻¹⁴.
- El argumento del orquestador sí se aplica aquí, **pero vale igual para el
  ajuste 4**. La fórmula es la de `TeamScoringRates.expected_total`, con otra
  ponderación: una ventana fija de 10 partidos frente a una media acumulada
  regresada a la media de la liga (`prior_games 6`), con decaimiento
  (`scoring_half_life_days`) solo en NBA (180 días) y WNBA (60). Por eso lo único
  que el ajuste 4 puede aportar es **recencia** (sección 3). Se mide el 4 en
  lugar del 7 por su nombre, sin otro motivo: son el mismo número.
- La identidad vale mientras las ventanas coincidan. Si alguien cambiara
  `off_def_n`, los términos se separarían. Este descarte se refiere a la
  configuración vigente.

## 3. Los seis que se miden, y qué podrían aportar

**Frente al mercado, ninguno aporta información nueva.** Son funciones de
marcadores públicos que las casas ya ven. Lo único que pueden mejorar es la
probabilidad **del modelo**. Con `market_shrink = 0,5`, la probabilidad servida
recibiría como mucho la mitad de lo que se mida aquí. Siete mediciones previas
no encontraron ventaja sobre el feed público, y la de 2026-09-07 concluyó que el
modelo está *encompassed* por el consenso.

| # | Ajuste | `n` | Mercados | Qué no tienen ya el Elo ni las tasas | Por qué puede no aportar nada |
|---|---|---:|---|---|---|
| 2 | `recent_form_coef`: tasa de victorias (últimos `n`), local − visitante | 5 | h2h y spreads | El Elo es un suavizado exponencial con K fijo (`elo_k` 20/24/6/10) y **no regresa a la media entre temporadas**. Una ventana de 5 partidos tiene mucha menos memoria: prueba si el Elo reacciona tarde a cambios de régimen (traspasos, lesiones largas, arranque de temporada) | Es un proxy de calidad, y la calidad ya está en el Elo. Correlación con x₉ entre 0,63 y 0,74 (sección 13). Las tasas de victoria sobre 5 partidos son muy ruidosas |
| 3 | `h2h_coef`: tasa de victorias en los últimos `n` enfrentamientos directos, centrada en 0,5 | 10 | solo h2h | El Elo es unidimensional y transitivo. El cara a cara prueba efectos de estilo **no transitivos** entre dos equipos concretos | Diez enfrentamientos abarcan varias temporadas en NBA, NHL y NFL (2-4 por temporada), con plantillas distintas. En MLB caen casi todos en la misma temporada, y entonces vuelve a ser un proxy de calidad. En NCAAF casi no hay datos (sección 13) |
| 4 | `totals_tendency_coef`: media del total en los últimos `n` de cada equipo, menos la línea | 10 | solo totales | **Recencia del entorno de anotación.** `TeamScoringRates` pondera igual toda la historia regresada (`prior_games 6`), salvo el decaimiento de NBA y WNBA. La media de x₄ es positiva en NBA y NFL (entre +1 y +2 puntos) y en NHL desde 2018 (+0,5 goles): la ventana corta sigue la deriva mejor que las tasas | Si mejora por eso, el sitio correcto es el adaptador (`scoring_half_life_days` / `scoring_prior_games`), no un término en probabilidad (sección 15). En producción el término se mide contra la línea del **mercado**, que ya incorpora la recencia (sección 7.3) |
| 8 | `home_away_form_coef`: forma del local **en casa** − forma del visitante **fuera** | 5 | h2h y spreads | El Elo usa una ventaja de campo **común** a toda la liga (`elo_home_adv`), salvo en la MLS (`elo_home_away_split: true`). Es la única feature que prueba una ventaja de campo **por equipo** | La media de x₈ es claramente positiva (+0,07 a +0,34): contiene la ventaja de campo de toda la liga. Sin el control de intercepto, un coeficiente positivo ganaría solo por corregir el `elo_home_adv` (sección 8). Cinco partidos por rol dan una estimación muy ruidosa |
| 9 | `margin_coef`: margen medio (últimos `n`), local − visitante | 10 | h2h y spreads | En las familias con `elo_mov` apagado (béisbol, hockey y fútbol), **el Elo ignora el margen**: solo usa ganar o perder. En MLB, la diferencia de carreras predice mejor que el balance de victorias (Pitágoras) | En basket y NFL, `elo_mov: True` ya incorpora `log(margen + 1)`: redundancia parcial. Es la más informativa de las tres de calidad, y por eso la que más solapa con el Elo |
| 10 | `over_under_rate_coef`: fracción de los últimos `n` partidos de cada equipo por encima de la línea actual, centrada en 0,5 | 10 | solo totales | La misma información que el 4, transformada en un recuento. Es robusta a las palizas y a las prórrogas | Correlación con x₄ entre 0,76 y 0,86. No es una identidad algebraica, así que se mide aparte. **Nunca se activarían el 4 y el 10 a la vez** (sección 15) |

**Qué se espera.** Lo más probable es que casi todas las celdas rechacen: las
features de calidad son casi colineales entre sí (Bitácora del 2026-09-01) y con
el Elo. Las hipótesis con más base previa son el 9 en MLB y NHL (Elo sin margen)
y el 4 donde el entorno de anotación deriva. Se deja escrito para que un rechazo
no se lea como «la forma de los equipos no importa», sino como «esta forma
aditiva no añade nada al modelo».

## 4. Exposición previa de la muestra (declarada)

El histórico **no es virgen** para estas ideas. Se declara:

1. **2026-09-01.** El arnés `scripts/measure_features.py`, ya corregido (KI-025),
   imprimió las correlaciones **brutas** de `form_diff`,
   `form_home_role_diff`, `margin_diff`, `off_def_margin`, `avg_total_combined`,
   `over_rate_combined` y `rest_diff` con el resultado, en diez ligas. La
   Bitácora solo recoge las cifras de `streak`, y dice que, controlando por las
   otras features de calidad, `margin_diff` también colapsa: son casi
   colineales.
2. **2026-09-15.** `scripts/evaluate_feature_blocks.py` exploró bloques
   parecidos (`opponent_form`, `venue_form`, `schedule`; ventana de 20 partidos,
   modelo aprendido) sobre todo el histórico local. Su selección está en
   `audit/feature_candidates_20260915.json`, y su confirmación prospectiva
   (feature-shadow, 2026-09-16 a 2027-09-16) sigue en curso
   (`docs/FEATURE-RESEARCH.md`).

**Cómo se ha tratado.** Quien redacta este documento **no ha leído** esas
cifras ni esa selección, salvo el párrafo de la Bitácora citado arriba. Ninguna
elección de este documento sale de ellas:

- las formas funcionales son las del código;
- las ventanas son las de la configuración;
- las ligas salen de la longitud del histórico;
- los criterios salen de los precedentes.

Además, una correlación bruta con el resultado no responde a la pregunta de
aquí, que es el valor **incremental sobre el modelo**. Aun así, un ACEPTA sobre
esta muestra es una evidencia algo más débil que sobre una muestra virgen. Por
eso la familia se corrige con Holm y se exige el signo en cada partición.

## 5. Ligas y mercados

| Liga | Familia | Filas (≤ 2026-09-26) | Rol | Motivo |
|---|---|---:|---|---|
| **NBA** | basketball | 34.065 (2002–2026) | **decide** | 25 temporadas, tres particiones (sección 9) |
| **NHL** | hockey | 32.888 (2002–2026) | **decide** | 25 temporadas, tres particiones |
| **NFL** | football | 8.046 (2002–2026) | **decide** | 25 temporadas, tres particiones. Potencia menor (sección 13) |
| **MLB** | baseball | 9.706 (2023–2026) | **decide** | 4 temporadas de ~2.430 partidos, dos particiones. Potencia menor |
| NCAAF | football | 3.155 (2023–2026) | secundaria | 3 temporadas. Sin datos de cara a cara (4 afectados en test A) |
| WNBA | basketball | 1.160 | secundaria | error estándar ≈ 0,0035 por partición, mayor que el margen (precedente del descanso) |
| NCAAB / WNCAAB | basketball | 6.331 / 6.125 (solo 2025-26) | secundaria | una sola temporada, sin test posterior |
| Fútbol (11 ligas, agrupadas) | soccer | 11.158 (2023–2026) | secundaria | Dos temporadas de test. h2h a tres vías: la capa suma al local y resta al visitante sin tocar el empate, y el motor evalúa P(local \| no empate), que no es lo que la capa mueve. Ligas heterogéneas, y la MLS ya tiene Elo local/visitante (redundante con el 8) |
| Tenis (ATP/WTA) | tennis | — | **excluido** | La orientación local/visitante es el orden del feed. El 8 no tiene sentido, y el 9 y el 4 tampoco (store ganador = 1, perdedor = 0). Un año de historia |

**Celdas que deciden** (ajuste × liga × mercado de decisión):

| Ajuste | Mercado de decisión | Restricción en el otro mercado | Ligas |
|---|---|---|---|
| 2, 8, 9 | h2h (moneyline) | spreads sin empeorar (criterio 6) | NBA, NHL, NFL, MLB |
| 3 | h2h | — (el código no lo aplica a spreads) | NBA, NHL, NFL, MLB |
| 4, 10 | totales | — | NBA, NHL, NFL, MLB |

Son **24 celdas**: seis ajustes por cuatro ligas. **Se mide por liga, no
agrupado.** El ajuste está en puntos de probabilidad, pero la escala de x cambia
por deporte (puntos de NBA frente a goles de NHL), y el Elo de cada familia
recoge cosas distintas: MOV sí o no, K distinto. Un coeficiente agrupado
mezclaría hipótesis distintas y, además, no se podría servir por liga. El
agrupado del fútbol es secundario por las razones de la tabla.

## 6. Datos y features

- **Fuente:** `ResultsStore(ROOT).load(liga)`, todas las filas con
  `date ≤ 2026-09-26`. Mismo orden que ven producción y el motor: orden estable
  por `date`. En MLB, las filas se enriquecen con `StartersStore.attach` y
  `StarterFIPStore.attach`, como en E2 del clima, porque la base de producción
  lleva `pitcher_bound 0.05`. El script registra el SHA-256 y las filas de cada
  fichero.
- **Semántica temporal:** `date` es el día UTC del inicio (ESPN). La feature de
  un partido del día D solo usa partidos con fecha **estrictamente anterior** a
  D, que es el recorte `_hasta` de `rest_form.py` y el de
  `roi_engine._prior_games` (`d < rd`). En producción se calcula sobre
  resultados ya liquidados. Un partido del mismo día nunca entra, así que no hay
  leakage.
- **Construcción:** el script **no reimplementa** las features. Llama a
  `build_adjustment_context(home, away, rd, prior, risk, adapter.normalize)` con
  `prior = roi_engine._prior_games(...)`, exactamente como `roi_engine`. El
  término over/under lo calcula `adjust_model_probability` desde `ctx.results`.
- **Ventanas `n`: se fijan las de la configuración**, sin estimarlas:
  `recent_form_n 5`, `h2h_n 10`, `totals_tendency_n 10`, `home_away_form_n 5`,
  `margin_n 10`, `over_under_rate_n 10`.
  - Estimar `n` sería un grado de libertad más por celda. Una rejilla de, por
    ejemplo, cinco ventanas convertiría 24 hipótesis en 120, y el `n` ganador
    sería una señal a medida.
  - Las ventanas de configuración son las que usaría producción al activar.
  - Un rechazo vale para esa ventana. Probar otra exige un pre-registro nuevo
    con datos nuevos.
- **Partido afectado** (por celda): la feature está disponible (no `None`) y su
  x es distinto de 0, es decir, el término vale ≠ 0 para cualquier coeficiente
  ≠ 0. Se define sin el resultado.

  | Ajuste | x |
  |---|---|
  | 2 | form_h − form_a |
  | 3 | h2h_home − 0,5 |
  | 4 | (avg_total_h + avg_total_a)/2 − L |
  | 8 | form_h@casa − form_a@fuera |
  | 9 | margin_h − margin_a |
  | 10 | (over_h + over_a)/2 − 0,5 |

## 7. Qué motor mide, y paridad

### 7.1 Por qué ni `walk_forward_backtest` solo ni `roi_engine`

- `walk_forward_backtest` es el arnés canónico de las decisiones previas (abridor,
  clima, descanso, portero). Tiene paridad exacta con el adaptador y 25
  temporadas, pero **no aplica la capa** (sección 1, hecho 1).
- `roi_engine` **sí** la aplica, con las mismas funciones que producción, pero
  solo sobre cuotas capturadas: unos meses, con n = 228 eventos h2h de NBA en el
  informe del descanso. Además mezcla el shrink, las penalizaciones y la
  selección por stake. Mide ROI realizado de una política, no la calidad de la
  probabilidad, y no tiene potencia.

### 7.2 Diseño: reproducción del motor + capa canónica

Script `scripts/research/measure_adjustment_battery.py`. Por liga:

1. **Base.** Reproduce el bucle de `walk_forward_backtest`: días completos
   estimados con el estado al cierre del día anterior, `warmup = 60`, la
   configuración de producción en `f9658ce` con
   `_league_meta(liga)["league_params"]` + `get_adapter`. Esto incluye
   `nba.rest_points_per_day 0.795` y, en MLB, `pitcher_bound 0.05`,
   `park_bound 0.10` y `tilt_scale 0.4`.
2. **Features.** Mantiene un historial por equipo como `roi_engine`, alimentado
   **después** de estimar cada día, y llama a `build_adjustment_context`
   (sección 6).
3. **Tratamiento.** `p_T = clip(p_base + c·x, 0,01, 0,99)`, con el signo de la
   selección que aplica `adjust_model_probability`.

**Aserciones de paridad (abortan si fallan):**

1. `p_base` del h2h coincide con `binary_probs` de
   `walk_forward_backtest(results, liga, familia, params)` con tolerancia 1e-12.
   `p_base` de los totales y spreads, en las líneas fijas de paridad
   (NBA −4,5/220,5; NFL −3,5/44,5; NHL ±1,5/5,5; MLB ±1,5/8,5), coincide con
   `markets["spreads@L"|"totals@L"]`. Los spreads usan la vista **con**
   empates, por la lección de la re-ejecución del descanso.
2. **Paridad con producción de la capa:** para el `c` estimado en la última
   partición, en **todos** los partidos de test de la celda,
   `adjust_model_probability(p_base, mercado, selección, punto, home, away, ctx, risk_c)`
   coincide con `p_T` analítico (tolerancia 1e-12). `risk_c` es un `RiskConfig`
   con **solo** ese coeficiente distinto de 0 y las ventanas de la
   configuración. Esto prueba que la x del script es el término que serviría
   producción, recorte incluido.
3. Con todos los coeficientes a 0, `adjust_model_probability` devuelve
   `clip(p_base)`.

**La base se evalúa recortada** a [0,01; 0,99], igual que la
`adjusted_probability` servida con coeficientes nulos. Así el recorte no se
atribuye al tratamiento. La aserción 1 se hace antes de recortar.

### 7.3 Líneas de evaluación

- **h2h:** P(local) binaria del motor. Los empates quedan fuera, como en el motor
  (NHL antes de 2005, NFL).
- **Totales (4 y 10):** la capa necesita el `point`. En producción es la línea
  del **mercado**, que el histórico no tiene. Se usa una línea por partido fijada
  sin resultado: **L_i = ⌊μ_i⌋ + 0,5**, donde μ_i es el total esperado del modelo
  base.
  - En `NormalMarginAdapter`, μ es `scoring.expected_total`.
  - En `PoissonAdapter`, μ es λ_h + λ_a de `_rates`, con bono, abridor y parque.
  - Es la línea más próxima a la que cotizaría un mercado que coincidiera con el
    modelo. Con medio punto no hay empujes. P(Over) queda cerca de 0,5, que es
    donde el ajuste tiene más efecto.
  - **Limitación declarada:** aquí el término mide «ventana de 10 frente al
    modelo». En producción mediría «ventana de 10 frente al mercado». El informe
    secundario 7 lo evalúa con la línea capturada.
- **Spreads (restricción del criterio 6):**
  - NBA y NFL: línea del local s_i = −(⌊μ_margen,i⌋ + 0,5), por el mismo
    argumento;
  - NHL y MLB: ±1,5, la puck line y la run line que cotiza el mercado (como en el
    pre-registro del portero). Se evalúan las dos.

## 8. Brazos y control

| Brazo | Probabilidad | Parámetro |
|---|---|---|
| Base | clip(p_base) | — |
| **Tratamiento T** | clip(p_base + c·x) | c |
| **Control C** | clip(p_base + a) | a, constante (local en h2h; Over en totales) |

**Por qué hace falta el control:**

- en el 8, la media de x₈ es +0,07 a +0,34, así que un c > 0 puede ganar solo por
  corregir un `elo_home_adv` bajo. Es el confusor que infló `c` en el descanso
  (el sesgo de la base NBA iba de −0,034 a −0,002 según la época);
- en el 4 y el 10, la media de x₄ es +1 a +2 puntos en NBA y NFL, y +0,5 goles en
  NHL desde 2018. Un c > 0 puede ganar solo por corregir el nivel del total que
  las tasas arrastran con retraso. Es el confusor que absorbió el intercepto en
  el clima;
- en el 2, el 3 y el 9, la media es casi 0 por simetría. El control se mantiene
  igual, por coherencia y porque no cuesta nada.

## 9. Particiones y estimación

| Liga | A: test | B: test | C: test | Entrenamiento |
|---|---|---|---|---|
| NBA | 2012-10-01 – 2017-09-30 | 2017-10-01 – 2022-09-30 | 2022-10-01 – 2026-06-30 | tras el warmup – día anterior al test (precedente del descanso) |
| NHL | 2014-10-01 – 2018-09-30 | 2018-10-01 – 2022-09-30 | 2022-10-01 – 2026-06-30 | ídem (precedente del portero) |
| NFL | 2012-07-01 – 2017-06-30 | 2017-07-01 – 2022-06-30 | 2022-07-01 – 2026-06-30 | ídem. Cortes en julio, fuera de temporada |
| MLB | 2025 | 2026-01-01 – 2026-09-26 | — | 2023–2024 (A) y 2023–2025 (B), como el clima |

- El modelo base es **un único walk-forward**. Lo único que se estima por
  partición, y solo con los partidos de entrenamiento de la celda, es c (brazo
  T) y a (brazo C), minimizando el log loss medio del mercado de decisión.
- **Optimizador:** `scipy.optimize.minimize`, Nelder-Mead, punto de partida 0,
  `xatol=1e-7`, `fatol=1e-10`, `maxiter=2000`, sin límites ni restricción de
  signo (E9 del clima). Si no converge, el script aborta, y se trata como defecto
  de código.
- **Pérdida:** log loss binario con recorte 1e-12 (`tuning._binary_nll_series`).
- **Test combinado:** unión de los tests de la liga, sin solapes, con media por
  partido.

## 10. Criterios de aceptación, por celda (todos a la vez)

1. **Δ log loss (T − base) ≤ −0,002** en los **afectados** del test combinado.
2. **Δ < 0** en los afectados de **cada** partición.
3. **ECE(T) ≤ ECE(base)** en todo el test combinado del mercado de decisión, con
   `sqp.calibration.metrics.expected_calibration_error` por defecto (10 bins).
4. **c > 0 en todas las particiones.** Es la convención de cada forma funcional,
   según sus docstrings: mejor forma → más probabilidad; H2H del 70 % → «+»;
   más anotación → Over. No es un umbral nuevo.
5. **log loss(T) < log loss(C)** en todo el test combinado.
6. **Solo en los ajustes 2, 8 y 9:** Δ log loss medio en spreads (líneas de la
   sección 7.3), con el c de cada partición aplicado a su test, **≤ 0** en todo el
   test combinado. El código aplica el mismo coeficiente a los dos mercados, así
   que no se puede activar para uno solo.
7. **Holm:** la celda debe estar entre las rechazadas por el procedimiento de
   Holm de la sección 11.

Si falla cualquiera, la celda **RECHAZA**. Todas las celdas se publican y se
commitean, pasen o no.

**Origen de los umbrales:**

- **0,002** es `IMPROVEMENT_MARGIN` (`tuning.py:38`), el margen del abridor, el
  clima, el descanso y el portero.
- **Solo afectados** hereda la decisión E6 del operador en el clima,
  confirmada para el descanso. Aquí casi no cambia nada: en el 9 y el 4, casi
  todos los partidos son afectados, y en el 2, el 3, el 8 y el 10 lo son entre
  el 75 % y el 85 % (sección 13). Se mantiene por coherencia y **se marca para
  confirmación** (sección 18).
- **Criterios 2-6:** signos y comparaciones con 0, sin constantes nuevas.
- **Criterio 7:** sección 11.

## 11. Multiplicidad: Holm sobre las 24 celdas

- **Familia:** las 24 celdas que deciden (sección 5). Los informes secundarios no
  entran: no pueden producir un ACEPTA.
- **Hipótesis nula por celda:** H₀: Δ ≥ 0 (el término no mejora el log loss en
  los afectados). La alternativa es unilateral, Δ < 0, como en el test de signo
  del gate.
- **p-valor:** p = Φ(Δ̂ / EE), con Δ̂ el Δ del criterio 1 y EE el error estándar
  del bootstrap por días de la sección 12. Se usa la aproximación normal y no la
  proporción de réplicas porque, con 10.000 réplicas, el p mínimo resoluble
  (≈ 10⁻⁴) queda cerca del primer umbral de Holm (0,05/24 ≈ 0,0021).
- **α de familia = 0,05.** No es un número nuevo: es el único α de familia que
  el proyecto ha pre-registrado, el del prediction gate (pre-registro del
  2026-09-04 y `2026-09-25-repreregistro-gate-k52.md`, §3.3). Una corrección de
  Holm exige algún α, y el margen de 0,002 no lo es. Tomarlo del gate es la
  única elección con origen en el proyecto. **Se marca para confirmación del
  operador** (sección 18).
- **Procedimiento:** los p ordenados de menor a mayor, p₍₁₎ ≤ … ≤ p₍₂₄₎. Se
  rechaza H₍ₖ₎ mientras p₍ₖ₎ ≤ 0,05/(24 − k + 1). Al primer fallo se para. Se
  informan todos los p y los p ajustados de Holm.
- **Holm y el margen piden cosas distintas y se exigen las dos:** Holm, que el
  efecto exista controlando el error de familia; el margen, que sea lo bastante
  grande para importar. La estructura sigue la del gate, que exige a la vez
  significación y EV > 0.
- **K = 24 es un hecho de diseño** (seis ajustes supervivientes × cuatro ligas
  con potencia), fijado antes de medir. No se re-divide α sobre la marcha: si se
  añadiera una celda, haría falta un pre-registro nuevo.

## 12. Incertidumbre

Bootstrap por **bloques de fecha**: se remuestrean días UTC completos del test
combinado de la liga, con todos sus partidos afectados. Son 10.000 réplicas con
semilla 42, por celda. Se informan el IC95 percentil y el EE del Δ del criterio
1, de T − C (criterio 5) y del Δ de spreads (criterio 6). El EE del criterio 1 es
el que alimenta el p de Holm. Fuera de Holm, el IC **no es puerta**: exigir que
su extremo superior sea < 0 sería un umbral que no se ha fijado (E8 del clima).

## 13. Potencia (distribución de las features, sin resultados)

Calculada el 2026-09-27 con un script de consulta que reproduce las
definiciones de `rest_form.py` sobre los marcadores de partidos **anteriores**.
Ninguna feature se emparejó con el desenlace de su partido. Condiciones:
`warmup = 60`, fechas ≤ 2026-09-26, y L_i calculada con
`TeamScoringRates.expected_total` más el `home_scoring_bonus` de la familia. En
MLB es una aproximación: no incluye el abridor ni el parque, que `--pre` sí
incluirá.

**Qué efecto hace falta** (la misma derivación que en el clima, el descanso y
el portero):

- cerca de p = 0,5, corregir un error δ gana ≈ 2δ² de log loss, así que para
  0,002 hace falta δ_RMS ≈ 3,2 pp en los afectados;
- un término c·x da δ_RMS = |c|·RMS(x), así que el **coeficiente necesario** es
  c* ≈ 0,032/RMS(x), en información que el modelo **no** tenga ya;
- **ruido:** DE del Δ por partido ≈ 2δ ≈ 0,063, así que EE ≈ 0,063/√n_afectados
  (sin agrupar por fecha; el bootstrap da el valor bueno).

**Afectados en el test combinado y coeficiente necesario** (c* es la mediana
entre particiones, en probabilidad por unidad de x):

| Liga | 2 (forma) | 3 (H2H) | 8 (rol) | 9 (margen) | 4 (tendencia de totales) | 10 (tasa O/U) |
|---|---|---|---|---|---|---|
| NBA | 15.201 · c* 0,078 | 15.914 · 0,140 | 15.407 · 0,075 | 19.185 · 0,0035/pto | 19.205 · 0,0053/pto | 16.470 · 0,22 |
| NHL | 13.049 · 0,084 | 13.277 · 0,154 | 12.981 · 0,082 | 16.375 · 0,024/gol | 16.518 · 0,039/gol | 14.611 · 0,23 |
| NFL | 3.636 · 0,081 | 3.588 · 0,138 | 3.727 · 0,080 | 4.566 · 0,0038/pto | 4.564 · 0,0073/pto | 3.943 · 0,22 |
| MLB | 3.896 · 0,077 | 3.722 · 0,160 | 3.878 · 0,077 | 4.739 · 0,013/carrera | 4.767 · 0,026/carrera | 4.151 · 0,21 |

Test por partición:

| Liga | Partidos | Días |
|---|---|---|
| NBA | A 7.134 · B 6.621 · C 5.577 | 1.162 · 1.112 · 931 |
| NHL | A 5.780 · B 5.192 · C 5.978 | 957 · 872 · 952 |
| NFL | A 1.664 · B 1.601 · C 1.339 | 454 · 447 · 389 |
| MLB | A 2.434 · B 2.403 | 184 · 182 |

**Cómo leer c*.** Para aprobar el criterio 1 en la NBA harían falta, por encima
de lo que ya recoge el Elo, cualquiera de estos efectos:

- +7,8 pp de probabilidad por pasar de una forma de 0/5 a 5/5 (2);
- +3,5 pp por cada 10 puntos de diferencia de margen medio (9);
- +5,3 pp por cada 10 puntos de total medio por encima de la línea (4).

En MLB, el 9 pide +1,3 pp por carrera de diferencia de margen medio. El 3 pide
+14–16 pp entre un 100 % y un 50 % de victorias en el cara a cara. Son efectos
grandes para información que el Elo en buena parte ya tiene. Se deja dicho para
que un rechazo no se lea como «el efecto no existe».

**Error estándar ingenuo en el test combinado, y lo que pide Holm:**

| Liga | EE (0,063/√n) | Δ = −0,002 en unidades de EE | Δ necesario para el primer escalón de Holm (z = 2,86) |
|---|---|---|---|
| NBA | 0,00045 – 0,00051 | 3,9 – 4,4 | ≈ −0,0015 (manda el margen) |
| NHL | 0,00049 – 0,00055 | 3,6 – 4,1 | ≈ −0,0016 (manda el margen) |
| NFL | 0,00093 – 0,00105 | 1,9 – 2,2 | ≈ −0,0027 a −0,0030 |
| MLB | 0,00091 – 0,00101 | 2,0 – 2,2 | ≈ −0,0026 a −0,0029 |

En el último escalón de Holm (z = 1,645), a NFL y MLB les basta con
Δ ≈ −0,0016. **NBA y NHL tienen potencia.** NFL y MLB solo aprueban con efectos
algo mayores que el margen, o si otras celdas se rechazan antes en el
procedimiento. El agrupamiento por días inflará algo estos EE, sobre todo en
MLB (unos 13 partidos por día) y NFL (jornadas semanales). Se declara ahora
para que no se discuta después.

**Estructura de las features** (correlaciones entre features, sin resultado,
sobre el test combinado):

| Liga | x₂~x₉ | x₂~x₈ | x₈~x₉ | x₃~x₉ | x₄~x₁₀ | max \|x₄ − x₇\| | max \|x₉/2 − x₆\| |
|---|---:|---:|---:|---:|---:|---:|---:|
| NBA | 0,704 | 0,613 | 0,645 | 0,287 | 0,833 | 5,7·10⁻¹⁴ | 2,1·10⁻¹⁴ |
| NHL | 0,658 | 0,516 | 0,580 | 0,216 | 0,855 | 1,8·10⁻¹⁵ | 1,1·10⁻¹⁵ |
| NFL | 0,652 | 0,570 | 0,632 | 0,184 | 0,850 | 1,4·10⁻¹⁴ | 6,2·10⁻¹⁵ |
| MLB | 0,629 | 0,669 | 0,535 | 0,233 | 0,823 | 3,6·10⁻¹⁵ | 1,3·10⁻¹⁵ |

Las dos últimas columnas prueban las identidades de las secciones 2.3 y 2.4.
Media de x₈ por partición: NBA +0,22/+0,16/+0,15, NHL +0,13/+0,09/+0,11, NFL
+0,17/+0,09/+0,13, MLB +0,10/+0,07. Media de x₄: NBA +2,1/+1,9/+1,0 puntos, NFL
+2,2/+2,0/+0,7, NHL +0,06/+0,54/+0,60 goles, MLB −0,19/−0,13 (aproximada).
Secundarias: la WNBA tiene 250–340 afectados por partición (EE ≈ 0,0035–0,004);
la NCAAF, 750–950 (EE ≈ 0,002); el fútbol agrupado, 2.900–3.300 (EE ≈ 0,0011).

**El modo `--pre` debe reproducir** los recuentos y las correlaciones de 2, 3,
8 y 9 en las cuatro ligas, y los de 4 y 10 en NBA, NFL y NHL. En MLB, los de 4
y 10 cambiarán, porque la línea incluye abridor y parque. Si no coinciden, la
diferencia se documenta **antes** del modo completo.

## 14. Informes secundarios (no deciden nada)

1. `bias` del brazo base por partición y mercado.
2. Estimación conjunta base + a + c·x por partición: el c que queda con el
   intercepto controlado.
3. Perfil del log loss de **entrenamiento** en una rejilla de c (de −2·c* a
   +4·c*, con 25 puntos) por celda y partición: si es monótono a los dos lados del
   mínimo.
4. Δ en test por terciles de |x| (¿crece con la dosis?) y por signo de x.
5. Δ en test por temporada, marcando la burbuja de 2019-20 y el calendario de
   2020-21.
6. **Colinealidad en los aceptados:** si dos o más celdas de la misma liga
   aceptan, Δ del modelo conjunto con los c de la partición final, sin
   reestimar. Solo describe; no autoriza a activar los dos (sección 15).
7. **Semántica de producción, con la línea capturada:** los c de la última
   partición, evaluados sobre la muestra con cuotas (`roi_engine.load_closing_odds`
   y `_pick_main_lines`). Se usa la línea principal del consenso como `point`
   (totales) y como línea de spread. Se informa el n. Es log loss frente al
   resultado en esa submuestra, **no ventaja sobre el mercado**.
8. **Ajuste 4 contra el adaptador:** Δ de la base con `scoring_half_life_days`
   en su valor de producción frente al término 4. Solo describe: dice si lo que
   aporta el 4 es la recencia que ya podría aportar el adaptador.
9. **Transferencia sin reajustar:** c de la partición C de la NBA a WNBA 2025-26,
   NCAAB y WNCAAB; de la NFL a NCAAF. Fútbol agrupado con sus propias
   particiones (A: test 2024-07 – 2025-06; B: test 2025-07 – 2026-06), log loss a
   tres vías en h2h (la capa suma al local, resta al visitante y deja el
   empate), y Over en L_i.
10. Cobertura: afectados por celda, `None` por falta de historia y partidos de
    exhibición.

## 15. Si una celda acepta: qué haría falta para activarla

Esta medición no toca producción. Activar sería un cambio aparte, con
aprobación, en este orden:

1. **Mecanismo por liga (cambio de código previo, decisión del operador).** Hoy
   un coeficiente distinto de 0 en `default.yaml` actúa en todas las ligas y
   familias, incluido el tenis, donde el 8 y el 9 no tienen sentido (sección 1,
   hecho 2). Hace falta un override por liga, con tests que fijen que el resto de
   ligas sigue en 0. Por ejemplo, un bloque `adjustments:` por liga en
   `configs/leagues/ratings.yaml`, leído por `adjust_model_probability`. Cambia
   el contrato de configuración: es de la clase de escalado de
   `MODEL_ROUTING.md`, con revisión independiente. **Sin ese mecanismo no se
   activa nada**, aunque la celda acepte.
2. **Valor:** el c de la **última partición** (C; B en MLB), sin reestimar con
   todo el histórico ni usar el c conjunto del informe 2, como en el descanso.
   Ventana `n` = la de la configuración.
3. **Un término por canal y liga.** Canales: calidad reciente (2, 8, 9),
   cara a cara (3) y entorno de anotación (4, 10). Si en una misma liga aceptan
   varias celdas del mismo canal, se activa **una**: la de menor log loss de
   **entrenamiento** en la última partición. Así no se elige mirando el test.
   Activar dos del mismo canal exige un pre-registro conjunto. El 6 y el 7
   siguen en 0 siempre, por las identidades de la sección 2.
4. **Ajuste 4 o 10 aceptado en una liga con deriva:** antes de activarlo,
   decidir si lo correcto es el término en probabilidad o ajustar
   `scoring_half_life_days` en el adaptador. Lo segundo exigiría su propio
   pre-registro (**decisión del operador**, ver el informe 8).
5. **Recalibrar en staging** (`controlled-recalibration`) los calibradores de la
   liga y los mercados afectados, que se entrenaron sobre `adjusted_probability`
   sin el término. La promoción necesita aprobación humana.
6. **Paridad entre entrenamiento y servicio**, verificada y no supuesta: el run
   diario tiene que tener los resultados de ayer al construir `results`, con el
   orden `SETTLE_ALL` → `RUN_DIARIO_ALL`. Si no, las ventanas llegan con un día
   de retraso. Hace falta un test con una ventana conocida.
7. **Totales:** en producción el término se mide contra la línea del mercado. Si
   el informe 7 contradice el signo, se documenta antes de activar.
8. **Addenda previos** en «el modelo manda» (sección 17).

## 16. Compromisos de ejecución

- Script único: `scripts/research/measure_adjustment_battery.py`, con tres modos:
  - `--pre`: recuentos, distribución de x, correlaciones entre features,
    comprobación de las identidades 6≡9/2 y 7≡4, líneas L_i y hashes. Lee los
    marcadores **solo** para construir las features y el estado del modelo con
    días anteriores. **No empareja ninguna feature con su desenlace** ni calcula
    ninguna pérdida;
  - `--parity-only`: aserciones de la sección 7.2 con c = 0 y con un c
    arbitrario fijado en el script. No estima nada;
  - modo completo: el JSON (`--out`), con `--pre-json` para abortar si algún hash
    cambió. El informe `docs/research/2026-09-XX-resultado-bateria-ajustes.md`
    se redacta a partir del JSON; el script no lo genera.
- Se commitea antes de ejecutar el modo completo.
- **Una sola ejecución** para las 24 celdas y los informes secundarios. Sin
  miradas intermedias, sin cambiar particiones, ventanas, líneas, ligas ni
  familia después de ver nada.
- **Regla de re-ejecución (E10):** solo se repite si aparece un defecto de
  **código o datos** demostrable sin mirar el resultado: paridad rota, filas mal
  ordenadas o unidas, hashes distintos de los de `--pre`, o un optimizador que no
  converge. Se documenta el defecto y se commitean las dos salidas. Un resultado
  adverso no es motivo para repetir. Si hay que diagnosticar, se hace a ciegas
  (solo longitudes e índices), como en el descanso.
- Las enmiendas, si las hay, se añaden al final **antes** del modo completo y
  mandan sobre el texto. En particular, si el portero NHL se activa antes de
  ejecutar esto, la base NHL cambia: se enmienda la referencia de código y se
  repite `--pre`.
- Reabrir una celda rechazada exige una forma funcional **distinta** o una
  ventana distinta, pre-registrada y sobre datos nuevos.

## 17. Interacciones con los tests pre-registrados en curso

**La medición no interfiere con ninguno:** solo lee el histórico. No toca el
stream servido, `data/bets/prediction_gate.json`, los calibradores ni la
configuración.

- **Prediction gate (K = 52).** Usa `model_probability`, el modelo puro, en el
  test de signo y en `ev_flat`. La capa de ajustes **no** lo toca. Por eso,
  activar un término **no cambia la `d`** de ningún corte, a diferencia del
  `RestModel`, que vive en el adaptador. Tampoco cambia la población del stream
  (se sirven todas las cotizaciones, antes del filtro de edge) ni el número de
  cortes, así que K no cambia. No hace falta addendum por criterio. Se recomienda
  una nota informativa con la fecha, para que nadie atribuya al modelo puro un
  cambio que no tuvo (**decisión del operador**).
- **«El modelo manda»** (≥ 3.402 eventos, ≈ 2026-11-17/24). Evalúa
  `p_cal = 2·calibrated_probability − implied_probability_novig`, que hereda la
  capa. Activar antes de su ejecución cambiaría `p_cal` en las ligas afectadas
  dentro de su ventana. Hay dos opciones:
  - activar con un addendum de cambio de régimen previo, como los tres del
    2026-09-26;
  - esperar a que se ejecute.
  **Decisión del operador.** Este documento recomienda esperar, si la ejecución
  queda a menos de dos meses: la capa también exige recalibrar (sección 15.5), y
  un cambio doble dentro de la ventana complica leer ese test.
- **Feature-shadow** (2026-09-16 a 2027-09-16): esta batería no lo toca. Se
  declara el solapamiento de ideas (sección 4).
- **Portero NHL:** ver la sección 16 (enmienda de la base si se activa antes).

## 18. Decisiones del operador que quedan marcadas

1. **α de familia = 0,05 para Holm**, tomado del gate (sección 11). La
   alternativa sería otro α con origen explícito. Sin α, Holm no se puede
   aplicar.
2. **Criterio 1 solo sobre los afectados** (herencia de E6). La alternativa es
   medirlo sobre todo el test combinado.
3. **Ligas que deciden:** NBA, NHL, NFL y MLB (24 celdas). Añadir o quitar ligas
   cambia K y hay que hacerlo **antes** de `--pre`.
4. **Activación por liga:** exige el mecanismo de override por liga (sección
   15.1), un cambio de código aparte con revisión. Sin él no se activa nada.
5. **Momento de una eventual activación** respecto a «el modelo manda», y nota
   informativa en el gate (sección 17).
6. **Descanso en NHL y MLB:** queda sin medir tras descartar el 1. ¿Se abre un
   pre-registro propio con una forma acotada en el `PoissonAdapter`?
7. **Confirmación prospectiva:** por la exposición previa de la muestra (sección
   4), ¿un ACEPTA activa directamente, como el descanso, o espera a confirmarse
   con la temporada 2026-27? La segunda opción tiene poca potencia: unos 1.300
   partidos NBA dan un EE ≈ 0,0018. Este documento recomienda la primera, con la
   vigilancia de la sección 15.

---

Relacionado: [[2026-09-26-preregistro-clima-mlb]], [[2026-09-26-resultado-clima-mlb]],
[[2026-09-26-preregistro-descanso-basket]], [[2026-09-26-resultado-descanso-basket]],
[[2026-09-26-preregistro-portero-nhl]], [[2026-09-25-repreregistro-gate-k52]],
[[2026-08-26-preregistro-el-modelo-manda]].

**Decisiones del operador resueltas el 2026-09-27, antes de implementar:**
1. **Holm sobre las 24 celdas con α de familia 0,05**, el mismo ya aprobado para el prediction gate, exigido **junto** al margen 0,002.
2. **Medir ya y activar después:** la medición no toca producción. Si se acepta alguna celda, la activación (que además exige un mecanismo de coeficientes por liga, con revisión) espera a que se ejecute «el modelo manda» o lleva un addendum previo.
3. **El descanso en NHL y MLB** se mide aparte con el `RestModel` acotado, como en NBA; NHL primero. Pasa a la cola.

---

## Enmienda 1 (2026-10-08, antes de implementar el script y antes de `--pre`; redactada por Fable)

Cumple la condición de la revisión de Fable del 2026-09-30 que dictaminó la activación del tilt NHL («enmiendas de base del portero y la batería»; la del portero es la Enmienda 3 de `2026-09-26-preregistro-portero-nhl.md`). También cumple la sección 16, que ya preveía enmendar la referencia de código si la base NHL cambiaba antes de ejecutar.

**Qué no se ha hecho.** El script `scripts/research/measure_adjustment_battery.py` no existe todavía. No se ha ejecutado `--pre` ni ninguna medición. No se ha emparejado ninguna feature con ningún desenlace. Para esta enmienda solo se ha leído código, configuración y documentos, y se han resuelto los parámetros de las cuatro ligas que deciden (sin leer ningún marcador).

**Qué no cambia:**

- los criterios de la sección 10, Holm (sección 11) y el bootstrap (sección 12);
- el descarte de la sección 2, los seis ajustes, las ventanas `n`, las ligas y K = 24;
- las particiones de la sección 9, el warmup, el optimizador y la pérdida;
- las líneas de evaluación de la sección 7.3 (su definición; el punto c dice qué valores cambian);
- los informes secundarios de la sección 14 y la sección 15.

**Dónde manda.** Sobre la línea «Código de referencia» del encabezado, el punto 1 de la sección 7.2, la sección 16 y el último punto de la sección 17, en lo que fija.

### (a) Commits posteriores a `f9658ce` que tocan la base o el motor

`git log --oneline f9658ce..HEAD -- configs/ src/sqp/` (HEAD al redactar: `df84789`):

| Commit | Qué cambia | Efecto en la base de la batería |
|---|---|---|
| `d349be7` | KI-070: `RestModel` usa la fecha más reciente **estrictamente anterior** a `game_date`. `PoissonAdapter` gana `rest_elo_per_day` (por defecto 0) | **Ninguno en el motor.** El walk-forward nunca observa un partido del día antes de estimar ese día, así que KI-070 es inerte bit a bit (hashes NBA/NHL/MLB idénticos, declarados en el commit). `rest_elo_per_day` vale 0 o no existe en NHL y MLB, así que sumar 0,0 a `diff` es la identidad. La paridad 1 lo comprueba igualmente |
| `c390c2f` | `nhl.tilt_scale: 0.439` en `configs/leagues/ratings.yaml` (antes 0,9, el de `FAMILY_PARAMS["hockey"]`) | **Cambia la base NHL.** Ver los puntos b a e |
| `ea5e651` | Índice por equipo (`TeamHistoryIndex`) en `rest_form.py`; `build_adjustment_context` acepta un `team_index` opcional | **Ninguno en las features.** Salida bit a bit idéntica (`tests/test_rest_form_index_equivalence.py`). La paridad 2 lo comprueba igualmente |
| `1932e68` | Reanudación del backfill de porteros | Ninguno: no toca el motor ni la capa |

NBA, NFL y MLB tienen, por tanto, la misma base que en `f9658ce`. Solo cambia la NHL.

### (b) La base nueva

- **Base:** la configuración de producción del **commit vigente al ejecutar `--pre`**, no `f9658ce`. Por liga: `_league_meta(liga)["league_params"]` (`src/sqp/pipeline/daily.py:75`) + `get_adapter(liga, familia, league_params)` (`src/sqp/sports/registry.py:107`), en ese commit.
- **El portero NHL no forma parte de la base.** No está implementado en el adaptador (no existe `goalie_beta` en `src/sqp/sports/` ni en `configs/`). La captura diaria de probables no toca ninguna probabilidad. Si se activara antes del modo completo, haría falta otra enmienda y repetir `--pre`, como ya dice la sección 16.
- **Aserción (sustituye a la referencia a `f9658ce`).** `--pre` y el modo completo registran en el JSON los parámetros resueltos de las cuatro ligas que deciden y **abortan** si no coinciden **exactamente** con estos dos niveles:
  1. `_league_meta(liga).get("league_params")`:
     - NBA: `{"rest_points_per_day": 0.795}`;
     - NHL: `{"elo_home_adv": 15.0, "tilt_scale": 0.439}`;
     - NFL: `None` (sin entrada en `ratings.yaml` ni en `SPORT_KEYS`);
     - MLB: `{"park_bound": 0.1, "pitcher_bound": 0.05, "pitcher_prior_starts": 5.0, "tilt_scale": 0.4}`.
  2. `adapter.params` efectivo (familia + `LEAGUE_OVERRIDES` + liga):
     - NBA (`BasketballAdapter`): `avg_total 224.0`, `elo_home_adv 70`, `elo_k 20`, `elo_mov True`, `margin_sigma 13.0`, `points_per_elo 0.028`, `rest_points_per_day 0.795`, `scoring_half_life_days 180.0`, `total_sigma 22.0`, y ninguna otra clave;
     - NHL (`HockeyAdapter`): `avg_total 6.1`, `elo_home_adv 15.0`, `elo_k 10`, `home_scoring_bonus 0.1`, `max_score 15`, **`tilt_scale 0.439`**, y ninguna otra clave (en particular, sin `rest_elo_per_day` ni `goalie_beta`);
     - NFL (`FootballAdapter`): `avg_total 44.0`, `elo_home_adv 55`, `elo_k 24`, `elo_mov True`, `margin_sigma 13.5`, `points_per_elo 0.025`, `total_sigma 13.5`, y ninguna otra clave;
     - MLB (`BaseballAdapter`): `avg_total 8.7`, `dispersion_k 3.8`, `elo_home_adv 25`, `elo_k 6`, `home_scoring_bonus 0.1`, `max_score 25`, `park_bound 0.1`, `pitcher_bound 0.05`, `pitcher_prior_starts 5.0`, `tilt_scale 0.4`, y ninguna otra clave (sin `pitcher_signal`, así que la señal es `"ra"`; sin `rest_elo_per_day`).

  Comprobado hoy en `df84789` resolviendo solo la configuración. **Un `tilt_scale` NHL de 0,9 aborta**, igual que cualquier otro valor distinto de 0,439.
- **HEAD y árbol limpio** (mecanismo de la Enmienda 2(b) y 3(f) del portero). El JSON de `--pre` registra `git rev-parse HEAD` y `git status --porcelain` de todo el repositorio, que tiene que salir vacío. El modo completo **aborta** si el HEAD difiere del de `--pre-json` o si hay cualquier cambio sin commitear en `src/`, `configs/` o `scripts/research/`.
- **Trampas que el script debe evitar** (las mismas que en el portero):
  - `FAMILY_PARAMS["hockey"]` sigue en 0,9: `get_adapter("nhl", "hockey")` sin `league_params` devuelve la base **vieja**. Lo mismo para MLB (0,8 de familia frente a 0,4);
  - `measure_tilt_nhl.load_league` aborta por diseño (su invariante es 0,9) y no se reutiliza;
  - ningún literal de tilt en funciones auxiliares: se pasa siempre el valor **resuelto**.
- **Sin base alternativa.** El script no calcula la batería con `tilt_scale` 0,9 en ningún modo, ni como informe secundario. Una segunda base sería un grado de libertad (elegir después la base con la que se lee el resultado).

### (c) Qué cambia en la NHL con el tilt nuevo, y qué no

El tilt solo reparte el total esperado entre los dos equipos (`PoissonAdapter._rates`, `src/sqp/sports/adapters.py:120-123`):

    tilt   = clip((p_home − 0,5)·tilt_scale, −0,30, 0,30)
    λ_home = avg·(0,5 + tilt) + home_scoring_bonus
    λ_away = avg·(0,5 − tilt)

1. **μ y L_i de los totales NHL no cambian.** μ_i = λ_home + λ_away = avg_i + `home_scoring_bonus` no depende de `tilt_scale` (el suelo `max(0,1, ·)` exigiría avg < 0,5 goles y no se alcanza). Por tanto **L_i = ⌊μ_i⌋ + 0,5 (sección 7.3) es idéntica con 0,9 y con 0,439**, y los afectados de los ajustes 4 y 10, que dependen de L_i, también. La P(Over) de la base en L_i solo cambia por el truncamiento en `max_score 15`: el resultado del tilt midió máx. |Δ P(over)| ≤ 2,3·10⁻⁵ (su informe 9). **Las celdas NHL de los ajustes 4 y 10 tienen, a efectos prácticos, la misma base que en `f9658ce`.** `--pre` lo aserta: en cada partido NHL, |λ_home + λ_away − (μ_scoring,i + 0,10)| ≤ 1e-12, donde μ_scoring,i es `scoring.expected_total` en ese partido.
2. **Lo que sí cambia:**
   - p_base del moneyline NHL, y con ella las celdas NHL de los ajustes 2, 3, 8 y 9 (la dispersión pasa de d.t. 0,175 a 0,091 en el test combinado, tabla de la Enmienda 3(d) del portero);
   - p_base de la puck line ±1,5, que entra en el criterio 6 de los ajustes 2, 8 y 9 en la NHL. Las líneas ±1,5 son fijas y no cambian.
3. **Las features no cambian.** Salen de los marcadores anteriores y no dependen del modelo. Los recuentos, las distribuciones de x y las correlaciones NHL de la sección 13 siguen valiendo, y c* también, porque depende de RMS(x). `--pre` debe reproducirlos en la NHL con la regla de la sección 13, sin excepción por el tilt.
4. **Paridad.** La aserción 1 de la sección 7.2 se hace contra `walk_forward_backtest(results, liga, familia, params)` con los `params` **resueltos** del punto b (0,439 en la NHL), en h2h y en `spreads@±1.5` / `totals@5.5` NHL. Una reconstrucción con 0,9 rompería la paridad 1, que actúa así de guarda adicional. La aserción 2 (capa contra `adjust_model_probability`) no depende del tilt, salvo por el p_base de entrada, que es el nuevo. Se mantiene la nota del tilt: en la NHL, los empates anteriores a 2005 quedan fuera de `binary_probs` y solo afectan a entrenamiento.

### (d) Exposición previa (completa la sección 4)

Desde el 2026-09-27, quien redacta y quien ejecuta conocen del histórico NHL, por el resultado del tilt (`2026-09-30-resultado-tilt-nhl.md`) y la Enmienda 3 del portero, datos de la **base**, no de las features:

- log loss de la base por partición, con 0,9 y con 0,439; AUC 0,6006, que el tilt no cambia;
- pendiente de calibración 0,97 con 0,439;
- sesgo de la base nueva: infraestima al local en ≈ 1 pp en el combinado;
- en la puck line con línea de mercado, Δ = +0,0037 (n = 258).

Ninguno empareja x₂, x₃, x₄, x₈, x₉ ni x₁₀ con un desenlace. Se evalúa honestamente si el cambio de base abre un grado de libertad o un sesgo en las 6 celdas NHL:

1. **No hay elección de base.** La base es la de producción al ejecutar, por una regla escrita en la sección 16 antes de que existiera el tilt. 0,439 sale del pre-registro propio del tilt (`t` de la partición C, redondeado) y no se eligió mirando la batería. Al prohibir la base alternativa (punto b), no queda ninguna bifurcación.
2. **La base NHL no es estrictamente fuera de muestra en los tests A y B.** El tilt usó las **mismas** particiones NHL (tests 5.780 / 5.192 / 5.978), y `t_C` se estimó con entrenamiento hasta el 2022-09-30, que contiene los tests A y B de la batería. **No es una propiedad nueva:** la base de `f9658ce` ya la tenía en la NBA (`rest_points_per_day 0,795` es la c de la partición C, entrenada hasta el 2022-09-30) y en la MLB (`pitcher_bound 0,05` es el mínimo del walk-forward sobre todo el histórico MLB). Su efecto es despreciable: es un solo escalar, estimado con más de 10.000 partidos, estable entre particiones (0,437 / 0,428 / 0,439), y lo comparten la base, T y C. No da a T ninguna ventaja sobre la base ni sobre C, y no cambia la pregunta, que es el valor **incremental** de c·x sobre la base de producción.
3. **El cambio corrige un sesgo contra las celdas NHL de calidad, no introduce uno a favor.** Con 0,9 la base era sobreconfiada (pendiente 0,45). x₂ y x₉ están correlacionadas con la diferencia de Elo (sección 13), así que el log loss de entrenamiento habría empujado c hacia valores negativos solo para aplanar el Elo: el criterio 4 (c > 0) habría rechazado por una razón ajena a la feature. Con 0,439 (pendiente 0,97) ese canal de recalibración queda cerrado, como en la Enmienda 3(e) del portero. Un ACEPTA NHL de calidad tiene que venir de discriminación o de nivel.
4. **Queda un canal de nivel, y su guarda ya existe.** La base nueva infraestima al local en ≈ 1 pp. La media de x₈ en la NHL es +0,09 a +0,13 (sección 13), así que un c > 0 en el ajuste 8 puede recoger parte de ese nivel. Corregir 1 pp vale ≈ 0,0002 de log loss, una décima parte del margen, así que no sostiene por sí solo el criterio 1. El criterio 5 (T frente a C) es exactamente la guarda que separa forma por rol de nivel, y no se cambia. x₂, x₃ y x₉ tienen media ≈ 0 por simetría y no tienen ese canal. **Lectura declarada ahora, que no es criterio:** si la celda NHL del ajuste 8 acepta con T − C estrecho y el informe secundario 1 muestra que el sesgo de la base explica la ganancia, el informe del resultado lo dirá.
5. **Puck line.** El dato de Δ = +0,0037 con línea de mercado es de la base, sobre 258 partidos, y no sobre las líneas ±1,5 del criterio 6 en todo el test. No se usa para nada.

Conclusión: el cambio de base no abre ningún grado de libertad y no sesga las celdas NHL a favor de T. Se mantiene la valoración de la sección 4: un ACEPTA sobre esta muestra es una evidencia algo más débil que sobre una muestra virgen, por la exposición ya declarada allí.

### (e) Criterio 6 con dos líneas (aclaración imprescindible, sin cambiar el criterio)

La sección 7.3 dice para NHL y MLB que «se evalúan las dos» líneas ±1,5, pero el criterio 6 habla de un único «Δ log loss medio en spreads». Para que no quede una lectura por elegir después de ver el resultado, se fija la del precedente (criterio 6 del descanso NHL, tomado del 6b del portero): en NHL y MLB, el Δ del criterio 6 es la **media de `spreads@-1.5` y `spreads@+1.5`** (línea del local), con el mismo peso por partido, y debe ser ≤ 0 en todo el test combinado. En NBA y NFL hay una sola línea por partido, s_i. El script informa además el Δ de cada línea por separado, sin valor de decisión.

### (f) Corte de datos

**Se mantiene `date ≤ 2026-09-26`.** Las razones:

- los recuentos de las secciones 5 y 13 y la partición B de la MLB (que termina el 2026-09-26) están fijados con ese corte;
- ampliarlo solo añadiría partidos al test B de la MLB, que no lo necesita por diseño, y abriría un cambio de partición sin ninguna ganancia;
- no se ha medido nada, así que mantenerlo no protege ningún resultado: simplemente no hay motivo para cambiarlo.

El corte es sobre `date`, no sobre la fecha de ingesta. Las filas con `date ≤ 2026-09-26` que la ingesta diaria haya añadido después del 2026-09-27 (precedente: `results_nhl.csv` pasó de 32.888 a 32.902 filas) entran en la muestra. `--pre` informa, por liga y por partición, la diferencia de filas con la tabla de la sección 5 y con los tests de la sección 13. Si alguna cae dentro de una partición de test, se documenta en una enmienda **antes** del modo completo, como en la Enmienda 1 del descanso NHL. No se corrige ni se excluye nada por esa diferencia.

### (g) Ejecución (concreta la sección 16)

- **Instantánea de entradas.** Se aplica el mismo mecanismo que el operador aprobó el 2026-10-01 para el portero: antes del `--pre` se copian a una carpeta fija fuera de `data/` todos los ficheros que lee el script, y `--pre` y el modo completo se ejecutan con `--data-root` apuntando a ella. Los ficheros son:
  - `results_*.csv` de las cuatro ligas que deciden y de las secundarias de la sección 14 (WNBA, NCAAB, WNCAAB, NCAAF y las 11 de fútbol);
  - los almacenes de abridores y de FIP de la MLB que usan `StartersStore.attach` y `StarterFIPStore.attach` (sección 6);
  - los ficheros de cuotas de cierre que resuelva `roi_engine.load_closing_odds` para el informe secundario 7.

  `ratings.yaml`, `default.yaml` y el código se leen del árbol del commit vigente, con el árbol limpio.
- **JSON de `--pre`:** HEAD, `git status --porcelain` (vacío), la ruta de la instantánea, el SHA-256 y las filas de cada fichero, el SHA-256 de `configs/leagues/ratings.yaml` y de `configs/default.yaml` (redundante con el HEAD, por trazabilidad), los parámetros resueltos del punto b para las cuatro ligas y, sin aserción, los de las ligas secundarias.
- El modo completo recalcula todo lo anterior y **aborta** si algo difiere. Es la causa «hashes distintos de los de `--pre`» de E10. Si aborta, no se ha medido nada: se repite `--pre` y se ejecuta el modo completo inmediatamente después.
- Se mantiene lo demás de la sección 16: script commiteado antes del modo completo, una sola ejecución y la regla E10.

### (h) Decisiones del operador

Ninguna nueva. Todo lo de esta enmienda se decide aquí, sin mirar resultados: la base y su aserción, la prohibición de una base alternativa, la invariancia de L_i en la NHL, la exposición, la lectura del criterio 6 con dos líneas, el corte de datos y la instantánea (que extiende a esta medición un mecanismo ya aprobado).

---

## Enmienda 2 (2026-10-08, antes de `--pre`; redactada por Fable)

Sale de la revisión de Fable del script `scripts/research/measure_adjustment_battery.py`, que dictaminó APTO CON CAMBIOS. Deja por escrito, antes de medir, las lecturas que el texto dejaba abiertas y lo que el script hace en los informes secundarios, para que ninguna se pueda elegir después de ver un resultado.

**Qué se ha hecho hasta ahora.** Solo `--parity-only` sobre los datos reales: PARIDAD OK en las cuatro ligas, con desviación máxima 0,0. Ese modo no estima nada, no calcula ninguna pérdida y no empareja ninguna feature con su desenlace. No se ha ejecutado `--pre` ni el modo completo. Ninguna decisión de esta enmienda sale de un resultado.

**Qué no cambia:**

- los criterios de la sección 10, Holm con K = 24 y α = 0,05 (sección 11) y el bootstrap (sección 12, que aquí solo se concreta);
- los seis ajustes, las ventanas `n`, las cuatro ligas que deciden, las particiones y la línea de cada mercado (secciones 6, 7.3 y 9);
- la base y sus aserciones, la instantánea y el corte de datos (Enmienda 1).

**Dónde manda.** Sobre la sección 14 (informes 5, 7, 8, 9 y 10), sobre la sección 16 y sobre la Enmienda 1(g), en lo que fija.

### (a) El fútbol agrupado sale del informe 9

Se retira el fútbol agrupado del informe secundario 9: particiones propias, log loss a tres vías en h2h y Over en L_i. **No se implementa ni se ejecuta.** Lo decidió el orquestador el 2026-10-08, siguiendo la recomendación de la revisión. Las razones:

- es un informe secundario: no puede dar un ACEPTA y no entra en Holm, así que retirarlo no cambia K ni ninguna celda;
- la sección 5 ya declara que lo que mide no es lo que mueve la capa: la capa suma al local y resta al visitante sin tocar el empate, y el motor evalúa P(local | no empate). Las ligas son heterogéneas, y la MLS ya tiene Elo local/visitante;
- implementarlo exigiría código nuevo sin paridad contra el motor: log loss a tres vías y estimación agrupada de 11 ligas. Si fallara, obligaría a re-ejecutar por E10 después de haber visto las 24 celdas.

El informe 9 queda como transferencia sin reajustar: NBA → WNBA, NCAAB y WNCAAB, y NFL → NCAAF (punto e). Los `results_*.csv` de fútbol pueden seguir en la instantánea y en el manifiesto de la Enmienda 1(g), solo por trazabilidad: no se usan para medir nada. Medir la capa en el fútbol exige un pre-registro propio.

### (b) Lecturas fijadas

Estas son las lecturas que aplica el script, por número de ambigüedad de la revisión:

3. **Recuentos de `--pre`.** Se cuentan sobre todos los partidos de test de cada partición, empates incluidos, porque `--pre` no mira marcadores. En el modo completo, el mercado h2h deja fuera los empates, como `binary_probs`. Por eso, en la NFL, los afectados de los ajustes 2, 3, 8 y 9 en el modo completo pueden ser unos pocos menos que en `--pre`. Esa diferencia no es un defecto. En totales no hay empujes, porque L_i es semientera.
5. **A qué partidos se aplica cada criterio.**
   - Criterios 1 y 2: solo los afectados del test combinado y de cada partición.
   - Criterios 3 y 5: todos los partidos válidos del test combinado en el mercado de decisión.
6. **Criterio 6.**
   - Se calcula sobre todos los partidos de test con spread válido.
   - Donde x no está disponible, Δ = 0, porque el término vale 0 en producción.
   - En NHL y MLB es la media con igual peso de `spreads@-1.5` y `spreads@+1.5` (Enmienda 1(e)). Un partido entra solo si es válido en las dos líneas.
7. **Bootstrap.**
   - Se remuestrean todos los días UTC del test combinado de la liga, también los que no tienen ningún afectado.
   - En cada réplica, el estadístico es Σnum/Σden. Para el criterio 1 es la media de Δ sobre los afectados remuestreados.
   - Las 10.000 réplicas salen de un único generador con semilla 42 por liga, en bloques de 250, compartido por todas las celdas y estadísticos de esa liga. Equivale a usar la semilla 42 por celda, porque todas las celdas de una liga remuestrean los mismos días.
   - Las réplicas con denominador 0 se descartan, y se informa `n_replicas`.
   - Si el EE no es utilizable (ausente, no finito o ≤ 0), p = 1 y la celda no se rechaza.
8. **Holm.** Los empates de p se ordenan por el nombre de la celda (`adj{k}_{liga}`). El p ajustado es el máximo acumulado de min(1, (K − k + 1)·p₍ₖ₎).
11. **Paridades 2 y 3 en el modo completo.** El contexto se reconstruye con el historial final, filtrado a `d < rd` por `roi_engine._prior_games`. Es idéntico al prior del recorrido incremental: los mismos partidos y en el mismo orden. Se comprueban **todos** los partidos de test.
12. **Informe 7.**
    - El emparejamiento usa `_match_index` y `_match_result` de `roi_engine`, recorriendo los resultados con la misma clave de orden que `roi_engine.backtest_league` (`src/sqp/backtesting/roi_engine.py:289-294`): (date, home, away, game_id, home_score, away_score).
    - Ante una doble jornada ambigua, no se empareja.
    - El spread principal del consenso (`_pick_main_lines`) cambia de signo cuando el local del feed no es el local del resultado.
    - Se usa el c de la última partición.
13. **Informe 8.** Solo se calcula en las ligas que deciden y tienen `scoring_half_life_days` > 0, es decir, solo en la NBA. En las demás se informa «no aplica».
14. **Informe 5.**
    - Las marcas de la burbuja 2019-20 y del calendario 2020-21 solo se ponen en NBA y NHL.
    - NBA, NHL y NFL se etiquetan por el año de inicio de la temporada (cambio en agosto); la MLB, por año natural.
15. **Informe 9.** Se usa el c de la última partición (C) de la NBA y de la NFL.

### (c) `--parity-stride N`

Solo existe en `--parity-only`, que no decide nada: argparse lo rechaza en `--pre` y en el modo completo. Con N > 1, las features y la paridad de la capa se comprueban en uno de cada N partidos de test. La paridad 1 (motor) sigue siendo completa, y el JSON registra `stride_features`. Las ejecuciones previas de `--parity-only` con stride 20 en NBA y NHL no sustituyen a ninguna aserción del modo completo: este comprueba las paridades 1, 2 y 3 en todos los partidos.

### (d) Errores en los informes secundarios

- **Ninguna de las 24 celdas pasa por `_safe_informe`.** Si falla algo en el camino de una celda, el script aborta: estimación, criterios, bootstrap, Holm y paridades. `_safe_informe` solo envuelve los informes 1 a 10 y la carga de cuotas capturadas del informe 7. Esa carga no alimenta ninguna celda.
- Un informe secundario que falla deja en el JSON, en su propia entrada, el tipo de la excepción, el mensaje y el traceback. Si falla la carga de cuotas, el error queda en el informe 7, que no puede salir como `n_emparejados: 0`. Un informe parcial lo dice explícitamente: por ejemplo, una no convergencia de la estimación conjunta (informe 2) se anota por ajuste y partición.
- **Re-ejecución para completar un informe secundario.** Es un defecto de código en el sentido de E10, demostrable sin mirar los resultados, porque basta con la excepción. Solo se permite con tres condiciones:
  1. la corrección no toca código del camino de las celdas;
  2. la segunda ejecución usa la misma instantánea, con los mismos hashes, y se asierta que las 24 celdas, el bloque de Holm y los bloques de paridad salen **idénticos bit a bit** a los de la primera;
  3. se commitean las dos salidas con el defecto documentado.

  Si las celdas no salen idénticas, eso es en sí un defecto que se diagnostica a ciegas, como dice la sección 16.

### (e) Informe 9: alcance de la WNBA

En la WNBA solo se evalúan los partidos con `date ≥ 2025-01-01`: las temporadas 2025 y 2026, que es la «WNBA 2025-26» de la sección 14.9. El estado del modelo y las features se siguen construyendo con todo el histórico, con el mismo warmup. NCAAB y WNCAAB, que solo tienen la temporada 2025-26, y NCAAF se evalúan en todo su histórico tras el warmup.

### (f) Informe 8: nueva definición (sustituye a la de la sección 14.8)

La comparación en una línea fija de totales sobre 2002-2026 mediría sobre todo el nivel del total, que se movió entre unos 185 y 235 puntos, y no la recencia. Por eso se sustituye por esta:

- se construye un segundo recorrido de la base NBA, idéntico al de producción salvo `scoring_half_life_days = 0`. Es un informe secundario y no vale como base alternativa para ninguna celda (Enmienda 1(b));
- en cada partido, la P(Over) sin decaimiento se evalúa en la L_i **de la base de producción**, no en la del segundo recorrido: `normal_total_probs(μ_sin, total_sigma, L_i)["over"]`. Así las dos bases se comparan en la misma línea;
- sobre el test combinado de la NBA se informa Δ = log loss(base de producción) − log loss(base sin decaimiento), en todos los partidos válidos y en los afectados del ajuste 4, junto al Δ del término 4 en esos mismos afectados. Es descriptivo y no condiciona nada.

### (g) Informe 10: los partidos de exhibición no están disponibles

`ResultsStore` no guarda el tipo de partido (sus columnas son `date`, `home`, `away`, `game_id`, `home_score`, `away_score`, `neutral` e `ingested_at`). El informe 10 declara «exhibición: no disponible en `ResultsStore`». Los partidos en campo neutral se informan aparte, con su propio nombre, y no se presentan como exhibiciones.

### (h) `--data-root` obligatorio

En `--pre` y en el modo completo, `--data-root` es obligatorio y tiene que apuntar a la instantánea de la Enmienda 1(g). Si resuelve a la raíz del repositorio (`sqp.config.ROOT`), es decir, a los datos vivos, el script aborta. La instantánea va fuera del repositorio o en una ruta ignorada por git, porque `--pre` exige `git status --porcelain` vacío en todo el repositorio (Enmienda 1(b)). Eso incluye ficheros sin seguimiento ajenos a esta medición, y la lectura literal se mantiene. El modo completo, además, registra en su JSON:

- los parámetros resueltos;
- el manifiesto de hashes;
- los SHA-256 de la configuración;
- el `git status --porcelain` de `src/`, `configs/` y `scripts/research/`;
- el SHA-256 del fichero de `--pre-json`.

Entre `--pre` y el modo completo no se commitea nada, porque el HEAD tiene que coincidir.

### (i) Qué añade `--pre` para la Enmienda 1(f)

Por liga y por partición, `--pre` informa:

- las filas con `ingested_at` posterior al 2026-09-27;
- los duplicados por `(date, home, away)` y por `game_id`.

Así se atribuyen las diferencias con las secciones 5 y 13. Lo ya visto en `--parity-only`, 4.850 partidos de test MLB frente a 4.837, queda pendiente de esa atribución. Las filas de ingesta tardía no se corrigen ni se excluyen (Enmienda 1(f)). Un duplicado sería un defecto de datos: se documenta y se resuelve en la Enmienda 3, sin mirar resultados. **La Enmienda 3 se redacta después de `--pre` y antes del modo completo**, con las diferencias por partición, su atribución y cualquier recuento o correlación que no coincida con la sección 13.

### (j) Decisiones del operador

La retirada del fútbol agrupado (punto a) la decidió el orquestador siguiendo la recomendación de la revisión. Si el operador prefiere implementarlo, tiene que decirlo **antes** de `--pre`, y entonces esta enmienda se sustituye por otra que lo comprometa con código, tests y revisión. Lo demás de esta enmienda son lecturas técnicas fijadas sin mirar resultados, y no abre ninguna decisión nueva.
