# Resultado — descanso diferencial en la NBA: ACEPTADO (5 de 5 criterios, por poco en el 1)

**Fecha:** 2026-09-26. Ejecución única del pre-registro
`2026-09-26-preregistro-descanso-basket.md`, con sus enmiendas E1–E6, el
contraste de `--pre` y la nota de re-ejecución. Script:
`scripts/research/measure_rest_basketball.py` (commit `fa8448d`). Es la segunda
ejecución del modo completo. La primera abortó en la aserción de paridad de los
spreads antes de producir ningún resultado, por un defecto de código documentado
en el pre-registro (el empate de la fila 346). Las paridades de la sección 5
(moneyline y spreads con `c_C`, tolerancia 1e-12) pasan: si no, el script habría
abortado. Hashes de entrada: `results_nba.csv` 34.065 filas, SHA-256
`6b2b0e04…62cf`. WNBA, NCAAB y WNCAAB, con los suyos, están en el JSON.

Mecanismo medido: (a) `RestModel`, `μ += c · (r_home − r_away)`, con `r` acotado
a `[0, 4]`. `rest_days_coef` no se ha medido y sigue en 0.

## Veredicto: ACEPTA (5 de 5 criterios)

Números comprobados a mano contra el JSON, sin fiarse de los booleanos del
script. La media ponderada de los tres Δ por partición reproduce el −0,00224
combinado, y la de T − C por partición reproduce el −0,00197 del universo.

| Criterio | Exigido | Obtenido | ¿Cumple? |
|---|---|---|---|
| 1. Δ log loss (T − base) en afectados, test combinado (sección 14: solo afectados) | ≤ −0,002 | **−0,00224** (n = 9.109; IC95 por días [−0,00371; −0,00076], EE 0,00075) | Sí, por 0,00024 |
| 2. Δ < 0 en los afectados de cada partición | A, B y C < 0 | A −0,00393 · B **−0,00026** · C −0,00243 | Sí (B casi nulo) |
| 3. ECE del universo no empeora | ECE(T) ≤ 0,01782 | 0,01647 | Sí |
| 4. `c > 0` en las tres particiones | los tres > 0 | A 0,813 · B 0,876 · C 0,795 | Sí |
| 5. T bate al control de intercepto (universo combinado) | ll(T) < ll(C) | 0,62313 frente a 0,62509 (T − C −0,00197; IC95 [−0,00339; −0,00053]) | Sí (pero no en A) |

El veredicto es correcto según las reglas pre-registradas. **No es una certeza.**
La estimación puntual del criterio 1 supera el margen por un tercio de error
estándar. Con una aproximación normal al bootstrap, la probabilidad de que el Δ
real sea ≤ −0,002 ronda el 60 %. Lo que el intervalo sí respalda con holgura es
otra cosa: que el efecto es **negativo** (el IC95 entero por debajo de 0) y que
el descanso bate al intercepto (el IC95 de T − C entero por debajo de 0).

## Motivos para desconfiar, y lo que dicen los datos

**1. Estabilidad y magnitud de `c`.** `c` = 0,81 / 0,88 / 0,80: estable entre
las tres ventanas de entrenamiento. Es justo el rango que la sección 9 estimaba
necesario (≳ 0,7–0,8 puntos por día), y por eso el criterio 1 pasa por poco. Los
perfiles de log loss de entrenamiento son monótonos a los dos lados del mínimo
en las tres particiones: no se repite la no-monotonía del rechazo de junio. En
magnitud es plausible: un back-to-back frente a dos días de descanso vale ≈ 0,8
puntos, y frente a tres días ≈ 1,6. El ruido UTC de la sección 4 (back-to-backs
que aparecen como `r = 2`) atenúa `c`, así que no lo infla.

**2. Confusión con la ventaja de campo: existe y es parcial.** Es la advertencia
principal.
- El sesgo de la base (probabilidad media − tasa observada del local) cambia
  mucho entre épocas: A −0,034, B −0,009, C −0,002. El Elo usa una ventaja de
  campo fija (`elo_home_adv 70`), y la ventaja real de la NBA ha bajado. El modelo
  infraestimaba al local en 2012-17 y hoy casi no lo hace.
- El control `a` baja en paralelo: 1,80 → 1,62 → 1,32 puntos.
- En la **estimación conjunta** (μ_base + a + c·Δr), `c` baja a **0,51 / 0,61 /
  0,60**. Una parte del `c` de ≈ 0,8 (≈ 0,2–0,3 puntos por día) viene del sesgo
  de nivel: Δr tiene media positiva. Lo que queda con el intercepto controlado
  es positivo y estable, y eso es la señal de descanso.
- Refuerza la misma lectura el Δ por signo de Δr: −0,0037 cuando el local está
  más descansado y solo −0,0001 cuando lo está el visitante. Con Δr > 0, `c`
  corrige a la vez el descanso y el sesgo. Con Δr < 0, corrige el descanso pero
  empuja contra el sesgo.
- Aun así, el residuo medio (y − p_base) en test crece de forma monótona con Δr:
  −0,054 / −0,035 / −0,004 / **+0,014** / +0,035 / +0,054 / +0,057 para Δr = −3…+3.
  Es una pendiente de ≈ 0,018 por día en probabilidad (≈ 0,6 puntos por día con
  dp/dμ ≈ 0,031), alrededor de un desplazamiento de +0,014 en Δr = 0. Pendiente e
  intercepto se ven separados. La señal de descanso no es un artefacto de la
  ventaja de campo, aunque el `c` sin control la sobreestima algo.

**3. El control queda batido en el combinado, pero no en A.** En A, T − C =
+0,00024: el intercepto gana, porque ese es el periodo con más sesgo de nivel
(−0,034). En B (−0,0028) y C (−0,0038) gana el descanso. Aquí se mezcla la
deriva de la ventaja de campo: `a` se estima en entrenamientos con más sesgo que
el test, así que el control se pasa en B y C. Una parte de la victoria de T en
el criterio 5 viene de que el control es un comparador que envejece mal. La
estimación conjunta (punto 2) confirma de todos modos que el descanso aporta
por encima del intercepto dentro de cada entrenamiento. El criterio 5 se
pre-registró sobre el combinado y se cumple. Se deja constancia de A.

**4. ¿Una sola época?** No. A (−0,0039) y C (−0,0024) superan el margen por sí
solas. B es casi nula (−0,00026). B incluye la burbuja de 2019-20 (+0,0016) y el
calendario comprimido de 2020-21 (+0,0014), además de 2017-18 (+0,0014), la
primera temporada con el calendario de la NBA rediseñado para reducir los
back-to-backs. Por temporada, **10 de 14 son negativas**. De las 4 positivas,
dos son de régimen atípico. La otra que preocupa es **2025-26 (+0,0006)**, la
más reciente, aunque es una sola temporada con ruido del orden de 0,001–0,002.

**5. Por |Δr|.** −0,0011 / −0,0049 / −0,0064 para |Δr| = 1 / 2 / 3. Crece con la
dosis, como debe hacer un efecto real y no un sesgo constante.

## Informes secundarios (no deciden)

- **Sin exhibiciones** (64 equipos con ≤ 25 apariciones fuera; 9.065 afectados):
  Δ −0,00239. No depende de los clubes de exhibición.
- **Spreads con líneas fijas** (E2: +1,5 / −1,5 / −5,5 del local): 8 de 9 celdas
  negativas. La excepción es B con +1,5 (+0,00008). Coherente, pero no es una
  prueba independiente: el spread mueve el mismo μ.
- **Línea capturada del mercado** (`c_C`, n = 228 h2h y 225 spreads, marzo–junio
  de 2026): Δ h2h −0,0034 y spread −0,0057. Mismo signo, pero la muestra es
  mínima. Además, esto mide el log loss del modelo frente al resultado en esa
  submuestra, **no ventaja sobre el mercado**.
- **WNBA** (particiones propias): `c` 0,69 (A) y 0,35 (B), los dos positivos. Δ en
  afectados +0,0021 (IC95 [−0,0066; +0,0114]) y −0,0014 (IC95 [−0,0055;
  +0,0028]). Sin potencia, como preveía la sección 9. Ni contradice ni confirma.
- **Transferencia de `c_C` = 0,795 sin reajustar:** WNBA 2025-26 +0,00045 en
  afectados (365), NCAAB −0,00083 (1.857), WNCAAB **+0,0031** (1.886). No hay
  base para extender el factor a otras ligas: en WNCAAB empeora.

## Cobertura

- NBA: 34.065 filas, 34.004 tras quitar el empate de la vista del moneyline (el
  empate sí entra en los spreads). Contraste de `--pre` con la sección 9:
  coincide exactamente en las tres particiones.
- Test combinado: 19.332 partidos, 9.109 afectados, 2.410 días con afectados y
  3.205 días de test en el bootstrap.
- Entrenamiento: A 14.672 · B 21.806 · C 28.427.
- WNBA 1.100 partidos (tests 327 + 350). NCAAB 6.271 (1.857 afectados) y WNCAAB
  6.065 (1.886), solo en transferencia.

## Qué significa y qué no

- Significa que, **en el histórico**, sumar al margen esperado 0,8 puntos por día
  de diferencia de descanso mejora la calidad de la probabilidad del modelo puro
  de la NBA frente al resultado. La mejora es pequeña: −0,0011 de log loss en
  todo el universo y −0,0022 en los afectados.
- **No** es una afirmación de rentabilidad ni de ventaja sobre el mercado. Las
  casas ya incorporan el descanso en sus líneas. Con `market_shrink = 0,5`, la
  probabilidad servida recibe como mucho la mitad del ajuste. Siete mediciones
  previas no encontraron ventaja sobre el feed público. El hit rate, el ROI
  esperado y el ROI realizado de los picks de la NBA no se han medido aquí y no
  se pueden inferir de este resultado.

## Consecuencias y dictamen de activación (sección 11; decisión del operador en la sección 14.3)

El operador ya decidió que un ACEPTA se activa **con nota previa**. Dictamen:
**APTO para activar**, con estas condiciones y en este orden:

1. **Antes de tocar la configuración:** addendum de cambio de régimen en
   `2026-09-25-repreregistro-gate-k52.md` y en
   `2026-08-26-preregistro-el-modelo-manda.md`. Cada uno lleva la fecha del
   cambio, no altera los criterios y prohíbe usar el cambio después para
   recortar la ventana, como con el abridor MLB. Hoy el gate no tiene cortes de
   `nba`, y la temporada empieza a finales de octubre: el momento es favorable.
2. **Valor y sitio:** `rest_points_per_day: 0.795` (es `c_C` = 0,79500586, el de
   la partición C, redondeado a milésimas; la diferencia no tiene efecto medible)
   **solo para `nba`**. Va en `configs/leagues/ratings.yaml`, en una entrada nueva
   `nba:` bajo `leagues:` (hoy no existe), con un comentario que remita a este
   documento. `_league_meta` la fusiona en `league_params`, y `BasketballAdapter`
   la lee (`adapters.py:40`). `rest_max_days` sigue en 4 (el valor por defecto):
   no se escribe otro. **No** se re-estima con todo el histórico ni se usa el `c`
   conjunto (≈ 0,60): cualquiera de los dos sería un valor no pre-registrado. Hay
   que saber que el 0,795 incluye ≈ 0,1 puntos de desplazamiento medio a favor del
   local en la época actual (media de Δr 0,12 en C). Es pequeño, y los
   calibradores lo absorberán.
3. **`rest_days_coef` sigue en 0** (`configs/default.yaml:43`), para no contar el
   descanso dos veces.
4. **WNBA, NCAAB y WNCAAB no se activan:** cada una necesita su propio
   pre-registro (sección 14.2). La transferencia no lo justifica.
5. **Paridad entre entrenamiento y servicio**, verificada y no supuesta: que
   `event.start_time` llega en UTC a `estimate`, y que el run diario tiene el
   resultado de ayer al generar (orden `SETTLE_ALL` → `RUN_DIARIO_ALL`). Si falta
   ese resultado, un back-to-back se ve como descanso largo y el ajuste se invierte.
   Hace falta un test con un back-to-back conocido.
6. **Volver a medir `margin_sigma` de la NBA** (13,0; el comentario de
   `registry.py` ya cuenta el descanso en el residual).
7. **Recalibrar en staging** (`controlled-recalibration`) `nba_h2h` y
   `nba_spreads`, entrenados sin descanso. La promoción necesita aprobación
   humana.
8. **Vigilancia:** 2025-26 salió positiva (+0,0006). Si la primera temporada con
   el factor activo empeora el log loss, es motivo para revisarlo con un
   pre-registro nuevo, no para ajustar `c` a mano.

Reabrir la forma funcional (indicadores de back-to-back, viajes, tope distinto)
exige un pre-registro nuevo. Este resultado no autoriza a buscar el tope ni a
ajustar `c` a posteriori.

---

Relacionado: [[2026-09-26-preregistro-descanso-basket]],
[[2026-09-26-resultado-clima-mlb]], [[2026-09-25-repreregistro-gate-k52]],
[[2026-08-26-preregistro-el-modelo-manda]].

FABLE-REVIEW: 2026-09-26 | veredicto: APTO CON CONDICIONES (activar rest_points_per_day=0.795 solo nba, tras los addenda previos en gate K=52 y «el modelo manda»; rest_days_coef en 0; recalibrar nba_h2h/nba_spreads; re-medir margin_sigma; test de back-to-back) | rutas: configs/leagues/ratings.yaml, docs/research/2026-09-26-resultado-descanso-basket.md
