# 05 — Calidad de datos, leakage y validez del backtesting

Base: commit `7871bdb`. **No se modificó código de aplicación.**
`data/`, `historical/`, `logs/` y `exports/` **no se escanearon** (regla
permanente del proyecto), así que todo hallazgo sobre contenido de datos queda
marcado como pendiente de verificación con autorización explícita.

---

### [DAT-01] El backtest lee precios que producción descarta

- **Severity:** High
- **Confidence:** Confirmed
- **Category:** Contaminación train/test / paridad backtest-producción
- **Location:** `src/sqp/backtesting/roi_engine.py:92-95` (`load_closing_odds`)
  frente a `src/sqp/pipeline/probabilities.py:27` (`_consensus_lines`)
- **Evidence:** El backtest construye sus `MarketLine` con
  `price_decimal=float(r.price_decimal)` sin filtro alguno. Producción descarta
  `None` y `<= 1.0` (`probabilities.py:27`) — un guard añadido explícitamente
  tras el hallazgo B-13 (auditoría 2026-07-29) porque *"such rows exist in the
  captured history (audit 2026-07-24)"* (`probabilities.py:22-26`). El histórico
  **contiene** esas filas por reconocimiento del propio código.
- **Impact:** La cifra OOS con la que se juzga el sistema (−5.32%,
  `audit/latest/QUANT_REVIEW.md:22`) se calculó sobre un universo de precios que
  el pipeline vivo nunca habría considerado. No es que el backtest sea
  optimista o pesimista: es que evalúa **otra política**.
- **Failure scenario:** Se decide desplegar o no una configuración basándose en
  un backtest que incluye apuestas imposibles a cuotas degeneradas. La decisión
  se toma sobre una simulación de un sistema que no existe.
- **Recommendation:** Aplicar el mismo predicado de línea utilizable en ambos
  caminos ([ARCH-02], [QNT-03]). **Re-ejecutar el backtest y publicar el delta**:
  la cifra OOS se moverá y hay que saber en qué dirección y cuánto.
- **Suggested validation:** `scripts/backtest_roi.py` antes y después, reportando
  ROI, n de apuestas y n de eventos. Un delta de 0 significa que el histórico
  reciente no tiene filas degeneradas y el riesgo era latente.
- **Estimated remediation scope:** Medium

---

### [DAT-02] El backtest no aplica el tope de exposición global entre ligas

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Paridad backtest-producción / riesgo
- **Location:** `src/sqp/backtesting/roi_engine.py:173-184`
  (`_apply_backtest_daily_cap`) frente a
  `src/sqp/pipeline/daily.py:245-304` (`apply_global_exposure_cap`)
- **Evidence:** El backtest agrupa por `date` y aplica **un solo** cap
  (`cap_pct`), cuyo docstring dice explícitamente *"the production **per-league**
  exposure cap"* (`:175`). Producción aplica dos capas: la per-liga dentro de
  `run_league` (`daily.py:733`) **y** `apply_global_exposure_cap` una vez tras
  correr todas las ligas, motivada porque *"the per-league cap above could
  compound to N x 10% on a multi-league day"* (`configs/default.yaml:7-9`).
- **Impact:** En un día multi-liga el backtest permite hasta N veces la
  exposición que producción permitiría, con N el número de ligas corridas. El ROI
  por unidad de riesgo del backtest no es comparable con el desplegable.
- **Failure scenario:** Un backtest multi-liga muestra un ROI aceptable
  apalancado en una exposición diaria que el sistema real recortaría, y el
  recorte cambia qué apuestas sobreviven, no solo su tamaño.
- **Recommendation:** Replicar la segunda capa en el backtest, o documentar
  el resultado como "sin tope global" allí donde se publique la cifra.
- **Suggested validation:** Correr el backtest con y sin el tope global sobre el
  mismo periodo multi-liga y comparar ROI y exposición diaria máxima.
- **Estimated remediation scope:** Medium

---

### [DAT-03] Las apuestas se registran a un precio que ninguna casa ofrece

- **Severity:** Medium
- **Confidence:** Confirmed
- **Category:** Realismo de ejecución / disponibilidad de mercado
- **Location:** `src/sqp/pipeline/daily.py:656` y `:714`
  (`"bookmaker": "consensus_median"`); precio calculado en
  `src/sqp/pipeline/probabilities.py:33` (`median` sobre las casas)
- **Evidence:** El precio de cada pick es la **mediana** entre casas, y así se
  persiste tanto en el served stream como en el candidato. No es el precio de
  ninguna casa concreta: por construcción, aproximadamente la mitad de las casas
  ofrecen peor precio que ese. No hay modelado de comisiones, de límites de
  apuesta, ni de disponibilidad de la línea en el momento del pick.
- **Impact:** Es una elección **conservadora frente a tomar el mejor precio**
  —que sería la trampa clásica— y está documentada como decisión deliberada
  (observación del 2026-07-31). Pero sigue siendo un precio no obtenible: el ROI
  realizado se calcula contra una cuota que habría requerido saber de antemano
  qué casa quedaría en la mediana.
- **Failure scenario:** El sistema sale de shadow con un ROI estimado sobre
  precios de mediana y la ejecución real, sujeta a la casa disponible y a
  límites, entrega sistemáticamente menos.
- **Recommendation:** Documentar el supuesto junto a toda cifra de ROI. Para el
  paso a dinero real, la referencia honesta es el peor precio entre las casas
  realmente accesibles al operador, no la mediana del mercado completo.
- **Suggested validation:** Recalcular el ROI histórico usando el precio del
  percentil 25 en vez de la mediana; la diferencia acota el optimismo del
  supuesto.
- **Estimated remediation scope:** Medium

---

### [DAT-04] Sesgo de supervivencia: filas servidas que nunca se gradúan

- **Severity:** High
- **Confidence:** High confidence (heredado y no re-medido en esta pasada)
- **Category:** Sesgo de supervivencia
- **Location:** `src/sqp/monitoring/health.py:78` (`_served_pending_expired`);
  política de expiración en `src/sqp/settlement/settle.py:18`
  (`STALE_VOID_DAYS = 3`) y `:79-108` (`void_stale_candidates`)
- **Evidence:** `audit/latest/FINDINGS.md:78-88` registra **54 filas servidas
  pendientes fuera de la ventana de scores** (chile 42,
  tennis_atp_canadian_open 12) con el health check en WARN, y clasifica la causa
  raíz como **no confirmada**. No re-ejecuté el health check en esta pasada.
- **Impact:** Las filas que no se gradúan salen de todos los agregados —CLV,
  Brier, hit rate, ROI— sin dejar rastro en el denominador. Si la falta de
  graduación se correlaciona con alguna característica del partido (ligas
  concretas, partidos cancelados, torneos terminados), el sesgo es sistemático,
  no aleatorio.
- **Failure scenario:** Una liga cuyos resultados el vendor no cubre desaparece
  progresivamente de la muestra; el CLV agregado mejora porque se están cayendo
  precisamente las apuestas no verificables.
- **Recommendation:** Cerrar B-0 de `audit/latest/BACKLOG.md` (requiere decisión
  del operador: el settle consume cuota). Mientras tanto, publicar el conteo de
  no graduadas junto a cada métrica agregada.
- **Suggested validation:** `python scripts/health_check.py` → objetivo OK (0/0),
  o filas anuladas con flag explícito y razón registrada.
- **Estimated remediation scope:** Small (ejecución), Medium (si falta vendor)

---

### [DAT-05] El emparejamiento resultado↔cuotas depende del orden de entrada

- **Severity:** Medium
- **Confidence:** Requires verification
- **Category:** Reproducibilidad
- **Location:** `src/sqp/backtesting/roi_engine.py:119-146` (`_match_result`)
- **Evidence:** Cada evento de cuotas se consume como máximo una vez mediante el
  conjunto `used` (`:136`, `:145`). La selección es la de menor distancia en días
  con desempate por `start_time` (`:141-143`), lo cual es determinista **para un
  resultado dado**; pero como el emparejamiento es codicioso y con consumo, el
  conjunto final depende del **orden en que llegan los resultados**. Con
  dobles jornadas o series en días consecutivos —el caso que motivó el hallazgo
  I-4 de la auditoría 2026-07-24, citado en el propio docstring— dos resultados
  compiten por las mismas cuotas.
- **Impact:** Si `results` no llega siempre en el mismo orden, el backtest no es
  reproducible bit a bit. La reproducibilidad es un requisito declarado del
  proyecto (`.claude/rules/modeling-rules.md`).
- **Failure scenario:** Dos ejecuciones del mismo backtest sobre los mismos datos
  producen ROI distintos porque un `groupby` o una lectura de directorio cambió
  el orden.
- **Recommendation:** Ordenar `results` explícitamente por (fecha, event_id)
  antes del emparejamiento, o resolver el emparejamiento como asignación global
  en vez de codiciosa.
- **Suggested validation:** Ejecutar el backtest dos veces con `results`
  barajado y comparar ROI y n. **Si coinciden, este hallazgo se descarta.**
- **Estimated remediation scope:** Small

---

### [DAT-06] El filtro de cierre depende de un `commence_time` que el proveedor corrige — control ya reparado

- **Severity:** Informational
- **Confidence:** Confirmed
- **Category:** Manejo de marcas temporales / look-ahead
- **Location:** `src/sqp/backtesting/roi_engine.py:72-91` (`load_closing_odds`)
- **Evidence:** El código toma ahora el `commence_time` **de la fila con
  `captured_at` máximo** (`:77-78`) en vez de una arbitraria, y compara como
  timestamps UTC en vez de cadenas (`:69-72`). Ambos son parches a defectos
  reales y confirmados: KI-019 (commit `dad8433`, 2026-08-05) —precios EN VIVO
  admitidos como cierre porque el proveedor corrigió la hora de inicio de 16:00Z
  a 15:00Z— y M-30 (2026-07-24) —orden lexicográfico distinto del temporal por
  mezcla de sufijos `Z`/`+00:00`.
- **Impact:** Ninguno pendiente. Se documenta porque establece un patrón: **este
  módulo ha producido dos leaks temporales confirmados en seis semanas**, ambos
  detectados por inspección humana de un outlier y no por una prueba. Es la
  justificación principal para la Fase 4 del plan.
- **Recommendation:** Un test de invariante que falle si algún snapshot usado
  como cierre tiene `captured_at >= commence_time`, sobre datos reales.
- **Estimated remediation scope:** Small

---

### [DAT-07] El ajuste de parámetros y la ventana OOS podrían solaparse

- **Severity:** Medium
- **Confidence:** Requires verification
- **Category:** Contaminación train/test
- **Location:** `src/sqp/backtesting/tuning.py:25-38`
  (`DEFAULT_HOLDOUT_SPLITS`, `HOLDOUT_MIN_TRAIN_FRAC`, `MIN_EVAL_HOME_ADV`,
  `MIN_DRAWS_DC_RHO`, `IMPROVEMENT_MARGIN`), `:75-113`
  (`rolling_origin_improvement`), `:114-133` (`_gate`); ventana OOS en
  `src/sqp/backtesting/roi_engine.py:190,196-198` (`bet_from_date`)
- **Evidence:** `realized_roi_backtest` documenta correctamente su ventana OOS:
  *"parameters frozen on the train period (date < bet_from_date) are scored only
  on later, unseen games"* (`:196-198`). Lo que **no verifiqué** es si los
  parámetros que se congelan —`home_advantage` y `dc_rho`, ajustados por
  `tune_home_advantage:134` y `tune_dc_rho:180`— se ajustaron sobre un periodo
  estrictamente anterior a `bet_from_date`. Si `tune_*` se ejecuta sobre el
  histórico completo y después se evalúa con `bet_from_date`, la evaluación no es
  fuera de muestra.
- **Impact:** Si se confirma, invalida la cifra OOS como medida fuera de muestra:
  sería una evaluación in-sample con apariencia de OOS.
- **Failure scenario:** El −5.32% documentado es en realidad optimista respecto
  de un OOS auténtico, y la decisión de no desplegar —que es la correcta— se
  tomó por el margen equivocado.
- **Recommendation:** Trazar el orden real de ejecución en
  `scripts/validate_oos.py` y `VALIDATE_OOS.bat`: qué periodo ve `tune_*` y qué
  periodo ve `realized_roi_backtest`. **No asumir ninguna de las dos respuestas.**
- **Suggested validation:** Leer `scripts/validate_oos.py` y `scripts/tune_ratings.py`
  extremo a extremo y documentar las fechas de cada fase. Si se solapan,
  re-ejecutar con separación estricta y publicar ambas cifras.
- **Estimated remediation scope:** Medium

---

### [DAT-08] `load_closing_odds` concatena todo el histórico en cada llamada

- **Severity:** Low
- **Confidence:** Confirmed
- **Category:** Escalabilidad / fiabilidad
- **Location:** `src/sqp/backtesting/roi_engine.py:63-66`
- **Evidence:** `files = sorted(odds_dir.glob(f"odds_{league}_*.csv"))` seguido de
  `pd.concat([pd.read_csv(f) for f in files], ignore_index=True)`: carga en
  memoria **todos los meses** de cuotas de la liga por invocación, sin filtrar
  por el rango temporal que el llamador necesita.
- **Impact:** Heredado de la auditoría 2026-07-12 (`audit/latest/BACKLOG.md:97-100`).
  Hoy es tolerable; crece linealmente con el histórico, que es precisamente el
  activo que el proyecto está acumulando a propósito.
- **Failure scenario:** El backtest empieza a fallar por memoria justo cuando el
  histórico alcanza el tamaño que lo haría estadísticamente útil.
- **Recommendation:** Filtrar por rango de meses. Es la misma corrección
  propuesta hace tres semanas y sigue abierta.
- **Suggested validation:** Medir tiempo y memoria pico de una llamada actual
  para fijar la línea base.
- **Estimated remediation scope:** Medium
