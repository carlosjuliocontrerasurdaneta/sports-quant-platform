# 04 — Modelos cuantitativos y validez estadística

Base: commit `7871bdb`. **No se modificó código de aplicación.**

Todo lo que sigue son **probabilidades estimadas** y controles de proceso. Este
documento no contiene ninguna afirmación de rentabilidad. El hecho dominante del
proyecto —**ninguna ventaja predictiva demostrada**, gate de CLV vacío, ROI
realizado −8.4% de banca sobre 431 apuestas graduadas
(`audit/latest/QUANT_REVIEW.md:18-25`)— no lo cambia ningún hallazgo de aquí.

---

### [QNT-01] La penalización de incertidumbre opera al 0.175 efectivo, la mitad del 0.35 configurado

- **Severity:** High
- **Confidence:** Confirmed (verificado por ejecución)
- **Category:** Validez cuantitativa / composición de controles de riesgo
- **Location:** `src/sqp/pipeline/daily.py:628-640` compuesto con
  `src/sqp/pipeline/probabilities.py:119-124` (`_decision_probability`) y
  `src/sqp/markets/edge.py:46-48` (`adjusted_edge`); parámetro en
  `configs/default.yaml:26` (`uncertainty_penalty: 0.35`)
- **Evidence:** `daily.py:635` pasa `p_decision` —no la probabilidad del
  modelo— como primer argumento de `adjusted_edge`. `p_decision` ya viene
  encogida hacia el mercado: `p_decision = (1-s)·p_cal + s·fair` con
  `market_shrink: 0.5` (`configs/default.yaml:17`). Por tanto
  `gap = |p_decision − fair| = (1−s)·|p_cal − fair|`. Ejecutado:

  ```
  p_model=0.60  fair=0.50  market_shrink=0.50 -> p_decision=0.550
  gap que VE adjusted_edge = 0.0500      gap del modelo REAL = 0.1000
  penalizacion aplicada    = 0.01750     con el gap real     = 0.03500
  => coeficiente EFECTIVO sobre el desacuerdo real = 0.175 (configurado 0.35)
  ```
- **Impact:** El control documentado con más detalle del sistema
  (`configs/default.yaml:18-25` dedica ocho líneas a justificar el 0.35 con
  evidencia OOS de 1654 apuestas) se aplica al 50% de su valor nominal. La
  validación OOS que fijó el 0.35 midió el sistema **compuesto**, así que el
  resultado empírico sigue siendo válido; lo que es falso es la lectura del
  parámetro. Nadie que ajuste ese número obtendrá el efecto que espera.
- **Failure scenario:** Un operador sube `uncertainty_penalty` de 0.35 a 0.50
  esperando un recorte del 43% en la penalización y obtiene la mitad. Peor: si
  algún día `market_shrink` cambia, la penalización efectiva se mueve sin que
  nadie toque `uncertainty_penalty`. Los dos parámetros están acoplados de forma
  invisible.
- **Recommendation:** **No cambiar el comportamiento** — está validado OOS tal
  como está y tocarlo invalida esa evidencia. Documentar el acoplamiento en
  `configs/default.yaml` y, preferiblemente, hacerlo explícito en el código
  pasando `p_cal` (la probabilidad no encogida) como base del `gap` **solo si**
  se recalibra el coeficiente a 0.175 para dejar el comportamiento idéntico.
- **Suggested validation:** Test de propiedad que fije
  `penalty == (1 − market_shrink) · uncertainty_penalty · |p_cal − fair|`. Ese
  test convierte el acoplamiento en algo que se rompe visiblemente.
- **Estimated remediation scope:** Small (documentar), Medium (hacerlo explícito
  sin alterar el comportamiento)

---

### [QNT-02] El tope de edge implausible también se evalúa sobre la probabilidad encogida

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Validez cuantitativa / control de riesgo
- **Location:** `src/sqp/pipeline/daily.py:630` (`e = edge(p_decision, price)`) y
  `:668` (`suspect = e > settings.risk.max_plausible_edge`); parámetro en
  `configs/default.yaml:16`
- **Evidence:** El edge que se compara contra `max_plausible_edge: 0.075` se
  calcula con `p_decision`, ya mezclada al 50% con el no-vig. Un modelo que se
  desvía del mercado lo suficiente para producir un edge crudo de 0.15 genera un
  `e` de ~0.075 y queda justo en la frontera del tope.
- **Impact:** El tope se describe en `configs/default.yaml:11-15` como detector
  de "probable miscalibración". Al medirlo sobre la mezcla, detecta la mitad de
  la miscalibración que su nombre sugiere. Es el mismo defecto de composición que
  [QNT-01] y comparte causa: `run_league` aplica el shrink antes de todos los
  controles que deberían mirar el desacuerdo crudo.
- **Failure scenario:** Un modelo se degrada y empieza a producir edges crudos
  del 12%; `e` sale ~6% y ningún pick se marca `edge_exceeds_max_plausible`,
  perdiéndose la señal de alarma.
- **Recommendation:** Decidir explícitamente sobre qué probabilidad debe operar
  el tope. Documentar la decisión donde está el parámetro.
- **Suggested validation:** Recorrer el histórico servido calculando ambos edges
  y contar cuántas filas cambiarían de clasificación.
- **Estimated remediation scope:** Small

---

### [QNT-03] `NaN` atraviesa los dos guards de eliminación de vig y anula el mercado completo

- **Severity:** High
- **Confidence:** Confirmed (demostrado con prueba ejecutable, commit `7871bdb`)
- **Category:** Estabilidad numérica / restricciones de probabilidad
- **Location:** `src/sqp/markets/vig.py:28` (`remove_vig_power`) y `:16`
  (`remove_vig_proportional`); origen en
  `src/sqp/pipeline/probabilities.py:27` (`_consensus_lines`)
- **Evidence:** Tres guards consecutivos fallan por la misma propiedad de
  IEEE-754 (toda comparación con `NaN` es `False`):
  1. `probabilities.py:27` — `ln.price_decimal <= 1.0` no filtra `NaN`.
  2. `vig.py:28` — `any(p <= 0 or p >= 1 for p in implied)` no lo detecta, así
     que `brentq` recibe `NaN`.
  3. `vig.py:16` — `if s <= 0: raise` no dispara porque `sum` es `NaN`; el
     fallback proporcional devuelve `NaN/NaN`.

  Resultado medido: las probabilidades justas del **mercado completo** salen
  `NaN`, no solo la del outcome afectado. El evento desaparece de los picks en
  silencio, porque toda comparación posterior con `NaN` es `False`.
- **Impact:** Pérdida silenciosa de eventos en el pipeline **vivo**
  (`_consensus_lines` la usa `daily.py:585`, no solo la auditoría). No hay
  contador de eventos perdidos por esta vía. La única señal audible es el log
  `power de-vig found no root` (`vig.py:40`), que apunta al síntoma equivocado.
- **Failure scenario:** Un proveedor emite un precio vacío; el evento sale de la
  selección sin aparecer en ningún conteo de "descartados", y el operador lee un
  día con menos picks como falta de oportunidades en vez de como fallo de datos.
- **Recommendation:** Un único predicado de línea utilizable que exija
  `math.isfinite(price) and price > 1.0`, invocado desde los tres sitios
  ([ARCH-02]). Añadir un contador explícito de líneas descartadas al log del run.
- **Suggested validation:** Test que pase un `EventOdds` con un precio `NaN` y
  afirme que el evento produce candidatos para el resto de sus mercados y que el
  descarte queda registrado.
- **Estimated remediation scope:** Medium

---

### [QNT-04] Un solo CLV `inf` puede aprobar un mercado en el gate que gobierna el dinero real

- **Severity:** High (latente bajo `shadow_mode: true`)
- **Confidence:** Confirmed (verificado por ejecución)
- **Category:** Validez estadística / control de riesgo
- **Location:** `src/sqp/risk/clv_gate.py:34` (`gate_decisions`) alimentado por
  `src/sqp/audit/clv.py:128-133` (`clv_segments`)
- **Evidence:** Ejecutado:

  ```
  league market  n  median_clv_pct  allowed
     mlb totals 30             inf     True
  ```

  Dos propiedades se componen:
  1. `clv_segments` agrega con `n=("clv_pct", "size")` (`clv.py:129`), que
     **cuenta** las filas no finitas, mientras `median`/`mean` saltan `NaN`. El
     `n ≥ min_n` del gate se satisface con filas que no aportan información.
  2. `pandas.median` **no** ignora `inf` (a diferencia de `NaN`), así que una
     sola fila con `inf` lleva la mediana a `inf`, e `inf > 0` es `True`.
- **Impact:** `market_allowed` es la regla vinculante de salida del shadow mode
  (`configs/default.yaml:101-110`): decide qué mercado puede llevar **stake
  real**. Un precio corrupto puede aprobarlo. Hoy el impacto monetario es nulo
  porque `shadow_mode: true` pone todos los stakes a 0 y tiene precedencia
  (`daily.py:389-392`), pero el gate existe precisamente para el día en que
  shadow se levante.
- **Failure scenario:** Se levanta el shadow mode confiando en el gate. Un
  mercado con una única fila de CLV `inf` —un precio de entrada corrupto— aparece
  como aprobado con `n=30` y empieza a llevar stake real sin ninguna evidencia
  real de CLV positivo.
- **Recommendation:** Dos correcciones independientes, ambas necesarias:
  (a) `clv_segments` debe contar con `count` (filas finitas) o excluir las no
  finitas antes de agregar; (b) `gate_decisions` debe exigir
  `np.isfinite(median_clv_pct)` además de `> 0`. **Ninguna debe aplicarse sin
  re-ejecutar `scripts/clv_analysis.py` y comparar el registro resultante**: el
  `n` de todos los segmentos puede bajar.
- **Suggested validation:** Test que construya un segmento con una fila `inf` y
  afirme `allowed == False`. Después, comparar `data/bets/clv_gate.json` antes y
  después: hoy debe seguir sin ningún mercado aprobado.
- **Estimated remediation scope:** Small

---

### [QNT-05] Kelly dimensiona apuestas correlacionadas del mismo partido como si fueran independientes

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Supuestos de Kelly / correlación
- **Location:** `src/sqp/risk/kelly.py:14-27` (`kelly_fraction_stake`) invocado
  por `src/sqp/pipeline/daily.py:641` dentro del bucle
  `for key, p_model in model_map.items()` (`:614`)
- **Evidence:** `model_map` (`daily.py:602-612`) contiene hasta seis selecciones
  del **mismo evento**: h2h local, h2h visitante (y empate), ambos lados del
  spread y Over/Under. Cada una pasa por `kelly_fraction_stake` de forma
  independiente. El criterio de Kelly presupone apuestas independientes o una
  optimización conjunta; el resultado de un partido determina simultáneamente
  h2h, spread y —parcialmente— el total.
- **Impact:** La exposición real a un solo resultado puede ser varias veces
  `max_stake_pct`. Los caps existentes son de **exposición agregada**
  (`_apply_daily_exposure_cap`, `apply_global_exposure_cap`), no de exposición
  por evento: escalan proporcionalmente el total del día pero no limitan cuánto
  se concentra en un partido.
- **Failure scenario:** Un partido con desacuerdo grande entre modelo y mercado
  genera tres o cuatro selecciones staked del mismo evento. Post-shadow, un solo
  resultado adverso produce una pérdida de varias veces el máximo por apuesta
  previsto.
- **Recommendation:** Añadir un cap por evento, o excluir selecciones
  correlacionadas del mismo partido. Es una decisión de política de riesgo, no
  una corrección: requiere decisión del operador.
- **Suggested validation:** Sobre el histórico de candidatos, calcular la
  distribución de stake agregado por `event_id` y compararla con
  `max_stake_pct · bankroll`. Si el p95 ya excede el máximo por apuesta, el
  riesgo es actual y no teórico.
- **Estimated remediation scope:** Medium

---

### [QNT-06] Las decisiones se toman con n=30 y sin intervalos de confianza

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Tamaño de muestra / inferencia
- **Location:** `src/sqp/risk/clv_gate.py:23` (`CLV_GATE_MIN_N = 30`),
  `src/sqp/risk/degradation.py:35` (`DEFAULT_MIN_N = 30`),
  `src/sqp/calibration/calibrator.py:420` (`AUTO_PROMOTE_MIN_N_VAL = 30`). Único
  cálculo de IC del proyecto: `src/sqp/evaluation/model_vs_market.py:48`
  (`_cluster_bootstrap_ci`)
- **Evidence:** Tres decisiones de consecuencia distinta —habilitar stake real,
  pausar un mercado y promover un calibrador— comparten el mismo umbral de 30 y
  ninguna publica incertidumbre. `gate_decisions` (`clv_gate.py:34`) exige
  únicamente `n >= min_n` y `median > 0`: una mediana de +0.01% con n=30 aprueba
  igual que una de +3%.
- **Impact:** El signo de una mediana de CLV con n=30 es, en la práctica,
  indistinguible del ruido. El propio proyecto ya llegó a esa conclusión en otro
  contexto y actuó en consecuencia: el gate intradía se reformuló como **test de
  signo con p<0.05** (`src/sqp/audit/intraday_gate.py`, decisión KI-020 del
  2026-08-05). El gate de CLV no recibió el mismo tratamiento.
- **Failure scenario:** Se levanta el shadow mode sobre un mercado cuyo CLV
  mediano positivo es ruido muestral, y la primera evidencia en contra llega ya
  con dinero comprometido.
- **Recommendation:** Alinear el gate de CLV con el criterio que ya se adoptó
  para el intradía: test de signo sobre filas no empatadas, con p explícito, en
  vez de "mediana > 0". Es coherencia interna, no una idea nueva.
- **Suggested validation:** Recalcular el registro del gate con el criterio de
  signo y comprobar que ningún mercado que hoy pasaría deja de pasar por azar.
- **Estimated remediation scope:** Medium

---

### [QNT-07] El backtest de calibración condiciona correctamente los empates — sin hallazgos

- **Severity:** Informational
- **Confidence:** Confirmed
- **Category:** Reglas de puntuación propias
- **Location:** `src/sqp/backtesting/engine.py:33-54` (`walk_forward_backtest`)
- **Evidence:** Para ligas de tres vías, la probabilidad evaluada se condiciona a
  "sin empate" (`probs.append(ph / denom)`, `:37-38`) y los empates se excluyen
  de las métricas binarias (`mask = [o in (0.0, 1.0)]`, `:54`), con la
  calibración del empate reportada por separado (`:64-67`) y una log-loss de tres
  vías propia (`:47`). El orden `estimate` → `observe` (`:31` y `:53`) garantiza
  que el estado del adaptador solo contenga partidos anteriores.
- **Impact:** Ninguno — se documenta como control verificado. Es el tratamiento
  correcto: puntuar probabilidades no condicionadas contra frecuencias con
  empates excluidos sobreestima mecánicamente la calibración, y el código lo
  evita explícitamente.
- **Recommendation:** Ninguna.
- **Estimated remediation scope:** —

---

### [QNT-08] `_novig_probs` de h2h agrupa por mercado sin discriminar el `point`

- **Severity:** Low
- **Confidence:** Requires verification
- **Category:** Corrección numérica
- **Location:** `src/sqp/pipeline/probabilities.py:58-68`
- **Evidence:** `keys = [k for k in cons if k[0] == "h2h"]` toma **todas** las
  claves de h2h sin filtrar por `k[2]` (el `point`), a diferencia de la rama de
  totals (`:62`), que sí exige `k[2] == point`. El guard posterior es
  `if len(keys) < required` (`:64`): comprueba un mínimo, no una igualdad. Si por
  cualquier motivo existieran claves h2h con `point` distinto de `None`, se
  eliminaría el vig sobre más de dos (o tres) outcomes.
- **Impact:** Un no-vig calculado sobre un conjunto de outcomes que no es una
  partición del espacio muestral produce probabilidades justas incorrectas para
  todo el mercado.
- **Failure scenario:** Depende enteramente de si el proveedor puede emitir h2h
  con `point`. En el esquema actual h2h no lleva línea, así que probablemente no
  sea alcanzable.
- **Recommendation:** Confirmar primero si es alcanzable. Si lo es, cambiar el
  guard a igualdad y filtrar por `point is None`. Si no lo es, no tocar el
  código: un guard más estricto sin caso que lo motive añade riesgo sin
  beneficio.
- **Suggested validation:** Comprobar en `providers/odds_api.py:_parse_events` si
  h2h puede recibir `point` no nulo.
- **Estimated remediation scope:** Small
