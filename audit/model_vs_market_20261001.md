# Modelo vs mercado y valor del edge

Generado: 2026-10-01 - filas servidas: 35835 - picks unicos: 14273 - eventos: 2374

Fuente: stream servido (`data/calibration/graded_*.csv`), todas las caras priceadas antes de cualquier filtro de stake. Intervalos al 95% por bootstrap agrupado por evento.

**Unidades.** El stream guarda una fila por dia de horizonte, asi que el mismo pick aparece varias veces (2,19x el 2026-08-27). Las secciones de ROI (3, 4 y 5) miden POLITICA y colapsan a **una fila por apuesta** -- una apuesta se hace una vez. La seccion 1 (Brier) se queda sobre todas las servidas a proposito: cada servida es una prediccion distinta a un precio distinto, la comparacion es pareada contra el mercado en la misma fila y el IC ya agrupa por evento.

ROI REALIZADO sobre muestra historica. NO es una promesa de ganancia.

## 1. Agregado: modelo vs mercado

`brier_diff = modelo - mercado`; NEGATIVO = el modelo gana. El veredicto lo fija el intervalo, no el punto estimado.

- `model_probability`: n=13920, eventos=2347, brier modelo=0.24488 vs mercado=0.2308, diff=+0.01409 IC95=[+0.0107, +0.01775] -> **mercado mejor**
- `calibrated_probability`: n=13920, eventos=2347, brier modelo=0.23457 vs mercado=0.2308, diff=+0.00377 IC95=[+0.00223, +0.00546] -> **mercado mejor**

## 2. Por (liga, mercado)

Atencion a las comparaciones multiples: con ~38 segmentos y alpha=0.05, un par de veredictos extremos son ruido esperado.

**AVISO: estos segmentos se sirvieron con la probabilidad CALIBRADA aplanada**, asi que su veredicto de abajo no puntua al modelo sino a una constante. Huella de un calibrador colapsado en produccion (`calibrator._keeps_resolution`).

| league | market | dias | filas | desde | hasta |
|---|---|---|---|---|---|
| mlb | totals | 25 | 564 | 2026-07-28 | 2026-09-19 |
| wnba | totals | 34 | 412 | 2026-07-22 | 2026-08-27 |
| wnba | spreads | 11 | 114 | 2026-08-29 | 2026-09-29 |
| bundesliga | spreads | 3 | 18 | 2026-09-14 | 2026-09-18 |
| seriea | spreads | 1 | 10 | 2026-09-19 | 2026-09-19 |

| league | market | n_rows | n_events | brier_model | brier_market | brier_diff | brier_diff_lo | brier_diff_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| mlb | totals | 1476 | 711 | 0.25025 | 0.2496 | 0.00065 | -0.00178 | 0.00329 | equivalente (IC cruza 0) |
| mlb | spreads | 1466 | 728 | 0.24201 | 0.24017 | 0.00184 | -0.00045 | 0.00424 | equivalente (IC cruza 0) |
| mlb | h2h | 1456 | 728 | 0.24067 | 0.24008 | 0.00059 | -0.00146 | 0.0027 | equivalente (IC cruza 0) |
| ncaaf | totals | 1090 | 205 | 0.25069 | 0.24969 | 0.001 | -0.00609 | 0.00812 | equivalente (IC cruza 0) |
| ncaaf | spreads | 954 | 204 | 0.26622 | 0.24972 | 0.0165 | 0.0015 | 0.03079 | mercado mejor |
| wnba | totals | 638 | 182 | 0.25674 | 0.24994 | 0.0068 | 0.00021 | 0.01409 | mercado mejor |
| wnba | spreads | 570 | 182 | 0.24999 | 0.24942 | 0.00058 | -0.00589 | 0.00673 | equivalente (IC cruza 0) |
| ncaaf | h2h | 410 | 205 | 0.14155 | 0.12184 | 0.01971 | 0.01107 | 0.028 | mercado mejor |
| wnba | h2h | 364 | 182 | 0.18426 | 0.17874 | 0.00552 | 0.00027 | 0.01068 | mercado mejor |
| mls | spreads | 364 | 116 | 0.24578 | 0.24059 | 0.00519 | -0.00579 | 0.01606 | equivalente (IC cruza 0) |
| mls | h2h | 354 | 118 | 0.22033 | 0.2173 | 0.00304 | -0.00172 | 0.00749 | equivalente (IC cruza 0) |
| mls | totals | 272 | 118 | 0.24322 | 0.242 | 0.00122 | -0.00285 | 0.0055 | equivalente (IC cruza 0) |
| tennis_atp_us_open | h2h | 220 | 110 | 0.19539 | 0.18704 | 0.00835 | -0.00489 | 0.01982 | equivalente (IC cruza 0) |
| brasileirao | h2h | 219 | 73 | 0.19595 | 0.19739 | -0.00144 | -0.00594 | 0.00304 | equivalente (IC cruza 0) |
| tennis_wta_us_open | h2h | 216 | 108 | 0.15457 | 0.1424 | 0.01216 | 0.00046 | 0.0231 | mercado mejor |
| tennis_wta_cincinnati_open | h2h | 208 | 104 | 0.20453 | 0.19671 | 0.00781 | -0.00492 | 0.01988 | equivalente (IC cruza 0) |
| brasileirao | spreads | 206 | 71 | 0.2472 | 0.24222 | 0.00498 | -0.00566 | 0.01653 | equivalente (IC cruza 0) |
| nfl | totals | 200 | 48 | 0.26376 | 0.24991 | 0.01385 | -0.00349 | 0.03196 | equivalente (IC cruza 0) |
| nfl | spreads | 200 | 48 | 0.25023 | 0.24976 | 0.00047 | -0.0114 | 0.01197 | equivalente (IC cruza 0) |
| tennis_atp_cincinnati_open | h2h | 192 | 96 | 0.21796 | 0.23149 | -0.01354 | -0.02441 | -0.00241 | modelo MEJOR |
| chile | spreads | 170 | 47 | 0.24864 | 0.24753 | 0.00111 | -0.01034 | 0.01419 | equivalente (IC cruza 0) |
| tennis_atp_canadian_open | h2h | 170 | 85 | 0.23066 | 0.21923 | 0.01143 | 0.00102 | 0.02173 | mercado mejor |
| tennis_wta_canadian_open | h2h | 166 | 83 | 0.19641 | 0.18156 | 0.01485 | 0.00457 | 0.02593 | mercado mejor |
| brasileirao | totals | 148 | 73 | 0.2508 | 0.25939 | -0.00859 | -0.01467 | -0.0024 | modelo MEJOR |
| chile | h2h | 141 | 47 | 0.20366 | 0.20133 | 0.00233 | -0.00335 | 0.00828 | equivalente (IC cruza 0) |
| ligamx | h2h | 129 | 43 | 0.21145 | 0.20329 | 0.00816 | 0.00154 | 0.01499 | mercado mejor |
| ligamx | spreads | 122 | 39 | 0.24793 | 0.23597 | 0.01196 | -0.00297 | 0.02809 | equivalente (IC cruza 0) |
| seriea | h2h | 120 | 40 | 0.19227 | 0.19216 | 0.00011 | -0.00607 | 0.00691 | equivalente (IC cruza 0) |
| seriea | spreads | 104 | 39 | 0.23858 | 0.24354 | -0.00496 | -0.0193 | 0.00932 | equivalente (IC cruza 0) |
| chile | totals | 100 | 47 | 0.24076 | 0.24545 | -0.00469 | -0.01157 | 0.00267 | equivalente (IC cruza 0) |
| laliga | h2h | 96 | 32 | 0.16974 | 0.16962 | 0.00012 | -0.00627 | 0.0067 | equivalente (IC cruza 0) |
| epl | h2h | 96 | 32 | 0.20025 | 0.2067 | -0.00646 | -0.01793 | 0.00402 | equivalente (IC cruza 0) |
| nfl | h2h | 96 | 48 | 0.22864 | 0.23482 | -0.00618 | -0.01888 | 0.0061 | equivalente (IC cruza 0) |
| ligamx | totals | 92 | 43 | 0.25182 | 0.25307 | -0.00125 | -0.00861 | 0.00546 | equivalente (IC cruza 0) |
| laliga | spreads | 88 | 32 | 0.24867 | 0.24977 | -0.00109 | -0.01331 | 0.01164 | equivalente (IC cruza 0) |
| seriea | totals | 84 | 40 | 0.24256 | 0.24874 | -0.00618 | -0.01695 | 0.00438 | equivalente (IC cruza 0) |
| epl | spreads | 84 | 29 | 0.2224 | 0.24453 | -0.02213 | -0.03815 | -0.00524 | modelo MEJOR |
| epl | totals | 74 | 32 | 0.23796 | 0.23339 | 0.00457 | -0.00571 | 0.0158 | equivalente (IC cruza 0) |
| laliga | totals | 72 | 32 | 0.24601 | 0.23229 | 0.01372 | -0.0014 | 0.03018 | equivalente (IC cruza 0) |
| ligue1 | h2h | 54 | 18 | 0.21418 | 0.21145 | 0.00273 | -0.00618 | 0.00984 | equivalente (IC cruza 0) |
| tennis_wta_guadalajara_open | h2h | 50 | 25 | 0.20963 | 0.17729 | 0.03234 | 0.01151 | 0.05221 | mercado mejor |
| tennis_atp_washington_open | h2h | 46 | 23 | 0.23305 | 0.23324 | -0.0002 | -0.01577 | 0.01636 | equivalente (IC cruza 0) |
| tennis_wta_washington_open | h2h | 46 | 23 | 0.20484 | 0.20427 | 0.00056 | -0.02259 | 0.01863 | equivalente (IC cruza 0) |
| tennis_wta_singapore_open | h2h | 40 | 20 | 0.19623 | 0.17523 | 0.021 | 0.00051 | 0.04036 | mercado mejor |
| tennis_wta_china_open | h2h | 40 | 20 | 0.20214 | 0.20339 | -0.00125 | -0.03239 | 0.02528 | equivalente (IC cruza 0) |
| ligue1 | spreads | 38 | 15 | 0.21922 | 0.23062 | -0.0114 | -0.02823 | 0.00509 | equivalente (IC cruza 0) |
| ligue1 | totals | 36 | 18 | 0.24697 | 0.25364 | -0.00667 | -0.01907 | 0.0042 | equivalente (IC cruza 0) |
| tennis_wta_monterrey_open | h2h | 34 | 17 | 0.24747 | 0.24777 | -0.0003 | -0.0388 | 0.03501 | equivalente (IC cruza 0) |
| bundesliga | h2h | 30 | 10 | 0.15698 | 0.16038 | -0.0034 | -0.0219 | 0.01608 | equivalente (IC cruza 0) |
| uwcl | spreads | 28 | 7 | 0.27678 | 0.2482 | 0.02859 | -0.06434 | 0.12245 | equivalente (IC cruza 0) |
| bundesliga | spreads | 28 | 9 | 0.24868 | 0.24954 | -0.00086 | -0.04857 | 0.04441 | equivalente (IC cruza 0) |
| tennis_atp_japan_open | h2h | 28 | 14 | 0.31064 | 0.31121 | -0.00057 | -0.02985 | 0.02397 | equivalente (IC cruza 0) |
| tennis_atp_china_open | h2h | 24 | 12 | 0.22437 | 0.20156 | 0.0228 | 0.00781 | 0.03616 | mercado mejor |
| bundesliga | totals | 24 | 10 | 0.23646 | 0.24142 | -0.00496 | -0.01644 | 0.00756 | equivalente (IC cruza 0) |
| uwcl | h2h | 21 | 7 | 0.20772 | 0.2044 | 0.00332 | -0.02034 | 0.02649 | equivalente (IC cruza 0) |
| nhl | totals | 20 | 8 | 0.23988 | 0.23994 | -7e-05 | -0.02035 | 0.01985 | equivalente (IC cruza 0) |
| nhl | spreads | 18 | 8 | 0.18679 | 0.20385 | -0.01706 | -0.06133 | 0.02311 | equivalente (IC cruza 0) |
| uwcl | totals | 18 | 7 | 0.26548 | 0.22969 | 0.03579 | -0.00433 | 0.07154 | equivalente (IC cruza 0) |
| nhl | h2h | 16 | 8 | 0.25916 | 0.26476 | -0.00561 | -0.05031 | 0.04754 | equivalente (IC cruza 0) |
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
| 0.0 | 0.0 | 3371 | 1719 | 0.43006 | -0.10548 | -0.15491 | -0.05115 | ROI negativo |
| 0.02 | 0.0 | 2626 | 1421 | 0.41457 | -0.12135 | -0.17653 | -0.06295 | ROI negativo |
| 0.05 | 0.0 | 1791 | 1026 | 0.38892 | -0.15357 | -0.22068 | -0.083 | ROI negativo |
| 0.08 | 0.0 | 1271 | 761 | 0.35697 | -0.19452 | -0.27181 | -0.11382 | ROI negativo |
| 0.12 | 0.0 | 853 | 531 | 0.31338 | -0.2572 | -0.35624 | -0.16261 | ROI negativo |

### Suelo de probabilidad implicita = 0.35

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.35 | 2714 | 1427 | 0.48967 | -0.05435 | -0.10122 | -0.00561 | ROI negativo |
| 0.02 | 0.35 | 2019 | 1121 | 0.48685 | -0.05466 | -0.10835 | 0.0007 | indistinguible de 0 |
| 0.05 | 0.35 | 1264 | 726 | 0.48968 | -0.04612 | -0.11756 | 0.02777 | indistinguible de 0 |
| 0.08 | 0.35 | 822 | 490 | 0.47561 | -0.07388 | -0.15559 | 0.0173 | indistinguible de 0 |
| 0.12 | 0.35 | 475 | 286 | 0.46203 | -0.09584 | -0.21936 | 0.02833 | indistinguible de 0 |

## 4. Cap de plausibilidad: esta cortando lo peor o picks buenos?

`risk.max_plausible_edge` descarta candidatos cuyo edge declarado es implausible. Es el control con MAS trabajo efectivo del sistema: en un run real el 63% de las filas descartadas llevan su flag, mas que el gate de prediccion. Un cap util corta lo que rinde PEOR.

AVISO: el techo se barre sobre la misma muestra que se evalua, asi que el mejor punto esta sesgado al alza. Sirve para VIGILAR que el cap sigue funcionando, no para optimizarlo.

| cap | n_pasan | roi_pasan | roi_pasan_lo | roi_pasan_hi | n_cortadas | roi_cortadas | roi_cortadas_lo | roi_cortadas_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 0.05 | 1579 | -0.05098 | -0.1056 | 0.00656 | 1789 | -0.15366 | -0.22227 | -0.08032 | el cap corta lo peor |
| 0.075 | 2022 | -0.05396 | -0.10585 | 8e-05 | 1346 | -0.18298 | -0.25936 | -0.10043 | el cap corta lo peor |
| 0.1 | 2338 | -0.04489 | -0.09506 | 0.00366 | 1030 | -0.24316 | -0.3336 | -0.15644 | el cap corta lo peor |
| 0.15 | 2706 | -0.063 | -0.10856 | -0.01186 | 662 | -0.27934 | -0.39792 | -0.15668 | el cap corta lo peor |
| 0.2 | 2918 | -0.07326 | -0.12089 | -0.02208 | 450 | -0.31472 | -0.46246 | -0.16248 | el cap corta lo peor |
| 0.3 | 3135 | -0.07758 | -0.12753 | -0.02822 | 233 | -0.48157 | -0.66651 | -0.26854 | el cap corta lo peor |
| inf | 3368 | -0.10552 | -0.15383 | -0.05795 | 0 |  |  |  | sin cap |

## 5. Contraste directo de la seleccion

- ROI donde el modelo apuesta (edge>0): **-0.1055** (n=3368)
- ROI en el resto (edge<=0): **-0.0519** (n=10564)
- Delta = **-0.0536**, IC95 = [-0.1127, +0.0097]

Delta negativo con IC que excluye 0 significa que la regla de seleccion RESTA valor: el sistema apuesta el peor lado de cada mercado.
