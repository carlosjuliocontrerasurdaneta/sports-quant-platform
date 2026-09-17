# Modelo vs mercado y valor del edge

Generado: 2026-09-17 - filas servidas: 26399 - picks unicos: 10614 - eventos: 1912

Fuente: stream servido (`data/calibration/graded_*.csv`), todas las caras priceadas antes de cualquier filtro de stake. Intervalos al 95% por bootstrap agrupado por evento.

**Unidades.** El stream guarda una fila por dia de horizonte, asi que el mismo pick aparece varias veces (2,19x el 2026-08-27). Las secciones de ROI (3, 4 y 5) miden POLITICA y colapsan a **una fila por apuesta** -- una apuesta se hace una vez. La seccion 1 (Brier) se queda sobre todas las servidas a proposito: cada servida es una prediccion distinta a un precio distinto, la comparacion es pareada contra el mercado en la misma fila y el IC ya agrupa por evento.

ROI REALIZADO sobre muestra historica. NO es una promesa de ganancia.

## 1. Agregado: modelo vs mercado

`brier_diff = modelo - mercado`; NEGATIVO = el modelo gana. El veredicto lo fija el intervalo, no el punto estimado.

- `model_probability`: n=10340, eventos=1888, brier modelo=0.24346 vs mercado=0.23003, diff=+0.01343 IC95=[+0.00971, +0.01738] -> **mercado mejor**
- `calibrated_probability`: n=10340, eventos=1888, brier modelo=0.23402 vs mercado=0.23003, diff=+0.00398 IC95=[+0.00234, +0.00569] -> **mercado mejor**

## 2. Por (liga, mercado)

Atencion a las comparaciones multiples: con ~38 segmentos y alpha=0.05, un par de veredictos extremos son ruido esperado.

**AVISO: estos segmentos se sirvieron con la probabilidad CALIBRADA aplanada**, asi que su veredicto de abajo no puntua al modelo sino a una constante. Huella de un calibrador colapsado en produccion (`calibrator._keeps_resolution`).

| league | market | dias | filas | desde | hasta |
|---|---|---|---|---|---|
| mlb | totals | 21 | 492 | 2026-07-28 | 2026-09-13 |
| wnba | totals | 34 | 412 | 2026-07-22 | 2026-08-27 |
| wnba | spreads | 2 | 14 | 2026-08-29 | 2026-08-30 |

| league | market | n_rows | n_events | brier_model | brier_market | brier_diff | brier_diff_lo | brier_diff_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| mlb | totals | 1266 | 606 | 0.25044 | 0.24972 | 0.00072 | -0.0019 | 0.00352 | equivalente (IC cruza 0) |
| mlb | spreads | 1254 | 622 | 0.24156 | 0.23959 | 0.00197 | -0.00061 | 0.00454 | equivalente (IC cruza 0) |
| mlb | h2h | 1244 | 622 | 0.2414 | 0.24082 | 0.00058 | -0.00189 | 0.003 | equivalente (IC cruza 0) |
| wnba | totals | 526 | 144 | 0.26031 | 0.24986 | 0.01045 | 0.00295 | 0.01824 | mercado mejor |
| ncaaf | totals | 464 | 94 | 0.24963 | 0.24978 | -0.00015 | -0.00982 | 0.00839 | equivalente (IC cruza 0) |
| wnba | spreads | 458 | 144 | 0.24894 | 0.24928 | -0.00034 | -0.00856 | 0.00711 | equivalente (IC cruza 0) |
| ncaaf | spreads | 394 | 93 | 0.28433 | 0.25007 | 0.03426 | 0.00951 | 0.05928 | mercado mejor |
| mls | spreads | 296 | 95 | 0.23633 | 0.22733 | 0.009 | -0.0002 | 0.01779 | equivalente (IC cruza 0) |
| mls | h2h | 291 | 97 | 0.22539 | 0.22229 | 0.0031 | -0.0014 | 0.00774 | equivalente (IC cruza 0) |
| wnba | h2h | 288 | 144 | 0.18626 | 0.17997 | 0.00629 | 0.00088 | 0.01187 | mercado mejor |
| tennis_atp_us_open | h2h | 220 | 110 | 0.19539 | 0.18704 | 0.00835 | -0.00489 | 0.01982 | equivalente (IC cruza 0) |
| mls | totals | 218 | 97 | 0.24612 | 0.24479 | 0.00134 | -0.00337 | 0.00596 | equivalente (IC cruza 0) |
| tennis_wta_us_open | h2h | 216 | 108 | 0.15457 | 0.1424 | 0.01216 | 0.00046 | 0.0231 | mercado mejor |
| tennis_wta_cincinnati_open | h2h | 208 | 104 | 0.20453 | 0.19671 | 0.00781 | -0.00492 | 0.01988 | equivalente (IC cruza 0) |
| tennis_atp_cincinnati_open | h2h | 192 | 96 | 0.21796 | 0.23149 | -0.01354 | -0.02441 | -0.00241 | modelo MEJOR |
| brasileirao | h2h | 192 | 64 | 0.20012 | 0.20176 | -0.00163 | -0.00649 | 0.0032 | equivalente (IC cruza 0) |
| ncaaf | h2h | 188 | 94 | 0.13528 | 0.11628 | 0.01901 | 0.00636 | 0.03125 | mercado mejor |
| brasileirao | spreads | 186 | 62 | 0.24746 | 0.24156 | 0.00591 | -0.00614 | 0.0173 | equivalente (IC cruza 0) |
| tennis_atp_canadian_open | h2h | 170 | 85 | 0.23066 | 0.21923 | 0.01143 | 0.00102 | 0.02173 | mercado mejor |
| tennis_wta_canadian_open | h2h | 166 | 83 | 0.19641 | 0.18156 | 0.01485 | 0.00457 | 0.02593 | mercado mejor |
| chile | spreads | 166 | 46 | 0.24744 | 0.2478 | -0.00037 | -0.01273 | 0.01212 | equivalente (IC cruza 0) |
| chile | h2h | 138 | 46 | 0.20394 | 0.20217 | 0.00177 | -0.00383 | 0.00716 | equivalente (IC cruza 0) |
| brasileirao | totals | 130 | 64 | 0.25033 | 0.25829 | -0.00796 | -0.01474 | -0.0014 | modelo MEJOR |
| ligamx | spreads | 104 | 32 | 0.24447 | 0.23506 | 0.00941 | -0.008 | 0.02635 | equivalente (IC cruza 0) |
| chile | totals | 98 | 46 | 0.23966 | 0.24465 | -0.00499 | -0.0123 | 0.00219 | equivalente (IC cruza 0) |
| ligamx | h2h | 96 | 32 | 0.19912 | 0.19358 | 0.00553 | -0.0021 | 0.01344 | equivalente (IC cruza 0) |
| seriea | h2h | 90 | 30 | 0.19031 | 0.19065 | -0.00034 | -0.00775 | 0.00798 | equivalente (IC cruza 0) |
| seriea | spreads | 78 | 29 | 0.23527 | 0.2414 | -0.00613 | -0.02089 | 0.01104 | equivalente (IC cruza 0) |
| epl | h2h | 75 | 25 | 0.20714 | 0.20936 | -0.00222 | -0.013 | 0.00843 | equivalente (IC cruza 0) |
| laliga | h2h | 72 | 24 | 0.16936 | 0.16854 | 0.00081 | -0.00612 | 0.00688 | equivalente (IC cruza 0) |
| laliga | spreads | 70 | 24 | 0.2514 | 0.2514 | 1e-05 | -0.0155 | 0.01383 | equivalente (IC cruza 0) |
| epl | spreads | 66 | 22 | 0.22489 | 0.24736 | -0.02247 | -0.04032 | 0.00127 | equivalente (IC cruza 0) |
| ligamx | totals | 66 | 32 | 0.26877 | 0.26453 | 0.00424 | -0.00287 | 0.01133 | equivalente (IC cruza 0) |
| seriea | totals | 62 | 30 | 0.24311 | 0.2507 | -0.0076 | -0.02054 | 0.0044 | equivalente (IC cruza 0) |
| laliga | totals | 54 | 24 | 0.25273 | 0.23829 | 0.01444 | -0.00677 | 0.0351 | equivalente (IC cruza 0) |
| epl | totals | 54 | 25 | 0.24008 | 0.2332 | 0.00688 | -0.00571 | 0.0184 | equivalente (IC cruza 0) |
| nfl | spreads | 50 | 15 | 0.2591 | 0.2508 | 0.00831 | -0.00843 | 0.02643 | equivalente (IC cruza 0) |
| tennis_atp_washington_open | h2h | 46 | 23 | 0.23305 | 0.23324 | -0.0002 | -0.01577 | 0.01636 | equivalente (IC cruza 0) |
| tennis_wta_washington_open | h2h | 46 | 23 | 0.20484 | 0.20427 | 0.00056 | -0.02259 | 0.01863 | equivalente (IC cruza 0) |
| ligue1 | h2h | 45 | 15 | 0.22247 | 0.22248 | -1e-05 | -0.01004 | 0.00769 | equivalente (IC cruza 0) |
| nfl | totals | 42 | 15 | 0.2726 | 0.24931 | 0.02329 | 0.0002 | 0.04439 | mercado mejor |
| tennis_wta_monterrey_open | h2h | 34 | 17 | 0.24747 | 0.24777 | -0.0003 | -0.0388 | 0.03501 | equivalente (IC cruza 0) |
| ligue1 | spreads | 32 | 12 | 0.21703 | 0.23074 | -0.01372 | -0.03107 | 0.00457 | equivalente (IC cruza 0) |
| ligue1 | totals | 30 | 15 | 0.25364 | 0.25945 | -0.00581 | -0.0196 | 0.00585 | equivalente (IC cruza 0) |
| nfl | h2h | 30 | 15 | 0.21525 | 0.21483 | 0.00041 | -0.01756 | 0.01812 | equivalente (IC cruza 0) |
| bundesliga | spreads | 22 | 7 | 0.25925 | 0.24676 | 0.01249 | -0.04274 | 0.05531 | equivalente (IC cruza 0) |
| bundesliga | h2h | 21 | 7 | 0.13905 | 0.13832 | 0.00073 | -0.02285 | 0.02361 | equivalente (IC cruza 0) |
| bundesliga | totals | 16 | 7 | 0.2424 | 0.24476 | -0.00236 | -0.02052 | 0.01245 | equivalente (IC cruza 0) |
| tennis_wta_guadalajara_open | h2h | 16 | 8 | 0.23233 | 0.21459 | 0.01774 | -0.0351 | 0.06661 | equivalente (IC cruza 0) |
| tennis_atp_wimbledon | h2h | 12 | 6 | 0.14109 | 0.13316 | 0.00793 | -0.02832 | 0.0344 | equivalente (IC cruza 0) |
| tennis_wta_wimbledon | h2h | 12 | 6 | 0.21968 | 0.23157 | -0.0119 | -0.0404 | 0.00944 | equivalente (IC cruza 0) |
| ucl | h2h | 12 | 4 | 0.19398 | 0.19526 | -0.00128 | -0.01848 | 0.01335 | equivalente (IC cruza 0) |
| ucl | totals | 10 | 4 | 0.19318 | 0.18554 | 0.00764 | -0.01588 | 0.04144 | equivalente (IC cruza 0) |
| ucl | spreads | 8 | 4 | 0.21339 | 0.21164 | 0.00175 | -0.02522 | 0.02698 | equivalente (IC cruza 0) |

## 3. Escalera de `min_edge`: vale algo el edge declarado?

Si el edge tuviera informacion, `roi_flat` CRECERIA con el umbral.

### Suelo de probabilidad implicita = 0.00

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.0 | 2327 | 1351 | 0.42329 | -0.1147 | -0.17318 | -0.05778 | ROI negativo |
| 0.02 | 0.0 | 1783 | 1101 | 0.40494 | -0.1309 | -0.19797 | -0.06413 | ROI negativo |
| 0.05 | 0.0 | 1185 | 780 | 0.37384 | -0.16909 | -0.24568 | -0.08142 | ROI negativo |
| 0.08 | 0.0 | 817 | 560 | 0.33293 | -0.22334 | -0.33069 | -0.1142 | ROI negativo |
| 0.12 | 0.0 | 529 | 374 | 0.2741 | -0.30899 | -0.43115 | -0.18034 | ROI negativo |

### Suelo de probabilidad implicita = 0.35

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.35 | 1859 | 1104 | 0.48467 | -0.06249 | -0.11538 | -0.00637 | ROI negativo |
| 0.02 | 0.35 | 1356 | 850 | 0.47788 | -0.0676 | -0.13266 | 0.00212 | indistinguible de 0 |
| 0.05 | 0.35 | 816 | 534 | 0.47426 | -0.07014 | -0.16104 | 0.01778 | indistinguible de 0 |
| 0.08 | 0.35 | 506 | 341 | 0.45059 | -0.11636 | -0.22646 | -0.01202 | ROI negativo |
| 0.12 | 0.35 | 274 | 187 | 0.40876 | -0.18838 | -0.34128 | -0.04604 | ROI negativo |

## 4. Cap de plausibilidad: esta cortando lo peor o picks buenos?

`risk.max_plausible_edge` descarta candidatos cuyo edge declarado es implausible. Es el control con MAS trabajo efectivo del sistema: en un run real el 63% de las filas descartadas llevan su flag, mas que el gate de prediccion. Un cap util corta lo que rinde PEOR.

AVISO: el techo se barre sobre la misma muestra que se evalua, asi que el mejor punto esta sesgado al alza. Sirve para VIGILAR que el cap sigue funcionando, no para optimizarlo.

| cap | n_pasan | roi_pasan | roi_pasan_lo | roi_pasan_hi | n_cortadas | roi_cortadas | roi_cortadas_lo | roi_cortadas_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 0.05 | 1140 | -0.05911 | -0.12394 | 0.00297 | 1184 | -0.16839 | -0.24936 | -0.0848 | el cap corta lo peor |
| 0.075 | 1458 | -0.05756 | -0.11296 | 0.00022 | 866 | -0.21111 | -0.30726 | -0.11013 | el cap corta lo peor |
| 0.1 | 1681 | -0.05198 | -0.11205 | 0.00361 | 643 | -0.27897 | -0.39706 | -0.16682 | el cap corta lo peor |
| 0.15 | 1911 | -0.06954 | -0.12777 | -0.01862 | 413 | -0.32409 | -0.46867 | -0.16503 | el cap corta lo peor |
| 0.2 | 2052 | -0.08175 | -0.13819 | -0.02869 | 272 | -0.36393 | -0.53563 | -0.17071 | el cap corta lo peor |
| 0.3 | 2184 | -0.0938 | -0.14708 | -0.04058 | 140 | -0.442 | -0.71453 | -0.10526 | el cap corta lo peor |
| inf | 2324 | -0.11478 | -0.16986 | -0.05875 | 0 |  |  |  | sin cap |

## 5. Contraste directo de la seleccion

- ROI donde el modelo apuesta (edge>0): **-0.1148** (n=2324)
- ROI en el resto (edge<=0): **-0.0502** (n=8016)
- Delta = **-0.0645**, IC95 = [-0.1322, +0.0020]

Delta negativo con IC que excluye 0 significa que la regla de seleccion RESTA valor: el sistema apuesta el peor lado de cada mercado.
