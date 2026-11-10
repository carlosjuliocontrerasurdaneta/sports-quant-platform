# Auditoría individual: PROMPT_191_EPL_v1_0

Fecha de la auditoría: 2026-11-10. Etiquetas: [COMPROBADO] con cita, [INFERENCIA], [HIPÓTESIS], [RECOMENDACIÓN]. Las citas `P:n` son líneas del prompt (`C:\dev\Prompts\PROMPT_191_EPL_v1_0.md`).

## 1. Ficha

- **Fichero / versión:** PROMPT_191_EPL_v1_0.md, «PROMPT 191-EPL v1.0» [COMPROBADO P:1]. Fecha del diseño 2026-11-10 [P:7].
- **Deporte / competición:** fútbol, English Premier League, solo liga; copas y UEFA solo como contexto de carga [P:5].
- **Tamaño:** 429 líneas.
- **Rol:** motor cuantitativo pregame de 90' + añadido [P:13].
- **Objetivo:** λ_home, λ_away; 1X2; Over/Under y BTTS; hándicap europeo y asiático; porterías a cero y marcadores; EV solo tras congelar [P:15-21].
- **Alcance / modos:** estados VALIDADO / EXPLORATORIO / INCOMPLETO [P:43]. Estado inicial EXPLORATORIO [P:6]. Modos de cálculo: log-lineal «preferente» o baseline multiplicativo exploratorio [P:180-194]; Poisson independiente o Dixon-Coles [P:198-217]. Existe un modo parcial («MODELO INCOMPLETO») [P:83].

## 2. Reglas y restricciones

- **Absolutas (18) [P:31-48]:** no inventar datos; todo as-of [P:32]; no mezclar proveedores de xG [P:33]; no sumar variables redundantes [P:35]; no reusar coeficientes de otras ligas [P:37]; ascendidos con ajuste [P:38]; 1X2 suma 100% [P:39]; sin prórroga ni penales [P:40]; no publicar sin distribución ejecutada [P:41]; EV «NO EVALUABLE» sin cuota [P:42]; huso `Europe/London` [P:46]; excluir partidos iniciados [P:47].
- **Excepciones:** salida parcial si faltan datos [P:41, 83]; escenarios IN/OUT [P:142]; sin clima → estimación central con incertidumbre [P:369].
- **«Validado» requiere [P:300]:** backtest rolling-origin, Brier y log loss 1X2, calibración por clase, RPS, log score de marcadores, BTTS/hándicap/totales, cobertura de intervalos, evaluación por temporadas; ablación frente a baselines [P:302].
- [INFERENCIA] No fija umbrales numéricos de aceptación para «validado» (ni delta mínimo de log loss ni n mínimo): la condición es cualitativa y no auditable por sí sola.

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Línea | Justificación |
|---|---|---|---|---|
| Masa omitida combinada máxima | ≤ 0,0001 | probabilidad | P:217, P:391 | Tolerancia numérica, declarada; no justificada |
| Equipos de la liga | 20 | clubes | P:95 | Hecho de formato; sin fuente citada en el cuerpo |
| `L_home`, `L_away` | no fijados | goles | P:66-69 | Se estiman hasta `as_of`; prohíbe fijarlos |
| `tau_shrink`, decay, HFA, `rho_DC`, dispersión | no fijados | – | P:70 | «se aprenden o se marcan exploratorios» |
| `w = n_eff/(n_eff+tau)` | fórmula | – | P:125-126 | Shrinkage estándar; tau sin valor |
| Pesos de forma 15 % / 20 % | prohibidos | – | P:134 | Rechazados por arbitrarios |
| Lambda del baseline | `L*OffIndex*DefWeakIndex*Context` | goles | P:191-192 | Heurística exploratoria |
| Husos | Europe/London | – | P:46 | Convención |

[COMPROBADO] El prompt no contiene ningún coeficiente numérico entrenado; la única cifra operativa es la tolerancia 1e-4 de cola. [INFERENCIA] No hay riesgo de sobreajuste en el texto, pero tampoco hay un valor ejecutable: el prompt es una especificación que depende de un motor externo.

## 4. Fuentes de datos

- Jerarquía [P:52-62]: premierleague.com / IFAB para fixtures y reglas; Opta/The Analyst, StatsBomb, Understat, FBref para xG; clubes y PL para lesiones y XI; meteorología; cuotas «consultadas solo al final» [P:60].
- Registro por campo: valor, unidad, fuente, `timestamp_as_of`, muestra, temporada, contexto, versión, fallback [P:64].
- Periodicidad y frescura: solo «as-of antes del instante de predicción» [P:32]; no define antigüedad máxima de la alineación ni del xG. [INFERENCIA] Falta una regla de frescura (por ejemplo, hora mínima de corte antes del kickoff).
- Calidad: prohíbe mezclar xG de proveedores sin armonizar [P:33, 381].

## 5. Cadena predictiva

1. Identificación del fixture [P:91-97].
2. Ataque y defensa con xG/NPxG por 90 [P:99-113], ajuste por rival [P:115-119] (modelo jerárquico o Poisson con efectos de equipo y sede).
3. Shrinkage a un prior, con puente Championship→Premier para ascendidos [P:121-130]:
   `w = n_eff / (n_eff + tau)` / `theta_post = w*theta_obs + (1-w)*theta_prior` [P:125-126].
4. Forma, once, portero, balón parado, táctica, descanso y localía como ajustes incrementales sin doble conteo [P:132-176].
5. Goles esperados [P:180-194]:
   `log(lambda_home) = beta_home + attack_home + defense_weakness_away + delta_context_home`
   `log(lambda_away) = beta_away + attack_away + defense_weakness_home + delta_context_away`
   Alternativa: `lambda_home = L_home * OffIndex_home * DefWeakIndex_away * Context_home`.
6. Distribución conjunta [P:200-205]: `P(H=h, A=a) = Pois(h; lambda_home) * Pois(a; lambda_away)`; Dixon-Coles opcional con τ(0,0)=1−λhλaρ, τ(0,1)=1+λhρ, τ(1,0)=1+λaρ, τ(1,1)=1−ρ [P:209-212]; malla hasta masa omitida ≤ 1e-4 [P:217].
7. Derivados: 1X2 [P:221-225], BTTS y portería a cero [P:235-238], totales con push [P:246-248], hándicap con win/push/loss [P:258-260], cuartos asiáticos por reparto 50/50 [P:250, 262], DNB y doble oportunidad [P:264].
8. Congelación [P:272] y solo entonces mercado [P:276].

Dependencias: Poisson independiente por defecto; la dependencia solo entra con DC. Prórroga/empate: el empate es resultado propio, sin prórroga [P:39-40]. Monte Carlo: no es el método base (malla analítica); se exige semilla si se usa (checks P:409). Mercados que produce: 1X2, margen esperado, totales, BTTS, CS, hándicap, DNB, doble oportunidad; **no** team totals explícitos (solo se mencionan derivados «si la distribución los sostiene» [P:20]).

## 6. Auditoría matemática

- [COMPROBADO] Las fórmulas τ de Dixon-Coles [P:209-212] coinciden con la parametrización original de 1997 (λ del local en (0,1)). [INFERENCIA] Con esa parametrización la suma de masa se conserva exactamente (los cuatro términos de ajuste se anulan), de modo que no es necesario renormalizar; el prompt acierta al exigir τ ≥ 0 [P:215].
- Coherencia interna: 1X2 suma 1, Over+Under+Push=1, win+push+loss=1 [P:227, 251, 396]; `P_break_even=(1−P_push)/D` es correcto: EV = P_win·D − (1−P_push) [P:278].
- [COMPROBADO] «No truncar λ de forma silenciosa» [P:72] pero tampoco define qué hacer con λ extremos más allá de «diagnóstico y advertencia».
- Distribución elegida: Poisson independiente. [INFERENCIA] Para fútbol es razonable como baseline; el prompt reconoce alternativas (bivariante, estados) [P:205] y exige elegirlas por validación, no por edge [P:205].
- Incoherencia: la fase 13 dice `beta_home` y `beta_away` separados y «no aplicar localía otra vez» [P:187], y la fase 12 «una sola vez» [P:174]; es coherente. Sin embargo `Context_home` / `delta_context_home` agrupa todo lo no-rating sin delimitar [P:182-183]. [INFERENCIA] Riesgo de doble conteo de lesiones, descanso y forma dentro de un término agregado; las reglas anti-doble-conteo [P:36] son declarativas, sin procedimiento.
- Coeficientes sin justificar: ninguno (no hay coeficientes). Pero el baseline multiplicativo mezcla xG ajustado con goles de liga (`L_home` en goles, índices en xG) [P:191-194]; [INFERENCIA] la conversión xG → goles no está calibrada: el propio prompt lo admite («Marcar baseline como EXPLORATORIO»).
- Fuga temporal: bien tratada en reglas (as-of [P:32], snapshots por `as_of` [P:274]). [HIPÓTESIS] Los xG de proveedores se revisan retroactivamente; el prompt no pide guardar la versión pregame del xG (LaLiga sí lo exige, P:91 de ese prompt).
- Datos faltantes: salida parcial y escenarios [P:83, 142, 365-371]. Incertidumbre: separa DataQuality, ValidationStatus, LineupCertainty, PredictiveUncertainty, MarketQuality [P:292-298]; «no solo error Monte Carlo» [P:44, 409].

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| P:6-7, 21 | EV y diferencias contra precios «únicamente después de congelar» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:27 | «El mercado no determina las probabilidades… Nunca introducir cuotas, movimientos de línea, consensos…» | Regla de independencia |
| P:27 | «Si se usan precios como benchmark para validación histórica, registrar ese hecho sin contaminarlos en el entrenamiento» | COMPARACIÓN POSTERIOR LEGÍTIMA (ambigua: ver abajo) |
| P:60 | Cuotas «consultadas solo al final» | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:246-252 | Línea `t` de goles como umbral; «sin línea de mercado se puede informar P(total ≥2)…» [P:252] | UMBRAL LEGÍTIMO |
| P:258-262 | Línea de hándicap `h` como umbral | UMBRAL LEGÍTIMO |
| P:272-288 | Congelación → cuotas → EV, devig proporcional «como aproximación» [P:284], CLV [P:288] | COMPARACIÓN POSTERIOR LEGÍTIMA |
| P:304 | «las cuotas no se usan como input del motor» | Regla |

[COMPROBADO] Ninguna mención es ENTRADA PROHIBIDA. [COMPROBADO] El prompt congela las probabilidades antes de consultar cuotas (`Antes de consultar cuotas, congelar…` P:270-274) y prohíbe reescribir silenciosamente [P:274]. [INFERENCIA] Matiz: la frase «registrar ese hecho sin contaminarlos» [P:27] es vaga sobre si un benchmark de mercado puede entrar en la selección de hiperparámetros (con odds históricas). [RECOMENDACIÓN] Añadir: «ningún hiperparámetro ni calibrador se selecciona con métricas contra mercado».

## 8. Validación que propone

Backtest rolling-origin sin fuga, Brier, log loss, calibración por clase, RPS, log score de marcadores, cobertura de intervalos, evaluación por temporadas, ablación incremental (Poisson-xG → rival → Dixon-Coles → XI → portero → calendario) [P:300-302]. No afirma superioridad sobre el mercado sin odds históricas del mismo instante [P:304]. [INFERENCIA] Faltan: tamaño muestral mínimo, margen de aceptación y regla de parada; no pide corrección por comparaciones múltiples en la ablación.

## 9. Contraste con la plataforma

- **Implementado.** Poisson/Dixon-Coles con malla: `src/sqp/models/distributions.py:204` (`poisson_match_probs`), τ en `distributions.py:71-80`; 1X2 de tres vías `src/sqp/sports/adapters.py:314-316` (`SoccerAdapter.three_way = True`); cuartos asiáticos por líneas adyacentes (`distributions.py` comentario AUD-001 de 2026-09-17); totales y spread con push.
- **Valor de producción EPL.** `dc_rho = -0.2` y `elo_home_adv = 15.0` [`configs/leagues/ratings.yaml:13-15`]; `avg_goals = 2.80` [`configs/leagues/soccer.yaml:4`]; resto del default de familia `soccer`: `tilt_scale 1.0`, `max_score 10`, `home_scoring_bonus 0.15`, `elo_k 18` [`src/sqp/sports/registry.py:45-47`].
- **Cadena de λ en la plataforma [`adapters.py:127-144`]:** `diff = Elo + descanso` → `p_home = 1/(1+10^(-diff/400))` → `avg` = total esperado del emparejamiento por `TeamScoringRates` → `tilt = clamp((p_home-0.5)*tilt_scale, ±0.30)` → `lam_home = avg*(0.5+tilt) + home_scoring_bonus`, `lam_away = avg*(0.5-tilt)`, mínimo 0,1.
- **Difiere.**
  1. No hay xG, NPxG, PSxG ni datos de once/portero para fútbol; la entrada es goles y Elo [adapters.py:84-95, 127-144]. [COMPROBADO] El prompt exige xG homogéneo (P:54).
  2. Ataque/defensa: media aditiva de ofensiva propia y defensa rival (`team_scoring.py:98-101`), no log-lineal multiplicativo ni ajustado por oponente.
  3. Localía: Elo con ventaja local de 15 puntos (que entra en `p_home`) **más** `home_scoring_bonus` 0,15 goles en λ_local. [INFERENCIA] Es una posible doble aplicación de la localía frente a P:174 («una sola vez»). [HIPÓTESIS] Que la sobreestime no está medido aquí.
  4. `avg_goals 2.80` es una constante fija por liga (soccer.yaml:4), que P:66-69 prohíbe fijar «para siempre». [INFERENCIA] Solo actúa como respaldo en arranque en frío (`team_scoring.py:95-97`).
  5. La malla se renormaliza siempre tras truncar a `max_score 10` [distributions.py, `mass = win+draw+loss`, l.294]; no reporta masa omitida. P:217 prohíbe «renormalizar silenciosamente».
  6. La probabilidad servida de spread/total en líneas con push es la de decisión `win/(win+loss)` [distributions.py comentario AUD-001], no `P_win/P_push/P_loss` separadas como P:258-260.
  7. Ascendidos, puente Championship, forma, clima y matchup: no encontrados para fútbol (solo descanso genérico por Elo en `PoissonAdapter.rest`, `rest_elo_per_day` por defecto 0). 
  8. `dc_rho -0.2` es un valor ajustado por búsqueda en rejilla walk-forward (`ratings.yaml:1-5`, `scripts/tune_ratings.py`), no estimación de máxima verosimilitud conjunta; [INFERENCIA] aceptable bajo P:70 si el procedimiento es temporal.
- **Información de mercado en la construcción de probabilidades.** [COMPROBADO] El pricing del adaptador (`estimate`, `adapters.py:146-164`) no usa cuotas. [COMPROBADO] Pero la probabilidad de decisión sí: `p_used = (1-s)*p_model + s*fair` con `market_shrink = 0.5` por defecto [`configs/default.yaml:17`, `src/sqp/pipeline/probabilities.py:303-304`, aplicada en `src/sqp/pipeline/daily.py:969-970`]. Es uso del mercado (probabilidad sin vig) como ENTRADA de la probabilidad que dimensiona la apuesta, aplicado a EPL como a todas las ligas. También `uncertainty_penalty 0.35` penaliza por la distancia modelo-mercado [`default.yaml:26`; `edge.py`]. El valor efectivo de `MARKET_SHRINK` en `.env` de producción no se pudo verificar (acceso denegado a `.env`). Los calibradores se entrenan sobre `adjusted_probability` PRE-blend, es decir, no contra el mercado [`probabilities.py:285-296`].

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Principio y reglas de independencia del mercado | CONSERVAR | Limpios; congelación explícita |
| Poisson + DC con τ ≥ 0 y masa omitida | CONSERVAR | Correcto; la plataforma ya lo implementa |
| Tolerancia 1e-4 de masa | OPTIMIZAR | Más laxa que las de Serie A, Ligue 1 y UCL (1e-6); unificar |
| Baseline multiplicativo xG/goles | CORREGIR | Mezcla unidades sin calibración conocida |
| `Context` agregado | CORREGIR | Riesgo de doble conteo; definir términos |
| Ascendidos / puente Championship | INTEGRAR | La plataforma no lo tiene; requiere histórico |
| xG/PSxG/once | INTEGRAR (parcial) | No hay proveedor en la plataforma; ver coste y licencia |
| Condición «validado» | OPTIMIZAR | Añadir umbrales cuantitativos |
| Líneas de mercado como umbral | CONSERVAR | Legítimo |
| `market_shrink 0,5` de la plataforma | CORREGIR (plataforma) | Contradice el principio rector; hay un pre-registro pendiente |
