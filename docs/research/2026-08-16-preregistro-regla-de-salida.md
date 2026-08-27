# Pre-registro — nueva regla de salida por mercado (prediction gate)

**Fecha:** 2026-08-16. Escrito y commiteado **antes** de ejecutar el criterio
sobre datos nuevos, siguiendo la convención del pre-registro de momentum de
línea (2026-08-15).

## Por qué

El objetivo del sistema es estimar probabilidades pregame **con el único fin de
ganar dinero** con las apuestas de sus picks. La regla de salida vigente hasta
hoy exigía **CLV mediano positivo** por (liga, mercado). No sirve:

1. El CLV mide rendimiento contra un mercado, no la veracidad de la predicción.
   Dejó de ser métrica rectora el 2026-08-15.
2. Lleva vacía desde julio: ningún mercado la ha pasado nunca. Una puerta que
   nadie puede cruzar equivale a no tener puerta.

Al levantar el shadow mode (2026-08-16) el gate de CLV quedó como única barrera,
así que la regla equivocada pasó a ser la que decide sobre dinero real.

## Qué mide la regla nueva

Un (liga, mercado) lleva stake real solo si **predice mejor que el precio** y
además **esa ventaja sobrevive al vig**. Dos condiciones, ambas obligatorias.

### Condición 1 — el modelo bate al mercado, evento a evento

Test de **signo pareado** sobre el stream servido graduado. Por fila:

```
d = (p_mercado − y)² − (p_modelo − y)²
```

`d > 0` significa que el modelo erró menos **en ese evento concreto**. Pareado,
así que no lo distorsiona que unos partidos sean más predecibles que otros.

- **Estimador:** `model_probability`, la probabilidad **pura** del modelo. No la
  mezcla ni la calibrada: ambas contienen el precio dentro, y compararlas contra
  el mercado no diría si el modelo aporta algo propio.
- **Empates exactos** (`d == 0`) excluidos, misma convención que el gate
  intradía (KI-020).
- **Unilateral**, hipótesis: el modelo gana.
- **n ≥ 300** filas no empatadas.
- **p < 0,05**.

> **CORRECCIÓN 2026-08-27 — qué cuenta como una observación.** Este criterio se
> escribió diciendo «filas», y el código lo implementó literalmente: filas del
> stream servido. Esas filas **no son ensayos independientes**, que es justo lo
> que el test de signo asume, por dos vías que se multiplican:
>
> 1. `append_served` deduplica solo dentro del mismo día de run, así que un pick
>    dentro del horizonte de 7 días se sirve una vez por día. Medido hoy: 13.999
>    filas graduadas para 6.379 picks (2,19×).
> 2. Las dos caras del mismo mercado dan el **mismo** `d`: si `p' = 1−p` e
>    `y' = 1−y`, entonces `(p'−y')² = (p−y)²`. El lado contrario duplica `n` sin
>    aportar información.
>
> Efecto real: `mls|h2h` acumulaba **348 filas procedentes de 21 eventos** (16,6
> por evento) con el umbral en 300, y su p-valor iba por **0,0600** contra un
> alpha de 0,05; `brasileirao|h2h` marcaba **p = 0,000039 sobre 8 eventos**. El
> gate estaba a un paso de autorizar dinero real sobre un test inválido.
>
> A partir de hoy **`n` cuenta observaciones independientes: una por (evento,
> mercado, línea)**, promediando `d` y el EV dentro de cada una. El umbral 300 y
> el alpha 0,05 **no se tocan**. La corrección es estrictamente **conservadora**
> —solo puede reducir `n` y subir el p-valor, nunca abrir una puerta cerrada— y
> por eso se aplica sin nuevo pre-registro. Tras aplicarla, el mercado con más
> evidencia es `mlb|spreads` con **n = 156** y `p = 0,76`: ninguno se acerca al
> umbral, y los dos que parecían acercarse eran artefacto de la duplicación.

### Condición 2 — EV neto de vig positivo

Sobre las mismas filas, a **stake plano** de 1 unidad:

```
EV_medio = mean(p_modelo × (precio − 1) − (1 − p_modelo))
```

Debe ser **> 0**. Acertar más que el precio no basta si el margen no cubre el
vig; es la lección de `pick_mode: accuracy` (favoritos a 1.07) y del techo de
ejecución (EV −1,83 %).

### Fuera de muestra: la parte no negociable

**Solo cuentan las filas con `game_date` estrictamente posterior a la fecha de
este pre-registro (2026-08-16).** Todo lo anterior ya fue observado —el análisis
`prediction_vs_reality.py` de hoy miró esos datos— y usarlo sería validar sobre
la muestra donde se descubrió el patrón, que es exactamente el error de KI-019.

**Consecuencia aceptada y buscada:** el día de su entrada en vigor, el gate
niega **todos** los mercados (n = 0). La evidencia se acumula desde cero. Es el
comportamiento correcto: el sistema no debe apostar por un hallazgo post-hoc.

## Hipótesis registradas (para no re-litigar después)

Del análisis post-hoc de hoy, los candidatos con señal, en orden:

| Corte | gana/n (post-hoc) | Brier modelo | Brier mercado |
|---|---:|---:|---:|
| `brasileirao/totals` | 246/410 | 0,2461 | 0,2620 |
| `ligamx/h2h` | 208/291 | 0,1981 | 0,1976 |
| `mlb/spreads` | 468/828 | 0,2402 | 0,2392 |
| `chile/h2h` | 204/348 | 0,1950 | 0,1859 |

`brasileirao/totals` es el único que gana en **ambas** métricas y la predicción
explícita es que sea el primero en pasar el gate. Si el que pasa primero es otro,
o si ninguno pasa en 90 días, queda registrado aquí de antemano.

## Criterios de descarte, fijados antes de ver los datos

- **No monotonía** entre magnitud de la ventaja y resultado → descartar (fue lo
  que delató KI-019 y el falso positivo del bucket 2–5pp).
- Un corte que pase el gate y luego lo pierda **no vuelve a entrar** sin revisión
  humana: la histéresis evita el trasiego dentro-fuera por ruido.
- **Comparaciones múltiples:** el gate se evalúa sobre ~25 cortes. A p < 0,05 se
  esperan ~1,25 falsos positivos. Se acepta ese riesgo **porque la condición 2
  (EV > 0) es un filtro independiente** que un falso positivo del test de signo
  no supera sistemáticamente. Si en la práctica entran varios cortes a la vez con
  EV marginal, se endurecerá a Bonferroni.

## Lo que esta regla NO promete

Pasar el gate no es rentabilidad garantizada. Es la condición mínima para
arriesgar capital: evidencia fuera de muestra de que la predicción bate al
precio y de que el margen cubre el vig. Quedan fuera la ejecución (dónde se
apuesta, límites de cuenta) y la selección adversa.
