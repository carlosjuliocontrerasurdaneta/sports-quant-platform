# Resultado — descanso diferencial en la NHL: RECHAZADO (5 de 7 criterios; el efecto existe, pero queda por debajo del margen)

**Fecha:** 2026-09-29. Ejecución única del pre-registro
`2026-09-27-preregistro-descanso-nhl.md`, con las decisiones del operador del
2026-09-27 y la Enmienda 1 (recuentos y hash). Script:
`scripts/research/measure_rest_nhl.py` (commit `d349be7`). Entrada:
`results_nhl.csv`, 32.902 filas, SHA-256 `6163a66f…7a81`, el mismo hash que el
`--pre` ejecutado justo antes (Enmienda 1). Pasaron las tres paridades con el motor,
todas con tolerancia 1e-12: la del brazo base, la del tratamiento con el `c` de
prueba y la del tratamiento con `c_C` en el moneyline, la puck line ±1,5 y los totales
5,5 y 6,5. Si alguna hubiera fallado, el script habría abortado antes de escribir el JSON. Nelder-Mead
convergió en todos los ajustes. Si no, también habría abortado.

Mecanismo medido: `diff_eff = rating_diff + c · Δr` en el `PoissonAdapter`, con
`r` acotado a `[0, 4]` por `RestModel` y la clave `rest_elo_per_day` (puntos Elo
por día). `rest_days_coef` no se ha medido y sigue en 0.

## Veredicto: RECHAZA (fallan los criterios 1 y 3)

Números comprobados a mano contra el JSON, sin fiarme de los booleanos del
script:

- la media de los Δ por partición, ponderada por afectados (2.824 / 2.376 / 2.900), reproduce el
  −0,00130 combinado;
- la media de T − C por partición, ponderada por partidos, reproduce el −0,00071 del
  universo (0,69331 − 0,69402).

| Criterio | Exigido | Obtenido | ¿Cumple? |
|---|---|---|---|
| 1. Δ log loss moneyline (T − base) en afectados, test combinado | ≤ −0,002 | **−0,00130** (n = 8.100; IC95 por días [−0,00240; −0,00024], EE 0,00055) | **No**: le faltan 0,0007 |
| 2. Δ < 0 en los afectados de cada partición | A, B y C < 0 | A **−0,00021** · B −0,00151 · C −0,00217 | Sí (A casi nulo) |
| 3. ECE(T) ≤ ECE(base), todo el test combinado | ≤ 0,072312 | **0,072435** | **No**: sobra +0,00012 |
| 4. `c > 0` en las tres particiones | los tres > 0 | A 7,17 · B 6,40 · C 6,80 Elo/día | Sí |
| 5. ll(T) < ll(C), todo el test combinado | T < C | 0,69331 frente a 0,69402 (T − C −0,00071; IC95 [−0,00121; −0,00020]) | Sí, y en las tres particiones |
| 6. Puck line no empeora (media de −1,5 y +1,5 del local) | ≤ 0 | −0,00040 (IC95 [−0,00082; +0,00002]) | Sí |
| 7. `c_conj > 0` en las tres particiones | los tres > 0 | A 6,96 · B 6,24 · C 6,84 | Sí |

El veredicto es correcto según las reglas pre-registradas. **El criterio 1 lo
decide sin ambigüedad.** El IC95 del bootstrap contiene el −0,002, pero la
estimación puntual queda a 1,3 errores estándar del margen. La probabilidad de que el Δ
real supere el margen es 0,10 (fracción de réplicas ≤ −0,002). El criterio 3 falla
por muy poco (+0,00012 de ECE, dentro del ruido), pero es una condición de signo
pre-registrada y cuenta igual. Aunque no fallara, el criterio 1 bastaría para rechazar.

## Qué dice el resultado: hay efecto, pero por debajo del margen

No es un «no hay efecto». Casi todo lo que el pre-registro podía medir apunta
en la misma dirección:

**1. `c` es estable y el intercepto no lo explica.** Los valores de `c` son
7,17 / 6,40 / 6,80, y los de `c_conj` son 6,96 / 6,24 / 6,84: la diferencia entre
ambos es de 0,2 Elo/día o menos. Con el intercepto dentro, `a_conj` queda en 1,43 / 1,00 /
−0,29 Elo, que es casi nada. Al revés que en la NBA, el confusor de la ventaja de
campo que el pre-registro temía (§5, `elo_home_adv 15`) **no aparece**. El sesgo
de la base es pequeño y **positivo**: sobreestima al local en +0,0037 en el
combinado (A −0,0017, B +0,0079, C +0,0052). Los perfiles de log loss de
entrenamiento son monótonos a los dos lados del mínimo, y el mínimo cae en la
rejilla hacia 7,5 en las tres particiones.

**2. El descanso bate al control, y en las tres particiones.** T − C es −0,00013 /
−0,00090 / −0,00111. En la NBA, el control ganaba en A. Aquí hay que matizar una cosa:
el control `a` (2,64 / 2,10 / 0,87) **empeora a la base** en test. ll(C) es 0,69402
frente a los 0,69393 de la base, porque empuja al local en un periodo en que la base ya lo
sobreestima. Parte de la victoria del criterio 5 se debe, por tanto, a que el comparador es malo. La estimación
conjunta (punto 1) es la prueba más limpia, y confirma la señal.

**3. La magnitud es la que el pre-registro anticipó como insuficiente.** Con
dP/dElo ≈ 0,0022–0,0024 (§9), `c` ≈ 6,4–7,2 Elo/día equivale a **≈ 1,4–1,7 pp de
probabilidad por día** de diferencia de descanso. §9 calculó que hacían falta
≈ 9–10 Elo/día (≈ 2,2 pp) para llegar a −0,002, y avisó: «es probable que no
llegue al margen». La cuenta cuadra: con δ_RMS ≈ 6,8 · 1,50 · 0,0024 ≈ 2,4 pp, la ganancia
esperada 2δ² vale ≈ 0,0012, frente al −0,0013 observado. El residuo medio de la base
en test (y − p_base) crece con Δr: −0,076 / −0,036 / −0,026 / −0,007 / +0,015 /
+0,038 / +0,009 para Δr = −3…+3. Entre −2 y +2, la pendiente es ≈ 0,018 por día
(≈ 7,6 Elo/día), coherente con `c`. El +3 rompe la monotonía, pero es la celda más
pequeña.

**4. ¿Una época?** En parte. A es casi nula en afectados (−0,0002). B (−0,0015) y
C (−0,0022) son claramente negativas, y C por sí sola supera el margen. Por temporada
(Δ sobre el universo), 8 de 12 son negativas. **Las seis últimas lo son todas**
(2020-21 a 2025-26: −0,0004 / −0,0019 / −0,0006 / −0,0018 / −0,0012 / −0,0007). Las positivas
son 2015-16 (+0,0005), 2016-17 (+0,0006), 2018-19 (+0,0004) y la burbuja de 2019-20 (+0,0002).
El efecto parece mayor en el periodo reciente. Aun así, el criterio es el combinado, y
elegir la partición buena a posteriori no está permitido.

**5. El efecto vive en el back-to-back, no en la escala lineal.** Es el hallazgo
secundario más importante:

| Back-to-back | n | Δ log loss (universo) |
|---|---:|---:|
| ninguno | 11.535 | **+0,00012** |
| solo el local | 1.098 | −0,00269 |
| solo el visitante | 2.676 | −0,00333 |
| los dos (Δr = 0) | 1.629 | 0 |

Cuando ninguno de los dos juega un back-to-back (es decir, 2 frente a 3 o 4 días), el término lineal no aporta
nada, e incluso empeora un poco. Toda la ganancia está en los partidos con un solo equipo en back-to-back.
Por |Δr| el patrón no es de dosis: −0,0008 / −0,0029 / −0,0004 para 1 / 2 / 3.
Por signo, el efecto es mayor cuando descansa más el visitante (−0,0019) que cuando descansa más el local (−0,0009). Es lo
esperable con un sesgo de base positivo: con Δr < 0, el ajuste corrige a la vez el descanso y
la sobreestimación del local. En la NBA pasaba lo contrario porque su sesgo tenía el signo opuesto.

**6. Robustez.**
- Sin exhibiciones (45 equipos con ≤ 11 apariciones; 8.094 afectados): −0,00131.
- Sin los 744 pares equipo-fecha dobles del mismo día UTC (7.719 afectados): −0,00130.
- El ruido UTC de §3.1 atenúa `c`. Quitar esos partidos no cambia nada.
- Solo 6 afectados tenían el tilt recortado de partida: la dilución es despreciable.

**7. Totales.** El máximo de |Δp_over| con `c_C` es 2,7·10⁻⁶ (5,5) y 3,6·10⁻⁶ (6,5), del
orden que anticipaba §10.7. Queda confirmado que el mecanismo no mueve los totales.

**8. Porteros (solo identidades, informe 11).** Con r = 1, el titular cambia respecto
al del partido anterior del equipo en el **60,8 %** de los casos (6.925 de 11.392). Con
r ≥ 2, en el 38,0 % (16.301 de 42.915). Una parte grande del back-to-back es cambio de portero. El
script lo da agregado, no por partición y lado como pedía §10.11. Es una
desviación menor de un informe que no decide.

**Contexto de la base, que no es objeto de este pre-registro.** El moneyline del modelo puro
de la NHL sin calibrar tiene en el test combinado un log loss de 0,69393, por
encima de ln 2 (0,69315), y un ECE de 0,072. Es una base débil y sobreconfiada, que en
producción corrige el calibrador `nhl_h2h`. El descanso se ha medido sobre ella, como
estaba pre-registrado. La calidad de la base NHL merece su propio diagnóstico.

## Comparación con la NBA (`2026-09-26-resultado-descanso-basket.md`)

| | NBA (ACEPTA) | NHL (RECHAZA) |
|---|---|---|
| `c` sin control | 0,81 / 0,88 / 0,80 puntos/día (≈ 2,5 pp/día) | 7,17 / 6,40 / 6,80 Elo/día (≈ 1,4–1,7 pp/día) |
| `c` conjunto | 0,51 / 0,61 / 0,60 (baja ≈ 30 %) | 6,96 / 6,24 / 6,84 (**no baja**) |
| Sesgo de la base | −0,034 / −0,009 / −0,002 (infraestima al local) | −0,002 / +0,008 / +0,005 (lo sobreestima un poco) |
| Δ en afectados | −0,00224 (pasa por 0,00024) | −0,00130 (le faltan 0,0007) |
| T − C | gana en el combinado, pierde en A | gana en las tres |
| Por dosis | crece con \|Δr\| | concentrado en el back-to-back |

En la NHL, el efecto por día es ≈ 60 % del de la NBA en probabilidad, lo que encaja
con que el hockey tenga más azar por partido. Visto con el intercepto controlado, es incluso más limpio que el de la NBA.
No llega al margen porque es pequeño, no porque sea dudoso.

## El fallo del informe secundario `linea_capturada`

`TypeError: only 0-dimensional arrays can be converted to Python scalars`. La causa
se puede demostrar leyendo el código. En `_informe_linea_capturada`
(`measure_rest_nhl.py:900-907`), `_lambda_split(np.array([d]), …)` devuelve
arrays de forma (1,), que se pasan desempaquetados a `dist.poisson_match_probs`, cuyo argumento
son escalares. La ruta de paridad hace bien la misma llamada con
`float(lam_h[0])` (línea 441). Falta el `[0]`.

**No invalida nada**, por tres motivos:
- el informe es el 10 de §10 («no deciden»);
- se ejecuta **después** de calcular los siete criterios y el veredicto;
- se ejecuta también después de la paridad de mercados con `c_C` (línea 934), que
  pasó.

No toca ningún número de la tabla del veredicto. La regla E10 solo permite repetir la
ejecución por un defecto que afecte al veredicto, así que **no se repite**. Queda anotado
como defecto a corregir en el script, con un test de humo del informe, antes de reutilizarlo
para MLB. En este resultado, la línea capturada del mercado NHL **no está
medida**. En la NBA, esa muestra era de todos modos mínima (≈ 228 partidos) y no medía ventaja
sobre el mercado.

## Qué significa y qué no

- Significa que, **en el histórico**, el descanso diferencial contiene información que
  el Elo de la NHL no recoge: ≈ 7 puntos Elo (≈ 1,5 pp) por día. Esa información es estable
  en las tres ventanas y no se debe a la ventaja de campo. Pero la mejora de la
  probabilidad del modelo puro (−0,0013 en afectados, −0,0006 en todo el universo) no alcanza
  el margen pre-registrado `IMPROVEMENT_MARGIN` = 0,002, y la calibración (ECE)
  no mejora.
- **No** significa que el descanso no exista en la NHL, que es justo la lectura que §9 pedía
  evitar.
- **No** es una afirmación de rentabilidad ni de ventaja sobre el mercado. Las casas
  ya incorporan el back-to-back. Con `market_shrink = 0,5`, la probabilidad servida
  recibiría como mucho la mitad del ajuste. Siete mediciones previas no encontraron ventaja
  sobre el feed público. Aquí no se han medido, ni se pueden inferir, la probabilidad implícita,
  el edge, el hit rate observado, el ROI esperado ni el ROI realizado de los picks NHL.

## Consecuencias

1. **`rest_elo_per_day` sigue en 0** para la NHL (y para MLB y fútbol, que heredan el
   mecanismo inerte). No se activa `c_C` = 6,80: el rechazo lo prohíbe, y usar
   `c_conj` o re-estimar con todo el histórico serían valores no pre-registrados.
   `rest_days_coef` sigue en 0. No hacen falta addenda en el gate K = 52 ni en «el modelo
   manda», porque no cambia ningún régimen. Tampoco hace falta la recalibración de §13.5.
2. **Orden con el portero (decisión del operador: primero el descanso, con anidamiento).** El
   descanso fue rechazado, así que **la base del portero es la configuración actual de
   producción** (sin `rest_elo_per_day`), sin enmienda de base. Lo que sí debe
   declarar su enmienda previa al modo completo es la **exposición** que crea este resultado:
   - el informe 5 (el efecto está en el back-to-back);
   - el informe 11 (con r = 1, el titular cambia en el 61 % de los casos, frente al 38 %).

   Esta exposición no permite al portero ajustar nada, porque sus criterios están fijados. Hay que
   esperar que M1 recoja parte de esta señal de back-to-back a través del cambio de
   titular. La batería de ajustes tampoco cambia su base NHL (§12).
3. **Reabrir el descanso en la NHL** exige, según §14, una forma distinta y pre-registrada.
   El informe 5 señala una candidata natural: un **indicador de back-to-back**. Pero ese
   diseño ya estaría informado por este resultado. Si se hace, conviene que:
   - declare esta exposición;
   - vaya **después** del portero y anidado sobre él si el portero acepta, porque el
     back-to-back y el cambio de portero comparten señal;
   - se valide de forma prospectiva, o con una partición que este resultado no favorezca.

   Tampoco se descarta, sin pre-registro, ajustar `c` a mano ni cambiar el tope.
4. **MLB (pendiente en la cola).** No hereda nada, y el mecanismo sigue inerte. Una
   medición en MLB tiene sentido como pre-registro propio, pero con expectativas bajas.
   Los equipos juegan casi a diario, el descanso diferencial es casi siempre 0 o ±1 día
   (días libres), y el cansancio relevante está sobre todo en el abridor y el bullpen, que el
   modelo ya trata por otros canales. Antes de redactarlo, conviene hacer el cálculo de potencia con el
   calendario, sin marcadores, como en el §9 de este documento. Si el RMS de Δr en los
   afectados queda muy por debajo de 1,5, el margen de 0,002 exigiría un efecto por
   día mayor que el de la NHL, y la medición nacería casi sin posibilidades. También conviene corregir antes el
   defecto de `linea_capturada` si se reutiliza el script.

---

Relacionado: [[2026-09-27-preregistro-descanso-nhl]],
[[2026-09-26-resultado-descanso-basket]], [[2026-09-26-preregistro-portero-nhl]],
[[2026-09-27-preregistro-bateria-ajustes]], [[2026-09-25-repreregistro-gate-k52]],
[[2026-08-26-preregistro-el-modelo-manda]].

FABLE-REVIEW: 2026-09-29 | veredicto: APTO (RECHAZA verificado: falla C1 Δ afectados −0,00130 > −0,002 y C3 ECE +0,00012; c≈6,4–7,2 Elo/día estable y c_conj≈igual, efecto real bajo el margen y concentrado en back-to-back; rest_elo_per_day sigue en 0; portero sobre la base actual con exposición declarada; linea_capturada es defecto secundario sin re-ejecución) | rutas: docs/research/2026-09-29-resultado-descanso-nhl.md
