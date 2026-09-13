---
name: edge-ranking
description: Use this skill to review, generate, or audit ranked betting edge outputs across supported sports and markets. Usar para "ranking de edge", "ordenar los picks por valor esperado", "revisar la lista diaria de oportunidades" o auditar la clasificacion de picks ya generados.
---

# edge-ranking

Clasificar por valor esperado los picks ya generados, en **todos** los deportes y
mercados que el proyecto soporta.

## Alcance: todos los deportes registrados, no una lista fija

Leer el catalogo vivo, nunca una lista escrita aqui:

- `src/sqp/providers/odds_api.py::SPORT_KEYS` y `src/sqp/sports/registry.py`
  (MLB, NBA, WNBA, NFL, NCAAF, NHL, NCAAB, WNCAAB, tenis ATP/WTA...).
- `configs/leagues/soccer.yaml` (las ligas de futbol, con su `sport_key`).
- Los torneos de tenis se descubren en ejecucion (`scripts/run_all.py::_active_tennis`).

Hasta el 2026-09-10 esta skill decia "across MLB, NBA, NFL and NHL" y dejaba
fuera futbol, tenis y las ligas femeninas y universitarias, que el proyecto SI
opera (auditoria integral, AUD-MED-009).

## Mercados

`h2h`, `spreads` (runline / puckline / handicap) y `totals`. En tenis, solo `h2h`.

## Requisitos

- Usar la probabilidad **calibrada** (`calibrated_probability`), que es la que
  decidio el stake, y distinguirla siempre de la estimada sin calibrar.
- Calcular la probabilidad implicita desde la cuota, y la implicita **sin vig**
  sobre el mercado completo (`sqp/markets/vig.py`). Nunca de-vigear precios
  best-of-N: la suma daria < 1 y fabricaria edge inexistente.
- Calcular el edge con la definicion canonica del proyecto,
  `src/sqp/risk/kelly.py::edge` = `p x cuota_decimal - 1`.
- Ordenar de mayor a menor valor esperado.

## Umbrales: los del proyecto, ninguno inventado

- Edge minimo: `risk.min_edge` de `configs/default.yaml`.
- Techo de plausibilidad: `risk.max_plausible_edge` (por encima se marca como
  probable error de calibracion y **no se stakea**, pero la fila se conserva).
- Gate vinculante por (liga, mercado): `prediction_gate` (default-deny).

Hasta el 2026-09-10 esta skill exigia excluir mercados por "liquidity or
confidence thresholds" y recortar a "top 100". Ninguno de los tres existe:
`grep -rn "liquidity|top 100|max_picks" configs src/sqp` devuelve **cero**
coincidencias. Eran umbrales inventados, prohibidos por `CLAUDE.md` ("Never
invent thresholds, cutoffs, or formulas that are not defined by the project").

## La lista se genera ENTERA

REGLA FUNDAMENTAL del proyecto: se genera la lista diaria de **todos** los
deportes y mercados ordenada por probabilidad/valor, y los gates retiran el
**stake**, nunca la fila. No truncar la salida a N elementos: si hace falta una
vista corta, es un `--top` explicito del operador, no un recorte por defecto.

## Lenguaje obligatorio

Separar siempre probabilidad estimada, probabilidad implicita, edge, hit rate
observado vs prometido, ROI esperado y ROI realizado. Nunca prometer beneficio.
Un hit rate no es una afirmacion de rentabilidad: el punto de equilibrio lo fija
la cuota de cada pick (`1/price_decimal`).
