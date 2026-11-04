# Re-pre-registro: el prediction gate pasa a K = 69 (68 cortes evaluados + `mlb|team_totals`)

**Fecha:** 2026-11-02.
**Estado:** **VIGENTE desde su commit.** Redactado por el escalón Fable (rol de pre-registro de `.claude/automation/MODEL_ROUTING.md`) bajo la autorización plena del operador del 2026-11-02 (§7). Implementado el mismo día (constantes y referencias de §7).
**Enmendado el 2026-11-03** por `docs/research/2026-11-03-enmienda-gate-k69-alfa-consumido.md` (KI-078): los seis tests gastados a 0,05/52 se cuentan a su α real; α_corte pasa de 0,05/69 = 0,000725 a (0,05 − 6 × 0,05/52)/63 = 0,000702, y la cota de §3.4 se calcula con el α consumido. K = 69 y el techo de 84 no cambian. Las cifras de §3.1, §3.3.2 (punto 2), §3.4 y §4 se conservan como se escribieron y quedan superadas por la enmienda.
**Modifica:** `docs/research/2026-09-25-repreregistro-gate-k52.md`, §3: el valor de K y el techo de re-pre-registro. A través de él modifica también `docs/research/2026-09-04-preregistro-multiplicidad-del-gate.md` §3.1, solo en esos dos números. Todo lo demás de ambos documentos sigue vigente sin cambios, incluidos sus addenda, en particular §3.2 del 2026-09-04: **un solo test de entrada por corte**.

**Nota sobre el nombre del fichero.** El encargo se abrió como «K = 68», que es el número de cortes que evalúa hoy el registro. La decisión de §3.3 añade a K el corte derivado `mlb|team_totals`, cuya entrada en el gate ya estaba pre-registrada. El valor fijado aquí es **K = 69**. El fichero se renombró a `…-k69.md` antes de su commit para que el nombre coincida con el valor fijado.

---

## 1. Por qué

El re-pre-registro del 2026-09-25 fijó K = 52 y aplicó la regla de §3.1 del 2026-09-04 con sus nuevos números (§3.2 de aquel documento):

> «Por encima de 63, ERROR y re-pre-registro antes de que ningún corte nuevo sea elegible. Es la misma regla, con los números nuevos.»

El registro de producción evalúa ahora **68 cortes**. Desde el run del 2026-10-22 (64 cortes) el run diario emite el ERROR «RE-PRE-REGISTRAR el criterio antes de que un corte nuevo alcance n>=300». Con K = 52 y 68 cortes, la cota real del error de familia es 68 × 0,05/52 = **0,0654**, un 31 % por encima del 0,05 declarado y por encima de la cota máxima tolerada (0,0606).

## 2. Estado medido antes de fijar nada

Fuente: `data/bets/prediction_gate.json`, generado el 2026-11-01T15:15Z. Se ha leído sin escribir nada.

```
n_cortes_evaluados = 68 · k_bonferroni = 52 · alpha = 0,000962 · fwer_bound = 0,065385
min_n = 300 · validation_start = 2026-08-16 · 0 permitidos
6 cortes con su test de entrada gastado (agotado_test_unico) · 62 en muestra_insuficiente
```

**Los seis tests ya gastados** (todos rechazados, ninguno con pestillo de aprobación):

| corte | n | victorias | p (test de signo) | ev_flat | `entry_test_at` (UTC) | cortes evaluados ese día |
|---|---:|---:|---:|---:|---|---:|
| `mlb\|h2h` | 350 | 145 | 0,9995 | −0,0310 | 2026-09-25T15:04Z | 52 |
| `mlb\|spreads` | 351 | 180 | 0,3347 | −0,0493 | 2026-09-25T15:04Z | 52 |
| `mlb\|totals` | 343 | 175 | 0,3730 | −0,0505 | 2026-09-26T15:04Z | 52 |
| `ncaaf\|h2h` | 490 | 133 | 1,0000 | +0,4321 | 2026-10-11T15:04Z | 59 |
| `ncaaf\|spreads` | 489 | 248 | 0,3931 | −0,0489 | 2026-10-11T15:04Z | 59 |
| `ncaaf\|totals` | 490 | 240 | 0,6904 | −0,0485 | 2026-10-11T15:04Z | 59 |

La última columna sale de `logs/run_diario.log`. El run de producción calla cuando n ≤ K, informa (INFO) cuando K < n ≤ techo y emite un ERROR por encima del techo. El recuento de producción fue 52 hasta el 2026-09-24, 58–60 entre el 2026-09-30 y el 2026-10-18, 61 el 2026-10-19 y 2026-10-20, 64 desde el 2026-10-22, 67 desde el 2026-10-27 y 68 el 2026-11-01. **Los seis tests se hicieron con el número de cortes dentro de lo pre-registrado** (52 y 59, ambos ≤ 63), así que fueron válidos bajo K = 52. Ninguno se ejecutó en la franja de ERROR.

> `logs/sqp.log*` también contiene evaluaciones con 64 cortes desde el 2026-09-29, en secuencias 63/60/64 separadas por segundos. No proceden del run diario: sus marcas de tiempo no coinciden con las de `entry_test_at` y no se ha identificado su origen. No alteran lo anterior, porque los seis `entry_test_at` corresponden a runs de las 12:04 hora local cuyo recuento está en `run_diario.log`.

**Los más cercanos a n = 300** entre los 62 restantes:

| corte | n | victorias | p | ev_flat |
|---|---:|---:|---:|---:|
| `nhl\|spreads` | 219 | 121 | 0,0685 | −0,0629 |
| `nhl\|totals` | 219 | 106 | 0,7056 | −0,0469 |
| ningún otro | < 200 | — | — | — |

La NHL está en temporada, así que esos dos cortes pueden llegar a n = 300 en semanas. Es el plazo de este documento: debe estar implementado antes de que cualquiera de los dos llegue a n = 300.

**Fuera del registro:** `mlb|team_totals`, el derivado de la Fase 1 de `docs/research/2026-08-24-preregistro-mercados-derivados.md`, se evaluó hoy con la regla canónica (`_decide`, unidad = evento, desde 2026-08-25). Resultado: n = 110 eventos no empatados, 54 victorias, p = 0,612, ev_flat = −0,0543, es decir, `muestra_insuficiente`. La temporada MLB ha terminado. Hay 40 eventos de postemporada capturados que no se gradúan por KI-072 (`results_mlb.csv` solo contiene `gameType` R). Este corte **no** está entre los 68.

## 3. Criterio re-pre-registrado

### 3.1 Bonferroni sobre K = 69

```
α_corte = 0,05 / K        con K = 69 fijado hoy
α_corte = 0,000725        (0,05/69 = 0,00072464)
```

K = 69 se compone de los 68 cortes del registro (seis agotados y 62 en `muestra_insuficiente`) más `mlb|team_totals` (§3.3).

### 3.2 Las cuestiones que había que resolver antes de fijar K

**(a) ¿Se cumple «antes de que ningún corte nuevo sea elegible», aunque seis cortes ya hayan gastado su test?** Sí. La condición protege una propiedad: que el criterio que decide la entrada de un corte esté fijado antes de su único test. Los seis cortes agotados no son nuevos. Se decidieron entre el 2026-09-25 y el 2026-10-11 bajo un criterio vigente y dentro de la tolerancia (§2), y por §3.2 del 2026-09-04 no se vuelven a evaluar sin liberación humana explícita. Este documento no los reabre ni los toca. Ningún corte ha alcanzado n ≥ 300 desde el 2026-10-11, y en particular ninguno lo ha hecho desde el 2026-10-22, cuando el recuento superó el techo. El máximo actual es n = 219. **Ningún corte nuevo es elegible.** La condición se cumple, aunque con un margen de semanas, no de meses.

**(b) ¿Cuentan en K los seis agotados?** Sí, y deben contar. Bonferroni acota la probabilidad de **al menos un** falso positivo en la familia de tests que se realizan bajo el criterio. Esos seis tests se realizaron: cada uno era una oportunidad de falso positivo, que no se materializó. Si se sacaran de K y α se repartiera solo entre los que quedan, el umbral se relajaría (0,05/63 en vez de 0,05/69) **porque** esos seis salieron rechazados. Eso es exactamente re-dividir α según los resultados, lo que prohíbe §3.1 del 2026-09-04. Además pueden volver a la familia: un corte agotado es reentrable tras liberación humana (`release_prediction_gate_latch`), y si eso ocurre su nuevo test debe estar cubierto por el mismo reparto. Por último, el propio código ya los cuenta: `n_cortes_evaluados = len(markets)` incluye los agotados, y K se compara con ese recuento.

**(c) ¿Conocer los p intermedios de cortes no elegibles da ventaja?** No, por dos razones independientes:

1. **El cambio solo endurece.** α baja de 0,000962 a 0,000725. Todo corte que el criterio anterior rechazaba lo rechaza también el nuevo. Endurecer no puede abrir ninguna puerta, así que saber que `nhl|spreads` va con p = 0,0685 a n = 219 no permite elegir un K que lo favorezca: cualquier K ≥ 52 lo perjudica o lo deja igual.
2. **K no se elige mirando p.** Es el recuento de cortes del pipeline más un corte cuya entrada estaba escrita desde el 2026-08-24. Es un hecho de diseño, como lo eran K = 41 y K = 52.

### 3.3 `mlb|team_totals` cuenta ya: K = 69, no 68

Había dos opciones: contarlo ya (K = 69) o dejar que su entrada se absorbiera en la tolerancia hasta el techo. **Se cuenta ya.** Motivos:

1. **Su entrada ya está pre-registrada.** `2026-08-24-preregistro-mercados-derivados.md` dice que «el derivado entra al gate de predicción como un (liga, mercado) más» (l. 94) y que la «Fase 1 hereda la postura Bonferroni del gate de predicción vigente» (l. 128–129). Es un miembro **conocido** de la familia, no un crecimiento imprevisto. La tolerancia hasta el techo existe para lo imprevisto, es decir, las ligas que entran por calendario. Usarla para absorber algo que ya se sabe que entrará es gastar el margen antes de necesitarlo.
2. **Es lo más conservador.** Con K = 68, en cuanto `team_totals` entrara habría 69 cortes y la cota real sería 69 × 0,05/68 = 0,0507, ya por encima del 0,05 declarado desde el primer día. Con K = 69 la cota es exactamente 0,05 cuando entra.
3. **Endurece y no favorece a nadie.** α pasa de 0,000735 (K = 68) a 0,000725. Cuesta una victoria a n = 300 (§4), y lo paga cualquier corte, incluidos los dos de la NHL. Contar `team_totals` no depende de su resultado: va con p = 0,612 y n = 110, lejos de 300. Se contaría igual si fuera ganando.
4. **El criterio para contar es cerrado y no se puede estirar.** K cuenta (i) los cortes del registro de producción y (ii) los cortes cuya entrada al gate está **escrita en un pre-registro vigente** en la fecha de este documento. Hoy solo `mlb|team_totals` cumple (ii). Un corte que aparezca por calendario de temporada no se cuenta por adelantado: entra en la tolerancia, que es su función.

Consecuencia operativa: hasta que `team_totals` entre en el registro, `n_cortes_evaluados = 68 < K = 69`. La franja n ≤ K del candado es silenciosa, así que no hay aviso, y eso es correcto: el reparto cubre de sobra lo evaluado. Cuando entre, n = 69 = K, también sin aviso.

**La medición de `team_totals` no se mueve de su sitio por esto.** Sigue su propio calendario, a n ≥ 300 eventos no empatados con un solo test de entrada (§3.2 del 2026-09-04). Ese test se hará con el α vigente en el momento en que llegue a n = 300, que hoy es 0,05/69. Este documento no cambia la unidad (evento), la ventana ni la exclusión de la postemporada no graduada (KI-072).

### 3.4 Techo para el próximo re-pre-registro: 84 cortes

Se mantienen los dos invariantes con los que el operador confirmó el techo de 63 el 2026-09-25:

- **Misma tolerancia relativa**, 50/41 (+22 % sobre K): ⌊69 × 50/41⌋ = ⌊84,15⌋ = **84**.
- **Cota máxima tolerada que no empeora** respecto de 50 × 0,05/41 = 0,060976:
  - 84 × 0,05/69 = 0,060870 ≤ 0,060976. **Cumple.**
  - 85 × 0,05/69 = 0,061594. No cumple.

**Techo = 84.** Es el máximo que no relaja lo aprobado. A título de comprobación, con K = 68 el techo habría sido 82 (82 × 0,05/68 = 0,060294; 83 daría 0,061029). Se descarta junto con K = 68 (§3.3).

- Hasta 69 cortes: el reparto cuadra y no se emite nada.
- Entre 70 y 84 cortes: se informa la cota real (INFO) y el criterio se aplica tal cual.
- Por encima de 84: ERROR y re-pre-registro antes de que ningún corte nuevo sea elegible. Es la misma regla, con los números nuevos.

### 3.5 Lo que NO cambia

- α de familia 0,05.
- `n ≥ 300` no empatadas.
- La definición de `d`, el modelo puro (`model_probability`) y la exclusión de empates.
- La condición 2 (`EV > 0`).
- La ventana fuera de muestra desde el 2026-08-16.
- **Un solo test de entrada por corte** (§3.2 del pre-registro del 2026-09-04).
- La salida diaria y el pestillo.
- Añadidos hoy:
  - **Los seis tests ya gastados quedan como están.** Su decisión (`agotado_test_unico`, rechazados) se tomó bajo K = 52 y no se recalcula, ni para endurecerla ni para relajarla. Solo vuelven a evaluarse tras liberación humana explícita, y si eso ocurre, con el α vigente en ese momento.
  - **Las reglas de tolerancia y de techo**: la fórmula ⌊K × 50/41⌋ con la comprobación de que la cota no empeora, y la regla de las tres franjas del candado.
  - **Los addenda del 2026-09-26, 2026-09-30 y 2026-10-18** del documento del 2026-09-25 siguen vigentes, con su prohibición de usarlos para recortar o re-segmentar la ventana.
  - **El pre-registro de derivados**: su unidad, su ventana, sus guardarraíles y sus hipótesis H1–H3. Lo único que se fija aquí es que `team_totals` cuenta en K.

## 4. El precio

Victorias pareadas necesarias con el test de signo unilateral (binomial, p = 0,5), recalculadas hoy:

| n | α = 0,000962 (K = 52) | α = 0,000735 (K = 68, descartado) | α = 0,000725 (K = 69) |
|---:|---:|---:|---:|
| 300 | 178 (59,3 %) | 178 (59,3 %) | 179 (**59,7 %**) |
| 500 | 286 (57,2 %) | 287 (57,4 %) | 287 (57,4 %) |
| 1000 | 550 (55,0 %) | 551 (55,1 %) | 551 (55,1 %) |

A n = 300, contar `team_totals` cuesta una victoria (178 → 179). A n = 500 y n = 1000 el precio es el mismo que con K = 68: una victoria más que con K = 52. Se acepta: es el precio de que la cota de familia sea exactamente 0,05 cuando entre un corte que ya sabemos que entrará.

## 5. Predicción registrada

No cambia la predicción del pre-registro del 2026-09-04 (§6 y §9) ni la del 2026-09-25 (§5). Esta última ya se resolvió para MLB: los tres cortes fallaron, con `ev_flat` < 0 y `reason` acabado en `agotado_test_unico`, como se predijo.

Para los dos cortes que llegarán antes a n = 300, se registra hoy, antes de que lleguen:

- **`nhl|totals`** (106/219, p = 0,706, ev_flat = −0,047): **será rechazado por el test de signo**, con `no_bate_al_mercado` en el día del test y `agotado_test_unico` después. Va por debajo del 50 % de victorias. Para pasar a n = 300 necesitaría 73 victorias en las 81 siguientes (90 %).
- **`nhl|spreads`** (121/219, p = 0,0685, ev_flat = −0,063): **será rechazado.** Para pasar a n = 300 necesitaría 179 − 121 = 58 victorias en las 81 siguientes (71,6 %), muy por encima de su ritmo actual (55,3 %). Si aun así pasara el test de signo, se predice que **fallará la condición 2** (`ev_flat` ≤ 0): hoy su EV a stake plano es el más negativo de los dos. Recordatorio de §5 del 2026-09-25: `_decide` evalúa el signo antes que el EV, así que el fallo de la condición 2 se lee en `ev_flat` de la entrada del registro, no en `reason`.
- **`mlb|team_totals`**: se mantiene la H3 de su pre-registro (nula, la más probable). Sin predicción nueva. Su test no llegará antes de la temporada MLB 2027.

Las cifras de 73/81 y 58/81 suponen que el test se ejecuta exactamente a n = 300. Si el primer run con n ≥ 300 cae en un n mayor, el umbral se recalcula con ese n, sin cambiar α.

Si alguno pasara, habrá superado un listón del 59,7 % a n = 300 **y** tendrá EV positivo, y la predicción quedará refutada por escrito.

## 6. Objeciones consideradas

- **«El techo se superó el 2026-10-22 y no se re-pre-registró hasta hoy.»** Es cierto, y es una demora de 11 días. Pero no invalida nada: en ese intervalo ningún corte alcanzó n ≥ 300, así que el criterio fuera de tolerancia nunca decidió un test. La regla dice «antes de que ningún corte nuevo sea elegible», no «el mismo día», y se cumple.
- **«Contar `team_totals` es contar un corte que no existe en el registro.»** Existe en un pre-registro vigente que obliga a que entre (§3.3). La regla de recuento es cerrada: registro + pre-registros vigentes. No admite «cortes que podrían existir».
- **«Seis cortes ya gastados hacen la familia más pequeña de facto.»** Re-dividir α entre los supervivientes es relajar en función de los resultados, y está prohibido (§3.2 b).

## 7. Decisión del operador

- **Base de la orden.** El 2026-11-02 el operador (Carlos) preguntó «¿Cuál es el objetivo del proyecto y qué falta para alcanzarlo?». A la respuesta contestó con la orden textual: **«Haz todo lo necesario para lograrlo. Te otorgo plena autorización para ello.»** Este re-pre-registro se redacta y se declara vigente bajo esa autorización. No hay otra cita del operador sobre este documento.
- [x] **K = 69**: 68 cortes del registro más `mlb|team_totals` (§3.3). Es una decisión de diseño tomada bajo esa autorización.
- [x] **Techo de 84 cortes**: **valor derivado** bajo esa autorización, no confirmado expresamente por el operador, al contrario que el 63 del 2026-09-25. Sale de los mismos dos invariantes que el operador confirmó entonces (§3.4) y es el máximo que no relaja lo aprobado. Si el operador quiere confirmarlo o corregirlo, se registra aquí como tal.
- [ ] Confirmación expresa del operador del techo de 84: pendiente, **no bloqueante**. El techo derivado rige desde el commit.

### Implementación (hecha el 2026-11-02; números de línea anteriores al cambio)

| Regla | Dónde | Cambio |
|---|---|---|
| `α_corte = 0,05/69`, derivado y no escrito a mano | `src/sqp/risk/prediction_gate.py` l. 120 | `PREDICTION_GATE_K = 69` |
| Techo de 84 cortes | `src/sqp/risk/prediction_gate.py` l. 128 | `PREDICTION_GATE_K_REPREGISTRO = 84` |
| Comentarios con K = 52, 0,000962 y 63 | `src/sqp/risk/prediction_gate.py` l. 57, 117–127, 232 (mención histórica: revisar que siga siendo cierta), 578–581, 610 | Citar este re-pre-registro, 0,000725, 84 = ⌊69 × 50/41⌋, y 84 × 0,05/69 = 0,0609 |
| Umbral citado en la documentación operativa | `configs/default.yaml` l. 240–241 y 267–268; `scripts/gate_status.py` l. 25; `.claude/skills/clv-shadow-exit/SKILL.md` l. 54 | `0,05/69 = 0,000725`, K = 69 desde el re-pre-registro del 2026-11-02 (antes 52 y 41). Lo fija `test_ningun_documento_presenta_el_alpha_de_familia_como_umbral_por_mercado` |
| Tests | `tests/test_prediction_gate.py` l. 716 (docstring con 0,000962), l. 918 (comentario «63 con K=52»), l. 942 (`== 63` → `== 84`; la fórmula `K * 50 // 41` sigue igual), l. 948 (docstring con 52 y 63) | Actualizar valores. La lógica de las tres franjas no cambia |
| Skill de salida | `.claude/skills/clv-shadow-exit/SKILL.md` | Ya incluido arriba. Al ser una skill, comprobar que el bloque `## Reglas comunes` no se toca (`test_quant_skills_share_an_identical_common_rules_block`) |

La implementación debe estar en `main` antes del primer run en que `nhl|spreads` o `nhl|totals` alcancen n ≥ 300. Si un run llegara a evaluar uno de ellos antes del commit, su test se haría con 0,05/52, un criterio más laxo y fuera de lo pre-registrado. En ese caso, el corte afectado se registra como incidente: la decisión se anota y no se usa para abrir la puerta.
