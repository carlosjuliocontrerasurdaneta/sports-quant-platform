# Auditoría individual: PROMPT_191_UCL_v1_0

Fecha: 2026-11-10. Citas `P:n` = líneas de `C:\dev\Prompts\PROMPT_191_UCL_v1_0.md`.

## 1. Ficha

- **Fichero / versión:** PROMPT_191_UCL_v1_0.md; «PROMPT 191-UCL v1.0» [COMPROBADO P:1].
- **Deporte / competición:** fútbol; UEFA Champions League masculina (clasificatorias solo si se verifica su reglamento) [P:3].
- **Tamaño:** 389 líneas.
- **Rol:** motor de predicción pregame de UCL [P:13].
- **Objetivo:** distinguir tres productos: `PARTIDO_90`, `CLASIFICACIÓN` (eliminatoria) y `CAMPEÓN` [P:15-19]. Mercados: 1X2, doble oportunidad, DNB, hándicap europeo/asiático, totales, BTTS, marcador exacto; clasificación/campeón solo con módulo eliminatorio válido [P:5].
- **Alcance / modos:** estados VALIDADO / EXPLORATORIO / INCOMPLETO [P:235-239]; niveles de fallback A-D [P:273-281]; log-lineal multiliga o fallback exploratorio [P:142-158]; Poisson o DC [P:164-180].
- **Afirmación de verificación:** «Base reglamentaria verificada: Reglamento UEFA Champions League 2026/27, artículos 13–22» [P:7]. [HIPÓTESIS] No verificada por esta auditoría (sin acceso a la fuente; la fecha de hoy es 2026-11-10 y mi conocimiento llega hasta junio de 2026).

## 2. Reglas y restricciones

- **Absolutas (15) [P:35-49]:** no inventar [P:35]; as-of [P:36]; verificar temporada y reglamento [P:37]; normalizar entre ligas [P:38]; **coeficientes UEFA, seed, Elo externo o fama no son probabilidad; un rating histórico puede servir de prior si se documenta y «no utiliza precios de mercado»** [P:39]; no mezclar proveedores [P:40]; 90' + descuento para mercados estándar [P:42]; **«no usar goles de visitante como desempate» en 2026/27** [P:43]; sin cuota no hay edge/EV [P:46]; CLV observado solo con apertura y cierre [P:47]; clasificación requiere modelar todos los encuentros pendientes [P:48].
- **«Validado» [P:237, 269]:** split temporal rolling/expanding, registros as-of, comparación con Poisson simple, DC y ratings nacionales; Brier y log loss 1X2, calibración de empates, log-verosimilitud de marcadores, error de λ, cobertura de intervalos, ablaciones, rendimiento por fases y fuerza de liga, ROI/CLV observados si hay cuotas históricas de calidad.
- **Pruebas:** «MÍNIMAS» 30 [P:336-367].
- **Abstención:** niveles A-D; en el D «no generar probabilidades artificiales» [P:281].

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Línea | Justificación |
|---|---|---|---|---|
| Masa fuera de la malla | `1 - suma(matriz) ≤ 1e-6` | masa | P:180 | Declarada |
| Prueba de masa | `sum P(h,a) >= 0.999999` | masa | P:345 | Coherente con 1e-6 |
| Fase liga | 36 clubes, 8 rivales (4 L/4 V), top 8 → octavos, 9-24 → playoff, 25-36 eliminados | – | P:73 | «sujeto a verificación de edición» |
| Eliminatorias | 2 partidos salvo final; ET 2×15 min; penales | – | P:73, 219 | Reglamento 2026/27 (no verificado) |
| Desempate | sin goles de visitante | – | P:43, 219 | Regla UEFA |
| HFA en final | `0` en la base | – | P:138 | Sede neutral |
| `tau`, `rho_DC`, `alpha_comp`, `HFA_g`, `beta0` | no fijados | – | P:93-97, 106, 178 | Estimar |
| Huso de selección de fecha | `Europe/Zurich` | – | P:75 | Convención (sede UEFA) |
| Escala común europea | exigida | – | P:91-99 | Sin valores |
| λ de prórroga | «no multiplicar λ90 por 1/3 sin marcar hipótesis» | – | P:225 | Fallback marcado |

[COMPROBADO] No hay coeficientes entrenados. [INFERENCIA] Las cifras estructurales (36, 8, 4/4, 8, 9-24, 25-36) proceden de un reglamento citado pero no auditado.

## 4. Fuentes de datos

Jerarquía [P:55-63]: A) oficiales UEFA.com y reglamentos; B) estadísticas Opta/The Analyst y proveedores xG compatibles; C) contexto (disponibilidad, alineaciones, clima, techo); D) mercado «SOLO AL FINAL». Registro mínimo con `sample_minutes`, `provider_definition`, `status`, `fallback`, `uncertainty`, `published_at` [P:65]. Referencias: documentos UEFA arts. 17, 19, 20, 21, 22 [P:373-378]. Sin antigüedad máxima. [INFERENCIA] Conectividad entre ligas (partidos interliga) es la fuente real de la fuerza común [P:97]; el prompt no cuantifica el número mínimo de cruces.

## 5. Cadena predictiva

1. Identificación de fase, pierna, sede efectiva [P:69-77].
2. Datos de ataque/defensa por club (xG, npxG, tiros, sede) [P:79-87].
3. **Normalización entre ligas** (núcleo diferencial) [P:89-99]:
   `log(lambda_i,g) = alpha_comp,g + attack_club_i - defense_club_j + HFA_g + context_i,g` [P:94]; modelo jerárquico multiliga con efectos por liga, club y temporada; si no, `CrossLeagueStrength=NO IDENTIFICABLE` [P:99].
4. Regularización: `w = n_eff / (n_eff + tau)`, `theta_post = w * theta_observada + (1-w) * theta_prior` [P:105-106].
5. Forma, XI, portero, balón parado, matchup, descanso/viajes, localía/estadio [P:110-138].
6. λ [P:144-147]:
   `eta_H = beta0 + Attack_H + DefenseWeakness_A + HFA + Context_H`
   `eta_A = beta0 + Attack_A + DefenseWeakness_H + Context_A`
   `lambda_H = exp(eta_H)`, `lambda_A = exp(eta_A)`.
   Fallback: `lambda_H = EuropeGoalsHome * OffIndex_H * DefWeakIndex_A`, etc. [P:153-156].
7. Distribución: `P(H=h, A=a) = Pois(h;lambda_H)*Pois(a;lambda_A)` [P:164]; DC `P_DC = P_Pois * tau` con τ(0,0)=1−λHλAρ, τ(0,1)=1+λHρ, τ(1,0)=1+λAρ, τ(1,1)=1−ρ [P:170-176].
8. Derivados [P:184-213]: `P_H_90 = Σ_{h>a} P(h,a)`, `P_X_90`, `P_A_90`; BTTS; CS; totales con push; hándicap con win/push/loss y cuartos por líneas adyacentes de 0,5 (`h = (h_low+h_high)/2`).
9. **Módulo de eliminatoria [P:215-229]:** si faltan ambas piernas, simular ambas conjuntamente; si ya se jugó la ida, condicionar al marcador observado, «NO volver a simular la ida»; global empatado tras 90' de la vuelta → prórroga (modelo de 30') → penales con modelo explícito o prior; sin esos elementos, `clasificación = NO CALCULABLE`.
10. Fase liga (top 8/24) y campeón: simulación de todo el calendario restante y el bracket [P:227-229].
11. Congelación [P:233] y mercado [P:247-261].

Empate: resultado en 90'; en eliminatoria, ET y penales. Monte Carlo: obligatorio para clasificación, fase liga y campeón con semilla y N [P:233, 362]. Mercados que produce: 1X2, BTTS, totales, hándicap, DNB, doble oportunidad, clasificación (condicional); no team totals.

## 6. Auditoría matemática

- [COMPROBADO] τ correcto [P:172-176]; «`rho_DC` no es coeficiente de correlación Pearson» [P:178]; exige τ ≥ 0 y masa normalizada.
- **Fuerza común entre ligas.** [INFERENCIA] El enfoque jerárquico con efectos por liga es el estándar defendible; su identificabilidad depende de los cruces UEFA, que son pocos por temporada. El prompt lo reconoce y define la salida `NO IDENTIFICABLE` en lugar de inventar multiplicadores [P:99, 158]: acertado.
- **Eliminatoria.** [INFERENCIA] La clasificación no es separable por pierna: el prompt exige simulación conjunta y condicionar a la ida realizada [P:221-223]; correcto. [COMPROBADO] El prompt avisa de no escalar λ90 por 1/3 sin marcar hipótesis [P:225]. [INFERENCIA] No define el modelo de penales (probabilidad por lanzamiento, efecto de portero); sin esos elementos manda `NO CALCULABLE`, lo que es honesto pero deja el módulo sin especificación ejecutable.
- **Coherencia.** 1X2 suma 1 y empate propio [P:42, 188, 347-348]; clasificación suma 1 solo si ET+penales están modelados [P:359]. EV: `EV = P_win*(D-1)-P_loss`, `P_break_even = (1-P_push)/D`, 1X2 `1/D`, `Edge_precio_pp = 100*(P_win-P_break_even)` [P:251-255]: correctos.
- **Doble conteo / HFA.** `HFA_g` por competición y «HFA de club/competición/estadio calibrada» [P:138]; [INFERENCIA] el prompt habla de HFA por club, estadio y competición a la vez sin decir cuál prevalece; riesgo de triple parametrización.
- **Regla de goles de visitante** [P:43, 219, 357]: coherente en todo el documento.
- Coeficientes sin justificar: ninguno. Sobreajuste: la jerarquía de efectos (liga, club, temporada, competición) tiene muchos parámetros con pocos datos interliga [INFERENCIA]; el prompt exige regularización y ablaciones [P:105, 269].
- Fuga temporal: as-of [P:36]; «Controlar sesgo de selección y cambios de reglamento» [P:269]; prueba «Backtest cronológico, no división aleatoria» [P:365].
- Faltantes: niveles A-D [P:273-281]; «NO CALCULABLE», «SIN DATOS», «SIN LÍNEA» [P:332]. Incertidumbre: cuantificada o no; MC no equivale a incertidumbre total [P:243].
- Líneas hipotéticas: «líneas de evaluación hipotéticas etiquetadas como tales, sin tratarlas como cuotas» [P:201]: bien.

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| P:13, 29, 61 | Cuotas solo tras congelar; «NO entran en ratings, goles esperados, dispersión, localía o probabilidades» | Regla |
| P:39 | Rating histórico/Elo externo como prior si «no utiliza precios de mercado» | Condición de pureza; [INFERENCIA] exige auditar el origen del Elo externo |
| P:201 | Líneas hipotéticas no son cuotas | UMBRAL LEGÍTIMO |
| P:205-213, 207 | Líneas de total y hándicap | UMBRAL LEGÍTIMO |
| P:247-261 | EV, edge, CLV, devig | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:269 | «ROI/CLV observados cuando existan cuotas históricas de calidad» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:283 | Ausencia de cuotas no autoriza inventar datos | Regla |
| P:267 | Ranking económico solo con precio | COMPARACIÓN POSTERIOR LEGÍTIMA |

[COMPROBADO] Sin ENTRADA PROHIBIDA. Congela antes de consultar [P:233, 247]. [INFERENCIA] Matiz: el Elo externo de P:39 podría provenir de sistemas que usan precios; el prompt ya lo condiciona.

## 8. Validación que propone

Split temporal rolling/expanding; Poisson simple, DC y ratings nacionales como baselines; Brier, log loss, calibración de empates, log-verosimilitud, error de λ, cobertura de intervalos, ablaciones por fuente/portero/alineaciones/ajuste interligas; rendimiento por fase y por fuerza de liga; ROI/CLV observados; control de sesgo de selección y cambios de reglamento [P:269]. [INFERENCIA] Es la validación más completa de la familia; carece de umbrales numéricos y del tamaño muestral mínimo (UCL tiene pocos partidos por temporada, 144 en fase liga según el formato citado (36 × 8 / 2) más eliminatorias [HIPÓTESIS: derivada de P:73, no verificada]).

## 9. Contraste con la plataforma

- **Implementado:** partido a 90' con Poisson/DC (`src/sqp/models/distributions.py:204`), tres vías (`src/sqp/sports/adapters.py:314-316`).
- **Valores de producción UCL:** `avg_goals 3.37` [`configs/leagues/soccer.yaml:9`]; sin entrada en `ratings.yaml` (solo bundesliga, epl, seriea: l.11, 14, 52) → hereda `dc_rho 0.0`, `elo_home_adv 48`, `tilt_scale 1.0`, `max_score 10`, `home_scoring_bonus 0.15`, `elo_k 18` [`registry.py:45-47`].
- **Falta (COMPROBADO por búsqueda en `src/sqp`, sin hallazgos):** módulo de clasificación (ida/vuelta/global/ET/penales), simulación de fase liga y de campeón, regla de visitante, ratings en escala común europea, sede neutral en el pricing del adaptador (`adapters.py:128` llama a `rating_diff(event.home, event.away)` sin pasar `neutral`; el Elo admite `neutral`: `src/sqp/models/elo.py:66-75`).
- **Difiere:** la liga `ucl` es una entrada más de `soccer.yaml` con su propio historial de resultados y Elo; [INFERENCIA] sin ratings que conecten los clubes con sus ligas domésticas (ni efectos por liga), la fuerza de un club en UCL solo se aprende de sus partidos UCL, es decir, no hay escala común europea y la muestra por club es mínima. Mismos puntos de las otras ligas: sin xG/once/portero; localía doble Elo 48 + bonus 0,15 [INFERENCIA]; malla a 10 renormalizada (`distributions.py:294`).
- **Mercado en las probabilidades:** el adaptador no usa cuotas; `market_shrink 0.5` mezcla el no-vig en `p_used` [`configs/default.yaml:17`; `probabilities.py:303-304`; `daily.py:969-970`]; `.env` no verificable. Calibradores pre-blend (`probabilities.py:285-296`).

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Separación PARTIDO_90 / CLASIFICACIÓN / CAMPEÓN | CONSERVAR | Evita el error central de UCL |
| Normalización multiliga con `NO IDENTIFICABLE` | CONSERVAR | Honesto y estándar |
| Módulo de eliminatorias | INTEGRAR | La plataforma no lo tiene; especificar modelo de ET y penales |
| «Base reglamentaria verificada» (P:7) | CORREGIR | No auditable; citar fecha de consulta |
| Elo externo como prior (P:39) | OPTIMIZAR | Exigir procedencia sin precios |
| HFA por club/estadio/competición (P:138) | CORREGIR | Fijar jerarquía de parámetros |
| Neutralidad en la final en la plataforma | INTEGRAR | Pasar `neutral` al Elo |
| Escala común europea en la plataforma | INTEGRAR | Requiere datos interliga |
| Pruebas «mínimas» 30 | OPTIMIZAR | Alinear con las 35 de otros prompts |
