"""Calibracion per-game del moneyline (pendiente del 2026-06-23).

Los calibradores por (liga, mercado) entrenan sobre picks liquidados: muestra
chica (~200) y sesgada por seleccion, incapaz de corregir la sobreconfianza
per-game del moneyline (bins 0.5-0.7 de MLB). Esta ruta entrena la MISMA
cantidad (model_probability pura, pre-blend — el target de servicio desde el
2026-07-02) contra los miles de juegos del backtest walk-forward, cuyo
generador es identico al de produccion (mismo adapter, mismos ratings sobre
el mismo store de resultados).

Piezas:
- pares simetrizados por juego (p, y) y (1-p, 1-y) con el MISMO event_id: el
  split temporal por evento de train_calibration mantiene juntos los dos
  lados, sin fuga del complemento entre train y validacion, y el calibrador
  aprendido queda aplicable a cualquier seleccion (local o visita).
- entrenamiento bajo la clave SANDBOX "<liga>_h2h_pergame" y SOLO en staging:
  produccion aplica "<liga>_h2h", asi que un candidato per-game jamas llega a
  live por este camino; adoptarlo es una decision aparte, con la evaluacion
  cruzada delante.
- evaluacion cruzada sobre la DISTRIBUCION DE SERVICIO: ECE/Brier del
  candidato per-game vs raw vs calibrador live actual, sobre la cola temporal
  de los picks h2h liquidados (la leccion del mismatch train/serve del
  2026-07-01: lo que importa es como transfiere a lo que se sirve).

Solo probabilidades estimadas; nada de esto promete rentabilidad.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import sqp.calibration.calibrator as _cal
from sqp.backtesting.engine import walk_forward_backtest
from sqp.calibration.calibrator import train_calibration
from sqp.calibration.metrics import brier_score, expected_calibration_error

PERGAME_SUFFIX = "_h2h_pergame"
DEFAULT_WARMUP = 60


def pergame_key(league: str) -> str:
    """Clave sandbox de staging; produccion aplica "<liga>_h2h", nunca esta."""
    return f"{league}{PERGAME_SUFFIX}"


def pergame_pairs_from_results(results: list[dict], league: str, family: str,
                               league_params: dict | None = None,
                               warmup: int = DEFAULT_WARMUP) -> pd.DataFrame:
    """DataFrame(probability, won, date, event_id) desde el walk-forward:
    dos filas complementarias por juego evaluado (sin empates), compartiendo
    event_id para que el split por evento nunca separe los lados."""
    res = walk_forward_backtest(results, league, family, league_params,
                                warmup=warmup)
    rows: list[dict] = []
    for i, (p, y, d) in enumerate(zip(res["binary_probs"],
                                      res["binary_outcomes"],
                                      res["binary_dates"])):
        gid = f"g{i:06d}"
        rows.append({"probability": float(p), "won": float(y),
                     "date": str(d), "event_id": gid})
        rows.append({"probability": 1.0 - float(p), "won": 1.0 - float(y),
                     "date": str(d), "event_id": gid})
    return pd.DataFrame(rows,
                        columns=["probability", "won", "date", "event_id"])


def train_pergame_calibrator(league: str, *, family: str | None = None,
                             league_params: dict | None = None,
                             results: list[dict] | None = None,
                             warmup: int = DEFAULT_WARMUP,
                             val_fraction: float = 0.20,
                             root: Path | None = None) -> dict:
    """Entrena iso+beta sobre los pares per-game bajo la clave sandbox, en
    STAGING y con los mismos 4 gates OOS (ECE, Brier, monotonia, extremos).
    Con ``results`` explicitos no toca disco de entrada (tests); si no, carga
    el historico de la liga (y los abridores en beisbol) como el backtest."""
    if results is None or family is None:
        from sqp.config import ROOT
        from sqp.pipeline.daily import _league_meta
        from sqp.storage.results_store import ResultsStore
        root = root or ROOT
        meta = _league_meta(league)
        family = family or meta["family"]
        league_params = league_params or meta.get("league_params")
        if results is None:
            results = ResultsStore(root).load(league)
            if family == "baseball":
                from sqp.storage.starters import StartersStore
                StartersStore(root).attach(league, results)
    df = pergame_pairs_from_results(results, league, family, league_params,
                                    warmup=warmup)
    key = pergame_key(league)
    out = train_calibration(df, prob_col="probability", outcome_col="won",
                            sport=key, staging=True, time_col="date",
                            group_col="event_id", val_fraction=val_fraction)
    out["key"] = key
    out["n_games"] = int(df["event_id"].nunique())
    return out


def _staged_pergame_predict(league: str):
    """predict() del candidato per-game staged (mejor metodo del registro de
    staging; fallback al que exista). None si no hay candidato."""
    key = pergame_key(league)
    method = _cal._load_method_registry(staging=True).get(key)
    order = {"isotonic": ["iso", "beta"], "beta": ["beta", "iso"]}.get(
        str(method), ["iso", "beta"])
    for name in order:
        path = _cal._model_path(key, name, staging=True)
        if path.exists():
            return _cal._load_calibrator(str(path)).predict
    return None


def cross_evaluate_on_settled(league: str, *, hist: pd.DataFrame | None = None,
                              recent_fraction: float = 0.20) -> dict:
    """ECE/Brier de raw vs candidato per-game vs calibrador LIVE actual sobre
    la cola temporal (``recent_fraction``) de los picks h2h liquidados — la
    distribucion que produccion sirve. ``pergame`` es None sin candidato."""
    if hist is None:
        from sqp.calibration.data import load_settled_training_history
        hist = load_settled_training_history()
    g = hist[(hist["league"].astype(str) == league)
             & (hist["market"].astype(str) == "h2h")
             & (hist["result"].isin(["win", "loss"]))].copy()
    g = g.dropna(subset=["model_probability"])
    out: dict = {"league": league, "n_settled": int(len(g)), "n_eval": 0,
                 "raw": None, "pergame": None, "live": None}
    if g.empty:
        return out
    g = g.sort_values("date", kind="stable")
    n_eval = max(1, int(len(g) * recent_fraction))
    tail = g.iloc[-n_eval:]
    probs = tail["model_probability"].to_numpy(dtype=float)
    y = (tail["result"] == "win").to_numpy(dtype=float)
    out["n_eval"] = int(len(tail))

    def _score(p: np.ndarray) -> dict:
        return {"ece": float(expected_calibration_error(p, y)),
                "brier": float(brier_score(p, y)),
                "mean_prob": float(np.mean(p)), "hit_rate": float(np.mean(y))}

    out["raw"] = _score(probs)
    predict = _staged_pergame_predict(league)
    if predict is not None:
        out["pergame"] = _score(np.clip(np.asarray(predict(probs),
                                                   dtype=float), 0.01, 0.99))
    live = _cal.apply_calibration(probs, sport=f"{league}_h2h", method="auto")
    out["live"] = _score(np.asarray(live, dtype=float))
    return out
