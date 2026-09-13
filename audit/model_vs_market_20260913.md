# Modelo vs mercado y valor del edge

Generado: 2026-09-13 - filas servidas: 24324 - picks unicos: 9550 - eventos: 1783

Fuente: stream servido (`data/calibration/graded_*.csv`), todas las caras priceadas antes de cualquier filtro de stake. Intervalos al 95% por bootstrap agrupado por evento.

**Unidades.** El stream guarda una fila por dia de horizonte, asi que el mismo pick aparece varias veces (2,19x el 2026-08-27). Las secciones de ROI (3, 4 y 5) miden POLITICA y colapsan a **una fila por apuesta** -- una apuesta se hace una vez. La seccion 1 (Brier) se queda sobre todas las servidas a proposito: cada servida es una prediccion distinta a un precio distinto, la comparacion es pareada contra el mercado en la misma fila y el IC ya agrupa por evento.

ROI REALIZADO sobre muestra historica. NO es una promesa de ganancia.

## 1. Agregado: modelo vs mercado

`brier_diff = modelo - mercado`; NEGATIVO = el modelo gana. El veredicto lo fija el intervalo, no el punto estimado.

- `model_probability`: n=9294, eventos=1759, brier modelo=0.24237 vs mercado=0.22983, diff=+0.01254 IC95=[+0.00876, +0.01636] -> **mercado mejor**
- `calibrated_probability`: n=9294, eventos=1759, brier modelo=0.23357 vs mercado=0.22983, diff=+0.00374 IC95=[+0.00199, +0.00537] -> **mercado mejor**

## 2. Por (liga, mercado)

Atencion a las comparaciones multiples: con ~38 segmentos y alpha=0.05, un par de veredictos extremos son ruido esperado.

**AVISO: estos segmentos se sirvieron con la probabilidad CALIBRADA aplanada**, asi que su veredicto de abajo no puntua al modelo sino a una constante. Huella de un calibrador colapsado en produccion (`calibrator._keeps_resolution`).

| league | market | dias | filas | desde | hasta |
|---|---|---|---|---|---|
| mlb | totals | 19 | 446 | 2026-07-28 | 2026-09-09 |
| wnba | totals | 34 | 412 | 2026-07-22 | 2026-08-27 |
| wnba | spreads | 2 | 14 | 2026-08-29 | 2026-08-30 |

| league | market | n_rows | n_events | brier_model | brier_market | brier_diff | brier_diff_lo | brier_diff_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| mlb | totals | 1222 | 587 | 0.25036 | 0.24956 | 0.00081 | -0.00192 | 0.00371 | equivalente (IC cruza 0) |
| mlb | spreads | 1214 | 602 | 0.24234 | 0.24054 | 0.0018 | -0.00101 | 0.00437 | equivalente (IC cruza 0) |
| mlb | h2h | 1204 | 602 | 0.24111 | 0.24034 | 0.00077 | -0.00146 | 0.00291 | equivalente (IC cruza 0) |
| wnba | totals | 526 | 144 | 0.26031 | 0.24986 | 0.01045 | 0.00295 | 0.01824 | mercado mejor |
| wnba | spreads | 458 | 144 | 0.24894 | 0.24928 | -0.00034 | -0.00856 | 0.00711 | equivalente (IC cruza 0) |
| wnba | h2h | 288 | 144 | 0.18626 | 0.17997 | 0.00629 | 0.00088 | 0.01187 | mercado mejor |
| mls | spreads | 274 | 85 | 0.23344 | 0.22572 | 0.00771 | -0.00205 | 0.01812 | equivalente (IC cruza 0) |
| ncaaf | totals | 264 | 50 | 0.25596 | 0.25003 | 0.00593 | -0.00631 | 0.01861 | equivalente (IC cruza 0) |
| mls | h2h | 261 | 87 | 0.22605 | 0.22348 | 0.00257 | -0.00291 | 0.00746 | equivalente (IC cruza 0) |
| tennis_atp_us_open | h2h | 218 | 109 | 0.19556 | 0.18713 | 0.00843 | -0.00445 | 0.01919 | equivalente (IC cruza 0) |
| tennis_wta_us_open | h2h | 214 | 107 | 0.15345 | 0.1407 | 0.01275 | 0.00188 | 0.02344 | mercado mejor |
| tennis_wta_cincinnati_open | h2h | 208 | 104 | 0.20453 | 0.19671 | 0.00781 | -0.00492 | 0.01988 | equivalente (IC cruza 0) |
| ncaaf | spreads | 202 | 49 | 0.29352 | 0.24981 | 0.04371 | 0.00764 | 0.08051 | mercado mejor |
| mls | totals | 196 | 87 | 0.24222 | 0.24114 | 0.00107 | -0.00403 | 0.00622 | equivalente (IC cruza 0) |
| tennis_atp_cincinnati_open | h2h | 192 | 96 | 0.21796 | 0.23149 | -0.01354 | -0.02441 | -0.00241 | modelo MEJOR |
| brasileirao | h2h | 174 | 58 | 0.20173 | 0.20393 | -0.00221 | -0.0073 | 0.00288 | equivalente (IC cruza 0) |
| tennis_atp_canadian_open | h2h | 170 | 85 | 0.23066 | 0.21923 | 0.01143 | 0.00102 | 0.02173 | mercado mejor |
| brasileirao | spreads | 168 | 56 | 0.24253 | 0.23947 | 0.00306 | -0.00779 | 0.01561 | equivalente (IC cruza 0) |
| tennis_wta_canadian_open | h2h | 166 | 83 | 0.19641 | 0.18156 | 0.01485 | 0.00457 | 0.02593 | mercado mejor |
| chile | spreads | 154 | 42 | 0.24965 | 0.2497 | -6e-05 | -0.01341 | 0.01278 | equivalente (IC cruza 0) |
| chile | h2h | 126 | 42 | 0.20104 | 0.19891 | 0.00213 | -0.00429 | 0.00823 | equivalente (IC cruza 0) |
| brasileirao | totals | 118 | 58 | 0.25084 | 0.25832 | -0.00748 | -0.01448 | -0.00019 | modelo MEJOR |
| ncaaf | h2h | 100 | 50 | 0.11324 | 0.09037 | 0.02286 | 0.00396 | 0.03715 | mercado mejor |
| ligamx | spreads | 98 | 30 | 0.24684 | 0.23352 | 0.01332 | -0.00184 | 0.03053 | equivalente (IC cruza 0) |
| ligamx | h2h | 90 | 30 | 0.20689 | 0.2003 | 0.00659 | -0.00101 | 0.01497 | equivalente (IC cruza 0) |
| chile | totals | 90 | 42 | 0.23883 | 0.24242 | -0.00359 | -0.01028 | 0.00387 | equivalente (IC cruza 0) |
| seriea | h2h | 75 | 25 | 0.18383 | 0.18128 | 0.00255 | -0.00644 | 0.01073 | equivalente (IC cruza 0) |
| seriea | spreads | 66 | 24 | 0.24119 | 0.24299 | -0.0018 | -0.01879 | 0.01685 | equivalente (IC cruza 0) |
| laliga | spreads | 64 | 21 | 0.25349 | 0.25338 | 0.00011 | -0.01351 | 0.014 | equivalente (IC cruza 0) |
| laliga | h2h | 63 | 21 | 0.18359 | 0.18246 | 0.00113 | -0.0062 | 0.00745 | equivalente (IC cruza 0) |
| ligamx | totals | 62 | 30 | 0.27374 | 0.26927 | 0.00447 | -0.00303 | 0.01194 | equivalente (IC cruza 0) |
| epl | h2h | 57 | 19 | 0.19407 | 0.19822 | -0.00415 | -0.01696 | 0.00842 | equivalente (IC cruza 0) |
| epl | spreads | 52 | 16 | 0.22 | 0.24763 | -0.02763 | -0.04771 | -0.00174 | modelo MEJOR |
| seriea | totals | 52 | 25 | 0.24015 | 0.24802 | -0.00786 | -0.02156 | 0.0056 | equivalente (IC cruza 0) |
| laliga | totals | 48 | 21 | 0.2492 | 0.24026 | 0.00894 | -0.01134 | 0.03089 | equivalente (IC cruza 0) |
| tennis_atp_washington_open | h2h | 46 | 23 | 0.23305 | 0.23324 | -0.0002 | -0.01577 | 0.01636 | equivalente (IC cruza 0) |
| tennis_wta_washington_open | h2h | 46 | 23 | 0.20484 | 0.20427 | 0.00056 | -0.02259 | 0.01863 | equivalente (IC cruza 0) |
| epl | totals | 42 | 19 | 0.24759 | 0.23582 | 0.01176 | -0.00156 | 0.02444 | equivalente (IC cruza 0) |
| tennis_wta_monterrey_open | h2h | 34 | 17 | 0.24747 | 0.24777 | -0.0003 | -0.0388 | 0.03501 | equivalente (IC cruza 0) |
| ligue1 | h2h | 33 | 11 | 0.22251 | 0.22654 | -0.00403 | -0.01476 | 0.00589 | equivalente (IC cruza 0) |
| ligue1 | spreads | 28 | 10 | 0.2228 | 0.23184 | -0.00904 | -0.02802 | 0.01047 | equivalente (IC cruza 0) |
| ligue1 | totals | 22 | 11 | 0.24478 | 0.2498 | -0.00502 | -0.01994 | 0.00809 | equivalente (IC cruza 0) |
| bundesliga | spreads | 16 | 5 | 0.26631 | 0.2543 | 0.01201 | -0.0658 | 0.06552 | equivalente (IC cruza 0) |
| bundesliga | h2h | 15 | 5 | 0.13074 | 0.13656 | -0.00582 | -0.03167 | 0.02481 | equivalente (IC cruza 0) |
| tennis_wta_wimbledon | h2h | 12 | 6 | 0.21968 | 0.23157 | -0.0119 | -0.0404 | 0.00944 | equivalente (IC cruza 0) |
| ucl | h2h | 12 | 4 | 0.19398 | 0.19526 | -0.00128 | -0.01848 | 0.01335 | equivalente (IC cruza 0) |
| tennis_atp_wimbledon | h2h | 12 | 6 | 0.14109 | 0.13316 | 0.00793 | -0.02832 | 0.0344 | equivalente (IC cruza 0) |
| bundesliga | totals | 12 | 5 | 0.26092 | 0.26419 | -0.00327 | -0.0235 | 0.01219 | equivalente (IC cruza 0) |
| ucl | totals | 10 | 4 | 0.19318 | 0.18554 | 0.00764 | -0.01588 | 0.04144 | equivalente (IC cruza 0) |
| ucl | spreads | 8 | 4 | 0.21339 | 0.21164 | 0.00175 | -0.02522 | 0.02698 | equivalente (IC cruza 0) |
| nfl | spreads | 4 | 2 | 0.26122 | 0.25218 | 0.00904 | 0.00479 | 0.0133 | mercado mejor |
| nfl | h2h | 4 | 2 | 0.26855 | 0.27606 | -0.00751 | -0.02068 | 0.00567 | equivalente (IC cruza 0) |
| nfl | totals | 4 | 2 | 0.21428 | 0.24716 | -0.03288 | -0.0625 | -0.00326 | modelo MEJOR |

## 3. Escalera de `min_edge`: vale algo el edge declarado?

Si el edge tuviera informacion, `roi_flat` CRECERIA con el umbral.

### Suelo de probabilidad implicita = 0.00

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.0 | 2023 | 1241 | 0.42215 | -0.11397 | -0.17465 | -0.05165 | ROI negativo |
| 0.02 | 0.0 | 1538 | 1008 | 0.40442 | -0.12784 | -0.19273 | -0.05382 | ROI negativo |
| 0.05 | 0.0 | 1014 | 710 | 0.37278 | -0.16718 | -0.25037 | -0.08134 | ROI negativo |
| 0.08 | 0.0 | 688 | 504 | 0.32703 | -0.23131 | -0.33108 | -0.12214 | ROI negativo |
| 0.12 | 0.0 | 432 | 329 | 0.25926 | -0.33051 | -0.47157 | -0.19045 | ROI negativo |

### Suelo de probabilidad implicita = 0.35

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.35 | 1604 | 997 | 0.48441 | -0.0611 | -0.11776 | -0.00793 | ROI negativo |
| 0.02 | 0.35 | 1154 | 759 | 0.48007 | -0.06132 | -0.13131 | 0.00766 | indistinguible de 0 |
| 0.05 | 0.35 | 684 | 470 | 0.47953 | -0.05594 | -0.14818 | 0.03191 | indistinguible de 0 |
| 0.08 | 0.35 | 413 | 296 | 0.45278 | -0.10758 | -0.22611 | 0.0048 | indistinguible de 0 |
| 0.12 | 0.35 | 211 | 155 | 0.3981 | -0.20197 | -0.36158 | -0.02775 | ROI negativo |

## 4. Cap de plausibilidad: esta cortando lo peor o picks buenos?

`risk.max_plausible_edge` descarta candidatos cuyo edge declarado es implausible. Es el control con MAS trabajo efectivo del sistema: en un run real el 63% de las filas descartadas llevan su flag, mas que el gate de prediccion. Un cap util corta lo que rinde PEOR.

AVISO: el techo se barre sobre la misma muestra que se evalua, asi que el mejor punto esta sesgado al alza. Sirve para VIGILAR que el cap sigue funcionando, no para optimizarlo.

| cap | n_pasan | roi_pasan | roi_pasan_lo | roi_pasan_hi | n_cortadas | roi_cortadas | roi_cortadas_lo | roi_cortadas_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 0.05 | 1007 | -0.06146 | -0.13177 | 0.00866 | 1013 | -0.16636 | -0.25377 | -0.08264 | el cap corta lo peor |
| 0.075 | 1288 | -0.05568 | -0.11782 | 0.01381 | 732 | -0.2168 | -0.33275 | -0.11343 | el cap corta lo peor |
| 0.1 | 1488 | -0.04994 | -0.11125 | 0.01385 | 532 | -0.29343 | -0.40975 | -0.17105 | el cap corta lo peor |
| 0.15 | 1684 | -0.06782 | -0.12622 | -0.00171 | 336 | -0.34585 | -0.51207 | -0.16813 | el cap corta lo peor |
| 0.2 | 1801 | -0.08115 | -0.13695 | -0.0224 | 219 | -0.3847 | -0.58497 | -0.16321 | el cap corta lo peor |
| 0.3 | 1914 | -0.09562 | -0.15203 | -0.03369 | 106 | -0.44717 | -0.76992 | -0.0728 | el cap corta lo peor |
| inf | 2020 | -0.11406 | -0.17734 | -0.05619 | 0 |  |  |  | sin cap |

## 5. Contraste directo de la seleccion

- ROI donde el modelo apuesta (edge>0): **-0.1141** (n=2020)
- ROI en el resto (edge<=0): **-0.0511** (n=7274)
- Delta = **-0.0630**, IC95 = [-0.1306, +0.0118]

Delta negativo con IC que excluye 0 significa que la regla de seleccion RESTA valor: el sistema apuesta el peor lado de cada mercado.
