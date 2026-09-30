# Resultado — `tilt_scale` de la NHL: ACEPTADO (7 de 7 criterios; el modelo deja de sobreafirmar, no sabe más)

**Fecha:** 2026-09-30. Ejecución única del pre-registro
`2026-09-29-preregistro-tilt-nhl.md`, con las decisiones del operador del
2026-09-30 (criterio 3 solo de signo, criterio 7 cuenta, activación antes del
~7 de octubre con nota previa) y la Enmienda 1 (recuentos y procedencia).
Script: `scripts/research/measure_tilt_nhl.py` (commit `8297295`), ejecutado con
HEAD `bf21fe4` y el árbol limpio (`git_status_porcelain` vacío en el `--pre`).
Entrada: `results_nhl.csv`, 32.907 filas, SHA-256 `6fe0acaf…550a`, el mismo hash que el
`--pre` regenerado justo antes (Enmienda 1). Duración del modo completo: 2.392 s.

La paridad con el motor pasó, con tolerancia 1e-12, en el brazo base y en el
tratamiento con `t_C`: moneyline, puck line ±1,5 y totales 5,5 y 6,5. La rejilla
canónica la verificó además en 0,0, 0,6 y 0,9. Si cualquiera hubiera fallado, el
script habría abortado antes de escribir el JSON. Nelder-Mead convergió en todos
los ajustes (T, P y T2 en las tres particiones). El log solo registra dos avisos
`emparejamiento AMBIGUO omitido` de `roi_engine` (VGK–ANA 2026-05-05, COL–MIN
2026-05-06), que afectan únicamente al informe 11. **Ningún informe tiene
`error`.**

Mecanismo medido: la pendiente `tilt_scale` con la que `PoissonAdapter._rates`
convierte la probabilidad Elo en reparto de goles. Hoy vale 0,9, el valor de la
familia hockey, que nunca se había ajustado para la NHL. `elo_k`, `elo_home_adv`
y `home_scoring_bonus` no se han tocado.

**Nota de recuentos.** En el modo completo, `n_train` vale 15.408 / 21.188 / 26.380.
En la sección 6 y en el `--pre` vale 15.827 / 21.607 / 26.799. La diferencia es 419
en las tres particiones: son los empates anteriores a 2005, que `binary_probs`
excluye del moneyline y el `--pre` no puede excluir porque no lee `y`. Todos caen
en entrenamiento. Los tests coinciden exactamente (5.780 / 5.192 / 5.978; 16.950 en
total).

## Veredicto: ACEPTA (se cumplen los siete criterios)

Números comprobados a mano contra el JSON, sin fiarme de los booleanos:

- la media de los Δ por partición, ponderada por partidos de test, reproduce el
  −0,019725 combinado;
- ll(T), ll(K) y ll(P) combinados son las medias ponderadas de las particiones
  (0,674206 / 0,689800 / 0,674143);
- ll(base) por partición es ll(T) − Δ: 0,69621 / 0,68754 / 0,69728. El combinado,
  0,69393, es el mismo que tenía la base en el resultado del descanso NHL
  (las filas nuevas son de septiembre de 2026, fuera de todo test).

| Criterio | Exigido | Obtenido | ¿Cumple? |
|---|---|---|---|
| 1. Δ log loss moneyline (T − base), test combinado | ≤ −0,002 | **−0,01973** (n = 16.950; IC95 por días [−0,02279; −0,01659], EE 0,00161; réplicas ≤ −0,002: 100 %) | Sí, **≈ 10 veces el margen** |
| 2. Δ < 0 en cada partición | A, B y C < 0 | A −0,01749 · B −0,01579 · C −0,02530 | Sí, las tres superan por sí solas el margen |
| 3. ll(T) < ll(K), combinado y cada partición (signo) | T < K | combinado 0,67421 frente a 0,68980 (T − K **−0,01559**; IC95 [−0,01843; −0,01276]; réplicas con T − K ≤ 0: 100 %) · A −0,00970 · B −0,01908 · C −0,01826 | Sí; pasaría también con el margen de 0,002 en el combinado y en cada partición |
| 4. ECE(T) ≤ ECE(base), combinado | ≤ 0,07231 | **0,01014** | Sí (−86 %) |
| 5. 0 < t < 0,9 en las tres particiones | los tres | A 0,4371 · B 0,4283 · C 0,4387 | Sí |
| 6. Puck line no empeora (media de −1,5 y +1,5 del local) | ≤ 0 | **−0,02241** (IC95 [−0,02508; −0,01969]) · A −0,02054 · B −0,01923 · C −0,02696 | Sí, mejora más que el moneyline |
| 7. t2 < 0,9 en las tres particiones (nivel controlado) | los tres | A 0,4182 · B 0,4102 · C 0,4243 | Sí |

El veredicto es correcto según las reglas pre-registradas. No es un «ACEPTA por
poco»: ningún criterio queda cerca de su frontera, y los intervalos del bootstrap
por días quedan lejos del margen en el criterio 1 y lejos de cero en los criterios
3 y 6.

## Motivos para desconfiar, uno por uno

**1. ¿Es estable `t`?** Sí, mucho. 0,437 / 0,428 / 0,439, un rango de 0,011, aunque
la desviación típica de `diff` en test crece de 74,8 a 94,7 Elo entre A y C (§2).
Los perfiles de log loss de entrenamiento (informe 3) son lisos y unimodales, con el
mínimo interior entre 0,40 y 0,50 en las tres particiones. El procedimiento canónico
del proyecto (`tuning.rolling_origin_improvement`, informe 4), con otros bloques y
limitado a la rejilla, elige **0,45 en los 4 bloques**, con una mejora OOS media de
0,0193. Dos procedimientos distintos llegan al mismo sitio.

**2. ¿Bate T de verdad a la constante, o solo aplana hacia ella?** La bate. Este es
el punto que el pre-registro señalaba como decisivo (§5.2), y la respuesta es
clara:

- La base es **peor** que la constante (0,69393 frente a 0,68980, +0,0041). T es
  **mejor** que la constante por 0,0156, con un IC95 que no se acerca a cero y en
  las tres particiones. Si el Elo no aportara nada, el óptimo habría caído cerca de
  0 y T habría empatado con K. Cayó en 0,44.
- **AUC** (informe 2): 0,60057 la base y 0,60053 T en el combinado, idénticas en
  cada partición (0,583 / 0,611 / 0,608). El tilt no cambia la ordenación, como
  anticipaba §1.4.3. La ganancia sobre K sale de una discriminación que ya existía
  (AUC 0,60) y que la pendiente de 0,9 estropeaba al exagerarla.
- **Fracción de la ganancia de Platt que captura T** (informe 10): **0,997**, con
  IC95 [0,967; 1,029]. Por partición: 0,966 / 1,034 / 0,999. T − P es +0,00006 en el
  combinado (IC95 [−0,00054; +0,00067]), y T gana a Platt en B. La forma de Poisson
  del tilt es, en la práctica, la mejor recalibración monótona de dos parámetros.
- **Pendiente de calibración** (informe 5): la base tiene 0,42 / 0,50 / 0,44
  (0,45 en el combinado), es decir, sobreafirma más del doble. T tiene 0,88 / 1,09 /
  0,93 (**0,97**). No hay tendencia sistemática entre particiones: el temor de §2 (un
  tilt de entrenamiento que aplana de menos en un test más disperso) se ve, como
  mucho, en el 0,93 de C, y es pequeño.
- **Coherencia con la potencia (§9.2).** Con t\* ≈ 0,44, la tabla sin resultados
  anticipaba una ganancia frente a 0,9 de ≈ 0,019 y una ventaja máxima sobre la
  constante de ≈ 0,017. Se observan 0,0197 y 0,0156. Es lo que se vería si el modelo
  con t ≈ 0,44 estuviera razonablemente bien especificado.

**3. ¿La mejora es de dispersión o de nivel?** De dispersión. T2 (tilt + nivel
analítico) da t2 0,418 / 0,410 / 0,424, apenas 0,015–0,02 por debajo de `t`, con
`a` = 20,6 / 20,2 / 16,3 Elo. Su log loss en test es prácticamente el de T: T2 − T =
−0,00064 / +0,00054 / −0,00001, y −0,00005 en el combinado. El nivel no aporta nada
fuera de muestra. El aplanamiento sobrevive intacto con el nivel controlado, que es
lo que exige el criterio 7.

**Pero sí queda un residuo de nivel, y hay que decirlo.** Como anticipaba §1.4.2,
aplanar también recorta la ventaja de campo que pasa por el tilt. T **infraestima al
local**: el sesgo es −0,0164 / −0,0059 / −0,0078 (−0,0101 en el combinado), frente a
−0,0017 / +0,0079 / +0,0052 (+0,0037) de la base. En la tabla de fiabilidad, la
frecuencia observada supera a la estimada en los seis bins ocupados. Por eso el ECE
de T (0,01014) coincide con su |sesgo| (0,01014): el error de calibración que le
queda es **nivel puro**, no forma. T2 y P se pasan al otro lado (+0,0086 y +0,0090).
El nivel óptimo fuera de muestra está entre los dos, y su valor en log loss es
minúsculo: corregir 1 pp cuesta ≈ δ²/(2p(1−p)) ≈ 0,0002, una décima parte del
margen. No justifica usar `t2`, que el pre-registro prohíbe (§13.2). Si algún día
se quiere corregir, es una hipótesis de nivel propia (`elo_home_adv` /
`home_scoring_bonus`) sobre la base nueva, y probablemente no llegaría al margen.

**4. ¿Empeora la puck line?** No, mejora más que el moneyline. −0,0225 en −1,5 y
−0,0223 en +1,5, negativas en las tres particiones. El ECE baja de 0,0744 a 0,0304
(−1,5) y de 0,0671 a 0,0153 (+1,5). El ECE residual de −1,5 (0,030) es el triple del
de +1,5. La causa probable es el mismo residuo de nivel, amplificado en la cola.

**5. Bootstrap.** Criterio 1: IC95 [−0,0228; −0,0166], EE 0,0016, 100 % de réplicas
por debajo de −0,002. T − K: [−0,0184; −0,0128], 100 % de réplicas por debajo de 0.
Puck line: [−0,0251; −0,0197]. T − P: [−0,0005; +0,0007], contiene el 0, como
corresponde a un techo que T alcanza.

**6. Por temporada (informe 7).** **Las 12 temporadas son negativas**, de −0,0101
(2021-22) a −0,0302 (2025-26). 2019-20 (burbuja) da −0,0219 y 2020-21 da −0,0116.
Las cuatro últimas están todas por debajo de −0,022 y crecen en magnitud (−0,0221 /
−0,0241 / −0,0264 / −0,0302), coherente con los ratings cada vez más dispersos de
§2: la pendiente de 0,9 es cada vez más dañina. No hay ninguna temporada en contra.

**7. Por quintil de |diff| (informe 6).** −0,0007 / −0,0029 / −0,0103 / −0,0283 /
−0,0565, del quintil más igualado al más desigual. Es monótono y se concentra en
los extremos, justo donde §1.4 predice que actúa el tilt. Es la huella del
mecanismo, no de un artefacto.

**8. Redondeo de `t_C` (informe 12).** `t_C` = 0,438655 → **0,439**. La diferencia de
log loss en el test de C entre el valor exacto y el redondeado es **+1,6·10⁻⁶**,
unas 1.000 veces menor que el margen. El redondeo es inocuo.

**9. Totales (informe 9).** Máx. |Δ P(over)| con `t_C`: 1,7·10⁻⁵ (5,5) y 2,3·10⁻⁵ (6,5),
lo que anticipaba §9.3. Una activación no mueve los totales ni el corte
`nhl|totals`.

**10. Lo más débil: la línea capturada del mercado (informe 11).** Sobre los 258
partidos del test de C con cuotas de cierre emparejadas (marzo–junio de 2026),
Δ h2h = **−0,0075**. Es negativo, pero es un tercio del −0,0253 de toda la partición C.
En la puck line **con la línea del mercado**, Δ = **+0,0037** (258 evaluados): **el
único número del informe que va en contra.** Con n = 258 en un único tramo de
temporada con playoffs, no decide y no contradice los 16.950 partidos del criterio
6. Pero es la muestra más parecida a producción, y queda como punto de vigilancia.
Además, el informe **no da el log loss del no-vig del consenso** que pedía §10.11
(solo da los Δ). Es una desviación menor de un informe secundario, y el efecto
práctico es que **la referencia frente al mercado no está medida**.

**11. Exposición previa.** El diagnóstico del orquestador ya decía que el óptimo
estaba por debajo de 0,9 (§3). Eso anticipaba la dirección, no la magnitud ni la
generalización. Los criterios estaban fijados antes, `t` se eligió solo con el
pasado de cada test, y las tres particiones y las 12 temporadas van en el mismo
sentido. La exposición no debilita este resultado.

## Qué significa y qué no

- Significa que el Elo NHL con la pendiente de familia (0,9) **exageraba su
  información más del doble** (pendiente de calibración 0,45) y que, con la pendiente
  estimada en el pasado (≈ 0,44), el modelo puro pasa de ser peor que la tasa del
  local (+0,0041) a batirla (−0,0156) de forma estable en 12 temporadas, con un ECE
  de 0,072 → 0,010. La probabilidad estimada NHL pasa de una dispersión típica de
  ≈ 0,175 a ≈ 0,09 (§9.1): deja de prometer un 75–84 % (bins 0,7–0,9 de la base)
  donde la frecuencia observada era del 64–70 %.
- **No** significa que el modelo sepa más: la AUC es la misma (0,60). Es una
  corrección de sobreconfianza, no una fuente de información nueva.
- **No** es una afirmación de rentabilidad ni de ventaja sobre el mercado. Siete
  mediciones previas no encontraron ventaja sobre el feed público, y aquí no se ha
  medido la comparación con el no-vig (punto 10). Un modelo mejor calibrado frente
  al resultado puede seguir siendo peor que el precio de cierre. Aquí no se han
  medido, ni se pueden inferir, la probabilidad implícita, el edge, el hit rate
  observado, el ROI esperado ni el ROI realizado de los picks NHL. Un edge declarado
  menor tras activar no es una pérdida de ventaja, sino menos error del modelo.
- **Efecto en el ranking por probabilidad:** con la mitad de la dispersión, las filas
  NHL bajarán en el ranking frente a otros deportes y habrá menos «favoritos
  fuertes» NHL. Es la consecuencia buscada (§12), no una caída de cobertura.

## Dictamen de activación

Se cumplen las condiciones del pre-registro (§13) y la decisión 3 del operador
(antes del ~7 de octubre, inicio de la temporada regular 2026-27, con nota previa).
Hoy es 30 de septiembre, así que hay margen. **Recomiendo activar**, en este orden y
sin saltarse pasos:

1. **Addenda previos**, commiteados **antes** del cambio de configuración:
   - `docs/research/2026-09-25-repreregistro-gate-k52.md`, «Addendum 2026-09-30 —
     `tilt_scale` NHL activado (antes de ejecutar)». Tiene que recoger: el commit y la
     fecha; que cambian las `d` de `nhl|h2h` y `nhl|spreads`, y no las de
     `nhl|totals` (Δ ≤ 2,4·10⁻⁵); que **K no cambia**; el estado actual (el registro de
     las 15:05Z del 30/09 evalúa **58 cortes**, dentro del techo de 63, con
     `nhl|h2h`, `nhl|spreads` y `nhl|totals` ya presentes, n = 5 cada uno,
     `muestra_insuficiente`, graduados con 0,9); que el test evalúa el sistema tal
     como operó, con los dos regímenes; y la prohibición de usarlo después para
     recortar o re-segmentar la ventana. No altera ningún criterio.
   - `docs/research/2026-08-26-preregistro-el-modelo-manda.md`, addendum análogo:
     `p_cal` NHL es hoy el modelo puro **sin calibrar**, así que el cambio mueve
     **todas** las filas h2h y de puck line NHL. Al activarlo antes del ~7 de octubre,
     toda la temporada regular de la ventana queda en un solo régimen. Las filas de
     pretemporada con 0,9 se declaran y no se excluyen a posteriori.
2. **Configuración:** en `configs/leagues/ratings.yaml`, entrada `nhl:` (hoy solo
   tiene `elo_home_adv: 15.0`), añadir **`tilt_scale: 0.439`** con un comentario que
   remita a este resultado y a su pre-registro. Es el `t` de la partición C
   (0,438655) redondeado a 3 decimales. **No** vale ni `t2`, ni la media de las
   particiones, ni una re-estimación con todo el histórico, ni 0,45 de la rejilla.
   `elo_k`, `elo_home_adv` y `home_scoring_bonus` no cambian. `FAMILY_PARAMS["hockey"]`
   sigue en 0,9 (ninguna otra liga real usa la familia hockey; solo el proveedor
   sintético).
3. **Test** (fichero nuevo, p. ej. `tests/test_nhl_tilt_activation.py`, con el patrón de
   `tests/test_nba_rest_activation.py`):
   - `_league_meta("nhl")["league_params"]["tilt_scale"] == 0.439` y
     `get_adapter("nhl", "hockey", params).params["tilt_scale"] == 0.439`, con
     `elo_home_adv == 15.0`;
   - `FAMILY_PARAMS["hockey"]["tilt_scale"] == 0.9` y
     `get_adapter("nhl", "hockey")` sin `league_params` sigue en 0,9 (de eso dependen
     `tests/test_team_scoring.py` y otros);
   - un caso conocido: con el mismo Elo, la probabilidad de un favorito baja frente a
     0,9 y P(over) no cambia más de 1e-4.
   - `measure_tilt_nhl.py` abortará en su `load_league` tras la activación
     (invariante `tilt_scale == 0.9`). **Es lo esperado**: el script es histórico y no
     se «arregla». Sus tests usan `monkeypatch` de `_league_meta` y no se ven
     afectados.
4. **Commit antes del run de las 12:00** (guarda KI-036), con `pytest -q`, `ruff` y
   `mypy` en verde.
5. **Calibradores:** hoy **no hay calibradores NHL** (§11), así que **no hay que
   recalibrar nada**. Rige la regla de un solo régimen: un calibrador NHL futuro se
   entrena solo con filas servidas con 0,439. Las filas de `served_nhl.csv` desde el
   2026-09-23 hasta la activación (con 0,9) no se mezclan, y un candidato NHL que
   apareciera en staging entrenado sobre 0,9 se descarta.
6. **Portero** (`docs/research/2026-09-26-preregistro-portero-nhl.md`): hace falta una
   **Enmienda 3 de base antes de su `--pre`**, que:
   - actualice la aserción de parámetros de la Enmienda 2(b) y la base de la §6
     (`tilt_scale 0.439` en lugar de 0,9);
   - rehaga la paridad del motor con ese valor;
   - calcule M1, M2 y su control sobre esa base;
   - **recalcule la potencia de su §10** (con un tilt más bajo, la misma variación de λ
     mueve menos `p`);
   - declare este resultado como exposición.

   Los criterios no cambian. El portero se mide sobre la base nueva, esté o no ya
   activada, por orden del 2026-09-29.
7. **Batería** (`docs/research/2026-09-27-preregistro-bateria-ajustes.md`): enmienda
   de la referencia de código y de la base NHL (`tilt_scale 0.439`) antes de su modo
   completo, y repetición de su `--pre` (§16 y §12 del tilt).
8. **Bitácora de la activación:** anotar el efecto en el ranking (sección anterior) y
   el sesgo residual de ≈ −1 pp al local, para que no se lea como un defecto nuevo.
9. **Vigilancia:** log loss NHL de la primera temporada activa y la puck line con
   línea de mercado (el único signo en contra, punto 10). Si empeora, se abre un
   pre-registro nuevo; no se ajusta el tilt a mano. Quedan como hipótesis abiertas,
   no como tareas de esta activación, la regresión del Elo a la media entre
   temporadas (§2 y §15: pendiente 0,93 en C, Δ creciente por temporada) y la
   corrección de nivel.

---

Relacionado: [[2026-09-29-preregistro-tilt-nhl]], [[2026-09-29-resultado-descanso-nhl]],
[[2026-09-26-resultado-descanso-basket]], [[2026-09-26-resultado-clima-mlb]],
[[2026-09-26-preregistro-portero-nhl]], [[2026-09-27-preregistro-bateria-ajustes]],
[[2026-09-25-repreregistro-gate-k52]], [[2026-08-26-preregistro-el-modelo-manda]].

FABLE-REVIEW: 2026-09-30 | veredicto: APTO CON CONDICIONES (ACEPTA verificado 7/7: Δ −0,0197 [IC −0,0228; −0,0166], T−K −0,0156 en las tres particiones, t 0,437/0,428/0,439 estable, AUC igual y 99,7 % de la ganancia de Platt; activar tilt_scale=0.439 solo en nhl de ratings.yaml tras los addenda previos en el gate K=52 y «el modelo manda», antes del ~7 de octubre; sin recalibración porque no hay calibradores NHL; enmienda de base del portero y de la batería; test de activación; vigilar el sesgo de −1 pp al local y la puck line con línea de mercado) | rutas: configs/leagues/ratings.yaml, docs/research/2026-09-30-resultado-tilt-nhl.md
