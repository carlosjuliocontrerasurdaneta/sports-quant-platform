"""Gate de PREDICCION por (liga, mercado): la regla de salida vigente.

Sustituye al gate de CLV como criterio rector (decision 2026-08-16). El CLV mide
rendimiento contra un mercado, no la veracidad de la prediccion, y su gate
llevaba vacio desde julio: una puerta que nadie puede cruzar equivale a no tener
puerta.

Un (liga, mercado) lleva stake real solo si cumple LAS DOS condiciones:

1. Su modelo PURO bate al mercado evento a evento -- test de signo pareado sobre
   ``d = (p_mercado - y)^2 - (p_modelo - y)^2``, unilateral, empates excluidos,
   n >= min_n y p < alpha. Se usa ``model_probability`` y no la mezcla ni la
   calibrada porque ambas contienen el precio dentro: compararlas con el mercado
   no diria si el modelo aporta algo propio.
   ``n`` cuenta OBSERVACIONES INDEPENDIENTES, una por (evento, mercado, linea),
   no filas del stream: ver ``_independent_units``.
2. Su EV a stake plano es positivo. Acertar mas que el precio no basta si el
   margen no cubre el vig (leccion de pick_mode accuracy, favoritos a 1.07).

FUERA DE MUESTRA: solo cuentan las filas posteriores a ``VALIDATION_START``, la
fecha del pre-registro. Lo anterior ya fue observado por el analisis que
descubrio los candidatos, y usarlo seria validar sobre la muestra del hallazgo
(KI-019). El dia de entrada en vigor el gate niega todos los mercados; es el
comportamiento correcto.

Politica default-deny: sin registro, sin entrada o con evidencia insuficiente,
stake 0 (flag "prediction_gate"). Criterio completo y criterios de descarte en
docs/research/2026-08-16-preregistro-regla-de-salida.md.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from scipy.stats import binomtest

from sqp.logging_config import get_logger

log = get_logger(__name__)

PREDICTION_GATE_FILENAME = "prediction_gate.json"
# Fecha del pre-registro. Solo cuenta lo ESTRICTAMENTE posterior.
VALIDATION_START = "2026-08-16"
# Minimo de filas no empatadas por (liga, mercado). Por debajo, el signo es
# ruido: deny.
PREDICTION_GATE_MIN_N = 300
PREDICTION_GATE_ALPHA = 0.05

_REQUIRED = ("model_probability", "implied_probability_novig", "price_decimal")
_TABLE_COLS = ["league", "market", "n", "wins", "p_value", "ev_flat",
               "allowed", "reason"]


def _usable(graded: pd.DataFrame, validation_start: str) -> pd.DataFrame:
    """Filas resueltas win/loss, posteriores al pre-registro y con las tres
    columnas numericas presentes."""
    if graded.empty or "result" not in graded.columns:
        return pd.DataFrame(columns=list(graded.columns) + ["y"])
    df = graded[graded["result"].isin(["win", "loss"])].copy()
    if df.empty:
        return df.assign(y=pd.Series(dtype=int))
    for col in ("game_date", "event_id"):
        if col not in df.columns:
            # `event_id` es tan obligatorio como `game_date`: sin identidad de
            # evento no se puede colapsar a observaciones independientes
            # (`_independent_units`) y el test de signo dejaria de ser valido.
            # Default-deny antes que un p-valor que no significa nada.
            log.warning("prediction_gate: columna '%s' ausente — todas las "
                        "filas filtradas (default-deny).", col)
            return df.iloc[0:0].assign(y=pd.Series(dtype=int))
    fecha = df["game_date"].astype(str)
    df = df[fecha > validation_start]
    for col in _REQUIRED:
        if col not in df.columns:
            return df.iloc[0:0].assign(y=pd.Series(dtype=int))
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=list(_REQUIRED))
    df["y"] = (df["result"] == "win").astype(int)
    return df


def _independent_units(g: pd.DataFrame) -> pd.DataFrame:
    """Una observacion por (evento, mercado, linea): `d` y `ev` promediados.

    El test de signo asume ENSAYOS INDEPENDIENTES, y las filas del stream servido
    no lo son, por dos vias que se multiplican:

    - **Repeticion diaria.** `append_served` deduplica solo dentro del mismo dia
      de run, asi que un pick dentro del horizonte de 7 dias se sirve una vez por
      dia. Medido el 2026-08-27: 13.999 filas graduadas para 6.379 picks (2,19x),
      y en la ventana del gate `mls|h2h` tenia **348 filas de 21 eventos** (16,6
      por evento) con el umbral en 300.
    - **Las dos caras del mismo mercado.** Si las probabilidades del lado
      contrario son complementarias (`p' = 1-p`, `y' = 1-y`), entonces
      `(p'-y')^2 = (p-y)^2` y `d` es EXACTAMENTE el mismo: el lado B duplica n
      sin aportar ni un bit.

    Contar esas filas como ensayos independientes infla `n` y hunde el p-valor
    del binomial. El 2026-08-27 `mls|h2h` estaba en `p = 0,0600` con alpha 0,05 y
    `brasileirao|h2h` en `p = 0,000039` sobre **8 eventos**: el gate estaba a un
    paso de autorizar dinero real sobre un test invalido. Colapsar es siempre
    CONSERVADOR -- solo puede reducir n y subir el p-valor, nunca abrir una
    puerta que estuviera cerrada.
    """
    d = ((g["implied_probability_novig"] - g["y"]) ** 2
         - (g["model_probability"] - g["y"]) ** 2)
    ev = (g["model_probability"] * (g["price_decimal"] - 1.0)
          - (1.0 - g["model_probability"]))
    units = pd.DataFrame({"d": d, "ev": ev})
    keys = [c for c in ("event_id", "market", "line") if c in g.columns]
    for k in keys:
        units[k] = g[k]
    return units.groupby(keys, dropna=False, sort=False)[["d", "ev"]].mean().reset_index()


def _decide(g: pd.DataFrame, min_n: int, alpha: float) -> dict:
    """Evalua un (liga, mercado) ya filtrado. Orden de las razones: la muestra
    manda sobre el signo, y el signo sobre el EV."""
    units = _independent_units(g)
    d = units["d"]
    n = int((d != 0).sum())
    wins = int((d > 0).sum())
    ev = float(units["ev"].mean())
    p = (float(binomtest(wins, n, 0.5, alternative="greater").pvalue)
         if n > 0 else float("nan"))
    if n < min_n:
        reason = "muestra_insuficiente"
    elif not (p < alpha):
        reason = "no_bate_al_mercado"
    elif not (ev > 0):
        reason = "ev_no_positivo"
    else:
        reason = ""
    return {"n": n, "wins": wins, "p_value": p, "ev_flat": ev,
            "allowed": reason == "", "reason": reason}


def evaluate_markets(graded: pd.DataFrame, *,
                     min_n: int = PREDICTION_GATE_MIN_N,
                     alpha: float = PREDICTION_GATE_ALPHA,
                     validation_start: str = VALIDATION_START) -> pd.DataFrame:
    """Una fila por (league, market) con la decision y su evidencia."""
    df = _usable(graded, validation_start)
    if df.empty:
        return pd.DataFrame(columns=_TABLE_COLS)
    rows = []
    for (lg, mk), g in df.groupby(["league", "market"]):
        rows.append({"league": str(lg), "market": str(mk),
                     **_decide(g, min_n, alpha)})
    return pd.DataFrame(rows, columns=_TABLE_COLS)


def write_prediction_gate(graded: pd.DataFrame, bets_dir: Path, *,
                          min_n: int = PREDICTION_GATE_MIN_N,
                          alpha: float = PREDICTION_GATE_ALPHA,
                          validation_start: str = VALIDATION_START) -> Path:
    """Persiste el registro (reemplazo atomico). Escribe SIEMPRE, incluso sin
    mercados: un ``markets`` vacio hace explicito el default-deny."""
    decided = evaluate_markets(graded, min_n=min_n, alpha=alpha,
                               validation_start=validation_start)
    markets = {
        f"{r.league}|{r.market}": {
            "n": int(r.n), "wins": int(r.wins), "p_value": float(r.p_value),
            "ev_flat": float(r.ev_flat), "allowed": bool(r.allowed),
            "reason": str(r.reason),
        }
        for r in decided.itertuples()
    }
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "min_n": int(min_n), "alpha": float(alpha),
               "validation_start": str(validation_start), "markets": markets}
    bets_dir = Path(bets_dir)
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / PREDICTION_GATE_FILENAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def load_prediction_gate(bets_dir: Path) -> dict[str, dict]:
    """Mapa "liga|mercado" -> decision. Devuelve {} si el registro no existe o
    es ilegible; el consumidor debe tratar {} como default-deny."""
    path = Path(bets_dir) / PREDICTION_GATE_FILENAME
    if not path.exists():
        return {}
    try:
        markets = json.loads(path.read_text(encoding="utf-8")).get("markets")
    except (OSError, json.JSONDecodeError):
        return {}
    return markets if isinstance(markets, dict) else {}


def market_allowed(gate: dict[str, dict], league: str, market: str) -> bool:
    """True solo si el registro tiene la entrada y esta aprobada (default-deny)."""
    entry = gate.get(f"{league}|{market}")
    return bool(entry and entry.get("allowed"))
