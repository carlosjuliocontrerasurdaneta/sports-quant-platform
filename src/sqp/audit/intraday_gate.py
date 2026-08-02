"""Gate de la fase ofensiva intradía (#4): decisión con datos, no especulación.

Regla acordada el 2026-07-14 (Tareas #4): la generación intradía solo se
construye si los picks hipotéticos del observatorio (`intraday_edge_log.csv`,
`would_generate=True` sin ser candidatos) SUPERAN a los picks de las 11:00 en
CLV. Este módulo la hace repetible y le fija criterios exactos:

- ``PASS``: n_intradía >= GATE_MIN_N, mediana de CLV intradía > 0 y mayor que
  la mediana de los picks de las 11:00. Batir a un grupo negativo no basta:
  para ganar dinero el CLV propio debe ser positivo.
- ``RECHAZO``: n suficiente y cualquiera de las dos condiciones falla.
- ``INSUFICIENTE``: n_intradía < GATE_MIN_N — seguir acumulando, no decidir.

El CLV de cada hipotético usa el precio de su PRIMER aviso (cuando el sistema
habría apostado); el de un pick de las 11:00 usa su precio de entrada. Filas
sin cierre fresco emparejable se excluyen (no cuentan como CLV 0). Mercados:
h2h desde el v1 del observatorio; spreads/totals desde el v2 (2026-08-02),
emparejados por línea EXACTA. Probabilidades estimadas, nunca certezas; un
PASS habilita CONSTRUIR la fase, no apostar dinero real.
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

# Mismo estándar de muestra que el gate de CLV (configs/default.yaml,
# clv_gate_min_n) y los umbrales de STATES.md: no decidir con menos.
GATE_MIN_N = 30

_KEY = ["league", "event_id", "market", "selection", "line"]

# (league, event_id, market, selection, line) -> precio de cierre o None.
CloseLookup = Callable[[str, str, str, str, "float | None"], "float | None"]


def _norm_line(market: str, line) -> float | None:
    if market == "h2h":
        return None
    pt = pd.to_numeric(pd.Series([line]), errors="coerce").iloc[0]
    return None if pd.isna(pt) else float(pt)


def first_detections(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(hipotéticos, picks_1100), ambos deduplicados por clave.

    Hipotéticos: filas ``would_generate`` cuya clave NUNCA fue candidata en el
    log (un hipotético que luego se volvió pick real ya está representado en el
    grupo 11:00) — se queda el PRIMER aviso cronológico. Picks 11:00: primer
    check de cada clave con ``is_candidate``."""
    if df.empty:
        empty = df.iloc[0:0]
        return empty, empty
    d = df.copy()
    if "line" not in d.columns:  # log anterior al v2 del observatorio
        d["line"] = float("nan")
    d["line"] = [_norm_line(str(m), ln) for m, ln in zip(d["market"], d["line"])]
    d["_ts"] = pd.to_datetime(d["timestamp"], utc=True, errors="coerce")
    d["_k"] = list(map(tuple, d[_KEY].astype(str).values))
    cand_keys = set(d.loc[d["is_candidate"].astype(bool), "_k"])
    hyp = d[d["would_generate"].astype(bool) & ~d["_k"].isin(cand_keys)]
    hyp = hyp.sort_values("_ts").groupby("_k", as_index=False).first()
    cand = d[d["is_candidate"].astype(bool)]
    cand = cand.sort_values("_ts").groupby("_k", as_index=False).first()
    return hyp, cand


def _clv_frame(rows: pd.DataFrame, price_col: str,
               close_for: CloseLookup) -> pd.DataFrame:
    out = []
    for r in rows.itertuples():
        close = close_for(str(r.league), str(r.event_id), str(r.market),
                          str(r.selection), _norm_line(str(r.market), r.line))
        if close is None or close <= 1.0:
            continue
        entry = pd.to_numeric(pd.Series([getattr(r, price_col)]),
                              errors="coerce").iloc[0]
        if pd.isna(entry) or entry <= 1.0:
            continue
        out.append({"league": str(r.league), "clv": float(entry) / float(close) - 1.0})
    return pd.DataFrame(out, columns=["league", "clv"])


def evaluate_gate(log_df: pd.DataFrame, close_for: CloseLookup) -> dict:
    """Evalúa la regla del gate sobre el log intradía. Devuelve un dict con
    tamaños, medianas/medias/beat-rate por grupo, desglose por liga del grupo
    intradía y ``verdict`` in {PASS, RECHAZO, INSUFICIENTE}."""
    hyp, cand = first_detections(log_df)
    h = _clv_frame(hyp, "price_now", close_for)
    c = _clv_frame(cand, "entry_price", close_for)
    rep: dict = {
        "gate_min_n": GATE_MIN_N,
        "n_intraday": len(h), "n_1100": len(c),
        "median_intraday": float(h["clv"].median()) if len(h) else float("nan"),
        "mean_intraday": float(h["clv"].mean()) if len(h) else float("nan"),
        "beat_intraday": float((h["clv"] > 0).mean()) if len(h) else float("nan"),
        "median_1100": float(c["clv"].median()) if len(c) else float("nan"),
        "mean_1100": float(c["clv"].mean()) if len(c) else float("nan"),
        "beat_1100": float((c["clv"] > 0).mean()) if len(c) else float("nan"),
        "by_league_intraday": (
            h.groupby("league")["clv"].agg(["count", "median", "mean"])
            .round(4).to_dict("index") if len(h) else {}),
    }
    if len(h) < GATE_MIN_N:
        rep["verdict"] = "INSUFICIENTE"
    elif rep["median_intraday"] > 0 and (
            len(c) == 0 or rep["median_intraday"] > rep["median_1100"]):
        rep["verdict"] = "PASS"
    else:
        rep["verdict"] = "RECHAZO"
    return rep
