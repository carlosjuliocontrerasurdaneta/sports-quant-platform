# Pre-registro — «Clima y Parque»: el viento según la orientación del estadio en los totales MLB

**Fecha:** 2026-09-26. Código de referencia: `main` en `5d4528f`. Escrito
**después** del rechazo del clima con la forma funcional de producción
(`2026-09-26-preregistro-clima-mlb.md`, enmiendas E1–E13;
`2026-09-26-resultado-clima-mlb.md`: 0 de 5 criterios, y lo superó el control de
intercepto) y **antes** de unir la dirección del viento con ninguna carrera.

Lo consultado para escribir este documento:

- los dos documentos anteriores, `scripts/research/fetch_weather_mlb.py`,
  `scripts/research/measure_weather_mlb.py`, `src/sqp/features/weather.py` y el
  factor parque del adaptador MLB (`src/sqp/sports/adapters.py`,
  `configs/leagues/ratings.yaml`: `park_bound 0.10`);
- la tabla de rumbos home → center field (sección 4), investigada por Sonnet;
- **solo clima**: velocidad y dirección del viento pronosticadas a 24 h
  (`gfs_seamless`) para los partidos de 2024–2026 del universo (sección 8). Se
  descargaron al scratchpad de la sesión y no a `data/`. **No** se leyó ningún
  marcador para calcularlas: del histórico solo se usaron los `game_id`.

Orden del operador: «Clima y Parque», es decir, el viento según la orientación
del estadio (a favor, hacia el jardín central, frente a en contra).

---

## 1. La decisión principal: ¿se puede probar otra vez sobre 2024–2026?

**No.** La muestra 2024–2026 no se usa como prueba confirmatoria. El test
confirmatorio es la **temporada regular 2027**, que es la primera muestra que
nadie ha mirado. Hasta entonces, 2024–2026 solo sirve para **estimar** el
coeficiente (sección 6) y para los informes sin marcadores de este documento.

Motivos, en orden de peso:

1. **Hay una decisión registrada.** El resultado del 2026-09-26 dejó escrito
   que reabrir exige una forma distinta «pre-registrada **sobre datos nuevos**».
   Probar sobre 2024–2026 contradiría una decisión registrada. Eso es clase de
   escalado según `CLAUDE.md` y exigiría una orden expresa del operador.
2. **La elección de la forma ya está contaminada por los datos.** Esta forma se
   propone *después* de ver el rechazo y sus secundarios sobre la misma muestra.
   Entre ellos está el «viento centrado por estadio» (Δ −0,0005 en afectados,
   coeficiente con cambio de signo), que ya es una mirada al viento por estadio.
   Una corrección de multiplicidad no arregla el jardín de caminos que se
   bifurcan: repartir α entre dos tests supone que los dos estaban
   pre-especificados antes de ver ninguno, y aquí el segundo nace del primero.
3. **La regla de decisión no es un p-valor.** Los criterios del proyecto son un
   margen de log loss (−0,002) más condiciones de signo, calibración y control.
   Bonferroni y Holm reparten un α, y aquí no hay α que repartir. Adaptarlos
   exigiría un margen «corregido» (por ejemplo, más exigente en el subconjunto
   afectado), y ese número no se puede derivar de nada del proyecto: sería un
   umbral inventado.
4. **Las dos variables no son independientes.** Sobre el universo de la sección
   4, la componente del viento a lo largo del eje se correlaciona un 0,33 con la
   velocidad escalar y un 0,32 con `max(0, v − 20)`, la variable rechazada
   (cálculo solo con clima, sección 8). La nueva prueba no es ajena a la
   anterior: comparte datos y parte de la señal.

**Multiplicidad frente al primer test.** Con datos de test disjuntos no hace
falta repartir nada con el primero. Ese test ya se gastó sobre 2024–2026 y
rechazó, así que no aportó ninguna falsa aceptación. La probabilidad de activar
por azar depende ahora solo de esta prueba y de su muestra nueva. El riesgo que
queda es la **secuencia**: probar formas hasta que una pase. Se cierra con esta
regla:

> **Una forma de clima por temporada de test.** 2027 queda reservada para esta
> forma. Cualquier otra forma de clima (temperatura, humedad, lluvia con otra
> función, interacción con el parque...) necesita su propia muestra no vista:
> 2028 o posterior. Si el operador quisiera probar más de una forma en 2027,
> tendría que decidirlo **antes** del primer partido de 2027 y fijar entonces
> una corrección explícita. **Decisión del operador**, que hoy no se toma.

**Alternativa descartada: la puerta de significación.** Exigir que el extremo
superior del IC95 bootstrap sea < 0, o un α unilateral de 0,025 (Bonferroni con
α de familia 0,05 entre las dos formas), endurecería la prueba. Ninguna de las
dos está fijada por el proyecto: en E8 el IC se informa pero no decide.
**Decisión del operador**, que no se activa por defecto.

---

## 2. La pregunta

Sumar a `P(Over)` del modelo MLB una corrección proporcional a la componente
del viento pronosticado a lo largo del eje home → center field, **medida como
desviación respecto al viento habitual de ese estadio**, ¿mejora el log loss de
los totales en 2027, por encima de un simple intercepto?

**Se mide esta forma y ninguna otra.** Temperatura, humedad, lluvia, viento
cruzado y umbrales quedan fuera (sección 3).

---

## 3. Forma funcional exacta

### 3.1 Componente del viento hacia el jardín central

Convención de Open-Meteo: `wind_direction_10m` da en grados de brújula (0° =
Norte, en sentido horario) **de dónde viene** el viento. El rumbo del estadio
`b` es la dirección home → center field en la misma convención.

    θ_hacia = θ_desde + 180°
    W = v · cos(θ_hacia − b) = −v · cos(θ_desde − b)        [km/h]

`W > 0` significa que el viento sopla **hacia fuera** (del plato hacia el
jardín central) y `W < 0` que sopla **hacia dentro**. Comprobación: en Wrigley
(`b` = 30°), un viento **desde** 210° va hacia 30°, y `W = −v·cos 180° = +v`
(hacia fuera). Un viento desde 30° da `W = −v` (hacia dentro).

- `v` = `wind_speed_10m_previous_day1` y `θ_desde` =
  `wind_direction_10m_previous_day1`, con `models=gfs_seamless`,
  `wind_speed_unit=kmh`, `timezone=UTC` y la hora **truncada** del inicio
  (E1).
- `b` = columna «rumbo» de la tabla de la sección 4, congelada en este
  documento.

### 3.2 Desviación respecto al estadio

    W_dev = W − m_estadio,   m_estadio = media de W en los partidos de ENTRENAMIENTO del universo en ese venue_id

Motivo, sin marcadores: la media de `W` por estadio varía mucho. Oracle Park da
+20,0 km/h, Angel Stadium +11,9 y Progressive Field −3,7, y la desviación
típica entre medias de estadio es de 5,3 km/h (sección 8). El modelo ya tiene
un factor parque acotado (`park_bound 0.10`, estimado con las carreras en casa
frente a fuera del equipo local). Ese factor absorbe el entorno de carreras
**habitual** de cada estadio, viento medio incluido. Usar `W` sin centrar
contaría dos veces el viento habitual. `W_dev` mide solo el viento **anómalo**
del día, que el factor parque no puede conocer.

`m_estadio` se congela con el coeficiente (sección 6) y en 2027 no se
actualiza. Un venue sin partidos de entrenamiento en el universo no tiene
`m_estadio` y se excluye del test.

### 3.3 Corrección de probabilidad

    Δp(Over) = β · W_dev,     Δp(Under) = −Δp(Over)
    P'(Over) = clip(P(Over) + Δp, 0,01, 0,99)

Es la misma estructura aditiva y el mismo recorte que
`weather.adjust_model_probability`.

- **Sin umbral.** Es lineal en `W_dev`. Un umbral o una zona muerta sería un
  parámetro libre sin origen en el proyecto. El 20 km/h de producción es de la
  velocidad escalar, que es la forma rechazada, y no se puede trasladar a una
  componente con signo.
- **Lluvia fuera.** Ya se probó y se rechazó (coeficiente B de signo positivo).
  Meterla otra vez añadiría un segundo parámetro y volvería a probar una
  variable rechazada dentro de la misma familia.
- **Viento cruzado fuera.** No tiene signo a priori.
- **Un solo coeficiente, con signo físico a priori:** `β > 0`. El viento hacia
  fuera prolonga el vuelo de la pelota bateada y el viento hacia dentro lo
  acorta. A diferencia del criterio 4 de E7, que era solo una convención de
  `weather.py`, aquí el signo es un argumento físico previo a los datos.

---

## 4. Universo y rumbos

### 4.1 Tabla de rumbos congelada (estadios `Open` con dos fuentes concordantes)

Fuente: `ballpark_bearings.csv` de la sesión, investigado por Sonnet.
«bp» = ballparks.com, «sh» = theshadium.com y «OSM» = geometría propia sobre
OpenStreetMap (del centro del plato al vértice más lejano del polígono). El
rumbo es la media de las dos fuentes concordantes.

**Convención de ballparks.com.** La página dice 0° = Este, pero se trata como
brújula (0° = Norte, sentido horario). La geometría OSM independiente coincide
con bp como brújula (Yankee 77 frente a 75; Progressive 358 frente a 0). Con la
convención 0° = Este antihoraria, el 75 de Yankee equivaldría a 15° de brújula
y no cuadraría con la geometría.

| venue_id | Estadio | Rumbo (°) | Fuentes concordantes | Discrep. | Tercera fuente | Partidos 2024–26 |
|---|---|---|---|---|---|---|
| 1 | Angel Stadium | 47,5 | bp 45 · sh 50 | 5 | — | 243 |
| 2 | Oriole Park at Camden Yards | 30,0 | bp 30 · sh 30 | 0 | — | 242 |
| 3 | Fenway Park | 51,5 | OSM 51 · sh 52 | 1 | bp 45 | 238 |
| 4 | Rate Field (antes Guaranteed Rate) | 127,5 | bp 135 · sh 120 | 15 | **OSM 22,4 (105°)** | 236 |
| 5 | Progressive Field | 359,0 | OSM 358 · bp 0 | 2 | sh 356 | 242 |
| 7 | Kauffman Stadium | 46,5 | bp 45 · sh 48 | 3 | **OSM 137,5 (91°)** | 239 |
| 17 | Wrigley Field | 30,0 | bp 30 · sh 30 | 0 | — | 241 |
| 19 | Coors Field | 0,0 | bp 0 · sh 0 | 0 | OSM 283,4 (77°) | 241 |
| 22 | Dodger Stadium (UNIQLO Field) | 27,5 | bp 30 · sh 25 | 5 | — | 242 |
| 31 | PNC Park | 120,0 | bp 120 · sh 120 | 0 | OSM 119,3 | 243 |
| 2394 | Comerica Park | 147,5 | bp 150 · sh 145 | 5 | **OSM 322,9 (175°)** | 239 |
| 2395 | Oracle Park | 88,5 | bp 90 · sh 87 | 3 | OSM 120,7 (32°) | 240 |
| 2602 | Great American Ball Park | 121,7 | OSM 123,4 (baja confianza) · bp 120 | 3,4 | sh 115 | 240 |
| 2680 | Petco Park | 0,0 | bp 0 · sh 0 | 0 | OSM 8,5 | 239 |
| 2681 | Citizens Bank Park | 16,5 | bp 15 · sh 18 | 3 | **OSM 178,5 (162°)** | 239 |
| 2889 | Busch Stadium | 60,0 | bp 60 · sh 60 | 0 | — | 241 |
| 3289 | Citi Field | 32,5 | bp 30 · sh 35 | 5 | — | 241 |
| 3309 | Nationals Park | 30,0 | bp 30 · sh 30 | 0 | OSM 34,1 | 240 |
| 3312 | Target Field | 90,0 | bp 90 · sh 90 | 0 | — | 236 |
| 3313 | Yankee Stadium | 76,0 | OSM 77 · bp 75 | 2 | sh 55 | 238 |

Los partidos cuentan el universo tras las exclusiones E3 y E13: 4.800 en total,
todos con velocidad y dirección pronosticadas.

Se excluyen por techo, aunque tengan rumbo concordante: American Family Field,
Chase Field, Daikin Park/Minute Maid, Rogers Centre y T-Mobile Park
(`Retractable`) y Tropicana Field (`Dome`). Es la regla de E12.

### 4.2 Tolerancia de concordancia y verificación de sentido

- **Tolerancia de concordancia: 15°.** Es la mayor discrepancia que ya se
  aceptó como concordante (Rate Field). Con `cos 7,5°` = 0,991 (media de dos
  fuentes a ±7,5°) la atenuación de `W` es < 1 %. Un error de 15° en el rumbo
  deja `W` con una correlación de 0,968 respecto a la de referencia (sección
  8). Queda como provisional: **decisión del operador**, que puede
  confirmarla o cambiarla antes de la congelación.
- **Verificación de sentido (obligatoria antes de la congelación).** Si el
  rumbo está girado más de 90°, cambia el **signo** de `W`, y el error que más
  importa en esta prueba es un signo al revés. En cuatro estadios una tercera
  fuente difiere más de 90° de la media concordante: Rate Field, Kauffman,
  Comerica y Citizens Bank (en negrita en la tabla). Los dos casos de ~180°
  apuntan a que el método OSM eligió el extremo equivocado del polígono, pero
  no basta con suponerlo. Cada uno se comprueba con una imagen de satélite
  (qué lado del campo ocupa el jardín central). Basta con acertar a ±90°, y se
  anota la fuente. Si no se puede comprobar antes de la congelación, ese
  estadio sale del universo.
- **Independencia de las fuentes (limitación).** En 16 de los 20 estadios la
  concordancia es solo bp frente a sh, con valores idénticos en 8 de ellos.
  Puede que theshadium copie a ballparks.com, y entonces la concordancia no
  probaría nada. La verificación geométrica independiente existe en Yankee,
  Progressive, Fenway, Great American (baja confianza), PNC, Nationals y Petco.
  Ampliarla a todos es deseable, pero no se exige: **decisión del operador**.

### 4.3 Estadios sin rumbo fiable

- **Se excluyen del universo de la prueba** en entrenamiento y en test, en
  lugar de recibir Δp = 0. Meterlos con Δp = 0 no mide nada y diluiría el
  criterio. En producción, si se activara, recibirían Δp = 0.
- **Pueden recuperarse antes de la congelación, y solo entonces**, los dos que
  importan en 2027:
  - **Truist Park** (DISCREPANTE: OSM 109,7 frente a sh 135, 25,3°);
  - **Sutter Health Park** (una sola fuente, sh 20°; los Athletics siguen allí
    en 2027).

  Entran si una fuente geométrica independiente concuerda dentro de la
  tolerancia con una de las existentes; se usa entonces la media del par
  concordante. Cada uno aporta unos 81 partidos por temporada.
- Oakland Coliseum, Steinbrenner Field, Las Vegas y las sedes especiales
  (Londres, Rickwood, Field of Dreams, Bristol, México, Seúl, Tokio) quedan
  fuera. No juegan en 2027 como sede habitual o no tienen fuente.
- El rumbo se asigna por `venue_id` del partido (calendario MLB), no por
  equipo. Así cubre cambios de nombre (Rate Field, UNIQLO Field) y de sede.

### 4.4 Exclusiones heredadas (E3 y E13, sin cambios)

- `roofType` distinto de `Open` o ausente;
- menos de 9 entradas completas, salvo las que terminan en la parte alta de la
  9.ª porque gana el local;
- partidos suspendidos y reanudados otro día;
- filas `Postponed` y `Cancelled` del calendario: el clima es el de la fecha en
  que el partido sí se jugó;
- universo = `game_id` del histórico (sin pretemporada ni exhibiciones).

A esto se añade: partidos en estadios sin rumbo congelado, o sin `m_estadio`.

---

## 5. Periodos, mercados y brazos

- **Mercado:** totales. `P(Over)` contra las líneas fijas **7,5 / 8,5 / 9,5**
  (`total_lines`), como en el primer test. Con medio punto no hay empujes.
- **Base:** walk-forward de `sqp.backtesting.engine` con la configuración MLB
  de producción **del commit de congelación** (`_league_meta("mlb")`), abridores
  enriquecidos con `StartersStore.attach` y `StarterFIPStore.attach` (E2), y
  todo el histórico desde 2023 como calentamiento.
- **Entrenamiento:** universo 2024-03-20 → último partido de la temporada
  regular 2026 presente en el histórico el día del ajuste.
- **Test:** temporada **regular** 2027 completa. Se excluye la postemporada,
  que es corta y tiene otra composición.
- **Tres brazos, estimados en el entrenamiento:**
  - **C (control de intercepto, E5):** `Δp = c_C`.
  - **T (tratamiento):** `Δp = c_T + β · W_dev`. El intercepto va dentro para
    que `β` no pueda ganar corrigiendo el sesgo de nivel del modelo, que fue lo
    que pasó en la partición A del primer test.
  - **P (forma de producción):** `Δp = β · W_dev`, con el `β` de T. Es lo único
    que se activaría. El intercepto no es un efecto del clima y no forma parte
    de esta propuesta.

---

## 6. Estimación y congelación

- Nelder-Mead sobre el log loss medio de las tres líneas, con el recorte
  incluido. Parte de (0, 0) en T y de (0) en C, con `xatol=1e-7`,
  `fatol=1e-10`, `maxiter=2000` y sin límites (E9).
- **Congelación:** antes del primer partido de temporada regular 2027 se
  commitean `β`, `c_T`, `c_C`, los `m_estadio`, la tabla de rumbos definitiva
  (tras la sección 4.2 y la 4.3) y el hash del CSV de clima de entrenamiento.
  Ese commit fija la prueba.
- El ajuste se ejecuta **una sola vez** y se commitea con cualquier resultado.
  Es el único momento, antes de 2027, en que viento y carreras se unen, y solo
  para estimar.
- **Rechazo temprano, nunca aceptación temprana:** si `β ≤ 0` en el
  entrenamiento, el criterio 3 falla y el veredicto es RECHAZA sin esperar a
  2027. La regla es asimétrica: el ajuste puede cerrar la prueba, pero no puede
  abrirla.
- Tras la congelación **no se cambia la forma**. Un cambio exige un
  pre-registro nuevo con test en 2028 o después (sección 1).

---

## 7. Criterios de aceptación (todos a la vez, sobre la temporada regular 2027)

1. **ll(T) − ll(C) ≤ −0,002** en todo el universo de test, con media por
   partido y línea. El margen es el de las decisiones del abridor (2026-06-12
   y 2026-06-16), que se aplicó a un parámetro que actuaba en **todos** los
   partidos evaluados. Aquí `Δp = β·W_dev ≠ 0` en casi todos los partidos del
   universo, así que el precedente se aplica tal cual. El argumento de E6
   (margen solo en los afectados) no es necesario: no hay partidos con Δp = 0
   por construcción que diluyan el efecto.
2. **ll(T) − ll(C) < 0 en cada mitad** del test, partido por la fecha mediana
   de los partidos del universo 2027. Es el análogo del criterio 2 de E7 (cada
   partición).
3. **β > 0** (sección 3.3), comprobado en la congelación.
4. **ll(P) < ll(base)** en el universo de test: la forma que se activaría no
   empeora el modelo por sí sola.
5. **ECE(P) ≤ ECE(base)** en el universo de test, con
   `expected_calibration_error` del proyecto por defecto y las tres líneas
   unidas.

Si falla cualquiera: **no se activa** y el resultado se commitea igual.

**Incertidumbre (E8, no decide):** bootstrap por bloques de fecha (se
remuestrean días completos), 10.000 réplicas, semilla 42, sobre
`ll(T) − ll(C)`. Se informa el IC95.

**Paridad (E4):** la base se reconstruye con el mismo orden que
`engine.walk_forward_backtest`. El script aborta si la probabilidad de cualquier
línea difiere de la del motor en más de 1e-12, o si los resultados no son
idénticos.

**Ejecución única y re-ejecución (E10):** una sola ejecución tras el último
partido de la temporada regular 2027, cuando el histórico y la Previous Runs
API lo cubran. Solo se repite si aparece un defecto de **código o datos**
demostrable sin mirar el resultado (paridad rota, filas mal unidas, descarga
incompleta, rumbo mal transcrito). En ese caso se documenta el defecto y se
commitean las dos salidas. Un resultado adverso no es motivo para repetir.

**Informes secundarios (no deciden):**

- el mismo Δp contra la **línea de totales capturada** (E11), sobre toda la
  temporada 2027. Es el secundario más relevante, porque las casas publican el
  pronóstico y con `market_shrink = 0,5` como mucho se transmite la mitad de lo
  medido;
- Δ por estadio y Δ en los partidos con `|W_dev|` por encima del p90 del
  entrenamiento (descriptivo);
- `W` sin centrar, para medir cuánto aporta el centrado.

**Informe previo sin marcadores** (antes de la congelación y otra vez antes de
la ejecución): cobertura, exclusiones por motivo, distribución de `W` y
`W_dev`, y partidos por estadio y temporada.

---

## 8. Potencia (solo clima, sin marcadores)

Descarga del 2026-09-26: `gfs_seamless`, `*_previous_day1`, hora truncada. Son
los 20 estadios de la tabla con las exclusiones E3 y E13: 4.800 partidos, 0 sin
pronóstico.

| Concepto | Valor |
|---|---|
| Partidos por temporada | 2024: 1.604 · 2025: 1.608 · 2026 (al 24/09): 1.588 |
| `W` (km/h): p5 / p25 / mediana / p75 / p95 | −14,0 / −5,4 / +3,4 / +11,2 / +21,6 |
| Media / DT / RMS de `W` | +3,1 / 11,0 / 11,4 |
| DT **dentro** de estadio (`W_dev`) | **9,6 km/h** |
| DT entre medias de estadio | 5,3 km/h |
| Media por estadio (extremos) | Oracle +20,0 · Angel +11,9 · Dodger +8,3 · … · Progressive −3,7 |
| Estadios casi sin variación (DT < 3 km/h) | Angel 2,6 · Dodger 2,3–2,9 |
| Fracción con `W > 0` | 0,58 |
| Correlación con la variable rechazada `max(0, v−20)` | 0,32 |
| Correlación de `W` con rumbo desplazado 5° / 15° | 0,996 / 0,968 |

**Derivación.** Cerca de p = 0,5, corregir una desviación real δ gana
≈ δ²/(2p(1−p)) ≈ 2δ² de log loss por línea. La varianza por partido de la
diferencia es ≈ Δp²/(p(1−p)) ≈ 4Δp². Es conservadora, porque supone las tres
líneas perfectamente correlacionadas. Con `rms(Δp) = r` y n partidos de test:

- **Techo que impone el margen, con cualquier n:** 2r² ≥ 0,002 ⇒
  **r ≥ 3,2 pp** ⇒ `β ≥ 0,032 / 9,6` ≈ **0,0033 por km/h**, es decir,
  **+3,3 pp de P(Over) por cada 10 km/h de viento anómalo hacia fuera**. Con
  un efecto verdadero de ese tamaño, la probabilidad de superar el margen es
  ≈ 50 %.
- **Potencia del 80 %:** 2r² − 2·0,84·r/√n ≥ 0,002.

| n de test | Origen | r necesario | β necesario (por 10 km/h) |
|---|---|---|---|
| ≈ 1.600 | 2027 (20 estadios) | 4,4 pp | 4,6 pp |
| ≈ 1.770 | 2027 + Truist + Sutter | 4,3 pp | 4,5 pp |
| ≈ 3.200 | 2027 + 2028 | 4,0 pp | 4,2 pp |
| ∞ | — | 3,2 pp | 3,3 pp |

**Lectura.** Lo que limita la prueba es el **margen**, no el ruido. Añadir 2028
apenas baja el efecto necesario (de 4,6 a 4,2 pp por 10 km/h) y retrasa la
decisión un año. La prueba solo puede aceptar si el viento anómalo mueve
`P(Over)` del orden de 3–5 pp por cada 10 km/h de componente. Sin mirar
resultados no hay forma de saber si un efecto así es plausible con viento de
rejilla GFS a 10 m, que no es el viento dentro del estadio: las gradas lo
apantallan y lo desvían. Tampoco se sabe cuánto de él ya está en la línea del
mercado. Se deja escrito para que un rechazo no sorprenda. El estimador de `β`
no limita: con 4.800 partidos de entrenamiento, su error típico es
≈ 0,5/(√4800·9,6) ≈ 0,0008 por km/h, una cuarta parte del efecto mínimo que
exige el margen.

Ampliar el test a 2027 + 2028 solo puede decidirse **antes** del primer partido
de 2027. **Decisión del operador**, y la recomendación es no hacerlo, por la
tabla anterior.

---

## 9. Qué haría falta para activarlo (solo si acepta; cambio aparte, con aprobación)

Producción no captura hoy la dirección del viento. `src/sqp/features/weather.py`:

- pide `temperature_2m,precipitation,wind_speed_10m`: falta
  `wind_direction_10m`;
- no pasa `models`: habría que fijar `gfs_seamless` (E1);
- para fechas pasadas usa el endpoint de **archivo**, que es clima observado.
  Da igual en producción, que pide el futuro, pero cualquier backtest que lo
  use tendría leakage;
- toma la hora más próxima a `dt.hour` y guarda la caché con coordenadas a 1
  decimal.

Cambios necesarios:

1. `wind_direction_10m` en la petición y `models=gfs_seamless`.
2. Una tabla de rumbos por `venue_id` en `configs/` con fuente y estado,
   copiada de la tabla congelada.
3. Coordenadas y `venue_id` **del partido** (calendario MLB), no del equipo:
   `configs/venues.yaml` fija a los Athletics en Sacramento en todas las
   temporadas.
4. Filtrar `Dome` **y** `Retractable` (E12).
5. Una función nueva junto a `weather_p_adjustment`, con un campo nuevo
   (`wind_out_coef_totals`) y los `m_estadio` congelados. Los coeficientes
   actuales siguen en 0.
6. Recalibrar en staging, porque los calibradores MLB se entrenaron sin clima.
7. Anotar el efecto sobre el test de `mlb|totals` del gate y sobre «el modelo
   manda».

**Captura en sombra durante 2027 (recomendada, no necesaria para el test).** El
test usa el archivo de la Previous Runs API, que no depende de producción. Pero
producción genera el pick entre ~4 h y varios días antes, con el endpoint de
pronóstico. Registrar en sombra, sin tocar probabilidades, `v`, `θ_desde` y el
instante de consulta de cada partido MLB de 2027 permitiría medir la diferencia
entre lo que producción vería y el pronóstico a 24 h del test. Es un cambio de
código: **decisión del operador**.

---

## 10. Calendario

| Cuándo | Qué |
|---|---|
| 2026-09-26 | Este pre-registro. |
| Antes del primer partido de 2027 | Verificación de sentido (4 estadios), intento de recuperar Truist y Sutter, decisiones del operador pendientes, scripts con test sintético, informe previo sin marcadores, ajuste único y **commit de congelación**. |
| Tras la temporada regular 2027 | Descarga, ejecución única y commit del resultado con cualquier veredicto. |

---

## 11. Decisiones del operador pendientes

1. Confirmar que el test confirmatorio es 2027 y no 2024–2026. Probar ahora
   contradiría la decisión registrada en el resultado del 2026-09-26.
2. Tolerancia de concordancia de rumbos: 15° provisional (sección 4.2).
3. Exigir o no verificación geométrica independiente en los 16 estadios que
   solo tienen bp frente a sh (sección 4.2).
4. Invertir o no en recuperar Truist Park y Sutter Health Park (sección 4.3).
5. Puerta de significación adicional (IC95 < 0 o α 0,025): no se activa por
   defecto (sección 1).
6. Probar más de una forma de clima en 2027 (hoy no), o ampliar el test a 2028
   (no recomendado). Las dos solo pueden decidirse antes de 2027.
7. Captura en sombra de la dirección del viento en producción durante 2027
   (sección 9).

**Decisiones del operador resueltas el 2026-09-26, antes de congelar:**
1. **Test confirmatorio: temporada regular 2027.** 2024–26 solo estima el coeficiente. Rige la regla de una sola forma de clima por temporada de test.
2. **Captura en sombra** de la dirección del viento en producción durante 2027: sí. Solo captura, sin tocar probabilidades.
3. **Verificación de rumbos antes de congelar la tabla:** los 4 estadios con discrepancia de más de 90° (Rate Field, Kauffman, Comerica, Citizens Bank) **y** los 16 que solo tienen ballparks.com frente a theshadium (posible copia).
4. **Sin puerta de significación extra:** decide solo el margen 0,002. El IC95 del bootstrap se informa pero no decide.
