# Modelo vs mercado y valor del edge

Generado: 2026-11-01 - filas servidas: 68866 - picks unicos: 24423 - eventos: 3691

Fuente: stream servido (`data/calibration/graded_*.csv`), todas las caras priceadas antes de cualquier filtro de stake. Intervalos al 95% por bootstrap agrupado por evento.

**Unidades.** El stream guarda una fila por dia de horizonte, asi que el mismo pick aparece varias veces (2,19x el 2026-08-27). Las secciones de ROI (3, 4 y 5) miden POLITICA y colapsan a **una fila por apuesta** -- una apuesta se hace una vez. Las secciones 1 y 2 (Brier) tambien colapsan a **una fila por pick** (la primera servida) antes de puntuar y antes del bootstrap (`score_model_vs_market`, KI-026(b), desde el 2026-09-04): sobre el stream inflado el estimador puntual salia sesgado. El IC agrupa por evento.

ROI REALIZADO sobre muestra historica. NO es una promesa de ganancia.

## 1. Agregado: modelo vs mercado

`brier_diff = modelo - mercado`; NEGATIVO = el modelo gana. El veredicto lo fija el intervalo, no el punto estimado.

- `model_probability`: n=23747, eventos=3653, brier modelo=0.24489 vs mercado=0.23229, diff=+0.01259 IC95=[+0.00978, +0.01535] -> **mercado mejor**
- `calibrated_probability`: n=23747, eventos=3653, brier modelo=0.23547 vs mercado=0.23229, diff=+0.00317 IC95=[+0.00184, +0.0045] -> **mercado mejor**

## 2. Por (liga, mercado)

Atencion a las comparaciones multiples: con ~38 segmentos y alpha=0.05, un par de veredictos extremos son ruido esperado.

**AVISO: estos segmentos se sirvieron con la probabilidad CALIBRADA aplanada**, asi que su veredicto de abajo no puntua al modelo sino a una constante. Huella de un calibrador colapsado en produccion (`calibrator._keeps_resolution`).

| league | market | dias | filas | desde | hasta |
|---|---|---|---|---|---|
| mlb | totals | 25 | 564 | 2026-07-28 | 2026-09-19 |
| wnba | totals | 34 | 412 | 2026-07-22 | 2026-08-27 |
| wnba | spreads | 12 | 122 | 2026-08-29 | 2026-10-01 |
| laliga | totals | 3 | 42 | 2026-10-06 | 2026-10-09 |
| bundesliga | spreads | 3 | 18 | 2026-09-14 | 2026-09-18 |
| seriea | spreads | 1 | 10 | 2026-09-19 | 2026-09-19 |

| league | market | n_rows | n_events | brier_model | brier_market | brier_diff | brier_diff_lo | brier_diff_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| ncaaf | totals | 2622 | 490 | 0.25488 | 0.24974 | 0.00514 | -0.00018 | 0.01071 | equivalente (IC cruza 0) |
| ncaaf | spreads | 2440 | 489 | 0.25518 | 0.24961 | 0.00557 | -0.00203 | 0.01299 | equivalente (IC cruza 0) |
| mlb | totals | 1518 | 732 | 0.25029 | 0.24941 | 0.00088 | -0.00162 | 0.00335 | equivalente (IC cruza 0) |
| mlb | spreads | 1512 | 750 | 0.24135 | 0.23961 | 0.00174 | -0.00061 | 0.00415 | equivalente (IC cruza 0) |
| mlb | h2h | 1500 | 750 | 0.24048 | 0.24014 | 0.00034 | -0.00162 | 0.00246 | equivalente (IC cruza 0) |
| ncaaf | h2h | 980 | 490 | 0.1761 | 0.16971 | 0.00639 | 0.00019 | 0.01248 | mercado mejor |
| wnba | totals | 686 | 197 | 0.25915 | 0.24992 | 0.00923 | 0.00092 | 0.01678 | mercado mejor |
| wnba | spreads | 612 | 197 | 0.24933 | 0.24957 | -0.00024 | -0.00659 | 0.00562 | equivalente (IC cruza 0) |
| mls | h2h | 612 | 204 | 0.21412 | 0.21114 | 0.00297 | -0.00093 | 0.00667 | equivalente (IC cruza 0) |
| mls | spreads | 578 | 199 | 0.24305 | 0.23791 | 0.00514 | -0.00282 | 0.01331 | equivalente (IC cruza 0) |
| nfl | totals | 502 | 108 | 0.25961 | 0.25041 | 0.0092 | -0.00153 | 0.02037 | equivalente (IC cruza 0) |
| nhl | totals | 468 | 219 | 0.25223 | 0.24902 | 0.00321 | -0.00162 | 0.00793 | equivalente (IC cruza 0) |
| nfl | spreads | 464 | 108 | 0.25022 | 0.25039 | -0.00017 | -0.00961 | 0.00933 | equivalente (IC cruza 0) |
| nhl | spreads | 454 | 219 | 0.22951 | 0.22834 | 0.00118 | -0.00256 | 0.00475 | equivalente (IC cruza 0) |
| mls | totals | 452 | 204 | 0.24205 | 0.24095 | 0.0011 | -0.00251 | 0.00482 | equivalente (IC cruza 0) |
| nhl | h2h | 438 | 219 | 0.2321 | 0.23157 | 0.00053 | -0.00279 | 0.00392 | equivalente (IC cruza 0) |
| wnba | h2h | 394 | 197 | 0.18693 | 0.18283 | 0.0041 | -0.00099 | 0.00906 | equivalente (IC cruza 0) |
| brasileirao | h2h | 375 | 125 | 0.18712 | 0.18715 | -3e-05 | -0.00316 | 0.00345 | equivalente (IC cruza 0) |
| brasileirao | spreads | 324 | 119 | 0.24779 | 0.24319 | 0.00459 | -0.00514 | 0.01512 | equivalente (IC cruza 0) |
| nba | totals | 268 | 88 | 0.24399 | 0.24982 | -0.00584 | -0.0173 | 0.00544 | equivalente (IC cruza 0) |
| ligamx | h2h | 261 | 87 | 0.22247 | 0.21637 | 0.00609 | 0.00115 | 0.01088 | mercado mejor |
| brasileirao | totals | 256 | 125 | 0.24641 | 0.25212 | -0.0057 | -0.01018 | -0.00111 | modelo MEJOR |
| seriea | h2h | 252 | 84 | 0.17815 | 0.17843 | -0.00028 | -0.00489 | 0.00421 | equivalente (IC cruza 0) |
| nba | spreads | 234 | 88 | 0.24822 | 0.24881 | -0.00058 | -0.01188 | 0.01232 | equivalente (IC cruza 0) |
| ligamx | spreads | 222 | 78 | 0.24945 | 0.2385 | 0.01095 | 0.00022 | 0.0217 | mercado mejor |
| seriea | spreads | 220 | 78 | 0.24212 | 0.24483 | -0.00271 | -0.01218 | 0.00789 | equivalente (IC cruza 0) |
| tennis_atp_us_open | h2h | 220 | 110 | 0.19539 | 0.18704 | 0.00835 | -0.00489 | 0.01982 | equivalente (IC cruza 0) |
| tennis_wta_us_open | h2h | 216 | 108 | 0.15457 | 0.1424 | 0.01216 | 0.00046 | 0.0231 | mercado mejor |
| nfl | h2h | 214 | 107 | 0.22945 | 0.23689 | -0.00744 | -0.01676 | 0.00198 | equivalente (IC cruza 0) |
| tennis_wta_cincinnati_open | h2h | 208 | 104 | 0.20453 | 0.19671 | 0.00781 | -0.00492 | 0.01988 | equivalente (IC cruza 0) |
| chile | spreads | 202 | 61 | 0.24963 | 0.2437 | 0.00593 | -0.00405 | 0.01515 | equivalente (IC cruza 0) |
| chile | h2h | 201 | 67 | 0.20487 | 0.20391 | 0.00095 | -0.00395 | 0.00598 | equivalente (IC cruza 0) |
| tennis_atp_cincinnati_open | h2h | 192 | 96 | 0.21796 | 0.23149 | -0.01354 | -0.02441 | -0.00241 | modelo MEJOR |
| ligamx | totals | 188 | 87 | 0.25253 | 0.24994 | 0.00259 | -0.00235 | 0.00801 | equivalente (IC cruza 0) |
| epl | h2h | 186 | 62 | 0.19769 | 0.19775 | -6e-05 | -0.00696 | 0.00649 | equivalente (IC cruza 0) |
| seriea | totals | 180 | 84 | 0.24286 | 0.24501 | -0.00215 | -0.00995 | 0.00548 | equivalente (IC cruza 0) |
| laliga | h2h | 177 | 59 | 0.16918 | 0.16893 | 0.00025 | -0.00443 | 0.00465 | equivalente (IC cruza 0) |
| nba | h2h | 176 | 88 | 0.20341 | 0.19449 | 0.00892 | -0.00051 | 0.01775 | equivalente (IC cruza 0) |
| tennis_atp_canadian_open | h2h | 170 | 85 | 0.23066 | 0.21923 | 0.01143 | 0.00102 | 0.02173 | mercado mejor |
| tennis_wta_canadian_open | h2h | 166 | 83 | 0.19641 | 0.18156 | 0.01485 | 0.00457 | 0.02593 | mercado mejor |
| tennis_atp_shanghai_masters | h2h | 166 | 83 | 0.19908 | 0.19796 | 0.00112 | -0.00855 | 0.01118 | equivalente (IC cruza 0) |
| epl | spreads | 166 | 55 | 0.24491 | 0.24831 | -0.0034 | -0.01637 | 0.01132 | equivalente (IC cruza 0) |
| chile | totals | 142 | 67 | 0.25069 | 0.25298 | -0.00229 | -0.00795 | 0.00395 | equivalente (IC cruza 0) |
| epl | totals | 142 | 62 | 0.24434 | 0.23942 | 0.00492 | -0.00138 | 0.01092 | equivalente (IC cruza 0) |
| laliga | totals | 134 | 59 | 0.23753 | 0.23471 | 0.00281 | -0.01115 | 0.01657 | equivalente (IC cruza 0) |
| ligue1 | h2h | 126 | 42 | 0.18589 | 0.18507 | 0.00082 | -0.00432 | 0.00573 | equivalente (IC cruza 0) |
| laliga | spreads | 126 | 47 | 0.25424 | 0.25159 | 0.00265 | -0.00973 | 0.01581 | equivalente (IC cruza 0) |
| ligue1 | spreads | 102 | 37 | 0.23679 | 0.23515 | 0.00164 | -0.01194 | 0.01565 | equivalente (IC cruza 0) |
| bundesliga | h2h | 96 | 32 | 0.21004 | 0.21225 | -0.00221 | -0.01131 | 0.00709 | equivalente (IC cruza 0) |
| bundesliga | spreads | 90 | 31 | 0.25133 | 0.24685 | 0.00448 | -0.01501 | 0.02443 | equivalente (IC cruza 0) |
| tennis_wta_china_open | h2h | 90 | 45 | 0.21664 | 0.22634 | -0.00971 | -0.03073 | 0.00853 | equivalente (IC cruza 0) |
| ligue1 | totals | 90 | 42 | 0.24478 | 0.24107 | 0.00371 | -0.00466 | 0.01145 | equivalente (IC cruza 0) |
| tennis_wta_wuhan_open | h2h | 74 | 37 | 0.29229 | 0.28925 | 0.00305 | -0.01586 | 0.02124 | equivalente (IC cruza 0) |
| bundesliga | totals | 70 | 32 | 0.23255 | 0.23235 | 0.0002 | -0.00864 | 0.0096 | equivalente (IC cruza 0) |
| tennis_atp_japan_open | h2h | 58 | 29 | 0.25323 | 0.24081 | 0.01242 | -0.00448 | 0.02796 | equivalente (IC cruza 0) |
| ucl | h2h | 57 | 19 | 0.1802 | 0.1816 | -0.0014 | -0.01508 | 0.01156 | equivalente (IC cruza 0) |
| ucl | spreads | 52 | 18 | 0.23984 | 0.23706 | 0.00278 | -0.02673 | 0.03777 | equivalente (IC cruza 0) |
| tennis_wta_ningbo_open | h2h | 52 | 26 | 0.17823 | 0.16821 | 0.01002 | -0.00526 | 0.02348 | equivalente (IC cruza 0) |
| tennis_wta_guadalajara_open | h2h | 50 | 25 | 0.20963 | 0.17729 | 0.03234 | 0.01151 | 0.05221 | mercado mejor |
| ucl | totals | 50 | 19 | 0.23057 | 0.22373 | 0.00684 | -0.00787 | 0.02181 | equivalente (IC cruza 0) |
| uwcl | spreads | 50 | 12 | 0.26825 | 0.24985 | 0.0184 | -0.04405 | 0.08334 | equivalente (IC cruza 0) |
| tennis_wta_pan_pacific_open | h2h | 46 | 23 | 0.24953 | 0.25464 | -0.00511 | -0.02117 | 0.00902 | equivalente (IC cruza 0) |
| tennis_wta_washington_open | h2h | 46 | 23 | 0.20484 | 0.20427 | 0.00056 | -0.02259 | 0.01863 | equivalente (IC cruza 0) |
| tennis_atp_washington_open | h2h | 46 | 23 | 0.23305 | 0.23324 | -0.0002 | -0.01577 | 0.01636 | equivalente (IC cruza 0) |
| tennis_wta_singapore_open | h2h | 40 | 20 | 0.19623 | 0.17523 | 0.021 | 0.00051 | 0.04036 | mercado mejor |
| tennis_atp_vienna_open | h2h | 40 | 20 | 0.20666 | 0.21987 | -0.01321 | -0.03693 | 0.00819 | equivalente (IC cruza 0) |
| tennis_atp_swiss_indoors | h2h | 38 | 19 | 0.16631 | 0.15622 | 0.0101 | -0.00503 | 0.0237 | equivalente (IC cruza 0) |
| uwcl | h2h | 36 | 12 | 0.20755 | 0.2036 | 0.00395 | -0.00959 | 0.01767 | equivalente (IC cruza 0) |
| tennis_wta_monterrey_open | h2h | 34 | 17 | 0.24747 | 0.24777 | -0.0003 | -0.0388 | 0.03501 | equivalente (IC cruza 0) |
| uwcl | totals | 34 | 12 | 0.2742 | 0.26357 | 0.01063 | -0.01419 | 0.04201 | equivalente (IC cruza 0) |
| tennis_atp_china_open | h2h | 34 | 17 | 0.20724 | 0.1889 | 0.01833 | 0.007 | 0.02997 | mercado mejor |
| tennis_wta_wimbledon | h2h | 12 | 6 | 0.21968 | 0.23157 | -0.0119 | -0.0404 | 0.00944 | equivalente (IC cruza 0) |
| tennis_atp_wimbledon | h2h | 12 | 6 | 0.14109 | 0.13316 | 0.00793 | -0.02832 | 0.0344 | equivalente (IC cruza 0) |
| tennis_atp_paris_masters | h2h | 6 | 3 | 0.2043 | 0.2147 | -0.0104 | -0.04515 | 0.04211 | equivalente (IC cruza 0) |

## 3. Escalera de `min_edge`: vale algo el edge declarado?

Si el edge tuviera informacion, `roi_flat` CRECERIA con el umbral.

### Suelo de probabilidad implicita = 0.00

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.0 | 6117 | 2758 | 0.44313 | -0.08428 | -0.12466 | -0.04458 | ROI negativo |
| 0.02 | 0.0 | 4810 | 2294 | 0.43144 | -0.09074 | -0.14047 | -0.04932 | ROI negativo |
| 0.05 | 0.0 | 3323 | 1687 | 0.41551 | -0.10138 | -0.1553 | -0.04537 | ROI negativo |
| 0.08 | 0.0 | 2309 | 1233 | 0.38763 | -0.1255 | -0.1949 | -0.05305 | ROI negativo |
| 0.12 | 0.0 | 1476 | 861 | 0.34922 | -0.16192 | -0.24168 | -0.07631 | ROI negativo |

### Suelo de probabilidad implicita = 0.35

| min_edge | price_floor | n_rows | n_events | hit_rate | roi_flat | roi_lo | roi_hi | veredicto |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.35 | 5076 | 2369 | 0.49197 | -0.05784 | -0.09358 | -0.02051 | ROI negativo |
| 0.02 | 0.35 | 3855 | 1896 | 0.48916 | -0.05639 | -0.10199 | -0.01267 | ROI negativo |
| 0.05 | 0.35 | 2498 | 1284 | 0.49455 | -0.04138 | -0.09582 | 0.0136 | indistinguible de 0 |
| 0.08 | 0.35 | 1603 | 863 | 0.48302 | -0.06075 | -0.13283 | 0.00954 | indistinguible de 0 |
| 0.12 | 0.35 | 887 | 503 | 0.47386 | -0.07845 | -0.16267 | 0.00882 | indistinguible de 0 |

## 4. Cap de plausibilidad: esta cortando lo peor o picks buenos?

`risk.max_plausible_edge` descarta candidatos cuyo edge declarado es implausible. Es el control con MAS trabajo efectivo del sistema: en un run real el 63% de las filas descartadas llevan su flag, mas que el gate de prediccion. Un cap util corta lo que rinde PEOR.

AVISO: el techo se barre sobre la misma muestra que se evalua, asi que el mejor punto esta sesgado al alza. Sirve para VIGILAR que el cap sigue funcionando, no para optimizarlo.

| cap | n_pasan | roi_pasan | roi_pasan_lo | roi_pasan_hi | n_cortadas | roi_cortadas | roi_cortadas_lo | roi_cortadas_hi | veredicto |
|---|---|---|---|---|---|---|---|---|---|
| 0.05 | 2791 | -0.06329 | -0.10706 | -0.01657 | 3320 | -0.10113 | -0.15876 | -0.04968 | el cap corta lo peor |
| 0.075 | 3656 | -0.05878 | -0.09954 | -0.01871 | 2455 | -0.12118 | -0.1864 | -0.05339 | el cap corta lo peor |
| 0.1 | 4286 | -0.05686 | -0.097 | -0.01605 | 1825 | -0.14722 | -0.2249 | -0.0724 | el cap corta lo peor |
| 0.15 | 5028 | -0.06284 | -0.10241 | -0.02388 | 1083 | -0.18136 | -0.27995 | -0.07533 | el cap corta lo peor |
| 0.2 | 5428 | -0.0685 | -0.10684 | -0.02997 | 683 | -0.20578 | -0.31843 | -0.07427 | el cap corta lo peor |
| 0.3 | 5769 | -0.06852 | -0.10989 | -0.02909 | 342 | -0.34243 | -0.53068 | -0.14345 | el cap corta lo peor |
| inf | 6111 | -0.08384 | -0.11927 | -0.04303 | 0 |  |  |  | sin cap |

## 5. Contraste directo de la seleccion

- ROI donde el modelo apuesta (edge>0): **-0.0838** (n=6111)
- ROI en el resto (edge<=0): **-0.0545** (n=17744)
- Delta = **-0.0293**, IC95 = [-0.0738, +0.0207]

Delta negativo con IC que excluye 0 significa que la regla de seleccion RESTA valor: el sistema apuesta el peor lado de cada mercado.
