# Enmienda 2026-10-16: datos de nhl|h2h en el gate de prediccion (AUD-003)

Enmienda a la DEFINICION DE DATOS del gate de prediccion
(`docs/research/2026-08-16-preregistro-regla-de-salida.md`, multiplicidad del
2026-09-04 y re-pre-registro K=52 del 2026-09-25). No cambia el criterio
(test de signo, `min_n` 300, alpha 0,05/52, EV plano > 0, test unico de
entrada, pestillo): cambia que filas son validas para un corte.

## Hecho

AUD-003 (ronda audit-2026-10-15, P1): en NHL, liga a 2 vias, las casas que
cotizan el 1X2 reglamentario entraban en el consenso h2h. El Draw deprimia las
dos probabilidades justas: fair(home)+fair(away) < 0,95 en 1.150 de 1.835
snapshots; mediana 0,8477 en el stream servido. El `implied_probability_novig`
de nhl|h2h, que es el baseline de mercado del test, era falso.

El arreglo entra con el commit `ffc5ad3` (2026-10-16T12:56:03Z). La primera
fila servida despues (2026-10-16T15:07:19Z) suma 1,0 en 9 de 9 pares.

## Regla

En nhl|h2h solo cuentan las filas con `generated_at` >= 2026-10-16T12:56:03Z
(`INVALID_BEFORE` en `src/sqp/risk/prediction_gate.py`). Las filas sin
`generated_at` o con un sello ilegible no cuentan. Las filas se conservan
intactas en el stream servido: solo dejan de contar en el gate.

## Por que es legitima, y lo que ya se sabia

- El corte lo fija un hecho del pipeline (el instante del arreglo), no el signo
  de ningun resultado: excluye todas las filas anteriores, gane o pierda el
  modelo.
- El test de entrada no se habia gastado: n = 118 unidades < 300 y
  `entry_test_at` null. No se repite ninguna tirada.
- **Declarado:** el resultado de esas 118 unidades ya era conocido al decidir
  (49 victorias y 69 derrotas del modelo, p = 0,97, EV plano -0,034). La regla
  seria la misma con cualquier resultado.
- Es conservadora: retrasa el test de entrada de nhl|h2h (n vuelve a 0) y no
  puede abrir ningun corte.

Revision Fable antes del commit: APTO CON CAMBIOS (tests de borde y este rastro).

## Fuera de esta enmienda

- **Degradacion** (`src/sqp/risk/degradation.py`) no se toca. Su pausa por ROI
  usa resultados reales a precios reales, que son validos. El sesgo solo afecta
  a `brier_market`, y en una direccion PERMISIVA: con el mercado artificialmente
  peor, la pausa por Brier cuesta mas de activar y la reanudacion es mas facil.
  Impacto hoy nulo (stake 0 por el gate). La ventana movil de 60 dias se limpia
  sola el 2026-12-15.
- **Mediciones pre-registradas** que leen `implied_probability_novig` del mismo
  stream (`scripts/research/measure_el_modelo_manda.py`,
  `measure_segment_market_weight.py`, `measure_tier_a_gap.py`) no aplican este
  filtro. Antes de ejecutar cada una hay que decidir y declarar como trata
  nhl|h2h anterior a `ffc5ad3`; no se decide aqui.
