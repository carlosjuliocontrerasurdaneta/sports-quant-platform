# Familia `futbol-europa`: EPL, LaLiga, Bundesliga, Serie A, Ligue 1, UCL

Fecha: 2026-11-10. Prompts en `C:\dev\Prompts\PROMPT_191_{EPL,LALIGA,BUNDESLIGA,SERIE_A,LIGUE_1,UCL}_v1_0.md`. Informes individuales: `docs/prompts-audit/individual/` (mismo nombre). Etiquetas: [COMPROBADO], [INFERENCIA], [HIPÓTESIS], [RECOMENDACIÓN].

## 1. Diff entre los prompts

**Medición.** Líneas de más de 25 caracteres (tras recortar) idénticas entre pares, con un script de Python sobre los seis ficheros: EPL-Ligue 1 10; Serie A-Ligue 1 11; Bundesliga-Serie A 7; Bundesliga-Ligue 1 7; EPL-Serie A 6; EPL-Bundesliga 5; EPL-LaLiga 0; LaLiga-Ligue 1 0; ninguna línea común a los seis. Tamaños: EPL 429, LaLiga 554, Bundesliga 468, Serie A 532, Ligue 1 357, UCL 389.

[COMPROBADO] **No existe una plantilla textual idéntica.** Los seis comparten una *estructura y un contenido matemático* (21 fases, mismas fórmulas, mismas reglas anti-doble-conteo) pero con redacción distinta, por lo que un `diff` no sirve para localizar cambios; hay que comparar semánticamente.

**Núcleo común (mismo contenido, distinta redacción):**
- Principio: ataque/defensa ajustados + rival + localía + portero + once + contexto → λ_home, λ_away → distribución conjunta → probabilidades → congelar → cuotas.
- 21 fases: identificación, ataque, defensa, ajuste por rival, shrinkage/ascendidos, forma, once, portero, balón parado/penales, matchup, descanso, localía/entorno, λ, distribución, 1X2, BTTS/CS, totales, hándicaps, congelación y mercado, confianza/validación, ranking y reporte (EPL las numera 1-21 sin título global; LaLiga, Bundesliga y Ligue 1 las titulan «21 FASES»; Serie A y UCL no lo rotulan).
- Fórmulas: `w = n_eff/(n_eff+tau)`; log-lineal con ataque + debilidad defensiva (+ localía); baseline `λ = LeagueGoals * OffIndex * DefWeakIndex`; `Pois(k;λ)=exp(-λ)λ^k/k!`; Dixon-Coles con los mismos cuatro τ; BTTS, CS, totales con push, hándicap win/push/loss, cuartos por mitades; `EV = P_win*(D-1) - P_loss`, `P_break_even=(1-P_push)/D`, `Edge_precio_pp=100*(P_win-P_break_even)`.
- Estados VALIDADO / EXPLORATORIO / INCOMPLETO; salida parcial sin inventar.
- Ninguno contiene coeficientes entrenados [COMPROBADO]; todos remiten a estimación histórica.

**Qué cambia (propio de cada prompt):**

| Prompt | Rasgo propio |
|---|---|
| EPL | Puente Championship → Premier para ascendidos (P:128); tolerancia 1e-4; Dixon-Coles; huso London; no nombra ascendidos 2026/27 |
| LaLiga | Preservar versión pregame de datos (P:91); combinados BTTS+resultado por intersección (P:295); 42 pruebas bajo «MÍNIMO 35» (P:468); ascendidos Racing de Santander, Deportivo, Málaga (P:151); vestigio «1.02 de localía» (P:76) |
| Bundesliga | Campo `available_at` (P:63); `VERIFICADA/PROVISIONAL/AUSENTE/CONFLICTIVA` (P:95); presión/PPDA; residuos de hockey y QB (P:105, 358); ascendidos Schalke, Elversberg, Paderborn (P:195) |
| Serie A | Cláusula «cuando operas en el modo independiente» (P:21); tolerancia 1e-6; árbitro; `ParameterUncertainty`; ascendidos Venezia, Frosinone, Monza (P:142); «por liga y temporada» (P:456) |
| Ligue 1 | «calibrarlas durante la ejecución» (P:19); control de unidades 0-1/0-100 (P:334); ascendidos «incluyen» Troyes y Le Mans (P:75); sin validación de precio |
| UCL | Módulo de eliminatoria (ida/vuelta/global/ET/penales), fase liga top 8/24, campeón; normalización multiliga; niveles de fallback A-D; sede neutral sin HFA en la final; reglamento 2026/27 |

## 2. Contradicciones entre los prompts

1. [COMPROBADO] **Tolerancia de masa omitida:** 1e-4 (EPL P:217; Bundesliga P:255), «p.ej. 1e-5» (LaLiga P:72), 1e-6 (Serie A P:69; Ligue 1 P:48; UCL P:180). Un factor de 100 entre extremos sobre el mismo objeto matemático.
2. [COMPROBADO] **Renormalización:** EPL prohíbe «renormalizar silenciosamente colas grandes» (P:217); Bundesliga admite renormalizar «solo con justificación numérica» (P:251); UCL «Si se renormaliza tras tolerancia, registrar operación» (P:180); Serie A «indicar el tratamiento» (P:259). Criterios cercanos pero no idénticos.
3. [COMPROBADO] **Cláusula de independencia:** cinco prompts la formulan sin condición; Serie A la condiciona («cuando operas en el modo independiente», P:21) y Ligue 1 limita la prohibición de calibrar a «durante la ejecución» (P:19).
4. [COMPROBADO] **Dimensiones de calidad:** EPL, Ligue 1 y UCL añaden `MarketQuality` o variantes (`CrossLeagueCalibration`, `QualificationModelStatus`); LaLiga y Bundesliga usan cuatro ejes; Serie A cinco con `ParameterUncertainty`; el eje `Uncertainty` cambia de nombre.
5. [COMPROBADO] **Recuento de controles:** EPL 35, Bundesliga 35, Serie A 35, Ligue 1 35, LaLiga «mínimo 35» con 42 listados, UCL 30 «mínimas».
6. [COMPROBADO] **Terminología defensiva:** `defense_weakness`, `DefenseWeakness`, `WeakDefense`, `DefensiveWeakness`, `DefWeakIndex`.
7. [INFERENCIA] **Localía:** EPL y Bundesliga usan interceptos propios `beta_home/beta_away`; LaLiga, Serie A, Ligue 1 y UCL usan intercepto común + `HFA` (o `beta_H`). Ambas son legítimas, pero un solo esquema operativo no vale para los seis sin elegir.
8. [COMPROBADO] **Huso:** London, Madrid, Berlin, Rome, Paris y Zurich: coherente con cada competición. En UCL se elige Zurich como día de competición; es una convención, no un huso del estadio (el prompt convierte luego a huso del estadio).

## 3. Versiones y obsolescencia

- Los seis son «v1.0», diseñados el mismo día (EPL declara 2026-11-10, P:7; los demás no fechan). [COMPROBADO] No hay conflicto de versiones, pero tampoco historial de cambios.
- [HIPÓTESIS] Datos de temporada 2026/27 (ascendidos, formato UCL de 36 clubes con 8 jornadas, art. 13-22 del reglamento) no verificados por esta auditoría contra las fuentes UEFA/ligas; caducan con cada temporada y los prompts lo reconocen («volver a verificar»).
- [COMPROBADO] Contaminación entre deportes en Bundesliga: hockey (P:105) y QB (P:358); LaLiga: vestigio «1.02 de localía» (P:76). Indican reutilización de plantillas de otros prompts (NHL/NFL).
- [INFERENCIA] LaLiga parece la revisión más cuidada (versión pregame de datos, intersecciones para combinados, resultado/BTTS).
- La plataforma cita en la lista de ligas `ucl` y `uwcl` (competición femenina) pero no existe prompt `UCL` femenino en esta familia [COMPROBADO `configs/leagues/soccer.yaml:9, 30`].

## 4. Tabla comparativa de constantes

| Prompt | Líneas | Masa omitida máx. | Equipos / jornadas | Ascendidos 2026/27 | Huso | Fases | Controles | `rho` | Estados | Localía |
|---|---|---|---|---|---|---|---|---|---|---|
| EPL | 429 | 1e-4 (P:217) | 20 (P:95) | no nombrados | Europe/London | 21 | 35 | estimado, τ ≥ 0 | V/E/I | `beta_home`/`beta_away` |
| LaLiga | 554 | 1e-5 «p.ej.» (P:72) | 20 / 38 (P:101) | Racing, Deportivo, Málaga | Europe/Madrid | 21 | 42 («mín. 35») | MLE, «jamás fijar» | V/E/I | `β_HFA` |
| Bundesliga | 468 | 1e-4 (P:255) | 18 / 34 (P:77) | Schalke 04, Elversberg, Paderborn | Europe/Berlin | 21 | 35 | datos de Bundesliga | V/E/I | `beta0_home/away` |
| Serie A | 532 | 1e-6 (P:69) | n/d | Venezia, Frosinone, Monza | Europe/Rome | 21 | 35 | entrenado para Serie A | V/E/I | `beta_HFA` |
| Ligue 1 | 357 | 1e-6 (P:48) | 18 / 34 (P:75) | «incluyen» Troyes y Le Mans | Europe/Paris | 21 | 35 | datos de Ligue 1 | V/E/I | `beta_H` |
| UCL | 389 | 1e-6 (P:180) | 36 clubes, 8 rivales (P:73) | n/a | Europe/Zurich | 21 | 30 | estimado | V/E/I | `HFA_g` (0 en final) |

Valores de producción de la plataforma para cada competición, de `configs/leagues/soccer.yaml:4-9`, `configs/leagues/ratings.yaml` y `src/sqp/sports/registry.py:45-47`:

| Liga | `avg_goals` | `dc_rho` | `elo_home_adv` | `max_score` | `tilt_scale` | `home_scoring_bonus` |
|---|---|---|---|---|---|---|
| epl | 2.80 | -0.2 | 15.0 | 10 | 1.0 | 0.15 |
| laliga | 2.65 | 0.0 (default) | 48 (default) | 10 | 1.0 | 0.15 |
| bundesliga | 3.20 | -0.2 | 15.0 | 10 | 1.0 | 0.15 |
| seriea | 2.53 | -0.2 | 15.0 | 10 | 1.0 | 0.15 |
| ligue1 | 2.84 | 0.0 (default) | 48 (default) | 10 | 1.0 | 0.15 |
| ucl | 3.37 | 0.0 (default) | 48 (default) | 10 | 1.0 | 0.15 |

[COMPROBADO] Solo EPL, Bundesliga y Serie A tienen `dc_rho` y `elo_home_adv` propios; LaLiga, Ligue 1 y UCL usan el default de la familia. [INFERENCIA] Esa asimetría de configuración (tres ligas con 15, tres con 48) no está justificada en los ficheros que leí.

## 5. Hallazgos transversales sobre el mercado

- Los seis prompts respetan el principio: cuotas solo tras congelar; líneas como umbral legítimas; CLV tras cierre. Dos matices de redacción: Serie A P:21 y Ligue 1 P:19 [RECOMENDACIÓN: hacerlos incondicionales].
- La plataforma, no los prompts, mezcla mercado: `market_shrink 0.5` (`configs/default.yaml:17`; `src/sqp/pipeline/probabilities.py:303-304`) sobre las seis ligas.
