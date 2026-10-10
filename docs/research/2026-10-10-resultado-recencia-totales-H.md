# Resultado — recencia del adaptador de totales, fase H: NBA y NFL ACEPTAN, NHL RECHAZA por H5 (h2h +0,000007), y nada se activa todavía

**Fecha:** 2026-10-10. Ejecución única de la fase H del pre-registro
`2026-10-09-preregistro-recencia-totales.md` (commit `027c019`), con su Enmienda 1
(a)–(q) (commit `f315f4c`) y las seis decisiones del operador del 2026-10-09
(«Aprobar todas»). Redacta y verifica Fable a partir de los JSON. No se ha repetido
ninguna fase (sección 15, E10).

**Esto no mide ventaja sobre el mercado.** La fase H mide solo la **probabilidad
estimada** (la distribución del total del propio adaptador) frente al total
realizado. No mide probabilidad implícita, edge, hit rate, ROI esperado ni ROI
realizado, y no autoriza ninguna afirmación sobre ellos (sección 16.5).

## Procedencia

- **Código:** `scripts/research/measure_totals_recency.py`, HEAD `f315f4c`
  (`f315f4c355fc…`), el mismo en el `--pre` y en la fase H. `git_status_porcelain`
  vacío en todo el repositorio en el `--pre`, y en `src/`, `configs/` y
  `scripts/research/` en la fase H. Entre los dos no hay commits.
- **SHA-256 de código** (normalizado a LF, Enmienda 1(q)), idénticos en `pre_H` y en
  `H.json` y reproducidos hoy sobre la copia de trabajo:
  - `measure_totals_recency.py` `326bb837…69482c8f`;
  - `measure_adjustment_battery.py` `bf1e0964…15c324b4`.
- **Configuración:** `configs/leagues/ratings.yaml` `7b904e4c…b483` y
  `configs/default.yaml` `fc2f9520…eed8f`, iguales a los de la sección 5 y a los de
  la batería. Parámetros resueltos de NBA, NFL y NHL idénticos en `pre_H` y `H.json` y
  conformes a la sección 5 (NBA `scoring_half_life_days 180.0`; NFL y NHL sin la
  clave).
- **Entradas:** la instantánea de la batería, `C:\dev\3\snapshots\bateria-ajustes-20261008`
  (sección 6). Manifiesto idéntico en `pre_H` y `H.json`:
  `results_nba.csv` `82d3b7ea…a66cdf3`, `results_nfl.csv` `ca9fb0e1…d36e7`,
  `results_nhl.csv` `6ded06ee…d7d29131`. Corte `date ≤ 2026-09-26`. Filas leídas
  NBA 34.065, NFL 8.046, NHL 32.900, con **0** descartes por `game_id` (Enmienda 3(c)
  de la batería).
- **`--pre`:** `pre_H_f315f4c.json`, SHA-256
  `2ad4bc7cb2296a3b86613172487c5efc7c492640a810999067b51b7886a6d449`. Es exactamente el
  `pre_json_sha256` registrado en `H.json`. El `--pre` reprodujo:
  - el aserto 5 de paridad frente a `pre_ee0ab19.json` (líneas L_i^base por hash y
    recuentos por partición);
  - la tabla 9.1 dentro de la tolerancia de la Enmienda 1(a);
  - la tabla 9.1 de la fase H, idéntica a la del `--pre`.
- **Fase H:** `H_f315f4c.json`, SHA-256
  **`32a0e9e3f3a216c9dfff41fc7f0d33be8df38954ea3e23f063d1cf205348b1ac`**
  (Enmienda 1(e): **es el valor que se pasa a `--fase M --pre --h-sha256`**).
  Log `H_f315f4c.log` `dd934a3f…7703ca00`; log del `--pre` `681f85c4…a31d68`.
  Duración 3.006 s, rc = 0.
- **Comando:**
  `python scripts/research/measure_totals_recency.py --fase H --data-root C:\dev\3\snapshots\bateria-ajustes-20261008 --pre-json <instantánea>\pre_H_f315f4c.json --out <instantánea>\H_f315f4c.json`.
- **Horario:** el `--pre` terminó a las 11:07:00 (UTC−3) y la fase H a las 11:57:32,
  3 minutos antes del run diario de las 12:00. La sección 15 pedía ejecutarla «lejos
  de las 12:00». Es una **desviación operativa sin efecto en el resultado**:
  - la fase H lee la instantánea, fuera de `data/`;
  - el código estaba commiteado, así que la guarda KI-036 no tenía nada que bloquear;
  - el script comprueba HEAD y hashes.
  Queda registrada.

**Recuentos de test** (iguales a los de la batería y a los de la sección 6):

| Liga | A | B | C | Combinado | Días UTC |
|---|---:|---:|---:|---:|---:|
| NBA | 7.134 | 6.621 | 5.577 | **19.332** | 3.205 |
| NFL | 1.664 | 1.601 | 1.339 | **4.604** | 1.290 |
| NHL | 5.780 | 5.192 | 5.978 | **16.950** | 2.781 |

Partidos fuera de la rejilla NHL (Enmienda 1(b)): **0**.

**Paridad** (sección 11; Enmienda 1(k): las tres ligas, antes de la primera pérdida).
Ninguna aserción falló; si alguna hubiera fallado, el script habría abortado sin
escribir salida.

| Aserción | NBA | NFL | NHL |
|---|---|---|---|
| 1. Motor (base y los 11 h) | 0,0 (n 34.005) | 0,0 (n 7.986) | 2,3·10⁻¹⁵ (n 32.840; h2h, spreads ±1,5, totals@5,5) |
| 2. μ frente a `adapter.estimate` (base y h = 90) | 0,0 | 0,0 | 1,9·10⁻¹⁵ (incluida la identidad λ_h + λ_a = μ + 0,10) |
| 3. Distribución del total NHL | no aplica | no aplica | 2,2·10⁻¹⁵ (Σ P(T = k) y P(Over) en 4,5–7,5) |

**Verificación independiente de esta revisión.** Los números de este informe se han
comprobado contra el JSON, sin fiarse de los booleanos. En concreto:

- la media de los Δ por partición, ponderada por los recuentos de test, reproduce el
  Δ H1 combinado de las tres ligas (diferencia < 10⁻¹⁵);
- Δ H1 y T − C coinciden con las diferencias de las pérdidas combinadas;
- p = Φ(Δ̂_H1/EE) recalculado: z = −14,64 (NBA), −3,72 (NFL) y −7,38 (NHL), con los
  mismos p que el JSON;
- Holm recalculado a mano;
- el código de los criterios (`evaluate_league_H`, l. 699-703, y H6 en l. 995-996)
  coincide literalmente con la sección 7.4;
- la regla de selección (`select_h`, l. 150-160) coincide con la sección 4.

## Veredicto: NBA ACEPTA, NFL ACEPTA, NHL RECHAZA

| | **NBA** | **NFL** | **NHL** |
|---|---|---|---|
| h vigente | 180 | 0 | 0 |
| h_A / h_B / **h_C** | 60 / 60 / **45** | 270 / 270 / **180** | 120 / 120 / **180** |
| a_A / a_B / a_C (control C) | +0,641 / +1,216 / +1,415 pts | +0,651 / +1,170 / +1,365 pts | −0,023 / −0,036 / +0,029 goles |
| Pérdida combinada base · T · C | 4,40706 · 4,39564 · 4,40453 | 4,06444 · 4,04935 · 4,05887 | 2,24054 · 2,23113 · 2,24047 |
| **Δ H1** (T − base) · IC95 · EE | **−0,01141** · [−0,01295; −0,00988] · 0,00078 | **−0,01510** · [−0,02280; −0,00671] · 0,00406 | **−0,00942** · [−0,01192; −0,00694] · 0,00128 |
| Δ A / B / C | −0,00893 / −0,01292 / −0,01280 | −0,02233 / −0,01910 / **−0,00132** | −0,00358 / −0,01262 / −0,01227 |
| IC95 de la partición C | [−0,01572; −0,00990] | **[−0,01851; +0,02052]** | [−0,01712; −0,00744] |
| T − C · IC95 | −0,00889 · [−0,01028; −0,00750] | −0,00952 · [−0,01672; −0,00134] | −0,00934 · [−0,01184; −0,00684] |
| Δ H4 (binario en L_i^base) · IC95 | −0,00817 · [−0,00948; −0,00685] | −0,00690 · [−0,01128; −0,00240] | −0,00363 · [−0,00563; −0,00172] |
| Δ H5 h2h · IC95 | no aplica | no aplica | **+0,0000071** · [−0,000101; +0,000116] |
| Δ H5 spreads ±1,5 (media) · IC95 | no aplica | no aplica | −0,000666 · [−0,000841; −0,000486] |
| p · p Holm | 8,1·10⁻⁴⁹ · 2,4·10⁻⁴⁸ | 1,01·10⁻⁴ · 1,01·10⁻⁴ | 8,2·10⁻¹⁴ · 1,6·10⁻¹³ |
| H1 · H2 · H3 · H4 · H5 · H6 | ✔ ✔ ✔ ✔ — ✔ | ✔ ✔ ✔ ✔ — ✔ | ✔ ✔ ✔ ✔ **✘** ✔ |
| **Veredicto H** | **ACEPTA** | **ACEPTA** | **RECHAZA** |

Las pérdidas son log loss por partido de la distribución del total (sección 7.3):
normal con σ = `total_sigma` en NBA y NFL, y Poisson conjunta truncada en 15 en la
NHL. Bootstrap por bloques de día UTC: 10.000 réplicas, semilla 42.

**H5 en NBA y NFL.** `delta_H5` es `null` y el JSON registra `H5: true`. Es la lectura
literal de la sección 7.4: H5 es «solo NHL». En NBA y NFL, h no mueve h2h ni spreads
(sección 1.2) y el criterio no aplica. El código lo implementa así
(`True if h5 is None`, l. 703). No es un aprobado medido.

**Holm** (K = 3, α = 0,05):

1. NBA, p 8,1·10⁻⁴⁹ ≤ 0,05/3;
2. NHL, p 8,2·10⁻¹⁴ ≤ 0,05/2;
3. NFL, p 1,01·10⁻⁴ ≤ 0,05.

Rechaza las tres nulas, así que H6 se cumple en las tres. En la NHL, H6 se cumple y la
liga rechaza por H5.

### Por qué la NHL rechaza con un Δ h2h de +7·10⁻⁶

La regla pre-registrada (sección 7.4.5, con la lectura de la Enmienda 1(c)) exige
**a la vez**:

- Δ log loss de h2h ≤ 0;
- Δ medio de spreads ±1,5 ≤ 0.

Las dos se miden en el test combinado, con el h_P de cada partición. La regla es un
**signo sobre la estimación puntual**, sin margen ni IC: es una restricción de «no
empeorar», no un contraste. El h2h subió **+0,0000071** (n = 16.950; ningún empate de
marcador). Es una cantidad indistinguible de 0: su IC95 [−0,000101; +0,000116]
contiene el 0 con holgura, y vale 0,13 EE (EE 5,6·10⁻⁵). Pero el
signo es positivo, y la regla literal dice que con eso falla. **Falla.** La
puck line sí mejora (−0,00067, IC lejos de 0).

Esto no se reinterpreta. La sección 16.1 ya lo previó: «Si en la NHL fallan solo H5,
se documenta como el empate del 2026-08-18, ahora medido.» Así se documenta:

- el 2026-08-18, con h = 90 en una línea fija, el moneyline empeoró +0,0011;
- hoy, con h_P = 120/120/180 y la pérdida sin línea, el h2h queda en +0,000007: un
  empate práctico.

El cambio de h mueve sobre todo el **nivel** de la NHL, que no afecta a quién gana.

## Lectura

### Qué significa

- **NBA.** Pasa de 180 días a h_P = 60/60/45. Mejora la distribución del total
  en las tres particiones, en las 14 temporadas del informe 3, frente al control de
  nivel y en el log loss binario en L_i^base. El efecto es unas 5,7 veces el margen
  de 0,002.
- **NFL.** Pasa de 0 (media acumulada desde 2002) a h_P = 270/270/180. Mejora en el
  combinado unas 7,5 veces el margen. Bate al control de nivel con un IC95 que no
  toca el 0.
- **NHL.** Pasa de 0 a h_P = 120/120/180. Mejora la distribución del total
  (−0,0094) y la puck line, pero no puede presentarse como aceptada: el h vigente
  (0) se mantiene (sección 16.1).
- En las tres ligas la mejora frente al **control C** es casi tan grande como frente
  a la base. Un desplazamiento constante de nivel, estimado en entrenamiento, no
  explica lo que gana h.

### Qué NO significa

- **Nada se activa.** La fase H decide existencia y valor; la activación exige además
  que la fase M no vete (sección 16.4). Producción sigue con NBA 180, NFL 0 y NHL 0.
- **La fase M puede vetar.** Se medirá contra la línea capturada del mercado y su
  no-vig. El modo de fallo que vigila es el del informe 7 de la batería: mejorar
  frente al desenlace y empeorar en la línea servida.
- Un M que no vete **tampoco** será evidencia de mejora frente al mercado (sección
  8.3). Lo que mejora aquí es la **probabilidad estimada** de la distribución del
  total. **No** crea edge, **no** cambia la conclusión de *encompassing* del
  2026-09-07 y **no** autoriza ninguna afirmación sobre hit rate, ROI esperado ni ROI
  realizado (sección 16.5). Un modelo menos desfasado se acerca a una línea que ya
  incorpora la recencia.
- La muestra no es virgen (sección 2): un ACEPTA aquí es una evidencia algo más débil
  que sobre una muestra nueva.

## Señales de cautela (descriptivas; no cambian ningún veredicto ni ninguna regla)

1. **NFL, partición C casi nula.** Es justo la partición que fija h_C = 180 (la que se
   activaría):
   - Δ C = **−0,00132**, IC95 [−0,0185; +0,0205], que cruza el 0 holgadamente;
   - T − C en C = −0,0011.
   H2 solo exige el signo y se cumple. Pero la evidencia de la NFL reciente es débil.
   En el informe 3, cuatro de las catorce temporadas tienen Δ > 0: 2017 (+0,0133),
   2021 (+0,0093), 2023 (+0,0029) y 2024 (+0,0079). La fuerza del combinado viene de
   A y B (−0,022 y −0,019) y de 2020 (−0,081, la temporada sin público). La fase M de
   la NFL, con n ≈ 250–310, tendrá poca potencia (sección 9.3).
2. **NBA, h_C = 45 frente al vigente 180:**
   - es una cuarta parte del valor desplegado y más corto que el 60 de la WNBA;
   - el perfil de entrenamiento de C es plano entre 30 y 90 (4,38299 / 4,38231 /
     4,38251 / 4,38406);
   - 45 no está en el extremo de la rejilla (informe 1), pero el vecino inferior es 30;
   - en el informe 4 (descriptivo, test), 30 daría −0,01246 y 45 da −0,01199.
   El valor activable es h_C y no se reestima (sección 4). Que el óptimo de test esté
   en 30 no cambia nada.
3. **NHL, h_C = 180 prácticamente empatado con 120 en entrenamiento.** La pérdida de C
   es 2,2211928 frente a 2,2211937: una diferencia de 9·10⁻⁷. No es un empate exacto,
   y la regla elige el argmin literal. Solo importa para la fase M descriptiva de la
   NHL.
4. **NHL, el control C no captura el nivel que cambia con el tiempo.**
   - a_P sale ≈ 0 (−0,02 a +0,03 goles), porque en el entrenamiento el sesgo de la
     base era casi nulo;
   - en los tests B y C el sesgo μ − T de la base es −0,31 y −0,36 goles; con T queda
     en +0,06 y +0,09 (informe 2).
   Por eso T − C ≈ Δ H1 en la NHL. Es la limitación declarada en la sección 7.2: el
   nivel que cambia con el tiempo cuenta como recencia legítima de la liga. Gran parte
   de lo que gana h en la NHL es seguir el nivel de la era. Lo mismo, en menor medida,
   en NBA (sesgo en C: base −1,00 → T +0,04) y NFL.
5. **`total_sigma` (informe 2; no se reestima aquí, sección 16.4.4):**
   - NBA: la DE del residuo con T es 19,30 en el combinado y 19,95 en C, frente a
     σ = 22. El σ vigente queda ancho, también con la base (19,52);
   - NFL: 13,86 frente a 13,5, sin desajuste relevante.
   Si la NBA llega a activarse, la reestimación de σ es un paso aparte con su propia
   medición.
6. **Duplicados por (fecha, local, visitante)** del `--pre`, informe de ingesta
   (`game_id` distintos, 0 duplicados de `game_id`):
   - NBA: 1 en C;
   - NHL: 4 / 11 / 3 en A / B / C.
   Son irrelevantes frente a los n de test (≈ 0,1 % en la NHL) y la NHL rechaza de
   todos modos. La sección 12 solo citaba los 2 pares NBA de la batería, así que esto
   queda registrado.

## Discrepancias encontradas entre pre-registro, script y JSON

- **Ninguna que afecte al resultado.** Los criterios, la selección, el bootstrap, Holm,
  la paridad, la procedencia y los recuentos coinciden con el pre-registro y su
  Enmienda 1.
- **Horario** (sección 15, «lejos de las 12:00»): la fase H terminó a las 11:57.
  Desviación operativa sin efecto en el resultado (ver Procedencia).
- **Nombre de este informe.** La sección 14 y la Enmienda 1(e) lo llaman
  `AAAA-MM-DD-resultado-recencia-totales-H.md`. Se redactó como
  `2026-10-10-resultado-recencia-fase-H.md` y se renombró antes del commit al nombre
  del contrato. El script no lee el informe.
- **`H5: true` en NBA y NFL** significa «no aplica» (ver arriba). No es un defecto.

## Siguientes pasos (según el pre-registro)

1. **Antes de crear la instantánea M** (sección 15; Enmienda 1(e)), commitear:
   - este informe, con el SHA-256 de `H.json` (`32a0e9e3…5348b1ac`);
   - el SHA-256 de `pre_H_f315f4c.json`.
   `H.json` sigue en la instantánea, fuera del repositorio, y no se toca.
2. **Hasta D no se cambia nada de lo que fija el pre-registro.**
   - Si antes de D cambia cualquier parámetro resuelto de NBA, NFL o NHL, el
     `--fase M --pre` aborta. Por ejemplo, la recalibración pendiente del descanso NBA
     o de `margin_sigma` que recoge la memoria del proyecto (estado del 2026-09-26).
   - En ese caso hace falta una enmienda **antes de medir** que fije la base de M
     (Enmienda 1(f).5).
   - Si cambia el código del script, se aplica la Enmienda 1(e).
3. **Fase M en D = 2027-01-31,** dentro de los 7 días siguientes:
   1. crear la instantánea nueva `C:\dev\3\snapshots\recencia-totales-M-<AAAAMMDD>`
      (sección 6);
   2. `--fase M --pre --data-root <inst. M> --h-json H_f315f4c.json --h-sha256 32a0e9e3f3a216c9dfff41fc7f0d33be8df38954ea3e23f063d1cf205348b1ac --m-cutoff 2027-01-31 --out pre_M.json`;
   3. sin commits en medio, `--fase M`.
4. **Qué ligas entran en M:**
   - **NBA (h_C = 45) y NFL (h_C = 180): valor decisorio.** Mínimos NBA 800 y NFL
     250. Si no llegan en D, tienen **una única prórroga** a D' = 2027-04-20. Si
     tampoco llegan, quedan NO CONCLUYENTE y no se activan.
   - Criterios M1 (n) y M2 (Δ_M ≤ 0 en totales).
   - **NHL (h_C = 180): valor solo descriptivo** (sección 16.1; Enmienda 1(f).3). Se
     mide en D solo si alcanza n ≥ 800, **sin prórroga**. No puede revertir el
     RECHAZA.
5. **Si NBA o NFL no son vetadas en M:** candidatas a activación por la secuencia
   de la sección 16.4. Incluye:
   - addendum previo en `2026-09-25-repreregistro-gate-k52.md`;
   - «el modelo manda» ejecutado antes;
   - h_C en `configs/leagues/ratings.yaml` con su test;
   - `total_sigma` aparte;
   - revisión de Fable y commit antes de las 12:00.
6. **NHL:** `scoring_half_life_days` sigue en 0. Reabrir exige **otra hipótesis**, no
   otra rejilla ni otra lectura de H5 (sección 15). Por ejemplo, separar el nivel de
   la liga del de cada equipo con dos medias vidas, que es justo lo que sugiere la
   señal 4.

## Veredicto de esta revisión sobre la validez de la ejecución: **APTO**

La ejecución es única y conforme al contrato:

- HEAD, código, configuración, manifiesto, parámetros y tabla 9.1 coinciden entre el
  `--pre` y la fase H;
- las paridades 1-3 están dentro de 1e-12;
- los criterios están aplicados literalmente;
- los números son internamente coherentes, recalculados a mano.

La única desviación es operativa: el horario respecto a las 12:00, sin efecto en el
resultado. Los veredictos se mantienen: NBA ACEPTA, NFL ACEPTA, NHL RECHAZA (H5). No
se activa nada hasta la fase M.

---

Relacionado: [[2026-10-09-preregistro-recencia-totales]],
[[2026-10-09-resultado-bateria-ajustes]], [[2026-09-25-repreregistro-gate-k52]],
[[2026-08-26-preregistro-el-modelo-manda]], [[Bitácora/2026-08-18]].
