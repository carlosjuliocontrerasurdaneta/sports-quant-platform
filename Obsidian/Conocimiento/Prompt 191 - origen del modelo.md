---
tags: [conocimiento, modelo, mlb, origen, sqp]
creada: 2026-08-15
actualizada: 2026-08-16
---

# Prompt 191 — el origen del modelo

Especificación fundacional de SQP: un motor cuantitativo de pricing pregame para
MLB en 21 fases. **Todo el repositorio es la industrialización de este
documento.** Se conserva aquí porque explica por qué `src/sqp` está construido
como está.

> El origen del **sistema completo** —alcance de ligas y mercados, y qué se
> optimiza— está en [[Idea fundacional - alcance y objetivo]]. Esta nota cubre
> solo el motor de MLB.

> Archivo fuente de la v2: `docs/prompts/prompt-191-mlb-pricing-v2.md`. La v1 no
> existe como archivo — solo citada y analizada en esta nota. Los cinco motores
> hermanos por deporte están en `docs/prompts/` y analizados en
> [[Motores de pricing por deporte - analisis]].

## Qué hace el sistema: PREDECIR, no preciar

Corrección del operador, 2026-08-15, textual:

> **"NO preciar, es PREDECIR el resultado de los juegos a través de estimar las
> probabilidades."**

No es vocabulario, es el marco entero. **Preciar** es relativo al mercado:
produces un número para compararlo con una cotización. **Predecir** es relativo
a la realidad: estimas qué va a pasar, y eso es verdad o mentira exista o no un
mercado. (Los prompts se titulan "motor de pricing" por convención de nombre;
el objeto es la predicción.)

Consecuencias directas:

- La regla "el mercado NUNCA es input" no es cautela metodológica: es que el
  mercado **no interviene en el acto de predecir**. Aparece al final solo porque
  es donde una predicción correcta se cobra.
- **Batir al mercado no es el objetivo**, es una consecuencia posible.
- **Calibración y rentabilidad son propiedades distintas.** Una predicción puede
  estar bien calibrada y no ser rentable. Lo primero es lo que el sistema
  persigue; lo segundo es si además se puede cobrar.
- Por eso un CLV de 0 **no cierra nada**: el CLV mide rendimiento contra un
  mercado, y que el mercado ya lo sepa dice algo del mercado, no de la
  predicción.
- En este marco las métricas rectoras son **Brier, log loss y curva de
  fiabilidad contra la realidad**, sin mercado de por medio — exactamente la
  fase que ninguno de los seis prompts tenía y que se añadió el 2026-08-15.

## La hipótesis fundacional

Carlos, textual (2026-08-15):

> "Cuando comencé hace meses en este proyecto todo se basaba en la idea plasmada
> en el prompt. Yo pensaba que si podía determinar las probabilidades con
> bastante exactitud podría llegar a ganar dinero apostando en los resultados de
> los partidos."

## La cadena causal del prompt

```
ofensiva + abridor + bullpen + defensa + matchup + entorno + localía
  → carreras esperadas → distribución → probabilidades reales
```

Regla vertebral: **el mercado nunca es input.** Solo entra en la Fase 17, como
benchmark. Es una decisión metodológicamente correcta y poco común — impide que
el modelo se ancle al precio y fabrique una independencia falsa.

Núcleo cuantitativo (Fase 14), un modelo multiplicativo (log-aditivo):

```
Runs_away = 4.60 × OffRating_final_away × PitchingAllowed_home × EnvAdj × AwayAdj
Runs_home = 4.60 × OffRating_final_home × PitchingAllowed_away × EnvAdj × HomeAdj
```

y de ahí a una Negative Binomial bivariante correlacionada (10.000 iteraciones)
para derivar ML, run line ±1.5 y totals.

## Mapa prompt → código

| Fases | Módulo en `src/sqp` |
|---|---|
| 2–9 (ofensiva, matchup) | `features/`, `sports/adapters.py` |
| 10–12 (abridor, bullpen, defensa) | `features/`, `sports/adapters.py` |
| 13–15 (rho, NB, simulación) | `simulation/`, `models/distributions.py` (`nbinom`) |
| 16 (probabilidades) | `pipeline/probabilities.py` |
| 17 (mercado, edge) | `markets/odds.py`, `markets/edge.py` |
| 19 (señal CLV) | `risk/clv_gate.py`, `audit/clv.py` |
| 21 (priorización) | ranking de edges, `pick_mode` |

## Lo que el prompt hace bien

Su disciplina es superior a la de la mayoría de modelos públicos:

- **El mercado fuera del modelo.** Ver arriba.
- **Fallbacks explícitos y declarados**, prohibición de inventar métricas.
- **Redistribución de pesos** cuando falta una métrica
  (`W_nuevo_i = W_i / Σ W_disponibles`): mantiene el índice centrado en 1.00 en
  vez de sesgarlo hacia abajo, que es el error habitual.
- **Trazabilidad obligatoria** de valores intermedios: el modelo es auditable.
  Es la misma exigencia que hoy sostiene todo el aparato de medición.
- **Shrink de principio de temporada** hacia 1.00 según muestra.
- **Negative Binomial en vez de Poisson**: correcto, las carreras están
  sobredispersas (var > media).
- **Degradación de confianza** en vez de abortar.

## Defectos técnicos identificados

### 1. Fase 21 — el ranking está dominado por la confianza, no por el edge

```
Score = 0.65 × EDGE_abs + 0.20 × Confianza_num + 0.15 × MarketConf_num
```

La fórmula es **ambigua en unidades** y da comportamientos opuestos:

- Si `EDGE_abs` es proporción (0.04 para un 4%): `0.65 × 0.04 = 0.026` frente a
  `0.20 × 1.0 = 0.20`. **El edge aporta ~7% del score**; el ranking ordena por
  confianza.
- Si es puntos porcentuales (4.0): `0.65 × 4.0 = 2.6` y los términos de
  confianza son despreciables.

Ninguna de las dos es lo que se pretende. Requiere normalizar `EDGE_abs` a un
rango comparable antes de ponderar.

### 2. Fase 17 — `EDGE_modelo = |Prob_modelo − 0.50|` no es un edge

Mide cuán desequilibrado está el partido, no cuánto valor hay. Usarlo en el
ranking cuando no hay línea **promueve los partidos más desiguales**, que son
justo los que exigen un precio altísimo para ser rentables.

Es exactamente el modo de fallo del **modo precisión**, revertido el 2026-07-31:
seleccionar por probabilidad alta elegía favoritos a cuota 1.07–1.16, donde el
punto de equilibrio es 93,5% de aciertos. Subía el hit rate y perdía dinero por
construcción. Ver [[Bitácora/2026-07-31]].

### 3. Fase 19 — la señal de CLV tiene la causalidad invertida

> Marcar "CLV potencial positivo" si `EDGE_mercado ≥ 4%` y MarketConfidence
> Alta/Media.

Un edge grande contra un mercado eficiente **no predice CLV positivo**; si acaso
indica error del modelo. Es la definición de selección adversa, y está medida en
este proyecto: los edges seleccionados tuvieron CLV ≤ 0. Ver
[[Conocimiento/CLV y selección adversa]].

### 4. Fase 15 — la varianza dinámica no es aplicable a la NB tal como está escrita

El prompt indica "mismos ajustes para NB y Normal" y luego lista escalados de
`sigma_margin` / `sigma_total`. Pero en una NB la varianza no es libre:
`var = μ + k·μ²`. No se puede escalar sigma sin tocar `k`. **Falta el
mecanismo**: los ajustes deberían expresarse sobre `k`, no sobre sigma.

### 5. Fase 15 — la NB bivariante está subespecificada

"Usar distribución bivariante correlacionada con rho" no define una
construcción. No existe una NB bivariante canónica: hace falta elegir cópula
(gaussiana sobre marginales NB) o frailty compartida. Sin especificarlo, dos
ejecuciones dan resultados distintos.

Sobre rho hay un matiz que conviene precisar (corrige una afirmación anterior de
esta nota): `EnvAdj` es una **constante** dentro de un partido, así que no induce
correlación entre los dos marcadores de esa simulación — solo desplaza ambas
medias. El problema real es de **procedencia**: si `rho_base = 0.12` se estimó de
la correlación histórica cruda, incluye el efecto parque/clima que el modelo ya
condiciona vía `EnvAdj`, y entonces sobreestima la correlación *residual*. El
prompt no declara de dónde sale el 0.12.

### 6. Solapamiento de señales en OffRating (Fase 8)

`SeasonAdjIndex` (0.55), `SplitIndex` (0.30) y `RecentIndex` (0.15) no son
independientes: el wRC+ de temporada **ya contiene** los juegos recientes y los
splits. Un 0.30 al split de plato es mucho peso para una métrica ruidosa.

Peor: el split se toma vs. la mano del abridor rival, pero la calidad de ese
abridor ya está en `PitchingAllowed`. Doble conteo parcial de la misma
información.

### 7. Rangos mal dimensionados

- **`DefenseAdj ∈ [0.97, 1.03]` es demasiado estrecho.** La diferencia entre la
  mejor y la peor defensa de MLB vale del orden de 40–50 carreras por temporada
  (~0,3 por juego, ~6–7% sobre 4,60). El rango real debería rondar
  [0.94, 1.06]. Tal como está, la defensa es prácticamente un no-op.
- **`UmpAdj` con clasificación "tendencia over/under histórica"** introduce
  ruido: esas tendencias son notoriamente poco predictivas fuera de muestra.
- **`Si KBB ≤ 0 → KBB_index = 1.20`**: un abridor con K% < BB% es catastrófico,
  mucho peor que "20% peor que la liga". La penalización se queda muy corta
  (aunque el caso casi no existe entre abridores de MLB).
- Los límites de `OffRating`/`PitchingAllowed`/`EnvAdj` permiten 2,4–8,8 carreras
  por equipo, muy por encima del rango real de esperadas (~3,2–6,0). **No
  regularizan nada en la práctica**; toda la contención viene de que los índices
  se quedan cerca de 1.00 por construcción.

### 8. Fase 9 — MatchupAdj es la fase de mayor riesgo

Cinco heurísticas con magnitudes fijadas a mano y sin validación
(GB-heavy vs poder: −0.02; alto K% vs lineup K-heavy: −0.03; etc.). Suenan a
conocimiento experto y son, casi con certeza, ruido. Y como se aplican de forma
**asimétrica por equipo**, mueven directamente la moneyline — el mercado con el
listón más alto.

## La corrección de fondo, y no invalida la idea

La hipótesis era: **probabilidades exactas → dinero**. El paso que falta:

> Se gana con la **diferencia** entre la probabilidad propia y el precio, neta
> de vig. Si el mercado es igual de exacto, esa diferencia es ruido, y el ruido
> paga vig.

Un modelo puede estar perfectamente calibrado y tener **cero** ventaja, porque
el mercado también lo está. Por eso el objetivo medible no es "ser exacto" sino
**"ser más exacto que la línea de cierre en los partidos concretos donde se
apuesta"** — que es exactamente lo que mide el CLV.

Esto es lo que las cinco mediciones de agosto confirmaron empíricamente
(CLV +0,0000%): no dicen que el modelo esté mal construido, dicen que **sus
insumos son públicos, están retrasados y ya están en el precio.**

## Hacia dónde apunta esto

La consecuencia útil no es abandonar la cadena causal del prompt —es sólida—
sino **cambiar dónde se aplica**: buscar los rincones donde el mercado está
menos informado, en vez de competir de frente en la moneyline de MLB, que es de
los mercados más eficientes que existen.

Candidatos coherentes con la evidencia acumulada, para evaluar por separado:

- **Mercados derivados que los books precian con menos cuidado**: primeros 5
  innings (F5), team totals, líneas alternativas. La misma simulación ya
  produce esas distribuciones — el coste marginal es bajo.
- **Ventana temporal**: líneas publicadas temprano, antes de que llegue el
  dinero informado.
- **Fuentes de información con ventaja temporal**: alineaciones y lesiones antes
  que el mercado.

Los tres son mejoras sobre el prompt, no sustituciones. Ver
[[Estado del proyecto]] y [[sin-ventaja-medida-2026-08-05]] (memoria).

---

# Versión corregida (v2) — análisis

Revisión de la versión corregida del prompt, 2026-08-15.

## Defectos de v1 que quedan cerrados

| Defecto v1 | Estado en v2 |
|---|---|
| Ranking dominado por confianza (unidades mezcladas) | **Cerrado.** Orden lexicográfico: EV/unidad → Edge_pp → Confianza → CalidadMercado. Y ordena por **EV**, no por edge, que es lo correcto: 4 pp a cuota 1.10 valen mucho menos que 4 pp a 3.00. |
| `EDGE_modelo = abs(p−0.50)` tratado como edge | **Cerrado.** Renombrado "convicción del modelo", excluido del ranking, presentado aparte "sin implicar valor". |
| Señal de CLV con causalidad invertida | **Cerrado.** Ahora "candidato a valor pregame"; el CLV se calcula *después* del cierre contra el precio tomado. Añade `EV > 0` como condición. |
| Varianza dinámica inaplicable a la NB | **Cerrado.** Parametrización explícita `var = μ + α·μ²`, `size = 1/α`, `p = size/(size+μ)`. La tabla de escalado de sigma desapareció. |
| NB bivariante subespecificada | **Cerrado y bien.** Exige método reproducible (cópula gaussiana calibrada), semilla y correlación empírica resultante; y si no se puede, **`rho_aplicado = 0` declarado**, nunca correlación ficticia. |

## Aciertos nuevos de v2 que no estaban en v1

Varios son errores que la mayoría de modelos cometen en silencio:

- **De-vig antes de comparar** (`p_market_i = q_i / Σq`). En v1 el edge se calculaba contra la probabilidad implícita **con vig**, lo que sesga sistemáticamente el edge a la baja en ambos lados. Era un defecto real de v1 que esta nota no había detectado.
- **Push en totales enteros.** "No definas Under como 1−Over". Correcto y muy poco frecuente.
- **MLB no admite empate.** Resolver los empates simulados *antes* de derivar la ML, con innings extra y regla del corredor automático, o 50/50 declarado. Los empates son ~9–10% de las simulaciones: mal resueltos mueven la moneyline de forma apreciable.
- **EV por unidad** como variable de decisión, no solo el edge en pp.
- **Error de Monte Carlo**: 100.000 iteraciones con semilla y `SE = √(p(1−p)/n)`.
- **Disciplina point-in-time** (Regla 5): solo información conocida antes del primer lanzamiento; en backtests, corte temporal estricto. Es la regla anti-fuga, la misma cuya violación produjo KI-019 en este proyecto.
- **Procedencia obligatoria**: fuente, timestamp y corte estadístico por dato.
- **Anti-alucinación dirigida al ejecutor**: "no afirmes haber ejecutado simulaciones que no hayas ejecutado"; ante fallo de cómputo, entregar carreras esperadas y declarar qué no se pudo calcular.
- **Lenguaje epistémico correcto**: "probabilidades justas estimadas", nunca "reales". Coincide con las reglas de salida de apuestas del proyecto.
- **Constantes declaradas configurables**, no verdades universales.
- **Bullpen sin métrica base → índice 1.00**, en vez de construirlo con los restos (WHIP + fatiga) vía redistribución.
- **Fase 18 no infiere steam ni dinero profesional** sin series temporales verificables.
- **Confianza del modelo ⊥ calidad del mercado** como dimensiones independientes.

En conjunto, v2 pasa de "modelo bien intencionado" a **especificación auditable**.

## Lo que sigue abierto en v2

### 1. `NB_alpha = 0.15` sub-dispersa las carreras

Con `var = μ(1 + αμ)` y μ = 4.60: var = 7.77, **sd = 2.79**. La dispersión real de
carreras por equipo-partido en MLB ronda **sd ≈ 3.1** (var/media ≈ 2.0–2.1). Para
reproducirla haría falta **α ≈ 0.22–0.24**, no 0.15.

Consecuencia direccional: menos varianza → distribución del margen más estrecha →
**probabilidades de favorito infladas**. En un partido con margen esperado 1,5
carreras el efecto ronda **+1 pp** sobre el favorito; en la cola es mayor.

Coincide con el diagnóstico registrado del proyecto: *"ROI realizado MLB
persistentemente negativo (−27,6%): sesgo sistemático de sobreconfianza"*.

### 2. `HomeAdj = 1.02` subestima la localía — probablemente el sesgo más grande

Aplicado solo a las carreras del local, desplaza el margen
`4.60 × 0.02 ≈ 0.09` carreras. Con sd del margen ≈ 4.4, eso implica una tasa de
victoria local de **~50,8%**. La localía real en MLB está en **~52,5–53,5%**.

Como los índices ofensivos y de pitcheo se calculan sobre totales de temporada
(no sobre splits casa/ruta), **toda la localía tiene que venir de `HomeAdj`** — y
1.02 no alcanza. El valor coherente rondaría **1.05–1.08** unilateral, o repartir
±3–4% entre local y visitante.

Es un sesgo **sistemático y direccional de ~2 pp contra el local**, sobre un
umbral de decisión de 4 pp. Fabricaría edges aparentes en visitantes de forma
persistente. **Es lo primero que comprobaría contra datos propios.**

### 3. El `± SE` reportado transmite una precisión que no existe

Con n = 100.000, `SE ≈ 0.16 pp`. Pero esa es solo la **incertidumbre de
simulación**, la menor de todas. La incertidumbre de especificación (pesos
fijados a mano, α, HomeAdj, MatchupAdj, rangos sin calibrar) es de otro orden —
plausiblemente 3–5 pp. Reportar `XX.X% ± 0.2%` junto a un umbral de 4 pp sugiere
que el edge es distinguible del ruido cuando probablemente no lo es.

### 4. No existe fase de calibración ni validación fuera de muestra

v2 dice que los límites "deben validarse/calibrarse fuera de muestra", pero **no
hay ninguna fase que lo haga**. No hay Brier, log-loss, curva de fiabilidad ni
ECE. El modelo emite probabilidades y nunca se confronta con lo ocurrido. Es la
carencia estructural que este proyecto terminó cubriendo con todo el módulo
`calibration/` y sus gates. **Falta una Fase 22.**

### 5. Solapamiento de señales, aún parcial

`OffRating = 0.55·Season + 0.30·Split + 0.15·Recent` sigue tratando como
independientes tres señales que no lo son: el wRC+ de temporada **contiene** los
juegos recientes y las apariciones del split. El shrink nuevo del split
(`0.50·raw + 0.50` sin regla calibrada) mitiga bastante el peso efectivo, pero
la estructura sigue implicando independencia.

Persiste además el doble conteo del abridor rival: su mano entra por el split
ofensivo y su calidad por `PitchingAllowed`.

### 6. `DefenseAdj ∈ [0.97, 1.03]` sigue siendo la mitad de lo que vale

Con categorías (0.98 / 1.00 / 1.02) el rango efectivo es ±2%, cuando la
diferencia entre la mejor y la peor defensa de MLB vale ~6–7% de las carreras.
La defensa sigue siendo casi un no-op.

### 7. `KBB_index = KBB_liga / KBB` mezcla escalas

`xFIP_index`, `WHIP_index` y `HR9_index` son razones respecto a la liga de
cantidades aproximadamente proporcionales a carreras permitidas. `KBB_index` es
el **recíproco de una diferencia de tasas**, con curvatura y escala distintas: un
abridor con KBB = 28 pp da 0.50 y con 7 pp da 2.00. Ponderarlo al 0.15 junto a
los otros tres no tiene una interpretación clara en unidades de carrera.

### 8. Procedencia de `rho_base = 0.12` no declarada

Ver el matiz de la sección de v1: si viene de correlación histórica cruda,
sobreestima la correlación residual una vez condicionado el entorno.

## Lo que se puede comprobar ya, con datos propios

Los puntos 1, 2 y 4 son **medibles con lo que el repositorio ya guarda**
(`data/bets/settled_*.csv` y el stream de probabilidades servidas de
`ServedStore`), sin gasto de cuota:

1. **Localía**: tasa de victoria local realizada vs. media de `P_home` servida.
   Una brecha persistente de ~2 pp confirmaría el punto 2.
2. **Dispersión**: sd del margen realizado vs. sd del margen simulado.
   Si la realizada es mayor, confirma α bajo.
3. **Calibración**: curva de fiabilidad de las probabilidades servidas por banda.
   La sobreconfianza en favoritos ya está documentada; esto la ataría a una causa
   concreta y corregible en vez de a "el modelo está mal".

Los tres son mejoras dirigidas, baratas y falsables. Ver
[[Bitácora/2026-08-15]].
