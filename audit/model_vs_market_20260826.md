# Modelo vs mercado y valor del edge

Generado: 2026-08-26 - filas graduadas: 14223 - eventos: 1214

Fuente: stream servido (`data/calibration/graded_*.csv`), todas las caras priceadas antes de cualquier filtro de stake. Intervalos al 95% por bootstrap agrupado por evento.

ROI REALIZADO sobre muestra historica. NO es una promesa de ganancia.

## 1. Agregado: modelo vs mercado

`brier_diff = modelo - mercado`; NEGATIVO = el modelo gana. El veredicto lo fija el intervalo, no el punto estimado.

- `model_probability`: n=13861, eventos=1200, brier modelo=0.2389 vs mercado=0.23013, diff=+0.00877 IC95=[+0.00451, +0.01311] -> **mercado mejor**
- `calibrated_probability`: n=13861, eventos=1200, brier modelo=0.23261 vs mercado=0.23013, diff=+0.00248 IC95=[+0.00052, +0.00444] -> **mercado mejor**

## 2. Por (liga, mercado)

Atencion a las comparaciones multiples: con ~38 segmentos y alpha=0.05, un par de veredictos extremos son ruido esperado.

| league | market | n_rows | n_events | brier_model | brier_market | brier_diff | brier_diff_lo | brier_diff_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| mls | h2h | 1161 | 61 | 0.22725 | 0.22299 | 0.00425 | -0.0018 | 0.00968 | equivalente (IC cruza 0) |
| mlb | spreads | 1020 | 467 | 0.2449 | 0.24356 | 0.00134 | -0.00194 | 0.00468 | equivalente (IC cruza 0) |
| mlb | h2h | 1014 | 467 | 0.23917 | 0.23937 | -0.0002 | -0.00319 | 0.00244 | equivalente (IC cruza 0) |
| mlb | totals | 1010 | 455 | 0.25004 | 0.24938 | 0.00066 | -0.00302 | 0.00419 | equivalente (IC cruza 0) |
| brasileirao | h2h | 855 | 43 | 0.2055 | 0.20754 | -0.00204 | -0.00821 | 0.00371 | equivalente (IC cruza 0) |
| mls | totals | 778 | 61 | 0.24026 | 0.24222 | -0.00195 | -0.00795 | 0.00417 | equivalente (IC cruza 0) |
| mls | spreads | 716 | 60 | 0.23788 | 0.23329 | 0.00459 | -0.00665 | 0.01567 | equivalente (IC cruza 0) |
| brasileirao | totals | 570 | 43 | 0.25486 | 0.26327 | -0.00841 | -0.01627 | -0.00135 | modelo MEJOR |
| wnba | spreads | 562 | 127 | 0.24704 | 0.24912 | -0.00208 | -0.01009 | 0.00619 | equivalente (IC cruza 0) |
| wnba | totals | 554 | 127 | 0.26064 | 0.24977 | 0.01087 | 0.00281 | 0.0193 | mercado mejor |
| wnba | h2h | 528 | 127 | 0.18208 | 0.17454 | 0.00754 | 0.00145 | 0.01268 | mercado mejor |
| chile | h2h | 525 | 28 | 0.20689 | 0.20152 | 0.00537 | -0.00152 | 0.01277 | equivalente (IC cruza 0) |
| brasileirao | spreads | 518 | 41 | 0.24664 | 0.24795 | -0.0013 | -0.01486 | 0.01196 | equivalente (IC cruza 0) |
| ligamx | h2h | 435 | 22 | 0.21313 | 0.20834 | 0.00479 | -0.00465 | 0.01349 | equivalente (IC cruza 0) |
| chile | totals | 350 | 28 | 0.23551 | 0.23667 | -0.00116 | -0.01021 | 0.00725 | equivalente (IC cruza 0) |
| chile | spreads | 348 | 28 | 0.26253 | 0.25189 | 0.01065 | -0.00635 | 0.0267 | equivalente (IC cruza 0) |
| tennis_atp_canadian_open | h2h | 302 | 85 | 0.23479 | 0.22286 | 0.01193 | -0.00023 | 0.02444 | equivalente (IC cruza 0) |
| tennis_wta_canadian_open | h2h | 298 | 83 | 0.19763 | 0.18195 | 0.01568 | 0.00601 | 0.0254 | mercado mejor |
| ligamx | totals | 292 | 22 | 0.26696 | 0.26363 | 0.00333 | -0.00506 | 0.01058 | equivalente (IC cruza 0) |
| ligamx | spreads | 280 | 22 | 0.26248 | 0.24618 | 0.0163 | -0.00558 | 0.03607 | equivalente (IC cruza 0) |
| tennis_wta_cincinnati_open | h2h | 276 | 104 | 0.205 | 0.20229 | 0.00271 | -0.01449 | 0.01847 | equivalente (IC cruza 0) |
| tennis_atp_cincinnati_open | h2h | 234 | 96 | 0.21037 | 0.22146 | -0.01109 | -0.02188 | -0.00109 | modelo MEJOR |
| seriea | h2h | 144 | 8 | 0.17834 | 0.17641 | 0.00193 | -0.00634 | 0.0109 | equivalente (IC cruza 0) |
| laliga | h2h | 141 | 8 | 0.18856 | 0.18661 | 0.00194 | -0.01265 | 0.01324 | equivalente (IC cruza 0) |
| epl | h2h | 108 | 6 | 0.21038 | 0.20257 | 0.00781 | -0.022 | 0.0372 | equivalente (IC cruza 0) |
| seriea | totals | 96 | 8 | 0.22054 | 0.20475 | 0.01579 | 0.00533 | 0.02675 | mercado mejor |
| laliga | totals | 94 | 8 | 0.21345 | 0.23048 | -0.01703 | -0.04125 | 0.01043 | equivalente (IC cruza 0) |
| seriea | spreads | 86 | 7 | 0.23854 | 0.23994 | -0.0014 | -0.01891 | 0.02173 | equivalente (IC cruza 0) |
| laliga | spreads | 82 | 8 | 0.26427 | 0.26177 | 0.0025 | -0.03142 | 0.02992 | equivalente (IC cruza 0) |
| epl | spreads | 74 | 6 | 0.26159 | 0.24564 | 0.01594 | -0.04105 | 0.07878 | equivalente (IC cruza 0) |
| epl | totals | 72 | 6 | 0.23463 | 0.24077 | -0.00613 | -0.02453 | 0.01393 | equivalente (IC cruza 0) |
| ligue1 | h2h | 72 | 4 | 0.16842 | 0.16077 | 0.00765 | 0.00249 | 0.01201 | mercado mejor |
| tennis_atp_washington_open | h2h | 70 | 23 | 0.23215 | 0.2367 | -0.00456 | -0.02307 | 0.01555 | equivalente (IC cruza 0) |
| tennis_wta_washington_open | h2h | 64 | 23 | 0.1931 | 0.19024 | 0.00286 | -0.01865 | 0.02087 | equivalente (IC cruza 0) |
| ligue1 | totals | 48 | 4 | 0.30324 | 0.29078 | 0.01246 | 0.00437 | 0.02055 | mercado mejor |
| ligue1 | spreads | 48 | 4 | 0.24097 | 0.22425 | 0.01672 | 0.00913 | 0.02461 | mercado mejor |
| tennis_atp_wimbledon | h2h | 18 | 6 | 0.1101 | 0.09823 | 0.01186 | -0.0172 | 0.03207 | equivalente (IC cruza 0) |
| tennis_wta_wimbledon | h2h | 18 | 6 | 0.25202 | 0.25907 | -0.00705 | -0.03627 | 0.00612 | equivalente (IC cruza 0) |

## 3. Escalera de `min_edge`: vale algo el edge declarado?

Si el edge tuviera informacion, `roi_flat` CRECERIA con el umbral.

### Suelo de probabilidad implicita = 0.00

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.0 | 2769 | 868 | 0.42976 | -0.11024 | -0.20012 | -0.01356 | ROI negativo |
| 0.02 | 0.0 | 2052 | 697 | 0.41618 | -0.1128 | -0.22559 | -0.00017 | ROI negativo |
| 0.05 | 0.0 | 1326 | 483 | 0.38386 | -0.15548 | -0.29249 | -0.0071 | ROI negativo |
| 0.08 | 0.0 | 813 | 334 | 0.3321 | -0.23845 | -0.40518 | -0.05647 | ROI negativo |
| 0.12 | 0.0 | 422 | 200 | 0.30095 | -0.23886 | -0.47584 | 0.01675 | indistinguible de 0 |

### Suelo de probabilidad implicita = 0.35

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.35 | 2218 | 728 | 0.48693 | -0.06241 | -0.15371 | 0.02836 | indistinguible de 0 |
| 0.02 | 0.35 | 1572 | 554 | 0.48028 | -0.0642 | -0.18057 | 0.04968 | indistinguible de 0 |
| 0.05 | 0.35 | 942 | 348 | 0.46921 | -0.07125 | -0.21543 | 0.08642 | indistinguible de 0 |
| 0.08 | 0.35 | 518 | 213 | 0.44015 | -0.1208 | -0.32028 | 0.07833 | indistinguible de 0 |
| 0.12 | 0.35 | 223 | 99 | 0.43498 | -0.10587 | -0.41207 | 0.1656 | indistinguible de 0 |

## 4. Cap de plausibilidad: esta cortando lo peor o picks buenos?

`risk.max_plausible_edge` descarta candidatos cuyo edge declarado es implausible. Es el control con MAS trabajo efectivo del sistema: en un run real el 63% de las filas descartadas llevan su flag, mas que el gate de prediccion. Un cap util corta lo que rinde PEOR.

AVISO: el techo se barre sobre la misma muestra que se evalua, asi que el mejor punto esta sesgado al alza. Sirve para VIGILAR que el cap sigue funcionando, no para optimizarlo.

| cap | n_pasan | roi_pasan | roi_pasan_lo | roi_pasan_hi | n_cortadas | roi_cortadas | roi_cortadas_lo | roi_cortadas_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 0.05 | 1441 | -0.06837 | -0.16551 | 0.03312 | 1324 | -0.15421 | -0.29181 | -0.00558 | el cap corta lo peor |
| 0.075 | 1893 | -0.05583 | -0.15548 | 0.04566 | 872 | -0.22591 | -0.38135 | -0.04197 | el cap corta lo peor |
| 0.1 | 2182 | -0.0781 | -0.17493 | 0.01817 | 583 | -0.22687 | -0.43341 | -0.00182 | el cap corta lo peor |
| 0.15 | 2479 | -0.0937 | -0.18261 | -0.00248 | 286 | -0.24621 | -0.52752 | 0.07044 | el cap corta lo peor |
| 0.2 | 2649 | -0.10044 | -0.19368 | -6e-05 | 116 | -0.31578 | -0.71953 | 0.0571 | el cap corta lo peor |
| 0.3 | 2724 | -0.1077 | -0.20306 | -0.01366 | 41 | -0.22695 | -0.82779 | 0.49207 | el cap corta lo peor |
| inf | 2765 | -0.10947 | -0.19727 | -0.01465 | 0 |  |  |  | sin cap |

## 5. Contraste directo de la seleccion

- ROI donde el modelo apuesta (edge>0): **-0.1095** (n=2765)
- ROI en el resto (edge<=0): **-0.0508** (n=11096)
- Delta = **-0.0586**, IC95 = [-0.1778, +0.0538]

Delta negativo con IC que excluye 0 significa que la regla de seleccion RESTA valor: el sistema apuesta el peor lado de cada mercado.
