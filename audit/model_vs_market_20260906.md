# Modelo vs mercado y valor del edge

Generado: 2026-09-06 - filas servidas: 20048 - picks unicos: 8348 - eventos: 1620

Fuente: stream servido (`data/calibration/graded_*.csv`), todas las caras priceadas antes de cualquier filtro de stake. Intervalos al 95% por bootstrap agrupado por evento.

**Unidades.** El stream guarda una fila por dia de horizonte, asi que el mismo pick aparece varias veces (2,19x el 2026-08-27). Las secciones de ROI (3, 4 y 5) miden POLITICA y colapsan a **una fila por apuesta** -- una apuesta se hace una vez. La seccion 1 (Brier) se queda sobre todas las servidas a proposito: cada servida es una prediccion distinta a un precio distinto, la comparacion es pareada contra el mercado en la misma fila y el IC ya agrupa por evento.

ROI REALIZADO sobre muestra historica. NO es una promesa de ganancia.

## 1. Agregado: modelo vs mercado

`brier_diff = modelo - mercado`; NEGATIVO = el modelo gana. El veredicto lo fija el intervalo, no el punto estimado.

- `model_probability`: n=8160, eventos=1600, brier modelo=0.24116 vs mercado=0.23128, diff=+0.00988 IC95=[+0.00633, +0.01367] -> **mercado mejor**
- `calibrated_probability`: n=8160, eventos=1600, brier modelo=0.23398 vs mercado=0.23128, diff=+0.0027 IC95=[+0.00111, +0.0043] -> **mercado mejor**

## 2. Por (liga, mercado)

Atencion a las comparaciones multiples: con ~38 segmentos y alpha=0.05, un par de veredictos extremos son ruido esperado.

**AVISO: estos segmentos se sirvieron con la probabilidad CALIBRADA aplanada**, asi que su veredicto de abajo no puntua al modelo sino a una constante. Huella de un calibrador colapsado en produccion (`calibrator._keeps_resolution`).

| league | market | dias | filas | desde | hasta |
|---|---|---|---|---|---|
| wnba | totals | 34 | 412 | 2026-07-22 | 2026-08-27 |
| mlb | totals | 17 | 402 | 2026-07-28 | 2026-09-02 |
| wnba | spreads | 2 | 14 | 2026-08-29 | 2026-08-30 |

| league | market | n_rows | n_events | brier_model | brier_market | brier_diff | brier_diff_lo | brier_diff_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| mlb | totals | 1156 | 555 | 0.25028 | 0.24958 | 0.0007 | -0.00222 | 0.00388 | equivalente (IC cruza 0) |
| mlb | spreads | 1148 | 569 | 0.24294 | 0.24097 | 0.00197 | -0.00077 | 0.00472 | equivalente (IC cruza 0) |
| mlb | h2h | 1138 | 569 | 0.24152 | 0.24074 | 0.00078 | -0.00166 | 0.00323 | equivalente (IC cruza 0) |
| wnba | totals | 526 | 144 | 0.26031 | 0.24986 | 0.01045 | 0.00295 | 0.01824 | mercado mejor |
| wnba | spreads | 458 | 144 | 0.24894 | 0.24928 | -0.00034 | -0.00856 | 0.00711 | equivalente (IC cruza 0) |
| wnba | h2h | 288 | 144 | 0.18626 | 0.17997 | 0.00629 | 0.00088 | 0.01187 | mercado mejor |
| mls | h2h | 213 | 71 | 0.22763 | 0.22533 | 0.0023 | -0.00342 | 0.00789 | equivalente (IC cruza 0) |
| tennis_wta_cincinnati_open | h2h | 208 | 104 | 0.20453 | 0.19671 | 0.00781 | -0.00492 | 0.01988 | equivalente (IC cruza 0) |
| mls | spreads | 206 | 69 | 0.23762 | 0.23338 | 0.00424 | -0.00562 | 0.01406 | equivalente (IC cruza 0) |
| tennis_atp_cincinnati_open | h2h | 192 | 96 | 0.21796 | 0.23149 | -0.01354 | -0.02441 | -0.00241 | modelo MEJOR |
| tennis_wta_us_open | h2h | 182 | 91 | 0.15275 | 0.13986 | 0.0129 | 0.00147 | 0.02553 | mercado mejor |
| tennis_atp_us_open | h2h | 180 | 90 | 0.19486 | 0.18994 | 0.00491 | -0.00752 | 0.0176 | equivalente (IC cruza 0) |
| tennis_atp_canadian_open | h2h | 170 | 85 | 0.23066 | 0.21923 | 0.01143 | 0.00102 | 0.02173 | mercado mejor |
| tennis_wta_canadian_open | h2h | 166 | 83 | 0.19641 | 0.18156 | 0.01485 | 0.00457 | 0.02593 | mercado mejor |
| mls | totals | 160 | 71 | 0.24637 | 0.2474 | -0.00103 | -0.00676 | 0.00383 | equivalente (IC cruza 0) |
| brasileirao | h2h | 153 | 51 | 0.19972 | 0.20048 | -0.00076 | -0.00592 | 0.00453 | equivalente (IC cruza 0) |
| brasileirao | spreads | 148 | 49 | 0.24745 | 0.24276 | 0.0047 | -0.00746 | 0.0184 | equivalente (IC cruza 0) |
| chile | spreads | 126 | 36 | 0.25251 | 0.25163 | 0.00087 | -0.01313 | 0.01677 | equivalente (IC cruza 0) |
| chile | h2h | 108 | 36 | 0.20909 | 0.20634 | 0.00275 | -0.00382 | 0.01006 | equivalente (IC cruza 0) |
| brasileirao | totals | 104 | 51 | 0.25144 | 0.25915 | -0.00771 | -0.0154 | 0.0002 | equivalente (IC cruza 0) |
| ligamx | spreads | 94 | 28 | 0.24472 | 0.23438 | 0.01034 | -0.00525 | 0.02707 | equivalente (IC cruza 0) |
| ligamx | h2h | 84 | 28 | 0.1985 | 0.19464 | 0.00386 | -0.00318 | 0.01161 | equivalente (IC cruza 0) |
| ncaaf | totals | 78 | 15 | 0.26583 | 0.24995 | 0.01588 | -0.00911 | 0.04483 | equivalente (IC cruza 0) |
| chile | totals | 74 | 36 | 0.24303 | 0.24314 | -0.00011 | -0.00758 | 0.00704 | equivalente (IC cruza 0) |
| ncaaf | spreads | 66 | 15 | 0.262 | 0.24936 | 0.01264 | -0.0522 | 0.07174 | equivalente (IC cruza 0) |
| ligamx | totals | 58 | 28 | 0.26881 | 0.2637 | 0.00511 | -0.00315 | 0.01237 | equivalente (IC cruza 0) |
| laliga | spreads | 54 | 17 | 0.25299 | 0.25312 | -0.00013 | -0.01718 | 0.01662 | equivalente (IC cruza 0) |
| seriea | h2h | 54 | 18 | 0.17215 | 0.16628 | 0.00588 | -0.0032 | 0.01584 | equivalente (IC cruza 0) |
| laliga | h2h | 51 | 17 | 0.18339 | 0.18419 | -0.0008 | -0.00985 | 0.00697 | equivalente (IC cruza 0) |
| seriea | spreads | 50 | 17 | 0.24406 | 0.24362 | 0.00044 | -0.01839 | 0.02362 | equivalente (IC cruza 0) |
| tennis_wta_washington_open | h2h | 46 | 23 | 0.20484 | 0.20427 | 0.00056 | -0.02259 | 0.01863 | equivalente (IC cruza 0) |
| tennis_atp_washington_open | h2h | 46 | 23 | 0.23305 | 0.23324 | -0.0002 | -0.01577 | 0.01636 | equivalente (IC cruza 0) |
| epl | h2h | 42 | 14 | 0.17996 | 0.18448 | -0.00453 | -0.02132 | 0.01093 | equivalente (IC cruza 0) |
| laliga | totals | 40 | 17 | 0.25495 | 0.24858 | 0.00637 | -0.01633 | 0.03124 | equivalente (IC cruza 0) |
| seriea | totals | 38 | 18 | 0.2401 | 0.25024 | -0.01014 | -0.02545 | 0.00499 | equivalente (IC cruza 0) |
| epl | spreads | 36 | 12 | 0.23016 | 0.25621 | -0.02604 | -0.05189 | 0.00877 | equivalente (IC cruza 0) |
| tennis_wta_monterrey_open | h2h | 34 | 17 | 0.24747 | 0.24777 | -0.0003 | -0.0388 | 0.03501 | equivalente (IC cruza 0) |
| epl | totals | 32 | 14 | 0.25152 | 0.2391 | 0.01242 | -0.00081 | 0.02538 | equivalente (IC cruza 0) |
| ligue1 | h2h | 30 | 10 | 0.21161 | 0.21605 | -0.00443 | -0.01626 | 0.00675 | equivalente (IC cruza 0) |
| ncaaf | h2h | 30 | 15 | 0.16794 | 0.14727 | 0.02067 | 0.00305 | 0.04154 | mercado mejor |
| ligue1 | spreads | 24 | 9 | 0.22485 | 0.23771 | -0.01286 | -0.03282 | 0.01038 | equivalente (IC cruza 0) |
| ligue1 | totals | 20 | 10 | 0.25359 | 0.25934 | -0.00575 | -0.02229 | 0.00881 | equivalente (IC cruza 0) |
| tennis_atp_wimbledon | h2h | 12 | 6 | 0.14109 | 0.13316 | 0.00793 | -0.02832 | 0.0344 | equivalente (IC cruza 0) |
| tennis_wta_wimbledon | h2h | 12 | 6 | 0.21968 | 0.23157 | -0.0119 | -0.0404 | 0.00944 | equivalente (IC cruza 0) |
| bundesliga | h2h | 9 | 3 | 0.06695 | 0.07746 | -0.01052 | -0.02916 | 0.00209 | equivalente (IC cruza 0) |
| bundesliga | totals | 8 | 3 | 0.2309 | 0.22793 | 0.00297 | -0.0299 | 0.02049 | equivalente (IC cruza 0) |
| bundesliga | spreads | 8 | 3 | 0.22255 | 0.24336 | -0.02081 | -0.06225 | 0.00187 | equivalente (IC cruza 0) |

## 3. Escalera de `min_edge`: vale algo el edge declarado?

Si el edge tuviera informacion, `roi_flat` CRECERIA con el umbral.

### Suelo de probabilidad implicita = 0.00

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.0 | 1730 | 1115 | 0.43468 | -0.09134 | -0.14703 | -0.02485 | ROI negativo |
| 0.02 | 0.0 | 1291 | 895 | 0.41828 | -0.10002 | -0.17373 | -0.02304 | ROI negativo |
| 0.05 | 0.0 | 838 | 627 | 0.38663 | -0.13736 | -0.22444 | -0.04582 | ROI negativo |
| 0.08 | 0.0 | 550 | 433 | 0.34182 | -0.20143 | -0.31499 | -0.0701 | ROI negativo |
| 0.12 | 0.0 | 333 | 274 | 0.27628 | -0.28293 | -0.44021 | -0.13086 | ROI negativo |

### Suelo de probabilidad implicita = 0.35

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.35 | 1382 | 896 | 0.49638 | -0.03615 | -0.10036 | 0.02751 | indistinguible de 0 |
| 0.02 | 0.35 | 971 | 670 | 0.49537 | -0.02829 | -0.10449 | 0.0454 | indistinguible de 0 |
| 0.05 | 0.35 | 564 | 411 | 0.49645 | -0.01777 | -0.1207 | 0.07839 | indistinguible de 0 |
| 0.08 | 0.35 | 326 | 247 | 0.47853 | -0.05291 | -0.17743 | 0.06971 | indistinguible de 0 |
| 0.12 | 0.35 | 158 | 121 | 0.43038 | -0.13434 | -0.31427 | 0.05562 | indistinguible de 0 |

## 4. Cap de plausibilidad: esta cortando lo peor o picks buenos?

`risk.max_plausible_edge` descarta candidatos cuyo edge declarado es implausible. Es el control con MAS trabajo efectivo del sistema: en un run real el 63% de las filas descartadas llevan su flag, mas que el gate de prediccion. Un cap util corta lo que rinde PEOR.

AVISO: el techo se barre sobre la misma muestra que se evalua, asi que el mejor punto esta sesgado al alza. Sirve para VIGILAR que el cap sigue funcionando, no para optimizarlo.

| cap | n_pasan | roi_pasan | roi_pasan_lo | roi_pasan_hi | n_cortadas | roi_cortadas | roi_cortadas_lo | roi_cortadas_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 0.05 | 891 | -0.04704 | -0.11552 | 0.02617 | 837 | -0.13633 | -0.225 | -0.0369 | el cap corta lo peor |
| 0.075 | 1142 | -0.042 | -0.1075 | 0.02304 | 586 | -0.1844 | -0.30203 | -0.06551 | el cap corta lo peor |
| 0.1 | 1308 | -0.04276 | -0.11047 | 0.02426 | 420 | -0.23831 | -0.36831 | -0.10169 | el cap corta lo peor |
| 0.15 | 1475 | -0.05329 | -0.11664 | 0.00815 | 253 | -0.30599 | -0.47988 | -0.10661 | el cap corta lo peor |
| 0.2 | 1577 | -0.06727 | -0.13192 | -0.00597 | 151 | -0.33073 | -0.59926 | -0.06689 | el cap corta lo peor |
| 0.3 | 1658 | -0.08071 | -0.13904 | -0.0194 | 70 | -0.31729 | -0.74861 | 0.18435 | el cap corta lo peor |
| inf | 1728 | -0.09029 | -0.15358 | -0.02469 | 0 |  |  |  | sin cap |

## 5. Contraste directo de la seleccion

- ROI donde el modelo apuesta (edge>0): **-0.0903** (n=1728)
- ROI en el resto (edge<=0): **-0.0544** (n=6432)
- Delta = **-0.0358**, IC95 = [-0.1093, +0.0428]

Delta negativo con IC que excluye 0 significa que la regla de seleccion RESTA valor: el sistema apuesta el peor lado de cada mercado.
