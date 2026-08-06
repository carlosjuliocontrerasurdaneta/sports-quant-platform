# FINAL-AUDIT — Informe final consolidado

Proyecto: Sports Quant Platform · Commit base `7871bdb` · 2026-08-05
**No se modificó código de producción.**

Este documento reconcilia la auditoría original (`02`–`11`) con la verificación
independiente (`12`, `13`) y **la sustituye como fuente única**. Donde ambas
discrepan, prevalece la verificación, salvo en los dos puntos donde re-comprobé
la evidencia yo mismo y consta cuál fue el resultado.

---

## 1. Resumen ejecutivo

Hay que separar dos juicios que este proyecto invita constantemente a mezclar.

**Como software, el proyecto está sano.** 637 tests verdes, `ruff` y `mypy`
limpios, `pip-audit` sin vulnerabilidades, sin secretos versionados, todas las
llamadas HTTP con timeout, escrituras atómicas y capas de riesgo por defecto
denegatorias.

**Como sistema de apuestas, no ha demostrado nada.** El gate de CLV sigue vacío:
ningún (liga, mercado) alcanza mediana positiva con n≥30. ROI realizado −8.4% de
banca sobre 431 apuestas graduadas; OOS de la regla edge/Kelly −5.32%
(`audit/latest/QUANT_REVIEW.md:18-25`). **Ninguna corrección de este informe
cambia eso**, y ninguna lo pretende: son de corrección, integridad y
observabilidad.

### Qué cambió tras la verificación independiente

La auditoría original declaró 11 hallazgos altos. Tras verificación quedan
**tres**:

| | Original | Final |
|---|---:|---:|
| Críticos | 0 | 0 |
| **Altos** | **11** | **3** |
| Medios | 19 | 14 |
| Bajos / informativos | 26 | 26 |
| **Rechazados (falsos positivos)** | — | **2** |
| **Cerrados (el control ya existía)** | — | **1** |

Los tres altos supervivientes son [F-01] (valores no finitos envenenan el
no-vig), [F-02] (un CLV no finito puede aprobar el gate post-shadow) y [F-04]
(la prueba que protege el shadow mode se salta en el estado que debería vigilar).

**Errores propios que la verificación corrigió**, y que conviene leer antes que
cualquier otra cosa de este informe:

1. **DAT-01 era falso.** Afirmé que el backtest evaluaba precios que producción
   descarta. Es falso: `roi_engine.py:32-33` importa `_consensus_lines` de
   `pipeline.daily` y lo invoca en `:218`. Rastreé `load_closing_odds` y me
   detuve ahí, en vez de seguir el flujo hasta su consumidor — exactamente el
   error que el encargo pedía evitar. **Lo re-verifiqué yo mismo: la
   verificación tiene razón.**
2. **OPS-06 estaba cerrado.** Afirmé que no existía control automático que
   impidiera declarar `PASS` sin evidencia. Existe:
   `tests/test_claude_system_contract.py:126-140` y
   `scripts/claude_project_health.py:51-80`. Heredé la afirmación de
   `audit/latest/BACKLOG.md` sin comprobarla contra el árbol actual. **Re-verificado.**
3. **TST-04 era parcialmente falso.** `storage/lock.py` **sí** tiene tests
   dirigidos, vía el alias `odds_store._locked` (`tests/test_odds_store.py:64+`).
   Mi análisis por nombre de módulo no vio el import aliasado. **Re-verificado.**
4. **DAT-07 queda cerrado.** `scripts/validate_oos.py:148-150,168` ajusta
   estrictamente sobre el train previo al corte. Lo había marcado "requiere
   verificación"; la verificación lo resolvió a favor de la separación estricta.

El patrón de mis errores es uno solo: **inferir ausencia a partir de una
búsqueda, en vez de trazar el flujo.** Está recogido como causa raíz RC-4.

---

## 2. Alcance y limitaciones

**Cubierto:** árbol completo de `src/` (72 módulos, 10.643 líneas) y `tests/`
(81 archivos, 8.800 líneas), `pyproject.toml`, `Makefile`, `configs/**`,
`.github/workflows/ci.yml`, los seis `.bat` de orquestación, `docs/`, `scripts/`
(41 archivos) y `audit/latest/**`.

**Limitaciones, todas vinculantes para leer los resultados:**

| Limitación | Consecuencia |
|---|---|
| `data/`, `historical/`, `logs/`, `exports/` **no escaneados** (regla permanente del proyecto) | La **frecuencia real** de [F-03] no está medida; [F-13] no pudo re-medirse |
| `.env.example` — **lectura denegada por permisos** | La plantilla de secretos no se verificó en ninguna de las dos pasadas |
| Programador de tareas de Windows | Fuera del repositorio: "el sistema corre a las 11:00" es indemostrable desde aquí |
| La verificación independiente cubrió **solo altos y medios** (30 de 56) | Los 26 hallazgos bajos e informativos **no tienen verificación independiente** y se marcan como tales |
| Sin `pytest-cov` local | Toda afirmación de cobertura se apoya en análisis estático, no en líneas ejecutadas |

**Lo que esta auditoría no puede establecer:** si el sistema gana dinero
(ninguna fase lo midió); la ausencia de leakage (se encuentran rutas, no se
demuestra su inexistencia); el contenido de los datos.

---

## 3. Comandos de validación y estado de línea base

Verificado por ejecución (`audit/01-baseline-results.md`, re-ejecutado en esta
sesión):

| Comprobación | Comando | Resultado |
|---|---|---|
| Suite completa | `$env:PYTHONPATH='src'; python -m pytest tests/ -q` | **637 passed**, 0 failed, 0 skipped (62–65 s) |
| Lint | `ruff check src scripts tests` | All checks passed |
| Tipos | `mypy src` | 89 archivos, sin incidencias |
| Dependencias | `python -m pip check` | Sin requisitos rotos |
| Vulnerabilidades | `pip-audit -r requirements.lock` | 0 conocidas |
| Suite dirigida (verificación) | 12 archivos de test | **129 passed** en 14,27 s |
| Reproducciones | `python audit/reproductions/verify_high_medium.py` | Exit 0 |
| Formato | `ruff format --check` | 191 reformatearía — **estado esperado**: no adoptado por decisión (`pyproject.toml:41-46`) |
| Cobertura | `pytest --cov` | **No disponible**: `pytest-cov` no instalado |
| `make check` | — | **No disponible**: `make` no existe en el entorno |

Runtime local y de producción: **Python 3.14.4**. Matriz de CI: 3.11–3.13.
Esa discrepancia es [F-09].

---

## 4. Hallazgos confirmados, por severidad

### ALTOS

---

#### [F-01] Los valores no finitos atraviesan toda la cadena de no-vig y anulan el mercado completo en silencio

- **Severidad:** Alta
- **Confianza:** Confirmado (reproducido de forma independiente)
- **Ubicación:** `src/sqp/pipeline/probabilities.py:27` (`_consensus_lines`),
  `:37-43` (`_consensus_counts`); `src/sqp/markets/vig.py:28`
  (`remove_vig_power`) y `:16` (`remove_vig_proportional`)
- **Evidencia:** Tres guards consecutivos fallan por la misma propiedad de
  IEEE-754 —toda comparación con `NaN` es `False`—:
  `ln.price_decimal <= 1.0` no filtra `NaN`; `any(p <= 0 or p >= 1)` no lo
  detecta y `brentq` lo recibe; `if s <= 0: raise` no dispara y el fallback
  proporcional devuelve `NaN/NaN`. Reproducción V4:
  `"consensus and both fair probabilities are NaN"`, con el único aviso emitido
  siendo `power de-vig found no root`, que señala el síntoma equivocado.
  **Absorbe COR-03:** `_consensus_counts` tampoco aplica el predicado, así que
  `books_count` cuenta líneas que el consenso descartó — reproducido:
  `consensus_home=1.9; count_home=2` con una cuota válida y una degenerada.
- **Impacto:** Pérdida silenciosa de eventos en el pipeline **vivo**
  (`daily.py:585`), sin contador ni aviso correcto. Además, `books_count`
  inflado desactiva `low_book_penalty` justo en los mercados finos, y se
  persiste en el served stream (`daily.py:662`) contaminando cualquier análisis
  posterior por profundidad de mercado.
- **Recomendación:** Un **único predicado compartido** de línea utilizable
  (`math.isfinite(price) and price > 1.0`) invocado desde el cálculo de consenso,
  el conteo de casas y el de-vig, más **telemetría explícita de líneas
  descartadas** en el log del run. La telemetría no es opcional: sin ella el
  arreglo es indistinguible del defecto.
- **Validación:** Test que pase un `EventOdds` con un precio `NaN` y afirme que
  (a) el resto de mercados del evento sigue produciendo candidatos, (b) el
  descarte queda registrado y (c) `books_count` refleja solo líneas utilizables.
- **Esfuerzo:** Medio
- **Dependencias:** Ninguna. **Es la dependencia de [F-02] y [F-03].**

---

#### [F-02] Un CLV no finito puede aprobar un mercado en el gate que gobierna el stake real

- **Severidad:** Alta (latente bajo `shadow_mode: true`)
- **Confianza:** Confirmado (reproducido de forma independiente)
- **Ubicación:** `src/sqp/risk/clv_gate.py:34` (`gate_decisions`), alimentado por
  `src/sqp/audit/clv.py:128-133` (`clv_segments`)
- **Evidencia:** Reproducción V4 con 29 filas `NaN` y una `inf`:
  `n=30; median=inf; allowed=true`. Se componen dos propiedades:
  `clv_segments` agrega con `n=("clv_pct","size")`, que **cuenta** filas no
  finitas mientras `median` salta los `NaN`; y `pandas.median` **no** ignora
  `inf`, de modo que una sola fila lleva la mediana a `inf`, e `inf > 0` es
  `True`.
- **Impacto:** `market_allowed` es la regla vinculante de salida del shadow mode
  (`configs/default.yaml:101-110`). Hoy el impacto monetario es **cero** porque
  `shadow_mode` pone todos los stakes a 0 y tiene precedencia
  (`daily.py:389-392`). El día que se levante, un precio corrupto puede autorizar
  dinero real sobre evidencia inexistente.
- **Recomendación:** Dos correcciones, ambas necesarias: (a) `clv_segments` debe
  contar solo filas finitas; (b) `gate_decisions` debe exigir
  `np.isfinite(median_clv_pct)` además de `> 0`.
- **Validación:** Test que construya un segmento con una fila `inf` y afirme
  `allowed == False`. Después re-ejecutar `scripts/clv_analysis.py` y comparar
  `data/bets/clv_gate.json`: hoy debe seguir **sin ningún mercado aprobado**. Si
  algún mercado desaparece del registro, el `n` estaba inflado y hay que decirlo.
- **Esfuerzo:** Pequeño
- **Dependencias:** Conceptualmente [F-01] (mismo predicado). Puede corregirse
  antes, pero **debe estar cerrado antes de cualquier salida del shadow mode**.

---

#### [F-04] La prueba que protege el shadow mode se salta a sí misma en el estado que debería vigilar

- **Severidad:** Alta
- **Confianza:** Confirmado
- **Ubicación:** `tests/test_audit_2026_07_29.py:142-152`
  (`test_b08_production_yaml_shadow_survives_unrecognized_env`)
- **Evidencia:** `if not cfg.get("shadow_mode"): pytest.skip(...)`. El propósito
  declarado del test es impedir que `shadow_mode` se desactive; su primera acción
  es saltarse si `configs/default.yaml` deja de declararlo. La verificación
  añade que **ningún otro test** exige que el YAML de producción siga en shadow
  ni registra una transición aprobada.
- **Impacto:** El control está invertido. Una edición que desactive el shadow
  mode deja los 637 tests verdes y la única prueba que existe para impedirlo se
  salta en silencio. La suite actual reporta **0 saltados**, lo que confirma que
  hoy sigue en `true`.
- **Recomendación:** Sustituir el `skip` por un fallo explícito, salvo que exista
  una invariante de aprobación registrada (una entrada en el registro de
  decisiones que el test pueda leer). Desactivar el shadow mode debe ser posible,
  pero nunca en silencio.
- **Validación:** Cambiar `shadow_mode` a `false` en una copia y comprobar que la
  suite **falla**. Hoy pasaría.
- **Esfuerzo:** Pequeño
- **Dependencias:** Ninguna. Es el hallazgo de mejor relación valor/esfuerzo del
  informe.

---

### MEDIOS

---

#### [F-03] La liquidación fabrica resultados cuando la línea no es finita

- **Severidad:** Media (corregida desde Alta: el defecto está probado, su
  alcance real no)
- **Confianza:** Confirmado en comportamiento · **alcance operativo sin medir**
- **Ubicación:** `src/sqp/settlement/settle.py:39-41` (spreads) y `:42-44` (totals)
- **Evidencia:** Reproducido de forma independiente (V4), marcador 5–4:
  `totals/Under/NaN → win`; `totals/Over/NaN → loss`; `spreads/NaN → loss`;
  control `totals/Under/8.5 → loss` (correcto). El resultado **no depende del
  marcador**. Contra-evidencia que justifica la rebaja: la construcción normal de
  candidatos exige un `total` no nulo seleccionado por `_pick_main_lines`, y un
  `point` ausente en el JSON llega como `None`, no como `NaN`. **La
  alcanzabilidad en datos persistidos no pudo comprobarse** por la prohibición de
  leer `data/`.
- **Impacto:** Si es alcanzable, corrompe simultáneamente ROI realizado,
  etiquetas de entrenamiento del calibrador y hit rate. Un `win` fabricado es
  peor que una fila perdida: entra en los agregados como evidencia válida. El
  sesgo es además asimétrico (Under gana, Over y spreads pierden).
- **Recomendación:** Un guard único de línea finita en `_grade` que devuelva
  `void` —no `push`: `push` afirma que la apuesta existió y se devolvió el stake;
  `void` afirma que no se pudo graduar, que es lo cierto.
- **Validación:** **Primero medir, después corregir.** Contar filas de
  `spreads`/`totals` con `line` no finita en `data/bets/settled_*.csv` (requiere
  autorización explícita). Si es 0, la corrección es preventiva; si no, hay que
  re-liquidar y republicar las métricas afectadas con el delta explícito.
- **Esfuerzo:** Pequeño (corrección) + Medio (auditoría de datos y posible
  re-liquidación)
- **Dependencias:** [F-17] (tests en rojo) debe ir antes. Comparte causa raíz con
  [F-01] pero es un módulo y una corrección distintos.

---

#### [F-05] Acoplamiento oculto entre `market_shrink` y los controles de edge

- **Severidad:** Media
- **Confianza:** Confirmado (reproducido)
- **Ubicación:** `src/sqp/pipeline/daily.py:628-640` y `:630,668`, compuesto con
  `src/sqp/pipeline/probabilities.py:119-124`; documentación en
  `configs/default.yaml:11-26`
- **Evidencia:** Reproducción V4: modelo 0.60, justa 0.50, shrink 0.50 →
  decisión 0.55; `adjusted_edge` ve un gap de 0.05 y aplica 0.0175, es decir un
  **coeficiente efectivo de 0.175** sobre el desacuerdo real de 0.10, frente al
  `uncertainty_penalty: 0.35` configurado. El mismo efecto aplica a
  `max_plausible_edge`, que se evalúa sobre `edge(p_decision, price)` (`:630`),
  ya encogido. Ocho líneas de comentario en el YAML justifican el 0.35 con
  evidencia OOS y **ninguna menciona el acoplamiento**.
- **Impacto:** El comportamiento compuesto fue validado OOS y es determinista, así
  que **no hay un comportamiento inseguro demostrado** — por eso es Media y no
  Alta. El daño es de gobernanza: el registro de decisiones cuantitativas del
  proyecto describe un parámetro con el doble de su efecto real, justo donde más
  se consulta. Y `market_shrink` mueve la penalización sin que nadie toque
  `uncertainty_penalty`.
- **Recomendación:** **Documentar, no cambiar.** Los valores están validados tal
  como se componen; alterarlos invalida esa evidencia. Corregir los comentarios
  del YAML y decidir explícitamente si la plausibilidad debe medirse sobre el
  edge crudo del modelo o sobre el de decisión.
- **Validación:** Test de propiedad que fije
  `penalty == (1 − market_shrink) · uncertainty_penalty · |p_cal − fair|`. Ese
  test convierte el acoplamiento en algo que se rompe visiblemente.
- **Esfuerzo:** Pequeño
- **Dependencias:** Ninguna. (Absorbe QNT-01, QNT-02 y OPS-03.)

---

#### [F-06] Cualquier advertencia de fiabilidad excluye el evento del stream de calibración

- **Severidad:** Media
- **Confianza:** Confirmado (frecuencia sin medir)
- **Ubicación:** `src/sqp/pipeline/daily.py:581`, `:616`; el `served.append` está
  en `:650`, después del `continue`
- **Evidencia:** `warn` es una cadena; cualquier valor no vacío salta todas las
  selecciones del evento, incluida su grabación en el served stream. La
  verificación acotó el origen de las advertencias: muestra escasa de ratings,
  abridores de béisbol desconocidos y eventos ya comenzados
  (`sports/base.py:50-54`, `sports/adapters.py:186-195`, `daily.py:582-584`).
- **Impacto:** El served stream existe explícitamente para entrenar el calibrador
  sobre la distribución completa servida y evitar el sesgo de selección
  (`daily.py:646-649`). Excluir eventos con advertencia lo reintroduce por la
  puerta de atrás. Para eventos ya comenzados la exclusión es correcta; para
  muestra escasa o abridor desconocido **contradice el propósito declarado**.
- **Recomendación:** Separar *grababilidad* de *elegibilidad para stake*: seguir
  excluyendo del staking, pero registrar en el served stream. Medir primero.
- **Validación:** Contar en un run real qué fracción de eventos queda fuera del
  served stream por esta vía, desglosada por tipo de advertencia. **Sin esa
  medición no puede afirmarse que el sesgo sea material.**
- **Esfuerzo:** Pequeño (cambio) + Pequeño/Medio (medición previa)
- **Dependencias:** Ninguna.

---

#### [F-07] Sin límite de exposición por evento, con Kelly aplicado a selecciones correlacionadas

- **Severidad:** Media (crítica tras la salida del shadow mode)
- **Confianza:** Confirmado
- **Ubicación:** `src/sqp/risk/kelly.py:14-27`, invocado en el bucle
  `src/sqp/pipeline/daily.py:614-645`; `model_map` construido en `:602-612`
- **Evidencia:** `model_map` puede contener hasta seis selecciones del **mismo
  evento** (h2h ambos lados y empate, ambos lados del spread, Over/Under), cada
  una dimensionada de forma independiente. La búsqueda en el repositorio no
  encontró ningún cap por evento. Los caps existentes —por apuesta, por liga y
  día, y global del día— acotan el **agregado**, no la **concentración**.
- **Impacto:** Kelly presupone independencia; el resultado de un partido
  determina simultáneamente h2h, spread y parcialmente el total. Post-shadow, un
  solo resultado adverso puede pegar varias veces el máximo por apuesta previsto.
- **Recomendación:** **Medir antes de decidir.** Es una decisión de política de
  riesgo del operador, no una corrección: puede resolverse con un cap por evento
  o excluyendo selecciones correlacionadas.
- **Validación:** Sobre el histórico de candidatos, distribución del stake
  agregado por `event_id` frente a `max_stake_pct · bankroll`. Si el p95 ya lo
  excede, el riesgo es actual.
- **Esfuerzo:** Medio
- **Dependencias:** Bloqueante para la salida del shadow mode.

---

#### [F-08] El lock puede colgar el run diario y, cuando cede, escribe igual

- **Severidad:** Media
- **Confianza:** Confirmado (reproducido)
- **Ubicación:** `src/sqp/storage/lock.py:41-52` (bucle) y `:48-51` (degradación)
- **Evidencia:** Dos defectos del mismo módulo, tratados aquí como uno solo para
  no duplicar la remediación (absorbe COR-04 y PRF-02):
  (a) el `continue` de `:47` salta tanto la comprobación de `deadline` (`:48`)
  como `time.sleep(0.25)` (`:52`); reproducción V4 con `Path.stat` fallando de
  forma persistente: el proceso hijo **seguía vivo tras 0,5 s con
  `timeout_s=0.05`**, diez veces su timeout, y hubo que terminarlo.
  (b) al agotarse el timeout ordinario, `locked` registra un warning y **cede el
  control sin poseer el lock** (`:49-51`), y los consumidores hacen
  read-modify-write igualmente.
- **Impacto:** (a) es un cuelgue del run diario al 100% de CPU que `timeout_s` no
  rescata. (b) es un intercambio deliberado y documentado —bloquear el pipeline
  sería peor—, pero deja abierta la condición que el lock existe para evitar:
  una revocación perdida o unos candidatos sobrescritos. Bajo shadow el coste es
  evidencia corrupta, no dinero.
- **Recomendación:** (a) comprobar el deadline y dormir también en la rama
  `OSError`. (b) **no** cambiar el fail-open ahora; persistir el estado degradado
  en `monitoring/run_status.py` para que sea visible en el dashboard, y
  reconsiderarlo antes de operar con dinero real.
- **Validación:** Test con `Path.stat` parcheado para fallar siempre, afirmando
  que `locked` retorna en ≤ `timeout_s`. Hoy ese test **colgaría** — que es la
  demostración. Debe escribirse con timeout de proceso para no bloquear la suite.
- **Esfuerzo:** Pequeño
- **Dependencias:** Ninguna.

---

#### [F-09] Se opera sobre una versión de Python que ninguna puerta valida

- **Severidad:** Media
- **Confianza:** Confirmado
- **Ubicación:** `.github/workflows/ci.yml:19-21` (matriz 3.11–3.13);
  runtime verificado 3.14.4; `.bat` con `SQP_PYTHON` → `Python314`
- **Evidencia:** El intérprete de producción y el de desarrollo son 3.14.4; la
  matriz de CI cubre 3.11, 3.12 y 3.13. El propio `ci.yml:17-18` lo reconoce.
  Contra-evidencia: la suite completa pasa localmente en 3.14.4 — evidencia útil,
  pero no una puerta.
- **Impacto:** Una regresión específica de 3.14 pasa el CI y falla solo en
  producción. El proyecto ya tiene un precedente de esta familia documentado en
  `Makefile:1-3`: una versión distinta de `joblib`/`scikit-learn` puede
  deserializar mal los artefactos `.joblib`.
- **Recomendación:** Añadir 3.14 a la matriz (aunque sea `continue-on-error`) **o**
  fijar el intérprete de producción a una versión de la matriz. El estado actual
  —operar fuera de la matriz sin ninguna de las dos— es el peor de los tres.
- **Validación:** Suite completa en 3.13 y en 3.14, comparadas.
- **Esfuerzo:** Pequeño
- **Dependencias:** Ninguna.

---

#### [F-10] `_model_map` duplicado literalmente entre producción y backtest

- **Severidad:** Media
- **Confianza:** Confirmado
- **Ubicación:** `src/sqp/pipeline/daily.py:602-612` y
  `src/sqp/backtesting/roi_engine.py:159-170`
- **Evidencia:** Ambos construyen el mismo mapa `(mercado, selección, punto) →
  probabilidad`, con las mismas seis entradas y las mismas convenciones de signo.
  No hay helper compartido ni invariante de igualdad que impida la deriva.
- **Impacto:** Añadir un mercado o cambiar una convención exige dos ediciones
  coherentes; una sola produce un backtest que evalúa una política distinta de la
  desplegada, en silencio. **Nota:** el resto del camino de precios **sí** está
  compartido — ver §6, DAT-01 rechazado.
- **Recomendación:** Extracción mecánica a un helper compartido.
- **Validación:** Test que afirme que ambos caminos producen claves idénticas
  para el mismo `EstimatedProbabilities`.
- **Esfuerzo:** Pequeño
- **Dependencias:** Ninguna.

---

#### [F-11] El emparejamiento resultado↔cuotas depende del orden de entrada

- **Severidad:** Media
- **Confianza:** Confirmado (reproducido)
- **Ubicación:** `src/sqp/backtesting/roi_engine.py:119-146` (`_match_result`)
- **Evidencia:** Reproducción V4: con dos eventos de cuotas del mismo par y día y
  dos resultados, **invertir el orden de los resultados intercambia** cuál recibe
  el evento `early` y cuál el `late`. La selección es determinista para un
  resultado dado (menor distancia en días, desempate por `start_time`), pero la
  asignación global no lo es, porque el emparejamiento es codicioso con consumo
  (`used`).
- **Impacto:** El backtest no es reproducible bit a bit ante una reordenación de
  la entrada. La reproducibilidad es un requisito declarado
  (`.claude/rules/modeling-rules.md`). Fechas cronológicamente únicas reducen la
  frecuencia práctica.
- **Recomendación:** Ordenar `results` explícitamente por (fecha, event_id) antes
  del emparejamiento, o resolverlo como asignación global.
- **Validación:** Ejecutar el backtest dos veces con `results` barajado y
  comparar ROI y n.
- **Esfuerzo:** Pequeño
- **Dependencias:** Ninguna.

---

#### [F-12] `run_league` concentra seis responsabilidades en 265 líneas

- **Severidad:** Media
- **Confianza:** Confirmado
- **Ubicación:** `src/sqp/pipeline/daily.py:476-740`; bucle de mercados en
  `:614-725` (111 líneas)
- **Evidencia:** Selección de proveedor y fetch, ajuste de ratings, consenso y
  no-vig, construcción del `model_map`, edge y staking, persistencia y cap de
  exposición, todo en una función. La verificación matiza que `_finalize`, los
  helpers de probabilidad y los de cap **ya están extraídos**, lo que acota la
  crítica sin invalidarla.
- **Impacto:** Es la razón estructural de [F-05]: la composición del shrink con
  los controles de edge no es visible leyendo ninguna etapa por separado.
- **Recomendación:** Extraer el bucle de mercados a una función pura
  `score_market_side(...) -> BetCandidate | None`, sin E/S. **Solo después de que
  existan tests que fijen el comportamiento.**
- **Validación:** Los tests de [F-05] y [F-17] deben pasar sin modificación antes
  y después de la extracción.
- **Esfuerzo:** Medio
- **Dependencias:** [F-05], [F-17]. **No hacerlo antes.**

---

#### [F-13] Filas servidas que nunca se gradúan (sesgo de supervivencia)

- **Severidad:** Media *pendiente de re-medición* (rebajada desde Alta: el conteo
  es heredado)
- **Confianza:** Requiere verificación — **bloqueado por el entorno**
- **Ubicación:** `src/sqp/monitoring/health.py:78-97` (`_served_pending_expired`);
  política de expiración en `src/sqp/settlement/settle.py:18,79-108`
- **Evidencia:** El mecanismo de detección **existe y funciona**. El conteo de 54
  filas (chile 42, tennis_atp_canadian_open 12) procede de
  `.claude/automation/runtime/current-task.md:65`, un artefacto previo. **Ninguna
  de las dos pasadas pudo re-medirlo**: requiere leer datos del proyecto.
- **Impacto:** Las filas no graduadas salen de todos los agregados sin dejar
  rastro en el denominador. Si la falta de graduación se correlaciona con la liga
  —y la concentración en dos ligas sugiere que sí—, el sesgo es sistemático.
- **Recomendación:** No mantener la severidad Alta apoyada solo en un conteo
  heredado. Re-medir y decidir.
- **Validación:** Con autorización explícita de datos: `python scripts/health_check.py`
  → objetivo OK (0/0), o filas anuladas con flag y razón registrada.
- **Esfuerzo:** Pequeño (ejecución) + Medio (si falta vendor de resultados)
- **Dependencias:** Autorización del operador (el settle consume cuota de API).

---

#### [F-14] El precio registrado no está ligado a una cuota ejecutable

- **Severidad:** Media
- **Confianza:** Confirmado parcialmente — **mi formulación original era
  categórica y falsa**
- **Ubicación:** `src/sqp/pipeline/daily.py:656,714`
  (`bookmaker="consensus_median"`); precio en `probabilities.py:33`
- **Evidencia:** Afirmé que el precio de mediana "no lo ofrece ninguna casa". Es
  **falso con un número impar de cotizaciones**: la verificación reprodujo
  `[1.8, 2.0, 2.2] → 2.0`, ofrecido = verdadero. Con número par, la mediana es la
  media de las dos centrales y **sí** puede ser sintética (reproducido:
  ofrecido = falso). Lo que se sostiene: el candidato no conserva **de qué casa**
  vino el precio, ni modela accesibilidad ni límites de apuesta.
- **Impacto:** Riesgo de disponibilidad del precio de ejecución, no de precio
  fabricado. El ROI se calcula contra una cuota cuya obtenibilidad no está
  registrada.
- **Recomendación:** Conservar la procedencia de la cotización (qué casa ofrecía
  el precio usado) y modelar la disponibilidad antes de operar con dinero real.
- **Validación:** Recalcular el ROI histórico con el precio del percentil 25 en
  vez de la mediana: la diferencia acota el optimismo del supuesto.
- **Esfuerzo:** Medio
- **Dependencias:** Ninguna.

---

#### [F-15] `clv_movement` mantiene una implementación de consenso propia

- **Severidad:** Media
- **Confianza:** Confirmado parcialmente — **residuo de un hallazgo sobredimensionado**
- **Ubicación:** `src/sqp/audit/clv_movement.py:40-55`
  (`snapshot_consensus_price`)
- **Evidencia:** Afirmé que el camino precios→consenso existía **tres** veces.
  Son **dos**: producción (`daily.py:585`), backtest (`roi_engine.py:218`) y la
  auditoría de CLV (`clv.py:77`) llaman **todos** al mismo `_consensus_lines`.
  Solo `clv_movement` conserva implementación separada. La deriva histórica (B-13)
  es real; su alcance actual es un módulo, no tres.
- **Impacto:** Un cambio en la definición de línea utilizable —exactamente lo que
  pide [F-01]— debe replicarse en `clv_movement` o el análisis de movimiento
  quedará con la definición antigua sin que nada lo señale.
- **Recomendación:** Unificar `clv_movement` con el predicado compartido de [F-01].
- **Validación:** Test que afirme que ambos caminos descartan el mismo conjunto
  de líneas para un `EventOdds` dado.
- **Esfuerzo:** Pequeño
- **Dependencias:** [F-01] debe definir el predicado primero.

---

#### [F-16] El gate de CLV decide por "mediana > 0" sin inferencia

- **Severidad:** Media (rebajada de la sobregeneralización original)
- **Confianza:** Confirmado en lo que respecta al gate de CLV
- **Ubicación:** `src/sqp/risk/clv_gate.py:23,34`
- **Evidencia:** `gate_decisions` exige únicamente `n >= 30` y `median > 0`: una
  mediana de +0.01% aprueba igual que una de +3%, sin intervalo ni test.
  **Contra-evidencia que acota mi hallazgo original:** afirmé que tres decisiones
  compartían "el mismo n=30 desnudo". Es falso — el monitor de degradación añade
  márgenes de Brier/ROI e histéresis (`degradation.py:31-125`) y la promoción
  automática exige gates OOS de ECE, Brier y monotonía y está **desactivada por
  defecto** (`auto_promote: false`). Solo el gate de CLV decide con el umbral
  desnudo.
- **Impacto:** El signo de una mediana con n=30 es difícilmente distinguible del
  ruido. El proyecto ya llegó a esa conclusión en otro contexto y actuó: el gate
  intradía se reformuló como **test de signo con p<0.05** (KI-020, 2026-08-05).
  El gate de CLV no recibió el mismo tratamiento.
- **Recomendación:** Alinear el gate de CLV con el criterio ya adoptado para el
  intradía. Es coherencia interna, no una idea nueva. Revisar los otros umbrales
  por separado, no como grupo.
- **Validación:** Recalcular el registro con el criterio de signo y comprobar que
  ningún mercado que hoy pasaría deja de pasar por azar.
- **Esfuerzo:** Medio
- **Dependencias:** [F-02] (primero garantizar métricas finitas).

---

## 5. Hallazgos parcialmente confirmados

Los siguientes se sostienen en su núcleo pero **mi formulación original los
sobredimensionaba**. La contra-evidencia forma parte del hallazgo.

| ID | Núcleo que se sostiene | Lo que era falso o excesivo | Severidad final |
|---|---|---|---|
| [F-03] | El defecto de grading con línea no finita es real y reproducible | Que fuera alcanzable en producción: no se pudo medir | Media |
| [F-13] | El mecanismo de sesgo por supervivencia existe | Que hoy sean 54 filas: conteo heredado, no re-medido | Media pendiente |
| [F-14] | La procedencia del precio ejecutable no se conserva | "Ningún libro ofrece la mediana": falso con n impar de casas | Media |
| [F-15] | Existe una implementación de consenso divergente | Que fueran tres: son dos, y backtest/producción comparten guard | Media |
| [F-16] | El gate de CLV decide sin inferencia | Que los tres umbrales de n=30 fueran equivalentes: no lo son | Media |
| [F-19] | Faltan tests de rutas de fallo en `lock`/`atomic` | Que `storage.lock` no tuviera tests dirigidos: **sí los tiene** vía `odds_store._locked` | Baja |
| [F-20] | La cobertura no es bloqueante y falta en local | "No existe medición": el CI sí produce tabla informativa | Baja |
| [F-21] | El backtest carece de cap global entre ligas | El escenario de N× exposición: no existe backtest multi-liga combinado que lo requiera | Baja |

---

## 6. Hallazgos rechazados o no verificados

### Rechazados como falsos positivos

**[DAT-01] — El backtest NO evalúa precios que producción descarta.**
`roi_engine.py:32-33` importa `_consensus_lines` de `pipeline.daily` y lo invoca
en `:218`; el precio del candidato sale de ese consenso filtrado en `:227`. Las
cuotas degeneradas se descartan con **el mismo guard** que en vivo. Mi error:
rastreé `load_closing_odds` —que efectivamente deserializa líneas crudas— y no
seguí el flujo hasta su consumidor. **Re-verificado por mí; la verificación tiene
razón.** No hay ninguna corrección de paridad justificada por esta evidencia.

**[DAT-07] — El ajuste de parámetros NO se solapa con la ventana OOS.**
`scripts/validate_oos.py:148-150` construye `train` estrictamente antes del
corte; `_freeze_on_train(train, ...)` en `:168` ajusta solo ese subconjunto; el
ROI se puntúa con `bet_from_date=cutoff`. El script además etiqueta por separado
los parámetros de histórico completo como optimistas, en vez de presentarlos
como congelados. Lo había marcado "requiere verificación": la separación es
estricta.

### Cerrado — el control ya existía

**[OPS-06] — El control automático de evidencia PASS existe.**
Afirmé que nada impedía declarar `PASS` sin evidencia y que B-1 seguía abierto.
Es falso en el árbol actual: `scripts/claude_project_health.py:51-80,129-141`
valida las secciones de evidencia y `tests/test_claude_system_contract.py:126-140`
lo prueba en casos sintéticos y reales (`test_pass_without_evidence_is_flagged`).
**Re-verificado por mí.** El fallo de proceso histórico del 2026-08-04 está
documentado y es real; el hallazgo accionable no lo es. Se marca **cerrado** y se
conserva el test.

### No verificados (fuera del alcance de la verificación independiente)

La verificación cubrió los 30 hallazgos altos y medios. Los siguientes **no
tienen verificación independiente** y conservan la confianza de la auditoría
original:

| ID orig. | Severidad | Estado |
|---|---|---|
| COR-06 | Baja | `remove_vig_power` solo captura `ValueError`; `RuntimeError` de `brentq` propagaría — **requiere verificación** contra la versión de SciPy pineada |
| COR-07 | Baja | `atomic_write_csv` sin `fsync` antes del `replace` — confirmado por lectura |
| COR-08 | Baja | La comprobación de temporada falla-abierto hacia el gasto de cuota — confirmado por lectura |
| QNT-08 | Baja | El no-vig de h2h agrupa sin filtrar por `point` — **requiere verificación** de alcanzabilidad |
| DAT-08 / PRF-03 | Baja | `load_closing_odds` concatena todo el histórico — confirmado por lectura |
| SEC-04 | Baja | Deserialización `joblib` desde `data/models/` — mecanismo confirmado, modelo de amenaza sin establecer |
| SEC-05 | Baja | 5 manejadores amplios sin registrar la excepción — confirmado por lectura |
| SEC-06 | Info | `.env.example` — **lectura denegada por permisos en ambas pasadas** |
| ARCH-04, ARCH-05, ARCH-06 | Baja/Info | Duplicación de agregación de CLV, mezcla cálculo/presentación en `html_report.py`, prohibición de ciclos sin test |
| OPS-02, OPS-04 | Baja | `make` no disponible; 4 residuos de shell sin trackear en la raíz |
| PRF-04, OPS-05 | Info | Camino de invocación de Monte Carlo; estado del Programador de tareas |

### Controles verificados sin hallazgos

Registrados para que conste qué se comprobó: timeouts en las 8 llamadas HTTP;
redacción de `apiKey` implementada en ambos caminos de error; único `subprocess`
seguro y sin `eval`/`exec`/`shell=True`; condicionamiento de empates correcto en
el backtest de calibración; idempotencia del served stream; orquestación BAT
coherente con lo documentado; `pick_mode` documentado y configurado coinciden; el
lenguaje obligatorio está implementado en código, no solo en la documentación.

---

## 7. Causas raíz transversales

Cuatro patrones explican 20 de los 24 hallazgos vivos. **Corregir el patrón vale
más que corregir sus instancias.**

### RC-1 — Ningún invariante de valor finito (afecta a F-01, F-02, F-03, F-15)

Siempre la misma mecánica: una comparación (`<= 1.0`, `>= 1`, `<= 0`, `> 0`)
que devuelve `False` ante `NaN` y deja pasar el valor. Recorre `probabilities.py`,
`vig.py`, `settle.py`, `clv.py` y `clv_gate.py`. **Un solo predicado compartido,
más telemetría de descartes, cierra el patrón.** Es la primera prioridad del
programa.

### RC-2 — Composición de controles invisible (afecta a F-05, F-12)

`run_league` aplica el shrink de mercado **antes** que los controles que deberían
mirar el desacuerdo crudo, lo que reduce a la mitad la penalización y el tope de
plausibilidad sin que nada lo indique. No es un error de cálculo: es que la
composición no es legible en ningún punto del código ni de la configuración.

### RC-3 — Los tests miran hacia atrás (afecta a F-04, F-17, F-19, F-22)

La suite es excelente en regresiones vividas —cada defecto tiene su prueba con
fecha e identificador del incidente— y está ausente en **estados degradados aún
no vividos**: línea no finita, `stat()` fallando, invariantes de las funciones
puras. El caso extremo es [F-04], donde el test de seguridad está invertido.

### RC-4 — Inferir ausencia a partir de una búsqueda (afecta a la auditoría misma)

Es la causa raíz de mis cuatro errores: DAT-01 (rastreé un archivo, no el flujo),
OPS-06 (heredé una afirmación sin comprobarla contra el árbol actual), TST-04
(grep por nombre de módulo que no vio el import aliasado) y DAT-03 (afirmación
categórica sin comprobar el caso impar). **Se registra aquí porque afecta a cómo
debe leerse todo hallazgo de tipo "no existe X"**, incluidos los 12 no
verificados de §6.

---

## 8. Victorias rápidas

Todas pequeñas, sin dependencias entre sí, y cada una cierra o previene un riesgo
real. Suman menos de un día.

| # | Acción | ID | Por qué ahora |
|---|---|---|---|
| 1 | Invertir el `skip` del test de shadow mode | [F-04] | Un `if` por un `raise`. Hoy la red de seguridad tiene un agujero conocido |
| 2 | Exigir métricas finitas en `clv_segments` y `gate_decisions` | [F-02] | Dos condiciones. Cierra un alto latente |
| 3 | Corregir los comentarios de `configs/default.yaml` sobre el acoplamiento | [F-05] | Solo documentación; el comportamiento está validado OOS |
| 4 | Deadline y sleep en la rama `OSError` del lock | [F-08a] | Reordenar tres líneas; elimina un cuelgue del run diario |
| 5 | Añadir 3.14 a la matriz de CI | [F-09] | Una línea de YAML |
| 6 | Ordenar `results` antes del emparejamiento | [F-11] | Un `sorted()`; devuelve reproducibilidad al backtest |
| 7 | Extraer `_model_map` a un helper compartido | [F-10] | Extracción mecánica con test de paridad |
| 8 | `pytest-cov` en las dependencias `dev` | [F-20] | Habilita medir; hoy no se puede |
| 9 | Borrar los 4 residuos de shell de la raíz | OPS-04 | Requiere confirmación: no los creé y son irrecuperables |

---

## 9. Hoja de ruta de remediación de alto riesgo

Los cambios que **pueden mover cifras publicadas o el comportamiento de
producción**. Ninguno debe hacerse sin la secuencia de §10.

| Riesgo | Qué cambia | Salvaguarda obligatoria |
|---|---|---|
| **Predicado de valor finito** [F-01] | Qué líneas entran en el consenso, el conteo de casas y el de-vig | Ejecutar `scripts/clv_analysis.py` y el backtest antes y después; **publicar el delta de n y de ROI**. Un delta de 0 significa que el histórico reciente estaba limpio |
| **Guard de liquidación** [F-03] | Filas que hoy se gradúan `win`/`loss` pasarían a `void` | **Medir primero** con autorización de datos. Si hay filas afectadas, re-liquidar y republicar ROI, calibración y hit rate con el delta explícito |
| **Gate de CLV finito** [F-02] | El `n` de todos los segmentos puede bajar | Comparar `clv_gate.json` antes y después. Hoy debe seguir **sin ningún mercado aprobado**; si alguno desaparece, el `n` estaba inflado y hay que decirlo |
| **Cap por evento** [F-07] | Qué apuestas sobreviven, no solo su tamaño | Decisión del **operador**. Medir la concentración actual antes de elegir política |
| **Criterio de inferencia del gate** [F-16] | La regla de salida del shadow mode | Cambio de criterio pre-registrado **antes** de mirar el resultado, como se hizo con KI-020 |
| **Extraer el bucle de mercados** [F-12] | Nada, si se hace bien | Los tests de [F-05] y [F-17] deben pasar **sin modificación** antes y después |

---

## 10. Secuencia de remediación recomendada

Criterio: **evidencia primero.** Mientras la liquidación pueda fabricar
resultados y el gate pueda aprobarse con un valor no finito, cualquier otra
corrección se valida contra números en los que no se puede confiar.

| Paso | Qué | IDs | Dependencias |
|---|---|---|---|
| 0 | Tests que documenten el defecto, **en rojo** | [F-17], [F-18] | — |
| 1 | Victorias rápidas 1, 3, 4, 5, 6, 8 de §8 | [F-04], [F-05], [F-08a], [F-09], [F-11], [F-20] | Ninguna entre sí |
| 2 | Predicado único de valor finito + telemetría de descartes | [F-01] | Paso 0 |
| 3 | Guard de finitud en agregación y gate de CLV | [F-02] | Paso 2 (mismo predicado) |
| 4 | Unificar `clv_movement` con el predicado | [F-15] | Paso 2 |
| 5 | Medir alcance en datos y guard de liquidación | [F-03] | Paso 0 + **autorización de datos** |
| 6 | Re-medir filas pendientes | [F-13] | **Autorización del operador** (consume cuota) |
| 7 | Medir concentración por evento; decidir política | [F-07] | **Decisión del operador** |
| 8 | Separar grababilidad de elegibilidad en el served stream | [F-06] | Medición previa |
| 9 | Criterio de inferencia del gate de CLV | [F-16] | Paso 3 |
| 10 | Helper compartido `_model_map`; procedencia del precio | [F-10], [F-14] | — |
| 11 | Extraer el bucle de mercados | [F-12] | Pasos 0, 1 y 2 cerrados |
| 12 | Invariantes y fuzz sobre funciones puras | [F-22] | — |

---

## 11. Requisitos de pruebas de regresión

Cada corrección entra **solo** con su prueba. Las marcadas ⚠ deben escribirse
antes del arreglo y **verse fallar**.

| ID | Prueba requerida | Fija |
|---|---|---|
| [F-01] ⚠ | `EventOdds` con un precio `NaN`: el resto de mercados sigue produciendo candidatos, el descarte se registra y `books_count` solo cuenta líneas utilizables | Predicado + telemetría |
| [F-02] ⚠ | Segmento con una fila `inf` → `allowed == False`; y `n` cuenta solo filas finitas | Gate no aprobable por corrupción |
| [F-03] ⚠ | Matriz parametrizada: `line ∈ {NaN, inf, -inf}` × `{spreads, totals}` × ambos lados → `void` | Sin resultados fabricados |
| [F-04] | Con `shadow_mode: false` en el YAML, la suite **falla** salvo aprobación registrada | Control no evadible |
| [F-05] | Propiedad: `penalty == (1 − market_shrink) · uncertainty_penalty · |p_cal − fair|` | Acoplamiento visible |
| [F-08] ⚠ | `Path.stat` fallando siempre → `locked` retorna en ≤ `timeout_s`, con timeout de proceso | Sin cuelgue |
| [F-08b] | El estado degradado del lock queda en un artefacto durable, no solo en el log | Observabilidad |
| [F-10] | Ambos caminos producen claves idénticas para el mismo `EstimatedProbabilities` | Paridad backtest/producción |
| [F-11] | Backtest con `results` barajado → mismo ROI y n | Reproducibilidad |
| [F-15] | `clv_movement` y el consenso compartido descartan el mismo conjunto de líneas | Predicado único |
| [F-19] | `atomic_write_csv` con fallo a mitad de escritura; `locked` con `stat()` persistente | Rutas de fallo |
| [F-22] | Invariantes sin dependencia nueva: vig suma 1 y está en (0,1); Kelly nunca > `max_stake_pct·bankroll` ni negativo; `adjusted_edge` nunca aumenta el edge | Contratos de las funciones puras |

**Invariante global sugerida:** ninguna métrica publicada puede derivarse de una
fila con valor no finito. Es la formulación ejecutable de RC-1.

---

## 12. Plan a 30 / 60 / 90 días

Con una restricción declarada por delante: **nada de esto aumenta la
probabilidad de que el sistema gane dinero.** El objetivo no es rentabilidad, es
poder confiar en las cifras con las que algún día se decidirá si la hay.

### 30 días — que la evidencia sea confiable

- Pasos 0–4: tests en rojo, las seis victorias rápidas, predicado único de valor
  finito con telemetría, guard del gate de CLV, `clv_movement` unificado.
- Paso 5 si se obtiene autorización de datos: medir el alcance de [F-03],
  corregir, y **republicar con el delta explícito** si hubo filas afectadas.
- Paso 6: re-medir [F-13] y cerrar o reclasificar.
- **Criterio de salida:** `health_check.py` en OK y **ninguna métrica publicada
  depende de una fila con valor no finito**, demostrado por la invariante global.

### 60 días — que las decisiones sean inferencia, no umbral

- Pasos 7–9: concentración por evento medida y política decidida; served stream
  separado de la elegibilidad para stake; criterio de inferencia del gate de CLV
  alineado con KI-020 y **pre-registrado antes de mirar el resultado**.
- Resolver las verificaciones pendientes de §6, empezando por COR-06 y QNT-08.
- Cerrar [F-09] con 3.14 en la matriz de CI.
- **Criterio de salida:** el gate de CLV decide con un test estadístico explícito
  y su `n` cuenta solo filas informativas.

### 90 días — que la decisión de salir del shadow sea defendible

- Pasos 10–12: helper compartido, procedencia del precio de ejecución, extracción
  del bucle de mercados, invariantes sobre las funciones puras.
- Revisión de la deuda de mantenibilidad (ARCH-04, ARCH-05) si no ha surgido nada
  con más prioridad.
- **Criterio de salida:** el gate de CLV puede consultarse y su respuesta —sea
  cual sea— es defendible. **Si sigue vacío, esa también es una respuesta válida
  y probablemente la correcta.**

---

## 13. Definición de "terminado" del programa de remediación

El programa está completo cuando **todas** estas condiciones se cumplen
simultáneamente y son verificables por ejecución, no por documentación:

1. **Invariante de finitud vigente.** Existe un predicado único de valor
   utilizable, invocado desde consenso, conteo de casas, de-vig, liquidación,
   agregación de CLV y gate; y existe un test que falla si alguna métrica
   publicada deriva de una fila no finita. [F-01, F-02, F-03, F-15]
2. **Cero resultados fabricados.** `_grade` devuelve `void` ante cualquier línea
   no finita, con matriz de pruebas parametrizada; y el alcance en datos
   persistidos está **medido**, no supuesto. [F-03]
3. **El gate de CLV es defendible.** Métricas finitas, `n` contando solo filas
   informativas, y criterio de inferencia explícito pre-registrado. [F-02, F-16]
4. **La red de seguridad no es evadible.** Desactivar el shadow mode hace fallar
   la suite salvo aprobación registrada. [F-04]
5. **Concentración por evento acotada o explícitamente aceptada** por el
   operador, con la medición delante. [F-07]
6. **Paridad backtest–producción demostrada por test**, no por lectura: helper
   compartido y test de igualdad de claves. [F-10]
7. **Backtest reproducible** ante reordenación de la entrada. [F-11]
8. **El run diario no puede colgarse** en la adquisición del lock, y su
   degradación queda en un artefacto durable. [F-08]
9. **El intérprete de producción está en la matriz de CI**, o producción corre en
   una versión de la matriz. [F-09]
10. **La configuración no miente:** los comentarios de `configs/default.yaml`
    describen el efecto **compuesto** real de cada parámetro. [F-05]
11. **Cobertura medible en local** y línea base registrada. [F-20]
12. **Todas las verificaciones pendientes de §6 resueltas** a confirmado o
    rechazado, ninguna en "requiere verificación".

**Criterio explícitamente excluido:** la rentabilidad. Ninguna de las doce
condiciones la afirma ni la aproxima. El hecho dominante del proyecto —ausencia
de ventaja predictiva demostrada— sobrevive intacto a este programa, y la mejor
salida posible del gate de CLV sigue siendo, con la evidencia de hoy, seguir
vacío.
