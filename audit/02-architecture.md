# 02 — Arquitectura y mantenibilidad

Base: commit `7871bdb`, árbol de trabajo limpio salvo lo indicado en
`audit/01-baseline-results.md`. **No se modificó código de aplicación.**

Alcance leído para este informe: `src/sqp/pipeline/{daily,probabilities}.py`,
`src/sqp/markets/*`, `src/sqp/risk/*`, `src/sqp/backtesting/{engine,roi_engine}.py`,
`src/sqp/settlement/settle.py`, `src/sqp/storage/{lock,atomic}.py`, `pyproject.toml`,
`.github/workflows/ci.yml`, `configs/default.yaml`.

## Resumen

La separación por capas es real y está respetada: `domain/` no importa de
`pipeline/`, `risk/clv_gate.py` documenta explícitamente evitar el ciclo
`daily → clv → roi_engine → daily` (`clv_gate.py:8-10`). El problema no es el
diseño de capas sino **la duplicación del camino de precios entre producción,
backtest y auditoría**, que ya ha divergido al menos una vez con consecuencias
medibles.

---

### [ARCH-01] `run_league` concentra seis responsabilidades en una función

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Mantenibilidad / acoplamiento
- **Location:** `src/sqp/pipeline/daily.py:476-740` (`run_league`); el módulo son 740 líneas y 19 funciones
- **Evidence:** Una sola función hace: selección de proveedor y fetch
  (`:504-569`), ajuste de ratings (`:544-552`), consenso y no-vig (`:585-587`),
  construcción del `model_map` (`:602-612`), cálculo de edge y staking
  (`:614-645`), persistencia del served stream (`:727-731`) y aplicación del cap
  de exposición (`:733-738`). El bucle de mercados (`:614-725`) tiene 111 líneas.
- **Impact:** Cada cambio en cualquiera de las seis etapas obliga a razonar sobre
  las otras cinco. Es el punto donde se compone la lógica de riesgo, y la
  composición no es evidente leyendo una etapa aislada — de hecho es la causa
  raíz de [QNT-01] y [QNT-02] en `04-quantitative-models.md`.
- **Failure scenario:** Un cambio en el orden de `_decision_probability` y
  `adjusted_edge` altera silenciosamente la magnitud efectiva de la penalización
  de EV sin que ningún test ni nombre de variable lo delate.
- **Recommendation:** Extraer el bucle de mercados a una función pura
  `score_market_side(...) -> BetCandidate | None` que reciba `cons`, `cons_n`,
  `fair` y `settings` y no toque E/S. No es urgente por corrección; lo es porque
  hace auditable la composición de penalizaciones.
- **Suggested validation:** Tras extraer, un test de propiedad sobre esa función
  fija la relación entre `market_shrink`, `uncertainty_penalty` y el edge final.
- **Estimated remediation scope:** Medium

---

### [ARCH-02] El camino "precios → consenso" está implementado tres veces con reglas distintas

- **Severity:** High
- **Confidence:** Confirmed
- **Category:** Duplicación / divergencia entre producción y backtest
- **Location:**
  - `src/sqp/pipeline/probabilities.py:17-34` (`_consensus_lines`) — **sí** filtra `price_decimal is None or <= 1.0`
  - `src/sqp/backtesting/roi_engine.py:92-95` (construcción de `MarketLine` en `load_closing_odds`) — **no** filtra nada: `price_decimal=float(r.price_decimal)`
  - `src/sqp/audit/clv_movement.py` (`snapshot_consensus_price:40`) — según el comentario de `probabilities.py:25`, filtra por su cuenta
- **Evidence:** El comentario de `probabilities.py:22-26` documenta la historia:
  *"Such rows exist in the captured history (audit 2026-07-24) and
  `clv_movement._consensus` already filters them; the live consensus did not
  (audit 2026-07-29, B-13)"*. Es decir: **ya divergieron una vez**, se arregló en
  dos de los tres sitios, y `roi_engine.load_closing_odds` sigue sin el guard.
- **Impact:** El backtest y la auditoría de CLV consumen un universo de precios
  distinto del que consume producción. Cualquier cifra OOS (el −5.32% citado en
  `audit/latest/QUANT_REVIEW.md:22`) se calculó sobre datos que producción habría
  descartado.
- **Failure scenario:** Un snapshot con cuotas degeneradas infla el backtest con
  apuestas que el pipeline vivo nunca habría emitido; la decisión de desplegar se
  toma sobre una simulación de otra política.
- **Recommendation:** Un único punto de verdad — extraer el predicado
  ("¿es esta línea utilizable?") a `markets/` e invocarlo desde los tres sitios.
  **No** cambiar el comportamiento del backtest sin re-correr y comparar: la
  cifra OOS se moverá y hay que saber cuánto.
- **Suggested validation:** Re-ejecutar `scripts/backtest_roi.py` antes y después
  del guard unificado y reportar el delta de ROI y de n. Si el delta es 0, el
  histórico no tenía filas degeneradas y el riesgo era teórico; si no, la cifra
  publicada cambia.
- **Estimated remediation scope:** Medium

---

### [ARCH-03] `_model_map` está duplicado literalmente entre producción y backtest

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Duplicación
- **Location:** `src/sqp/pipeline/daily.py:602-612` y
  `src/sqp/backtesting/roi_engine.py:159-170` (`_model_map`)
- **Evidence:** Ambos bloques construyen el mismo diccionario
  `(market, selection, point) -> probabilidad`, con las mismas seis entradas y el
  mismo tratamiento de `spread`/`-spread` y `Over`/`Under`. Son copias.
- **Impact:** Añadir un mercado o cambiar una convención de signo exige dos
  ediciones coherentes; una sola produce un backtest que evalúa una política
  distinta de la desplegada, en silencio.
- **Failure scenario:** Se añade un mercado nuevo a producción, se olvida el
  backtest, y la validación OOS del mercado nuevo nunca ocurre pese a aparecer
  como "cubierta".
- **Recommendation:** Mover a un único helper compartido. Es una extracción
  mecánica y de bajo riesgo, a diferencia de [ARCH-02].
- **Suggested validation:** Un test que afirme que ambos caminos producen claves
  idénticas para el mismo `EstimatedProbabilities`.
- **Estimated remediation scope:** Small

---

### [ARCH-04] Reglas de agregación de CLV duplicadas en dos módulos de auditoría

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Duplicación
- **Location:** `src/sqp/audit/clv.py:124-136` (`clv_segments`) y
  `src/sqp/audit/clv_movement.py:131-152` (`movement_segments`)
- **Evidence:** Ambas agregan `beat_close_rate=("beat_close", "mean")`
  (`clv.py:132`, `clv_movement.py:145`) y redondean el mismo conjunto de columnas
  (`clv.py:134`, `clv_movement.py:149`).
- **Impact:** Un cambio en la definición de "batir el cierre" —por ejemplo
  excluir filas no finitas, que es exactamente lo que pide [QNT-04]— hay que
  hacerlo dos veces.
- **Failure scenario:** Se corrige el `n` inflado en `clv_segments` (el que
  alimenta el gate) y no en `movement_segments`, dejando el análisis de
  movimiento con la definición antigua sin que nada lo señale.
- **Recommendation:** Extraer la especificación de agregación a una constante
  compartida.
- **Estimated remediation scope:** Small

---

### [ARCH-05] `audit/html_report.py` mezcla cálculo y presentación en 832 líneas

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Mantenibilidad
- **Location:** `src/sqp/audit/html_report.py` (832 líneas — el archivo más
  grande del proyecto); `_diagnostics_section:153-248`, `_patterns_section:249-285`,
  `_history_section:323-379`
- **Evidence:** Las funciones `_*_section` construyen HTML y a la vez derivan
  métricas; `_fmt_cell:109` y `_emph:286` son formateo puro mezclado con las
  anteriores en el mismo módulo.
- **Impact:** Riesgo de mantenibilidad, no de corrección. Se reporta porque el
  dashboard es la superficie por la que el operador lee el estado, y ya hubo un
  incidente de parseo de flags que lo dejó mostrando mal los picks del modo
  precisión (observación 2026-07-29).
- **Recommendation:** Separar "calcular la tabla" de "renderizar la tabla". No es
  prioritario frente a los hallazgos de `03`/`04`.
- **Estimated remediation scope:** Large

---

### [ARCH-06] La evitación de ciclos está documentada pero no verificada por ninguna prueba

- **Severity:** Informational
- **Confidence:** Confirmed
- **Category:** Arquitectura
- **Location:** `src/sqp/risk/clv_gate.py:8-10` (docstring: *"sin imports del
  pipeline (evita el ciclo daily -> clv -> roi_engine -> daily)"*)
- **Evidence:** La restricción existe solo como comentario. Nada impide que una
  edición futura importe `sqp.pipeline` desde `sqp.risk`.
- **Impact:** La restricción arquitectónica es voluntaria; se pierde en cuanto
  alguien no lea el docstring.
- **Recommendation:** Un test que afirme que `sqp.risk.*` y `sqp.markets.*` no
  importan `sqp.pipeline.*`. Barato y hace ejecutable la regla.
- **Suggested validation:** Parseo de imports con `ast` sobre esos paquetes.
- **Estimated remediation scope:** Small
