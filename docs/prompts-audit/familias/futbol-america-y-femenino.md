# Familia fútbol-américa-y-femenino

Prompts: `PROMPT_191_UWCL_v1_0.md` (468 líneas), `PROMPT_191_MLS_v1_0.md` (360), `PROMPT_191_LIGA_MX_v1_0.md` (454), `PROMPT_191_BRASILEIRAO_v1_0.md` (431), `PROMPT_191_CHILE_v1_0.md` (402). Informes individuales en `docs/prompts-audit/individual/`. Fecha: 2026-11-10. La familia europea (`futbol-europa.md`) la audita otro agente y no se toca aquí.

## 1. Diff entre los prompts

**Medición.** [COMPROBADO] Comparando líneas no vacías exactas entre pares de ficheros, solo coinciden 4 a 10 líneas (por ejemplo UWCL-BRASILEIRAO 10; MLS-BRASILEIRAO 4); 2 líneas son idénticas en los cinco: la separación `---` y la fórmula `` `w = n_eff / (n_eff + tau)` ``. **No hay plantilla textual compartida**: son cinco redacciones independientes de una misma especificación semántica. Para detectar plantilla común hay que comparar contenido, no texto.

**Núcleo semántico común (idéntico en intención y a menudo en fórmula):**

- Principio fundamental: datos deportivos → λ → matriz conjunta de goles a 90' → mercados → solo entonces mercado/EV. El mercado "nunca" es input: MLS:18, UWCL:30, LMX:25, BRA:17 y :28, CHI:14 y :37.
- Modelo preferente log-lineal `log(lambda_H) = beta0 + (HFA) + Attack_H + DefenseWeakness_A + contexto` (MLS:151, UWCL:203, LMX:182, BRA:164, CHI:174).
- Baseline Poisson independiente; Dixon-Coles con las cuatro `tau` estándar (todas idénticas en forma: UWCL:227-231, LMX:216-220, BRA:200-203, CHI:208-211; MLS la nombra sin escribir las fórmulas, MLS:179).
- Mercados desde una sola matriz: `P_1`, `P_X`, `P_2`, BTTS, portería a cero, totales con push, hándicap con push, doble oportunidad, DNB; asiáticos de cuarto con 50/50 (MLS:195-223; UWCL:243-276; LMX:230-266; BRA:216-239; CHI:222-242).
- Shrinkage `w = n_eff/(n_eff+tau)` con `tau` "estimado, no fijado" (todos).
- EV: `EV = P_win*(D-1) - P_loss` y `Edge_pp = 100*[P_win - (1-P_push)/D]`, con aclaración de que no es `|P-0.5|` (MLS:266, UWCL:324-336, LMX:304-308, BRA:260-264, CHI:252-256); CLV solo con cierre real.
- Estados VALIDADO / EXPLORATORIO / INCOMPLETO y la salida NO CALCULADO en lugar de números inventados (todos).
- Congelación previa a cuotas (MLS:254-256, UWCL:320, LMX:292-296, BRA:243-252, CHI:246).

**Lo que cambia (constantes y fases propias):**

| Aspecto | MLS | UWCL | Liga MX | Brasileirão | Chile |
|---|---|---|---|---|---|
| Género / nivel | masc., liga + playoffs | femenino, copa continental | masc., 2 torneos/año | masc., liga larga | masc., liga anual |
| Fase propia exclusiva | Playoffs 2026: Wild Card, Bo3, ET (F17) | Escala interligas (F5); fase liga y tabla (F18); título (F19) | Liguilla con desempate por posición (F18); altitud (F12) | Ascendidos B→A (F6); receso Mundial 2026 (F13); viajes largos (F12) | Estadio real, superficie y altitud (F13); tarjetas (F12); simulador de tabla/descenso (F21) |
| Estructura numérica del formato | 3/1/0; ET 2x15' desde semifinales de conferencia | 18 clubes, 6 partidos, 4+8 plazas | 18 clubes, 17 jornadas, 8 a cuartos | 20 clubes, 38 jornadas | 16 clubes, 30 partidos, 2 descensos |
| Tolerancia de cola | sin valor numérico | 1e-6 | 1e-6 (YAML y F14) | 1e-6 | retención >= 0.999999 |
| Prior de ascendidos | no | no | solo aviso | sí, con 4 clubes nombrados | sí, con 2 clubes nombrados |
| Nº de controles | 30 | 40 | 35 | 45 | 40 |
| Ejemplo de fuente avanzada | ASA | proveedores "cuya cobertura se confirme" | FotMob | proveedores genéricos | FootyStats |
| Ejemplos de prohibición | `rho` manual | 50/50 en penales | altitud fija | `-0.15 xG` por baja | `-0,15 goles` por lesión; bono a Cobresal/Cobreloa |

## 2. Contradicciones entre ellos

1. [COMPROBADO] **Tolerancia de cola:** MLS exige "tolerancia numérica especificada" sin cifra (MLS:181); los otros cuatro fijan 1e-6 (UWCL:235, LMX:224/68, BRA:208, CHI:216, este último como retención >= 0.999999). Equivalentes salvo en MLS, donde el criterio es inoperante.
2. [COMPROBADO] **Etiqueta de salida:** `ValidationStatus` (MLS, UWCL, LMX), `MODEL_STATUS` (BRA), `ModelStatus` y además `RESULTADO: CALCULADO/EXPLORATORIO/INCOMPLETO` (CHI:316). Sin impacto de cálculo, pero un consumidor automático necesita un esquema único.
3. [COMPROBADO] **Nombre y signo de la defensa:** `DefenseWeakness` (MLS, UWCL, LMX), `Dweak` (BRA), `defense_weakness` (CHI); LMX:108 avisa de invertir el signo si la defensa se modela como fortaleza. Convención común: mayor = más débil.
4. [COMPROBADO] **Parámetro de localía:** MLS usa `beta0_H` y `beta0_A` o un único término (MLS:159), UWCL `HFA` (:203), LMX `beta_home*H` (:182), BRA `beta_home` (:164), CHI `beta_HFA` (:174). Todos exigen aplicarlo una sola vez. [INFERENCIA] La plataforma lo aplica por dos vías (ver informes).
5. [COMPROBADO] **Definición de "edge":** todos usan `Edge_pp = 100*[P_win - (1-P_push)/D]` (precio, no probabilidad); la plataforma define `edge` como EV por unidad resuelta condicionado a no-push (`pipeline/daily.py`, comentario sobre AUD-011). Los números no son directamente comparables.
6. [COMPROBADO] **Prórroga y penales:** MLS la modela por ronda; UWCL solo en la vuelta y final; LMX la usa solo en la final y declara ausencia de ET en cuartos y semifinales (LMX:281); BRA y CHI la excluyen. No hay contradicción de fondo, pero no existe una definición común de `q_shootout`: MLS lo trata como probabilidad a modelar (MLS:240-242), UWCL prohíbe 50/50 (UWCL:47) y LMX lo deja en `NO CALCULADO` (LMX:286). Ninguno da un procedimiento para estimarlo.
7. [COMPROBADO] **Intervalo de predicción:** CHI:283 dice "No declarar intervalos numéricos sin método implementado", UWCL:344 pide `Uncertainty: CUANTIFICADA` y BRA:278 "CUANTIFICADA (método e intervalo)"; ninguno define el método.
8. [INFERENCIA] **Uso de xG como target:** todos dicen que xG no equivale a goles (MLS:171, UWCL:211, LMX:190, BRA:172, CHI:31), pero el baseline multiplicativo de cada uno usa índices de xG como si fueran tasas de gol; la conversión calibrada se exige sin dar su forma.

No se detectaron contradicciones en el principio de independencia del mercado: los cinco son compatibles con el principio del operador y ninguno usa el mercado como entrada.

## 3. Versiones y obsolescencia

- [COMPROBADO] Los cinco son "v1.0". No hay historial de cambios ni número de revisión; las fechas internas son 2026 (MLS reglas 2026, UWCL 2026/27, LMX 2026-11-10, BRA temporada 2026, CHI 10 de noviembre de 2026).
- [COMPROBADO] LMX (:6) y CHI (:4) están fechados el mismo día de la auditoría (2026-11-10), por lo que no hay desfase calendario, pero sus datos de formato (Apertura 2026, Bases 2026) son los que más envejecen: cada torneo o temporada puede cambiarlos; ambos lo dicen (LMX:34, :448; CHI:59).
- [COMPROBADO] MLS (:6), UWCL (:3), BRA (:45) se refieren a la temporada 2026 o 2026/27: UWCL fija su estructura "a 2026/27" aunque la competición se juega desde el otoño de 2026.
- [HIPÓTESIS] Todos los hechos de reglamento (Wild Card sin prórroga, ocho a cuartos sin Play-In, 18 clubes con 6 partidos, 16 clubes y dos descensos, clubes ascendidos de 2026) no se verificaron contra fuentes oficiales; son citas internas a enlaces del prompt.
- [INFERENCIA] Obsolescencia estructural: ninguno incorpora los resultados de las mediciones de la plataforma (por ejemplo, que el modelo queda encompassed por el consenso, o que `rho` DC y `home_scoring_bonus` se tuneen por liga). Los prompts parten de cero.
- [INFERENCIA] Falta de homogeneidad con la familia europea: este grupo cubre ligas de calidad de datos muy desigual, pero comparte el mismo esqueleto de 21 fases; los dos extremos (UWCL sin datos de eventos fiables y MLS con datos de ASA) piden el mismo andamiaje.

## 4. Tabla comparativa de constantes

| Constante | MLS | UWCL | Liga MX | Brasileirão | Chile |
|---|---|---|---|---|---|
| Líneas | 360 | 468 | 454 | 431 | 402 |
| Fases | 21 | 21 | 21 | 21 | 21 |
| Controles | 30 | 40 | 35 | 45 | 40 |
| Reglas absolutas | 18 | 20 | 17 | 17 | 17 |
| Tolerancia cola | no fijada | 1e-6 | 1e-6 | 1e-6 | >=0.999999 |
| `w` shrinkage | `n_eff/(n_eff+tau)` | idem | idem | idem | idem |
| `tau` | estimado | estimado | estimado | estimado | aprendido |
| `rho` DC | estimado | estimado | estimado | estimado | estimado |
| Stake asiático | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 |
| Puntos | 3/1/0 | 3/1/0 | (no explícito) | (no explícito) | 3/1/0 |
| Clubes en la competición | (no explícito) | 18 en fase liga | 18 | 20 | 16 |
| Partidos por club | (no explícito) | 6 | 17 | 38 | 30 |
| Prórroga | 2x15' desde semifinales de conferencia | 2x15' en vuelta y final | solo final | no | no |
| Penales sin ET | Wild Card y Bo3 Round One | tras ET | tras ET en final | no | no |
| Zona horaria | por estadio | por estadio | America/Mexico_City + local | por estadio | America/Santiago |
| `avg_goals` de la plataforma (`soccer.yaml`) | 3.07 (:11) | 3.00 (:30) | 2.85 (:10) | 2.40 (:12) | 2.71 (:13) |
| Override en `ratings.yaml` | `elo_home_adv 30`, `elo_home_away_split true` (:31-33) | ninguno | ninguno | ninguno | ninguno |

Valores de familia de la plataforma para las cinco (salvo el override de MLS): `elo_home_adv 48`, `home_scoring_bonus 0.15`, `tilt_scale 1.0`, `dc_rho 0.0`, `max_score 10`, `elo_k 18` (`src/sqp/sports/registry.py:45-47`).

## 5. Observaciones transversales de la plataforma

- [COMPROBADO] El fútbol de la plataforma se calcula con `SoccerAdapter(PoissonAdapter)`, `three_way=True` (`adapters.py:314-316`), `_rates` en `adapters.py:126-143`, mallas en `distributions.py:204-309`.
- [COMPROBADO] `market_shrink: 0.5` (`configs/default.yaml:17`) es global y se aplica al fútbol: `p_decision = (1-s)*cal(p_model) + s*fair` (`pipeline/probabilities.py:303-306`; `pipeline/daily.py:969-970`). Es el único punto donde el mercado entra en la probabilidad usada para decidir, y es contrario al principio compartido por los cinco prompts. El valor de producción del `.env` no es legible desde este agente: NO VERIFICADO.
- [INFERENCIA] Los cinco prompts piden estimar `rho`, `beta_home`, `tau`; la plataforma deja `dc_rho = 0.0` en estas cinco ligas y usa valores de familia para localía (sin ajuste por liga salvo MLS).
