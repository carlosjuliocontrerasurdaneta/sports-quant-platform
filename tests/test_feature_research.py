"""Regression and discriminating tests for pregame feature research."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import pearsonr

from sqp.features.builders import CONFIGS, build_team_rolling_dataset
from sqp.features.mlb import build_mlb_dataset
from sqp.features.research import (FeatureDataset, build_research_dataset,
                                   snapshot_features, sporting_interactions, SPORTING_INPUTS)
from sqp.features.temporal import daily_splits, holdout_start
from sqp.evaluation.feature_blocks import evaluate_blocks


def games(n=36):
    return pd.DataFrame([{"date": str(pd.Timestamp("2025-01-01") + pd.Timedelta(days=i // 2))[:10],
                          "game_id": str(i), "home": "A", "away": "B",
                          "home_score": 2 + i % 3, "away_score": 3,
                          "neutral": False} for i in range(n)])


def measure_module():
    spec = importlib.util.spec_from_file_location("measure", Path(__file__).parents[1] / "scripts/measure_features.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("missing", [None, np.nan, pd.NA, "", "nan", " None "])
def test_unknown_pitchers_never_share_history(missing):
    d = games(6).rename(columns={"home": "home_team", "away": "away_team"})
    d["home_pitcher"] = missing
    d["away_pitcher"] = missing
    out, state = build_mlb_dataset(d)
    assert (out.home_p_starts == 0).all()
    assert (out.away_p_starts == 0).all()
    assert not any(k.startswith("__p_") for k in state)


@pytest.mark.parametrize("league", ["mlb", "nba", "nfl", "nhl"])
def test_daily_features_invariant_to_same_day_scores_and_id_order(league):
    d = games(6).rename(columns={"home": "home_team", "away": "away_team"})
    d["home_pitcher"], d["away_pitcher"] = "P", "Q"
    builder = build_mlb_dataset if league == "mlb" else lambda df: build_team_rolling_dataset(df, CONFIGS[league])
    before, _ = builder(d)
    changed = d.copy()
    changed.loc[0, "home_score"] = 99
    after, state = builder(changed)
    cols = [c for c in before if c.startswith(("home_", "away_", "diff_"))
            and c not in {"home_score", "away_score", "home_win"}]
    pd.testing.assert_frame_equal(before.loc[:1, cols], after.loc[:1, cols])
    assert not before.loc[2:, cols].equals(after.loc[2:, cols])
    assert state  # final day is flushed, not lost


def test_date_splits_keep_whole_days_and_move_holdout_boundary():
    d = games(48)
    for tr, va in daily_splits(d.date, 3):
        assert d.iloc[tr].date.max() < d.iloc[va].date.min()
        assert not set(d.iloc[tr].date) & set(d.iloc[va].date)
    start = holdout_start(d.date, .23)
    assert d.iloc[start - 1].date < d.iloc[start].date
    with pytest.raises(ValueError):
        list(daily_splits(d.date.iloc[::-1], 3))


@pytest.mark.parametrize("r", [-.99, -.43, 0., .42, .99])
def test_pearson_matches_scipy_near_significance_boundaries(r):
    x = np.arange(20, dtype=float)
    x = (x - x.mean()) / np.linalg.norm(x - x.mean())
    z = (-1.) ** np.arange(20)
    z -= z.mean()
    z -= np.dot(x, z) * x
    z /= np.linalg.norm(z)
    y = r * x + np.sqrt(1 - r * r) * z
    got = measure_module()._pearson(x.tolist(), y.tolist())
    assert got == pytest.approx(tuple(pearsonr(x, y)), abs=1e-12)


def test_measure_pairs_missing_features_with_their_own_outcomes(monkeypatch):
    mod = measure_module()
    records = games(40)
    # One event per day makes the expected first test index unambiguous.
    records["date"] = pd.date_range("2025-01-01", periods=40).strftime("%Y-%m-%d")
    records = records.to_dict("records")
    monkeypatch.setattr(mod.ResultsStore, "load", lambda *args: records)
    calls, expected, seen = [], [], []

    def feature(*args):
        i = len(calls)
        calls.append(i)
        if i % 3 == 1:
            return None
        r = records[10 + i]
        expected.append(1. if r["home_score"] > r["away_score"] else .5 if r["home_score"] == r["away_score"] else 0.)
        return i / 100

    monkeypatch.setattr(mod, "team_h2h_form", feature)
    monkeypatch.setattr(mod, "_pearson", lambda x, y: (seen.append((x, y)) or (0., 1.)))
    mod._measure_league("mlb", 10, None)
    assert seen[2][1] == expected


def test_research_features_exclude_same_day_and_future_outcomes():
    d = games()
    a = build_research_dataset(d, "mlb", "baseball")
    d.loc[10:, "home_score"] = 100
    b = build_research_dataset(d, "mlb", "baseball")
    cols = [c for cs in a.blocks.values() for c in cs] + ["base_home", "base_total"]
    pd.testing.assert_frame_equal(a.frame.loc[:11, cols], b.frame.loc[:11, cols])
    assert a.frame.loc[12, "form_home_scored"] != b.frame.loc[12, "form_home_scored"]


def test_snapshots_require_provenance_and_do_not_use_future_versions():
    d = games(4)
    s = pd.DataFrame([{"game_id": "2", "available_at": "2025-01-01T23:00:00Z",
                       "source": "fixture", "home_surface_elo": 1600},
                      {"game_id": "2", "available_at": "2025-01-02T01:00:00Z",
                       "source": "fixture", "home_surface_elo": 2000}])
    out = snapshot_features(d, s, "tennis")
    assert out.loc[2, "home_surface_elo"] == 1600
    assert pd.isna(out.loc[0, "home_surface_elo"])
    with pytest.raises(ValueError, match="timezone"):
        snapshot_features(d, s.assign(available_at="2025-01-01"), "tennis")
    with pytest.raises(ValueError, match="unknown"):
        snapshot_features(d, s.assign(home_score=1), "tennis")
    with pytest.raises(ValueError, match="duplicate"):
        snapshot_features(d, pd.concat([s, s]), "tennis")


def test_tennis_winner_first_history_is_oriented_and_totals_not_scored():
    d = games(60).assign(home_score=1, away_score=0)
    dataset = build_research_dataset(d, "atp", "tennis")
    assert set(dataset.frame.target_h2h) == {0, 1}
    assert not any("scored" in c for c in dataset.blocks["opponent_form"])
    report = evaluate_blocks(dataset, n_splits=2, n_boot=40)
    assert set(report["tasks"]) == {"h2h"}
    assert report["tasks"]["h2h"]["status"] == "MEASURED"


def test_fip_rotation_uses_prior_results_not_current_starter_performance():
    d = games(6).assign(home_starter_fip=2., away_starter_fip=5.)
    a = build_research_dataset(d, "mlb", "baseball")
    assert pd.isna(a.frame.loc[0, "pitching_home_rotation_fip"])
    assert a.frame.loc[2, "pitching_home_rotation_fip"] == 2.
    d.loc[2:3, "home_starter_fip"] = 99.
    b = build_research_dataset(d, "mlb", "baseball")
    assert b.frame.loc[2, "pitching_home_rotation_fip"] == 2.
    assert b.frame.loc[4, "pitching_home_rotation_fip"] != a.frame.loc[4, "pitching_home_rotation_fip"]


def test_ablation_detects_new_signal_and_rejects_constant_feature():
    rng = np.random.default_rng(18)
    n = 600
    signal = rng.normal(size=n)
    y = (signal > 0).astype(int)
    d = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=n).strftime("%Y-%m-%d"),
                      "event_id": np.arange(n).astype(str), "is_draw": False,
                      "target_h2h": y, "base_home": .5, "base_away": .5,
                      "base_draw": 0., "signal": signal, "constant": 1.})
    ds = FeatureDataset(d, {"signal": ["signal"], "constant": ["constant"]}, "tennis", "atp", {})
    report = evaluate_blocks(ds, n_splits=3, n_boot=100)
    scores = {r["variant"]: r for r in report["tasks"]["h2h"]["scores"]}
    assert scores["signal"]["delta_hi"] < 0
    assert abs(scores["constant"]["delta_vs_baseline"]) < 1e-8
    assert scores["without_signal"]["removal_lo"] > 0
    for fold in report["tasks"]["h2h"]["folds"]:
        assert fold["train_end"] < fold["test_start"]


@pytest.mark.parametrize("family,league", [("baseball", "mlb"), ("basketball", "wnba"),
                                          ("football", "ncaaf"), ("hockey", "nhl"),
                                          ("soccer", "epl"), ("tennis", "wta")])
def test_all_families_produce_evaluable_blocks(family, league):
    d = games(72)
    if family == "tennis":
        d = d.assign(home_score=1, away_score=0)
    ds = build_research_dataset(d, league, family)
    report = evaluate_blocks(ds, n_splits=2, n_boot=20)
    assert "sporting" in report["missing_blocks"]
    assert all(task["status"] == "MEASURED" for task in report["tasks"].values())
    for task in report["tasks"].values():
        assert all(np.isfinite(row["loss"]) for row in task["scores"])


def test_pace_and_efficiency_interaction_and_missingness():
    values = {f"{side}_{name}": np.nan for name in SPORTING_INPUTS["basketball"]
              for side in ("home", "away")}
    assert np.isnan(sporting_interactions(values, "basketball")["sporting_pace_efficiency_total"])
    values.update(home_pace=100., away_pace=100., home_off_rating=110.,
                  away_off_rating=110., home_def_rating=110., away_def_rating=110.)
    assert sporting_interactions(values, "basketball")["sporting_pace_efficiency_total"] == 220.


def test_invalid_snapshot_units_are_rejected():
    s = pd.DataFrame([dict(game_id="0", available_at="2024-12-31T00:00:00Z",
                           source="test", home_starter_expected_innings=10.)])
    with pytest.raises(ValueError, match="innings"):
        snapshot_features(games(), s, "baseball")


def test_sim_comparison_uses_configured_adapter_and_daily_boundary():
    from sqp.evaluation.compare import _sim_probs
    from sqp.pipeline.daily import _league_meta
    from sqp.sports.registry import get_adapter
    from sqp.domain.models import Event
    d = games(6).rename(columns={"home": "home_team", "away": "away_team"})
    meta = _league_meta("mlb")
    adapter = get_adapter("mlb", meta["family"], meta.get("league_params"))
    expected = adapter.estimate(Event("0", "test", "mlb", "A", "B", d.iloc[0].date), None, None)
    p = _sim_probs(d, "mlb")
    assert p[0] == pytest.approx(expected.home_win_estimated_probability)
    assert p[0] == p[1]
    d.loc[0, "home_score"] = 99
    changed = _sim_probs(d, "mlb")
    assert p[0] == changed[0] and p[1] == changed[1]
    assert p[2] != changed[2]
