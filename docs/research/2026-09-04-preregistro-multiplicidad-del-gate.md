# Pre-registro — multiplicidad y miradas repetidas del prediction gate

**Fecha:** 2026-09-04.
**Estado:** **VIGENTE.** Aprobado por el operador el 2026-09-04 e implementado el
mismo día en `src/sqp/risk/prediction_gate.py`.
**Modifica:** `docs/research/2026-08-16-preregistro-regla-de-salida.md`, sección
«Criterios de descarte» → «Comparaciones múltiples».

> **Nota de implementación (2026-09-04).** El criterio se aprobó con los 41
> cortes en `muestra_insuficiente`, es decir **sin que ninguno fuera elegible y
> sin saber quién cruzaría primero** — que era justo la condición que este
> documento perseguía. Los registros anteriores no traen `entry_test_at`; se
> leen como «test no consumido», que es lo correcto: ninguno lo había gastado.
> Dos reglas fijadas por test, y una tercera consecuencia que solo apareció al
> implementarlo: un corte que gasta su test **no arma pestillo** (nunca estuvo
> dentro), así que `release_prediction_gate_latch` tuvo que ampliarse o esos
> cortes habrían quedado fuera **para siempre**, sin mecanismo de revisión.

> Se escribe **antes** de que ningún corte sea elegible. Hoy los 41 evaluados
> están en `muestra_insuficiente` (n < 300), así que fijar el criterio ahora no
> puede abrir ni cerrar una puerta a nadie en concreto. Esa ventana **se cierra
> en unos 16 días** (abajo), y con ella la posibilidad de decidir esto sin saber
> quién cruza primero.

---

## 1. Por qué

El pre-registro del 2026-08-16 aceptó explícitamente el riesgo de comparaciones
múltiples con este razonamiento:

> «el gate se evalúa sobre ~25 cortes. A p < 0,05 se esperan ~1,25 falsos
> positivos. Se acepta ese riesgo **porque la condición 2 (EV > 0) es un filtro
> independiente**. Si en la práctica entran varios cortes a la vez con EV
> marginal, se endurecerá a Bonferroni.»

Dos de las tres premisas ya no se sostienen, y la tercera nunca se comprobó.

### 1.1 No son ~25 cortes, son 41

Medido hoy en `data/bets/prediction_gate.json`: **41 cortes evaluados**. Con 41
tests simultáneos a α = 0,05, si todos fueran nulos:

| | P(al menos un falso positivo) en **una** evaluación |
|---|---:|
| α = 0,05, K = 41 | **87,8 %** |
| α = 0,05/41 (Bonferroni) | 4,9 % |

No es «~1,25 falsos positivos esperados»: es que **es más probable que haya al
menos uno a que no lo haya**.

### 1.2 La evaluación se repite a diario — esto no estaba contemplado

El pre-registro razona como si hubiera **un** análisis. `write_prediction_gate`
corre en cada `RUN_DIARIO_ALL.bat`: **19 evaluaciones** desde el 2026-08-16, una
más cada día, indefinidamente. Es testeo secuencial con parada opcional, y a α
fijo la tasa de error de tipo I **crece sin cota** con el número de miradas.

No pongo una cifra de FWER acumulado porque **no la tengo**: las miradas diarias
comparten casi todos los datos, así que la cota ingenua `1−(1−α)^(K·miradas)`
satura en 1,0000 y es un **techo grosero, no una estimación**. Lo que sí es
cierto sin necesidad de cuantificarlo: crece con cada día y nada lo acota.

### 1.3 El pestillo no protege del falso positivo — protege del segundo

`_apply_latch`: `latched = was_latched or (was_allowed and not stat_allowed)`.
Un corte que cruza por azar el día *k* obtiene `allowed: true` **ese día** y
puede llevar stake real. El pestillo solo se arma el día *k+1*, cuando deja de
cumplir. Es decir: el control **no impide que el falso positivo cueste dinero**,
solo impide la reentrada. Con `shadow_mode: false` y `clv_gate` desactivado, el
prediction gate es la única barrera vinculante.

### 1.4 «La condición 2 es un filtro independiente» — no verificado

Es la premisa sobre la que descansa la aceptación del riesgo y **nunca se
comprobó**. Hoy 8 de 41 cortes tienen `ev_flat > 0`, así que ~1 de cada 5
supera la condición 2. Un falso positivo del test de signo tiene por tanto del
orden de un 20 % de probabilidad de pasar también la condición 2 — la reduce,
no la elimina, y desde luego no es «independiente» en el sentido estadístico:
ambas se calculan sobre las mismas filas.

---

## 2. Estado medido hoy (antes de fijar nada)

```
41 cortes evaluados · los 41 en muestra_insuficiente · 0 permitidos
1 corte con p < 0,05 (epl|spreads, p=0,0106) pero n=16 y EV −0,044
8 cortes con ev_flat > 0
```

Cortes más cerca del umbral, y **por eso corre prisa**:

| corte | n | p | ev_flat | días a n=300 al ritmo observado |
|---|---:|---:|---:|---:|
| `mlb\|totals` | 163 | 0,3193 | −0,0495 | **~16** |
| `mlb\|spreads` | 162 | 0,7602 | −0,0490 | **~16** |
| `mlb\|h2h` | 159 | 1,0000 | −0,0301 | ~17 |
| `tennis_wta_us_open\|h2h` | 83 | 1,0000 | +0,1141 | ~50 |
| `wnba\|spreads` | 67 | 0,9290 | −0,0501 | ~66 |

**Ninguno es elegible todavía.** Ese es exactamente el motivo por el que este
documento se puede escribir con las manos limpias: no sé quién cruzará primero
ni con qué signo. Dentro de ~16 días sí lo sabré, y entonces cualquier cambio de
criterio sería indistinguible de ajustar la regla al resultado — el error de
KI-019, otra vez.

---

## 3. Qué se propone

### 3.1 Bonferroni sobre los cortes

```
α_corte = 0,05 / K        con K = 41 fijado hoy
α_corte = 0,00122
```

**Por qué K = 41 no es espiar los datos.** Contar cuántos cortes existe es un
hecho de diseño del pipeline, no un resultado: no dice quién gana ni con qué
p-valor. Los 41 están hoy en `muestra_insuficiente`, así que fijar K ahora no
puede favorecer ni perjudicar a ninguno en particular.

**Si el universo crece.** Las ligas entran y salen de temporada. Regla fijada de
antemano: si el número de cortes evaluados supera **50** (un 22 % sobre 41),
este criterio se **re-pre-registra antes** de que ningún corte nuevo sea
elegible. No se re-divide α sobre la marcha: eso volvería el umbral dependiente
del calendario.

### 3.2 Un solo test de entrada por corte

**La entrada se decide UNA vez**, en la primera evaluación en que el corte
alcanza `n ≥ 300`. Ese es su punto de análisis, determinado por los datos pero
declarado de antemano, y elimina la parada opcional: un corte no puede seguir
tirando el dado cada día hasta que salga.

- Si pasa (`p < α_corte` **y** `EV > 0`) → `allowed: true`.
- Si no pasa → queda **fuera** con `reason: agotado_test_unico`, y solo vuelve a
  evaluarse tras liberación humana explícita (`release_prediction_gate_latch`,
  el mecanismo que ya existe).

**La salida sigue siendo diaria.** La asimetría es deliberada y va en la
dirección segura: **una** oportunidad de entrar, vigilancia **continua** para
salir. Es la misma filosofía del pestillo del 2026-08-16, aplicada también a la
entrada.

### 3.3 Lo que NO cambia

`n ≥ 300` observaciones independientes; la definición de `d`; el uso de
`model_probability` pura; la exclusión de empates; la condición 2 (`EV > 0`); la
ventana fuera de muestra desde 2026-08-16; el pestillo de salida.

---

## 4. El precio, en la única unidad que importa

Con test de signo unilateral, victorias necesarias sobre `n` unidades:

| n | α = 0,05 (hoy) | α = 0,00122 (propuesto) |
|---:|---:|---:|
| 300 | 165 (**55,0 %**) | 177 (**59,0 %**) |
| 500 | 269 (53,8 %) | 285 (57,0 %) |
| 1000 | 527 (52,7 %) | 549 (54,9 %) |

**A n = 300 el listón sube de 55,0 % a 59,0 % de aciertos pareados.** Es un
salto grande y hay que decirlo sin adornos: **esto hace la puerta bastante más
difícil de cruzar, y es posible que ningún mercado la cruce nunca.**

Contrapeso, igual de honesto: hoy la puerta está calibrada de tal modo que, si
los 41 cortes fueran puro ruido, casi seguro que alguno la cruzaría. Una puerta
que el ruido abre con un 88 % de probabilidad no es una puerta. El proyecto ya
vivió la versión contraria —el gate de CLV, «una puerta que nadie puede cruzar
equivale a no tener puerta»— y la lección de ambas es la misma: el umbral tiene
que responder a la evidencia, no a lo cómodo que resulte.

---

## 5. Alternativas consideradas y por qué no

| Alternativa | Por qué no |
|---|---|
| **Benjamini–Hochberg (FDR q=0,05)** | Más potente que Bonferroni y sería defendible. Descartada por dos razones: bajo dependencia positiva exige la variante BY (que pierde casi toda la ventaja), y el umbral de cada corte pasaría a depender de los p-valores de los demás — es decir, **de resultados**. Bonferroni es peor estadísticamente y mejor como candado: es un número fijo, escrito, que nadie puede mover sin que se note en el diff. |
| **Frontera secuencial (Pocock / O'Brien-Fleming)** | Es la respuesta canónica al problema de las miradas repetidas y permitiría varios análisis por corte. Descartada por coste de implementación y de verificación: exige declarar el número de miradas por adelantado y una frontera por mirada. Un solo test por corte consigue el mismo control con una regla que cabe en una frase y se puede fijar con un test. |
| **Dejar de evaluar a diario y pasar a mensual** | Reduce las miradas pero no las elimina, y retrasa la entrada de un corte legítimo hasta un mes. Peor en las dos direcciones. |
| **No tocar nada** | Es la opción vigente. Su coste esperado, si los cortes son ruido, es dinero real sobre un falso positivo dentro de ~16 días. |

---

## 6. Predicción registrada, para no re-litigarla después

Con α = 0,00122 y el ritmo actual, **la predicción es que ningún corte pase el
gate en los próximos 90 días.** Si alguno pasa, será evidencia genuinamente
fuerte. Si al cabo de 180 días ninguno ha pasado y los EV siguen negativos en la
mayoría de cortes, la conclusión que toca no es relajar el umbral: es que el
modelo no bate al precio en ningún mercado, que es una respuesta legítima y la
que el conjunto de mediciones de agosto ya venía sugiriendo.

Los tres primeros cortes elegibles serán, salvo sorpresa, `mlb|totals`,
`mlb|spreads` y `mlb|h2h`, hacia el **2026-09-20**. Sus `ev_flat` de hoy son
**negativos los tres**, así que la predicción concreta es que **fallarán la
condición 2 antes incluso de llegar al test de signo**.

---

## 7. Lo que este cambio NO hace

No mejora el modelo, no aumenta el ROI y no acerca ningún mercado a ser
apostable. Reduce la probabilidad de que el sistema arriesgue capital sobre un
artefacto estadístico. Es un control de riesgo, no una fuente de rendimiento.

---

## 8. Decisión del operador

- [x] **APROBADO** el 2026-09-04, sin cambios sobre lo propuesto.

Implementado el mismo día:

| Regla | Dónde |
|---|---|
| `α_corte = 0,05/41 = 0,00122` derivado, no escrito a mano | `PREDICTION_GATE_{FAMILY_ALPHA,K,ALPHA}` |
| Un solo test de entrada, en la primera evaluación con `n ≥ 300` | `_apply_latch`, campo `entry_test_at` |
| Salida diaria sin cambios | `_apply_latch` (rama `was_allowed`) |
| Liberación humana devuelve el test | `release_prediction_gate_latch` |
| Aviso si el universo supera 50 cortes | `write_prediction_gate` |
| Reparto de α trazable en el registro | `family_alpha`, `k_bonferroni` en el payload |

Siete tests nuevos fijan ambas reglas, incluido el que discrimina de verdad
(`test_a_cut_that_would_pass_at_005_but_not_at_bonferroni_is_denied`: 165/300,
que pasaba con el α viejo y no con el nuevo) y los dos que cierran las puertas
traseras del test único — desaparecer del stream no lo devuelve, y la liberación
sí. Suite: 1289 pasan, 0 fallan.

## 9. Cuándo se sabrá si esto fue acertado

La predicción de la sección 6 es falsable y tiene fecha. Hacia el **2026-09-20**
los tres cortes de MLB alcanzan `n = 300` y gastarán su test único. Predicción
registrada: **fallarán la condición 2 (EV > 0) antes incluso de llegar al test de
signo**, porque hoy sus `ev_flat` son −0,0495, −0,0490 y −0,0301.

Si alguno pasa, será la primera evidencia fuera de muestra del proyecto de que el
modelo bate al precio en un mercado — y habrá pasado un listón del 59 %, no del
55 %. Si ninguno pasa en 180 días y los EV siguen negativos, la conclusión no es
relajar el umbral: es que el modelo no bate al precio, que es exactamente lo que
las seis mediciones de agosto venían sugiriendo.
