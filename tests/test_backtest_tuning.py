"""Three-way backtest scoring, home-advantage tuning, and ratings overrides."""
from pathlib import Path

import sqp.pipeline.daily as daily
from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.tuning import tune_home_advantage
from sqp.providers.synthetic import SyntheticProvider


def test_walk_forward_three_way_conditional_and_draw_stats():
    results = SyntheticProvider("soccer").fetch_results("epl")
    res = walk_forward_backtest(results, "epl", "soccer", {"avg_total": 2.8})
    assert res["n_games_evaluated"] > 0
    assert 0.0 < res["observed_draw_rate"] < 1.0
    assert 0.0 < res["mean_estimated_draw_probability"] < 1.0
    assert 0.0 < res["brier_score"] < 0.5


def test_walk_forward_two_way_has_no_draw_stats():
    results = SyntheticProvider("basketball").fetch_results("nba")
    res = walk_forward_backtest(results, "nba", "basketball")
    assert res["observed_draw_rate"] is None
    assert res["mean_estimated_draw_probability"] is None


def test_dixon_coles_negative_rho_boosts_draw():
    from sqp.models.distributions import poisson_match_probs
    base = poisson_match_probs(1.4, 1.2, None, None, three_way=True)
    dc = poisson_match_probs(1.4, 1.2, None, None, three_way=True, dc_rho=-0.10)
    assert dc["draw"] > base["draw"]
    assert abs(dc["home_win"] + dc["draw"] + dc["away_win"] - 1.0) < 1e-9
    same = poisson_match_probs(1.4, 1.2, None, None, three_way=True, dc_rho=0.0)
    assert same == base  # rho=0 must be a no-op


def test_walk_forward_reports_threeway_log_loss():
    soccer = SyntheticProvider("soccer").fetch_results("epl")
    res = walk_forward_backtest(soccer, "epl", "soccer", {"avg_total": 2.8})
    assert res["log_loss_threeway"] is not None and res["log_loss_threeway"] > 0
    nba = walk_forward_backtest(SyntheticProvider("basketball").fetch_results("nba"),
                                "nba", "basketball")
    assert nba["log_loss_threeway"] is None


def test_tune_dc_rho_grid():
    from sqp.backtesting.tuning import tune_dc_rho
    results = SyntheticProvider("soccer").fetch_results("epl")
    res = tune_dc_rho(results, "epl", "soccer", {"avg_total": 2.8}, grid=(-0.10, 0.0))
    assert res["best_dc_rho"] in (-0.10, 0.0)
    assert len(res["table"]) == 2


def test_tune_home_advantage_grid():
    results = SyntheticProvider("basketball").fetch_results("nba")
    res = tune_home_advantage(results, "nba", "basketball", grid=(40.0, 80.0))
    assert res["best_home_adv"] in (40.0, 80.0)
    assert len(res["table"]) == 2
    assert res["best_log_loss"] == res["table"]["log_loss"].min()


def test_dc_rho_grid_clamps_out_of_range_values():
    from sqp.backtesting.tuning import tune_dc_rho
    results = SyntheticProvider("soccer").fetch_results("epl")
    # 0.35 is outside the Dixon-Coles bounds and must be dropped before search.
    res = tune_dc_rho(results, "epl", "soccer", {"avg_total": 2.8}, grid=(-0.10, 0.0, 0.35))
    assert 0.35 not in set(res["table"]["dc_rho"])
    assert len(res["table"]) == 2
    assert -0.30 <= res["best_dc_rho"] <= 0.05


def test_home_adv_gate_rejects_thin_sample_and_keeps_default():
    results = SyntheticProvider("basketball").fetch_results("nba")  # 200 games -> 140 eval
    res = tune_home_advantage(results, "nba", "basketball", grid=(0.0, 150.0),
                              default_home_adv=70.0, min_eval=10_000)
    assert res["accepted"] is False
    assert res["recommended_home_adv"] == 70.0          # reverts to family default
    assert res["best_home_adv"] in (0.0, 150.0)         # raw argmin still reported


def test_dc_rho_gate_rejects_when_too_few_draws():
    from sqp.backtesting.tuning import tune_dc_rho
    results = SyntheticProvider("soccer").fetch_results("epl")
    res = tune_dc_rho(results, "epl", "soccer", {"avg_total": 2.8},
                      grid=(-0.10, 0.0), min_draws=10_000)
    assert res["accepted"] is False
    assert res["recommended_dc_rho"] == 0.0             # independent-Poisson default


def test_rolling_origin_rewards_uniformly_better_value():
    from sqp.backtesting.tuning import rolling_origin_improvement
    loss = {0.0: [1.0] * 100, 1.0: [0.5] * 100}   # value 1.0 better everywhere
    ro = rolling_origin_improvement(loss, default_value=0.0, n_splits=4)
    assert ro is not None
    assert ro["mean_oos_improvement"] > 0.4        # ~0.5 default-minus-selected
    assert set(ro["selections"]) == {1.0}          # always picks the better value


def test_rolling_origin_penalizes_overfit_value():
    from sqp.backtesting.tuning import rolling_origin_improvement
    # value 2.0 looks great early, collapses late: in-sample argmin, OOS disaster.
    loss = {0.0: [1.0] * 100, 2.0: [0.1] * 60 + [3.0] * 40}
    ro = rolling_origin_improvement(loss, default_value=0.0, n_splits=2)
    assert ro is not None
    assert ro["mean_oos_improvement"] < 0          # holdout rejects the overfit value


def test_rolling_origin_none_when_insufficient_data():
    from sqp.backtesting.tuning import rolling_origin_improvement
    assert rolling_origin_improvement({0.0: [1.0] * 5}, 0.0, n_splits=4) is None
    assert rolling_origin_improvement({0.0: [1.0] * 100}, 0.0, n_splits=1) is None  # need >=2


def test_home_adv_holdout_gate_sets_oos_field():
    results = SyntheticProvider("basketball").fetch_results("nba")
    res = tune_home_advantage(results, "nba", "basketball", grid=(0.0, 70.0, 150.0),
                              default_home_adv=70.0, min_eval=10, n_splits=3)
    assert "oos_improvement" in res
    assert res["oos_improvement"] is not None      # holdout path was exercised
    assert "rolling-origin" in res["reason"] or "holdout" in res["reason"]


def test_league_meta_merges_ratings_overrides(tmp_path, monkeypatch):
    leagues_dir = tmp_path / "leagues"
    leagues_dir.mkdir(parents=True)
    (leagues_dir / "ratings.yaml").write_text(
        "leagues:\n  nba: {elo_home_adv: 99}\n  ligamx: {elo_home_adv: 77}\n",
        encoding="utf-8")
    (leagues_dir / "soccer.yaml").write_text(
        "leagues:\n  ligamx: {sport_key: soccer_mexico_ligamx, avg_goals: 2.7}\n",
        encoding="utf-8")
    monkeypatch.setattr(daily, "CONFIG_DIR", Path(tmp_path))
    nba = daily._league_meta("nba")
    assert nba["league_params"]["elo_home_adv"] == 99
    ligamx = daily._league_meta("ligamx")
    assert ligamx["league_params"] == {"avg_total": 2.7, "elo_home_adv": 77}
    # SPORT_KEYS shared dicts must not be mutated by the merge
    from sqp.providers.odds_api import SPORT_KEYS
    assert "league_params" not in SPORT_KEYS["nba"]
