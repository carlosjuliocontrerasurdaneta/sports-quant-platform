# Modelo vs mercado y valor del edge

Generado: 2026-08-25 - filas graduadas: 14223 - eventos: 1214

Fuente: stream servido (`data/calibration/graded_*.csv`), todas las caras priceadas antes de cualquier filtro de stake. Intervalos al 95% por bootstrap agrupado por evento.

ROI REALIZADO sobre muestra historica. NO es una promesa de ganancia.

## 1. Agregado: modelo vs mercado

`brier_diff = modelo - mercado`; NEGATIVO = el modelo gana. El veredicto lo fija el intervalo, no el punto estimado.

- `model_probability`: n=13861, eventos=1200, brier modelo=0.2389 vs mercado=0.23013, diff=+0.00877 IC95=[+0.00449, +0.01304] -> **mercado mejor**
- `calibrated_probability`: n=13861, eventos=1200, brier modelo=0.23261 vs mercado=0.23013, diff=+0.00248 IC95=[+0.00051, +0.00444] -> **mercado mejor**

## 2. Por (liga, mercado)

Atencion a las comparaciones multiples: con ~38 segmentos y alpha=0.05, un par de veredictos extremos son ruido esperado.

| league | market | n_rows | n_events | brier_model | brier_market | brier_diff | brier_diff_lo | brier_diff_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| mls | h2h | 1161 | 61 | 0.22725 | 0.22299 | 0.00425 | -0.00179 | 0.00966 | equivalente (IC cruza 0) |
| mlb | spreads | 1020 | 467 | 0.2449 | 0.24356 | 0.00134 | -0.00193 | 0.00477 | equivalente (IC cruza 0) |
| mlb | h2h | 1014 | 467 | 0.23917 | 0.23937 | -0.0002 | -0.00318 | 0.0026 | equivalente (IC cruza 0) |
| mlb | totals | 1010 | 455 | 0.25004 | 0.24938 | 0.00066 | -0.00303 | 0.00411 | equivalente (IC cruza 0) |
| brasileirao | h2h | 855 | 43 | 0.2055 | 0.20754 | -0.00204 | -0.00818 | 0.00367 | equivalente (IC cruza 0) |
| mls | totals | 778 | 61 | 0.24026 | 0.24222 | -0.00195 | -0.00788 | 0.00402 | equivalente (IC cruza 0) |
| mls | spreads | 716 | 60 | 0.23788 | 0.23329 | 0.00459 | -0.00674 | 0.0157 | equivalente (IC cruza 0) |
| brasileirao | totals | 570 | 43 | 0.25486 | 0.26327 | -0.00841 | -0.01628 | -0.00134 | modelo MEJOR |
| wnba | spreads | 562 | 127 | 0.24704 | 0.24912 | -0.00208 | -0.01009 | 0.00616 | equivalente (IC cruza 0) |
| wnba | totals | 554 | 127 | 0.26064 | 0.24977 | 0.01087 | 0.00288 | 0.01931 | mercado mejor |
| wnba | h2h | 528 | 127 | 0.18208 | 0.17454 | 0.00754 | 0.00164 | 0.01284 | mercado mejor |
| chile | h2h | 525 | 28 | 0.20689 | 0.20152 | 0.00537 | -0.00155 | 0.01252 | equivalente (IC cruza 0) |
| brasileirao | spreads | 518 | 41 | 0.24664 | 0.24795 | -0.0013 | -0.01527 | 0.0117 | equivalente (IC cruza 0) |
| ligamx | h2h | 435 | 22 | 0.21313 | 0.20834 | 0.00479 | -0.00463 | 0.01343 | equivalente (IC cruza 0) |
| chile | totals | 350 | 28 | 0.23551 | 0.23667 | -0.00116 | -0.01026 | 0.00691 | equivalente (IC cruza 0) |
| chile | spreads | 348 | 28 | 0.26253 | 0.25189 | 0.01065 | -0.00633 | 0.02672 | equivalente (IC cruza 0) |
| tennis_atp_canadian_open | h2h | 302 | 85 | 0.23479 | 0.22286 | 0.01193 | -3e-05 | 0.02439 | equivalente (IC cruza 0) |
| tennis_wta_canadian_open | h2h | 298 | 83 | 0.19763 | 0.18195 | 0.01568 | 0.00616 | 0.02564 | mercado mejor |
| ligamx | totals | 292 | 22 | 0.26696 | 0.26363 | 0.00333 | -0.00475 | 0.01034 | equivalente (IC cruza 0) |
| ligamx | spreads | 280 | 22 | 0.26248 | 0.24618 | 0.0163 | -0.00546 | 0.03577 | equivalente (IC cruza 0) |
| tennis_wta_cincinnati_open | h2h | 276 | 104 | 0.205 | 0.20229 | 0.00271 | -0.01409 | 0.01846 | equivalente (IC cruza 0) |
| tennis_atp_cincinnati_open | h2h | 234 | 96 | 0.21037 | 0.22146 | -0.01109 | -0.02168 | -0.00113 | modelo MEJOR |
| seriea | h2h | 144 | 8 | 0.17834 | 0.17641 | 0.00193 | -0.00635 | 0.01076 | equivalente (IC cruza 0) |
| laliga | h2h | 141 | 8 | 0.18856 | 0.18661 | 0.00194 | -0.01254 | 0.01317 | equivalente (IC cruza 0) |
| epl | h2h | 108 | 6 | 0.21038 | 0.20257 | 0.00781 | -0.022 | 0.03782 | equivalente (IC cruza 0) |
| seriea | totals | 96 | 8 | 0.22054 | 0.20475 | 0.01579 | 0.00531 | 0.02666 | mercado mejor |
| laliga | totals | 94 | 8 | 0.21345 | 0.23048 | -0.01703 | -0.04129 | 0.00967 | equivalente (IC cruza 0) |
| seriea | spreads | 86 | 7 | 0.23854 | 0.23994 | -0.0014 | -0.01892 | 0.02184 | equivalente (IC cruza 0) |
| laliga | spreads | 82 | 8 | 0.26427 | 0.26177 | 0.0025 | -0.03112 | 0.02968 | equivalente (IC cruza 0) |
| epl | spreads | 74 | 6 | 0.26159 | 0.24564 | 0.01594 | -0.04105 | 0.07878 | equivalente (IC cruza 0) |
| epl | totals | 72 | 6 | 0.23463 | 0.24077 | -0.00613 | -0.02561 | 0.01428 | equivalente (IC cruza 0) |
| ligue1 | h2h | 72 | 4 | 0.16842 | 0.16077 | 0.00765 | 0.00249 | 0.01201 | mercado mejor |
| tennis_atp_washington_open | h2h | 70 | 23 | 0.23215 | 0.2367 | -0.00456 | -0.02276 | 0.01558 | equivalente (IC cruza 0) |
| tennis_wta_washington_open | h2h | 64 | 23 | 0.1931 | 0.19024 | 0.00286 | -0.01875 | 0.02101 | equivalente (IC cruza 0) |
| ligue1 | totals | 48 | 4 | 0.30324 | 0.29078 | 0.01246 | 0.00437 | 0.02055 | mercado mejor |
| ligue1 | spreads | 48 | 4 | 0.24097 | 0.22425 | 0.01672 | 0.00913 | 0.0252 | mercado mejor |
| tennis_atp_wimbledon | h2h | 18 | 6 | 0.1101 | 0.09823 | 0.01186 | -0.01684 | 0.03207 | equivalente (IC cruza 0) |
| tennis_wta_wimbledon | h2h | 18 | 6 | 0.25202 | 0.25907 | -0.00705 | -0.03613 | 0.00614 | equivalente (IC cruza 0) |

## 3. Escalera de `min_edge`: vale algo el edge declarado?

Si el edge tuviera informacion, `roi_flat` CRECERIA con el umbral.

### Suelo de probabilidad implicita = 0.00

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.0 | 2769 | 868 | 0.42976 | -0.11024 | -0.20021 | -0.01451 | ROI negativo |
| 0.02 | 0.0 | 2052 | 697 | 0.41618 | -0.1128 | -0.22166 | 0.00145 | indistinguible de 0 |
| 0.05 | 0.0 | 1326 | 483 | 0.38386 | -0.15548 | -0.2948 | -0.00745 | ROI negativo |
| 0.08 | 0.0 | 813 | 334 | 0.3321 | -0.23845 | -0.40956 | -0.05363 | ROI negativo |
| 0.12 | 0.0 | 422 | 200 | 0.30095 | -0.23886 | -0.47402 | 0.01921 | indistinguible de 0 |

### Suelo de probabilidad implicita = 0.35

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.35 | 2218 | 728 | 0.48693 | -0.06241 | -0.15575 | 0.02909 | indistinguible de 0 |
| 0.02 | 0.35 | 1572 | 554 | 0.48028 | -0.0642 | -0.18026 | 0.05133 | indistinguible de 0 |
| 0.05 | 0.35 | 942 | 348 | 0.46921 | -0.07125 | -0.21564 | 0.0875 | indistinguible de 0 |
| 0.08 | 0.35 | 518 | 213 | 0.44015 | -0.1208 | -0.31965 | 0.07715 | indistinguible de 0 |
| 0.12 | 0.35 | 223 | 99 | 0.43498 | -0.10587 | -0.42056 | 0.17641 | indistinguible de 0 |

## 4. Contraste directo de la seleccion

- ROI donde el modelo apuesta (edge>0): **-0.1095** (n=2765)
- ROI en el resto (edge<=0): **-0.0508** (n=11096)
- Delta = **-0.0586**, IC95 = [-0.1752, +0.0537]

Delta negativo con IC que excluye 0 significa que la regla de seleccion RESTA valor: el sistema apuesta el peor lado de cada mercado.
