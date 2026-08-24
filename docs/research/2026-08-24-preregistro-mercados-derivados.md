# Pre-registro — edge del motor en mercados derivados (team_totals, F5)

**Fecha:** 2026-08-24. Escrito y commiteado **antes** de ejecutar cualquier
medición sobre datos, siguiendo la convención de los pre-registros de la regla de
salida (2026-08-16) y de momentum de línea (2026-08-15).

## Por qué

El objetivo del sistema es estimar probabilidades pregame **con el único fin de
ganar dinero** con las apuestas de sus picks. Cinco mediciones sobre el feed
público de líneas principales (`h2h`/`spreads`/`totals`) dan **cero ventaja**
(memoria `sin-ventaja-medida`), y la medición walk-forward de features del
2026-08-24 lo reconfirma: ningún feature pregame actual correlaciona con el
desenlace.

La hipótesis viva —bitácora 2026-08-18— es que la ventaja, si existe, no está en
las líneas principales sino en los **mercados derivados** que los libros precian
con una **fórmula** en lugar de con un modelo:

- **team_totals** (carreras del equipo local / visitante por separado).
- **F5 / first-5-innings** (`h2h_1st_5_innings`, `totals_1st_5_innings`).

Motivo mecánico: el motor MLB ya calcula la **distribución conjunta**
Poisson/NegBin por equipo (`lam_home`, `lam_away` con ajuste de pitcher abridor y
corrección de sobredispersión `dispersion_k`). Los derivados son **funciones
analíticas de esa misma distribución** que el motor ya produce:

- `team_totals` = cola de la marginal `score_pmf(lam_team, dispersion_k)`.
- `F5` aísla las ~5 primeras entradas, dominadas por el **abridor**, que es la
  señal más rica del motor (`fip.py`, `starters.py`) y la que el bullpen diluye en
  el juego completo.

## Restricciones de factibilidad (medidas antes de diseñar)

1. **El motor NO expone hoy estos mercados.** No hay clave de mercado F5 ni
   team_totals en `src/`. team_totals es derivable sin modelo nuevo (es la
   marginal ya calculada); F5 requiere una **lambda de 5 entradas** que no existe.
2. **No hay odds históricas** de F5/team_totals almacenadas. El sondeo del
   2026-08-18 (books=7–9) fue una consulta **en vivo** al API, no dato persistido.
   Sin odds históricas **no se puede medir edge/ROI realizado hacia atrás**.
3. **Desenlaces históricos:** los runs por equipo (`home_score`, `away_score`)
   SÍ están en `data/historical/results_mlb.csv` → team_totals es **calibrable
   walk-forward hoy, gratis**. Los runs por entrada (F5) **no** están → F5 exige
   backfill de line scores por entrada (statsapi), que consume cuota.

Estas restricciones imponen un diseño de **dos fases con gate duro**: nada de
cuota de API hasta que una condición necesaria, medible gratis, se cumpla.

## Fase 0 — condición necesaria: calibración de la marginal (GRATIS, sin API, sin tocar producción)

Un mercado derivado no puede tener edge real si la probabilidad que el motor le
asigna no es fiable. La única pieza medible sin odds es la **calibración de la
marginal por equipo** contra los runs realizados, walk-forward.

**Procedimiento (temporalmente correcto, sin lookahead):** para cada partido MLB,
ajustar el adaptador solo con partidos estrictamente anteriores, obtener
`lam_home`, `lam_away` vía el adaptador real, derivar `P(equipo Over L)` de
`score_pmf(lam, max_score, dispersion_k)` para una rejilla de líneas
`L ∈ {2.5, 3.5, 4.5, 5.5}` por equipo, y liquidar contra `home_score`/
`away_score`.

**Métricas y umbrales, fijados ANTES de correr:**

- **Sesgo** `= P̄(Over) − tasa observada de Over`, por línea. Aprobar si
  `|sesgo| ≤ 0.03` en cada línea con `n ≥ 300`.
- **ECE ≤ 0.05** agregado sobre las cuatro líneas.
- **Skill sobre base rate:** el Brier de `P(Over L)` derivada debe ser
  **≤** el Brier de un baseline de tasa-base (frecuencia histórica de Over L por
  liga, walk-forward). Si el motor no bate a la tasa base, su forma no aporta
  información y el derivado no puede tener edge propio.

**Regla de decisión de Fase 0:**

- **PASA** (los tres umbrales) → la marginal es fiable; se habilita solicitar
  aprobación para la Fase 1 de team_totals.
- **FALLA** → es una **miscalibración de la marginal a corregir**
  (candidatos: `dispersion_k` por línea, nivel de `avg_total`), **no** evidencia
  de edge de mercado. Se registra, se diagnostica, y **no se gasta ni un crédito**.

Fase 0 usa datos históricos pero **no reclama edge**; reclama calibración. Por
tanto no contamina el test de edge fuera de muestra de la Fase 1 (KI-019 intacto).

## Fase 1 — edge forward contra el libro (REQUIERE APROBACIÓN HUMANA + créditos de API)

Solo si la Fase 0 de team_totals PASA. Mide edge real, que exige odds del libro y
por tanto recolección forward.

- **Recolección:** odds de team_totals hacia adelante durante la ventana
  pre-registrada, hasta `n ≥ 300` selecciones graduadas por (equipo-lado). No-vig
  con el devig existente del proyecto. Liquidación por marcador (sin cuota extra).
- **Gate = la MISMA regla de salida ya decidida (2026-08-17), sin caso especial:**
  test de signo pareado de que el modelo **puro** bate al mercado fuera de muestra
  (`n ≥ 300` no empatadas, `p < 0.05`) **y** EV a stake plano `> 0`. El derivado
  entra al gate de predicción como un (liga, mercado) más.
- **Guardarraíles:** `shadow`/stake 0 durante toda la Fase 1; **cero capital
  real**; tope de créditos pre-registrado (`≤ 45 créditos/día`, `≤ 1.400/mes`,
  consistente con el presupuesto de 20.000 del 2026-08-18); F5 **excluido** hasta
  su propia sub-fase.
- **Fuera de muestra:** solo cuentan selecciones con `commence_time`
  estrictamente posterior a la fecha de este pre-registro.
- **CLV** con filtro de frescura (skill `clv-shadow-exit`) como evidencia
  secundaria, no rectora.

## Fase 2 (posterior, doblemente bloqueada) — F5

F5 requiere (a) un **modelo de lambda de 5 entradas** (no existe) y (b) **backfill
de line scores por entrada** para calibrar (consume cuota). Se pre-registra como
motivación pero **no se ejecuta** hasta que Fase 0/1 de team_totals cierre y exista
aprobación explícita para el backfill. Su lambda candidata: la contribución del
abridor prorrateada a 5 entradas, no `5/9 · lam` (el bullpen no entra en F5).

## Hipótesis registradas (para no re-litigar después)

- **H1:** la marginal por equipo (con `dispersion_k` de béisbol) **pasa** la
  Fase 0, porque la misma marginal ya calibra a nivel de total completo tras el
  arreglo de sobredispersión (2026-07-31). Predicción explícita: team_totals PASA.
- **H2:** el edge, si existe, es mayor en **F5** que en team_totals o juego
  completo, porque F5 aísla al abridor. Registrada como la hipótesis motivadora;
  su prueba está bloqueada por datos.
- **H3 (nula, la más probable dado "sin ventaja medida"):** el motor **tampoco**
  tiene edge en team_totals contra el libro → el gate de la Fase 1 queda vacío.
  Registrada de antemano para que un resultado nulo no se re-litigue.

## Criterios de descarte, fijados antes de ver los datos

- Sesgo de Fase 0 grande y unidireccional → **miscalibración a corregir**, no
  señal de mercado. No se avanza a Fase 1.
- **Comparaciones múltiples:** Fase 0 evalúa 4 líneas × 2 lados; Fase 1 hereda la
  postura Bonferroni del gate de predicción vigente.
- Rotura del tope de créditos → **auto-stop** de la Fase 1.
- Un derivado que pase el gate y luego lo pierda no reentra sin revisión humana
  (histéresis), igual que el gate de predicción.

## Lo que este experimento NO promete

Pasar la Fase 0 no es edge; es la condición mínima para que valga la pena gastar
créditos. Pasar la Fase 1 no es rentabilidad garantizada: el edge en derivados
puede evaporarse por line shopping, límites de cuenta y selección adversa, y F5
exige modelado aún no construido. No se promete beneficio en ninguna fase.
