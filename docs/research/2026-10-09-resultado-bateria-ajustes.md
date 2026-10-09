# Resultado — batería de los ajustes aditivos: 4 ACEPTA de 24 (solo totales, NBA y NFL), y ninguno activable tal como está programado

**Fecha:** 2026-10-09. Ejecución única del modo completo del pre-registro
`2026-09-27-preregistro-bateria-ajustes.md`, con sus Enmiendas 1, 2 y 3 y las
decisiones del operador del 2026-09-27 (Holm con α de familia 0,05 junto al
margen 0,002; medir ya y activar después).

## Procedencia

- **Código:** `scripts/research/measure_adjustment_battery.py`, HEAD `ee0ab19`
  (`ee0ab1970fc8…`), árbol limpio: `git_status_porcelain` vacío en todo el
  repositorio en el `--pre`, y en `src/`, `configs/` y `scripts/research/` en el
  modo completo.
- **Entradas:** instantánea `C:\dev\3\snapshots\bateria-ajustes-20261008`
  (Enmienda 1(g)), con 43 ficheros. El manifiesto de SHA-256 y filas del modo
  completo es idéntico al del `--pre` regenerado y al del `pre.json` original de
  `4d9efca`. También coinciden los SHA-256 de `configs/leagues/ratings.yaml`
  (`7b904e4c…b483`) y `configs/default.yaml` (`fc2f9520…eed8f`), y los parámetros
  resueltos de las cuatro ligas que deciden (Enmienda 1(b)).
- **`--pre` regenerado** (Enmienda 3(d).2): `pre_ee0ab19.json`, SHA-256
  `173a5c1c…66c14be`, que es el `pre_json_sha256` registrado en el resultado.
  - NBA, NHL y NFL coinciden con el `pre.json` de `4d9efca` (SHA-256 `cd3ba152…aaaee`)
    en todo salvo el bloque `procedencia`, que añade los campos del filtro por
    `game_id`.
  - MLB: 9.719 filas → **9.704** tras descartar las 15 copias anteriores de la
    Enmienda 3(c), que son exactamente las 15 de su tabla. A 2.430 partidos / 184 días,
    B 2.415 / 183, 9.644 evaluados. En NBA, NHL y NFL el filtro descartó 0 filas.
  - Filas leídas: NBA 34.065, NHL 32.900, NFL 8.046.
- **Comando:**
  `python scripts/research/measure_adjustment_battery.py --data-root C:\dev\3\snapshots\bateria-ajustes-20261008 --pre-json <instantánea>\pre_ee0ab19.json --out <instantánea>\resultado_ee0ab19.json`.
  Terminó con rc = 0 el 2026-10-09 hacia las 10:22, tras 3.025 s.
- **Salidas:** `resultado_ee0ab19.json` (SHA-256 `becee9ba…3accc1`) y
  `resultado_ee0ab19.log` (SHA-256 `dc135c3a…306de9`), las dos en la instantánea.
- **Paridades** (sección 7.2). Si alguna hubiera fallado, el script habría abortado
  antes de escribir el JSON.
  - **Paridad 1** (motor): desviación máxima **0,0** en h2h, spreads y totales de
    las líneas fijas de las cuatro ligas, con n h2h de 34.004 / 32.421 / 7.961 / 9.644.
  - **Paridades 2 y 3** (capa contra `adjust_model_probability`, con el c de la última
    partición y con todos los coeficientes a 0): desviación máxima **0,0** en
    **todos** los partidos de test. Son 115.992 + 57.996 comprobaciones en NBA,
    101.700 + 50.850 en NHL, 27.624 + 13.812 en NFL y 29.070 + 14.535 en MLB.
- **Optimizador:** Nelder-Mead convergió en todas las celdas (si no, el script
  aborta) y también en la estimación conjunta del informe 2, sin ninguna
  anotación de no convergencia. **Ningún informe secundario tiene `error`.**
- **Log:** solo hay avisos `emparejamiento AMBIGUO omitido` de `roi_engine`: 503
  líneas, que corresponden a 483 parejas (equipos y fecha) distintas. Son **2 de la NHL**
  (VGK–ANA el 2026-05-05 y COL–MIN el 2026-05-06, los mismos del resultado del tilt) y
  **481 de la MLB**, repartidas entre marzo y septiembre de 2026. No se limitan a las
  dobles carteleras del 25 y 26 de septiembre. Solo afectan al informe 7: ahí reducen
  el n, sin fabricar ninguna etiqueta (ver el informe 7).

Los números de este informe se han comprobado contra el JSON, sin fiarse de los
booleanos. Por ejemplo, la media de los Δ por partición de la celda 4 NBA, ponderada
por afectados (7.088 / 6.571 / 5.546), reproduce el −0,016435 combinado. El orden de
Holm y sus umbrales se han recalculado a mano.

## Veredicto: 4 ACEPTA y 20 RECHAZA

| Celda | ¿Acepta? | Δ afectados (crit. 1) | IC95 por días · EE | T − C (crit. 5) · IC95 | p · p Holm |
|---|---|---:|---|---|---|
| **adj4 NBA** (tendencia de totales) | **ACEPTA** | **−0,01644** (n = 19.205) | [−0,01898; −0,01393] · 0,00130 | −0,01606 · [−0,01857; −0,01355] | 5,4·10⁻³⁷ · 1,3·10⁻³⁵ |
| **adj10 NBA** (tasa O/U) | **ACEPTA** | **−0,01437** (n = 16.470) | [−0,01699; −0,01175] · 0,00134 | −0,01198 · [−0,01419; −0,00973] | 3,0·10⁻²⁷ · 7,0·10⁻²⁶ |
| **adj4 NFL** | **ACEPTA** | **−0,00936** (n = 4.564) | [−0,01308; −0,00558] · 0,00193 | −0,00901 · [−0,01256; −0,00535] | 5,9·10⁻⁷ · 1,3·10⁻⁵ |
| **adj10 NFL** | **ACEPTA** | **−0,00761** (n = 3.943) | [−0,01146; −0,00367] · 0,00197 | −0,00625 · [−0,00967; −0,00281] | 5,7·10⁻⁵ · 1,1·10⁻³ |

En las cuatro se cumplen los siete criterios, sin ninguno cerca de su frontera:

- criterio 2: Δ < 0 en cada partición;
- criterio 3: el ECE baja;
- criterio 4: c > 0 en las tres particiones;
- criterio 5: T bate a C con un IC95 lejos de 0;
- criterio 6: no aplica en totales;
- criterio 7: Holm rechaza.

**Holm** (K = 24, α = 0,05). Rechaza los cinco primeros:

1. adj4 NBA;
2. adj10 NBA;
3. adj4 NFL;
4. **adj4 NHL** (p 3,1·10⁻⁵ ≤ 0,05/21);
5. adj10 NFL (p 5,7·10⁻⁵ ≤ 0,05/20).

Se para en el sexto, adj10 NHL: p = 0,0046 > 0,05/19 = 0,0026. adj4 NHL pasa Holm,
pero rechaza por el margen.

### Las 24 celdas

c por partición (A/B/C; A/B en la MLB), en probabilidad por unidad de x.

- Criterio 1: Δ log loss (T − base) en los afectados del test combinado, ≤ −0,002.
- Criterio 2: Δ por partición, todos < 0.
- Criterio 3: ECE(T) ≤ ECE(base).
- Criterio 5: log loss(T) − log loss(C) < 0.
- Criterio 6: Δ de spreads ≤ 0 (solo en los ajustes 2, 8 y 9; media de ±1,5 en
  NHL y MLB).

«Falla» lista los criterios incumplidos.

| Celda | c | Crit. 1 | Crit. 2 | ECE base → T | Crit. 5 | Crit. 6 | p | Falla | Veredicto |
|---|---|---:|---|---|---:|---:|---:|---|---|
| adj2 NBA | 0,0038 / 0,0069 / 0,0029 | +0,00001 | −0,00004 / +0,00008 / −0,00001 | 0,0166 → 0,0157 | −0,00095 | +0,00006 | 0,60 | 1, 2, 6, 7 | RECHAZA |
| adj3 NBA | 0,0369 / 0,0466 / 0,0311 | +0,00000 | −0,00053 / +0,00059 / −0,00001 | 0,0166 → 0,0165 | −0,00096 | — | 0,51 | 1, 2, 7 | RECHAZA |
| adj8 NBA | 0,0568 / 0,0515 / 0,0453 | −0,00018 | −0,00061 / +0,00016 / −0,00002 | 0,0166 → 0,0103 | −0,00110 | +0,00022 | 0,34 | 1, 2, 6, 7 | RECHAZA |
| adj9 NBA | 0,0017 / 0,0017 / 0,0015 | −0,00041 | −0,00067 / −0,00006 / −0,00050 | 0,0166 → 0,0159 | −0,00137 | −0,00013 | 0,062 | 1, 7 | RECHAZA |
| **adj4 NBA** | 0,0157 / 0,0155 / 0,0154 | **−0,01644** | −0,01451 / −0,01684 / −0,01841 | 0,0291 → 0,0080 | −0,01606 | — | 5·10⁻³⁷ | — | **ACEPTA** |
| **adj10 NBA** | 0,590 / 0,580 / 0,571 | **−0,01437** | −0,01324 / −0,01300 / −0,01745 | 0,0291 → 0,0142 | −0,01198 | — | 3·10⁻²⁷ | — | **ACEPTA** |
| adj2 NHL | −0,0170 / −0,0235 / −0,0195 | −0,00007 | −0,00031 / +0,00009 / +0,00002 | 0,0100 → 0,0099 | +0,00002 | −0,00014 | 0,31 | 1, 2, 4, 5, 7 | RECHAZA |
| adj3 NHL | 0,0085 / 0,0085 / 0,0072 | −0,000003 | −0,000007 / +0,000004 / −0,000005 | 0,01000 → 0,01001 | +0,00007 | — | 0,46 | 1, 2, 3, 5, 7 | RECHAZA |
| adj8 NHL | 0,0200 / 0,0148 / 0,0103 | +0,00009 | +0,00012 / +0,00014 / +0,00002 | 0,0100 → 0,0087 | +0,00014 | +0,00025 | 0,79 | 1, 2, 5, 6, 7 | RECHAZA |
| adj9 NHL | 0,0058 / 0,0048 / 0,0054 | +0,00005 | +0,00004 / −0,00019 / +0,00027 | 0,0100 → 0,0115 | +0,00012 | +0,00029 | 0,68 | 1, 2, 3, 5, 6, 7 | RECHAZA |
| adj4 NHL | 0,0442 / 0,0408 / 0,0429 | −0,00198 | −0,00046 / −0,00300 / −0,00253 | 0,0143 → 0,0123 | −0,00435 | — | 3·10⁻⁵ | **1** | RECHAZA |
| adj10 NHL | 0,263 / 0,262 / 0,248 | −0,00155 | −0,00278 / −0,00106 / −0,00079 | 0,0143 → 0,0078 | −0,00377 | — | 0,0046 | 1, 7 | RECHAZA |
| adj2 NFL | 0,0434 / 0,0506 / 0,0429 | −0,00106 | −0,00134 / +0,00016 / −0,00214 | 0,0200 → 0,0220 | −0,00147 | +0,00026 | 0,054 | 1, 2, 3, 6, 7 | RECHAZA |
| adj3 NFL | −0,0062 / −0,0206 / −0,0128 | −0,00003 | −0,00007 / +0,00013 / −0,00016 | 0,0200 → 0,0214 | −0,00065 | — | 0,40 | 1, 2, 3, 4, 7 | RECHAZA |
| adj8 NFL | 0,0446 / 0,0375 / 0,0309 | +0,00023 | −0,00004 / +0,00022 / +0,00056 | 0,0200 → 0,0199 | −0,00044 | +0,00076 | 0,65 | 1, 2, 6, 7 | RECHAZA |
| adj9 NFL | 0,0018 / 0,0019 / 0,0017 | −0,00050 | −0,00076 / −0,00033 / −0,00038 | 0,0200 → 0,0244 | −0,00112 | +0,000003 | 0,18 | 1, 3, 6, 7 | RECHAZA |
| **adj4 NFL** | 0,0144 / 0,0141 / 0,0145 | **−0,00936** | −0,00700 / −0,01026 / −0,01123 | 0,0249 → 0,0056 | −0,00901 | — | 6·10⁻⁷ | — | **ACEPTA** |
| **adj10 NFL** | 0,382 / 0,379 / 0,392 | **−0,00761** | −0,00609 / −0,00882 / −0,00805 | 0,0249 → 0,0162 | −0,00625 | — | 6·10⁻⁵ | — | **ACEPTA** |
| adj2 MLB | −0,0056 / 0,0115 | +0,00017 | +0,00018 / +0,00017 | 0,0106 → 0,0100 | −0,00013 | +0,00005 | 0,94 | 1, 2, 4, 6, 7 | RECHAZA |
| adj3 MLB | −0,0079 / −0,0059 | −0,00004 | +0,000005 / −0,00009 | 0,0106 → 0,0115 | −0,00030 | — | 0,18 | 1, 2, 3, 4, 7 | RECHAZA |
| adj8 MLB | 0,0018 / 0,0139 | −0,00003 | −0,00004 / −0,00002 | 0,0106 → 0,0104 | −0,00030 | +0,00013 | 0,40 | 1, 6, 7 | RECHAZA |
| adj9 MLB | 0,0059 / 0,0069 | −0,00032 | −0,00091 / +0,00027 | 0,0106 → 0,0155 | −0,00058 | +0,00019 | 0,25 | 1, 2, 3, 6, 7 | RECHAZA |
| adj4 MLB | 0,0243 / 0,0240 | −0,00051 | −0,00193 / +0,00092 | 0,0059 → 0,0088 | −0,00047 | — | 0,28 | 1, 2, 3, 7 | RECHAZA |
| adj10 MLB | 0,2017 / 0,2014 | −0,00046 | −0,00205 / +0,00116 | 0,0059 → 0,0128 | −0,00036 | — | 0,32 | 1, 2, 3, 7 | RECHAZA |

Tamaños del test combinado:

- NBA: 19.332 partidos en h2h y en totales, y 19.332 en spreads;
- NHL: 16.950;
- NFL: 4.584 en h2h (sin empates) y 4.604 en totales y spreads;
- MLB: 4.845.

Afectados por celda: informe 10 y columna `n_afectados` del JSON. Coinciden con la
sección 13 en NBA y NHL; en la NFL, el h2h tiene unos pocos menos por los empates
(Enmienda 2(b).3).

**Lo que dice la tabla, en tres líneas:**

- **Calidad reciente (2, 8, 9) y cara a cara (3): nada en ninguna liga.** El mayor
  Δ es −0,0011 (adj2 NFL), un 53 % del margen y con p = 0,054. Es lo que la
  sección 3 anticipaba: son casi colineales con el Elo.
- **Totales (4, 10): efecto grande en NBA y NFL, real pero por debajo del margen en
  NHL, y nulo en MLB.**
- **El canal de nivel de la NHL que señalaba la Enmienda 1(d).4 no se ha
  materializado.** adj8 NHL da Δ = +0,00009, así que la lectura declarada allí no
  aplica.

## Dictamen de validez (antes de interpretar)

Un Δ de −0,016 en los totales NBA es unas 8 veces el margen, y mucho mayor que
cualquier ganancia medida antes en el proyecto. Además, la base de totales tiene un
log loss ≈ ln 2. Las dos cosas obligan a descartar una fuga antes de leer nada. Lo
comprobado:

**1. Ninguna feature ve el partido ni el día del partido.**

- `_prior_games` filtra `d < rd` (`src/sqp/backtesting/roi_engine.py:245`).
- Las ventanas de `rest_form` cortan por `date < ref`
  (`src/sqp/features/rest_form.py:57`, l. 106-127).
- `compute_pregame_features` usa `ref = ref_date[:10]` en todas las ventanas
  (l. 462-515). En particular, `avg_total` (l. 482-485) es la media de los totales
  de los últimos 10 partidos **anteriores**.
- En el script, el partido se añade a `team_hist` **después** de calcular su fila
  (`scripts/research/measure_adjustment_battery.py:691-696`), y las features se
  construyen con `_prior_games` antes de leer el marcador (l. 638-644). El
  marcador solo se lee en l. 655-657.

**2. La línea L_i no usa el resultado.**

- μ sale del estado del adaptador **al cierre del día anterior**: los partidos del día
  se observan solo cuando cambia la fecha (l. 604-607). μ se calcula antes
  (l. 614-630), y `L = ⌊μ⌋ + 0,5` en l. 630.
- La consistencia de μ con `adapter.estimate` se asierta partido a partido
  (l. 663-669).
- El desenlace del mercado de decisión es `total > L` (l. 837).

**3. No hay contaminación entre entrenamiento y test.**

- c y a se estiman solo con `date ≤ train_end`, el día anterior al test (l. 863).
- Cada test se asigna por fechas a su partición (l. 811-815).
- El test combinado es la unión de los tres, sin solapes.

**4. Paridad exacta con el motor y con producción.** La desviación es 0,0 en las
tres aserciones y en todos los partidos de test (procedencia). La x del script es el
término que serviría `adjust_model_probability` (`src/sqp/pipeline/probabilities.py:344`,
l. 382-384 y 400-402), recorte incluido.

**5. No hay copias del mismo partido en fechas distintas en las ligas que
aceptan.**

- Por `game_id`: 0 descartes en NBA, NHL y NFL.
- Comprobación adicional de esta revisión, solo con recuentos sobre la instantánea:
  parejas con el mismo local, visitante y marcador separadas 1–3 días. Hay **2 en la
  NBA y 0 en la NFL**. Dos filas entre 19.205 afectados no pueden mover el Δ.
- (NHL 59 y MLB 133, sin `game_id` común. En deportes de pocos goles y series
  consecutivas son coincidencias esperables, y además esas ligas no aceptan.)

**6. La firma no es la de una fuga.**

- La base de totales tiene log loss 0,6931 / 0,6931 / 0,6930 en las particiones
  NBA. Una fuga en la base lo bajaría.
- Una fuga en T exigiría que la ventana contuviera el propio total, y los puntos 1 y
  5 lo excluyen.
- El efecto es estable y tiene dosis:
  - las **14 temporadas** NBA del test son negativas (informe 5), de −0,0079 a
    −0,0314, y la burbuja 2019-20 da −0,0095;
  - por terciles de |x|, el Δ es −0,0012 / −0,0104 / −0,0378 (informe 4);
  - mejora **en los dos signos** de x: −0,0188 con x > 0 y −0,0123 con x < 0.
- En la NFL, 11 de 14 temporadas son negativas, y los terciles dan +0,0003 /
  −0,0045 / −0,0239.

**7. El brazo C controla lo que el pre-registro le pide: un desplazamiento
constante.**

- C = clip(p + a), con a estimado en el mismo entrenamiento (l. 867 y 882).
- En la NBA, C apenas mejora a la base (0,69281 frente a 0,69307). La base sí tiene
  un sesgo de nivel en totales (informe 1, media de p menos frecuencia de Over:
  −0,038 / −0,029 / −0,018). Pero ese sesgo **cambia de época en época**, y el a
  estimado en el pasado (−0,004 / +0,010 / +0,014) no lo sigue.
- La estimación conjunta base + a + c·x (informe 2) deja c **intacto**:
  0,0160 / 0,0158 / 0,0156, frente a 0,0157 / 0,0155 / 0,0154 sin intercepto. En la
  NFL, 0,0146 / 0,0139 / 0,0143.
- La ganancia, por tanto, no es nivel constante.
- Lo que C no puede separar, y no se le pidió, es la recencia del **nivel de la
  liga** frente a la del **entorno de cada emparejamiento**. Las dos son la
  «recencia» que la sección 3 declaró como única aportación posible del ajuste 4. Que
  el Δ sea negativo también con x < 0, y en temporadas sin deriva al alza, indica que
  hay discriminación por emparejamiento y no solo arrastre del nivel.

**8. Por qué es tan grande, y por qué solo en totales.** El tamaño queda explicado
cuantitativamente, sin necesidad de ninguna fuga.

- **Por construcción, la base de totales no tiene información.** Con L_i = ⌊μ⌋ +
  0,5 y `total_sigma` 22, la P(Over) de la base NBA queda en [0,491; 0,509], y su log
  loss es ≈ ln 2 en cualquier caso, sea μ buena o mala. La celda pregunta: **¿predice
  la media de 10 partidos de qué lado de la μ del propio modelo cae el total?** Si μ
  fuera la media condicional verdadera, la respuesta sería no. Cualquier error de μ
  que la ventana vea se convierte íntegro en ganancia. En h2h no pasa: la base ya
  discrimina, y el Elo es en sí un estimador de fuerza ponderado por recencia.
- **μ es un estimador de memoria larga.**
  - `TeamScoringRates` (`src/sqp/models/team_scoring.py:64-101`) acumula
    puntos a favor y en contra, regresados con 6 partidos ficticios a la media de la
    liga.
  - El decaimiento solo existe en la NBA (180 días naturales,
    `src/sqp/sports/registry.py:92`, elegido por precedente y no por minimizar:
    l. 87-89) y en la WNBA (60).
  - **En la NFL y la NHL, μ es la media acumulada desde 2002**: el comentario de
    `registry.py:90-91` dice que la NHL «NO se cambió». En la MLB, los cuatro años del
    store limitan el arrastre.
  - El informe 8 lo cuantifica en la NBA: quitar el decaimiento empeora el log loss de
    la base en **+0,20** en la misma L_i. μ es muy sensible a cuánta memoria tiene, y
    180 días no es necesariamente el óptimo.
- **Comprobación independiente** (exploratoria, hecha por esta revisión **después**
  de ver el resultado; no pre-registrada y sin valor de decisión). Sobre la
  instantánea, con `TeamScoringRates` de producción y su estado al cierre del día
  anterior, frente a la media de los 10 partidos previos de cada equipo, en los tests
  combinados:

  | Liga | RMSE de μ | RMSE de la ventana | RMS(ventana − μ) | Pendiente de (total − μ) sobre (ventana − μ) | Δ previsto ≈ −2(φ(0)·b·RMS/σ)² | Δ observado (adj4) |
  |---|---:|---:|---:|---:|---:|---:|
  | NBA | 19,35 | **18,76** | 6,02 pts | 0,79 | ≈ −0,019 | −0,0164 |
  | NFL | 14,08 | **13,86** | 4,37 pts | 0,60 | ≈ −0,011 | −0,0094 |
  | NHL | 2,30 | 2,31 | 0,68 goles | 0,33 | ≈ −0,003 | −0,0020 |

  - En la NBA y la NFL, la media ingenua de 10 partidos **predice el total mejor que
    μ**.
  - El 79 % y el 60 % de la desviación de la ventana respecto a μ se trasladan al
    total. Eso equivale, cerca de p = 0,5, a ≈ 1,6 y 1,7 pp por punto, del orden de
    los c estimados (1,54 y 1,45 pp/punto).
  - La aproximación gaussiana reproduce el orden de magnitud de los tres Δ
    observados, incluido que la NHL quede justo en el margen.
  - Es la estructura del error de μ lo que produce la ganancia, no una fuga.
- **Por qué NBA > NFL > NHL > MLB.** Depende de cuánto varía el entorno de anotación
  de cada emparejamiento frente al ruido de un partido:
  - en el baloncesto, el ritmo y la eficiencia de cada equipo cambian mucho y un
    partido es relativamente poco ruidoso: RMS de 6 puntos frente a σ ≈ 19;
  - en el hockey, el ruido de Poisson domina (0,68 frente a 2,3 goles);
  - en la MLB, además, los totales dependen del abridor y del parque, que la base ya
    incorpora, y el store solo tiene cuatro años.
- **El 4 y el 10 son la misma señal.** Con los c de la partición C sin reestimar, el
  modelo con los dos términos a la vez da Δ = **−0,0002** en la NBA, frente a −0,0163
  y −0,0122 por separado (informe 6). Cada uno corrige casi todo el error, y sumarlos
  lo corrige dos veces. En la NFL, −0,0039 frente a −0,0093 y −0,0065.

**Dictamen:** el resultado es **válido** como medición de lo pre-registrado:

- procedencia verificada;
- paridades exactas;
- sin fuga temporal ni del objetivo;
- control de intercepto operativo;
- Holm y criterios aplicados como estaban escritos.

No hay ningún defecto que active la regla E10. **Lo que mide es otra cosa que lo que
serviría producción**, y eso decide la sección siguiente.

## Lo que el resultado no autoriza: la línea del mercado (informe 7)

La sección 7.3 declaró la limitación: en la batería, el término mide «ventana de
10 frente a la μ del modelo»; en producción, mediría «ventana de 10 frente a la
línea del **mercado**». `totals_tendency_p_adjustment` usa el `point` de la cuota
(`rest_form.py:1108-1134`), y el run diario lo toma de `_pick_main_lines`
(`src/sqp/pipeline/daily.py:824`). El informe 7 evalúa los c de la última partición
con la línea capturada del consenso:

| Liga | n (totales) | Δ adj4 | Δ adj10 |
|---|---:|---:|---:|
| NBA | 237 | **+0,1071** | **+0,0663** |
| NFL | 33 | **+0,0516** | **+0,0493** |
| NHL | 238 | +0,0014 | +0,0046 |
| MLB | 1.721 | +0,0092 | +0,0049 |

**Los ocho valores son positivos: con la línea del mercado, los términos 4 y 10
empeoran el log loss en las cuatro ligas.**

- Las muestras son pequeñas: un solo tramo, de marzo a junio de 2026, en la NBA y la
  NHL; las tres primeras jornadas de 2026 en la NFL, fuera de todo test pero con el c
  de C entrenado hasta 2022. Además, en la MLB faltan las 481 parejas ambiguas.
- Pero el signo es unánime, y encaja con el mecanismo del punto 8. El término corrige
  el arrastre de μ **cuando la línea es μ**. La línea del mercado ya incorpora la
  recencia, así que `(media − línea)·c` deja de medir el error de μ y empuja la
  probabilidad lejos de una línea que ya es la buena.
- La magnitud de la NBA (+0,107) exige desplazamientos típicos de P(Over) del orden
  de 20 pp. Eso implica distancias grandes entre la media de 10 partidos y la línea
  del mercado en ese tramo, que incluye los playoffs. **No se ha comprobado** con los
  datos de cuotas: es una conjetura sobre el tamaño, no sobre el signo.
- La sección 15.7 exige documentar esto **antes** de activar. Queda documentado aquí.

El h2h y los spreads del informe 7 no contradicen nada, pero tampoco aportan: no hay
ninguna celda h2h aceptada.

## Informes secundarios

1. **Sesgo de la base** (media de p menos frecuencia).
   - Totales: NBA −0,038 / −0,029 / −0,018, NFL −0,046 / −0,033 / +0,010, NHL
     +0,044 / −0,031 / −0,044, MLB +0,012 / −0,000. Es la huella del arrastre de μ.
   - h2h: NBA −0,029 / −0,007 / −0,001, NHL −0,016 / −0,006 / −0,008. El −1 pp de
     la NHL es el residuo del tilt ya documentado.
2. **c con intercepto controlado.** En los totales aceptados, c no cambia (punto 7).
   En el h2h NBA, adj2 queda en ≈ 0 (−0,004 / +0,001 / −0,003) y adj8 baja de
   ≈ 0,05 a 0,006 / 0,007 / 0,013. Sin intercepto, el 8 recogía sobre todo la
   ventaja de campo, como anticipaba la sección 8. Y aun así no acepta.
3. **Perfil de entrenamiento.** Es monótono a los dos lados del mínimo en todas las
   celdas que aceptan. El mínimo de la rejilla está junto al c estimado: 0,0160 en
   adj4 NBA y 0,0147 en adj4 NFL.
4. **Dosis y signo:** ver el punto 6 del dictamen. En la NHL, adj4 da −0,0003 /
   −0,0008 / −0,0051 por terciles: hay dosis, pero el efecto es pequeño.
5. **Por temporada.**
   - adj4 NBA: 14 de 14 temporadas negativas. adj10 NBA: 14 de 14.
   - adj4 NFL: 11 de 14 (positivas 2012, 2017 y 2021). adj10 NFL: 11 de 14.
   - adj4 NHL: 9 de 12.
   - Marcas: la burbuja 2019-20 da −0,0095 y el calendario 2020-21 da −0,0083 en
     adj4 NBA. No son atípicas.
6. **Colinealidad de los aceptados** (solo describe): ver el punto 8. El modelo
   conjunto del 4 y el 10 **destruye** la ganancia en la NBA (−0,0002) y la reduce a
   menos de la mitad en la NFL (−0,0039).
7. **Línea capturada:** sección anterior.
   - Emparejados: NBA 239, NHL 258, NFL 33, MLB 1.790.
   - Los 483 emparejamientos ambiguos del log (2 NHL y 481 MLB) se **omiten** por
     diseño de `roi_engine`: emparejar por orden de id fabricaría una etiqueta. Solo
     reducen el n de este informe y no tocan ninguna celda.
   - Como en el precedente del tilt, el informe da solo Δ y **no** el log loss del
     no-vig del consenso. La referencia frente al mercado sigue sin medirse.
8. **Ajuste 4 frente al adaptador** (solo NBA; definición de la Enmienda 2(f)).
   - Quitar `scoring_half_life_days` (180 → 0) empeora la base en +0,2005 en todo el
     test y en +0,2015 en los afectados del 4, en la misma L_i.
   - Lo que el 4 añade (−0,0164) es la recencia que el decaimiento de 180 días todavía
     no captura.
   - No dice qué valor del adaptador la capturaría; eso exige su propia medición.
9. **Transferencia sin reajustar** (c de la partición C de NBA y NFL). Δ en los
   afectados:

   | Liga | n eval. | adj2 | adj3 | adj4 | adj8 | adj9 | adj10 |
   |---|---:|---:|---:|---:|---:|---:|---:|
   | WNBA (2025-26) | 677 | −0,0001 | −0,0017 | −0,0070 | −0,0022 | −0,0034 | −0,0056 |
   | NCAAB | 6.240 | −0,0005 | −0,0034 (n 130) | −0,0100 | −0,0106 | −0,0106 | −0,0090 |
   | WNCAAB | 5.970 | −0,0009 | −0,0070 (n 147) | −0,0151 | −0,0133 | −0,0189 | −0,0128 |
   | NCAAF | 3.151 | −0,0108 | +0,0025 (n 168) | −0,0014 | −0,0072 | −0,0193 | −0,0007 |

   - En las universitarias, los términos de calidad (8 y 9, y el 2 en NCAAF) mejoran
     **también el h2h**, al contrario que en las profesionales. Es lo esperable en
     ligas con una sola temporada en el store y un Elo joven, que la forma reciente
     supera.
   - Es una observación secundaria, sobre todo el histórico tras el warmup y sin
     particiones. No decide nada. Si se quiere, se mide con un pre-registro propio y
     con la temporada 2026-27.
   - **Filtro de la Enmienda 3(c) en las secundarias.** Descartó **31 filas en NCAAB y
     95 en WNCAAB**, y 0 en WNBA y NCAAF. Comprobado con recuentos sobre la
     instantánea:
     - son 31 y 95 `game_id` que aparecen dos veces **el mismo día**, siempre con el
       mismo marcador del local;
     - en 13 y 47 de ellos, el nombre del local difiere entre las dos copias (alias o
       sede neutral invertida);
     - por empate de fecha, la regla conserva la primera fila en el orden estable del
       store, como fija la Enmienda 3(c).
   - Como comparten fecha, ninguna copia entraba en las features de la otra (`d < rd`).
     Sin el filtro, el partido habría contado dos veces en las ventanas y en el estado
     de los partidos posteriores.
   - La Enmienda 3(c) aplica la regla a todas las ligas, con recuento y sin aserción
     en las secundarias. Por eso no es una desviación, pero se declara: el universo de
     NCAAB y WNCAAB es de 6.300 y 6.030 filas, no de 6.331 y 6.125. El fútbol agrupado
     está retirado (Enmienda 2(a)).
10. **Cobertura** (test combinado). Afectados del ajuste 4: NBA 19.205 de 19.332,
    NHL 16.518 de 16.950, NFL 4.564 de 4.604, MLB 4.776 de 4.845. Valores `None`
    por falta de historia: 64 / 23 / 15 / 2. Partidos neutrales: 270 / 257 / 88 / 0.
    Exhibiciones: no disponibles en `ResultsStore` (Enmienda 2(g)).

## Qué significa y qué no

- **Significa** que la μ de totales del modelo base arrastra información vieja:
  - en la NFL y la NHL, porque es una media acumulada desde 2002;
  - en la NBA, porque 180 días naturales siguen mezclando la temporada anterior.
  
  Una media de los últimos 10 partidos predice de qué lado de μ cae el total con una
  ganancia de log loss de 0,016 (NBA) y 0,009 (NFL), estable en particiones y
  temporadas. Es un hallazgo sobre el **adaptador de totales**, y es la hipótesis de
  recencia que la sección 3 ya señalaba («si mejora por eso, el sitio correcto es el
  adaptador»).
- **No significa** que el término aditivo, tal como está programado, mejore la
  probabilidad servida. El informe 7 dice lo contrario en las cuatro ligas, con
  muestras pequeñas pero signo unánime.
- **No significa** que la calidad reciente, el cara a cara o la forma por rol
  importen poco en el juego. Significa que **estas formas aditivas no añaden nada al
  Elo** en las cuatro ligas profesionales (sección 3).
- **No es una afirmación de ventaja ni de rentabilidad.** La batería mide solo el
  log loss de la probabilidad estimada frente al desenlace, en una línea fijada por el
  propio modelo. No mide la probabilidad implícita, el edge, el hit rate observado,
  el ROI esperado ni el ROI realizado. Corregir la μ de totales acercaría el modelo a
  una línea de mercado que ya incorpora esa recencia, y la medición del 2026-09-07
  (modelo *encompassed* por el consenso) sigue en pie. Un modelo menos desfasado no
  es un modelo con ventaja.

## Limitaciones

1. **Semántica de la línea** (sección 7.3). Es la limitación decisiva y el informe 7
   la confirma.
2. **Exposición previa de la muestra** (sección 4 y Enmienda 1(d)). Las correlaciones
   brutas del 2026-09-01 incluían `avg_total_combined` y `over_rate_combined`. Con
   p = 5·10⁻³⁷, la exposición no explica el resultado, pero un ACEPTA sobre una
   muestra vista es una evidencia algo más débil que sobre una virgen.
3. **El informe 7 tiene poca potencia y una cobertura sesgada**: un solo tramo de
   temporada por liga, y 481 parejas MLB omitidas por ambigüedad (≈ 21 % de las
   2.271 parejas que podían emparejarse: 481 omitidas más 1.790 emparejadas). No da el log loss del no-vig.
4. **La comprobación independiente del punto 8 es posterior al resultado.** Explica la
   magnitud y no decide nada.
5. **El JSON no guarda el log loss de entrenamiento en el c estimado**, que la sección
   15.3 usa para elegir entre el 4 y el 10. La rejilla del informe 3 lo aproxima:
   - en la partición C, el mínimo de la rejilla es 0,67798 (adj4) frente a 0,68159
     (adj10) en la NBA, y 0,68601 frente a 0,68747 en la NFL;
   - la diferencia es mucho mayor que la resolución de la rejilla, así que el orden es
     fiable: en las dos ligas, **el 4**.
6. **El brazo C controla un nivel constante, no un nivel que cambia con el tiempo.**
   Lo compensan el informe 2, la dosis y la mejora con x < 0, pero la parte de la
   ganancia que es deriva del nivel de la liga no está aislada.
7. **Los resultados y los JSON viven en la instantánea, fuera del repositorio**, como
   en los precedentes. La procedencia los fija por hash.

## Qué se deriva

**Según las reglas pre-registradas:** adj4 y adj10 en NBA y NFL **ACEPTAN**; las 20
celdas restantes **RECHAZAN**. Reabrir una celda rechazada exige otra forma funcional
u otra ventana, pre-registrada y con datos nuevos (sección 16). Nada de esto toca
producción: todos los coeficientes siguen en 0 (`configs/default.yaml`).

**Lo que haría falta para activar una celda aceptada** (sección 15, Enmienda 1 y
decisiones del 2026-09-27), en orden y sin saltarse pasos:

1. **Mecanismo de coeficientes por liga.** Hoy no existe: un coeficiente distinto de
   0 actúa en todas las ligas, incluido el tenis. Es un cambio de contrato de
   configuración, de la clase de escalado de `MODEL_ROUTING.md`, con tests que fijen
   el 0 en el resto de ligas y con revisión independiente. **Sin él, no se activa
   nada.**
2. **Valor:** el c de la partición C (adj4: 0,01540 en la NBA y 0,01451 en la NFL),
   con la ventana n = 10 de la configuración. No vale ni el c conjunto ni una
   reestimación.
3. **Un término por canal y liga.** Canal «anotación»: según la rejilla de
   entrenamiento, **el 4** en la NBA y en la NFL. **Nunca el 4 y el 10 a la vez**
   (informe 6). El 7 sigue en 0 siempre (identidad 7 ≡ 4).
4. **Decidir entre el término y el adaptador** (sección 15.4, **decisión del
   operador**). La evidencia de este resultado apunta al adaptador: la ganancia es
   error de μ, y el informe 8 muestra que la memoria de `TeamScoringRates` mueve el
   log loss de la base en 0,20. Ajustar `scoring_half_life_days` en la NFL y la NHL
   (hoy 0) o en la NBA (180) exige su propio pre-registro.
5. **Informe 7:** contradice en las cuatro ligas. Queda documentado (sección 15.7).
6. **Recalibrar en staging** (`controlled-recalibration`) los calibradores de los
   mercados de totales afectados, con promoción humana.
7. **Paridad entre entrenamiento y servicio:** un test con una ventana conocida que
   pruebe que el run diario tiene los resultados de ayer (`SETTLE_ALL` →
   `RUN_DIARIO_ALL`).
8. **Interacciones con los tests en curso.**
   - **«El modelo manda»** (≥ 3.402 eventos, ≈ 24/11) evalúa `p_cal`, que hereda la
     capa. Por decisión del 2026-09-27, cualquier activación espera a su ejecución o
     lleva antes un addendum de cambio de régimen.
   - **Gate K = 52:** usa `model_probability`, el modelo puro, así que la capa no
     cambia ninguna `d` ni K. Solo haría falta una nota informativa con la fecha.
     Ajustar el adaptador, en cambio, **sí** cambiaría las `d` de los cortes de
     totales y exigiría un addendum como el del tilt.

**Recomendación de esta revisión (no es una activación):**

- **No activar `totals_tendency_coef` ni `over_under_rate_coef`** en ninguna liga,
  aunque se construya el mecanismo por liga. La celda acepta en la semántica que se
  midió, y el informe 7 indica que, en la semántica de producción, el término empeora
  la probabilidad. Activarlo sería servir una corrección de μ contra una línea que no
  es μ.
- **Abrir, si el operador lo decide, un pre-registro de recencia de la anotación en
  el adaptador:**
  - qué medir: `scoring_half_life_days` en NFL y NHL, y una revisión del 180 de la
    NBA, o una ventana de recencia dentro de `TeamScoringRates`;
  - criterio: evaluado **contra la línea capturada del mercado** y contra el
    no-vig, no solo en L_i;
  - interacciones: el gate y «el modelo manda»;
  - exposición: declarar este resultado y el punto 8 como exposición previa.
  
  Es la línea de mejora que este resultado abre. Que un cambio en la μ deje el modelo
  más cerca del mercado no implica ninguna ventaja, y no se presentaría como tal.

---

Relacionado: [[2026-09-27-preregistro-bateria-ajustes]], [[2026-09-30-resultado-tilt-nhl]],
[[2026-09-29-resultado-descanso-nhl]], [[2026-09-26-resultado-descanso-basket]],
[[2026-09-26-resultado-clima-mlb]], [[2026-09-25-repreregistro-gate-k52]],
[[2026-08-26-preregistro-el-modelo-manda]].

FABLE-REVIEW: 2026-10-09 | veredicto: APTO CON CONDICIONES (resultado válido: procedencia y hashes verificados, paridades 0,0, sin fuga temporal ni del objetivo, control de intercepto operativo; 4 ACEPTA —adj4/adj10 × NBA/NFL— explicados por el arrastre de la μ de TeamScoringRates; NO activables tal como están programados: el informe 7 empeora en las 4 ligas con la línea del mercado; la vía es un pre-registro del adaptador, por decisión del operador) | rutas: docs/research/2026-10-09-resultado-bateria-ajustes.md
