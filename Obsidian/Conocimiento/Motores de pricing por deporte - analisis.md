---
tags: [conocimiento, modelo, prompts, multideporte, sqp]
creada: 2026-08-15
actualizada: 2026-08-15
---

# Motores de pricing por deporte — análisis de la familia v1

Cinco motores hermanos de [[Prompt 191 - origen del modelo]]. Los archivos fuente
están versionados en `docs/prompts/` (antes vivían fuera del repo, en
`C:\dev\4`, sin historial ni respaldo):

| Archivo | Deportes | Distribución |
|---|---|---|
| `prompt-basket-pricing-v1.md` | NBA, WNBA, NCAAB, WNCAAB | Normal bivariante |
| `prompt-football-pricing-v1.md` | NFL, NCAAF | Normal + números clave |
| `prompt-nhl-pricing-v1.md` | NHL | Poisson bivariante + OT/EN |
| `prompt-soccer-pricing-v1.md` | 12 competiciones | Matriz Poisson + Dixon-Coles |
| `prompt-tenis-pricing-v1.md` | ATP, WTA | Elo / Markov jerárquico |

Comparten esqueleto y difieren en el cuerpo. Cubren exactamente los verticales
que ya existen en `src/sqp/sports/`.

## Lo que la familia añade sobre MLB v2

Estos cinco son **posteriores a MLB v1 y anteriores a MLB v2**, y contienen cinco
mecanismos que MLB v2 **no tiene**:

1. **Fase 0 — motor de cálculo declarado.** Obliga a decir si se ejecutó código
   real o se usó la vía analítica, y prohíbe afirmar simulaciones no ejecutadas.
   *"Mentir sobre el motor invalida la salida."*
2. **Regla 8 — ANTI DOBLE CONTEO, explícita y por deporte.** Es el defecto que
   la revisión de MLB detectó por análisis; aquí está escrito como regla dura.
3. **Bandera de outlier.** `|edge| > 6%` (NFL), `> 7%` (NBA/NHL), `> 8%` (tenis)
   → *"revisar inputs: posible error"*, sin ajustar el modelo. **Es una defensa
   contra la selección adversa que MLB v2 no tiene.**
4. **Fase de SANITY CHECKS obligatoria antes de imprimir.** Coherencias internas
   verificables (ver abajo). MLB no tiene nada equivalente.
5. **Dos modos de trazabilidad** (auditoría ≤3 partidos / resumen), práctico para
   carteleras grandes.

## Lo que la familia NO tiene y MLB v2 sí

Seis correcciones de MLB v2 que faltan en los cinco:

1. **`EV_por_unidad` como variable de decisión.** Ninguno de los cinco lo calcula:
   todos rankean por edge en pp. **Es la carencia más consecuente**: 4 pp a cuota
   1.10 y 4 pp a cuota 3.00 no valen lo mismo ni de lejos.
2. **`Score = 0.65×EDGE_abs + 0.20×Conf + 0.15×MarketConf`** — el bug de unidades,
   **idéntico en los cinco**. Con `EDGE_abs` como proporción, el edge aporta ~7%
   del score y el ranking ordena por confianza. MLB v2 lo resolvió con orden
   lexicográfico.
3. **`EDGE_modelo = |p − 0.50|`** sigue tratándose como rankeable. MLB v2 lo
   renombró "convicción del modelo" y lo sacó del ranking. (Fútbol es el más
   cuidadoso: usa `p_ref = 1/3` en mercados a 3 vías. Sigue sin ser un edge.)
4. **"probabilidades reales"** en los cinco. MLB v2 lo prohibió expresamente a
   favor de "probabilidades justas estimadas". Choca con
   `.claude/rules/betting-output-rules.md`.
5. **Disciplina point-in-time y procedencia.** Ninguno exige fuente + timestamp +
   corte estadístico, ni corte temporal estricto en backtest. **Es la regla
   anti-fuga cuya ausencia produjo KI-019 en este proyecto.**
6. **"Candidato a valor" en vez de "CLV potencial positivo".** Los cinco marcan
   CLV *antes* del cierre, que es imposible por definición. (Mitigado en parte por
   la bandera de outlier, que MLB v2 no tiene.)

Ninguno de los seis, tampoco MLB v2, **tiene fase de calibración**.

## Conocimiento de dominio: lo mejor de cada uno

No son plantillas rellenadas. Cada uno identifica correctamente el input que
gobierna su deporte y lo trata como ciudadano de primera:

**NHL** — el portero. La regla anti-doble-conteo `xGA` (independiente del
portero, aplicar `GoalieAdj`) vs `GA` real (ya lo incluye, aplicar solo el delta)
es sutil y correcta. Añade **regresión de PDO** (el hockey es el deporte con más
varianza de resultado vs proceso), **corrección de portería vacía** en el total
(+0.20) **y en la puck line** (+0.04, porque los goles EN convierten victorias
por 1 en victorias por 2 — efecto real que casi ningún modelo aficionado
captura), y módulo OT/SO acreditando +1 gol al ganador.

**Fútbol** — Dixon-Coles con τ explícito y el empate como resultado de primera
clase, nunca residuo. **Todos los mercados salen de LA MISMA matriz**, lo que
garantiza coherencia entre 1X2, AH, totales y BTTS. Prohíbe comparar índices
entre ligas (Ruta C con Elo obligatoria en UCL) — error que cuesta dinero real.
Y **la localía ya está dentro de `λ_home`/`λ_away`**, con prohibición explícita
de añadir un `HomeAdj` encima: exactamente el doble conteo que MLB no controla.

**Football** — la tabla de **números clave**: `P(|margen| = 3) = 9.5%`,
`= 7 → 8.5%`. Es lo que separa un modelo de NFL real de uno ingenuo, y las
magnitudes son correctas. Añade que medio punto cruzando el 3 o el 7 vale ~la
mitad de la masa, y **umbrales de edge más bajos porque la NFL es el mercado más
eficiente** — conciencia explícita de contra quién se compite.

**Baloncesto** — `Pace_esp = AdjT_A + AdjT_B − Pace_liga`, correcto. Y la
coherencia interna de las constantes es verificable: con `σ_margin = 11.5` y
`σ_total = 18.5` (NBA), `(1+ρ)/(1−ρ) = (18.5/11.5)²` da **ρ = 0.44**, que cuadra
con el `rho_base = 0.40` declarado. No están puestas al azar.

**Tenis** — el Elo por superficie ya captura la superficie, así que prohíbe un
`SurfaceAdj` encima. Limita el H2H a ±15 pts Elo (se sobrevalora
sistemáticamente) y declara que **el ranking oficial no es un rating
predictivo**. Y lo más notable: *"en tenis, un edge enorme a favor del modelo
suele significar que el MERCADO SABE ALGO FÍSICO"* — **es selección adversa,
nombrada explícitamente**, que es justo lo que este proyecto midió después.

## Defectos concretos encontrados

### 1. Tenis — la tabla Bo3→Bo5 contradice sus propias fórmulas

La Fase 6 da las fórmulas `P_bo3 = p²(3−2p)` y
`P_bo5 = p³[1 + 3(1−p) + 6(1−p)²]`, y **también** una tabla de conversión para la
vía sin código. No coinciden:

| P_bo3 | Tabla | Fórmulas | Δ |
|---:|---:|---:|---:|
| 80% | 83.5% | **85.4%** | −1.9 pp |
| 90% | 93.0% | **94.6%** | −1.6 pp |

La vía con código y la vía sin código dan resultados distintos en ~2 pp,
**justo en el orden de magnitud del umbral de decisión (4–5 pp)**.

Puede que la tabla sea un amortiguamiento empírico deliberado —la conversión
ingenua sobreestima al favorito en Bo5 porque `p_set` no es constante entre
sets—, pero el prompt las presenta como equivalentes. Hay que resolverlo y
declarar cuál manda.

### 2. Dos fórmulas quedaron sin terminar en el documento

- **Baloncesto, Fase 3:** *"SOSAdj: calendario claramente duro ×0.98 sobre
  DefIndex propio y ×1.02 sobre OffIndex**...** simplificación permitida"*
- **NHL, Fase 3:** *"STAdj_A: (PP_A − PP_liga) × 0.02 + (PK_liga − PK_B**...**
  simplificación permitida y preferida"*

Ambas cortan a media expresión con puntos suspensivos literales. Quien ejecute
ese punto no tiene comportamiento definido. Son artefactos de redacción, pero
en un documento que gobierna cálculos hay que cerrarlos.

### 3. `rho` sin procedencia declarada, en todos

`rho_base = 0.40` (baloncesto), `0.05` (NHL), `−0.10` (Dixon-Coles en fútbol).
Ninguno declara de dónde sale. Si vienen de correlación histórica **cruda**,
sobreestiman la correlación *residual* una vez que el modelo ya condiciona por
pace, entorno o liga. Mismo problema que el `rho_base = 0.12` de MLB.

### 4. El `rho_DC = −0.10` de fútbol es global para 12 competiciones

Dixon-Coles ajusta ρ por liga. Un valor único para EPL, Brasileirão,
Frauen-Bundesliga y UWCL —con distribuciones de marcador muy distintas— es una
simplificación que conviene declarar como tal.

## Los sanity checks son lo más valioso de la familia

Son coherencias internas falsables, y varias sirven como **tests unitarios
directos** para el código de `src/sqp`:

- Fútbol: `P(AH −0.5) = P(1X2 gana)` **exactamente**; `P(DNB) > P(1X2)` del mismo
  lado; suma de la matriz pre-normalización ≥ 0.98.
- NHL: `P(empate reglamentario) ∈ [20%, 27%]`; `P(fav −1.5)/P(fav ML) ∈
  [0.55, 0.72]`; ML ∈ [25%, 80%].
- Football: si la línea es −3 o −7 exacta y no se reporta `P_push`, **la salida
  es inválida**.
- Tenis: `P(2-0) + P(2-1) = P(ML)` exactamente; Bo5 nunca reduce al favorito.
- Todos: equipos idénticos en casa → `P_home` en un rango declarado por liga
  (NBA 56–58%, NFL 54–55%, NHL 53–55%, fútbol 43–47%).

**Ese último es exactamente la comprobación de localía que propuse para MLB** —
aquí ya está escrita como regla para los otros cinco deportes.

## Trabajo que esto sugiere

Dos pasadas, ambas acotadas:

1. **v2 de los cinco**: importar las seis correcciones de MLB v2 (EV por unidad,
   ranking lexicográfico, "convicción" en vez de edge, lenguaje epistémico,
   point-in-time + procedencia, "candidato a valor"), y cerrar los defectos 1 y 2
   de arriba. Es mecánico y de alto valor.
2. **v3 de MLB**: importar las cinco aportaciones de la familia (Fase 0, regla
   anti-doble-conteo, bandera de outlier, sanity checks, dos modos de
   trazabilidad).

Y para los seis: **la fase de calibración que ninguno tiene**.

Ver [[Prompt 191 - origen del modelo]] y [[Bitácora/2026-08-15]].
