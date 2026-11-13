# Regla de adopción tras «el modelo manda»: qué política de mercado se aplica con cada resultado

**Fecha:** 2026-11-13.
**Estado:** ADOPTADA el 2026-11-13 por delegación expresa del operador («Continúa con todas las tareas pendientes. Te otorgo mi autorización para llevarlas a cabo»); decisiones D1-D6 resueltas en §5. D1 queda revocable por el operador hasta el commit del resultado de MM, no después. Solo vale como regla si se commitea **antes** del commit que añada `docs/research/*-resultado-el-modelo-manda.md`. Después de ese commit no se enmienda, salvo defecto técnico documentado y revisado por Fable.
**Qué se ha mirado para escribirla:** código, configuración y documentos. No se ha ejecutado `scripts/research/measure_el_modelo_manda.py` en ningún modo, no se ha leído ningún fichero de `data/` y no existe ningún `*resultado-el-modelo-manda*.md`. Del registro de recuentos solo se ha leído la última línea (`docs/research/2026-08-26-preregistro-el-modelo-manda.contar.jsonl`: 2.394 eventos el 2026-10-13), que no contiene resultados.

En adelante, **MM** es `docs/research/2026-08-26-preregistro-el-modelo-manda.md`, **07** es `docs/prompts-audit/07-independencia-del-mercado.md`, **06** es `docs/prompts-audit/06-arquitectura-recomendada.md`, **09** es `docs/prompts-audit/09-principios-fundamentales.md` y **PM** es `docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.md`.

Este documento **no cambia ningún criterio de MM**. Solo fija, para cada desenlace que MM ya define, qué valor toma cada parámetro de producción y qué decisiones siguen siendo del operador. Responde a la tarea abierta de `Obsidian/Tareas.md:13`.

---

## 0. Punto de partida verificado

| Parámetro | Valor hoy | Ruta |
|---|---|---|
| `market_shrink` (M1) | 0,5, global | `configs/default.yaml:17`; se aplica en `src/sqp/pipeline/probabilities.py:303-305`, llamada desde `src/sqp/pipeline/daily.py:1050-1051` |
| `uncertainty_penalty` (M3, M16) | 0,35 | `configs/default.yaml:26`; `src/sqp/markets/edge.py:69-73, 87-88` |
| `anomaly_edge_gap` / `anomaly_extra_penalty` / `low_book_penalty` / `min_books_for_consensus` | 0,06 / 0,02 / 0,015 / 2 | `configs/default.yaml:27-30` |
| `min_edge` / `max_plausible_edge` (M7, M16) | 0,02 / 0,075 | `configs/default.yaml:4, 16` |
| Penalizaciones de movimiento, velocidad y dispersión (M4) | 0,0 | `configs/default.yaml:35, 39, 49` |
| `picks.mode` (M21) | `edge` | `configs/default.yaml:199-200` |
| `shadow_mode` / `prediction_gate.enabled` | `false` / `true` | `configs/default.yaml:248, 283-284` |
| Monitor de degradación (M10) | `brier_margin` 0,01; `roi_pause` −0,15; `roi_resume` −0,05; ventana 60 días; `min_n` 30 | `configs/default.yaml:297-303` |
| `park_bound` MLB (M15) | 0,10 | `configs/leagues/ratings.yaml:25-30` |

Hechos que condicionan la regla:

- **No existe `market_shrink` por liga ni por segmento.** El valor es un escalar global (`daily.py:1051`; PM:21). La variable de entorno `MARKET_SHRINK` gana sobre el yaml (`src/sqp/config.py:466-467`), y el `.env` no está versionado (PM:337).
- **El `s` de cada fila ya se persiste** en la columna `market_shrink` del stream servido (`daily.py:1121-1123`; `src/sqp/storage/served_store.py:45-51`). Es la precondición técnica que 07 da por cumplida (07:44).
- **El stake real lo gobierna el `prediction_gate`**, por defecto denegado (`configs/default.yaml:231-246, 262-284`). El 2026-10-31 los 67 cortes evaluados tenían `allowed = False` (`docs/research/2026-10-31-preregistro-modo-inicio-temporada.md:84-86`). El estado actual no se ha consultado (vive en `data/`).
- Los valores `uncertainty_penalty` 0,35, `max_plausible_edge` 0,075 y `park_bound` 0,10 se eligieron por ROI sobre cuotas y están declarados como herencia pendiente de revalidación (`tests/test_market_independence.py:486-489`; 09:63-69).

---

## 1. Tabla de decisiones

### 1.1 Los veredictos que produce MM

- **Primario (P):** PASA si el IC95 de `Brier(p_cal) − Brier(fair)` queda entero por debajo de 0; PEOR si queda entero por encima; FALLA en otro caso (MM:159-160, 333). Se ejecuta una sola vez con ≥ 3.402 eventos (MM:156-157).
- **Segmentos:** solo los `liga|mercado` con ≥ 800 eventos; Holm a α = 0,05 sobre los elegibles; un segmento pasa la primera puerta si Holm rechaza y `D̂ < 0`, y es «PEOR en el segmento» si rechaza con `D̂ > 0` (MM:164-167, 337-343). Se deciden siempre, pase o no el primario, y el primario no entra en la familia de Holm (MM:344).
- **Segunda puerta (ROI):** `Δ = ROI_0 − ROI_0,5` con stake plano; PASA si el límite inferior del IC95 por evento es > 0. Solo se calcula para las unidades que pasaron la primera puerta: la global si pasa el primario, y cada segmento que pasó Holm (MM:349-359). Las dos puertas deben pasar (MM:187-188, 362).

Notación: **G2** es la segunda puerta de la unidad global; **S2** es el conjunto de segmentos que pasan **las dos** puertas; **SP** es el conjunto de segmentos «PEOR».

### 1.2 Acción sobre `market_shrink`

| Fila | P | G2 | S2 | `market_shrink` | Fundamento |
|---|---|---|---|---|---|
| **R1** | PASA | PASA | cualquiera | **0,0 global**, salvo los segmentos de SP, que siguen en 0,5. Shadow de 30 días. | MM:192-194, 349. La excepción de SP es regla nueva de este documento (§1.5). |
| **R2** | PASA | FALLA | vacío | **0,5, sin cambio.** | MM:187-188: cualquier puerta que falle deja al mercado mandando en el stake. |
| **R3** | PASA | FALLA | no vacío | **0,0 solo en los segmentos de S2**; 0,5 en el resto. Shadow de 30 días. | MM:192-194 («para el segmento que las pase y solo para ese»). |
| **R4** | FALLA | no evaluada | vacío | **0,5, sin cambio.** La tesis queda cerrada para esta temporada y esta configuración. | MM:196-200. |
| **R5** | FALLA | no evaluada | no vacío | **0,0 solo en los segmentos de S2**; 0,5 en el resto. Shadow de 30 días. | MM:166-167, 344. |
| **R6** | PEOR | no evaluada | vacío | **0,5, sin cambio.** Un `s` mayor que 0,5 solo puede salir de PM. | MM:202-204; PM:51, 276. |
| **R7** | PEOR | no evaluada | no vacío | **0,0 solo en los segmentos de S2**; 0,5 en el resto. Shadow de 30 días. | MM:166-167, 344 (un segmento que pasa es candidato aunque el global falle). |
| **R8** | no medido | — | — | **0,5, sin cambio.** | Ver §1.4. |

Un segmento que pasa la primera puerta y falla la de ROI sigue en 0,5 (MM:187-188). Si no hay ningún segmento con ≥ 800 eventos, S2 y SP están vacíos (MM:338).

Los únicos valores que esta regla puede escribir son **0,5** y **0,0**. Ningún valor intermedio está definido por MM. Un `s_k` distinto solo puede salir de PM, con su propio procedimiento y nunca antes de T0 + 14 días (PM:49, 130).

### 1.3 El resto de parámetros, en todas las filas

| Ítem de 07 | Acción en R1-R8 | Por qué |
|---|---|---|
| **M3** `uncertainty_penalty` 0,35, `anomaly_edge_gap` 0,06, `anomaly_extra_penalty` 0,02, `low_book_penalty` 0,015, `min_books_for_consensus` 2 | **Sin cambio.** | MM no los mide (07:46). La segunda puerta se calcula con esos literales congelados (MM:352-355): si `s` pasa a 0 por esa evidencia, cambiarlos a la vez la invalida. Con `s = 0` el `gap` de cada pick se duplica frente al de la mezcla; eso es lo que la puerta midió. Su revalidación queda pendiente (§5, D2). |
| **M7 / M16** `min_edge` 0,02 y `max_plausible_edge` 0,075 | **Sin cambio.** | Mismos literales de la segunda puerta (MM:355). Revalidación de `max_plausible_edge`: §5, D2. |
| **M4** penalizaciones de movimiento, velocidad y dispersión | **Siguen en 0,0.** | 07:47: el principio las descarta como entrada; activarlas exigiría pre-registro propio. |
| **M9** `prediction_gate` | **Sin cambio.** Sigue siendo la única vía a stake real. | Lee `model_probability`, que no depende de `s` (07:52; `configs/default.yaml:264`). K = 69, α por corte 0,000702, n ≥ 300 (`configs/default.yaml:266-269`). |
| **M10** monitor de degradación | **Parámetros sin cambio.** | Compara `estimated_probability` con el mercado (07:53). Donde `s` pase a 0, esa columna será `cal(p_adj)` y el monitor medirá el modelo sin mezcla. Se declara como efecto esperado; no se retoca `brier_margin` para compensarlo. |
| **M15** `park_bound` 0,10 | **Sin cambio por MM.** Lo gobierna su pre-registro. | `docs/research/2026-11-10-preregistro-park-bound-mlb.md:427-464` (qué valor con cada veredicto) y `:466-505` (cuándo). Con el resultado de MM commiteado, la medición puede ejecutarse (`Obsidian/Tareas.md:19`). |
| **M21** `picks.mode` | **Sigue en `edge`.** | 07:64. |
| **M2, M5, M6, M8, M11-M14, M17-M20** | **Nada.** | Ya clasificados como legítimos o comparación posterior (07:45, 48-49, 51, 54-57, 60-63). |

### 1.4 Fila R8: MM no produce resultado

- **No se alcanza N.** No se mide y no se rebaja el umbral (MM:237-238). Si MM no se ha ejecutado el 2026-12-31, el operador fija por addendum el T0 de PM sin haber calculado ningún `s_k` (PM:52).
- **`--medir` aborta por la comprobación de `s`** (MM:366). El pre-registro se reescribe (MM:230-232). Esta regla deja de valer y debe reemitirse antes de la nueva medición.
- **Corrección técnica posterior a la publicación.** Va como sección añadida al mismo fichero, con revisión de Fable (MM:373). Manda el resultado corregido. Si la fila que le corresponde es distinta de la aplicada, la configuración vuelve a la de la fila correcta en el siguiente commit previo al run de las 12:00.

### 1.5 Dos precisiones que MM deja abiertas

1. **Global pasa y un segmento sale «PEOR» (R1 con SP no vacío).** MM no dice qué manda. Regla de este documento: el segmento de SP **se queda en 0,5**. Es la lectura conservadora: mantiene lo vigente allí donde hay evidencia específica, corregida por Holm, en contra. Queda sujeta a la aprobación del operador (§5, D5).
2. **Segmento «frágil».** Si el veredicto de Holm y la clase del IC bootstrap del segmento no coinciden, MM lo marca como frágil y decide Holm (MM:345). Esta regla no añade criterio: se aplica Holm, y la revisión de Fable previa al commit de configuración lo hace constar.

### 1.6 Cómo se aplica un `s → 0` (R1, R3, R5, R7)

1. **Nunca en el commit del resultado.** Ese commit lleva solo el `.md` y el `.json` (MM:373) y fija T0 de PM (PM:46). El cambio de configuración va en un commit posterior.
2. **Revisión de Fable antes del commit** (parámetro de riesgo: `CLAUDE.md`, clase escalada) y commit antes del run de las 12:00 (`docs/research/2026-11-10-preregistro-park-bound-mlb.md:502`).
3. **Addenda previos, sin alterar criterios:**
   - PM: una línea en su tabla de régimen con el formato literal `s servido = 0.0 | desde = <ISO-8601 con zona> | alcance = <global | liga|mercado>` (PM:373-376). PM ya prevé este caso (PM:88, 291). Un torneo de tenis no es un alcance válido en esa tabla (PM:385); en esas filas manda la columna `market_shrink` (PM:370).
   - Brecha tier A: addendum A2 (`docs/research/2026-10-02-preregistro-brecha-tier-a.md:260`, que nombra este caso).
   - Gate: nota informativa. No cambia `model_probability`, K ni el techo.
4. **Valor efectivo.** Comprobar `Settings.load().risk.market_shrink` tras el cambio, porque `MARKET_SHRINK` en el `.env` gana sobre el yaml (`config.py:466-467`). Lo comprueba el operador.
5. **Por segmento (R3, R5, R7 y la excepción de R1).** Hace falta código que hoy no existe (PM:21). Debe vivir en la política de decisión y no en `configs/leagues/` (06:239-240), escribir en la columna `market_shrink` de cada fila el valor aplicado y llevar tests. Hasta que ese cambio esté revisado y commiteado, el segmento sigue en 0,5.
6. **Shadow de 30 días** (MM:192-194), contados desde el commit que aplica el cambio. Se sirve `s = 0` (así lo lee PM:88) con stake 0 en los cortes afectados durante el plazo (D3, vía `paused_markets`: la fila se sigue sirviendo, marcada `market_paused`); al vencer, el stake real vuelve a depender solo del `prediction_gate` y de la regla de salida vigente (`docs/research/2026-08-16-preregistro-regla-de-salida.md`). MM no define ningún criterio medible para el final del shadow ni una regla de reversión; esta regla no los inventa (§5, D3).

---

## 2. Compatibilidad con el principio de independencia

El principio del operador (2026-11-10) dice que las probabilidades salen solo de datos deportivos y que el mercado solo se compara después de congelarlas. 07 separa dos capas (07:70):

- **Estimación.** Adaptadores, features, calibradores y tuning por resultados no leen cuotas, y la probabilidad pura se persiste antes de la mezcla (07:45, 51, 62-63). **Cumple hoy y cumple en todas las filas.** Ninguna fila de §1 introduce el mercado en esta capa, tampoco R6.
- **Decisión y publicación.** La probabilidad que selecciona, dimensiona y se muestra es 50 % mercado (M1) y la de stake incorpora la distancia al mercado (M3) (07:44, 46).

| Filas | Estimación | Decisión y publicación |
|---|---|---|
| **R1** | Cumple | M1 queda resuelto en todo lo que pase a `s = 0`: la probabilidad servida es `cal(p_adj)`. M3 sigue: la penalización 0,35 usa `|p − fair|` y entra en la probabilidad de stake. El cumplimiento es parcial hasta resolver D2. |
| **R3, R5, R7** | Cumple | M1 resuelto solo en S2. En el resto vale lo dicho para R2/R4/R6. M3 sigue. |
| **R2, R4** | Cumple | M1 y M3 siguen. La evidencia pre-registrada no respalda quitar la mezcla del stake. La vía de cumplimiento es la de 06: la mezcla y la penalización pasan a ser **política de decisión etiquetada, posterior a la congelación, nunca parte de la probabilidad** (06:85, 239), y la probabilidad congelada se registra y se muestra con su nombre (06:160-200; `Obsidian/Tareas.md:16`). Son cambios aditivos: no se altera el significado de ninguna columna existente. Si eso basta para dar el principio por cumplido lo decide el operador (§5, D1). |
| **R6** | Cumple | Igual que R2/R4. Un `s` mayor que 0,5 aleja más la decisión del modelo. Solo puede llegar por PM, como política de decisión y con aprobación expresa (PM:249-259). |
| **R8** | Cumple | Sin cambio; el conflicto de 07 sigue abierto. |

En ninguna fila queda resuelto M16 (parámetros de decisión elegidos por ROI). M15 lo resuelve su propio pre-registro.

---

## 3. Lo que no se hará en ninguna fila

1. **Re-medir MM**, repetirlo con otra ventana, métrica o segmentación, o rebajar N (MM:198-200, 238, 245-246). Tampoco crear un segundo `*resultado-el-modelo-manda*.md` (MM:373).
2. **Decidir con una sensibilidad o un descriptivo.** Las sensibilidades de MM no tienen poder de decisión (MM:279, 361, 372).
3. **Elegir un parámetro por ROI o CLV.** En MM el ROI solo veta: es necesario, no suficiente (MM:175). 09:63-69 prohíbe usarlo como selector.
4. **Escribir un `market_shrink` distinto de 0,5 o 0,0** por esta regla, o calcular un `s_k` antes de lo que PM permite (PM:49, 130).
5. **Cambiar `uncertainty_penalty`, `anomaly_*`, `low_book_penalty`, `min_edge` o `max_plausible_edge`** junto con `s` o como consecuencia del resultado de MM.
6. **Activar M4 o `pick_mode: accuracy`.**
7. **Meter el mercado en la estimación o en la calibración**, en ninguna dirección.
8. **Dar stake real fuera del `prediction_gate`**, o presentar cualquier resultado como rentabilidad (MM:211-212; `.claude/rules/betting-output-rules.md`).
9. **Usar el resultado de MM para enmendar PM o tier A.** Ambos lo vetan (PM:222; `2026-10-02-preregistro-brecha-tier-a.md:189`).
10. **Cambiar el significado de columnas servidas existentes o quitar filas del stream.**
11. **Tocar `configs/` antes de que el resultado esté commiteado**, o sin la revisión de Fable previa.
12. **Reescribir esta regla después de ver el resultado.**

---

## 4. Multiplicidad entre los pre-registros abiertos

### 4.1 Qué comparte cada uno, según su propio texto

| Pre-registro | Muestra confirmatoria | ¿Lee el stream servido? | Control interno | Acción que gobierna |
|---|---|---|---|---|
| **MM** | graduado hasta T1 (MM:48-52, 328) | Sí | Primario al 95 %; Holm a 0,05 en segmentos; ROI como segunda puerta (MM:159, 343, 362) | `market_shrink` → 0 |
| **Peso por segmento (PM)** | eventos con `start_time > T0`, disjuntos de MM (PM:48) | Sí | H1 primero; luego Holm sobre H2 y segmentos (PM:153-160). «Cada test conserva su α = 0,05» (PM:50) | columna shadow con `p_k`; `s` solo con aprobación (PM:249-259) |
| **Brecha tier A** | picks con primera servida en (T0, T1] desde el 2026-10-02 (`…brecha-tier-a.md:61-63, 187`) | Sí; sus filas solapan con las de MM y PM | Un test, α = 0,05 unilateral, familia propia (`:131-136`) | una etiqueta y su descripción (`:213-221`) |
| **Gate K = 69** | servido desde el 2026-08-16 | Sí | Bonferroni, familia 0,05 (`configs/default.yaml:266-269`) | stake real por corte |
| **`park_bound` MLB** | instantánea del histórico, sin cuotas (`…park-bound-mlb.md:178-181, 468-470`) | **No** | Una celda; siete criterios a la vez; sin corrección (`:329-333`) | `park_bound` |
| **Portero NHL** | histórico y backfill (`…portero-nhl.md:598-600`) | **No** | Seis criterios a la vez (`:343-358`) | `goalie_beta` |
| **Recencia, fase M** | resultados emparejados con cuotas capturadas, con `model_probability` recalculada (`…recencia-totales.md:297-313`) | **No** | Solo puede vetar; sin α (`:328-341`). La fase H ya usó Holm con K = 3 (`:281-283`) y dio NBA y NFL ACEPTA, NHL RECHAZA (`2026-10-10-resultado-recencia-totales-H.md:90`) | `scoring_half_life_days` |

**Corrección a la premisa.** Solo MM, PM, tier A y el gate comparten el stream servido. `park_bound`, portero y la fase M de la recencia no lo leen. Interfieren de otro modo: **su activación cambia el régimen** de las filas que los otros miden, y cada uno exige addenda previos (`…park-bound-mlb.md:485-494`; `…portero-nhl.md:602-613`; `…recencia-totales.md:567-576`). Lo mismo vale para el Elo NBA y el modo de inicio de temporada (`2026-10-29-preregistro-elo-regresion-temporada.md:522-553`; `2026-10-31-preregistro-modo-inicio-temporada.md:460-480`).

### 4.2 Regla propuesta: una acción, una familia; en serie dentro de la familia

1. **La familia se define por la acción de producción**, no por las filas. Es el criterio que ya usan tier A (`…brecha-tier-a.md:136`: no forman familia porque ninguna decisión combina sus resultados) y PM (PM:44-50). Dentro de cada familia rige el control que declara su pre-registro. Entre familias no se reparte α.
2. **Familia «política de mercado»** (`market_shrink`, `uncertainty_penalty`, `anomaly_*`, `low_book_penalty`, `max_plausible_edge`; el bloque que 06:239 llama `market_policy`). Se resuelve **en serie**: primero MM, después PM, y solo después cualquier contraste nuevo sobre esos parámetros. MM y PM no se pueden recalibrar: sus criterios están sellados (MM:245-246; PM:222). Si chocan, no se aplica ninguno solo y decide el operador; una decisión conjunta exige pre-registro nuevo (PM:273-276).
3. **Familia «etiqueta»**: tier A, sola.
4. **Familia «stake real»**: el gate. Toda decisión de dinero pasa por él, con su Bonferroni.
5. **Familias de modelo**: una por liga y parámetro (`park_bound`, portero, recencia, Elo). No comparten muestra con el stream servido. Sus **activaciones** sí se ordenan: una por liga cada vez, con los addenda previos que cada documento exige y nunca antes del resultado de MM (`…park-bound-mlb.md:475-480`).
6. **Decisiones cruzadas.** Si una decisión llegara a depender a la vez de dos familias, la multiplicidad se pre-registra antes de ejecutar cualquiera de los dos tests (`…brecha-tier-a.md:136`). Si uno ya está ejecutado, la combinación es solo descriptiva.

**Lo que esta regla no arregla, declarado.** [INFERENCIA] En la familia de política de mercado hay tres contrastes al 5 % bilateral con decisión unilateral: el primario de MM, la familia de Holm de MM y el H1 de PM. Por la cota de unión, la probabilidad de al menos un cambio de `s` sin efecto real es como mucho unas tres veces 0,025, antes de exigir las puertas de ROI. No es 0,05. No se corrige porque exigiría cambiar criterios sellados. Se acepta porque las muestras de MM y PM son disjuntas, cada cambio pasa además por una puerta de ROI y por un shadow, y el stake real sigue bajo el gate.

### 4.3 Congelación de pre-registros nuevos

**Sí, parcial.**

- **Congelados** hasta que se publique el resultado de PM (estimado hacia marzo de 2027, PM:218): los pre-registros nuevos que gobiernen un parámetro de la familia de política de mercado, o que usen el stream servido como muestra confirmatoria para una acción que ya gobierna un test abierto (`market_shrink`, la etiqueta del tier A, el stake por corte). Pueden **redactarse** antes, pero no medirse. Esto incluye la revalidación de `uncertainty_penalty` y `max_plausible_edge` (§5, D2).
- **No congelados:** los pre-registros de modelo sobre instantáneas del histórico, sin cuotas y sin el stream servido, como los de `Obsidian/Tareas.md:20`. No gastan la muestra compartida. Su activación sigue el punto 5 de §4.2.
- **Excepción:** un pre-registro nuevo sobre el stream servido puede medirse antes si su ventana confirmatoria empieza después de su propio commit, gobierna una acción que ningún test abierto gobierna y declara por escrito su relación de multiplicidad con los abiertos.

---

## 5. Decisiones que quedan para el operador

- **D1 — El principio cuando MM no abre `s → 0` (R2, R4, R6 y los segmentos fuera de S2).** Pregunta exacta: «Si MM no autoriza `s = 0` en una unidad, ¿el principio de independencia se da por cumplido cuando la probabilidad congelada `cal(p_adj)` se registra y se muestra como la estimación, y la mezcla 0,5 queda etiquetada como política de decisión posterior a la congelación (06:85, 239)? ¿O el operador ordena `s = 0` también en la selección y el stake, contra el resultado, "por orden", como hizo con `pitcher_bound` (`configs/leagues/ratings.yaml:17-21`)?» **Propuesta de esta regla:** lo primero. Si se ordena lo segundo, el comentario de `configs/default.yaml` debe decir «por orden del operador, MM del <fecha>: <veredicto>», y hay que registrar antes los addenda de §1.6. El `prediction_gate` seguiría decidiendo el stake real.
- **D2 — `uncertainty_penalty` 0,35 y `max_plausible_edge` 0,075.** Ningún documento del proyecto define cómo revalidarlos ni un valor alternativo, aparte del no-op (0,0 para la penalización, `src/sqp/config.py:126-129`; 0,15 como valor anterior del tope, `configs/default.yaml:11-12`). Pregunta exacta: «¿Se conservan "por orden" como política de decisión heredada y declarada, o se encarga un pre-registro propio? Si es lo segundo, ¿con qué métrica se valida un parámetro de la capa de stake, dado que 09:63-69 prohíbe elegir por ROI y MM solo usa el ROI como veto?» Hasta que se responda, no cambian.
- **D3 — El shadow de 30 días.** MM:192-194 fija el plazo, pero no qué se comprueba al terminarlo ni cuándo se revierte. Pregunta exacta: «¿El shadow termina solo por plazo, con el stake real sujeto únicamente al `prediction_gate`, o exige un criterio medible, y cuál? Si al aplicar el cambio algún corte afectado tuviera `allowed: true`, ¿se deja a stake 0 durante los 30 días (por ejemplo con `paused_markets`, `configs/default.yaml:214-219`) o sigue apostando?» **Propuesta:** solo por plazo, y stake 0 durante el shadow.
- **D4 — `market_shrink` por segmento.** Pregunta exacta: «¿Autoriza el operador el cambio de código que permite un `market_shrink` por `liga|mercado` (necesario en R3, R5, R7 y en la excepción de R1), como parte de la política de decisión y con revisión de Fable?» Sin él, esas filas no se pueden aplicar.
- **D5 — Segmento «PEOR» con global que pasa (§1.5).** Pregunta exacta: «¿Aprueba que un segmento que Holm declara PEOR quede en 0,5 aunque el global pase las dos puertas?»
- **D6 — Aprobación de este documento** y de la congelación parcial de §4.3, antes del commit del resultado de MM.

### 5.1 Resolución (2026-11-13, por delegación del operador; orquestación `claude-opus-5-5` sobre la propuesta de Fable)

- **D1:** se adopta la propuesta: en las unidades donde MM no autorice `s = 0`, el principio se dará por cumplido cuando `cal(p_adj)` congelada se registre y se muestre como la estimación (pendiente, `Obsidian/Tareas.md:16`); la mezcla 0,5 se etiqueta como política de decisión posterior a la congelación. Revocable por el operador solo antes del commit del resultado de MM.
- **D2:** `uncertainty_penalty` 0,35 y `max_plausible_edge` 0,075 se conservan como política de decisión heredada y declarada. No se elige ningún valor por ROI. Un pre-registro de revalidación queda congelado por §4.3 hasta el resultado de PM.
- **D3:** el shadow termina solo por plazo (30 días), con stake 0 en los cortes afectados durante ese plazo, vía `paused_markets` (no quita filas; compatible con §3).
- **D4:** autorizado de forma condicional. El código de `market_shrink` por `liga|mercado` se escribe solo si el resultado cae en R1 con excepción, R3, R5 o R7, y con revisión de Fable antes del commit. No se escribe por adelantado. En R1 con segmentos PEOR, el 0,0 global no se aplica hasta que ese código esté revisado y commiteado; mientras tanto todo sigue en 0,5.
- **D5:** sí. Un segmento PEOR por Holm queda en 0,5 aunque el global pase.
- **D6:** documento y congelación parcial de §4.3 aprobados. Se commitea hoy, antes de cualquier medición de MM.

---

Relacionado: [[2026-08-26-preregistro-el-modelo-manda]], [[2026-10-13-preregistro-peso-mercado-por-segmento]], [[2026-10-02-preregistro-brecha-tier-a]], [[2026-11-10-preregistro-park-bound-mlb]], [[2026-09-26-preregistro-portero-nhl]], [[2026-10-09-preregistro-recencia-totales]], [[2026-08-16-preregistro-regla-de-salida]].

Redactado el 2026-11-13 antes de la medición MM; autor: Fable
