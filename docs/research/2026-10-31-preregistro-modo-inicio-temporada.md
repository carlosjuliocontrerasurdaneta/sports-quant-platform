# Pre-registro — modos de inicio de temporada (NORMAL / CONSERVATIVE / SHADOW / BLOCKED)

**Fecha:** 2026-10-31. Escrito **antes** de calcular ningún efecto. No se ha
ejecutado ningún walk-forward para esta pregunta. Tampoco se ha calculado ningún
log loss, Brier, ECE, sesgo o acierto por partidos de temporada. Lo único
consultado es:

- el código: `src/sqp/sports/base.py:45-80`, `src/sqp/pipeline/daily.py:871-933`,
  `src/sqp/backtesting/engine.py:42-111` y `src/sqp/backtesting/tuning.py:36-38,196`;
- la skill `.claude/skills/season-transition/SKILL.md` y el vocabulario de
  `.claude/loops/quant/STATES.md`;
- la revisión de hoy, que cerró `BLOCKED` (final de
  `.claude/automation/runtime/current-task.md`);
- los pre-registros en curso (sección 13);
- el **calendario** de `data/historical/results_*.csv`: fechas, equipos y
  recuentos, **sin marcadores** (los scripts no leyeron las columnas de
  marcador);
- el estado agregado de `data/bets/prediction_gate.json`: solo los campos
  `allowed`/`latched` por corte, sin p-valores.

Código de referencia: `main` en `4cac45b` (en el árbol solo está modificado
`current-task.md`). La estructura sigue a
`2026-10-29-preregistro-elo-regresion-temporada.md` y a
`2026-09-26-preregistro-portero-nhl.md`:

- regla de límite de temporada heredada;
- particiones;
- reglas objetivas fijadas antes de medir;
- potencia razonada sin resultados;
- ejecución única;
- interacciones;
- decisiones del operador.

---

## 0. Regla fundamental que este documento respeta

**Generar no es apostar.** Se siguen generando picks de **todos** los deportes y
mercados, siempre. Ningún modo:

- elimina, oculta o filtra una fila del stream servido;
- cambia una probabilidad estimada o implícita, el edge, el ranking, el tier ni
  las entradas de un calibrador.

Un modo actúa sobre **una sola cosa: el factor de stake**, que se aplica al
final, **después** de todos los gates y solo puede reducir el stake. Además
añade columnas informativas (sección 12). Un gate quita el stake, nunca la fila.

**Hallazgo lateral, verificado en el código y no corregido aquí.** El único
mecanismo actual, `SportAdapter.reliability_warning` (`base.py:76`, con
`min_games=10`), no se limita a dejar el evento sin stake. En
`daily.py:932` hace `if price is None or p_model is None or warn: continue`, y
los mercados del evento **no generan fila de candidato**. Hoy está latente,
porque cuenta `games_played` de todo el histórico y lleva 0 avisos en 14 días.
No se ha verificado si el stream servido se construye exclusivamente a partir
de esos candidatos. **El modo de temporada no reutiliza ese camino.** Si
eliminar filas contradice la regla fundamental, lo decide el operador
(decisión 8).

## 1. La pregunta

Al cruzar un límite de temporada, el modelo arrastra el estado de la temporada
anterior. El Elo sin regresión (λ = 0 en producción) y las tasas de anotación
pasan intactos a la nueva temporada, aunque las plantillas hayan cambiado. Lo
más claro es NCAAB y WNCAAB: empiezan hacia el 2026-11-03 con el Elo de abril.

**Pregunta.** ¿Cuánto pierde el modelo en **habilidad probabilística** en
función de cuántos partidos de la temporada en curso llevan los equipos? ¿A
partir de qué recuento vuelve a su nivel de mitad de temporada?

La respuesta fija, por liga, una tabla de modos y de factores de stake que
**se deriva mecánicamente** de la medición (sección 7). No se elige ningún
número después de ver datos.

**Lo que no es.** No es una prueba de ventaja sobre el mercado. Siete
mediciones previas no la encontraron (encompassing, 2026-09-07). Un modo
NORMAL no significa «rentable». Se mantienen separadas la probabilidad
estimada, la probabilidad implícita, el edge, el hit rate observado frente al
prometido, el ROI esperado estimado y el ROI realizado.

## 2. ¿Cambia algo hoy en la práctica? No.

Según `data/bets/prediction_gate.json` (`generated_at`
2026-10-31T15:09:32Z, K = 52, 67 cortes evaluados), los **67/67 cortes tienen
`allowed = False`** y ninguno tiene `latched`. Todo el stake servido es 0 por
el prediction gate. Un factor ≤ 1 aplicado después del gate deja 0 en 0.

Hoy el modo solo añadiría columnas informativas. **Su efecto sobre el stake
empieza el día en que un corte abra.** Por eso no hay urgencia operativa,
tampoco por NCAAB del 3 de noviembre, y la secuencia de la sección 14 puede
esperar al resultado de «el modelo manda».

## 3. Datos

- `ResultsStore(ROOT).load(league)`, con la deduplicación por `game_id`, sobre
  una **instantánea** tomada en `--pre`. Se registran el SHA-256 y el número de
  filas por liga.
- **Corte de la medición: filas con `date ≤ 2026-06-30`.** Es el mismo corte
  del Elo NBA y de la fase H de la recencia.
  - Las temporadas que empezaron después (europeas 2026-27, NFL, NCAAF, NBA,
    NHL y Brasileirão/Chile/MLS tras el parón del Mundial) quedan fuera de toda
    medición.
  - Motivo: sus primeras jornadas ya se han servido y auditado a diario, así que
    no son ciegas.
- `date` es el día UTC del inicio, tomado como `str(...)[:10]`, igual que en
  producción y en el pre-registro del Elo.
- **No se filtra nada.** La pretemporada, las exhibiciones y los partidos
  neutrales cuentan como los observa el modelo.
- Los parámetros resueltos se ajustaron sobre este mismo histórico; S_b y S_ref
  son por tanto parcialmente in-sample en parámetros. Se declara; afecta a ambos
  lados del cociente. (Enmienda H11, revisión independiente 2026-10-31.)

## 4. Límite de temporada (heredado, sin cambios)

Es la regla de la sección 4 de `2026-10-29-preregistro-elo-regresion-temporada.md`:
hay un límite antes del primer partido de la fecha D si el hueco con la fecha
anterior con algún partido **de la liga** es de **≥ 30 días naturales UTC**.

- No se añaden excepciones.
- Es la misma regla que implementa `EloRatings` con `season_gap_days = 30`
  (commit `4cac45b`). En producción, el recuento de la sección 5 debe usar
  **esa misma lógica**, de una sola fuente, para que el modo y la regresión no
  diverjan.

**Robustez de la regla por liga (fijada ahora).** La regla solo se considera
inequívoca en una liga si el **menor hueco entre temporadas** dentro del corte
es de **≥ 60 días**, el doble del umbral. Si no lo es, un parón a mitad de
temporada (Mundial, Leagues Cup, fases de copa) cae en la zona del umbral. En
ese caso los «límites» no son cambios de plantilla y la liga **no se mide**
(sección 8).

El 60 (= 2 × 30) es una constante nueva de este documento, fijada sin datos. La
robustez exige además que el mayor hueco dentro de temporada sea ≤ 15 días
(= 30/2); el --pre informa ambos. Los límites por suspensión a mitad de
temporada (2020) se cuentan por la regla y se informan aparte en el informe
secundario 6. (Enmienda H7, revisión independiente 2026-10-31.)

**Primera temporada del histórico.** Es un arranque en frío, con todos los
ratings en la base. No es una transición, **no se mide** y solo sirve de
historia.

## 5. Variable de muestra

**m(e):** para un partido e del día D, el **menor** de los dos recuentos de
partidos de la temporada en curso de cada equipo. Solo cuentan los partidos con
fecha **estrictamente anterior** a D dentro de la misma temporada (sección 4).

- La clave de equipo es el nombre normalizado con `get_team_normalizer(league)`,
  el mismo que usa el adaptador.
- Se define solo con el calendario, sin resultados, así que no hay leakage.
- Se usa «el menor» y no la media, por la misma razón que el «al menos uno» del
  Elo: basta un equipo desfasado para que la probabilidad lo esté.

**R_L (frontera de «temporada madura»), solo con calendario:**
R_L = ⌊ (mediana sobre temporadas medidas de la mediana de partidos por equipo)
/ 2 ⌋. (Enmienda H8, revisión independiente 2026-10-31.) Es decir, la mitad de
una temporada típica.

- Los partidos con m ≥ R_L forman la **referencia** de la liga.
- Los partidos con m < R_L son **tempranos**.

**Cubetas fijas de m:**

- {0}, [1,2], [3,5], [6,10], [11,20], [21,40], [41,80];
- truncadas en R_L − 1.

**Muestra mínima por cubeta: n ≥ 200.** Es `MIN_EVAL_HOME_ADV = 200`
(`tuning.py:36`), los partidos evaluados que el proyecto exige para sobrescribir
un parámetro a partir del log loss. Si una cubeta no llega a 200, se fusiona
con la siguiente cubeta superior hasta llegar. Si sobra un resto final por
debajo de 200, se fusiona con la cubeta inferior. La referencia también exige
n ≥ 200.

## 6. Métrica

**Modelo:** la configuración de producción de cada liga en el commit del
`--pre`, resuelta con `get_adapter(league, family, params)`. El script imprime y
congela los parámetros resueltos. `elo_season_regression` está ausente, es decir,
vale 0.

La evaluación reproduce el bucle de `walk_forward_backtest(..., warmup=60)`: el
día D se estima con el estado al cierre de D−1. Se guarda el vector por partido,
y el script aserta que sus agregados coinciden con los de
`walk_forward_backtest` (paridad: el script aborta si no coinciden).

**Mercado primario: moneyline.**

- **Ligas a dos vías:** log loss binario con recorte 1e-12, la expresión de
  `tuning._binary_nll_series`. Los empates se excluyen, como en el motor.
- **Fútbol:** log loss a tres vías (`threeway_ll_terms` del motor).

**Línea base ingenua:** las frecuencias empíricas del resultado (victoria local;
en fútbol, local, empate y visitante) en todos los partidos de la liga con fecha
< D. Es expansiva y walk-forward, con recorte 1e-12. No tiene ningún parámetro
ajustable.

**Habilidad de una cubeta:** S_b = LL_ingenua(b) − LL_modelo(b), en medias por
partido. La habilidad de la referencia es S_ref.

**Pérdida de habilidad temprana:** G_b = S_ref − S_b.

**Por qué la habilidad y no el log loss crudo.** Al principio de temporada
cambian la mezcla de partidos (pretemporada, exhibiciones, calendario) y las
tasas de base. La línea base ingenua sufre esa mezcla igual que el modelo. La
diferencia aísla lo que el modelo sabe de más, que es justo lo que se degrada
con un estado desfasado.

**Factor de habilidad:** r_b = min(1, max(0, S_b / S_ref)), solo si S_ref > 0.
Si la habilidad temprana es una fracción de la madura, el edge informativo
también lo es. Kelly es proporcional al edge, así que el stake se escala por
esa fracción.

Supuesto de modelado (no derivado): se asume que la fracción de habilidad frente
a la línea base ingenua aproxima la fracción del edge informativo; S se mide
sobre la probabilidad cruda del adaptador (antes de calibración y de
market_shrink) y el stake de producción se dimensiona sobre la probabilidad
final frente a la cuota. El factor sale de la medición, pero su interpretación
como fracción de Kelly es un supuesto declarado. (Enmienda H5, revisión
independiente 2026-10-31.)

## 7. Regla de derivación de modos (fijada ahora; todas las condiciones a la vez)

Para cada liga medible (sección 8) y cada cubeta temprana b, después de las
fusiones de la sección 5:

1. **SHADOW** si S_b ≤ 0: el modelo no supera a la línea base ingenua. Factor 0.
2. Si no, **CONSERVATIVE** si G_b > 0,002. Factor r_b.
   - 0,002 es `IMPROVEMENT_MARGIN` (`tuning.py:38`), el margen de log loss que
     el proyecto considera material en todas sus mediciones.
3. Si no, **NORMAL**. Factor 1.

Después se aplican tres ajustes:

- **Estabilidad entre mitades.** Los límites medidos se reparten en dos
  mitades cronológicas: los ⌈k/2⌉ primeros y el resto. En cada mitad en que la
  cubeta tenga n ≥ 200, se aplica la misma regla. El modo final de la cubeta es
  el **más restrictivo** entre el agregado y las mitades evaluables. Su factor
  es el **menor** de los factores.
  En cada mitad, S_b, G_b y r_b se calculan con la S_ref de esa misma mitad; la
  mitad solo es evaluable para la cubeta si la cubeta y la referencia de esa
  mitad tienen n ≥ 200 y S_ref de la mitad > 0. Una mitad no evaluable no entra
  en el mínimo. (Enmienda H2, revisión independiente 2026-10-31.)
- **Envolvente monótona.** El modo de la cubeta b es el más restrictivo entre
  b y todas las cubetas tempranas superiores, y el factor es el mínimo sobre
  ellas. Una restricción tardía se propaga hacia atrás, nunca al revés.
- **Referencia sin habilidad.** Si S_ref ≤ 0, r_b no está definido y no hay
  CONSERVATIVE: cada cubeta temprana es SHADOW (factor 0) si S_b ≤ 0 y NORMAL
  (factor 1) si S_b > 0, con las mitades y la envolvente aplicadas igual. Se
  informa al operador como hallazgo aparte. (Enmienda H3, revisión independiente
  2026-10-31.)

Los partidos con m ≥ R_L son NORMAL por definición.

Orden de restricción: BLOCKED > SHADOW > CONSERVATIVE > NORMAL; el factor final
es siempre el mínimo de los factores comparados. (Enmienda H9, revisión
independiente 2026-10-31.)

**Multiplicidad.** No es un contraste de hipótesis con veredicto ACEPTA o
RECHAZA, sino una clasificación descriptiva con reglas fijadas de antemano. Los
errores por ruido van, por construcción, **hacia lo restrictivo**: la mitad
peor y la envolvente. El coste de un falso CONSERVATIVE no es pequeño: el error
estándar de r_b es ≈ EE(S_b)/S_ref, que con σ_d ∈ [0,2; 0,4] y S_ref del orden de
0,03 (no medida) vale ≈ 0,3–0,9 en cubetas de n ≈ 200 y ≈ 0,1–0,2 en n ≈ 3.700;
el mínimo sobre agregado, mitades y envolvente sesga además r_b a la baja, y un
SHADOW espurio en una mitad de n < 300 es plausible. Se acepta conscientemente
porque el error va hacia menos stake; el IC95 de r_b (§11) se publica junto a la
tabla y forma parte de la revisión previa a la activación. (Enmienda H1, revisión
independiente 2026-10-31.) Queda declarado y no se aplica ninguna corrección.

## 8. Ligas: medibles y BLOCKED por falta de historia (recuentos del 2026-10-31)

Los recuentos son del calendario, con corte ≤ 2026-06-30 y con la primera
temporada excluida. Se obtuvieron con `count_early.py` (scratchpad de la sesión),
normalizador `sqp`. El `--pre` debe reproducirlos y documentar cualquier
diferencia **antes** de medir.

| Liga | Límites medidos | Menor hueco entre temporadas (días) | R_L | Tempranos (m < R_L) | Días con tempranos | Referencia (m ≥ R_L) | Estado |
|---|---:|---:|---:|---:|---:|---:|---|
| NBA | 25 | 62 | 45 | 16.704 | 2.515 | 16.531 | **Medible** |
| NHL | 24 | 79 | 45 | 16.334 | 2.526 | 15.775 | **Medible** |
| NFL | 24 | 173 | 10 | 3.948 | 1.041 | 3.989 | **Medible** |
| MLB | 3 | 169 | 81 | 3.676 | 289 | 2.464 | **Medible** |
| NCAAF | 2 | 214 | 6 | 1.024 | 89 | 899 | **Medible** |
| WNBA | 3 | 193 | 22 | 450 | 175 | 315 | **Medible** (al límite) |
| EPL | 2 | 82 | 19 | 381 | 105 | 379 | **Medible**, 1 cubeta |
| LaLiga | 2 | 81 | 19 | 381 | 150 | 379 | **Medible**, 1 cubeta |
| Serie A | 2 | 76 | 19 | 385 | 130 | 375 | **Medible**, 1 cubeta |
| Bundesliga | 2 | 97 | 17 | 308 | 103 | 304 | **Medible**, 1 cubeta |
| Ligue 1 | 2 | 89 | 17 | 306 | 101 | 305 | **Medible**, 1 cubeta |
| Brasileirão | 3 | **52** | 19 | 568 | 160 | 369 | **BLOCKED** (regla de límite no robusta) |
| Chile | 3 | **54** | 15 | 360 | 175 | 240 | **BLOCKED** (ídem) |
| Liga MX | 3 | **33** | 18 | 500 | 175 | 491 | **BLOCKED** (ídem; Apertura/Clausura) |
| MLS | 5 | **30** | 7 | 528 | 101 | 939 | **BLOCKED** (ídem) |
| UCL | 5 | **41** | 2 | 160 | 24 | 247 | **BLOCKED** (ídem; fases de copa) |
| UWCL | 6 | **33** | 1 | 33 | 12 | 115 | **BLOCKED** (ídem) |
| NCAAB | **0** | — | (13)* | — | — | — | **BLOCKED** (una sola temporada, 2025-11-03 → 2026-04-07) |
| WNCAAB | **0** | — | (15)* | — | — | — | **BLOCKED** (una sola temporada, 2025-11-03 → 2026-04-05) |
| ATP / WTA | — | — | — | — | — | — | **Fuera de alcance** (circuito continuo; sin plantillas) |

\* R_L sale del calendario de la única temporada: medianas de partidos por
equipo de 27 y 30. Sirve solo para el modo por defecto (sección 9).

**Cubetas tempranas, con n agregado (mitad 1 / mitad 2), antes de fusionar:**

- **NBA:** {0} 552 (290/262); [1,2] 803; [3,5] 1.105; [6,10] 1.860; [11,20] 3.708;
  [21,40] 7.240; [41,44] 1.436. Siete cubetas sin fusión.
- **NHL:** {0} 557; [1,2] 759; [3,5] 1.096; [6,10] 1.851; [11,20] 3.604;
  [21,40] 7.078; [41,44] 1.389. Siete cubetas.
- **NFL:** {0} 431; [1,2] 769; [3,5] 1.158; [6,9] 1.590. Cuatro cubetas.
- **MLB:** {0} 47; [1,2] 92; [3,5] 144; [6,10] 226; [11,20] 460; [21,40] 898;
  [41,80] 1.809. Fusionadas: [0,5] 283; [6,10]; [11,20]; [21,40]; [41,80]. La
  mitad 2 es solo la temporada 2026 hasta el corte, con una referencia de 55,
  y casi nunca es evaluable.
- **NCAAF:** {0} 285; [1,2] 349; [3,5] 390. Tres cubetas.
- **WNBA:** {0} 30; [1,2] 42; [3,5] 65; [6,10] 104; [11,20] 196; [21,21] 13.
  Fusionadas: [0,10] 241 y [11,21] 209. La referencia de la mitad 2 es 0, porque
  la temporada 2026 está truncada por el corte.
- **Las cinco grandes ligas europeas:** [0,R_L−1] queda como **una sola
  cubeta** (EPL: [0,10] 220 más un resto [11,18] de 161, fusionado hacia abajo;
  Bundesliga: [0,10] 198 < 200, se fusiona hasta [0,16] 308). En fútbol, el modo
  es uno solo para toda la primera mitad de la temporada.

## 9. Modo por defecto donde no se puede medir (definido sin mirar efectos)

Se aplica en NCAAB, WNCAAB, Brasileirão, Chile, Liga MX, MLS, UCL y UWCL:

- **m < R_L → BLOCKED.** El modo no se puede determinar con evidencia, así que
  el factor de stake es **0**. La fila se sirve completa.
- **m ≥ R_L → NORMAL.** Factor 1: el modo de temporada no interviene, y siguen
  mandando todos los demás gates.

**Razón.** Sin evidencia, la regla de `STATES.md` («si no puede determinarse a
partir de un artefacto… `BLOCKED`, nunca `PASS`») se traduce en no dimensionar
stake. No se elige ningún número: R_L sale del calendario.

**Disponibilidad de datos, cubierta por construcción.** Si una liga no tiene
resultados de la temporada en curso, todos sus partidos tienen m = 0. Es el
caso de NCAAB y WNCAAB hoy: sin resultados desde abril y con picks servidos
desde el 2026-11-01/03. Si la ingesta se cae ≥ 30 días, la regla de límite
reinicia m. Las dos situaciones desembocan en el lado restrictivo.

**Con los recuentos actuales:**

- **NCAAB** estaría en BLOCKED hasta que los dos equipos lleven 13 partidos,
  hacia finales de diciembre o enero.
- **MLS** vuelve a m = 0 tras cada parón ≥ 30 días, lo que también es
  restrictivo.
- En todas estas ligas, el stake es hoy 0 de todos modos (sección 2).

**Salida de BLOCKED.**

- **NCAAB y WNCAAB** se vuelven medibles cuando termine la temporada 2026-27,
  que es su primer límite (2026-11-03). La medición va en el verano de 2027, con
  esta misma regla y un corte nuevo que se declara en un addendum **antes** de
  medir.
- **Las ligas con la regla no robusta** solo salen con un calendario de
  temporadas oficial, externo y versionado, que sustituya a la regla de 30 días
  en esa liga. Eso exige un pre-registro propio (decisión 6).

En las ligas BLOCKED por regla de límite no robusta (Brasileirão, Chile, Liga MX,
MLS, UCL, UWCL), R_L y m dependen de esa misma regla; el modo por defecto hereda
su falta de fiabilidad. Se declara como limitación y la decisión 6 incluye una
tercera opción: factor 0 para todo m hasta disponer de un calendario oficial.
(Enmienda H4, revisión independiente 2026-10-31.)

## 10. Potencia (calendario, sin resultados)

Con σ_d, la desviación típica por partido de (LL_ingenua − LL_modelo), el error
estándar de S_b es ≈ σ_d / √n_b. **σ_d no se ha medido**, porque exige
resultados. Como orden de magnitud declarado, σ_d entre 0,2 y 0,4:

| n de la cubeta | EE(S_b) |
|---:|---|
| 200 | 0,014–0,028 |
| 552 (NBA {0}) | 0,009–0,017 |
| 3.700 (NBA [11,20]) | 0,003–0,007 |

**Consecuencias, declaradas antes de medir:**

1. **La frontera CONSERVATIVE/NORMAL** (G_b > 0,002) **no es resoluble** con el
   ruido en ninguna cubeta. Es 2–14 veces más pequeña que el error estándar.
   Con la mitad más restrictiva y la envolvente, es **probable que casi todas
   las cubetas tempranas queden CONSERVATIVE**, con factores r_b de varianza
   alta (véase §7) y sesgados a la baja por el mínimo; el factor continuo no
   absorbe ese ruido, solo lo orienta hacia menos stake. (Enmienda H1, revisión
   independiente 2026-10-31.)
2. **SHADOW** (S_b ≤ 0) solo aparecerá si la habilidad temprana se hunde de
   verdad. Con una S_ref típica del orden de varias centésimas (no medida),
   es detectable en NBA, NHL, NFL y MLB, y dudoso en WNBA, NCAAF y fútbol.
3. **Fútbol con dos límites** es la medición más débil: una cubeta de unos 300
   a 380 partidos y un factor con un error estándar grande. Se aplica la regla
   igual.
4. El `--pre` informa, **sin desenlaces**, el n final de cada cubeta tras las
   fusiones, por liga y por mitad.

## 11. Incertidumbre e informes secundarios (no deciden)

**Bootstrap por bloques de días UTC:** 10.000 réplicas, semilla 42. Se
informan el IC95 percentil de S_b, G_b y r_b, y el de S_ref. No es una puerta
(E8 del clima: no hay umbral fijado por el operador).

**Informes secundarios:**

1. ECE (`expected_calibration_error`, 10 bins) y Brier por cubeta y en la
   referencia.
2. Sesgo por cubeta: probabilidad media del local menos la tasa observada.
3. La variante «los dos equipos» (el mayor de los recuentos) en lugar de m.
4. NBA y NHL sin exhibiciones, con la regla de ≤ 25 apariciones del descanso.
5. Totales con líneas fijas (q25, q50 y q75 del total en el entrenamiento,
   redondeadas al medio punto), con la habilidad frente a la frecuencia ingenua
   del over. El modo es por liga y no por mercado (decisión 2); este informe
   indica si los totales se comportan distinto.
6. S_b de la cubeta {0} por temporada (por ejemplo, la burbuja NBA de 2020).
7. Perfil de S_b sin fusionar, en las cubetas con n < 200, marcadas como no
   evaluables.

## 12. Comportamiento de cada modo (qué toca y qué no)

| Modo | Factor de stake | Fila servida | Probabilidad, edge, ranking, tier, calibrador | Columnas nuevas |
|---|---|---|---|---|
| NORMAL | 1 | sí, intacta | sin cambios | `season_mode`, `season_games_min` (m), `season_stake_factor` |
| CONSERVATIVE | r_b ∈ (0, 1), congelado | sí, intacta | sin cambios | ídem |
| SHADOW | 0 | sí, intacta | sin cambios | ídem |
| BLOCKED | 0 | sí, intacta | sin cambios | ídem |

**Reglas:**

- `stake_final = stake_tras_todos_los_gates × season_stake_factor`. Se aplica
  el último y nunca abre nada que un gate haya cerrado.
- **El tier no se toca.** El tipster A/B/C/NO BET sigue igual mientras no se
  ejecute la medición de la brecha del tier A (≈ julio de 2027; sección 13).
  Marcar el tier con el modo sería un cambio de régimen en su ventana
  (decisión 4).
- **La configuración** va en un fichero propio (propuesta:
  `configs/season_modes.yaml`), con la tabla por liga: R_L, cubetas, modo y
  factor. Lleva el SHA del JSON de resultado.
  - **No** va en `league_params` ni en `LEAGUE_OVERRIDES`: no debe cambiar
    ningún parámetro resuelto (la fase M de la recencia aserta «y ninguna otra
    clave»).
- **Implementación** (propuesta: `src/sqp/risk/season_mode.py`). El cálculo de
  m en producción reutiliza la detección de límite de `EloRatings` (una sola
  fuente) y la normalización del adaptador.
- **Tests obligatorios:**
  - el valor por defecto sin tabla no tiene efecto;
  - ninguna fila desaparece;
  - el factor nunca sube el stake;
  - m se calcula con fecha < D;
  - el límite se detecta con 30 días;
  - las ligas sin medición caen en BLOCKED si m < R_L.
- En producción, m(e) cuenta solo partidos de la temporada en curso con
  resultado ingerido y fecha < min(D, fecha de generación). Como el factor de la
  envolvente es no decreciente en m, el infrarrecuento es conservador. Test
  obligatorio: m no cuenta partidos sin resultado. (Enmienda H6, revisión
  independiente 2026-10-31.)
- **Disponibilidad de features activas** (abridor MLB `pitcher_bound 0.05`,
  descanso NBA 0,795, `tilt_scale` NHL): este pre-registro **no** añade reglas
  sobre ellas. La conducta cuando falta su entrada la sigue decidiendo el
  código actual. Queda como decisión 10.

## 13. Interacciones con los tests en curso

**La medición no interfiere con ninguno.** Lee una instantánea del histórico y
no toca:

- el stream;
- `prediction_gate.json`;
- los calibradores;
- la configuración.

**Una activación** añade tres columnas al stream servido, lo que cambia el
contrato de un artefacto persistido (clase de escalado), y reduce el stake
después de los gates.

| Test | Qué evalúa | Efecto de activar el modo | Qué hace falta |
|---|---|---|---|
| **«El modelo manda»** (≈ mediados o finales de nov-2026, N = 3.402) | `p_cal` / `market_shrink` | Ninguno sobre probabilidades. Las columnas son aditivas | **Activar después de que su resultado esté commiteado.** Si no, addendum previo que declare las columnas |
| **Recencia, fase M** (D = 2027-01-31) | totales con `model_probability`; el `--pre` aserta los parámetros resueltos | Ninguno, si la tabla vive fuera de `league_params` (sección 12) | Test que pruebe que los parámetros resueltos no cambian |
| **Peso del mercado por segmento** (≈ mar-2027) | `p_cal` por segmento; `policy_stats` | Las probabilidades no cambian; las métricas con stake real podrían cambiar | Addendum de régimen previo (§10 de aquel documento), solo aditivo |
| **Brecha del tier A** (≈ jul-2027) | el tier A tal como opera | Ninguno, mientras el tier no se toque | Addendum A2 previo si el modo llega a afectar al tier o al stake del tier A |
| **Gate K = 52** | `model_probability` pura por corte, con stake plano | Ninguno: el modo va después del gate y no cambia `model_probability`, K ni el techo de 63 | Nota de registro informativa; no se necesita addendum de régimen |
| **Regresión del Elo NBA** (`4cac45b`, por defecto 0; activación propuesta en el verano de 2027) | log loss temprano NBA | Comparte la regla de límite. Si se activa la regresión, cambia la habilidad temprana NBA | La tabla NBA de este documento queda **obsoleta**: se re-mide con este mismo script antes de la temporada 2027-28 (re-medición pre-registrada, sección 14), con la regresión activa |

## 14. Compromisos de ejecución

**Script:** `scripts/research/measure_season_modes.py`, con tres modos:

- `--pre`: imprime los recuentos de la sección 8 por liga, mitad y cubeta (antes
  y después de fusionar), los límites, R_L, el SHA de la instantánea y los
  parámetros resueltos. **No compara ninguna probabilidad con ningún
  resultado.** Debe reconciliar explícitamente el número de límites NBA con los
  26 del pre-registro del Elo (§4) antes de medir; si difieren, documentar la
  causa. (Enmienda H10, revisión independiente 2026-10-31.)
- `--parity-only`: comprueba la paridad con `walk_forward_backtest`.
- modo completo: produce el JSON (`--out`) con S, G, r, el modo por cubeta y los
  informes secundarios.

**Reglas:**

- El script se commitea **antes** del modo completo, con revisión de Fable
  frente a este texto.
- **Una sola ejecución** del modo completo. Después de ver el resultado no se
  cambian:
  - la regla de límite ni la de robustez;
  - R_L;
  - las cubetas ni la fusión;
  - la línea base ni la métrica;
  - los umbrales 0,002 y 200;
  - la regla de modos.
- **Re-ejecución:** solo por un defecto de código o datos demostrable a ciegas
  (paridad rota, otra instantánea, recuentos distintos). Se commitean las dos
  salidas.
- **Re-medición anual pre-registrada:** en el parón de cada liga, con el mismo
  script, la misma regla y un corte nuevo declarado en un addendum **antes** de
  medir. Así entran NCAAB y WNCAAB en el verano de 2027, y se re-mide la NBA si
  se activa la regresión del Elo. No es un nuevo grado de libertad: solo cambia
  el corte.
- **La tabla resultante no se activa sin** aprobación del operador y revisión
  de Fable **antes** del commit (parámetro de riesgo/stake y contrato de
  artefacto: clase de escalado, `MODEL_ROUTING.md`).

## 15. Decisiones del operador

1. **Aprobar la regla de la sección 7:** habilidad frente a la línea base
   ingenua; SHADOW si S ≤ 0; CONSERVATIVE si G > 0,002 con factor r_b; mitad más
   restrictiva; envolvente monótona; n ≥ 200 por cubeta.
2. **Un modo por liga para todos los mercados** (propuesta) o un modo por
   mercado. Esto último exige medir spreads y totales como primarios, con menos
   potencia.
3. **Modo por defecto en las ligas no medibles** (sección 9): factor 0 mientras
   m < R_L (propuesta) o NORMAL.
4. **El tier no se toca** hasta la medición de la brecha del tier A (propuesta).
5. **Corte en 2026-06-30** (propuesta) o incluir los límites de 2026-27 ya
   servidos de las ligas europeas, que no son ciegos.
6. **Ligas con la regla de límite no robusta** (Brasileirão, Chile, Liga MX,
   MLS, UCL, UWCL): BLOCKED por defecto (propuesta) o un calendario oficial por
   liga, con su propio pre-registro; o, como tercera opción, factor 0 para todo
   m hasta disponer de un calendario oficial. (Enmienda H4, revisión
   independiente 2026-10-31.)
7. **Tenis fuera de alcance** (propuesta).
8. **`reliability_warning` en `daily.py:932`:** hoy hace `continue` y los
   mercados del evento no generan candidato. Abrir una revisión aparte
   (`bugfix`) para comprobar si eso elimina filas del stream servido y alinearlo
   con «un gate quita el stake, nunca la fila».
9. **Momento de activación:** después del resultado de «el modelo manda»
   (propuesta). Hoy no cambia ningún stake (sección 2).
10. **Disponibilidad de features activas:** dejarla fuera de este modo
    (propuesta) o pre-registrar una regla aparte. Mientras no se decida, el
    cierre de la skill season-transition para este pre-registro es BLOCKED en
    el apartado de disponibilidad de features (STATES.md), sin efecto sobre el
    stake. (Enmienda H12, revisión independiente 2026-10-31.)

---

Relacionado: [[2026-10-29-preregistro-elo-regresion-temporada]],
[[2026-09-26-preregistro-portero-nhl]], [[2026-08-26-preregistro-el-modelo-manda]],
[[2026-10-09-preregistro-recencia-totales]],
[[2026-10-13-preregistro-peso-mercado-por-segmento]],
[[2026-10-02-preregistro-brecha-tier-a]], [[2026-09-25-repreregistro-gate-k52]].
