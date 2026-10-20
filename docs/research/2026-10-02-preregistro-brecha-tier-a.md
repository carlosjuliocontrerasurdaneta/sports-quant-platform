# Pre-registro — ¿el tier A del Tipster acierta menos de lo que promete?

**Fecha:** 2026-10-02.
**Estado:** **APROBADO** (2026-10-02, §10). El commit que añade este fichero, marcado con el tag anotado `prereg-tier-a-t0`, fija H y T0 (§2.1). Diseño: Fable (rol de pre-registro de `.claude/automation/MODEL_ROUTING.md`).
**Escrito antes de mirar ningún resultado de la muestra del test.** Esa muestra todavía no existe: son picks que se generarán **después** del commit que añade este fichero (§2.1). Lo único consultado hoy es el código, la documentación, los precedentes y **agregados** del ledger y del stream graduado hasta el 2026-09-30 (§4.1), que ya estaban vistos y por eso quedan **fuera** de la muestra.

Precedentes de formato y de método: `2026-09-25-repreregistro-gate-k52.md` (multiplicidad, techo), `2026-08-26-preregistro-el-modelo-manda.md` (efecto mínimo anclado, fecha por recuento y no por calendario, addenda de régimen) y `2026-09-29-preregistro-tilt-nhl.md` (bootstrap por días, ejecución única, potencia antes de medir).

---

## 1. La pregunta

### 1.1 Qué es el tier A (verificado en el código)

`src/sqp/evaluation/tipster.py`, función `classify(ev, edge_pp, casas, prob, max_plausible_ev)`, en este orden:

1. `EV ≤ 0` o no finito → NO BET. `EV = prob · cuota − 1`, con `cuota = price_decimal` (la mediana del consenso guardada en la fila; `execution_price`, si existe, no clasifica).
2. `EV > max_plausible_ev` → NO BET. Para este test `max_plausible_ev` es el **literal 0,075**, congelado en este documento (§2.5). Hoy coincide con `risk.max_plausible_edge` de `configs/default.yaml:16`, pero el valor efectivo de `Settings` puede venir de otra fuente: la variable de entorno `MAX_PLAUSIBLE_EDGE` (`.env`) tiene prioridad sobre el yaml, y el default del código es 0,15 (`src/sqp/config.py:113` y `:462-463`). El test no lee ese valor; solo lo registra (§2.5).
3. `casas < 10` → C; `edge_pp < 0.02` → C.
4. **A** si `casas ≥ 20`, `edge_pp ≥ 0.03` y `prob ≥ 0.50` (`TIER_A`). Si no, B.

`prob` es la **probabilidad de decisión** (`sqp.evaluation.labels.decision_prob`: la calibrada, con fallback por fila a la estimada). `edge_pp = prob − implied_probability_novig`. El motivo que el Tipster muestra para A es «edge sólido con consenso profundo».

El tier **no se persiste**. Se reconstruye aplicando `tipster_table` a las filas guardadas, con la cuota y la probabilidad del momento de servir, que sí están en cada fila.

### 1.2 La observación que motiva el test (YA VISTA; no puede ser la muestra)

| universo (hasta generated_at 2026-09-30) | n win/loss tier A | acierto | prob. prometida media | brecha |
|---|---:|---:|---:|---:|
| ledger `data/bets/settled_*.csv`, colapsado con `_unique_settled_picks` | 386 | 47,7 % | 56,8 % | −9,1 pp |
| stream graduado `ServedStore.load_all_graded`, primera servida por pick (medido hoy, §4.1) | 641 | 51,2 % | 56,7 % | −5,6 pp |

Controles ya vistos: tier B en el ledger 42,2 % frente a 43,6 % prometido y en el graduado 43,0 % frente a 46,9 %. Tier C: 53,8/54,8 y 54,0/55,2.

Estas cifras salen de un corte elegido **a posteriori**, el que más llamaba la atención. Eso infla la brecha (maldición del ganador). Por eso sirven para generar la hipótesis, nunca para contrastarla.

### 1.3 Hipótesis

Sea, para cada pick `i` del tier A con resultado win/loss, `y_i ∈ {0,1}` (acierto) y `p_i` su probabilidad de decisión. Se define la **brecha** como

    D = E[y − p]        (acierto observado medio − probabilidad prometida media)

- **H₀:** `D ≥ 0`. El tier A acierta al menos lo que promete.
- **H₁:** `D < 0`. El tier A acierta menos de lo que promete.

El contraste es **unilateral**: la única dirección que cambia algo (§6) es «promete de más». La otra cola se informa, pero no actúa.

### 1.4 Qué significa y qué no

- **Es un test de calibración del tier A, no de rentabilidad.** Un acierto inferior a lo prometido no implica pérdidas, y un acierto igual a lo prometido no implica beneficio. Una favorita a 1,07 puede acertar el 90 % y perder dinero (`.claude/rules/betting-output-rules.md`). Probabilidad estimada, probabilidad implícita, edge, acierto observado, ROI esperado y ROI realizado se informan **por separado** (§5.4).
- **Relación con la regla de salida.** La regla de salida es el `prediction_gate`, que decide el stake por `liga|mercado` con un test de signo pareado contra el mercado (`2026-08-16-preregistro-regla-de-salida.md`, K = 52). El tier A **no** entra en el stake ni en el gate. Este test no puede abrir ni cerrar ningún corte del gate, y el gate no depende de él. Su relevancia es otra:
  1. **La etiqueta.** «A» le dice al operador «edge sólido». Si A promete de más de forma sistemática, la etiqueta comunica una probabilidad falsa.
  2. **El diagnóstico.** La `p` que A promete es la misma `decision_prob` con la que decide el pipeline. Una brecha específica de A, mayor que la de B (§5.2), apuntaría a una sobreconfianza **inducida por la selección**: filtrar por `edge_pp ≥ 0,03` y `prob ≥ 0,50` escoge los errores del modelo. Es coherente con la escalera de `min_edge` invertida (2026-08-25). Si se confirma, alimenta un pre-registro de calibración posterior. No autoriza nada por sí mismo.

---

## 2. Población

### 2.1 Ventana temporal

- **H** es el commit que **añade** este fichero. Justo después de crearlo se crea sobre él el **tag anotado `prereg-tier-a-t0`** (`git tag -a prereg-tier-a-t0 -m "..." H`). **T0** es el committer date de H, en UTC.
- **Resolución:** el script lee H con `git rev-parse prereg-tier-a-t0^{commit}` y T0 con `git log -1 --format=%cI H`. **Fallback**, solo si el tag no existe: `git log --diff-filter=A --format="%H %cI" -- docs/research/2026-10-02-preregistro-brecha-tier-a.md`. Si existen los dos y dan commits distintos, el script aborta y lo informa. El informe dice qué vía se usó.
- **Entra un pick solo si su PRIMERA servida es estrictamente posterior a T0**, donde «primera servida» es el `generated_at` mínimo de su clave (§2.3) sobre el stream servido **completo** (`data/calibration/served_*.csv`), no sobre el graduado. La deduplicación se hace sobre todo el stream y el filtro por T0 se aplica **después**. Así queda fuera tanto un pick servido por primera vez antes de T0 y re-servido después como uno cuyas servidas anteriores a T0 no llegaron a graduarse: en los dos casos su momento de decidir ya era conocido.
- **Orden de operaciones, único y vinculante** (lo repiten §2.3, §2.4 y §7):
  1. Cargar `served_*.csv` (solo `data_label == "real"` si la columna existe), excluir y contar las filas con identidad incompleta (§2.3), y quedarse con **una fila por clave: la de `generated_at` mínimo**.
  2. Filtrar la ventana (T0, T1] sobre el `generated_at` de **esa** fila.
  3. Aplicar los filtros de validez de §2.4 sobre **esa misma fila**. Si no los pasa, el pick queda excluido y se cuenta; **nunca** se salta a una servida posterior del mismo pick.
  4. Unir el resultado desde `graded_*.csv` por clave del pick (§2.3). Cualquier fila graduada de la clave sirve, porque todas las servidas de un pick comparten partido y resultado. Si las filas graduadas de una clave discrepan en `result`, el pick se excluye y se cuenta. Si no hay ninguna, el pick cuenta como «sin graduar» (§4.3).
  5. Clasificar el tier con `p`, cuota y novig de la fila del paso 1 (§2.5) y aplicar §2.6.
- **Cierre (T1):** véase §4.3.

### 2.2 Universo: graduado como primario y ledger como secundario

**Primario: el stream servido y graduado.** La fila de decisión sale del stream servido completo (`data/calibration/served_*.csv`) y el resultado, del graduado (`ServedStore(ROOT).load_all_graded()`, `data/calibration/graded_*.csv`, filas con `data_label == "real"`), en el orden de §2.1. Hay tres razones para que sea el primario:

1. **Es lo que el Tipster etiqueta.** `scripts/tipster_report.py` (`cargar_stream` → `cargar_stream_servido`) y la pestaña «Todos los Picks» (`src/sqp/audit/html_report.py:842`) clasifican el **stream servido**, no el ledger de candidatos. El tier A que ve el operador vive en este universo.
2. **No tiene el sesgo de selección del ledger.** El ledger solo contiene los lados que pasaron el suelo de edge del pipeline. El graduado contiene todos los lados priceados (docstring de `load_all_graded`).
3. **Llega más rápido** (§4.1): unos 7,5 picks A por día frente a unos 3,8.

**Secundario: el ledger** (`load_all_settled(data/bets)`). Es lo que muestra el Historial del dashboard (`load_history`), que es donde se vio la brecha. Se mide con el mismo test y se informa al lado, **sin poder de decisión**. Sigue el mismo orden de §2.1 con dos precisiones: la fila de decisión es la de `generated_at` mínimo **dentro del ledger** (es la que muestra el Historial, y ya lleva su resultado, así que el paso 4 es trivial), pero la pertenencia a la ventana se decide con la primera servida del **stream servido** de esa clave. Así, un pick servido antes de T0 tampoco entra en el ledger aunque su primera fila de ledger sea posterior. Si la clave no aparece en `served_*.csv`, se usa el mínimo del ledger y esas claves se cuentan.

### 2.3 Unidad y deduplicación (regla textual, independiente del código)

- **Clave del pick:** `(event_id, market, selection, line)`, con `line` numérico redondeado a 4 decimales **y +0,0 sumado tras redondear** (normaliza −0,0 a 0,0: un pick'em con `-0.0` y otro con `0.0` son el mismo pick), y vacío en h2h. Cada valor se convierte a texto **celda a celda**, con NaN → `""`. Concatenar series con NaN fusionaba todos los h2h (nota en `_unique_settled_picks`).
- **Identidad incompleta:** una fila con `event_id`, `market` o `selection` ausente (NaN o texto vacío tras recortar espacios) **se excluye y se cuenta**. No se colapsa con nada ni se conserva: una clave parcial fusionaría partidos distintos, y conservarla sin clave impediría saber si es una primera servida. Si el fichero carece de alguna de esas columnas, el script aborta.
- **Se conserva una sola fila por clave: la de `generated_at` mínimo** (orden estable por el instante parseado; un sello ilegible va al final y nunca se elige; una clave cuyos sellos son todos ilegibles se excluye y se cuenta). Es el momento de decidir. El tier, `p` y la cuota se toman de **esa** fila. Que el pick sea A en otra servida no lo convierte en A. Es el paso 1 del orden de §2.1.
- **Ledger:** se aplica la misma regla estricta. `_unique_settled_picks` conserva además todas las filas con `stake > 0`, porque el Historial no debe perder PnL real. Para un test de acierto el stake no importa, así que aquí manda una fila por clave. Se informa cuántas claves tenían más de una fila con stake (con shadow mode, previsiblemente 0).
- **Verificación cruzada con `_unique_settled_picks`** (`src/sqp/audit/report.py`, commiteado con H según §10). Se aplica a todo el ledger, como hace el Historial, y se compara con la regla textual **restringida a las claves de la ventana (T0, T1]**. Diferencias esperadas, que se enumeran y cuentan por separado:
  1. claves con alguna fila `stake > 0`: `_unique_settled_picks` conserva todas sus filas con stake (y descarta la de stake 0), y la regla textual una sola, la primera;
  2. filas con identidad incompleta **por NaN**: `_unique_settled_picks` las conserva sin tocar y la regla textual las excluye; las de texto vacío, `_unique_settled_picks` las agrupa en una clave con campo vacío y la regla textual las excluye;
  3. claves cuya pertenencia a la ventana cambia porque la regla textual la decide con el stream servido (§2.2) y no con el ledger.
  Cualquier diferencia fuera de esas tres clases se informa como discrepancia. En todos los casos manda la regla textual.

### 2.4 Filtros de validez (se aplican antes de clasificar y se cuentan)

Se aplican **solo a la fila de decisión** (la primera servida, paso 3 de §2.1), después del filtro de ventana. Si esa fila no los pasa, el pick entero queda fuera y se cuenta por motivo; no se busca otra servida del mismo pick que sí los pase, porque eso sería elegir la promesa a posteriori.

- Solo **pregame**: se excluyen las filas con `generated_at ≥ start_time`, y las que tienen `start_time` ilegible. Es el invariante del corte de información: una cuota tomada en juego no es la promesa del pick.
- Se excluyen las filas sin `p` finita, sin cuota (`price_decimal`) > 1 o sin `implied_probability_novig`. `tipster_table` ya no las clasifica.
- Ligas: **todas**, sin excluir ninguna. El universo del Tipster es todo el stream. Recortar ligas después sería segmentar a posteriori.

### 2.5 Definición de tier congelada en H

- El tier se calcula con `classify`/`tipster_table` de `src/sqp/evaluation/tipster.py` y `decision_prob` de `src/sqp/evaluation/labels.py` **tal como están en H**, con **`max_plausible_ev = 0,075` como literal congelado en este documento**. El script no lo lee de ninguna configuración: ni del yaml, ni de `Settings`, ni del entorno.
- El informe **registra** el valor efectivo de `Settings().risk.max_plausible_edge` (`src/sqp/config.py`, que antepone `MAX_PLAUSIBLE_EDGE` del `.env` al yaml) **en H y en el momento de medir**, junto con el de `configs/default.yaml` en H y en HEAD. El de H se escribe en el **mensaje del tag anotado** `prereg-tier-a-t0` al crearlo (§2.1), porque este fichero no puede contener un valor leído después de su propio commit; al medir, el script lo calcula y lo compara. Si alguno difiere de 0,075, se informa como dato y se cuantifica como en el punto siguiente; no cambia la definición.
- Si al medir esos blobs difieren de los de HEAD (`git rev-parse H:<ruta>` frente a `HEAD:<ruta>`), el script carga las versiones de H (`git show H:<ruta>`) en un espacio de módulos aislado y clasifica con ellas. Informa los dos hashes.
- **Un cambio posterior de `TIER_A`, `TIER_B` o `max_plausible_edge` no cambia la definición del test.** El test mide el clasificador congelado. Si el umbral vivo diverge, el informe dice cuántos picks de la muestra clasificaría distinto el vivo, como dato descriptivo.

### 2.6 Resultados

- **Primario:** solo `result ∈ {win, loss}`. Es la convención de `hit_rate` del proyecto (`_segment_audit`, AUD-MED-002): una media no es ni acierto ni fallo.
- `void` y `push` quedan fuera (no hay resultado) y se cuentan.
- `half_win` y `half_loss` quedan fuera del primario y se cuentan. **Sensibilidad S5:** incluirlas como en `calibrator.py:724-726` (acierto si `half_win`, peso 0,5).

---

## 3. Estadístico y test

### 3.1 Primario

    D̂ = (1/n) Σ (y_i − p_i)          sobre los n picks A win/loss de §2

- **Error estándar robusto por clúster de DÍA**, con el día definido como la fecha del partido (`start_time`, instante UTC) convertida a la **zona IANA fija `America/New_York`**. La zona se pasa explícitamente al script (`--tz-cluster America/New_York`, valor por defecto congelado) y se informa en la salida. **No** se usa `labels.game_date_local` ni `labels.tz_local()`, porque dependen de la zona de la máquina que ejecuta: el mismo dato daría clústeres distintos en el equipo de desarrollo y en el CI (lo documenta el propio docstring de `tz_local`). Las filas sin `start_time` legible ya quedaron fuera por §2.4, así que no hay fallback a `game_date`.
- **Por qué `America/New_York`.** La zona del operador **no es derivable** del repositorio con seguridad: no hay zona configurada en `configs/` ni en `src/sqp`, y los docstrings de `labels.py` dan indicios contradictorios (UTC+2 en `tz_local`, UTC−4 en `local_date`). Entre las candidatas restantes se elige la que mejor cumple el fin del clúster, que es agrupar los choques comunes de una jornada: la mayoría de los A de la ventana serán de ligas de EE. UU. (NFL, NCAAF, NBA, NHL, MLB, §4.1), cuyos partidos nocturnos empiezan después de las 00:00Z. En UTC una misma jornada se partiría en dos días y se infraestimaría la correlación intra-día (sesgo anticonservador); en hora del Este empieza y se fecha dentro del mismo día. Fútbol europeo y tenis empiezan en su mayoría entre las 06:00 y las 16:00 ET y no se ven afectados. La zona IANA resuelve el horario de verano sin ambigüedad. Los efectos de diseño de §4.1 se midieron con la zona de la máquina; la diferencia se acepta porque N ya toma el mayor de los cuatro.
- Es el estimador sándwich con corrección CR1:

      SE² = G/(G−1) · Σ_g (Σ_{i∈g} (r_i − D̂))² / n²        r_i = y_i − p_i,  G = nº de días

- Se usa el **día** y no el evento porque el evento está anidado en el día (la primera servida de un pick fija su partido, que se juega un día) y porque el día recoge además los choques comunes de una jornada: una jornada de NFL o NCAAF concentra muchos A. Medido sobre la muestra ya vista (§4.1), el efecto de diseño por día es mayor que el de evento en los dos universos (graduado 1,169 frente a 1,124; ledger 1,228 frente a 1,164). Es la elección conservadora.
- **z = D̂ / SE**, con p unilateral = Φ(z).
- **α = 0,05 unilateral.** Se rechaza H₀ si `z ≤ −1,6449`. No se usa la t de Student. Con G de varios centenares de días, la diferencia es despreciable, y el script informa G.

### 3.2 Multiplicidad

- **Un solo test confirmatorio** (§3.1) con α = 0,05. Todo lo de §5 es descriptivo o de control y no tiene poder de decisión. Actuar sobre un secundario exige un pre-registro nuevo.
- **Familia propia, sin repartir α con los otros pre-registros vivos.** El gate K = 52 controla el error de familia de una decisión de **stake** (Bonferroni 0,05/52 por corte). «El modelo manda» decide `market_shrink`. Este test decide como mucho una **etiqueta y su descripción** (§6). Ninguna decisión del proyecto combina los tres resultados, así que no forman una familia de contrastes sobre la misma acción y dividir α entre ellos no protegería nada. Si un día una decisión dependiera conjuntamente de este test y de otro, se re-pre-registraría la multiplicidad antes de ejecutar ninguno de los dos.

---

## 4. Tamaño muestral, potencia y fecha

### 4.1 Lo medido hoy (agregados por script, sin cargar filas en contexto)

Script de un solo uso en el scratchpad de la sesión, que solo imprime agregados. Usa `load_all_settled` + `_unique_settled_picks`, `load_all_graded` + la regla de §2.3 y `tipster_table` con 0,075. Último `generated_at` presente: 2026-09-30 15:23 UTC. El stream graduado empieza el 2026-07-07.

| métrica | graduado (primera servida) | ledger (colapsado) |
|---|---:|---:|
| picks A win/loss | 641 (+8 void, +7 push) | 386 (+2 void, +2 push) |
| tasa A win/loss por día, desde el inicio del universo | 7,45 (641 en 86 d) | 3,82 (386 en 101 d) |
| tasa desde el 2026-09-01 | 8,80 | 5,87 |
| ídem, sin MLB ni WNBA (temporadas que terminan) | 6,40 (192 en 30 d) | — |
| varianza del residuo `y − p` | 0,2489 | 0,2517 |
| efecto de diseño, clúster día / evento | 1,169 / 1,124 | 1,228 / 1,164 |
| tamaño medio del clúster: evento / día | 1,21 / 8,3 | 1,17 / 5,3 |
| latencia generación → liquidación, mediana / p90 (días) | 1,76 / 7,0 | 1,0 / 3,1 |

Composición del A graduado desde el 2026-09-01: ncaaf 80, nfl 63, mlb 52, fútbol 27, wnba 20, tenis 15, nhl 7. La NBA no tiene filas servidas todavía, y la NHL solo 54.

### 4.2 Efecto mínimo de interés y N

- **δ = 0,03** (3 pp de brecha). **Es derivable, no elegido:** `TIER_A["edge_pp"] = 0,03` es el edge mínimo sobre el mercado sin vig que la etiqueta A afirma. Si `p` promete de más en 3 pp, el acierto esperado de un A en el umbral cae a la probabilidad del mercado sin vig, y el «edge sólido» que justifica la etiqueta desaparece por completo. Una brecha menor deja A miscalibrado pero con edge esperado positivo. Una brecha de 3 pp o más vacía de contenido la etiqueta.
- **Qué significa aquí «edge esperado positivo».** Es edge **sobre la probabilidad del mercado sin vig** (`edge_pp = p − implied_probability_novig`), no EV ni ROI. Con brecha menor que δ, el acierto esperado de un A sigue por encima del novig, pero la cuota cobrada lleva vig, así que el EV y el ROI esperados pueden ser negativos igualmente. δ no dice nada de rentabilidad (§1.4).
- **δ está anclado en el umbral, no en la media.** 0,03 es el `edge_pp` del A **marginal**. La media de `edge_pp` de los A es mayor, así que con una brecha de exactamente 3 pp el A medio aún conservaría algo de edge sobre el novig. Se ancla en el umbral a propósito: es la afirmación mínima que la etiqueta hace de **cada** pick A, y una brecha que la anula en el margen ya hace falsa la etiqueta para una parte de los picks que la llevan.
- Se rechaza anclar δ en la brecha ya observada (5,6 o 9,1 pp), como hizo el precedente del 2026-08-26 con la suya. Aquí esa cifra procede de un corte elegido por llamativo y está sesgada al alza. Potenciar contra ella daría un test que solo detecta lo que ya se cree ver.
- α = 0,05 unilateral (z = 1,6449) y **potencia 0,80** (z = 0,8416). El precedente del 2026-08-26 usaba `N = (1,96·DE/δ)²`, que equivale a una potencia de 0,5. Aquí se pide la convención estándar, porque un «no significativo» con potencia 0,5 se leería como «A está calibrado».
- σ² = 0,2489 (varianza del residuo medida en el graduado).
- **Efecto de diseño = 1,228**, el mayor de los cuatro medidos. Tras T0 la composición se desplaza a NFL y NCAAF, que concentran los A en sábados y domingos, así que se espera más correlación intra-día que en la muestra con MLB diaria. Se toma la cota superior de lo medido en lugar de inventar un número.

      N = (1,6449 + 0,8416)² · 0,2489 / 0,03² · 1,228 = 1.709,8 · 1,228 = 2.099,7  →  **N = 2.100 picks A win/loss**

Potencia del test con efecto de diseño 1,228 (α = 0,05 unilateral):

| N | SE | δ = 0,02 | **δ = 0,03** | δ = 0,056 | δ = 0,09 |
|---:|---:|---:|---:|---:|---:|
| 300 | 0,0319 | 0,15 | 0,24 | 0,54 | 0,88 |
| 600 | 0,0226 | 0,22 | 0,38 | 0,80 | 0,99 |
| 1.000 | 0,0175 | 0,31 | 0,53 | 0,94 | 1,00 |
| 1.500 | 0,0143 | 0,40 | 0,68 | 0,99 | 1,00 |
| **2.100** | 0,0121 | 0,51 | **0,80** | 1,00 | 1,00 |

### 4.3 Fecha y disparo

- **Fecha estimada: hacia julio de 2027**, con un rango que va de finales de mayo a finales de agosto de 2027. Con T0 ≈ 2026-10-02: a 8,8 picks/día, 2027-05-29; a 7,45, 2027-07-11; a 6,4 (sin MLB ni WNBA), 2027-08-27. A eso se suman hasta 14 días de margen de liquidación (ver abajo). Es una estimación gruesa. La NBA y la NHL arrancan en octubre sin tasa A medible hoy, y NFL y NCAAF terminan entre enero y febrero.
- **La medición se dispara por recuento, no por calendario** (precedente del 2026-08-26). El script tiene un modo `--contar` (§7) que solo imprime `n`, `G` y fechas, **nunca** aciertos, `p` ni brechas. Se recomienda ejecutarlo una vez al mes, y semanalmente cuando `n` pase de 1.800.
- **Qué `n` dispara.** `n` es siempre el del **universo PRIMARIO** (servido y graduado, §2.2): picks con primera servida en (T0, E − 14 días], que pasan §2.4, clasificados A con el clasificador de H y **graduados** con `result ∈ {win, loss}`. Los no graduados, void, push y medios no cuentan. El ledger no dispara nada.
- **Registro versionado de recuentos.** Cada ejecución de `--contar` **añade** una línea JSON a `docs/research/2026-10-02-preregistro-brecha-tier-a.contar.jsonl` (append-only; nunca se reescribe ni se borra una línea) con: instante de ejecución E (UTC), HEAD, H, T0, T1 candidato = E − 14 días, `n` primario, `G`, `n` del ledger (informativo), picks de la ventana sin graduar, y el SHA-256 de cada CSV leído. El fichero se commitea tras cada ejecución. Vive junto a este pre-registro porque forma parte de su procedencia; `scripts/research/` es para código.
- **Fijación de T1.** La **primera** línea del registro con `n ≥ 2.100` fija **T1 = E − 14 días** de esa ejecución. Ese T1 se escribe en un **addendum commiteado** a este documento (sección «Addenda», con el hash del commit del registro que lo justifica) antes de cualquier ejecución de `--medir`. Ejecuciones posteriores de `--contar` siguen anotándose pero no mueven T1. La población son los picks con primera servida en (T0, T1]. Los 14 días son 2 × el p90 de latencia medido (7,0 días en el graduado). Así casi todos los picks de la ventana estarán liquidados y no se seleccionan por rapidez de liquidación: un torneo de tenis liquida más tarde que un partido de MLB. Los picks de la ventana que sigan sin graduar se cuentan y se informan.
- **`--medir --t1 <ISO>`** exige el T1 explícito, comprueba que coincide con el del addendum commiteado y con la primera línea del registro que cruzó 2.100, y verifica que `n(T1) ≥ 2.100` con los datos del momento de medir. Si alguna comprobación falla, aborta sin calcular nada.
- **δ y N no se cambian después de H** salvo por un fallo técnico documentado (por ejemplo, un error aritmético en §4.2), y en ese caso con revisión de Fable y sin haber mirado ningún resultado de la muestra. La razón es concreta: desde el commit 49abb16 el Historial del dashboard muestra **a diario** el acierto frente a lo prometido del tier A del **ledger**, picks posteriores a T0 incluidos. El operador y cualquier sesión ven, de hecho, una versión parcial de la muestra mientras se acumula. Cualquier enmienda adaptativa de δ, N, T1, la población o el criterio de decisión queda por eso **vetada**: no habría forma de demostrar que no la motivó lo visto.
- **Una sola ejecución** del modo de medición. No hay miradas intermedias. Un diseño secuencial (gasto de α tipo O'Brien-Fleming) adelantaría la fecha si la brecha es grande, pero se descarta porque la orden es de ejecución única. Re-ejecutar solo se permite por un fallo técnico que impida producir el informe. Si, tras producirlo, aparece un error que altere la población, se publican **ambos** resultados, el original y el corregido, con revisión de Fable. El original no se borra.

---

## 5. Controles, contrapruebas y descriptivos (sin poder de decisión)

Todos sobre la misma población y la misma ventana, con SE por clúster de día.

1. **S1 — Ledger.** El mismo test sobre el universo del ledger (§2.2).
2. **S2 — Tier B como control.** Se informan `D̂_B` y la diferencia `D̂_A − D̂_B`, con SE por clúster de día sobre la unión. Una brecha de A **mayor** que la de B localiza el problema en el filtro A. Una brecha igual apunta a una sobreconfianza general del pipeline, y entonces la etiqueta no es el sitio donde corregirla. También se informa el tier C. NO BET no es comparable, porque contiene EV ≤ 0 por construcción.
3. **S3 — Benchmark de mercado.** `acierto − media(implied_probability_novig)` dentro de A. Responde a si A supera siquiera al mercado sin vig, que es exactamente lo que afirma «edge sólido».
4. **S4 — Calibración por bandas.** Dentro de A, `p` en [0,50; 0,55), [0,55; 0,60) y ≥ 0,60, y `edge_pp` en [0,03; 0,05) y ≥ 0,05. Las bandas son cortes redondos de presentación y no deciden nada. También por grupo de deporte (MLB, NFL, NCAAF, NBA, WNBA, NHL, fútbol y tenis), para hacer visible la composición (amenaza A1). Y, **pre-declarado aquí como descriptivo**, la partición antes/después de **cada** addendum de régimen de §8 A2 (por ejemplo, si «el modelo manda» cambia `market_shrink` hacia noviembre de 2026), con `D̂` y su SE en cada tramo. No decide nada ni recorta la ventana.
5. **S5 — Sensibilidad del primario.** (a) Clúster por evento en lugar de día. (b) Bootstrap por bloques de día: 10.000 réplicas, semilla 20261002, cotas unilaterales al 95 % por percentil (la inferior, percentil 5; la superior, percentil 95). (c) Inclusión de `half_win`/`half_loss` (§2.6). **Fragilidad, definida por clase:** el bootstrap (b) clasifica por su cuenta — **CONFIRMA** si la cota superior unilateral al 95 % es < 0; **DESCARTA** si la cota inferior unilateral al 95 % es > −0,03; **INCONCLUSO** en otro caso (la cola opuesta de §6 cuenta como DESCARTA a estos efectos). Si esa clase no coincide con la del primario, el resultado se declara **frágil** en el informe y no se actúa sin revisión.
6. **S6 — Métricas de apuesta, separadas y solo descriptivas.** «Cuota» es `price_decimal`, la mediana del consenso guardada en la fila de decisión: la misma con la que se clasifica el tier. Métricas: acierto observado; prob. prometida media; prob. implícita media (`1/cuota`); edge medio (`p − novig`); ROI esperado medio (`EV = p·cuota − 1`); ROI realizado a stake plano de 1 unidad (`cuota − 1` si gana, `−1` si pierde). Si la fila trae `execution_price` no vacío (line shopping, capa aditiva), el ROI esperado y el realizado a ese precio se informan **aparte**, con el número de filas que lo tienen, y nunca sustituyen a los de `price_decimal`. Las métricas de ROI se informan **por separado** y ninguna es una promesa.

---

## 6. Criterios de decisión y acciones permitidas

Con `z` y `SE` del §3.1 (clúster día, CR1):

| resultado | condición | lectura | acciones permitidas |
|---|---|---|---|
| **CONFIRMA** | `z ≤ −1,6449` | El tier A promete de más, fuera de muestra y con dependencia intra-día. | (1) Registrar el resultado en `docs/research/<fecha>-resultado-brecha-tier-a.md` y en la memoria del proyecto. (2) **Proponer** al operador: una nota en el Tipster/Historial con la brecha medida y su IC; un pre-registro **nuevo**, con muestra posterior propia, para revisar `TIER_A` o la calibración de los picks filtrados por edge. **Ningún umbral se cambia sin aprobación expresa del operador**, y ninguno se ajusta sobre esta misma muestra. |
| **DESCARTA brecha ≥ δ** | no confirma y `D̂ − 1,6449·SE > −0,03` | Con potencia 0,80, una brecha que anule el edge declarado queda descartada al 95 %. Puede seguir habiendo una brecha menor. | Registrar. La observación de §1.2 queda como un artefacto de selección a posteriori. Ninguna acción. |
| **INCONCLUSO** | ni lo uno ni lo otro | No se rechaza H₀, pero tampoco se descarta una brecha de 3 pp. | Registrar con el IC. No se re-mide sobre la misma ventana ni se amplía N a posteriori. |
| (cola opuesta) | `z ≥ +1,6449` | A promete de menos. | Solo se informa. Ninguna acción por este test. |

En **ningún** caso el resultado:
- toca el stake, el `prediction_gate`, `max_plausible_edge` ni ningún calibrador;
- promueve o despromueve nada automáticamente;
- se presenta como evidencia de rentabilidad o de su ausencia.

S2 y S3 matizan la **redacción** de la propuesta al operador, por ejemplo «el problema es de A» frente a «el problema es general». No cambian la clasificación del resultado.

---

## 7. Contrato del script de medición (NO escrito todavía)

**Ruta propuesta:** `scripts/research/measure_tier_a_gap.py`.

**Entradas**
- `--data-root` (por defecto, la raíz del repositorio): lee `data/calibration/served_*.csv` (fila de decisión y ventana), `data/calibration/graded_*.csv` vía `ServedStore.load_all_graded` (solo el resultado) y `data/bets/settled_*.csv` vía `load_all_settled` (universo secundario). Nunca vuelca filas a la salida.
- `--preregistro` (por defecto, la ruta de este fichero): H y T0 se derivan del tag anotado `prereg-tier-a-t0`, con fallback a `git log --diff-filter=A` sobre esta ruta (§2.1).
- `--tz-cluster` (por defecto y congelado, `America/New_York`): zona IANA del día de clúster (§3.1). Un valor distinto solo se admite como sensibilidad marcada, nunca para el primario.
- Modo `--contar`: imprime solo `n_A_winloss` por universo (el primario es el que dispara, §4.3), `G`, primera y última servida de la ventana, T1 candidato y picks sin graduar. Ni `y`, ni `p`, ni brechas. **Añade** la línea correspondiente a `docs/research/2026-10-02-preregistro-brecha-tier-a.contar.jsonl` (§4.3).
- Modo `--medir --t1 <ISO>`, **una sola vez**: exige el T1 fijado por addendum, comprueba que coincide con la primera línea del registro con `n ≥ 2.100` y que `n(T1) ≥ 2.100`, y aborta si algo falla (§4.3). Admite `--out <json>`.
- `--seed 20261002` y `--n-boot 10000`, fijos por defecto, para S5(b).

**Proceso**, en el orden único de §2.1: (1) cargar `served_*.csv`, excluir identidad incompleta y quedarse con la primera servida por clave (§2.3) → (2) ventana (T0, T1] sobre esa fila → (3) validez (§2.4) sobre esa misma fila → (4) resultado desde `graded_*.csv` por clave → (5) clasificación con el código de H y el literal 0,075 (§2.5) → §2.6 → §3.1 → §5. El ledger sigue el mismo orden con las precisiones de §2.2.

**Salida** (JSON en `--out` y en stdout):
- procedencia: H, T0, T1, HEAD, vía de resolución de H (tag o fallback), zona del clúster de día, hashes de blob de `tipster.py`, `labels.py` y `configs/default.yaml` en H y en HEAD, `max_plausible_edge` efectivo de `Settings` al medir frente al registrado en el tag y frente al literal 0,075, `git status --porcelain -- src configs scripts/research`, y SHA-256 y número de filas de cada CSV leído;
- recuentos de cada filtro y paso (identidad incompleta, sellos ilegibles, fuera de ventana, cada motivo de §2.4, resultados discrepantes, sin graduar, §2.6, duplicados colapsados, claves con varias filas con stake, claves del ledger ausentes del stream servido) y la verificación cruzada de §2.3 por clase de diferencia;
- primario: `n`, `G`, `D̂`, `SE`, `z`, `p`, `D̂ − 1,6449·SE` y la etiqueta de §6;
- S1 a S6, con la clase del bootstrap y la marca de fragilidad de S5.

**Tests mínimos** (`tests/research/`, solo datos sintéticos):
- la deduplicación conserva la primera servida, no fusiona h2h con NaN, trata `-0.0` y `0.0` como la misma línea y excluye (y cuenta) las filas con identidad incompleta;
- un pick servido antes de T0 y re-servido después queda fuera, también cuando la servida anterior a T0 no está graduada;
- un pick cuya primera servida no pasa §2.4 queda fuera aunque una servida posterior sí la pase;
- el clúster de día usa la zona pasada y no la de la máquina, y reproduce el SE a mano en un caso de 3 días;
- `--contar` no emite ningún campo de resultado y añade exactamente una línea al registro;
- `--medir` aborta sin T1, con un T1 distinto del registrado o con `n(T1) < 2.100`.

---

## 8. Amenazas a la validez

- **A1 — Composición.** La brecha vista viene en un 39 % de MLB en el graduado y en un 44 % en el ledger. La muestra del test será sobre todo NFL, NCAAF, NBA y NHL, y MLB volverá en primavera. El test responde por el tier A **tal como opere** en (T0, T1], no por el tier A del verano de 2026. Se informa S4 por deporte, pero no se re-segmenta para decidir.
- **A2 — Cambios de régimen.** Desde H, cada cambio de modelo, de calibrador o de población (como los del tilt NHL 0,439, `pitcher_bound` 0,05 o el descanso NBA 0,795, todos **anteriores** a T0) se registra como **addendum antes de medir**, con el formato de `2026-09-25-repreregistro-gate-k52.md`. Esos addenda no alteran ningún criterio, y queda prohibido usarlos después para recortar la ventana. El test evalúa el sistema tal como operó. Lo único que se hace con ellos está **pre-declarado** en S4 (§5): la partición antes/después de cada addendum, solo descriptiva. El candidato previsible es «el modelo manda» (`2026-08-26-preregistro-el-modelo-manda.md`, medición hacia noviembre de 2026), si su resultado cambia `market_shrink`. Una ventana de unos 9 meses acumulará varios regímenes. Es el precio de δ = 0,03 y se acepta a sabiendas.
- **A3 — Deriva de umbrales.** El clasificador queda congelado en H (§2.5). Si el operador cambia `TIER_A` o `max_plausible_edge`, el test sigue midiendo la definición de H y el informe cuantifica la divergencia con la viva.
- **A4 — Sesgo de selección del ledger.** Por eso el ledger es secundario. El graduado tiene su propio filtro, porque solo contiene lo que el pipeline pudo pricear y servir. Es el universo del Tipster, que es lo que importa aquí.
- **A5 — Probabilidad de la fila frente a probabilidad mostrada.** El Tipster muestra la servida **más reciente** vigente (`picks_vigentes_unicos`), mientras que el test usa la **primera** (el momento de decidir). Un pick puede ser A el lunes y B el martes. El test mide la promesa inicial. S5 no cubre esta variante y no se añade ahora para no multiplicar contrastes. Se documenta.
- **A6 — Dependencia residual.** Hay correlación entre días contiguos (rachas de forma, una misma serie de MLB) que el clúster de día no recoge. El efecto de diseño medido es pequeño (≤ 1,23) y S5(b) es la contraprueba.
- **A7 — Sello temporal.** `generated_at` es el instante de servir y `start_time` el del partido. El filtro pregame (§2.4) depende de que ambos estén en UTC. Así lo escribe el pipeline hoy (ISO 8601 con zona), y el script lo verifica.

---

## 9. Lo que este pre-registro NO prueba

- Que el tier A sea o no rentable, ni que lo sea ningún otro tier.
- Que los umbrales de `TIER_A` sean óptimos. Elegir umbrales es otra pregunta y necesita otra muestra.
- Nada sobre la calibración global del pipeline, aunque S2 da una pista.

---

## 10. Decisión del operador

- [x] **Pre-registro aprobado.** El operador ordenó realizar el pre-registro («Sí, házlo», 2026-10-02), en respuesta a la propuesta de comprobar la brecha del tier A con un test pre-registrado. **No revisó el texto.** El commit que añade este fichero (tag `prereg-tier-a-t0`) fija H y T0. Hasta ese commit nada cuenta como muestra.
- [x] **N = 2.100 y su horizonte (≈ julio de 2027) aceptados.** No lo eligió el operador en persona: N y δ los decidió el coordinador de la sesión (Opus) por delegación, porque el operador delega esta clase de decisiones, siguiendo la recomendación de diseño de §4.2: δ = 0,03 es el edge mínimo que declara la propia etiqueta. La alternativa de anclar en la brecha ya vista (0,056, N ≈ 600) se rechaza por sesgo a posteriori. **Después de H, δ y N no se cambian** salvo por fallo técnico (§4.3). Esto incluye una preferencia posterior del operador por otro δ: como el Historial (commit 49abb16) muestra a diario el acierto frente a lo prometido del tier A del ledger, picks posteriores a T0 incluidos, ninguna enmienda de δ o N posterior a H podría demostrar que no la motivó lo visto, y queda vetada. Un δ distinto exige un pre-registro nuevo con muestra propia.
- [x] **Precondición técnica:** `_unique_settled_picks` se commitea en el mismo commit que este fichero. Justo después se crea el tag anotado `prereg-tier-a-t0` sobre ese commit, con el valor efectivo de `Settings().risk.max_plausible_edge` en su mensaje (§2.1, §2.5).

---

## Addenda

Ninguno todavía. Aquí se añaden, por commits posteriores a H y sin editar nada de lo anterior: los addenda de régimen (§8 A2) y el addendum que fija T1 (§4.3).

### Addendum 1 (2026-10-03): implementación del script. No altera ningún criterio.

`scripts/research/measure_tier_a_gap.py` y `tests/research/test_measure_tier_a_gap.py` (82 tests sintéticos):
- implementación de Sonnet;
- revisión de Fable en tres rondas: APTO CON CAMBIOS (6 hallazgos medios y 5 bajos, todos aplicados), APTO (3 bajos, aplicados) y APTO CON CAMBIOS sobre el texto de este addendum (aplicados).

Estas son decisiones de implementación que el contrato de la §7 no fijaba. Ninguna cambia la hipótesis, la población, el test, δ, N ni las reglas de decisión.
1. **`--no-log`.** Bandera de diagnóstico, fuera del contrato. Permite comprobar `--contar` sin añadir línea al registro, que sigue la letra de §4.3 («cada ejecución añade»). Ninguna ejecución con `--no-log` cuenta para fijar T1, y no emite ningún resultado.
2. **`start_time` del ledger (solo S1).** `settled_*.csv` no tiene esa columna, así que se toma de la primera servida por clave. Si la clave no está en `served_*.csv`, la fila se trata como ilegible: se excluye y se cuenta.
3. **Formato del addendum de T1.** Lleva dos líneas literales: `T1 fijado = <ISO-8601>` y `commit del registro = <sha>`. `--medir --t1` lee el addendum y el registro con `git show HEAD:`. Verifica que el commit citado contiene la primera línea con n ≥ 2.100 y el mismo T1, compara instantes y no texto, y aborta si algo no cuadra.
4. **Lectura de CSV sin efectos secundarios.** Se usa un lector propio con la misma semántica que `load_all_graded` (concatena y filtra `real`), pero sin la cuarentena de `ServedStore._load`, que renombra ficheros: medir no puede mutar `data/`.
   - `--medir` aborta si una liga listada falta o no se puede leer. Una liga que solo trae cabecera se informa como vacía y no aborta.
5. **Clasificador congelado.** Si el blob de `tipster.py` o `labels.py` en disco (`git hash-object`) o en HEAD difiere del de H, se carga siempre la versión de H, aislada. `default.yaml` solo se registra: no clasifica nada, porque el tope es el literal 0,075 (§2.5).
6. **Zona del clúster.** El primario usa siempre `America/New_York`. Otro `--tz-cluster` solo produce una sensibilidad aparte y marcada. Una zona inválida se rechaza antes de calcular nada.
7. **`--seed` y `--n-boot`.** Si difieren de los congelados (20261002 y 10.000), se marcan en `procedencia.seed_n_boot` sin abortar. El bootstrap solo informa de la fragilidad (§5 S5), no decide.
8. **Exclusiones de §2.4.** Se cuentan de forma mutuamente excluyente, en el orden pregame → p → cuota → novig.

**Primera ejecución oficial de `--contar` (2026-10-03T12:50Z):** n = 0, G = 0. El T1 candidato (2026-09-19) es anterior a T0, así que la ventana está vacía, como prevé §4.3.

---

## Historial de revisión

- **Diseño:** Fable (rol de pre-registro de `.claude/automation/MODEL_ROUTING.md`).
- **Revisión Fable, 2026-10-02, de solo lectura: APTO CON CAMBIOS.** Sus 12 hallazgos se aplicaron **antes** del commit que fija H: registro versionado de `--contar` y T1 por addendum (§4.3, §7); orden de operaciones único a partir de `served_*.csv` (§2.1–§2.4, §7); zona IANA fija para el día de clúster (§3.1); veto a cambiar δ o N tras H (§4.3, §10); tag anotado `prereg-tier-a-t0` (§2.1); normalización de −0,0, identidad incompleta y verificación cruzada acotada (§2.3); literal 0,075 congelado y valor efectivo registrado (§1.1, §2.5); fragilidad por clase (§5 S5); cuota = `price_decimal` (§5 S6); alcance de «edge esperado positivo» y anclaje de δ (§4.2); partición por régimen pre-declarada (§5 S4, §8 A2); procedencia de la aprobación (§10).

## Addendum 2 (2026-10-17): filas `nhl|h2h` anteriores a `ffc5ad3` (AUD-003). Antes de medir.

Este addendum pertenece a la sección «Addenda». Se añade al final del fichero para no editar nada anterior. Diseño y revisión: Fable. Es un **fallo técnico documentado** en el sentido de §4.3, y se escribe sin haber mirado ningún resultado de la muestra: ni acierto, ni brecha, ni `D̂`. Lo pendiente lo dejó declarado `docs/research/2026-10-16-enmienda-gate-nhl-h2h-aud003.md`.

**Hecho.** Hasta `ffc5ad3` (2026-10-16T12:56:03Z), el consenso h2h de la NHL incluía casas del 1X2 con Draw. Por eso el `implied_probability_novig` de esas filas es falso: fair(home)+fair(away) quedaba por debajo de 0,95 en 1.150 de 1.835 snapshots, con una mediana de 0,8477. Totales y spreads de la NHL y el resto de ligas no estaban afectados.

**Efecto sobre este test.** El `fair` falso entra dos veces en la fila de decisión:

- **En la promesa:** `p = 0,5·cal(p_adj) + 0,5·fair`, rebajada en los dos lados.
- **En la clasificación:** `edge_pp = p − fair` sale inflado, y `EV = p·cuota − 1` sale rebajado.

Una `p` rebajada empuja `y − p` hacia arriba. Va contra CONFIRMA, pero a favor de DESCARTA, que también es una conclusión del §6. El tier asignado a esas filas es un artefacto del fallo, no una decisión del clasificador sobre datos válidos. Además, S3 compara directamente contra la columna falsa. No es un sesgo conservador para todas las salidas del test, así que no basta con dejarlo «como operó».

**Regla.** Se excluye y se cuenta (`mercado_invalido_aud003`) la fila de decisión de `nhl|h2h` cuyo `generated_at` sea anterior a 2026-10-16T12:56:03Z o ilegible. La regla es la misma que `INVALID_BEFORE` del gate. Se aplica en el paso 3 del orden de §2.1, después de pregame y antes de los filtros de `p`, cuota y novig (recuentos mutuamente excluyentes, Addendum 1 punto 8). Vale para el universo primario y para el ledger (S1), cada uno sobre su propia fila de decisión, igual que el resto de §2.4. Nunca se salta a una servida posterior del mismo pick: §2.4 lo prohíbe porque sería elegir la promesa a posteriori. No se recalcula el no-vig: el consenso correcto no se reconstruye con las columnas guardadas, y la renormalización del par no es la definición canónica.

**Por qué no es una enmienda adaptativa (§4.3, §10).** El corte lo fija un hecho del pipeline, el instante del arreglo, y no depende de ningún resultado. Recuento hecho hoy, sin resultados y con `tipster.py`/`labels.py` de HEAD: el stream servido tiene 176 picks `nhl|h2h` con primera servida en (T0, corte). Su clasificación con el literal 0,075 da **0 A**, 1 B, 1 C y 174 NO BET (la `p` rebajada deja casi todo con EV ≤ 0). El universo primario del test, que solo cuenta picks A, no pierde ningún pick. Ni `n` ni T1 ni el calendario (≈ julio de 2027) se mueven, y la regla no puede haberla motivado ningún acierto del tier A. Solo cambian, en dos picks, los controles descriptivos S2 (tier B/C). δ = 0,03, N = 2.100, la zona del clúster, el clasificador congelado y los criterios no cambian. La línea existente del registro `.contar.jsonl` (n = 0) no se reescribe.

**Código:** `scripts/research/measure_tier_a_gap.py` (`INVALID_BEFORE` como literal congelado, `invalid_market_mask` y su paso en `build_primary_from_primeras` y en `build_ledger_population`). Tests: `tests/research/test_measure_tier_a_gap.py`, con dos tests nuevos: exclusión sin sustitución en los dos universos con el corte en `>=`, y literal igual al del gate. Si el gate añade otra entrada a `INVALID_BEFORE`, el test falla y obliga a decidir por addendum antes de medir. Queda prohibido usar este addendum para recortar la ventana.

## Addendum 3 (2026-10-18): remediación audit-2026-10-18. Antes de medir.

Desde el commit de la remediación de la ronda `audit-2026-10-18` (2026-10-18): (1) AUD-001: el modelo NHL reparte el empate del tiempo reglamentario en (k+1,k)/(k,k+1) y reescala los ritmos para conservar el total esperado; cambian las p de `nhl|totals` (2-3 pp), `nhl|spreads` (≤0,6 pp) y `nhl|h2h` (≤0,3 pp). (2) AUD-002: el descanso cuenta los partidos programados del run; solo afecta a la NBA (0,795). (3) AUD-008: el gate y el entrenamiento del calibrador excluyen las filas totals/spreads de línea de cuarto con `generated_at` < 2026-09-13T12:36:34Z (c578f52), graduadas sin medias; el corte lo fija el código, no un resultado. Diseño y revisión: Fable (rol de pre-registro de `.claude/automation/MODEL_ROUTING.md`). Se registra **antes** de mirar ningún resultado. **No altera ningún criterio**, y queda prohibido usarlo para recortar o re-segmentar la ventana.

(3) no afecta: la población empieza en T0 (2026-10-02).

## Addendum 4 (2026-10-20): `execution.books: [pinnacle]`. Antes de medir.

Desde el commit que declara `execution.books: [pinnacle]` (2026-10-20), `execution_price`/`execution_book` dejan de repetir la mediana y toman el precio de Pinnacle cuando cotiza la línea (si no, la mediana). `price_decimal`, edge, selección, stake y liquidación no cambian. Solo afecta a las métricas descriptivas de `execution_price`, que se informarán partidas antes/después de esta fecha. Redactado por Fable (rol de pre-registro de `.claude/automation/MODEL_ROUTING.md`). Corte: `generated_at` ≥ 2026-10-20T13:31:09Z (instante de f92e8e1); sin fecha legible, `sin_fecha`. Desglose en `execution_price_por_regimen` de S6; el agregado se conserva. No altera ningún criterio y queda prohibido usarlo para recortar o re-segmentar la ventana.
