# Auditoría: PROMPT_191_NHL_v1_0.md

Fecha: 2026-11-10. Solo lectura sobre la plataforma; no se ejecutó ningún script de `scripts/research/`. Etiquetas: [COMPROBADO] [INFERENCIA] [HIPÓTESIS] [RECOMENDACIÓN].

## 1. Ficha

| Campo | Valor |
|---|---|
| Fichero | `C:\dev\Prompts\PROMPT_191_NHL_v1_0.md` |
| Versión | «PROMPT 191-NHL v1.0» (NHL:1) |
| Deporte / competición | Hockey sobre hielo, NHL (REG y PLAYOFF) |
| Tamaño | 632 líneas, 35.261 bytes |
| Rol | Sistema cuantitativo pregame; proyecta la distribución conjunta de goles por estado de juego; compara con cuotas solo después (NHL:12) |
| Estado inicial | EXPLORATORIO hasta calibración OOS (NHL:5) |
| Mercados | 1X2 en 60 min, ML 2 vías con OT/SO, Puck Line ±1,5 y alternativos, Totales reglamentarios/finales, team totals «cuando existan líneas verificadas» (NHL:4) |
| Estructura | 20 reglas absolutas (NHL:42-61), 21 fases (NHL:111-487), formato de salida (NHL:489-564), 30 invariantes (NHL:566-597), validación (NHL:601-613) |
| Modos | VALIDADO / EXPLORATORIO / INCOMPLETO (NHL:414, 419-428) |

Versiones: [COMPROBADO] solo existe v1.0 en `C:\dev\Prompts`. En el worktree `.claude/worktrees/agent-a2bc3d835b878219b/docs/prompts/prompt-nhl-pricing-v3.md` hay otro motor NHL «v3» anterior (inventario de la plataforma); [HIPÓTESIS] el v1.0 auditado pertenece a una generación nueva de prompts (21 ficheros uniformes) y no es continuación de aquel.

## 2. Reglas y restricciones

Reglas absolutas (NHL:42-61), las más relevantes:
- No inventar datos (42); información disponible antes del puck drop con `as_of_utc` y `published_at_utc` (43).
- No mezclar 5v5 / all situations / 5v4 / EN / per 60 sin conversión (46); no aplicar dos veces localía, portero, lesiones, ST o EN (47).
- Portero desconocido → escenarios, no intuición (48). Poisson independiente solo como baseline (49).
- Empate en 60 min existe en el 1X2 (51). REG: OT 3v3 de 5 min + SO; PLAYOFF: OT 20 min 5v5 muerte súbita (52).
- Registrar por separado `score_reg`, `score_after_OT`, `winner_SO`, `score_final_official`, `score_for_settlement` (53); gol de SO cuenta uno solo (54).
- Pesos/varianzas/tamaños de muestra «deben provenir de entrenamiento/backtesting o etiquetarse como supuestos EXPLORATORIOS» (59).
- Sin cuotas no hay edge ni EV; la distancia a 50 % no es valor (56).
- NHL:36: «El mercado es únicamente un benchmark económico posterior».

Excepciones (NHL:477-485): partido iniciado, portero no confirmado, xG no disponible, sin PP/PK. Condiciones de «VALIDADO» (NHL:419-428): walk-forward, Brier/Log Loss en 2-way y 1X2, calibración por buckets, ablaciones (5v5, +portero, +PP/PK, +roster, +EN, +contexto, +OT/SO), comparación con baseline y mercado sin margen exclusivamente para evaluación.

## 3. Variables y parámetros

[COMPROBADO] El prompt NO fija casi ninguna constante numérica; es deliberadamente un esqueleto sin coeficientes (NHL:98 «Prohibido fijar como universales…», NHL:59, 94). Tabla de lo que sí aparece:

| Nombre | Valor | Unidad | Línea | Justificación |
|---|---|---|---|---|
| Duración de regulación | 60 | min | 8, 301 | Reglamentaria |
| Periodos | 3 × 20 | min | 321 | Reglamentaria |
| OT REG | 5:00, 3v3, muerte súbita | min | 356 | Reglamentaria |
| Rondas SO | 3 + muerte súbita | rondas | 357 | Reglamentaria |
| OT PLAYOFF | 20 min 5v5 | min | 361 | Reglamentaria |
| `rho` (dependencia de goles) | no fijar 0,12 | — | 94, 274 | Prohíbe el valor «0,12» sin validación NHL |
| `tau_s` (regularización) | «por estimar» | TOI | 100-107 | Sin valor |
| `w_s = TOI_s/(TOI_s+tau_s)` | fórmula | peso | 102-105 | Sin tau |
| `β_G` (portero) | «debe entrenarse» | — | 191 | Sin valor |
| `HFA` | «estimado con datos NHL, aplicado una vez» | — | 95 | Sin valor |
| `MC_N` | «realmente ejecutado»; error MC objetivo <0,5 pp | iteraciones | 96, 344 | Orientativo |
| Penalizaciones por equipo | «no fijar cuatro PP por defecto» | — | 237 | Sin valor |
| Tolerancias de invariantes | «dentro de tolerancia numérica» | — | 580-583 | Sin valor |

Las fórmulas con parámetros libres son lo único «numérico». [INFERENCIA] Esto lo hace inmune a «constantes inventadas», pero también no ejecutable: para correr necesita un `model_config` que el prompt no define.

## 4. Fuentes de datos

Jerarquía (NHL:67-79): (1) NHL.com/gamecenter/NHL Stats (calendario, estado, reglas, eventos, alineaciones/porteros oficiales); (2) MoneyPuck, Natural Stat Trick, Evolving-Hockey (xGF/xGA, GSAx, 5v5, ST); (3) reportes de equipos y periodistas (disponibilidad, titularidad de porteros); (4) contexto (viaje, descanso, altitud; viento exterior prohibido para pista cerrada, NHL:72, 248); (5) sportsbooks solo tras congelar. Documentar por campo: valor, unidad, proveedor, enlace, periodo, situación, muestra, `fetched_at_utc`, `as_of_utc`, calidad, fallback (NHL:75). Conflictos: la fuente oficial manda en identidad/reglas; fuente estadística elegida para su métrica; la confirmatoria más reciente para porteros; si persiste, escenarios (NHL:79). Frescura: exige snapshots a varios cortes (mañana, 60 min antes, porteros confirmados) (NHL:607). [COMPROBADO] Cita atribución y licencia (NHL:77, 623).

## 5. Cadena predictiva

Esquema (NHL:25-34): ataque/defensa 5v5 + tiros/calidad + porteros + PP/PK + disciplina + lineups + descanso + localía + contexto → tasas por estado → minutos por estado → goles esperados y evolución del marcador en 60 min → 1X2 → OT/SO → distribución final → ML/PL/Totales.

Fórmulas literales:
- Regularización (NHL:102-105): `w_s = TOI_s / (TOI_s + tau_s)`; `Rate_reg_s = w_s * Rate_observada_s + (1 - w_s) * Rate_prior_s`.
- 5v5 (NHL:164-165): `λ_home_5v5_base = xGF60_home_reg * xGA60_away_reg / League_xG60_5v5`; `λ_away_5v5_base = xGF60_away_reg * xGA60_home_reg / League_xG60_5v5`.
- Portero (NHL:188): `λ_goals_{i,s} = λ_xG_{i,s} * exp(-β_G * GSAx60_opponent_reg)`.
- PP (NHL:219-220): `λ_home_PP = xGF60_PP_home_reg * xGA60_PK_away_reg / League_xG60_PP` y simétrica.
- Tasa general (NHL:281-282): `λ_{i,s} = f(attack_{i,s}, defense_{j,s}, goalie_j, lineup_i, matchup_{i,j}, context, finishing_i)`.
- Regulación (NHL:300): `μ_i_reg_base = Σ_s [ E(T_s) / 60 * λ_{i,s} ]`.
- 1X2 (NHL:372-375): `P_home_60 = P(H_reg > A_reg)`, `P_draw_60 = P(H_reg = A_reg)`, `P_away_60 = P(H_reg < A_reg)`.
- ML 2 vías (NHL:381-383): `P_home_FT = P(H_final > A_final)`.
- PL (NHL:389-391): `P_cover = P(G_equipo_settlement + h > G_rival_settlement)`; `P_push`, `P_loss = 1 - P_cover - P_push`.
- Totales (NHL:399-402): `P_over = P(G_home + G_away > t)`, etc.
- EV (NHL:456-458): `EV = P_win*(D-1) - P_loss`; `P_break_even_unconditional = (1-P_push)/D`; `Edge_precio_pp = 100*[P_win - (1-P_push)/D]`.

Distribuciones: no fija. Poisson/NB univariada solo como «comparador EXPLORATORIO» (NHL:274, 339); método preferido: simulador por eventos con estados de ventaja numérica, reloj, marcador, portero, líneas y portería vacía (NHL:335). Dependencia: se debe estimar, no fijar (NHL:274). Prórroga/empate: simulación explícita de OT 3v3 (REG) y SO (3 rondas + muerte súbita), o OT 20 min 5v5 (PLAYOFF) (NHL:352-365). Monte Carlo: semilla explícita, error <0,5 pp, pares enteros (NHL:343-346). Mercados: 1X2 60 min, ML FT, PL ±1,5 y alternativos, Totales (reg y FT), team totals mencionados (NHL:4, 451) pero sin fase propia. El `E(T_s)` de minutos de PP no tiene modelo (NHL:231 «derivar una distribución…»).

## 6. Auditoría matemática

- [COMPROBADO] Las fórmulas multiplicativas `xGF·xGA/League` (NHL:164-165, 219-220) son el baseline estándar (log-lineal) y suponen escala consistente; el prompt lo advierte (NHL:168).
- [INFERENCIA] Defecto de coherencia: NHL:165 usa `xGF60_away_reg * xGA60_home_reg`, es decir la mitad de ataque del visitante con la defensa del local; correcto. Pero `λ_5v5` es **por 60 min de 5v5**, y NHL:300 la multiplica por `E(T_s)/60`; bien definido, aunque `T_5v5` = 60 − tiempo de ST y la suma de estados exige el invariante 5 (NHL:571). Estable.
- [INFERENCIA] La fórmula de portero `exp(-β_G·GSAx60_opp)` (NHL:188) multiplica **xG a goles**; correcto estructuralmente y es el mismo diseño que la plataforma (multiplicador acotado sobre la lambda del rival, `adapters.py:309-312`). Pero `GSAx60` es suma de goles evitados por 60 min; usar su exponencial como multiplicador de λ en goles/60 mezcla dimensiones (goles/60 restados a un log-multiplicador sin escala) a no ser que β_G absorba las unidades. [HIPÓTESIS] La plataforma normaliza por `(1-L)` (`goalies.py:20-22`: `f=clip(1-β·q/(1-L_D))`), que da un significado directo (fracción de goles); más sólido.
- [COMPROBADO] Coherencia 1X2 vs 2 vías: el prompt separa `score_reg` de `score_final_official` (NHL:53) y exige que el ML FT sume 1 (NHL:383, 582) y que PL −1,5 FT no se cubra con victoria en OT/SO por un gol (NHL:587). Es lo correcto: un gol de SO suma 1.
- [INFERENCIA] El gol de SO como «un solo gol al vencedor» es correcto para marcador oficial, pero el modelo de regulación de goles estimado sobre marcadores finales (como hace la plataforma) ya contiene ese gol; el prompt trabaja sobre regulación pura (60 min) y lo separa, lo cual es más limpio que la plataforma (ver §9).
- [INFERENCIA] Empty net: bien identificado como determinante de PL −1,5 y Over (NHL:329); sin parámetros, no es calculable sin un simulador por eventos que hoy no existe.
- [COMPROBADO] Trata el push: `P_push` presente en PL y Totales. [INFERENCIA] Con líneas ±1,5 y t medio-entero el push es 0; el prompt lo deja general.
- Coeficientes sin justificar: ninguno inventado (positivo); pero todos los necesarios («tau_s», «β_G», HFA, dispersión) están vacíos. [HIPÓTESIS] Un operador que dé estos valores «a ojo» reintroduciría el problema que el prompt quiere evitar.
- Sobreajuste: el listado de ablaciones (NHL:426) y fases (21) sugiere un modelo de >100 grados de libertad sobre ~1.300 partidos/temporada. [INFERENCIA] Sin regularización dura ni selección por validación temporal anidada, el riesgo es alto; la plataforma, que midió solo tres ajustes (tilt, descanso, portero), va por el camino contrario (mínimo de complejidad).
- Fuga temporal: bien cubierta (NHL:43, 153, 570, 595). [INFERENCIA] Hay riesgo específico: porteros «confirmados tarde» en backtest (NHL:423, 595 lo prohíbe), que es justo lo que el preregistro de la plataforma resuelve con la medida M1 (portero real) frente a M2 (proxy: último titular).
- Datos faltantes: política de fallback explícito (NHL:58, 477-485); [INFERENCIA] «Sin PP/PK: prior de liga» y «xG no disponible: baseline de goles o tiros» son opciones válidas, con pérdida de fiabilidad declarada.

## 7. Independencia del mercado

| Cita | Contenido | Clasificación |
|---|---|---|
| NHL:6, 36 | Regla de independencia; mercado solo benchmark posterior | Regla correcta |
| NHL:12 | «Después de cerrar y registrar las probabilidades… compara contra líneas reales» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| NHL:15 | Sin cuotas no hay edge | Regla |
| NHL:451 (fase 20) | Libro, mercado, línea, cuota, timestamp | COMPARACIÓN POSTERIOR LEGÍTIMA |
| NHL:389-405 (PL, Totales con t y h) | Línea h / t como umbral | UMBRAL LEGÍTIMO |
| NHL:394 | Línea teórica «etiquetada sin cuota» | UMBRAL LEGÍTIMO |
| NHL:428 | Comparación con mercado sin margen «exclusivamente evaluación» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| NHL:432-445 (fase 19) | Congelación antes de consultar mercado | Congelación explícita |
| NHL:461-465 | De-vig, CLV observado solo con cierre | COMPARACIÓN POSTERIOR LEGÍTIMA |
| NHL:595 (invariante 25) | «La fuente de los odds no alimenta las variables deportivas previas» | Regla |
| NHL:609 | ROI y CLV como medidas económicas secundarias | COMPARACIÓN POSTERIOR LEGÍTIMA |

[COMPROBADO] Ninguna ENTRADA PROHIBIDA. [COMPROBADO] Congela antes de consultar (fase 19 antes de 20, NHL:432-449). [INFERENCIA] Como en el MLB, no prohíbe elegir hiperparámetros por ROI/CLV en backtest; NHL:609 los trata como «secundarios», lo que ayuda.

## 8. Validación propuesta

NHL:419-428 y 601-613: entrenamiento y validación walk-forward rolling-origin; Brier y Log Loss (ML 2 vías y 1X2); calibración por buckets; MAE/RMSE de goles; log-verosimilitud de la distribución conjunta; resultados de Over/Under y PL; ablaciones (5v5; +portero; +PP/PK; +roster; +EN; +contexto; +OT/SO); estabilidad por temporada, totales bajos/altos, OT y underdogs; comparación con baseline y mercado sin margen (solo evaluación). 30 invariantes automáticos (NHL:566-597). [INFERENCIA] Más completo que el MLB, pero igual sin umbrales numéricos de aceptación. [RECOMENDACIÓN] Un pre-registro como el del portero (Δ log loss, IC95 bootstrap, criterios simultáneos), `docs/research/2026-09-26-preregistro-portero-nhl.md:343-382` (sección 8).

## 9. Contraste con la plataforma

| Componente del prompt | Plataforma | Estado |
|---|---|---|
| Modelo de goles | `HockeyAdapter(PoissonAdapter)` (`adapters.py:276`), Poisson con `dispersion_k` ausente (`registry.py:43-44`, el comentario `registry.py:38` mide 1,01 en hockey) | PARCIAL: Poisson por equipo, sin estados de juego, sin PP/PK, sin EN |
| Escala | `avg_total=6,1` constante (`registry.py:43`), matizada por tasas de equipo (`team_scoring.py:92-101`) | DIFIERE: sin xG, ni 5v5 por 60 |
| Reparto local/visitante | Elo → `tilt`, con `tilt_scale=0,439` en producción (`ratings.yaml:50`; antes 0,9 de `registry.py:43`) y `elo_home_adv=15` (`ratings.yaml:44`) | DIFIERE (Elo, no xGF/xGA) |
| Portero | `goalie_beta` (default 0,0) en `adapters.py:292`, factor `GoalieRatings.factor` (`goalies.py`), prior `goalie_prior_shots`, `goalie_bound=0,35` por defecto (`adapters.py:293-294`); observer no se alimenta con β=0 (`adapters.py:298`) | IMPLEMENTADO e INACTIVO (β=0: no figura en `ratings.yaml`; pre-registro `docs/research/2026-09-26-preregistro-portero-nhl.md`) |
| Descanso | `RestModel`, `rest_elo_per_day=0,0` (`adapters.py:~48`); NHL no figura en `ratings.yaml` con él | IMPLEMENTADO e inactivo |
| Regulación vs final | `TIE_ADDS_GOAL=True` (`adapters.py:288`): un empate reglamentario siempre termina con un gol más; las tasas se reescalan para que el total FINAL coincida (`distributions.py:219-238`) | DIFIERE: la plataforma modela marcador FINAL de 2 vías con ajuste ad hoc de empate; no separa 1X2 de 60 min, ni OT/SO, ni playoffs |
| 1X2 de 60 min | No hay (`three_way` es de fútbol: `adapters.py:316`) | FALTA |
| Puck line / Totales | `poisson_match_probs` con líneas asiáticas; PL −1,5 sobre marcador final con tie-adds-goal (`distributions.py:204-264`) | IMPLEMENTADO (final, no 60 min) |
| Empty net | No | FALTA |
| Estados PP/PK, disciplina | No | FALTA |
| xG, GSAx | La plataforma usa SV% y tiros (`goalies.py:20-22`: `e_g = SV_g − SA_g·L_g`) | DIFIERE: no usa xG, exceso de paradas sobre liga |
| Playoffs | No hay tratamiento (REG y PLAYOFF mezclados) | FALTA |
| Team totals | Derivados MLB en curso; NHL no | FALTA |
| Congelación | `model_probability`/`adjusted_probability` guardadas (`daily.py:1031`) | IMPLEMENTADO |

**Uso de mercado en la construcción de las probabilidades NHL de la plataforma:**
- [COMPROBADO] Misma capa que MLB: `market_shrink: 0.5` (`default.yaml:17`) aplicado a `p_decision` (`probabilities.py:304-305`), `uncertainty_penalty: 0.35` (`default.yaml:26`). ENTRADA PROHIBIDA en la decisión (la probabilidad estimada pura queda en `model_probability`, `daily.py:1031`).
- [COMPROBADO] La activación de `tilt_scale` 0,439 en NHL se hizo con pre-registro por log loss frente a resultados, no por ROI (`ratings.yaml:45-50`: «log loss −0,0197 frente a 0,9… bate al modelo constante»). Sin mercado.
- [INFERENCIA] El portero pre-registrado mide Δ log loss frente a resultados (`preregistro-portero-nhl.md` §8), también sin mercado. Cumple el principio de independencia.
- [COMPROBADO] `registry.py:90` («NHL comparte el mecanismo… la ganancia en totals se compensa con spreads y moneyline») se refiere a medición de Brier, no a precios.

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Reglas absolutas e invariantes (NHL:42-61, 566-597) | CONSERVAR | Muy superior como lista de control; cubre OT/SO/playoffs |
| Separación `score_reg` / `score_for_settlement` | INTEGRAR | La plataforma no distingue 1X2 de 60 min |
| Congelación y comparación posterior (F19-20) | CONSERVAR | Cumple el principio rector |
| Baseline xGF·xGA/League (F4, F7) | OPTIMIZAR | Requiere xG de proveedor y datos 5v5 que la plataforma no ingiere; medir antes |
| Factor de portero `exp(-β·GSAx60)` (F5) | CORREGIR | Mejor la forma de la plataforma `1-β·q/(1-L)` (`goalies.py`); misma estructura, pero unidades más claras |
| Estados PP/PK y disciplina (F7-8) | INTEGRAR (gated) | Faltan datos y modelo; alto coste, ganancia no medida |
| Empty net (F14) | INTEGRAR (gated) | Relevante en PL −1,5 y Over; hoy no modelado |
| OT/SO por reglas, playoffs sin SO (F16) | INTEGRAR | La plataforma usa el truco del gol extra para 2 vías |
| `rho`, dispersión, HFA | OPTIMIZAR | Sin valor; medir en NHL (`registry.py:38` ya muestra Poisson 1,01) |
| 21 fases con ~15 módulos simultáneos | OPTIMIZAR | Riesgo de sobreajuste; ablaciones previas a cada módulo |
| Team totals | DESCARTAR (por ahora) | Mencionados en cabecera sin fase ni datos |
| Validación sin umbrales | CORREGIR | Fijar criterios numéricos previos |
