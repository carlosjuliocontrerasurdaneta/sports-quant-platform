# Auditoría de PROMPT_191_CHILE_v1_0.md

Fecha: 2026-11-10. Citas `CHI:n` = líneas de `C:\dev\Prompts\PROMPT_191_CHILE_v1_0.md`.

## 1. Ficha

| Campo | Valor |
|---|---|
| Fichero | `PROMPT_191_CHILE_v1_0.md` |
| Versión | "v1.0"; fecha de especificación 10 de noviembre de 2026 (CHI:1, :4) |
| Deporte / competición | Fútbol masculino; Campeonato Nacional de Primera División de Chile ("Liga de Primera Mercado Libre" en 2026, CHI:3) |
| Tamaño | 402 líneas, 21 fases, 40 controles C01-C40 (CHI:331-383), 17 reglas absolutas (CHI:35-51) |
| Rol | Motor cuantitativo de pricing pregame (CHI:14) |
| Objetivo | `lambda_home`, `lambda_away`, distribución conjunta, 1X2, BTTS, portería a cero, totales, hándicaps (con push y asiáticos parciales), EV si hay cuotas (CHI:16-25) |
| Modos | `CALCULADO` / `EXPLORATORIO` / `INCOMPLETO` (CHI:316); `ModelStatus` VALIDADO/EXPLORATORIO/INCOMPLETO (CHI:277-281). Zona `America/Santiago` (CHI:8) |

## 2. Reglas y restricciones

- [COMPROBADO] "Las cuotas y líneas del mercado no son inputs del modelo deportivo" (CHI:14); regla 3: "No consultar ni incorporar cuotas en las fases de estimación de tasas o distribuciones" (CHI:37).
- [COMPROBADO] Regla 8: "No importar coeficientes de Brasil, Argentina, México o Europa sin recalibración o justificación empírica" (CHI:42). Regla 5: la clasificación, la fama o el historial de clásicos no son parámetros (CHI:39).
- [COMPROBADO] Regla 10: ninguna ventaja fija por altitud, césped sintético, desplazamiento o clima sin validación (CHI:44), con mención específica a Cobresal y Cobreloa: "No aplicar bonificación automática" (CHI:156).
- [COMPROBADO] Regla 14: `CLV observado` requiere cuota de cierre real (CHI:48). Regla 15: no afirmar que se corrió Monte Carlo si solo se describió (CHI:49).
- Condiciones de VALIDADO (CHI:279): modelo entrenado, evaluado fuera de muestra, calibración y versión reproducible documentadas.

## 3. Variables y parámetros

| Nombre | Valor | Unidad | Fase/línea | Justificación |
|---|---|---|---|---|
| Clubes / partidos por club | 16 / 30 (dos ruedas de 15 fechas) | | F1 :59 | Bases ANFP 2026 (enlace CHI:387) |
| Puntos | 3/1/0 | | :59 | |
| Descensos | 2 | | :59 | |
| Desempate del título | partido definitorio si dos clubes igualan en puntos en el primer puesto | regla | :59, :291 | Bases 2026; [HIPÓTESIS] sin verificar aquí |
| Ascendidos 2026 | Universidad de Concepción, Deportes Concepción | | F8 :124 | [HIPÓTESIS] |
| `w = n_eff/(n_eff+tau)` | `n_eff`, `tau` aprendidos | | F8 :119-120 | "deben ser aprendidos y documentados" |
| `beta_0`, `beta_HFA`, `attack_i`, `defense_weakness_i`, `theta` | estimados | | F15 :174-176 | |
| `rho` DC | estimado | | F16 :206-214 | |
| Masa retenida | `>= 0.999999` antes de renormalizar | probabilidad | F16 :216 | Tolerancia |
| Stake asiático | 50/50 | | F18 :242 | |
| `D > 1` | | cuota decimal | F19 :248 | |

[COMPROBADO] Ningún coeficiente deportivo fijado.

## 4. Fuentes de datos

[COMPROBADO] CHI:65-73: 1) ANFP y Campeonato Chileno; 2) clubes y partes médicos; 3) proveedores de eventos/tiros con registro de licencia y cobertura; 4) otras fuentes estadísticas trazables; 5) meteorología verificada. Para cada campo: `source_url`, `retrieved_at`, `published_at/as_of`, `definition`, `unit`, `sample`, `provider`, `missingness`, `confidence` (CHI:73). Control de calidad con homologación de IDs (Universidad de Concepción ≠ Deportes Concepción, CHI:77), cobertura real de xG por partido (CHI:83). La fuente xG mencionada es FootyStats, "proveedor no oficial; ver licencia/cobertura" (CHI:393). [INFERENCIA] Es la liga con peor cobertura de datos avanzados de la familia: el Nivel B de goles (CHI:103) será el habitual.

## 5. Cadena predictiva

1. Niveles de modelo (F6, CHI:101-107): A) xG/NPxG de calidad + ratings calibrados + modelo de goles reales; B) goles GF/GA ajustados por rival, localía y regularizados, "entrenados históricamente" (etiquetar `fallback_goals`, no `xG reconstruido`); C) prior real de liga o `NO CALCULADO`.
2. Ratings (F4-F5, F7): `NPxGF/90`, etc.; ataque y debilidad defensiva estimados conjuntamente con restricciones de identificación (ej.: suma de ataques = 0, CHI:111).
3. Regularización (F8): `w = n_eff / (n_eff + tau)`; `rating_post = w * rating_actual + (1-w) * rating_prior` (CHI:119-120).
4. Forma, once, matchup, balón parado y tarjetas, estadio, descanso (F9-F14): sólo con modelos entrenados (CHI:128, :140, :185).
5. Goles esperados (F15):
   `log(lambda_H) = beta_0 + beta_HFA * home_effect + attack_H + defense_weakness_A + theta' X_H` (CHI:174)
   `log(lambda_A) = beta_0 + attack_A + defense_weakness_H + theta' X_A` (CHI:176)
   Baseline: `lambda_H = league_goals_home * off_H * weak_A` (CHI:191).
6. Distribución (F16): `P(H=h, A=a) = Pois(h; lambda_H) * Pois(a; lambda_A)` (CHI:200); `P_DC(h,a) = tau(h,a; lambda_H,lambda_A,rho) * P_Pois(h,a)` con `tau(0,0)=1 - lambda_H*lambda_A*rho`, `tau(0,1)=1 + lambda_H*rho`, `tau(1,0)=1 + lambda_A*rho`, `tau(1,1)=1 - rho` (CHI:206-211). Malla hasta retener `>= 0.999999`, sin atribuir masa truncada al 0-0 (CHI:216).
7. Mercados (F17-F18): `P_local = sum_{h>a} P(h,a)`, `P_empate`, `P_visita` (CHI:222-224); BTTS, portería a cero, totales, hándicap con push (CHI:234-240); asiáticos de cuarto "Over 2,25 = 0,5 Over 2,0 + 0,5 Over 2,5"; "Un total exactamente 2 implica media pérdida; exactamente 3 implica ganancia completa" (CHI:242).
8. Eliminatorias/título: no hay playoffs (campeonato de tabla anual); título, cupos y descenso solo con simulador de calendario restante (CHI:291). Prórroga/penales: no aplica en liga (CHI:61).
9. Monte Carlo: opcional, con seed e iteraciones registradas (CHI:216).

## 6. Auditoría matemática

- [COMPROBADO] Fórmulas DC y Poisson correctas; ejemplo asiático correcto (Over 2,25 con total 2 devuelve media apuesta y pierde media: pérdida neta de media unidad; con 3 gana todo).
- [COMPROBADO] Tolerancia de cola expresada como retención `>= 0.999999` antes de renormalizar (CHI:216), equivalente a masa omitida `<= 1e-6` de las demás.
- [COMPROBADO] Distingue explícitamente que `E[H] = lambda_H` solo si las lambdas son esperanzas de la distribución elegida (CHI:228); condición que comparten UWCL (UWCL:251) y MLS (MLS:189). [INFERENCIA] Es correcto para DC (marginales preservadas) y para NegBin, no para cópulas arbitrarias.
- [INFERENCIA] Riesgo de sobreajuste: 16 clubes, 240 partidos por temporada; la plantilla de covariables (superficie sintética, altitud, clima, viaje, tarjetas) excede la información disponible. El prompt lo previene con la regla de que los efectos se "activan únicamente con evidencia empírica reproducible" (CHI:185).
- [INFERENCIA] Con 16 clubes y dos ascendidos por año, el efecto de ascendidos (CHI:124) afecta al 12,5 % de la liga; el prior de transición B → A es crítico y la muestra para estimarlo (2 clubes por año) es pequeña.
- [INFERENCIA] Altitud y superficie: Cobresal (Salvador, Atacama) y Cobreloa (Calama) juegan en altura moderada (Calama ~2.260 m); el prompt rechaza la "bonificación automática" y pide un efecto calibrado. Correcto, pero sin metodología: [RECOMENDACIÓN] efectos aleatorios por estadio con encogimiento fuerte.
- [COMPROBADO] Falta de datos: Nivel C solo con "prior realmente estimado" (CHI:105); multiplicadores ad hoc prohibidos ("-0,15 goles por lesión", CHI:107).
- [HIPÓTESIS] Descensos: "dos descensos" (CHI:59) y "Copa de la Liga 2026, nuevo torneo" (CHI:164) son hechos de calendario a verificar.

## 7. Independencia del mercado

| Cita | Mención | Clasificación |
|---|---|---|
| CHI:14 | Cuotas y líneas no son inputs | Principio |
| CHI:24 | EV solo con cuotas verificadas | COMPARACIÓN POSTERIOR LEGÍTIMA |
| CHI:37 | Regla 3: no incorporar cuotas en la estimación de tasas | Principio |
| CHI:73 | No tratar la predicción oficial de un proveedor como input si usa probabilidades o mercados | Principio; cierra una vía de contaminación indirecta |
| CHI:234-242 | Líneas `t`, `u` | UMBRAL LEGÍTIMO |
| CHI:246-262 | Congelar antes de cuotas; EV; CLV | COMPARACIÓN POSTERIOR LEGÍTIMA |
| CHI:272, :274 | Backtest con EV neto; "nunca usar las cuotas como input del motor" | COMPARACIÓN POSTERIOR LEGÍTIMA |
| CHI:289 | Ranking con cuotas | COMPARACIÓN POSTERIOR LEGÍTIMA |

[COMPROBADO] Sin ENTRADA PROHIBIDA. Es el único prompt que cierra la contaminación indirecta por proveedores cuyo "pronóstico" ya incorpora cuotas (CHI:73).

## 8. Validación que propone

[COMPROBADO] CHI:266-283: rolling-origin sin fuga; log loss multiclase, Brier, calibración; log-verosimilitud predictiva y control de colas; ablaciones (ataque/defensa base, xG, porteros, lesionados, localía, viajes, altitud, clima, forma, DC); comparación con Poisson simple; periodos con ascensos/cambios de cobertura; `MonteCarloError` si aplica. [INFERENCIA] 240 partidos por temporada es el mínimo viable; se necesita pooling de varias temporadas, lo que choca con cambios de plantilla y de cobertura xG. No define umbral de aceptación.

## 9. Contraste con la plataforma

- [COMPROBADO] `configs/leagues/soccer.yaml:13` `chile: {sport_key: soccer_chile_campeonato, avg_goals: 2.71}`; ESPN `soccer/chi.1` (`espn_results.py:93`); alias `team_aliases.yaml:51`; sedes `venues.yaml:216`.
- [COMPROBADO] Sin entrada en `ratings.yaml`; valores de familia (`registry.py:45-47`): `elo_home_adv 48`, `home_scoring_bonus 0.15`, `dc_rho 0.0`, `max_score 10`.
- Implementado: Poisson + DC (`distributions.py:71-83`, `204-309`), mercados de una sola malla, líneas asiáticas de cuarto (`:253-293`), 1X2 con `three_way` (`adapters.py:314-316`).
- Faltan: ratings con xG; porteros; once; altitud/superficie; tarjetas; prior de ascendidos; simulador de tabla/título/descenso; las reglas de Bases ANFP (partido definitorio).
- Difiere: Elo + tasas de gol globales en vez de ataque/defensa por club (`adapters.py:126-143`; `team_scoring.py:92-101`); `dc_rho 0.0` frente a la exigencia de estimarlo (CHI:214); posible doble localía ([INFERENCIA]: `elo_home_adv` y `home_scoring_bonus`); la malla se renormaliza sin informar la masa omitida (`distributions.py:294-297`), contra CHI:216; el edge de la plataforma está condicionado a no-push, el EV del prompt es incondicional (CHI:252, :256).
- **Mercado en las probabilidades de la plataforma:** [COMPROBADO] `market_shrink: 0.5` (`default.yaml:17`; `probabilities.py:303-306`; `daily.py:969-970`) mezcla el no-vig del consenso; contradice CHI:14 y CHI:37. Valor efectivo del `.env` no verificable (acceso denegado). `uncertainty_penalty 0.35` (`default.yaml:26`).

## 10. Veredicto por componente

| Componente | Veredicto | Motivo |
|---|---|---|
| Niveles A/B/C de modelo y etiqueta `fallback_goals` (CHI:101-107) | CONSERVAR | Honestidad sobre la cobertura xG en Chile |
| Cierre de contaminación por pronósticos de proveedor (CHI:73) | CONSERVAR | Más estricto que los demás |
| Modelo log-lineal y DC | CONSERVAR | Ya implementado en lo esencial |
| Prior de ascendidos B → A | INTEGRAR | Falta en plataforma; 2 clubes/año |
| Altitud y superficie | OPTIMIZAR | Efectos por estadio con encogimiento; hoy no hay modelo |
| Simulador de tabla/título/descenso con Bases ANFP | INTEGRAR (condicionado) | Verificar reglas (partido definitorio) antes |
| Tarjetas/expulsiones (F12) | DESCARTAR por ahora | Sin modelo calibrado el prompt ya prohíbe predecirlas |
| Edge condicionado a no-push de la plataforma | OPTIMIZAR | Alinear definiciones con CHI:256 al reportar |
| `market_shrink` de la plataforma | CORREGIR | Contradice CHI:14 y CHI:37 |
