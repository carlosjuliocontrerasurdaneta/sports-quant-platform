"""Test the simulation-vs-ML comparison (blend evidence gate). SYNTHETIC only."""
from __future__ import annotations

import numpy as np

from sqp.evaluation.compare import compare_league
from sqp.storage.results_store import ResultsStore


def _seed_league(root, league="nba", n=160, seed=0):
    """Games among 6 teams of fixed latent strength (stronger team scores more)."""
    rng = np.random.default_rng(seed)
    teams = ["A", "B", "C", "D", "E", "F"]
    strength = {t: rng.normal() for t in teams}
    games = []
    import datetime as dt
    d0 = dt.date(2023, 1, 1)
    for i in range(n):
        h, a = rng.choice(teams, size=2, replace=False)
        edge = strength[h] - strength[a] + 0.2  # home edge
        hs = max(0, int(round(rng.normal(105 + 8 * edge, 8))))
        as_ = max(0, int(round(rng.normal(105 - 8 * edge, 8))))
        if hs == as_:
            hs += 1
        games.append({"date": (d0 + dt.timedelta(days=i)).isoformat(),
                      "home": h, "away": a, "game_id": str(i),
                      "home_score": hs, "away_score": as_})
    ResultsStore(root).upsert(league, games)


def test_compare_league_reports_sim_ml_and_weight(tmp_path):
    _seed_league(tmp_path, "nba", n=160)
    r = compare_league("nba", val_fraction=0.25, root=tmp_path)

    assert r["league"] == "nba" and r["n_holdout"] > 0
    for side in ("sim", "ml"):
        assert {"brier_score", "log_loss", "ece"} <= set(r[side])
    # grid covers 0.0, 0.25, 0.5, 0.75, 1.0 and the recommendation is one of them
    assert set(r["grid_log_loss"]) == {0.0, 0.25, 0.5, 0.75, 1.0}
    assert r["recommended_ml_weight"] in r["grid_log_loss"]
    # M-27 (auditoria 2026-07-24): la recomendacion es el argmin del corte de
    # SELECCION (primera mitad del holdout); su metrica honesta se reporta
    # aparte sobre la segunda mitad, disjunta de la seleccion.
    best = min(r["selection_log_loss"].items(), key=lambda kv: (kv[1], kv[0]))[0]
    assert r["recommended_ml_weight"] == best
    assert r["recommended_oos_log_loss"] > 0
