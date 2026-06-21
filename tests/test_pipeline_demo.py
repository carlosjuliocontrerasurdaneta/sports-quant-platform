"""End-to-end demo-mode test: no credentials, synthetic data, full pipeline."""
from pathlib import Path
import pandas as pd
from sqp.config import Settings
from sqp.pipeline.daily import run_league, _archive_existing
from sqp.backtesting.engine import walk_forward_backtest
from sqp.providers.synthetic import SyntheticProvider

def test_demo_pipeline_all_families():
    settings = Settings.load()
    for league in ["mlb", "nba", "nfl", "nhl"]:
        df = run_league(league, settings, mode="demo")
        assert len(df) > 0
        assert (df["data_label"] == "demo_synthetic").all()
        p = df["home_win_estimated_probability"]
        assert ((p >= 0) & (p <= 1)).all()

def test_demo_soccer_three_way():
    settings = Settings.load()
    df = run_league("epl", settings, mode="demo")
    s = (df["home_win_estimated_probability"] + df["draw_estimated_probability"]
         + df["away_win_estimated_probability"])
    assert (abs(s - 1.0) < 1e-6).all()

def test_spread_novig_pairs_only_the_main_line():
    from sqp.pipeline.daily import _spread_novig
    # MLB-style: both teams quoted at +-1.5 across books (4 keys); the main line
    # is Mets -1.5 / Braves +1.5. The alternate runlines must NOT pollute de-vig.
    cons = {
        ("spreads", "New York Mets", -1.5): 2.765,
        ("spreads", "Atlanta Braves", 1.5): 1.49,
        ("spreads", "Atlanta Braves", -1.5): 2.63,    # alternate
        ("spreads", "New York Mets", 1.5): 1.50,      # alternate
    }
    fair = _spread_novig(cons, "New York Mets", "Atlanta Braves", -1.5)
    assert set(fair) == {"New York Mets", "Atlanta Braves"}
    assert abs(sum(fair.values()) - 1.0) < 1e-9
    # Braves +1.5 @ 1.49 (implied ~0.67) de-vigs to ~0.63, not the buggy 0.11.
    assert 0.60 < fair["Atlanta Braves"] < 0.66
    assert _spread_novig(cons, "New York Mets", "Atlanta Braves", None) == {}


def test_default_config_pauses_mlb_totals():
    # The shipped default.yaml suspends MLB totals (audit 2026-06-14).
    assert "totals" in Settings.load().paused_markets.get("mlb", [])


def test_paused_market_produces_no_actionable_candidates():
    from sqp.config import ROOT
    settings = Settings.load()
    settings.paused_markets = {"mlb": ["totals"]}
    run_league("mlb", settings, mode="demo")
    f = ROOT / "data" / "predictions" / "demo" / "candidates_mlb.csv"
    if not f.exists():
        return  # no candidates at all -> rule holds vacuously
    c = pd.read_csv(f)
    tot = c[c["market"] == "totals"]
    if not tot.empty:
        flags = tot["flags"].fillna("")
        # every MLB totals candidate is suspended: stake 0 and flagged, none actionable
        assert ((tot["stake"] <= 0) & (flags == "market_paused")).all()


def test_archive_existing_preserves_prior_picks(tmp_path: Path):
    # A candidates file is archived (keyed by its generated_at date) before being
    # overwritten, so an out-of-order RUN-before-SETTLE cannot destroy un-settled
    # picks. Regression guard for the 2026-06-20 pick-loss incident.
    p = tmp_path / "candidates_mlb.csv"
    pd.DataFrame([{"event_id": "e1", "market": "h2h", "selection": "A",
                   "line": 0, "generated_at": "2026-06-20T13:00:00Z"}]).to_csv(p, index=False)
    _archive_existing(p)
    archived = tmp_path / "archive" / "candidates_mlb_2026-06-20.csv"
    assert archived.exists()
    assert pd.read_csv(archived)["event_id"].tolist() == ["e1"]
    # Idempotent and safe on a missing file.
    _archive_existing(p)
    assert list((tmp_path / "archive").iterdir()) == [archived]
    _archive_existing(tmp_path / "does_not_exist.csv")  # no-op, no raise
    # An empty / header-less file (out-of-season league) is a silent no-op.
    empty = tmp_path / "predictions_nfl.csv"
    empty.write_text("")
    _archive_existing(empty)
    assert not (tmp_path / "archive" / "predictions_nfl_*.csv").exists()
    assert list((tmp_path / "archive").iterdir()) == [archived]


def test_walk_forward_backtest_demo():
    results = SyntheticProvider("basketball").fetch_results("nba")
    res = walk_forward_backtest(results, "nba", "basketball")
    assert res["n_games_evaluated"] > 0
    assert 0 < res["brier_score"] < 0.5
