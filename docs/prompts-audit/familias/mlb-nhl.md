# Familia mlb-nhl (béisbol y hockey: deportes de baja anotación con abridor/portero)

Compara `prompt_191_mlb_corregido_v2.md` (266 líneas) con `PROMPT_191_NHL_v1_0.md` (632 líneas). Etiquetas: [COMPROBADO] [INFERENCIA] [HIPÓTESIS] [RECOMENDACIÓN]. No se pudo ejecutar `diff` útil sobre los dos ficheros: los dos textos son de generaciones distintas; la comparación es estructural.

## Diff entre los prompts

**Plantilla común (idéntica en intención, no en texto):**
- [COMPROBADO] Independencia del mercado y mercado solo al final (MLB:14, 54; NHL:6, 36, 74).
- [COMPROBADO] Congelación de la predicción antes de consultar cuotas (MLB:177-178 «Fase 16»; NHL:432-445 «Fase 19»).
- [COMPROBADO] Tres modos VALIDADO / EXPLORATORIO / INCOMPLETO (MLB:24-28; NHL:414, 419).
- [COMPROBADO] No declarar Monte Carlo no ejecutado (MLB:17, 154; NHL:61, 346, 578).
- [COMPROBADO] Misma fórmula de EV y break-even con push: `EV = P_win*(D-1) - P_loss` y `(1-P_push)/D` (MLB:194-195; NHL:456-458).
- [COMPROBADO] CLV solo con cierre observado (MLB:202; NHL:465).
- [COMPROBADO] Tests obligatorios de suma de probabilidades y coherencia (MLB:245-258; NHL:566-597).

**Lo que cambia (propio de cada deporte):**

| Aspecto | MLB v2 | NHL v1.0 |
|---|---|---|
| Número de fases | 21 | 21 |
| Constantes numéricas | 14 provisionales explícitas (MLB:36-46) | Ninguna; todo «por estimar» (NHL:98) |
| Núcleo | `mu_9 = L·Off·Pitch·Env·Home/Away` | `λ_s = xGF·xGA/League` por estado y `Σ_s T_s/60·λ_s` |
| Unidad de tasa | carreras de 9 entradas | goles/60 min por estado de juego |
| Variable de ancla | abridor (xFIP/FIP/ERA, IP esperadas) | portero (GSAx, SV%, TOI) |
| Dependencia | NB con gamma compartida; `rho_9` derivada (MLB:138) | «estimar»; `rho=0,12` prohibido sin validar (NHL:94) |
| Resolución del empate | extras con corredor automático (MLB:143-145) | OT 3v3 + SO (REG) / OT 20 min 5v5 (PLAYOFF) (NHL:352-365) |
| Mercados | ML, RL ±1,5, Totales | 1X2 60 min, ML FT, PL ±1,5, Totales reg/FT, team totals |
| Especificidad de marcador | tres marcadores (reg/9, final) | cinco (`score_reg`, `score_after_OT`, `winner_SO`, `score_final_official`, `score_for_settlement`, NHL:53) |
| Invariantes | 14 tests | 30 invariantes |
| Fuente del `as_of` | `as_of` | `as_of_utc` + `published_at_utc` (NHL:43) |
| Contexto físico | clima, viento, techo (MLB:102) | viaje, descanso; viento exterior prohibido (NHL:72, 248) |
| Ranking | EV; `|P-0,5|` no es edge (MLB:197) | idem + ranking deportivo sin mercado (NHL:473) |

## Contradicciones entre ellos

- [COMPROBADO] MLB trae constantes provisionales con valor (1200/600/400, 5,0 IP, 1,02, k=0,15, f=0,30; MLB:36-46); NHL prohíbe fijar constantes equivalentes (NHL:98). La política «valor provisional etiquetado» frente a «valor vacío» es una divergencia de método, no un conflicto lógico. [INFERENCIA] Con el MLB, el operador obtiene números; con el NHL, ninguno hasta tener `model_config`.
- [COMPROBADO] Tratamiento de la dependencia: MLB impone una estructura (gamma compartida con `f=0,30`), NHL prohíbe fijar la correlación sin validación (NHL:94, 274). [INFERENCIA] Misma preocupación, distinta solución.
- [COMPROBADO] «Ranking»: el MLB deja ordenar por EV «meramente ilustrativo» en EXPLORATORIO (MLB:208); el NHL exige etiqueta «ranking deportivo» sin mercado (NHL:473) y no menciona ranking ilustrativo por EV en EXPLORATORIO. [INFERENCIA] No contradictorios, pero la política de salida difiere.
- [INFERENCIA] El MLB define la distribución de nueve entradas completas y reconoce que no es la final (MLB:125); el NHL separa explícitamente regulación y final (NHL:315). Mismo problema (aproximación intermedia vs final), solución más estricta en el NHL.

## Versiones y obsolescencia

- [COMPROBADO] MLB: fichero «corregido_v2», minúsculas, sin sufijo de versión numérica del resto; convive con la serie `PROMPT_191_<X>_v1_0.md`. No hay v1 como archivo (`.claude/worktrees/agent-a2bc3d835b878219b/docs/prompts/README.md:38`); en ese worktree hay un v3 (`prompt-191-mlb-pricing-v3.md`, 646 líneas) cuya cabecera usa `NB_alpha=0.15` y `HomeAdj=1.02` sin corregir; el v2.0 de aquí usa `NB_k=0.15` + `f=0.30` y la regla «PROVISIONAL». [HIPÓTESIS] Son lineajes distintos; no es posible ordenar cronológicamente sin fechas de los ficheros fuente (los dos ficheros auditados tienen la misma fecha de modificación, 2026-11-10 07:53).
- [COMPROBADO] NHL: solo v1.0 en la carpeta; el worktree anterior tiene `prompt-nhl-pricing-v3.md`. [HIPÓTESIS] Mismo comentario.
- [INFERENCIA] Sin metadatos de versión interna (changelog) en ninguno; imposible saber cuál es posterior al otro.

## Tabla comparativa de constantes (una fila por prompt, junto con la plataforma)

| Constante | MLB v2.0 | NHL v1.0 | Plataforma MLB (producción) | Plataforma NHL (producción) |
|---|---|---|---|---|
| Media de goles/carreras por equipo | `L` por temporada (MLB:33) | `LeagueRate_s` por temporada (NHL:98) | `avg_total` 8,7 fijo (`registry.py:40`) | `avg_total` 6,1 fijo (`registry.py:43`) |
| Localía | `HomeAdj=√1,02` (MLB:43) | `HFA` estimado (NHL:95) | `home_scoring_bonus` 0,10 + Elo `elo_home_adv` 25 (`registry.py:41`) | 0,10 + `elo_home_adv` 15 (`ratings.yaml:44`) |
| Dispersión | `NB_k=0,15` (Var=μ+kμ²) | por estimar | `dispersion_k=3,8` (Var=μ+μ²/k; k equiv. 0,263) (`registry.py:40-41`) | Poisson puro, sin k (`registry.py:38`, medido 1,01) |
| Correlación | derivada, `f=0,30` | no 0,12; por estimar | `score_rho` 0 por defecto (`adapters.py:152`) | idem |
| Regularización de equipo | PA/(PA+1200), 600, 400 | `TOI/(TOI+tau)` | `scoring_prior_games` 6,0 (`adapters.py:101`) | idem |
| Abridor/portero: peso | `IP/(IP+80)`; IP esp. 5,0 | `β_G` por entrenar | `pitcher_bound` 0,05; `pitcher_prior_starts` 5,0 (`ratings.yaml:22-23`) | `goalie_beta` 0,0; `goalie_prior_shots` 0; `goalie_bound` 0,35 (`adapters.py:292-294`) |
| Tilt Elo→reparto | no usa Elo | no usa Elo | `tilt_scale` 0,4 (`ratings.yaml:24`) | `tilt_scale` 0,439 (`ratings.yaml:50`) |
| Parque | de la fuente | no aplica | `park_bound` 0,10 (`ratings.yaml:30`) | n/a |
| Penalización por mercado | prohibida (MLB:14) | prohibida (NHL:595) | `market_shrink` 0,5; `uncertainty_penalty` 0,35 (`default.yaml:17,26`) | idem |
| MC | 1e5–1e6, semiancho 0,003 | error <0,5 pp | sin MC; rejilla exacta (`distributions.py:204`) | idem |

## Observaciones de familia

- [COMPROBADO] En ambos prompts el mercado no entra como entrada; en la plataforma sí entra en la decisión vía `market_shrink` (`probabilities.py:304-305`) y `uncertainty_penalty`. El incumplimiento del principio es de la plataforma, no de los prompts.
- [INFERENCIA] Los dos prompts piden un simulador de reglas reales (extras con corredor automático / OT + SO) que la plataforma no tiene; para ambos usa Poisson/NB sobre marcadores finales. Para NHL lo compensa con `tie_adds_goal` + reescalado (`distributions.py:219-238`), que es una aproximación que no se aplica a béisbol (`adapters.py:96`).
- [RECOMENDACIÓN] Si se unifican, tomar del MLB la política «constante provisional con etiqueta» (da números ejecutables) y del NHL la separación `score_reg` / `score_for_settlement` y la lista de invariantes.
