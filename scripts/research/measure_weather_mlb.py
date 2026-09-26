"""Medicion del pre-registro del clima MLB (2026-09-26). UNA sola ejecucion.

Ver `docs/research/2026-09-26-preregistro-clima-mlb.md`. Entrada: el CSV de
`fetch_weather_mlb.py`. Reproduce el walk-forward canonico de
`sqp.backtesting.engine` partido a partido (hace falta el `game_id` para unir
el clima, y el motor solo devuelve series anonimas) y COMPRUEBA la paridad con
el motor antes de medir: si la probabilidad base no coincide, aborta.

  python scripts/research/measure_weather_mlb.py --weather <csv> --out <json>
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from sqp.backtesting.engine import walk_forward_backtest
from sqp.calibration.metrics import expected_calibration_error
from sqp.config import ROOT, Settings
from sqp.domain.models import Event
from sqp.pipeline.daily import _league_meta
from sqp.sports.registry import get_adapter
from sqp.storage.results_store import ResultsStore
from sqp.storage.starter_fip import StarterFIPStore
from sqp.storage.starters import StartersStore

LINES = (7.5, 8.5, 9.5)
WARMUP = 60  # default de walk_forward_backtest
FOLDS = {"A": (("2024",), ("2025",)), "B": (("2024", "2025"), ("2026",))}


def walk_forward_over(results: list[dict], params: dict) -> pd.DataFrame:
    """P(Over) por partido y linea, con la MISMA secuencia que el motor."""
    adapter = get_adapter("mlb", "baseball", params)
    rows, pending = [], []
    for i, r in enumerate(sorted(results, key=lambda x: str(x.get("date", "")))):
        if pending and str(r.get("date", ""))[:10] != str(pending[0].get("date", ""))[:10]:
            for done in pending:
                adapter.observe(done)
            pending.clear()
        if i >= WARMUP:
            ev = Event(event_id=str(i), sport_key="bt", league="mlb",
                       home=r["home"], away=r["away"], start_time=str(r.get("date")),
                       data_label=r.get("data_label", "real"),
                       home_pitcher=r.get("home_starter"),
                       away_pitcher=r.get("away_starter"))
            total = r["home_score"] + r["away_score"]
            row = {"game_id": str(r.get("game_id")), "date": str(r["date"])[:10]}
            for t in LINES:
                row[f"p{t}"] = adapter.estimate(ev, None, t).over_estimated_probability
                row[f"y{t}"] = 1.0 if total > t else 0.0
            rows.append(row)
        pending.append(r)
    return pd.DataFrame(rows)


def delta_over(df: pd.DataFrame, wind_coef: float, precip_coef: float,
               threshold: float) -> np.ndarray:
    """Formula de `weather.weather_p_adjustment`; 0 sin pronostico."""
    wind = df["wind_kmh"].to_numpy(dtype=float)
    prec = df["precip_mm"].to_numpy(dtype=float)
    d = (np.maximum(0.0, wind - threshold) * wind_coef + prec * precip_coef)
    return np.where(np.isfinite(d), d, 0.0)


def mean_logloss(df: pd.DataFrame, delta: np.ndarray) -> float:
    terms = []
    for t in LINES:
        p = np.clip(df[f"p{t}"].to_numpy() + delta, 0.01, 0.99)
        y = df[f"y{t}"].to_numpy()
        terms.append(-(y * np.log(p) + (1 - y) * np.log(1 - p)))
    return float(np.mean(np.concatenate(terms)))


def pooled_ece(df: pd.DataFrame, delta: np.ndarray) -> float:
    p = np.concatenate([np.clip(df[f"p{t}"].to_numpy() + delta, 0.01, 0.99) for t in LINES])
    y = np.concatenate([df[f"y{t}"].to_numpy() for t in LINES])
    return float(expected_calibration_error(list(p), list(y)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weather", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    threshold = float(Settings.load().weather.wind_threshold_kmh)
    params = dict(_league_meta("mlb").get("league_params") or {})
    results = ResultsStore(ROOT).load("mlb")
    StartersStore(ROOT).attach("mlb", results)
    StarterFIPStore(ROOT).attach("mlb", results)

    base = walk_forward_over(results, params)
    ref = walk_forward_backtest(results, "mlb", "baseball", params, total_lines=LINES)
    for t in LINES:  # paridad con el motor canonico
        mine = base[f"p{t}"].tolist()
        theirs = ref["markets"][f"totals@{t}"]["probs"]
        if len(mine) != len(theirs) or not np.allclose(mine, theirs, atol=1e-12):
            raise SystemExit(f"PARIDAD ROTA en la linea {t}: no se mide nada.")

    w = pd.read_csv(args.weather, dtype={"game_id": str})
    df = base.merge(w[["game_id", "roof_type", "wind_kmh", "precip_mm"]],
                    on="game_id", how="inner")
    universo = df[(df["date"] >= "2024-01-01") & (df["date"] <= "2026-09-24")]
    abiertos = universo[universo["roof_type"] == "Open"].copy()
    abiertos["season"] = abiertos["date"].str[:4]

    out: dict = {"threshold_kmh": threshold, "params": params,
                 "coverage": {"universo": int(len(universo)),
                              "abiertos": int(len(abiertos)),
                              "abiertos_con_pronostico": int(abiertos["wind_kmh"].notna().sum()),
                              "por_techo": universo["roof_type"].value_counts().to_dict()},
                 "folds": {}}
    tests = []
    for name, (train_s, test_s) in FOLDS.items():
        tr = abiertos[abiertos["season"].isin(train_s)]
        te = abiertos[abiertos["season"].isin(test_s)]
        res = minimize(lambda c: mean_logloss(tr, delta_over(tr, c[0], c[1], threshold)),
                       x0=np.zeros(2), method="Nelder-Mead",
                       options={"xatol": 1e-7, "fatol": 1e-10, "maxiter": 2000})
        wc, pc = (float(x) for x in res.x)
        d_te = delta_over(te, wc, pc, threshold)
        ll0, ll1 = mean_logloss(te, np.zeros(len(te))), mean_logloss(te, d_te)
        out["folds"][name] = {
            "train": list(train_s), "test": list(test_s),
            "n_train": int(len(tr)), "n_test": int(len(te)),
            "wind_coef": wc, "precip_coef": pc,
            "logloss_base": ll0, "logloss_trat": ll1, "delta_logloss": ll1 - ll0,
            "ece_base": pooled_ece(te, np.zeros(len(te))), "ece_trat": pooled_ece(te, d_te),
            "n_test_afectados": int((d_te != 0).sum())}
        tests.append((te, d_te))
    te_all = pd.concat([t for t, _ in tests])
    d_all = np.concatenate([d for _, d in tests])
    ll0 = mean_logloss(te_all, np.zeros(len(te_all)))
    ll1 = mean_logloss(te_all, d_all)
    aff = d_all != 0
    out["combinado"] = {
        "n_test": int(len(te_all)), "delta_logloss": ll1 - ll0,
        "ece_base": pooled_ece(te_all, np.zeros(len(te_all))),
        "ece_trat": pooled_ece(te_all, d_all),
        "secundario_delta_logloss_afectados": (
            mean_logloss(te_all[aff], d_all[aff]) - mean_logloss(te_all[aff], np.zeros(int(aff.sum())))
            if aff.any() else math.nan)}
    fb = out["folds"]["B"]
    c = out["combinado"]
    out["criterios"] = {
        "1_delta_combinado_le_-0.002": c["delta_logloss"] <= -0.002,
        "2_delta_negativo_en_cada_particion": all(f["delta_logloss"] < 0 for f in out["folds"].values()),
        "3_ece_no_empeora": c["ece_trat"] <= c["ece_base"],
        "4_coefs_B_negativos": fb["wind_coef"] < 0 and fb["precip_coef"] < 0}
    out["veredicto"] = "ACEPTA" if all(out["criterios"].values()) else "RECHAZA"
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
