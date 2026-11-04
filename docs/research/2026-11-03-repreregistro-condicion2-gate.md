# Re-pre-registro: la condición 2 del prediction gate pasa a ser el EV realizado de la cara que elige el modelo (AUD-001), con la muestra de medias liquidaciones (AUD-021) y el candado del techo como bloqueo (AUD-009)

**Fecha:** 2026-11-03.
**Estado:** **VIGENTE desde su commit.** Lo redactó el escalón Fable (pre-registros y parámetros de gate, `.claude/automation/MODEL_ROUTING.md`), bajo la autorización total y plenipotenciaria que el operador dio el 2026-11-03 para remediar la ronda `audit-2026-11-03` (§8).
**Enmienda:** cinco pasajes (la frase de la condición 2 aparece en tres documentos), nada más:

- la condición 2 de `docs/research/2026-08-16-preregistro-regla-de-salida.md`;
- la frase «la condición 2 (`EV > 0`)», que aparece en §3.3 del 2026-09-04, en §3.5 del 2026-11-02 y en §6 de `2026-11-03-enmienda-gate-k69-alfa-consumido.md`;
- el punto 4 de §4 de esa misma enmienda («las franjas siguen siendo solo log»).

Todo lo demás sigue vigente: K = 69, α_corte = 23/32760 = 0,000702, techo 84, cota mixta, `n ≥ 300`, test único de entrada, salida diaria, pestillo, ventana desde el 2026-08-16, `INVALID_BEFORE` y `drop_pre_fix_quarter_lines`.

---

## 1. Motivo

### 1.1 La condición 2 vigente no mide al modelo

La condición 2 del 2026-08-16 calcula `EV = p·(d − 1) − (1 − p)` **por fila** y lo promedia «sobre las mismas filas» que la condición 1. El stream servido registra **todas** las caras de cada mercado antes de aplicar ningún filtro (`src/sqp/pipeline/daily.py:995-1020`). Desde el 2026-09-06 la unidad es (evento, mercado), y `_independent_units` promedia `ev` dentro de ella. En una unidad de dos vías, con probabilidades complementarias (p, 1 − p) y cuotas d_A y d_B:

    EV_unidad = [p·d_A + (1 − p)·d_B − 2] / 2

- **Cuotas simétricas** (d_A = d_B = d): EV_unidad = (d − 2)/2, **sea cual sea p**. Con un margen v, d = 2/(1 + v) y EV_unidad = −v/(1 + v); a 1,909 da −0,0455. Ningún modelo puede pasar.
- **En general:** EV_unidad sube con p solo si d_A > d_B. Es decir, sube cuando el modelo se inclina hacia el **underdog**, tanto si acierta como si no.

Lo publicado lo confirma. Los cortes agotados de spreads y totals tienen un ev_flat entre −0,0485 y −0,0505, que es el vig. `ncaaf|h2h` tiene un ev_flat de **+0,4321** con 133 victorias pareadas de 490 (p = 1,0000): el peor modelo en el test de signo es el «mejor» en EV.

La reproducción del auditor (CLAUDE-001) usa 400 eventos, ambas caras a 1,909, mercado a 0,5 y modelo a 0,9 en el ganador. Resultado: n = 400, 400 victorias, p = 3,87·10⁻¹²¹, `ev_flat = −0,0455` y `ev_no_positivo`. El EV de la cara que el modelo prefiere es +0,909.

**Consecuencia.**

- En spreads y totals la condición es inalcanzable por construcción.
- En h2h premia el sesgo al underdog.
- No pone dinero en riesgo, pero puede **gastar el test único** de un corte que sí bate al mercado. Ese corte quedaría en `agotado_test_unico` hasta una liberación humana. `nhl|spreads` y `nhl|totals` van por n = 224 de 300.

### 1.2 Lo que se sabía al diseñar (declarado para que no se re-litigue)

- **Conocido:** el registro del 2026-11-03T23:52Z, con 74 cortes (68 en `muestra_insuficiente` y 6 agotados) y el n, las victorias, el p y el ev_flat de cada uno. Los más avanzados son `nhl|spreads` (123/224, p = 0,0802, ev_flat −0,0632) y `nhl|totals` (108/224, p = 0,7261, ev_flat −0,0469).
- **No conocido:** la métrica nueva de §2.1 **no se ha calculado nunca sobre datos reales**, ni en la auditoría (CLAUDE-001, «Limitaciones») ni en este diseño. **Queda prohibido** calcularla sobre el stream real antes del commit de este documento y de su código. La regla se eligió solo con argumentos estructurales y sintéticos (§3).

---

## 2. Criterio

### 2.1 Condición 2: EV realizado, a stake plano, de la cara que elige el modelo

Se aplica sobre las filas que filtra la condición 1 (ventana posterior al 2026-08-16, `INVALID_BEFORE`, `drop_pre_fix_quarter_lines` y columnas numéricas presentes), **más las filas `push`** (paso 5).

1. **Precio de la condición** por fila: `precio_c2 = min(price_decimal, execution_price)` si `execution_price` es finito y > 1; si no, `price_decimal`. Es el precio cobrable en la casa de ejecución, que nunca supera la mediana del consenso. Es la dirección conservadora y coincide con la regla de ejecución de AUD-005.
2. **Edge del modelo puro** por fila: `e_m = model_probability × precio_c2 − 1`. Se usa la probabilidad **pura** por el mismo motivo que en la condición 1: la mezcla y la calibrada ya llevan el precio dentro.
3. **Elección por run.** El run es el `generated_at` de la fila. Dentro de cada (evento, mercado, run), el modelo «apuesta» una sola fila: la de mayor `e_m`, **siempre que `e_m > 0`**.
   - Si hay empate, se desempata de forma determinista por `selection` y luego por `line`, ambos ascendentes.
   - Si ninguna fila del run tiene `e_m > 0`, el modelo **se abstiene** en ese run.
   - Cada run elige solo con la información de su instante. No se toman máximos entre snapshots, que mirarían hacia delante.
4. **Retorno realizado por unidad apostada** de la fila elegida, con `d = precio_c2`:
   - `win`: d − 1
   - `loss`: −1
   - `half_win`: (d − 1)/2
   - `half_loss`: −0,5
   - `push`: 0

   Son los mismos pagos que `settle.settle_candidates`.
5. **Los `push` cuentan en la condición 2.** Si se quitaran, la elección del paso 3 dependería del resultado: un run cuya mejor línea empató acabaría eligiendo otra. El retorno de un push es 0 y entra como tal. Las filas `void` o sin resultado no entran.
6. **Unidad (evento, mercado):** la misma de §3 del 2026-09-04 y de la condición 1.
   - El retorno de la unidad es la **media de los runs en que apostó**: stake total 1 por partido, repartido entre los runs, igual que la condición 1 promedia sus repeticiones.
   - Las unidades en que el modelo se abstuvo en todos los runs no entran en la condición 2, pero sí siguen en la condición 1.
7. **Estadístico:** `ev_lado_modelo`, la media sobre las `n_ev` unidades con apuesta.
   - **La condición se cumple si `n_ev > 0` y `ev_lado_modelo > 0`.**
   - Si `n_ev = 0`, `ev_lado_modelo` vale NaN y la condición no se cumple (default-deny).

No se añade un umbral de `n_ev` ni un test de significación: el proyecto no define ninguno para esta condición y no se inventa. El control del error de tipo I recae **entero** en la condición 1 (§2.4). `n_ev` se publica en el registro para que se pueda leer.

El orden de las razones no cambia: primero muestra, luego signo, luego EV (`muestra_insuficiente`, `no_bate_al_mercado`, `ev_no_positivo`).

### 2.2 Medias liquidaciones en la condición 1 (AUD-021)

Hasta hoy `_usable` solo admitía `win`/`loss`. En una línea de cuarto descartaba las filas `half_*` y conservaba las de esa misma línea liquidadas enteras. El resultado era **una muestra condicionada al resultado** (268 de 68.866 filas, CLAUDE-021).

**Decisión: cada fila pesa la fracción de stake que se resolvió.** No se usa y = 0,5 ni se excluye la línea de cuarto.

| resultado | y | peso w |
|---|---:|---:|
| `win` | 1 | 1 |
| `loss` | 0 | 1 |
| `half_win` | 1 | 0,5 |
| `half_loss` | 0 | 0,5 |
| `push` | — | 0 (fuera de la condición 1) |

La `d` de la unidad es Σ w·d / Σ w.

**Por qué.** Por definición del código, `model_probability` es `SettlementProbabilities.decision_probability = W/(W + L)`, con W = full_win + ½·half_win y L = full_loss + ½·half_loss (`src/sqp/markets/settlement_math.py`; `src/sqp/models/distributions.py::_decision_probability`). La probabilidad implícita 1/d está en la misma escala: el punto de equilibrio de W·(d − 1) − L = 0 es W/(W + L) = 1/d.

- En un `half_win` se devuelve la mitad del stake y la mitad resuelta **gana entera**: y = 1 con peso ½. En un `half_loss`, y = 0 con peso ½.
- El Brier ponderado Σ w·(q − y)², con w = W + L e y = W/(W + L), se minimiza en esperanza en q = E[W]/E[W + L]. Es **propio** exactamente para la probabilidad que publica el modelo.
- Usar y = 0,5 trataría la mitad resuelta como medio acierto y medio fallo, un contrato que no existe.
- Excluir toda línea de cuarto sería válido, pero tiraría información sin motivo.
- El `push` con peso 0 aplica el mismo principio, que ya estaba vigente: la probabilidad se condiciona a que la apuesta se resuelva.

### 2.3 Fuera del universo pre-registrado no se consume ningún test (AUD-009)

§3.4 del 2026-11-02 y §4.4 de la enmienda del 2026-11-03 ordenan re-pre-registrar «antes de que ningún corte nuevo sea elegible», pero el código solo lo anotaba en el log. Desde hoy se aplica esta regla.

Sea `n_cortes` el número de entradas del registro que se va a escribir, y sea `cota = max(fwer_bound_registro(markets), fwer_bound(n_cortes))`. Si

    n_cortes > 84  o  cota > 5/82 + 1e-12

entonces, en esa evaluación, todo corte cuyo test de entrada **se consumiría** (n ≥ 300 y sin `entry_test_at`) queda así:

- `allowed: false` y `reason: "fuera_de_preregistro"`;
- `entry_test_at` y `entry_test_alpha` siguen en `null`: el test **no se gasta** y no se cobra α;
- no se arma el pestillo.

El resto sigue igual:

- los cortes ya dentro siguen bajo vigilancia diaria de salida, porque salir es la dirección segura;
- los agotados siguen agotados;
- los cortes con n < 300 siguen en `muestra_insuficiente`.

El registro publica `entradas_bloqueadas: true` y el log mantiene el ERROR de re-pre-registro.

La cota no depende de si el test se consume: `fwer_bound_registro` ya cobra un test pendiente a α_corte, igual que uno consumido hoy. Por eso la condición se evalúa una sola vez y es estable al aplicar el bloqueo. La segunda condición cubre las liberaciones (enmienda del 2026-11-03, §4.4): con 84 cortes, una sola liberación con su nuevo test da 0,061233 > 0,060976.

La regla es estrictamente conservadora: solo puede impedir entradas.

### 2.4 Por qué nada de esto toca el control del error de familia

La autorización exige **las dos** condiciones a la vez. Para un corte nulo, P(condición 1 y condición 2) ≤ P(condición 1) ≤ α_corte.

- La cota de Bonferroni depende solo de la condición 1, que **no cambia**: misma `d`, mismo `model_probability`, empates excluidos, test unilateral, `n ≥ 300` y p < 0,000702.
- Lo de §2.2 solo afecta al peso de las filas dentro de su unidad.

K, α_corte, techo y cota mixta siguen exactamente igual. Ya no se apela a la «independencia» de la condición 2, que §1.4 del 2026-09-04 refutó.

---

## 3. Cálculo

Ejemplos sintéticos, que serán los tests discriminantes. Cada evento tiene sus dos caras, con mercado sin vig a 0,5. α = 23/32760.

| caso | datos | condición 1 | `ev_lado_modelo` (`n_ev`) | ev_flat (retirado) | decisión |
|---|---|---|---|---|---|
| T1 modelo bueno (repro auditoría) | 400 eventos a 1,909; modelo 0,9 al ganador | 400/400, p = 3,87·10⁻¹²¹ | en el ganador 0,9 × 1,909 − 1 = 0,7181 > 0 y se apuesta: **+0,909** (400) | −0,0455 | **pasa** |
| T2 modelo = mercado | 400 eventos a 1,909; modelo 0,5 | d = 0 en todos, n = 0 | e_m = −0,0455 en las dos caras, abstención: **NaN** (0) | −0,0455 | `muestra_insuficiente`; la condición 2 tampoco pasa por sí sola |
| T3 modelo = mercado + ruido | 400 eventos a 1,909; modelo 0,6 a A, A gana 200 | 200/400, p ≈ 0,52 | siempre apuesta A: (200 × 0,909 − 200)/400 = **−0,0455** (400) | −0,0455 | `no_bate_al_mercado`; la condición 2 tampoco pasaría |
| T4 bate en signo, el vig se come el margen | 2000 eventos a 1,80; modelo 0,6 a A, A gana 1100 | 1100/2000, p = 4,23·10⁻⁶ < α | e_m(A) = 0,08 > 0: (1100 × 0,8 − 900)/2000 = **−0,0100** (2000) | −0,10 | `ev_no_positivo` |
| T5 modelo bueno realista | 400 eventos a 1,909; modelo 0,6 a A, A gana 240 | 240/400, p = 3,71·10⁻⁵ < α | 0,6 × 0,909 − 0,4 = **+0,1454** (400) | −0,0455 | **pasa** (con la regla vieja, `ev_no_positivo`) |

T3 es el caso que descarta usar un «EV estimado con la p_modelo de la cara elegida»: con esa regla, T3 daría +0,1454 fueran cuales fueran los resultados.

**Precio de ejecución.**

- T1 con `execution_price` 1,85 en todas las filas: e_m = 0,665 y retorno **+0,85**.
- Con `execution_price` 2,50, por encima de la mediana: se usa 1,909 y el retorno es +0,909.

**Varios runs.** En un mismo evento que gana A:

- run 1: A a 2,0 con modelo 0,6 (e_m 0,2) y B con 0,4 (−0,2);
- run 2: A con 0,45 (−0,1) y B con 0,55 (+0,1).

El run 1 apuesta A (+1) y el run 2 apuesta B (−1): la unidad da **0,0**, con n_ev = 1.

**Push.** En un mismo run de totals hay un Over 3,0 (modelo 0,7, precio 2,0, e_m 0,4, resultado push) y un Over 2,5 (modelo 0,6, e_m 0,2, resultado win). Se elige el 3,0 y el retorno es **0,0**. Si se quitaran los push, saldría +1,0.

**Medias liquidaciones (§2.2).** Modelo 0,6, mercado 0,5, totals.

- Una unidad con un `win` en 2,5 (w = 1, d = 0,25 − 0,16 = +0,09) y un `half_loss` en 2,75 (w = 0,5, d = 0,25 − 0,36 = −0,11): d de la unidad = (0,09 − 0,055)/1,5 = **+0,023333**, victoria. La media sin pesos daría −0,01, derrota.
- Tres eventos a 2,0: uno `half_win` en 2,25, uno `half_loss` en 2,25 y uno `push` en 3,0.
  - Condición 1: **n = 2, 1 victoria**.
  - Condición 2: retornos +0,5, −0,5 y 0, así que **ev_lado_modelo = 0,0** con n_ev = 3.

**Techo (§2.3).**

- Con 85 cortes sin tests: fwer_bound_registro = 85 × 23/32760 = 0,059676 y fwer_bound(85) = 3/520 + 79 × 23/32760 = 0,061233 > 0,060976, así que hay bloqueo.
- Con 84: 0,060531, sin bloqueo.

---

## 4. Los cortes agotados y la NHL

- **Los seis agotados no se reabren ni se recalculan.** Ninguno cayó por la condición 2: todos fallaron el test de signo.

  | corte | p |
  |---|---:|
  | `mlb\|h2h` | 0,9995 |
  | `mlb\|spreads` | 0,3347 |
  | `mlb\|totals` | 0,3730 |
  | `ncaaf\|h2h` | 1,0000 |
  | `ncaaf\|spreads` | 0,3931 |
  | `ncaaf\|totals` | 0,6904 |

  - Con cualquier condición 2 habrían quedado igual.
  - Su `ev_lado_modelo` se publicará a diario solo como observación.
  - Este cambio **no es motivo** de liberación. Liberar sigue siendo un acto humano con rastro: el corte se re-evalúa con el criterio vigente y su α se cobra según la enmienda del 2026-11-03.
- **AUD-021 no les afecta:** MLB y NCAAF no cotizan líneas de cuarto en el consenso. La implementación lo verifica contando filas por línea, no por resultado (§6).
- **`nhl|spreads` y `nhl|totals` no han gastado su test.** Su test de entrada se decidirá con este criterio si este commit llega antes de su primer run con n ≥ 300, que es el plazo. A n = 300 el listón sigue en 179 victorias:
  - `nhl|spreads` necesita 179 − 123 = 56 victorias en las 76 unidades siguientes (73,7 %);
  - `nhl|totals` necesita 71 de 76 (93,4 %).

  Las cifras cambian si el run cae en otro n. NHL publica puckline ±1,5 y totales x,0/x,5; §6 verifica cuántas filas de cuarto tiene.
- **Si se ejecutara un test de entrada antes del commit** con la condición 2 vieja, la decisión queda como está y se registra como incidente. El operador puede liberarlo; la liberación cobra su α y re-evalúa con este criterio.

---

## 5. Qué no cambia

- K = 69, α_corte = 23/32760 = 0,000702, α de familia 0,05, techo 84, cota mixta y franjas INFO/ERROR del log.
- La condición 1 completa: `d`, `model_probability`, empates excluidos, test unilateral, `n ≥ 300` y unidad (evento, mercado). Solo cambia el peso de las medias liquidaciones dentro de la unidad (§2.2).
- Un solo test de entrada por corte, la salida diaria, el pestillo y la liberación humana con el α conservado.
- La ventana desde el 2026-08-16, `INVALID_BEFORE` (`nhl|h2h`) y `drop_pre_fix_quarter_lines`. Siguen vigentes los addenda citados en §3.5 del 2026-11-02, con su prohibición de recortar o re-segmentar la ventana.
- Las seis decisiones ya tomadas.
- `ev_flat` se sigue publicando en el registro como **métrica retirada**, sin efecto en la decisión, para mantener la continuidad del rastro.
- Lo que la regla no promete: pasar el gate no garantiza rentabilidad. `ev_lado_modelo` es un **retorno realizado** en la ventana, no un ROI esperado ni una promesa.

## 6. Implementación

En `src/sqp/risk/prediction_gate.py` y sus tests, según la especificación de la remediación audit-2026-11-03:

- `_graded_rows`: filtro común con `win/loss/half_win/half_loss/push`, más las columnas `y` y `w`.
- `_independent_units`, ponderado por `w`.
- `_ev_lado_del_modelo`, según §2.1.
- `_decide`, con la condición 2 nueva.
- Campos nuevos por entrada: `ev_lado_modelo` y `n_ev`.
- Campos nuevos en el payload: `criterio_condicion2 = "ev_realizado_lado_modelo_2026-11-03"` y `entradas_bloqueadas`.
- `_apply_latch(..., bloquear_entradas)`, con la razón `fuera_de_preregistro`.

Antes del commit se cuentan, con un script que solo devuelva recuentos (sin resultados ni métricas nuevas), las filas de **línea de cuarto** en los seis cortes agotados y en `nhl|*`. Se cuentan por valor de línea, no por resultado. Lo esperado es 0 en los agotados; si no lo fuera, se anota aquí sin cambiar ninguna decisión ya tomada.

Las referencias operativas que describen la condición 2 («EV a stake plano», `ev_flat`) pasan a citar `ev_lado_modelo` y este documento: `configs/default.yaml`, `scripts/update_prediction_gate.py`, `scripts/gate_status.py` y `.claude/skills/clv-shadow-exit/SKILL.md`.

**Plazo:** en `main` antes del primer run en que un corte llegue a n ≥ 300.

## 7. Predicción registrada

- **Condición 1:** se mantienen las predicciones de §5 del 2026-11-02. Los dos cortes NHL serán rechazados por el test de signo.
- **Condición 2:** la predicción del 2026-11-02 de que `nhl|spreads` «fallará la condición 2 (ev_flat ≤ 0)» **queda sin objeto**. Era cierta por construcción (−vig) y no decía nada del modelo.
- **Sin predicción nueva sobre `ev_lado_modelo`:** no se ha medido (§1.2). Si un corte pasara el test de signo, la condición 2 se leerá en el `ev_lado_modelo` y el `n_ev` de su entrada.
- **Esperado por la estructura:** en un corte sin información propia, `ev_lado_modelo` estará cerca de −v/(1 + v), como en T3, y será ≤ 0 en esperanza.

## 8. Decisión del operador

- **Base de la orden.** El 2026-11-03 el operador (Carlos) autorizó la remediación total de la ronda `audit-2026-11-03` con «autorización total y plenipotenciaria», y delegó el criterio. Este documento es una decisión de diseño del escalón Fable tomada bajo esa orden, sin menú de opciones.
- [x] AUD-001: la condición 2 es el EV realizado a stake plano de la cara de mayor edge positivo del modelo puro. Se calcula por run, en la unidad (evento, mercado), al precio `min(mediana, ejecución)` y con los push dentro.
- [x] AUD-021: las medias liquidaciones entran con la y del lado resuelto y peso ½.
- [x] AUD-009: por encima del techo o de la cota máxima tolerada no se consume ningún test de entrada (`fuera_de_preregistro`).
- [ ] Confirmación expresa del operador. No bloquea, igual que en el caso del techo de 84.
