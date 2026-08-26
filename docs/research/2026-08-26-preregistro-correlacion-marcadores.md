# Pre-registro — correlación entre marcadores en `poisson_match_probs`

**Fecha:** 2026-08-26. Escrito **antes** de implementar y antes de medir ninguna
mejora OOS. La medición diagnóstica que lo motiva (abajo) sí es previa y está
completa; lo que queda pre-registrado es el criterio de aceptación.

## Diagnóstico previo (ya medido, walk-forward, warmup 60)

`poisson_match_probs` compone el marcador como `p = p_home[i] * p_away[j]`:
independencia pura. Dixon-Coles corrige solo la esquina `i,j ≤ 1`.

**Correlación condicional** de los residuos estandarizados `(y − λ)/√Var(λ)`,
con `Var = λ` (Poisson) o `λ + λ²/k` (NegBin):

| liga | n | k | corr condicional | p | IC95 |
|---|---:|---|---:|---:|---|
| mlb | 9.208 | 3,8 | −0,0043 | 0,68 | [−0,025, +0,016] |
| **nhl** | **32.777** | — | **−0,0873** | **<0,0001** | **[−0,098, −0,077]** |
| mls | 1.593 | — | +0,0347 | 0,17 | [−0,014, +0,084] |
| brasileirao | 1.214 | — | −0,0027 | 0,93 | [−0,059, +0,054] |
| epl | 1.089 | — | −0,0555 | 0,067 | [−0,115, +0,004] |
| ligamx | 1.002 | — | +0,0734 | 0,020 | [+0,012, +0,135] |

**Prueba discriminante** (la que el backlog exigía correr antes de implementar):
`ρ` implícito por la varianza del **margen** frente al implícito por la del
**total**. Si el defecto fuera de dispersión (forma de la NB), ambas varianzas
se desviarían en el **mismo** sentido y los dos `ρ` saldrían de **signo
opuesto**. Si es correlación, saldrán **coherentes**.

| liga | ρ por margen | ρ por total | veredicto |
|---|---:|---:|---|
| mlb | −0,0033 | −0,0053 | coherentes, **ambos ≈ 0**: nada que corregir |
| **nhl** | **−0,0590** | **−0,0654** | **coherentes ≈ −0,06: correlación real** |
| mls | +0,0273 | +0,0370 | coherentes pero muestra corta |

Ratios `real/modelo` de la desviación típica, por tercil de `λ_total`:

```
nhl   margen: 1,005 / 1,029 / 1,047   (global 1,028 — el modelo se queda CORTO)
      total : 0,963 / 0,958 / 0,961   (global 0,967 — el modelo se pasa, y es PLANO)
mlb   margen: 1,010 / 0,990 / 1,001   (global 1,000)
      total : 0,996 / 0,971 / 1,012   (global 0,996)
```

**Lo que esto refuta.** La hipótesis registrada el 2026-08-17 era que la falta de
correlación explica por qué `dispersion_k` no puede servir a totales y runline a
la vez **en MLB**. Es **falsa**: en MLB la correlación condicional es
indistinguible de cero y los dos mercados están correctamente dispersos
(ratios 1,000 y 0,996). Sea cual sea la tensión del runline MLB, no es esta.

**Lo que confirma.** En NHL el defecto es real, grande en muestra (n=32.777) y
tiene exactamente la forma que solo la correlación puede corregir: el margen
necesita **ensancharse** y el total **estrecharse**, y

```
Var(margen) = Vh + Va − 2ρ·sh·sa
Var(total)  = Vh + Va + 2ρ·sh·sa
```

`ρ < 0` los mueve en sentidos **opuestos**; `dispersion_k` los mueve en el
**mismo** sentido y por eso no puede servir a los dos. Es el hueco estructural.

## Cambio propuesto

Parámetro nuevo `score_rho` (default `0.0` → **todas las ligas byte-idénticas**),
aplicado en `poisson_match_probs` como término de primer orden de la cópula
gaussiana:

```
p(i,j) = p_h(i)·p_a(j) + ρ · [φ(z_h(i)) − φ(z_h(i−1))] · [φ(z_a(j)) − φ(z_a(j−1))]
z(i) = Φ⁻¹(F(i))
```

Se elige esta forma y no una cópula exacta por tres razones:

1. **Preserva las marginales.** Sumando en `j`, el término de corrección
   telescopa a `φ(+∞) − φ(−∞) = 0`. Las tasas por equipo, el modelo de anotación
   y el moneyline de un solo lado quedan intactos. *(Corrección tras implementar:
   exacto en aritmética real, **no** en punto flotante — el recorte de celdas
   negativas en la cola sesga las marginales. Medido: 1,4e-10 en el punto de
   trabajo de NHL y 4,7e-7 en `|ρ|=0,12`; en MLB con NegBin sube a ~1e-4, que es
   otra razón para no usarlo ahí.)*
2. **Es barato**: dos vectores de 16 entradas y un producto externo, frente a
   ~289 evaluaciones de la normal bivariante por evento. Corre en el pipeline
   diario y en backtests de miles de partidos.
3. **Es la aproximación correcta en el régimen medido** (`|ρ| ≈ 0,06`). Para `ρ`
   grande la expansión de primer orden degrada; se acota `|score_rho| ≤ 0,15`
   *(bajado desde 0,25 tras medir: pasado 0,15 el sesgo del recorte crece a
   1e-3)* y se recortan probabilidades negativas antes de la renormalización que
   el grid ya hace. **Descartado por medición:** amortiguar la corrección entera
   por un escalar en vez de recortar preservaría las marginales exactamente, pero
   el factor sale proporcional a `1/ρ` y el resultado queda idéntico para todo
   `ρ` — el parámetro deja de tener efecto. Queda registrado para no reintentarlo.

Compone con `dc_rho` (que sigue actuando solo en la esquina baja) y con
`dispersion_k` (que sigue moviendo ambos mercados en el mismo sentido).

## Métrica primaria y umbral (fijados ANTES de medir la mejora OOS)

- **Alcance:** solo **NHL**. MLB queda fuera por refutación explícita; el fútbol
  queda fuera por muestra insuficiente (ninguna liga llega a n=2.000 y solo
  `ligamx` roza p<0,05 entre cuatro cortes, que es ruido esperado).
- **Arnés:** `tune_market_param` con su gate rolling-origin ya existente
  (4 folds, margen `IMPROVEMENT_MARGIN`), el mismo que cerró NHL
  `scoring_half_life_days` y `home_scoring_bonus` con un NO el 2026-08-18.
- **Rejilla:** `score_rho ∈ {−0,12, −0,09, −0,06, −0,03, 0,0}`.
- **Primaria:** Brier OOS del **spread** (puckline ±1,5) y del **total** (5,5),
  evaluados por separado.
- **ACEPTAR** solo si el candidato **pasa el gate en AMBOS mercados a la vez**.
  Es el punto entero de la correlación: si mejora uno y empeora el otro, es
  indistinguible de mover `dispersion_k` y no se despliega.
- **Guardarraíl del moneyline:** el Brier OOS del h2h **no puede empeorar** más
  de `+0,0010`. La correlación toca el margen y por tanto el ganador.
- **RECHAZAR** en cualquier otro caso, incluido "mejora prometedora pero no pasa
  el gate".

## Falsación y contraprueba

- Si el argmin de la rejilla es `0,0`, queda refutado y no se escribe override.
- **Contraprueba obligatoria si pasa:** el `ρ` que elige el gate debe caer cerca
  del medido (≈ −0,06). Un óptimo en el extremo de la rejilla (−0,12) sin apoyo
  del diagnóstico sería señal de que el gate está absorbiendo otro defecto, y se
  rechaza igualmente.
- **Caveat registrado:** el ratio del margen en NHL crece con `λ_total`
  (1,005 → 1,047) mientras el del total es plano (0,963 → 0,961). Un `ρ`
  constante no reproduce ese gradiente. Se ajusta un `ρ` constante por ser el
  modelo más simple; si el gate lo acepta, el gradiente residual queda como
  pregunta abierta separada, **no** como justificación para añadir un `ρ`
  dependiente de `λ` en la misma sesión.

## Frontera reversible

- `score_rho` default `0.0` en `FAMILY_PARAMS` y en el código → **sin override,
  ninguna liga cambia**. Los tests existentes de distribuciones deben pasar sin
  tocarlos.
- Desplegar = escribir un override de liga en `configs/leagues/ratings.yaml`.
  Revertir = borrar esa línea.
- **Nada se despliega al implementar.** `shadow_mode` sigue en `true` y los
  stakes en 0; esto no cambia con este trabajo.
- **CORRECCION 2026-08-26.** La linea de arriba decia que `shadow_mode` sigue en `true`. **Es FALSO**: esta en `false` desde el 2026-08-16, cuando el gate de prediccion paso a ser la regla rectora. El error se hereda de `REPO_DESCRIPTION.md` y de la auditoria del 2026-08-05, y se propago sin leer el YAML. Lo que SI se sostiene y es lo que importaba aqui: **los stakes siguen en 0**, pero por los gates, no por shadow (`prediction_gate.json` tiene 0 de 32 mercados en `allowed: true`).


## Expectativa declarada

Con la evidencia acumulada —seis mediciones negativas y el mercado batiendo al
modelo con IC que excluye el cero— **la expectativa razonable es que esto mejore
la calibración de NHL sin producir ventaja explotable**. Mejor dispersión no es
edge: el mercado ya está bien calibrado en esos mercados. El valor de este
cambio es de corrección del motor, y conviene tenerlo escrito antes de mirar el
resultado.
