# Auditoría: prompt_191_mlb_corregido_v2.md

Fecha de auditoría: 2026-11-10. Solo lectura sobre la plataforma. Etiquetas: [COMPROBADO] [INFERENCIA] [HIPÓTESIS] [RECOMENDACIÓN].

## 1. Ficha

| Campo | Valor |
|---|---|
| Fichero | `C:\dev\Prompts\prompt_191_mlb_corregido_v2.md` (nombre en minúsculas; el resto de la carpeta es `PROMPT_191_<X>_v1_0.md`) |
| Versión declarada | «PROMPT 191 — MLB PREGAME PRICING ENGINE v2.0 — Especificación corregida, auditable y consciente de la incertidumbre» (prompt:1-2) |
| Deporte / competición | Béisbol, MLB (temporada regular y playoffs, prompt:59, 143) |
| Tamaño | 266 líneas, 28.137 bytes |
| Rol | Asistente cuantitativo pregame; estima carreras y probabilidades de ML, Run Line ±1.5 y Totales; solo después compara con cuotas (prompt:5) |
| Objetivos | (1) predicción calibrada, (2) pricing/EV si hay cuotas fiables (prompt:7-9) |
| Modos | VALIDADO / EXPLORATORIO / INCOMPLETO, determinados «con evidencia» (prompt:24-28) |
| Mercados | ML, RL ±1.5 y otras líneas por desigualdad de liquidación, Totales con línea t (prompt:159-165). No hay team totals ni F5. |

**Versiones.** [COMPROBADO] El fichero se llama «corregido_v2» y declara v2.0. [COMPROBADO] No existe v1 en `C:\dev\Prompts`. El único rastro está en el worktree `.claude/worktrees/agent-a2bc3d835b878219b/docs/prompts/README.md:38` («La v1 de prompt 191 no existe como archivo: se conserva únicamente citada y analizada en las notas de la bóveda») y en `Obsidian/Conocimiento/Prompt 191 - origen del modelo.md` (secciones «Defectos de v1 que quedan cerrados», línea ~249, y «Versión corregida (v2)», línea ~245; fuente de esa v2: `docs/prompts/prompt-191-mlb-pricing-v2.md`). [COMPROBADO] En ese worktree existe además `prompt-191-mlb-pricing-v3.md` (646 líneas, «v3 2026-08-15»), cuya cabecera dice que las constantes `HomeAdj=1.02` y `NB_alpha=0.15` no se corrigieron a ojo. [INFERENCIA] El fichero auditado NO es la v2 de ese inventario: usa `NB_k=0.15` con fracción compartida `f=0.30` (prompt:44) y no «NB_alpha + cópula»; es una reescritura posterior, más cautelosa, donde casi todo lo cuantitativo es «PROVISIONAL». [HIPÓTESIS] El «v2.0» del título y el «v2» del inventario de la plataforma son numeraciones independientes; solo el operador puede confirmarlo.

## 2. Reglas y restricciones

Reglas absolutas (prompt:13-21):
1. Independencia del mercado: ninguna cuota, consenso, pick o movimiento modifica inputs, coeficientes o probabilidades (prompt:14).
2. No inventar datos; valores por defecto marcados como *supuesto* (prompt:15).
3. Corte temporal `as_of` (prompt:16).
4. No declarar Monte Carlo/backtest no ejecutado (prompt:17).
5. Abstención ante datos indispensables ausentes (prompt:18).
6. Trazabilidad: fuente, fecha, unidad, n, fallback, versión, semilla (prompt:19).
7. Calidad / validación / incertidumbre reportadas por separado (prompt:20).
8. No hacer preguntas innecesarias (prompt:21).

Reglas de excepción: parámetros `PROVISIONAL` solo si no hay `model_config` calibrado (prompt:35); stand-ins de IP del abridor (5,0) (prompt:42); `LineupAdj=1.00` si no hay proyección (prompt:82).

Condición de «validado»: versión de modelo + coeficientes entrenados + evaluación temporal OOS + calibración documentada (prompt:24); el modo no se elige retóricamente (prompt:28). Condición para publicar ML/RL/Totals como finales: simulador que implemente reglas reales de la entrada 9, walk-off y extras (prompt:147). Tests obligatorios antes de publicar (prompt:245-258).

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Línea | ¿Justificado? |
|---|---|---|---|---|
| prior_offense, prior_pitching | 1,00 | multiplicador | 36 | No; «neutralidad declarada» |
| lambda_season | PA/(PA+1200) (o juegos/(juegos+30)) | peso | 37 | No; PROVISIONAL |
| lambda_split | PA_split/(PA_split+600) | peso | 38 | No |
| lambda_recent | PA_recent/(PA_recent+400) | peso | 39 | No |
| b_split | 0,20·wSP_opp | exponente | 40, 79 | No; «exploratorio» |
| b_recent | 0,10 | exponente | 40, 79 | No |
| lambda_SP | IP/(IP+80) | peso | 41 | No |
| lambda_BP | IP/(IP+120) | peso | 41 | No |
| IP_SP esperadas | 5,0 (fallback) | entradas | 42 | No; declarado supuesto |
| H/A | 1,02 → HomeAdj=√1,02, AwayAdj=1/√1,02 | ratio | 43 | No; «hipótesis provisional» |
| NB_k | 0,15 | adimensional (Var=μ+kμ²) | 44, 137 | No; «hipótesis» |
| shared_fraction f | 0,30 | fracción | 44 | No |
| MC_min / MC_max | 100.000 / 1.000.000 | iteraciones | 45 | Parcial: objetivo de semiancho ≤0,003 |
| Líneas RL | ±1,5 | carreras | 161 | Reglamentario |
| Conversión cuotas | D=1+X/100; D=1+100/X | — | 184-186 | Fórmulas estándar |

Los promedios de liga (`L`, wOBA, etc.) NO se fijan: se obtienen por temporada y fecha de corte (prompt:33). [COMPROBADO] Es una buena práctica.

## 4. Fuentes de datos

Jerarquía (prompt:51-54): (1) MLB.com / Stats API (calendario, abridores, alineaciones); (2) FanGraphs, Savant, Baseball-Reference (ofensiva, pitcheo, defensa); (3) fuente meteorológica con timestamp; (4) cuotas, **solo tras fijar las probabilidades**. Periodicidad: no declarada, solo el corte `as_of` (prompt:16). Frescura: «todos los datos anteriores a `as_of`» (prompt:248). Calidad: `CalidadDatos` Alta/Media/Baja con criterios cualitativos (prompt:168-171). [INFERENCIA] No distingue el momento de publicación de la alineación del momento del partido; no hay `published_at` (en cambio el prompt NHL sí lo pide, NHL prompt:43).

## 5. Cadena predictiva

1. Evento y `as_of` (F1). 2. Controles mínimos (F2): `L`, ofensiva y prevención por equipo, parque o neutralidad, si no INCOMPLETO (prompt:64).
3. Ofensiva (F3): `S=prior_offense+lambda_season*(S_raw-prior_offense)`, `Split=S+lambda_split*(split_raw-S)`, `Recent=S+lambda_recent*(recent_raw-S)`, y literalmente
`OffRating = S^(1-b_split-b_recent) * Split^b_split * Recent^b_recent * LineupAdj` (prompt:80).
4. Abridor (F4): `StarterIndex=SP_prior+lambda_SP*(SP_raw-SP_prior)` (prompt:86).
5. Bullpen (F5), defensa (F6, `DefenseAdj=1.00` por defecto), entorno (F7): `EnvAdj=ParkFactor*WeatherAdj*UmpAdj` (prompt:106), matchup (F8, 1,00 salvo módulo entrenado).
6. Prevención (F9): `PitchingAllowed_equipo = [wSP*StarterIndex + (1-wSP)*BullpenIndex]*DefenseAdj` con `wSP=IP_SP/9` (prompt:114).
7. Carreras base (F10), literalmente:
`mu_away_9 = L*OffRating_away*MatchupAdj_away*PitchingAllowed_home*EnvAdj*AwayAdj` y
`mu_home_9 = L*OffRating_home*MatchupAdj_home*PitchingAllowed_away*EnvAdj*HomeAdj` (prompt:121-123). Son carreras de **nueve entradas completas**, no del marcador final (prompt:125).
8. Distribución (F11): `Z_shared ~ Gamma(f/k, k)`, `Z_i ~ Gamma((1-f)/k, k)`, `G_i=Z_shared+Z_i`, carreras|G ~ Poisson(`mu_i_9*G_i/9`). Marginales NB con `E=mu`, `Var=mu+k*mu²`; correlación derivada:
`rho_9 = f*k*mu_away_9*mu_home_9 / sqrt((mu_away_9+k*mu_away_9^2)*(mu_home_9+k*mu_home_9^2))` (prompt:138).
9. Reglas reales (F12): alternancia, baja de la 9ª omitida, walk-off, extras con corredor automático. 10. Monte Carlo (F13). 11. Probabilidades (F14): `P_home=count(home>away)/N`; RL `P(home-away≥2)`; Totales con `P_push` explícito (prompt:159-165).
Prórroga/empate: el béisbol no tiene empate final; el prompt exige extras con corredor automático y prohíbe asignar empates a visitante (prompt:165).
Mercados: ML, RL, Totales. Sin team totals, sin F5, sin 3 vías.

## 6. Auditoría matemática

- [COMPROBADO] La varianza de G: `Gamma(shape=f/k, scale=k)` tiene media f y `Z_i` media (1-f); `G_i` media 1 y Var(G_i)=k. Con Poisson condicional, `Var(R)=μ+μ²·k` (compuesta Poisson-Gamma), coherente con prompt:137. La covarianza de los dos G es `f·k` y la fórmula de `rho_9` (prompt:138) es correcta: Cov(R_a,R_h)=μ_aμ_h·f·k. Correlación positiva entre equipos por construcción.
- [INFERENCIA] `k=0,15` es mucho menor que la dispersión medida en la plataforma: `registry.py:40-41` fija `dispersion_k=3,8` con la parametrización `Var=mu+mu²/k` (`distributions.py:95-96`), o sea k_prompt equivalente ≈ 1/3,8 = 0,263. Para μ≈4,35 (avg_total 8,7, `registry.py:40`) la varianza por equipo sería 7,19 en el prompt frente a 9,33 en la plataforma (razón varianza/media 1,65 vs 2,14; la plataforma cita una medida de 2,21 sobre 14.223 equipos-partido, `registry.py:34-36`). [HIPÓTESIS] El prompt subdispersa; el worktree v3 ya sospecha lo mismo («sd ≈ 2,79 frente a ~3,1», v3 cabecera). Efecto: colas de totales y RL ±1,5 sobreconfiadas.
- [COMPROBADO] Fuga conceptual de nueve entradas vs final: el prompt lo reconoce (prompt:125, 147) y prohíbe publicar sin simulador que respete walk-off. Es correcto y más honesto que la plataforma, que ajusta Poisson/NB a marcadores finales (ver §9).
- [INFERENCIA] El modelo `Poisson|G con tasa mu*G/9 por entrada` supone entradas homogéneas; el béisbol tiene la parte baja de la 9ª omitida y bullpen con otra calidad que la mitad inicial. El propio prompt lo admite (prompt:116, 135).
- [INFERENCIA] Aplicar `HomeAdj=√1,02` a una sola mu (prompt:122) equivale a un ratio total 1,02 que implica ~50,8 % de victoria local, por debajo de la tasa real ~52,5-53,5 % que cita el worktree v3 (cabecera). [HIPÓTESIS] No lo he medido hoy; hace falta un script de la plataforma.
- Coeficientes sin justificar: todos los de §3 salvo las fórmulas de conversión. El prompt es explícito en que son provisionales (prompt:48), lo cual es una virtud: [COMPROBADO] declara «no tienen garantía de optimalidad».
- Riesgo de sobreajuste: bajo en el prompt (casi todo desactivado por defecto); riesgo alto de **subajuste** de entorno (WeatherAdj, UmpAdj, defensa, matchup todos a 1,00).
- Fuga temporal: bien tratada (prompt:16, 248), pero la frescura de alineaciones no está modelada.
- Datos faltantes: política de abstención, `null`, INCOMPLETO. [INFERENCIA] La mezcla de candidatos de abridor «con probabilidades justificadas» (prompt:89) tiene el mismo riesgo que el NHL (§ portero): requiere P(start) defendible.
- [INFERENCIA] Posible doble conteo residual: `S` (wRC+ de equipo, ya incluye parque) y `ParkFactor` en `EnvAdj` (prompt:100-106); y `PitchingAllowed` con `xFIP` ajustado a liga mas `DefenseAdj`. El prompt lo menciona para defensa (prompt:97) pero no para wRC+ ya ajustado por parque. wRC+ está park-adjusted por definición, [HIPÓTESIS] luego aplicar `ParkFactor` otra vez al ataque estaría duplicando.

## 7. Independencia del mercado

| Cita | Contenido | Clasificación |
|---|---|---|
| prompt:5 | Compara con cuotas «solo después» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| prompt:14 | Independencia, el mercado «se consulta exclusivamente al final» | Regla; correcta |
| prompt:54 | Cuotas solo cuando las probabilidades están fijadas | COMPARACIÓN POSTERIOR LEGÍTIMA |
| prompt:147, 163 | Línea `t` de totales | UMBRAL LEGÍTIMO (P(total>t) sale del modelo) |
| prompt:161 | RL ±1,5 | UMBRAL LEGÍTIMO (regla del deporte, no del mercado) |
| prompt:177-178 | Congelar antes de consultar; «no cambiar la predicción para acercarla a las cuotas» | Congelación explícita |
| prompt:181-190 | Cuotas, de-vig, break-even | COMPARACIÓN POSTERIOR LEGÍTIMA |
| prompt:199-202 | Apertura, cierre, CLV; `MarketQuality` «no modifica probabilidades» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| prompt:261 | Benchmark del mercado sin vig «sin usarlo para entrenar» | COMPARACIÓN POSTERIOR LEGÍTIMA |

[COMPROBADO] No hay ninguna ENTRADA PROHIBIDA. El prompt congela las probabilidades antes de ver el mercado (Fase 16 precede a 17). [INFERENCIA] Matiz: prompt:14 permite «Si se usa como benchmark en evaluaciones históricas, debe quedar separado del entrenamiento»; la separación se enuncia pero no se operativiza (p. ej. no prohíbe seleccionar hiperparámetros por ROI sobre cuotas, que es justo lo que hizo la plataforma, ver §9).

## 8. Validación propuesta

Walk-forward con snapshots pregame, nunca split aleatorio; Brier, Log Loss, curvas de fiabilidad; log-verosimilitud de la distribución de carreras; MAE/RMSE; ablaciones contra el modelo simple ofensiva+pitcheo; segmentación por temporada, favorito, rango de totales; intervalos; benchmark mercado sin vig (prompt:261). Bien. [INFERENCIA] No fija umbrales de aceptación (equivalentes al margen 0,002 de log loss de la plataforma, `ratings.yaml:18-20`): «VALIDADO» queda sin criterio numérico. [RECOMENDACIÓN] Fijar pre-registro con umbrales antes de medir, como hace `docs/research/2026-09-26-preregistro-portero-nhl.md`.

## 9. Contraste con la plataforma

| Componente del prompt | Plataforma | Estado |
|---|---|---|
| Distribución de carreras | `PoissonAdapter` + `BaseballAdapter`; NB por equipo con `dispersion_k=3,8` (`registry.py:40-41`), `score_rho` (`adapters.py:152`) 0 por defecto | DIFIERE: la plataforma ajusta marcadores finales con rejilla conjunta independiente, sin simulador de entradas ni walk-off ni gamma compartida |
| Escala de goles (L) | `avg_total` 8,7 constante (`registry.py:40`) mezclada con ataque/defensa por equipo (`TeamScoringRates.expected_total`, `team_scoring.py:92-101`) | DIFIERE: constante de liga no actualizada por temporada; el prompt lo prohíbe (prompt:33) |
| Reparto local/visitante | `tilt = clip((p_home-0,5)·tilt_scale, ±0,30)` desde Elo (`adapters.py:140`); producción MLB `tilt_scale: 0,4` (`ratings.yaml:24`), bono local `home_scoring_bonus` 0,10 (`registry.py:41`) | DIFIERE: el prompt usa `HomeAdj=√1,02`; la plataforma deriva el reparto de Elo (resultados) |
| Abridor | `StarterRatings`, `pitcher_bound=0,05` en producción (`ratings.yaml:22`, activado 2026-09-26 «por orden, no por evidencia concluyente», `ratings.yaml:17-21`), `pitcher_prior_starts=5` (`ratings.yaml:23`), señal RA (v1) por defecto (`adapters.py:189`) | PARCIAL: el prompt exige xFIP→FIP→ERA con prior; la plataforma usa carreras permitidas (con bullpen) o FIP por apertura. El bound 0,05 = ±5 % es casi inerte frente al prompt |
| Bullpen | No hay módulo | FALTA |
| Defensa, ump, matchup | No hay | FALTA (coincide con el prompt: ambos a 1,00) |
| Parque | `ParkFactors`, `park_bound: 0,10` (`ratings.yaml:30`) | IMPLEMENTADO. Ver riesgo abajo |
| Clima | `weather` en `adjust_model_probability` (`daily.py:966`); clima MLB «rechazado» según memoria del 2026-09-26 | DIFIERE |
| Alineación / LineupAdj | No hay | FALTA |
| Regularización PA/(PA+1200) | `scoring_prior_games=6,0` (`adapters.py:101`) | DIFIERE: constante propia, no de PA |
| Simulación de reglas reales (extras, walk-off) | No hay; `TIE_ADDS_GOAL=False` para béisbol (`adapters.py:96`) con la nota de que los extras pueden sumar varias carreras | FALTA |
| ML/RL/Totales con push | `poisson_match_probs` con líneas asiáticas, push eliminado en convención de decisión (`distributions.py:253-262`) | IMPLEMENTADO |
| Congelar antes del mercado | `model_probability`/`adjusted_probability` se guardan antes del blend (`daily.py:1031-1033`) | IMPLEMENTADO en el stream servido |

**Uso de información de mercado en las probabilidades de la plataforma (MLB y general):**
- [COMPROBADO] `market_shrink: 0.5` en `configs/default.yaml:17`; `_decision_probability` calcula `p_decision = (1.0 - shrink) * p_cal + shrink * fair` (`src/sqp/pipeline/probabilities.py:304-305`) y `p_decision` es lo que alimenta `edge()`, Kelly y selección (`daily.py:966-982`). El `fair` es el no-vig del consenso. Esto es **ENTRADA PROHIBIDA** para la decisión: la probabilidad usada para apostar está mezclada a un 50 % con el mercado. La probabilidad pura se conserva aparte como `model_probability` (`daily.py:1031`). No he podido verificar si `.env` sobreescribe `MARKET_SHRINK` (la clave aparece en `config.py:65,466`; en `.env` solo vi `MARKET_SHRINKAGE_SPREAD/TOTALS`, claves distintas y sin consumidor en `src`/`configs`, por una grep rápida).
- [COMPROBADO] `uncertainty_penalty: 0.35` (`default.yaml:26`) deflacta el edge por la brecha modelo-vs-mercado y se pliega a la probabilidad de stake (`daily.py:982-1000`): mercado como entrada de la decisión, no de la estimación.
- [COMPROBADO] La selección de `park_bound: 0.10` se justificó por ROI sobre cuotas capturadas («flips MLB totals from -17.1% to +2.8% ROI», `ratings.yaml:25-29`); `max_plausible_edge` y `uncertainty_penalty` igual (`default.yaml:10-26`). Es **optimización contra el mercado** de parámetros que afectan a la probabilidad del modelo (park_bound sí entra en `lam`). [INFERENCIA] Contamina el objetivo de independencia aunque el cálculo no lea cuotas en producción.
- [COMPROBADO] El umbral de totales y spread (`total_line`, `spread_line`) llega del mercado y se usa solo como umbral en la rejilla (`adapters.py:148-153`): UMBRAL LEGÍTIMO. El `avg_total` NO viene del mercado.
- [INFERENCIA] Los calibradores se entrenan sobre `adjusted_probability` (pura) frente a resultados (`calibration/data.py:69-80`), no contra el mercado. Sin evidencia de que entrenen contra precios.

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Principios innegociables y congelación (F16) | CONSERVAR | Cumple el principio rector; modelo de redacción para el resto de la familia |
| Modos VALIDADO/EXPLORATORIO/INCOMPLETO | CONSERVAR | Evita llamar «validado» a lo que no lo está |
| Estructura de cadena ofensiva (S, Split, Recent) | OPTIMIZAR | Constantes 1200/600/400 sin respaldo; medir antes de usar |
| wSP·Starter + (1-wSP)·Bullpen | CORREGIR | Aproximación, sin modelo de uso; posible doble conteo con parque |
| `HomeAdj=1,02` | CORREGIR | Subestima la localía (~50,8 % implícito); medir |
| `NB_k=0,15`, `f=0,30` | CORREGIR | Subdispersado respecto a 3,8 de la plataforma (k equivalente 0,263) |
| Simulador de reglas reales (F12) | INTEGRAR | Falta en la plataforma; requisito real para totales/RL en MLB |
| Parque / clima / ump / defensa / matchup a 1,00 | CONSERVAR | Honesto; no inventar |
| Fórmulas de EV, edge, push (F17-18) | CONSERVAR | Correctas y coherentes con `edge.py` |
| Monte Carlo ≥100k con semiancho | CONSERVAR | Buena práctica |
| Validación sin umbrales numéricos | CORREGIR | Pre-registro de criterios |
| Ranking por EV en EXPLORATORIO (F20) | OPTIMIZAR | Permite ordenar por EV «ilustrativo»; mantener etiqueta |
