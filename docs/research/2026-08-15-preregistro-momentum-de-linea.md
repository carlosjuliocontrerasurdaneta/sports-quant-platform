---
tags: [investigacion, preregistro, clv, momentum, sqp]
creada: 2026-08-15
actualizada: 2026-08-15
---

# Pre-registro — ¿queda movimiento de línea capturable? (test terminal)

> **Este documento se committea ANTES de ejecutar el análisis.** El orden queda
> probado por el historial de git, no por una afirmación aquí. Mismo
> procedimiento que KI-020 (`74aad07`, 2026-08-05).

## 1. Por qué este test y por qué es el último

Al 2026-08-05 hay cuatro mediciones negativas independientes:

| Sonda | Resultado |
|---|---|
| CLV mediano de los picks (consenso) | +0,0000% |
| Control: mejor precio en entrada **y** cierre | +0,0000% |
| Techo de ejecución, todas las casas | EV vs justo −1,83% |
| Value scanning graduado, sin 1xBet ni exchanges | ROI −3,72% |

Todas comparten un supuesto: **usan el modelo, o usan la dispersión entre casas
en un instante**. Queda una hipótesis estructuralmente distinta y sin tocar:

> ¿El movimiento pasado de la línea predice su movimiento futuro lo bastante
> como para pagar el vig?

Si la respuesta es sí, existe una estrategia que **no necesita el modelo**: se
compra el lado hacia el que el mercado ya se está moviendo y se cobra el
diferencial contra el cierre. Si es no, no queda ninguna vía sobre el feed
público de cuotas, y el proyecto se cierra.

Es el test terminal porque agota la última fuente de estructura disponible en
los datos que ya existen: el tiempo.

## 2. Hipótesis nula

**H0: el movimiento del consenso no-vig entre dos ventanas prepartido es
independiente del movimiento posterior hasta el cierre.** Es decir, la línea es
un martingala a resolución de 30 minutos y no hay nada que perseguir.

## 3. Diseño

Unidad de observación: `(liga, event_id, market, outcome, point)`.

Tres anclajes temporales, todos con `captured_at < commence_time`:

- **t1** — snapshot más antiguo disponible del evento.
- **t2** — último snapshot a ≥ 6 h del comienzo (el instante de decisión).
- **t3** — último snapshot a ≤ 90 min del comienzo (el cierre, mismo criterio de
  frescura que `CLOSE_MAX_AGE_MIN` en el gate vigente).

Se calcula la probabilidad estimada implícita **sin vig** del consenso (mediana
entre casas) en cada anclaje, y:

- `move_A = p_novig(t2) − p_novig(t1)` — el movimiento observable al decidir.
- `move_B = p_novig(t3) − p_novig(t2)` — el movimiento que habría que predecir.

**Regla evaluada:** en t2, tomar el lado con `move_A > 0` (el mercado viene hacia
él) al **precio de consenso** de t2, y medir su CLV contra el consenso de t3.

Precio de consenso, no mejor precio: es lo conservador y es lo que refleja lo
que se puede ejecutar de verdad. Ya está medido que el mejor precio de 67 casas
es anchura de mercado, no información.

### Filtros de plausibilidad (heredados de `value_scan.py`)

Sin ellos el resultado es basura presentada como oportunidad — ya ocurrió el
08-05 con órdenes sin emparejar de exchanges a 1000,0 decimal:

- `price_decimal` finito y en (1,0 , 51,0]
- ≥ 5 casas en el consenso de ese anclaje
- overround del mercado ≤ 1,25
- cuota ≤ 1,5× su propio consenso

### Trampa temporal (KI-019), explícita

`commence_time` vale el **último reportado** por el proveedor para ese evento
(fila de `captured_at` máximo), nunca uno arbitrario. El proveedor corrige la
hora de inicio sobre la marcha y con el valor obsoleto entran precios EN VIVO,
que fabrican resultados espectaculares y falsos. Este defecto ya se coló dos
veces en análisis de este proyecto. Cualquier snapshot con
`captured_at >= commence_time` se descarta.

## 4. Criterio de decisión — fijado antes de ver los resultados

**PASS** exige las tres condiciones, sin excepción:

1. **n ≥ 200** lados con los tres anclajes válidos tras filtros.
2. **Test de signo unilateral p < 0,05** sobre el CLV de la regla, excluyendo
   empates exactos de precio. Los empates se excluyen, no se cuentan en contra
   (criterio KI-020: un empate es ausencia de información).
3. **El efecto sobrevive excluyendo tenis.** Todo el ruido histórico de este
   proyecto vive ahí, y su muestra está congelada. Si la señal es solo tenis, no
   es señal.

Además se reporta, sin ser criterio: CLV mediano y medio, tasa de batir el
cierre, correlación `move_A`↔`move_B`, y desglose por liga y mercado.

**FAIL en cualquiera de las tres → se cierra el proyecto.** No se abre una
variante, no se ajusta el umbral, no se prueba otra ventana. Esa es la razón de
escribir esto antes.

**Un PASS no autoriza apostar dinero.** Autorizaría *construir* la fase de
ejecución y volver a medirla en shadow, con el gate de CLV por (liga, mercado)
intacto. El shadow mode no se toca en ningún escenario.

## 5. Salvaguarda contra el auto-engaño

Señales de que el resultado está contaminado, a comprobar antes de creerlo:

- **No-monotonía**: si el CLV no crece con la magnitud de `move_A`, se está
  midiendo otra cosa. Fue lo que delató KI-019.
- **Resultado demasiado bueno**: cualquier CLV mediano > +3% con este diseño es
  casi con certeza contaminación temporal, no un hallazgo.
- **Concentración en una liga o en pocos eventos**: se reporta el desglose
  precisamente para poder verlo.

## 6. Alcance

Solo lectura sobre `data/odds`. **Cero consumo de cuota del API.** No toca el
pipeline, ni configuración, ni riesgo, ni el shadow mode. Script en
`audit/reproductions/line_momentum.py`, junto a las otras reproducciones.

Todas las cifras son probabilidades estimadas y CLV es un diagnóstico de
proceso, nunca una promesa de ganancia.
