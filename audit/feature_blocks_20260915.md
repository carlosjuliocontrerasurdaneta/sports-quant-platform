# Evaluación de features — 2026-09-15

**Estado: exploratorio; ningún bloque promovido a producción.**

Código/configuración: `480789fe7af66a83917d4ae2c75b802068d40ee095efb45b1980fa0e1503cceb`.
Cambio de código durante el run: False.

Cinco folds expansivos por fecha, ventana de 20 partidos, 2.000 remuestreos por contraste. Imputación y escalado dentro de train; intervalos por fecha con corrección de multiplicidad por liga.

El baseline aprendido usa las salidas del adaptador configurado. La columna “todos” añade los bloques con datos. Diferencia negativa = menor error. Los parámetros actuales del adaptador pueden haber sido ajustados con parte del historial: estos resultados son retrospectivos, no una confirmación prospectiva.

| Liga | Objetivo | N evaluación | Baseline aprendido | Todos | Delta todos − baseline | Intervalo corregido |
|---|---|---:|---:|---:|---:|---|
| atp | h2h (brier) | 6217 | 0.23117 | 0.22715 | -0.00403 | [-0.00743, -0.00078] |
| brasileirao | h2h (brier) | 1085 | 0.62150 | 0.67270 | +0.05120 | [+0.02478, +0.08670] |
| brasileirao | total_score (mae) | 1085 | 1.20417 | 1.28391 | +0.07975 | [+0.02530, +0.16320] |
| bundesliga | h2h (brier) | 787 | 0.60681 | 0.63935 | +0.03254 | [-0.00320, +0.07995] |
| bundesliga | total_score (mae) | 787 | 1.43045 | 1.49374 | +0.06329 | [-0.01324, +0.15120] |
| chile | h2h (brier) | 643 | 0.61636 | 0.68247 | +0.06611 | [+0.02204, +0.11283] |
| chile | total_score (mae) | 643 | 1.36573 | 1.39629 | +0.03057 | [-0.01644, +0.07500] |
| epl | h2h (brier) | 980 | 0.60979 | 0.64475 | +0.03496 | [+0.00719, +0.06036] |
| epl | total_score (mae) | 980 | 1.32154 | 1.37999 | +0.05845 | [+0.01372, +0.12435] |
| laliga | h2h (brier) | 983 | 0.60297 | 0.63533 | +0.03236 | [+0.00675, +0.05975] |
| laliga | total_score (mae) | 983 | 1.25565 | 1.31276 | +0.05711 | [+0.00464, +0.12221] |
| ligamx | h2h (brier) | 918 | 0.60159 | 0.63940 | +0.03781 | [+0.01443, +0.06174] |
| ligamx | total_score (mae) | 918 | 1.34104 | 1.36756 | +0.02652 | [-0.00564, +0.05923] |
| ligue1 | h2h (brier) | 799 | 0.62341 | 0.68273 | +0.05933 | [+0.02609, +0.09568] |
| ligue1 | total_score (mae) | 799 | 1.39756 | 1.52623 | +0.12867 | [+0.04407, +0.26280] |
| mlb | h2h (brier) | 7918 | 0.24482 | 0.24746 | +0.00264 | [+0.00071, +0.00486] |
| mlb | total_score (mae) | 7918 | 3.54306 | 3.62838 | +0.08532 | [-0.00449, +0.36926] |
| mls | h2h (brier) | 1451 | 0.63995 | 0.66994 | +0.02999 | [+0.00760, +0.05910] |
| mls | total_score (mae) | 1451 | 1.43722 | 1.50568 | +0.06846 | [+0.03167, +0.11820] |
| nba | h2h (brier) | 28116 | 0.21481 | 0.21379 | -0.00102 | [-0.00180, -0.00032] |
| nba | total_score (mae) | 28116 | 15.70261 | 15.11787 | -0.58474 | [-0.66655, -0.49199] |
| ncaab | h2h (brier) | 4749 | 0.20191 | 0.19864 | -0.00327 | [-0.01024, +0.00506] |
| ncaab | total_score (mae) | 4749 | 13.84976 | 13.95549 | +0.10573 | [-0.01447, +0.23732] |
| ncaaf | h2h (brier) | 2438 | 0.19427 | 0.18381 | -0.01046 | [-0.02173, +0.00279] |
| ncaaf | total_score (mae) | 2438 | 12.80860 | 17.67390 | +4.86531 | [+0.25597, +16.09848] |
| nfl | h2h (brier) | 6504 | 0.22977 | 0.23076 | +0.00098 | [-0.00107, +0.00313] |
| nfl | total_score (mae) | 6541 | 11.03392 | 10.85242 | -0.18149 | [-0.30223, -0.06432] |
| nhl | h2h (brier) | 27334 | 0.24194 | 0.24182 | -0.00012 | [-0.00068, +0.00044] |
| nhl | total_score (mae) | 27334 | 1.83187 | 1.81940 | -0.01246 | [-0.01776, -0.00763] |
| seriea | h2h (brier) | 960 | 0.60761 | 0.64221 | +0.03460 | [+0.00837, +0.06587] |
| seriea | total_score (mae) | 960 | 1.27292 | 1.37084 | +0.09792 | [+0.01278, +0.22574] |
| ucl | h2h (brier) | 413 | 0.56126 | 0.65508 | +0.09382 | [+0.02151, +0.16866] |
| ucl | total_score (mae) | 413 | 1.56933 | 1.99712 | +0.42779 | [+0.19779, +0.67948] |
| uwcl | h2h (brier) | 144 | 0.44938 | 0.62683 | +0.17745 | [+0.05803, +0.33469] |
| uwcl | total_score (mae) | 144 | 1.44580 | 2.11307 | +0.66727 | [+0.19900, +1.25494] |
| wnba | h2h (brier) | 934 | 0.21501 | 0.22345 | +0.00844 | [-0.00237, +0.02099] |
| wnba | total_score (mae) | 934 | 14.21743 | 17.13543 | +2.91799 | [+0.64031, +7.60123] |
| wncaab | h2h (brier) | 4643 | 0.17812 | 0.16787 | -0.01025 | [-0.01673, -0.00409] |
| wncaab | total_score (mae) | 4643 | 12.88293 | 13.09652 | +0.21359 | [+0.07341, +0.37254] |
| wta | h2h (brier) | 8792 | 0.23465 | 0.22889 | -0.00576 | [-0.00900, -0.00229] |

## Bloques individuales con mejora detectada

- **atp/h2h — schedule**: delta -0.00217, IC [-0.00452, -0.00009].
- **atp/h2h — opponent_form**: delta -0.00542, IC [-0.00826, -0.00253].
- **atp/h2h — venue_form**: delta -0.00404, IC [-0.00614, -0.00201].
- **nba/h2h — opponent_form**: delta -0.00103, IC [-0.00165, -0.00039].
- **nba/total_score — opponent_form**: delta -0.58191, IC [-0.65851, -0.49464].
- **ncaab/h2h — schedule**: delta -0.00471, IC [-0.00858, -0.00034].
- **ncaaf/h2h — schedule**: delta -0.00647, IC [-0.01246, -0.00125].
- **nfl/total_score — opponent_form**: delta -0.12184, IC [-0.21374, -0.04264].
- **nhl/total_score — opponent_form**: delta -0.01303, IC [-0.01776, -0.00896].
- **wncaab/h2h — schedule**: delta -0.00505, IC [-0.00942, -0.00068].
- **wncaab/h2h — opponent_form**: delta -0.01093, IC [-0.01729, -0.00473].
- **wta/h2h — schedule**: delta -0.00304, IC [-0.00476, -0.00146].
- **wta/h2h — opponent_form**: delta -0.00650, IC [-0.00966, -0.00319].
- **wta/h2h — venue_form**: delta -0.00489, IC [-0.00709, -0.00284].

La lista es descubrimiento sobre esta muestra. Elegir ligas/bloques a partir de ella requiere un preregistro y una ventana futura; no acredita ventaja contra el mercado.

## Cobertura y pendientes

- atp: bloques sin datos = sporting.
- brasileirao: bloques sin datos = sporting.
- bundesliga: bloques sin datos = sporting.
- chile: bloques sin datos = sporting.
- epl: bloques sin datos = sporting.
- laliga: bloques sin datos = sporting.
- ligamx: bloques sin datos = sporting.
- ligue1: bloques sin datos = sporting.
- mlb: bloques sin datos = sporting.
  - pitching_home_rotation_fip: 39.8% de cobertura pregame.
  - pitching_away_rotation_fip: 39.7% de cobertura pregame.
- mls: bloques sin datos = sporting.
- nba: bloques sin datos = sporting.
- ncaab: bloques sin datos = sporting.
- ncaaf: bloques sin datos = sporting.
- nfl: bloques sin datos = sporting.
- nhl: bloques sin datos = sporting.
- seriea: bloques sin datos = sporting.
- ucl: bloques sin datos = sporting.
- uwcl: bloques sin datos = sporting.
- wnba: bloques sin datos = sporting.
- wncaab: bloques sin datos = sporting.
- wta: bloques sin datos = sporting.

Los snapshots externos necesitan `available_at` y `source`. No había archivos suministrados de alineaciones, xG, quarterbacks, porteros o superficie. Sus contratos e interacciones están implementados, pero su señal no ha podido medirse.

La comparación contra cuotas al mismo instante sigue pendiente de IDs y horizontes alineados. El MAE de total_score no representa calibración de Over/Under ni ROI.

## Validación de implementación

- 121 pruebas específicas/de integración aprobadas.
- Ruff y mypy sobre src/scripts/tests y src, respectivamente: aprobados.
- Datasets ML reconstruidos; los joblib anteriores no se reetiquetan como modelos corregidos.

Detalle reproducible: [JSON](feature_blocks_20260915.json). Contrato y comandos: [FEATURE-RESEARCH](../docs/FEATURE-RESEARCH.md).

## Decisión por liga y objetivo

Estos dictámenes se limitan al modelo, bloques y protocolo evaluados. “Sin mejora demostrada” no prueba ausencia de señal en otras variables o modelos.

| Liga | Objetivo | Todos los bloques | Bloques individuales favorables |
|---|---|---|---|
| atp | h2h | Mejora exploratoria | schedule, opponent_form, venue_form |
| brasileirao | h2h | Empeora: descartar esta combinación | Ninguno |
| brasileirao | total_score | Empeora: descartar esta combinación | Ninguno |
| bundesliga | h2h | Sin mejora demostrada | Ninguno |
| bundesliga | total_score | Sin mejora demostrada | Ninguno |
| chile | h2h | Empeora: descartar esta combinación | Ninguno |
| chile | total_score | Sin mejora demostrada | Ninguno |
| epl | h2h | Empeora: descartar esta combinación | Ninguno |
| epl | total_score | Empeora: descartar esta combinación | Ninguno |
| laliga | h2h | Empeora: descartar esta combinación | Ninguno |
| laliga | total_score | Empeora: descartar esta combinación | Ninguno |
| ligamx | h2h | Empeora: descartar esta combinación | Ninguno |
| ligamx | total_score | Sin mejora demostrada | Ninguno |
| ligue1 | h2h | Empeora: descartar esta combinación | Ninguno |
| ligue1 | total_score | Empeora: descartar esta combinación | Ninguno |
| mlb | h2h | Empeora: descartar esta combinación | Ninguno |
| mlb | total_score | Sin mejora demostrada | Ninguno |
| mls | h2h | Empeora: descartar esta combinación | Ninguno |
| mls | total_score | Empeora: descartar esta combinación | Ninguno |
| nba | h2h | Mejora exploratoria | opponent_form |
| nba | total_score | Mejora exploratoria | opponent_form |
| ncaab | h2h | Sin mejora demostrada | schedule |
| ncaab | total_score | Sin mejora demostrada | Ninguno |
| ncaaf | h2h | Sin mejora demostrada | schedule |
| ncaaf | total_score | Empeora: descartar esta combinación | Ninguno |
| nfl | h2h | Sin mejora demostrada | Ninguno |
| nfl | total_score | Mejora exploratoria | opponent_form |
| nhl | h2h | Sin mejora demostrada | Ninguno |
| nhl | total_score | Mejora exploratoria | opponent_form |
| seriea | h2h | Empeora: descartar esta combinación | Ninguno |
| seriea | total_score | Empeora: descartar esta combinación | Ninguno |
| ucl | h2h | Empeora: descartar esta combinación | Ninguno |
| ucl | total_score | Empeora: descartar esta combinación | Ninguno |
| uwcl | h2h | Empeora: descartar esta combinación | Ninguno |
| uwcl | total_score | Empeora: descartar esta combinación | Ninguno |
| wnba | h2h | Sin mejora demostrada | Ninguno |
| wnba | total_score | Empeora: descartar esta combinación | Ninguno |
| wncaab | h2h | Mejora exploratoria | schedule, opponent_form |
| wncaab | total_score | Empeora: descartar esta combinación | Ninguno |
| wta | h2h | Mejora exploratoria | schedule, opponent_form, venue_form |

## Interpretación y prioridades

- Priorizar confirmación futura de forma reciente en NBA, ATP/WTA y WNCAAB; descanso en NCAAB/NCAAF/WNCAAB; forma para total de puntos/goles en NFL/NHL. No trasladar la evidencia entre objetivos.
- En las 11 ligas de fútbol no se detectó mejora individual con estos bloques. Todos juntos empeoran significativamente el ganador en 10; Bundesliga queda inconclusa. Esto exige revisar la representación y disponer de proyecciones deportivas con procedencia temporal antes de afirmar que xG o alineaciones solucionan el problema.
- MLB: la combinación empeora el ganador y el FIP de rotación no demuestra mejora individual. Su cobertura ronda el 40%; no sustituye una proyección del abridor confirmado y bullpen.
- WNBA: no hay mejora individual demostrada y los bloques juntos empeoran el total. NCAAF y WNCAAB también empeoran totales al combinarlos; el beneficio en ganador no justifica reutilizarlos para totales.
- El bloque de rol local/visitante en tenis refleja la orientación del proveedor. Su mejora necesita investigar estabilidad y posibles artefactos del orden de los participantes; no interpretarlo como ventaja de localía.
- Los intervalos corregidos usan cuantiles extremos de 2.000 remuestreos: los límites cercanos a cero tienen incertidumbre Monte Carlo. La corrección no cubre selección entre ligas ni dependencia entre fechas.

## Detalle de ablaciones

Brier binario y Brier multiclase tienen escalas diferentes. MAE se expresa en puntos/goles del deporte; no comparar sus magnitudes entre deportes.

### atp — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.23117 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.22900 | -0.00217 | [-0.00452, -0.00009] | — |
| opponent_form | 0.22576 | -0.00542 | [-0.00826, -0.00253] | — |
| venue_form | 0.22714 | -0.00404 | [-0.00614, -0.00201] | — |
| all | 0.22715 | -0.00403 | [-0.00743, -0.00078] | — |
| without_schedule | 0.22638 | -0.00479 | [-0.00769, -0.00168] | -0.00076 [-0.00215, +0.00055] |
| without_opponent_form | 0.22718 | -0.00399 | [-0.00671, -0.00135] | +0.00004 [-0.00150, +0.00157] |
| without_venue_form | 0.22646 | -0.00471 | [-0.00800, -0.00145] | -0.00068 [-0.00147, +0.00002] |
| operational | 0.23091 | -0.00027 | [-0.00090, +0.00031] | — |
| constant | 0.24996 | +0.01878 | [+0.01322, +0.02472] | — |

### brasileirao — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.62150 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.65261 | +0.03111 | [+0.01054, +0.06032] | — |
| opponent_form | 0.63301 | +0.01151 | [-0.00141, +0.02596] | — |
| venue_form | 0.63391 | +0.01240 | [-0.00425, +0.03046] | — |
| all | 0.67270 | +0.05120 | [+0.02478, +0.08670] | — |
| without_schedule | 0.64550 | +0.02400 | [+0.00703, +0.04440] | -0.02720 [-0.05884, -0.00580] |
| without_opponent_form | 0.66169 | +0.04019 | [+0.01252, +0.07169] | -0.01100 [-0.02159, -0.00081] |
| without_venue_form | 0.65989 | +0.03839 | [+0.01505, +0.06953] | -0.01280 [-0.02772, +0.00170] |
| operational | 0.61469 | -0.00681 | [-0.01427, -0.00045] | — |
| constant | 0.63503 | +0.01353 | [-0.00483, +0.03350] | — |

### brasileirao — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.20417 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.23555 | +0.03138 | [+0.00478, +0.06304] | — |
| opponent_form | 1.21200 | +0.00784 | [-0.00872, +0.02702] | — |
| venue_form | 1.20650 | +0.00233 | [-0.01065, +0.01725] | — |
| all | 1.28391 | +0.07975 | [+0.02530, +0.16320] | — |
| without_schedule | 1.22370 | +0.01953 | [-0.00475, +0.04553] | -0.06022 [-0.15198, -0.00110] |
| without_opponent_form | 1.25590 | +0.05173 | [+0.00785, +0.10903] | -0.02801 [-0.06816, +0.00514] |
| without_venue_form | 1.27421 | +0.07004 | [+0.01931, +0.14342] | -0.00971 [-0.02993, +0.00488] |
| operational | 1.20921 | +0.00504 | [-0.00827, +0.01828] | — |
| constant | 1.18802 | -0.01615 | [-0.06391, +0.03338] | — |

### bundesliga — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.60681 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.63018 | +0.02337 | [+0.00483, +0.06222] | — |
| opponent_form | 0.61209 | +0.00528 | [-0.01528, +0.02424] | — |
| venue_form | 0.61159 | +0.00478 | [-0.01005, +0.01952] | — |
| all | 0.63935 | +0.03254 | [-0.00320, +0.07995] | — |
| without_schedule | 0.61575 | +0.00894 | [-0.01279, +0.03007] | -0.02360 [-0.06685, -0.00060] |
| without_opponent_form | 0.63828 | +0.03147 | [+0.00584, +0.07466] | -0.00107 [-0.01749, +0.01714] |
| without_venue_form | 0.63747 | +0.03066 | [-0.00363, +0.07796] | -0.00187 [-0.01126, +0.00751] |
| operational | 0.59233 | -0.01449 | [-0.02983, +0.00053] | — |
| constant | 0.65657 | +0.04976 | [+0.00712, +0.09487] | — |

### bundesliga — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.43045 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.47879 | +0.04833 | [-0.00284, +0.14123] | — |
| opponent_form | 1.43633 | +0.00587 | [-0.03582, +0.05204] | — |
| venue_form | 1.45404 | +0.02358 | [-0.01152, +0.06044] | — |
| all | 1.49374 | +0.06329 | [-0.01324, +0.15120] | — |
| without_schedule | 1.45341 | +0.02296 | [-0.02810, +0.07435] | -0.04033 [-0.11812, +0.00662] |
| without_opponent_form | 1.48542 | +0.05497 | [-0.00208, +0.12848] | -0.00832 [-0.05386, +0.03493] |
| without_venue_form | 1.47034 | +0.03989 | [-0.02074, +0.11574] | -0.02340 [-0.04718, +0.00022] |
| operational | 1.41934 | -0.01111 | [-0.04874, +0.02333] | — |
| constant | 1.41550 | -0.01495 | [-0.04791, +0.01955] | — |

### chile — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.61636 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.62695 | +0.01059 | [-0.00364, +0.03160] | — |
| opponent_form | 0.67072 | +0.05435 | [+0.01851, +0.09197] | — |
| venue_form | 0.63581 | +0.01945 | [-0.00525, +0.04793] | — |
| all | 0.68247 | +0.06611 | [+0.02204, +0.11283] | — |
| without_schedule | 0.67086 | +0.05450 | [+0.01584, +0.09300] | -0.01161 [-0.03152, +0.00486] |
| without_opponent_form | 0.64690 | +0.03054 | [-0.00032, +0.06538] | -0.03557 [-0.06011, -0.00939] |
| without_venue_form | 0.67919 | +0.06283 | [+0.02603, +0.10637] | -0.00328 [-0.01970, +0.01232] |
| operational | 0.61003 | -0.00633 | [-0.02361, +0.01027] | — |
| constant | 0.63318 | +0.01682 | [-0.00386, +0.03655] | — |

### chile — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.36573 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.37370 | +0.00797 | [-0.01230, +0.02705] | — |
| opponent_form | 1.38810 | +0.02238 | [-0.01805, +0.06030] | — |
| venue_form | 1.36620 | +0.00048 | [-0.02997, +0.03102] | — |
| all | 1.39629 | +0.03057 | [-0.01644, +0.07500] | — |
| without_schedule | 1.39081 | +0.02509 | [-0.01752, +0.06641] | -0.00548 [-0.02228, +0.01202] |
| without_opponent_form | 1.37765 | +0.01193 | [-0.02447, +0.04876] | -0.01864 [-0.05032, +0.01103] |
| without_venue_form | 1.39399 | +0.02827 | [-0.01852, +0.06954] | -0.00230 [-0.02118, +0.01611] |
| operational | 1.32868 | -0.03704 | [-0.08137, +0.00387] | — |
| constant | 1.31882 | -0.04691 | [-0.09337, +0.00281] | — |

### epl — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.60979 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.62604 | +0.01625 | [+0.00178, +0.03915] | — |
| opponent_form | 0.62474 | +0.01496 | [-0.00660, +0.03339] | — |
| venue_form | 0.62499 | +0.01521 | [+0.00250, +0.02749] | — |
| all | 0.64475 | +0.03496 | [+0.00719, +0.06036] | — |
| without_schedule | 0.63940 | +0.02962 | [+0.00698, +0.05216] | -0.00535 [-0.02236, +0.00572] |
| without_opponent_form | 0.63297 | +0.02318 | [+0.00565, +0.04030] | -0.01178 [-0.02792, +0.00410] |
| without_venue_form | 0.63389 | +0.02410 | [-0.00227, +0.05111] | -0.01086 [-0.02479, +0.00134] |
| operational | 0.59686 | -0.01293 | [-0.02444, -0.00217] | — |
| constant | 0.65708 | +0.04730 | [+0.01502, +0.08135] | — |

### epl — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.32154 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.36278 | +0.04124 | [+0.00523, +0.09642] | — |
| opponent_form | 1.34289 | +0.02135 | [+0.00135, +0.04278] | — |
| venue_form | 1.32772 | +0.00619 | [-0.00541, +0.01892] | — |
| all | 1.37999 | +0.05845 | [+0.01372, +0.12435] | — |
| without_schedule | 1.33979 | +0.01825 | [-0.00445, +0.04368] | -0.04020 [-0.10055, -0.00101] |
| without_opponent_form | 1.37177 | +0.05023 | [+0.01200, +0.11167] | -0.00822 [-0.02905, +0.01381] |
| without_venue_form | 1.37679 | +0.05525 | [+0.01313, +0.11673] | -0.00320 [-0.01541, +0.00859] |
| operational | 1.34082 | +0.01928 | [-0.00398, +0.04042] | — |
| constant | 1.28061 | -0.04093 | [-0.06045, -0.02062] | — |

### laliga — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.60297 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.62091 | +0.01794 | [+0.00461, +0.03583] | — |
| opponent_form | 0.61145 | +0.00848 | [-0.00843, +0.02612] | — |
| venue_form | 0.60991 | +0.00694 | [-0.00569, +0.01894] | — |
| all | 0.63533 | +0.03236 | [+0.00675, +0.05975] | — |
| without_schedule | 0.61584 | +0.01287 | [-0.00755, +0.03348] | -0.01949 [-0.03780, -0.00524] |
| without_opponent_form | 0.62707 | +0.02410 | [+0.00593, +0.04405] | -0.00826 [-0.02159, +0.00507] |
| without_venue_form | 0.63036 | +0.02739 | [+0.00566, +0.05235] | -0.00497 [-0.01602, +0.00681] |
| operational | 0.58765 | -0.01532 | [-0.03258, +0.00001] | — |
| constant | 0.64329 | +0.04032 | [+0.00396, +0.07202] | — |

### laliga — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.25565 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.28070 | +0.02505 | [-0.00898, +0.07013] | — |
| opponent_form | 1.26601 | +0.01036 | [-0.01952, +0.04047] | — |
| venue_form | 1.28371 | +0.02806 | [-0.00476, +0.06859] | — |
| all | 1.31276 | +0.05711 | [+0.00464, +0.12221] | — |
| without_schedule | 1.28941 | +0.03376 | [-0.00637, +0.07662] | -0.02335 [-0.07289, +0.01243] |
| without_opponent_form | 1.29856 | +0.04291 | [-0.00166, +0.08950] | -0.01420 [-0.05756, +0.02686] |
| without_venue_form | 1.29004 | +0.03439 | [-0.01165, +0.09921] | -0.02272 [-0.05166, +0.00484] |
| operational | 1.26757 | +0.01192 | [-0.02064, +0.04203] | — |
| constant | 1.27874 | +0.02309 | [-0.04001, +0.08422] | — |

### ligamx — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.60159 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.61812 | +0.01653 | [+0.00132, +0.03232] | — |
| opponent_form | 0.61725 | +0.01566 | [+0.00072, +0.02936] | — |
| venue_form | 0.61013 | +0.00854 | [+0.00041, +0.01779] | — |
| all | 0.63940 | +0.03781 | [+0.01443, +0.06174] | — |
| without_schedule | 0.62398 | +0.02238 | [+0.00415, +0.03983] | -0.01542 [-0.03558, +0.00068] |
| without_opponent_form | 0.62297 | +0.02137 | [+0.00517, +0.03949] | -0.01643 [-0.03261, -0.00016] |
| without_venue_form | 0.63067 | +0.02908 | [+0.00924, +0.05002] | -0.00873 [-0.01995, +0.00043] |
| operational | 0.59732 | -0.00427 | [-0.01269, +0.00404] | — |
| constant | 0.64055 | +0.03896 | [+0.00760, +0.06612] | — |

### ligamx — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.34104 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.34280 | +0.00176 | [-0.01908, +0.02019] | — |
| opponent_form | 1.36171 | +0.02067 | [+0.00553, +0.03560] | — |
| venue_form | 1.35288 | +0.01184 | [-0.01052, +0.03250] | — |
| all | 1.36756 | +0.02652 | [-0.00564, +0.05923] | — |
| without_schedule | 1.36559 | +0.02455 | [-0.00496, +0.04976] | -0.00197 [-0.02215, +0.02108] |
| without_opponent_form | 1.35374 | +0.01271 | [-0.01557, +0.03983] | -0.01381 [-0.03402, +0.00671] |
| without_venue_form | 1.36361 | +0.02258 | [-0.00239, +0.04772] | -0.00394 [-0.02973, +0.02345] |
| operational | 1.34234 | +0.00131 | [-0.02418, +0.02864] | — |
| constant | 1.32135 | -0.01968 | [-0.04231, +0.00430] | — |

### ligue1 — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.62341 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.65253 | +0.02912 | [+0.00550, +0.05735] | — |
| opponent_form | 0.63862 | +0.01521 | [-0.00403, +0.03427] | — |
| venue_form | 0.63550 | +0.01209 | [-0.00032, +0.02748] | — |
| all | 0.68273 | +0.05933 | [+0.02609, +0.09568] | — |
| without_schedule | 0.65019 | +0.02678 | [+0.00402, +0.04848] | -0.03254 [-0.06766, -0.00292] |
| without_opponent_form | 0.66493 | +0.04153 | [+0.01428, +0.07125] | -0.01780 [-0.03846, +0.00193] |
| without_venue_form | 0.67029 | +0.04688 | [+0.01623, +0.08504] | -0.01244 [-0.02387, -0.00186] |
| operational | 0.60636 | -0.01705 | [-0.03347, +0.00190] | — |
| constant | 0.65183 | +0.02843 | [-0.00719, +0.06507] | — |

### ligue1 — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.39756 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.44359 | +0.04603 | [-0.00662, +0.14359] | — |
| opponent_form | 1.45632 | +0.05876 | [+0.01520, +0.11425] | — |
| venue_form | 1.42830 | +0.03074 | [-0.00003, +0.06923] | — |
| all | 1.52623 | +0.12867 | [+0.04407, +0.26280] | — |
| without_schedule | 1.46134 | +0.06378 | [+0.01953, +0.11827] | -0.06489 [-0.17826, -0.00188] |
| without_opponent_form | 1.46366 | +0.06610 | [+0.01360, +0.14609] | -0.06257 [-0.12805, -0.01653] |
| without_venue_form | 1.52464 | +0.12708 | [+0.03607, +0.25706] | -0.00159 [-0.02573, +0.01925] |
| operational | 1.38634 | -0.01122 | [-0.03987, +0.02080] | — |
| constant | 1.40050 | +0.00294 | [-0.03084, +0.03834] | — |

### mlb — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.24482 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.24560 | +0.00078 | [-0.00040, +0.00264] | — |
| opponent_form | 0.24528 | +0.00046 | [-0.00044, +0.00136] | — |
| venue_form | 0.24529 | +0.00047 | [-0.00015, +0.00120] | — |
| pitching | 0.24534 | +0.00052 | [+0.00003, +0.00116] | — |
| all | 0.24746 | +0.00264 | [+0.00071, +0.00486] | — |
| without_schedule | 0.24626 | +0.00144 | [+0.00019, +0.00276] | -0.00121 [-0.00306, +0.00033] |
| without_opponent_form | 0.24687 | +0.00205 | [+0.00053, +0.00394] | -0.00059 [-0.00154, +0.00036] |
| without_venue_form | 0.24707 | +0.00225 | [+0.00041, +0.00434] | -0.00040 [-0.00105, +0.00024] |
| without_pitching | 0.24661 | +0.00179 | [+0.00005, +0.00407] | -0.00085 [-0.00162, -0.00021] |
| operational | 0.24471 | -0.00011 | [-0.00113, +0.00099] | — |
| constant | 0.24919 | +0.00437 | [+0.00197, +0.00721] | — |

### mlb — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 3.54306 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 3.61879 | +0.07573 | [-0.00069, +0.34070] | — |
| opponent_form | 3.54554 | +0.00248 | [-0.01100, +0.01623] | — |
| venue_form | 3.54158 | -0.00148 | [-0.00643, +0.00357] | — |
| pitching | 3.54327 | +0.00021 | [-0.00522, +0.00561] | — |
| all | 3.62838 | +0.08532 | [-0.00449, +0.36926] | — |
| without_schedule | 3.54447 | +0.00141 | [-0.01486, +0.01772] | -0.08391 [-0.36604, -0.00146] |
| without_opponent_form | 3.61471 | +0.07165 | [-0.00418, +0.32389] | -0.01367 [-0.05183, +0.00700] |
| without_venue_form | 3.62584 | +0.08278 | [-0.00259, +0.35717] | -0.00254 [-0.01327, +0.00516] |
| without_pitching | 3.62746 | +0.08439 | [-0.00486, +0.36809] | -0.00093 [-0.00642, +0.00374] |
| operational | 3.56467 | +0.02160 | [+0.00879, +0.03524] | — |
| constant | 3.53764 | -0.00543 | [-0.02858, +0.01887] | — |

### mls — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.63995 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.65397 | +0.01402 | [-0.00097, +0.04191] | — |
| opponent_form | 0.65346 | +0.01351 | [+0.00167, +0.02552] | — |
| venue_form | 0.64764 | +0.00769 | [-0.00027, +0.01610] | — |
| all | 0.66994 | +0.02999 | [+0.00760, +0.05910] | — |
| without_schedule | 0.65910 | +0.01915 | [+0.00532, +0.03394] | -0.01084 [-0.03225, +0.00208] |
| without_opponent_form | 0.66078 | +0.02082 | [+0.00451, +0.04513] | -0.00916 [-0.02228, +0.00253] |
| without_venue_form | 0.66480 | +0.02485 | [+0.00575, +0.05365] | -0.00514 [-0.01364, +0.00457] |
| operational | 0.63677 | -0.00318 | [-0.01218, +0.00527] | — |
| constant | 0.64688 | +0.00692 | [-0.00448, +0.01907] | — |

### mls — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.43722 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.47091 | +0.03369 | [+0.00425, +0.09623] | — |
| opponent_form | 1.46679 | +0.02957 | [+0.00784, +0.05216] | — |
| venue_form | 1.45502 | +0.01780 | [+0.00203, +0.03617] | — |
| all | 1.50568 | +0.06846 | [+0.03167, +0.11820] | — |
| without_schedule | 1.47797 | +0.04074 | [+0.01733, +0.06830] | -0.02772 [-0.07501, -0.00267] |
| without_opponent_form | 1.47963 | +0.04240 | [+0.01545, +0.08683] | -0.02606 [-0.04669, -0.00501] |
| without_venue_form | 1.50505 | +0.06782 | [+0.02362, +0.14706] | -0.00064 [-0.02376, +0.03429] |
| operational | 1.44628 | +0.00906 | [+0.00011, +0.01979] | — |
| constant | 1.40868 | -0.02854 | [-0.04639, -0.01128] | — |

### nba — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.21481 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.21485 | +0.00005 | [-0.00034, +0.00039] | — |
| opponent_form | 0.21378 | -0.00103 | [-0.00165, -0.00039] | — |
| venue_form | 0.21484 | +0.00004 | [-0.00016, +0.00024] | — |
| all | 0.21379 | -0.00102 | [-0.00180, -0.00032] | — |
| without_schedule | 0.21384 | -0.00096 | [-0.00160, -0.00033] | +0.00006 [-0.00031, +0.00042] |
| without_opponent_form | 0.21491 | +0.00010 | [-0.00036, +0.00049] | +0.00112 [+0.00051, +0.00179] |
| without_venue_form | 0.21373 | -0.00108 | [-0.00186, -0.00040] | -0.00006 [-0.00024, +0.00010] |
| operational | 0.21538 | +0.00058 | [-0.00016, +0.00129] | — |
| constant | 0.24358 | +0.02877 | [+0.02598, +0.03146] | — |

### nba — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 15.70261 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 15.70937 | +0.00676 | [-0.02248, +0.03680] | — |
| opponent_form | 15.12070 | -0.58191 | [-0.65851, -0.49464] | — |
| venue_form | 15.71938 | +0.01677 | [+0.00662, +0.02812] | — |
| all | 15.11787 | -0.58474 | [-0.66655, -0.49199] | — |
| without_schedule | 15.12277 | -0.57984 | [-0.66046, -0.49308] | +0.00490 [-0.01608, +0.02551] |
| without_opponent_form | 15.71417 | +0.01156 | [-0.01822, +0.04179] | +0.59630 [+0.50929, +0.67468] |
| without_venue_form | 15.11543 | -0.58719 | [-0.67090, -0.49490] | -0.00244 [-0.00953, +0.00616] |
| operational | 15.15724 | -0.54537 | [-0.68807, -0.40588] | — |
| constant | 21.46749 | +5.76488 | [+5.36488, +6.18658] | — |

### ncaab — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.20191 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.19720 | -0.00471 | [-0.00858, -0.00034] | — |
| opponent_form | 0.19819 | -0.00372 | [-0.01119, +0.00490] | — |
| venue_form | 0.20568 | +0.00377 | [-0.00329, +0.01228] | — |
| all | 0.19864 | -0.00327 | [-0.01024, +0.00506] | — |
| without_schedule | 0.19852 | -0.00338 | [-0.01039, +0.00523] | -0.00011 [-0.00328, +0.00287] |
| without_opponent_form | 0.19850 | -0.00341 | [-0.00802, +0.00147] | -0.00014 [-0.00510, +0.00374] |
| without_venue_form | 0.19813 | -0.00378 | [-0.01117, +0.00484] | -0.00051 [-0.00237, +0.00109] |
| operational | 0.21208 | +0.01017 | [+0.00003, +0.01939] | — |
| constant | 0.24066 | +0.03875 | [+0.02935, +0.04810] | — |

### ncaab — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 13.84976 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 13.85978 | +0.01002 | [-0.05662, +0.06417] | — |
| opponent_form | 13.97358 | +0.12383 | [-0.01564, +0.30065] | — |
| venue_form | 13.97469 | +0.12493 | [+0.02607, +0.23797] | — |
| all | 13.95549 | +0.10573 | [-0.01447, +0.23732] | — |
| without_schedule | 13.98649 | +0.13673 | [-0.00443, +0.29981] | +0.03100 [-0.03432, +0.08883] |
| without_opponent_form | 13.90823 | +0.05848 | [-0.02282, +0.14140] | -0.04725 [-0.14478, +0.04798] |
| without_venue_form | 13.93191 | +0.08216 | [-0.02761, +0.20904] | -0.02357 [-0.07406, +0.03239] |
| operational | 14.22602 | +0.37627 | [+0.19315, +0.58733] | — |
| constant | 15.45062 | +1.60086 | [+1.28033, +1.95107] | — |

### ncaaf — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.19427 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.18780 | -0.00647 | [-0.01246, -0.00125] | — |
| opponent_form | 0.19149 | -0.00278 | [-0.01599, +0.01239] | — |
| venue_form | 0.19881 | +0.00454 | [-0.00514, +0.01629] | — |
| all | 0.18381 | -0.01046 | [-0.02173, +0.00279] | — |
| without_schedule | 0.19017 | -0.00410 | [-0.01798, +0.01166] | +0.00636 [-0.00287, +0.02221] |
| without_opponent_form | 0.19470 | +0.00043 | [-0.00881, +0.01032] | +0.01089 [+0.00237, +0.02216] |
| without_venue_form | 0.18331 | -0.01096 | [-0.02166, -0.00086] | -0.00050 [-0.00494, +0.00336] |
| operational | 0.20602 | +0.01175 | [+0.00208, +0.02095] | — |
| constant | 0.22981 | +0.03554 | [+0.02170, +0.04908] | — |

### ncaaf — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 12.80860 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 17.05141 | +4.24281 | [+0.15223, +14.23717] | — |
| opponent_form | 12.80359 | -0.00501 | [-0.09319, +0.07514] | — |
| venue_form | 12.80168 | -0.00692 | [-0.04859, +0.04402] | — |
| all | 17.67390 | +4.86531 | [+0.25597, +16.09848] | — |
| without_schedule | 12.82327 | +0.01467 | [-0.09029, +0.12472] | -4.85063 [-16.06614, -0.29412] |
| without_opponent_form | 17.65167 | +4.84307 | [+0.26594, +16.19181] | -0.02223 [-0.26479, +0.18665] |
| without_venue_form | 17.23399 | +4.42539 | [+0.19250, +14.49090] | -0.43992 [-1.60758, -0.01123] |
| operational | 12.78233 | -0.02626 | [-0.08692, +0.03102] | — |
| constant | 13.14438 | +0.33579 | [+0.13623, +0.54941] | — |

### nfl — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.22977 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.22987 | +0.00010 | [-0.00102, +0.00128] | — |
| opponent_form | 0.23033 | +0.00056 | [-0.00111, +0.00226] | — |
| venue_form | 0.23007 | +0.00030 | [-0.00056, +0.00117] | — |
| all | 0.23076 | +0.00098 | [-0.00107, +0.00313] | — |
| without_schedule | 0.23089 | +0.00112 | [-0.00066, +0.00304] | +0.00013 [-0.00077, +0.00105] |
| without_opponent_form | 0.23017 | +0.00040 | [-0.00091, +0.00192] | -0.00058 [-0.00205, +0.00080] |
| without_venue_form | 0.23020 | +0.00043 | [-0.00141, +0.00236] | -0.00056 [-0.00137, +0.00020] |
| operational | 0.22952 | -0.00025 | [-0.00167, +0.00095] | — |
| constant | 0.24741 | +0.01763 | [+0.01310, +0.02170] | — |

### nfl — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 11.03392 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 10.98751 | -0.04640 | [-0.11116, +0.02471] | — |
| opponent_form | 10.91208 | -0.12184 | [-0.21374, -0.04264] | — |
| venue_form | 11.04568 | +0.01177 | [-0.01008, +0.03359] | — |
| all | 10.85242 | -0.18149 | [-0.30223, -0.06432] | — |
| without_schedule | 10.91756 | -0.11636 | [-0.20086, -0.03631] | +0.06513 [-0.00737, +0.13959] |
| without_opponent_form | 10.99883 | -0.03509 | [-0.10174, +0.04138] | +0.14641 [+0.05113, +0.23834] |
| without_venue_form | 10.84927 | -0.18464 | [-0.30071, -0.06563] | -0.00315 [-0.01360, +0.00971] |
| operational | 11.01157 | -0.02235 | [-0.07571, +0.02639] | — |
| constant | 11.19064 | +0.15673 | [+0.04735, +0.26649] | — |

### nhl — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.24194 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.24198 | +0.00004 | [-0.00020, +0.00030] | — |
| opponent_form | 0.24171 | -0.00023 | [-0.00073, +0.00026] | — |
| venue_form | 0.24204 | +0.00010 | [-0.00005, +0.00025] | — |
| all | 0.24182 | -0.00012 | [-0.00068, +0.00044] | — |
| without_schedule | 0.24180 | -0.00014 | [-0.00068, +0.00040] | -0.00002 [-0.00025, +0.00020] |
| without_opponent_form | 0.24209 | +0.00015 | [-0.00011, +0.00045] | +0.00027 [-0.00019, +0.00075] |
| without_venue_form | 0.24173 | -0.00021 | [-0.00070, +0.00032] | -0.00009 [-0.00026, +0.00007] |
| operational | 0.24940 | +0.00746 | [+0.00594, +0.00890] | — |
| constant | 0.24805 | +0.00611 | [+0.00460, +0.00762] | — |

### nhl — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.83187 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.83217 | +0.00030 | [-0.00168, +0.00242] | — |
| opponent_form | 1.81884 | -0.01303 | [-0.01776, -0.00896] | — |
| venue_form | 1.83218 | +0.00032 | [-0.00059, +0.00110] | — |
| all | 1.81940 | -0.01246 | [-0.01776, -0.00763] | — |
| without_schedule | 1.81883 | -0.01304 | [-0.01787, -0.00892] | -0.00058 [-0.00235, +0.00101] |
| without_opponent_form | 1.83247 | +0.00061 | [-0.00151, +0.00284] | +0.01307 [+0.00900, +0.01744] |
| without_venue_form | 1.81941 | -0.01246 | [-0.01737, -0.00765] | +0.00001 [-0.00075, +0.00086] |
| operational | 1.82921 | -0.00266 | [-0.00477, -0.00064] | — |
| constant | 1.84027 | +0.00840 | [-0.00493, +0.02285] | — |

### seriea — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.60761 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.62061 | +0.01299 | [-0.00458, +0.03546] | — |
| opponent_form | 0.62492 | +0.01731 | [+0.00125, +0.03414] | — |
| venue_form | 0.61709 | +0.00947 | [-0.00042, +0.01944] | — |
| all | 0.64221 | +0.03460 | [+0.00837, +0.06587] | — |
| without_schedule | 0.63665 | +0.02904 | [+0.00727, +0.04980] | -0.00556 [-0.02344, +0.01239] |
| without_opponent_form | 0.62961 | +0.02200 | [+0.00023, +0.04557] | -0.01260 [-0.02551, -0.00062] |
| without_venue_form | 0.63490 | +0.02729 | [+0.00378, +0.05579] | -0.00731 [-0.01428, -0.00089] |
| operational | 0.59585 | -0.01176 | [-0.02798, +0.00319] | — |
| constant | 0.66421 | +0.05660 | [+0.01879, +0.09452] | — |

### seriea — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.27292 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.34305 | +0.07013 | [+0.00054, +0.17602] | — |
| opponent_form | 1.28132 | +0.00840 | [-0.01290, +0.03168] | — |
| venue_form | 1.28707 | +0.01415 | [-0.00161, +0.03074] | — |
| all | 1.37084 | +0.09792 | [+0.01278, +0.22574] | — |
| without_schedule | 1.29545 | +0.02254 | [-0.00586, +0.05181] | -0.07539 [-0.19660, +0.00232] |
| without_opponent_form | 1.36595 | +0.09303 | [+0.00834, +0.21416] | -0.00489 [-0.02569, +0.01808] |
| without_venue_form | 1.34927 | +0.07635 | [-0.00071, +0.18885] | -0.02157 [-0.05018, +0.00355] |
| operational | 1.27801 | +0.00509 | [-0.01816, +0.02972] | — |
| constant | 1.29167 | +0.01875 | [-0.02901, +0.06865] | — |

### ucl — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.56126 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.60740 | +0.04614 | [+0.00634, +0.10060] | — |
| opponent_form | 0.60084 | +0.03958 | [-0.01149, +0.09265] | — |
| venue_form | 0.58727 | +0.02601 | [-0.00815, +0.06419] | — |
| all | 0.65508 | +0.09382 | [+0.02151, +0.16866] | — |
| without_schedule | 0.60060 | +0.03934 | [-0.00964, +0.09223] | -0.05447 [-0.10290, -0.01467] |
| without_opponent_form | 0.64398 | +0.08272 | [+0.02293, +0.14453] | -0.01110 [-0.03728, +0.01551] |
| without_venue_form | 0.65185 | +0.09059 | [+0.01679, +0.18007] | -0.00323 [-0.03817, +0.03152] |
| operational | 0.57079 | +0.00952 | [-0.03007, +0.04927] | — |
| constant | 0.60752 | +0.04625 | [-0.01633, +0.10551] | — |

### ucl — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.56933 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.68211 | +0.11278 | [-0.01013, +0.33444] | — |
| opponent_form | 1.63603 | +0.06670 | [-0.01432, +0.14223] | — |
| venue_form | 1.75668 | +0.18735 | [+0.03945, +0.32382] | — |
| all | 1.99712 | +0.42779 | [+0.19779, +0.67948] | — |
| without_schedule | 1.76093 | +0.19160 | [+0.04663, +0.31945] | -0.23619 [-0.46197, -0.07186] |
| without_opponent_form | 1.96739 | +0.39805 | [+0.15838, +0.66956] | -0.02974 [-0.11299, +0.04480] |
| without_venue_form | 1.77478 | +0.20545 | [+0.06308, +0.40712] | -0.22234 [-0.38585, -0.09508] |
| operational | 1.56103 | -0.00830 | [-0.04425, +0.02850] | — |
| constant | 1.53995 | -0.02938 | [-0.06699, +0.00301] | — |

### uwcl — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.44938 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.52195 | +0.07257 | [-0.00857, +0.17157] | — |
| opponent_form | 0.55221 | +0.10283 | [+0.02311, +0.20655] | — |
| venue_form | 0.49513 | +0.04575 | [-0.00649, +0.09282] | — |
| all | 0.62683 | +0.17745 | [+0.05803, +0.33469] | — |
| without_schedule | 0.54909 | +0.09971 | [+0.01200, +0.18725] | -0.07774 [-0.18045, +0.00601] |
| without_opponent_form | 0.61436 | +0.16498 | [+0.04879, +0.32322] | -0.01247 [-0.06833, +0.05564] |
| without_venue_form | 0.64462 | +0.19524 | [+0.06093, +0.36032] | +0.01778 [-0.02557, +0.08307] |
| operational | 0.49483 | +0.04545 | [-0.03541, +0.11908] | — |
| constant | 0.59836 | +0.14898 | [+0.03350, +0.25257] | — |

### uwcl — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 1.44580 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 1.52932 | +0.08352 | [-0.05296, +0.30158] | — |
| opponent_form | 1.66482 | +0.21902 | [-0.03465, +0.43694] | — |
| venue_form | 1.65165 | +0.20585 | [-0.02877, +0.45185] | — |
| all | 2.11307 | +0.66727 | [+0.19900, +1.25494] | — |
| without_schedule | 1.73517 | +0.28937 | [+0.00811, +0.58431] | -0.37790 [-0.89110, -0.07304] |
| without_opponent_form | 2.19079 | +0.74498 | [+0.23153, +1.35832] | +0.07772 [-0.07573, +0.21301] |
| without_venue_form | 2.00957 | +0.56377 | [+0.16806, +1.07212] | -0.10350 [-0.22711, +0.02665] |
| operational | 1.46779 | +0.02199 | [-0.08139, +0.14233] | — |
| constant | 1.40278 | -0.04303 | [-0.14571, +0.06139] | — |

### wnba — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.21501 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.22027 | +0.00526 | [-0.00360, +0.01723] | — |
| opponent_form | 0.21766 | +0.00265 | [-0.00444, +0.00931] | — |
| venue_form | 0.21517 | +0.00016 | [-0.00506, +0.00438] | — |
| all | 0.22345 | +0.00844 | [-0.00237, +0.02099] | — |
| without_schedule | 0.21969 | +0.00468 | [-0.00293, +0.01273] | -0.00376 [-0.01467, +0.00477] |
| without_opponent_form | 0.22080 | +0.00579 | [-0.00331, +0.01709] | -0.00265 [-0.01314, +0.01037] |
| without_venue_form | 0.22078 | +0.00577 | [-0.00469, +0.01798] | -0.00267 [-0.00663, +0.00173] |
| operational | 0.21659 | +0.00158 | [-0.00517, +0.00783] | — |
| constant | 0.24758 | +0.03257 | [+0.01428, +0.05119] | — |

### wnba — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 14.21743 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 17.20376 | +2.98633 | [+0.19814, +8.90200] | — |
| opponent_form | 14.89863 | +0.68120 | [+0.12360, +1.29020] | — |
| venue_form | 14.48827 | +0.27084 | [-0.01153, +0.51062] | — |
| all | 17.13543 | +2.91799 | [+0.64031, +7.60123] | — |
| without_schedule | 15.03372 | +0.81629 | [+0.23921, +1.43730] | -2.10170 [-6.72177, +0.01250] |
| without_opponent_form | 17.11959 | +2.90215 | [+0.34233, +8.15599] | -0.01584 [-0.62088, +0.77612] |
| without_venue_form | 17.10579 | +2.88836 | [+0.56959, +7.66346] | -0.02963 [-0.31186, +0.35955] |
| operational | 14.20425 | -0.01318 | [-0.12139, +0.08980] | — |
| constant | 15.19486 | +0.97743 | [+0.36142, +1.62136] | — |

### wncaab — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.17812 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.17306 | -0.00505 | [-0.00942, -0.00068] | — |
| opponent_form | 0.16719 | -0.01093 | [-0.01729, -0.00473] | — |
| venue_form | 0.17525 | -0.00286 | [-0.00600, +0.00130] | — |
| all | 0.16787 | -0.01025 | [-0.01673, -0.00409] | — |
| without_schedule | 0.16699 | -0.01112 | [-0.01765, -0.00534] | -0.00087 [-0.00281, +0.00120] |
| without_opponent_form | 0.17390 | -0.00421 | [-0.00966, +0.00129] | +0.00604 [+0.00219, +0.00954] |
| without_venue_form | 0.16787 | -0.01024 | [-0.01601, -0.00397] | +0.00001 [-0.00191, +0.00181] |
| operational | 0.20136 | +0.02324 | [+0.01619, +0.03124] | — |
| constant | 0.24667 | +0.06855 | [+0.05614, +0.08099] | — |

### wncaab — total_score

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 12.88293 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 13.00731 | +0.12438 | [+0.03864, +0.25966] | — |
| opponent_form | 12.93993 | +0.05701 | [-0.04684, +0.17250] | — |
| venue_form | 13.01305 | +0.13013 | [+0.00421, +0.26671] | — |
| all | 13.09652 | +0.21359 | [+0.07341, +0.37254] | — |
| without_schedule | 13.02671 | +0.14379 | [+0.02445, +0.28503] | -0.06981 [-0.16560, +0.03311] |
| without_opponent_form | 13.08120 | +0.19827 | [+0.06430, +0.33648] | -0.01532 [-0.07614, +0.04462] |
| without_venue_form | 13.03919 | +0.15626 | [+0.03427, +0.29710] | -0.05733 [-0.14042, +0.03463] |
| operational | 13.33067 | +0.44774 | [+0.22183, +0.65280] | — |
| constant | 14.85699 | +1.97406 | [+1.57296, +2.36973] | — |

### wta — h2h

| Variante | Error | Delta vs baseline | IC corregido | Coste de retirarla del conjunto (IC) |
|---|---:|---:|---|---|
| baseline | 0.23465 | +0.00000 | [+0.00000, +0.00000] | — |
| schedule | 0.23160 | -0.00304 | [-0.00476, -0.00146] | — |
| opponent_form | 0.22814 | -0.00650 | [-0.00966, -0.00319] | — |
| venue_form | 0.22976 | -0.00489 | [-0.00709, -0.00284] | — |
| all | 0.22889 | -0.00576 | [-0.00900, -0.00229] | — |
| without_schedule | 0.22827 | -0.00637 | [-0.00940, -0.00316] | -0.00061 [-0.00161, +0.00021] |
| without_opponent_form | 0.22999 | -0.00466 | [-0.00711, -0.00228] | +0.00110 [-0.00057, +0.00253] |
| without_venue_form | 0.22872 | -0.00592 | [-0.00916, -0.00230] | -0.00016 [-0.00094, +0.00050] |
| operational | 0.23453 | -0.00011 | [-0.00051, +0.00032] | — |
| constant | 0.25003 | +0.01538 | [+0.01120, +0.01952] | — |
