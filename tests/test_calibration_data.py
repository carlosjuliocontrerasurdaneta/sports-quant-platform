import pandas as pd
import pytest

from sqp.calibration.data import TRAINING_COLS, load_settled_training_history


def _write_settled(bets_dir, name, rows):
    bets_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(bets_dir / f"settled_{name}.csv", index=False)


def test_projects_to_training_schema(tmp_path):
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "estimated_probability": 0.58, "result": "win",
         "game_date": "2026-06-20", "generated_at": "2026-06-20T12:00:00Z"},
        {"market": "spreads", "estimated_probability": 0.61, "result": "loss",
         "game_date": "2026-06-21", "generated_at": "2026-06-21T12:00:00Z"},
    ])
    out = load_settled_training_history(tmp_path)
    assert list(out.columns) == TRAINING_COLS
    assert out.loc[0, "league"] == "mlb"
    assert out.loc[0, "market"] == "h2h"
    assert out.loc[0, "date"] == "2026-06-20"
    assert out.loc[0, "estimated_probability"] == pytest.approx(0.58)
    assert set(out["result"]) == {"win", "loss"}


def test_date_falls_back_to_generated_at(tmp_path):
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "estimated_probability": 0.55, "result": "win",
         "game_date": "", "generated_at": "2026-06-22T09:30:00Z"},
    ])
    out = load_settled_training_history(tmp_path)
    assert out.loc[0, "date"] == "2026-06-22"


def test_drops_rows_without_estimated_probability(tmp_path):
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "estimated_probability": 0.55, "result": "win",
         "game_date": "2026-06-20", "generated_at": ""},
        {"market": "h2h", "estimated_probability": "", "result": "loss",
         "game_date": "2026-06-21", "generated_at": ""},
    ])
    out = load_settled_training_history(tmp_path)
    assert len(out) == 1
    assert out.loc[0, "result"] == "win"


def test_date_tracks_game_date_not_row_order(tmp_path):
    # Row inserted later has an EARLIER game_date. `date` must reflect the game
    # date (so the downstream temporal sort is correct), not the row position.
    _write_settled(tmp_path, "mlb", [
        {"market": "h2h", "estimated_probability": 0.60, "result": "loss",
         "game_date": "2026-06-25", "generated_at": ""},
        {"market": "h2h", "estimated_probability": 0.40, "result": "win",
         "game_date": "2026-06-10", "generated_at": ""},
    ])
    out = load_settled_training_history(tmp_path)
    assert out.loc[0, "date"] == "2026-06-25"
    assert out.loc[1, "date"] == "2026-06-10"
    # Guard against a future accidental sort: order must be preserved as written,
    # not sorted by date (the temporal sort belongs downstream, not here).
    assert out.loc[0, "date"] > out.loc[1, "date"]


def test_empty_or_missing_dir_is_empty_frame(tmp_path):
    out = load_settled_training_history(tmp_path / "nope")
    assert out.empty
    assert list(out.columns) == TRAINING_COLS


def test_overconfident_settled_feeds_trainable_history(tmp_path, monkeypatch):
    # An overconfident MLB h2h market (est ~0.70, wins ~40%) projected from
    # settled must feed train_market_calibrators and produce a STAGED candidate,
    # proving the new source integrates with the existing gate/staging machinery.
    import numpy as np
    from sqp.calibration import calibrator as cal

    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    rng = np.random.default_rng(0)
    n = 200
    wins = rng.random(n) < 0.40  # true ~40% vs claimed ~70% -> overconfident
    rows = [{"market": "h2h", "estimated_probability": 0.70,
             "result": "win" if w else "loss",
             "game_date": f"2026-05-{1 + i % 28:02d}", "generated_at": ""}
            for i, w in enumerate(wins)]
    _write_settled(tmp_path, "mlb", rows)

    hist = load_settled_training_history(tmp_path)
    results = cal.train_market_calibrators(hist, min_n=40)  # staging=True default
    mlb = next(r for r in results if r["league"] == "mlb" and r["market"] == "h2h")
    assert mlb["trained"] is True
    assert mlb["persisted"] is True  # a calibrator that lowers OOS Brier was kept
    # Staged, NOT live: nothing was promoted into the live registry.
    assert (tmp_path / "models" / "staging").exists()
    assert cal._load_method_registry(staging=False) == {}


def test_stage_helper_disabled_returns_empty():
    from types import SimpleNamespace
    from sqp.calibration.data import stage_calibrators_from_settled
    assert stage_calibrators_from_settled(SimpleNamespace(calibration_enabled=False)) == []


def test_stage_helper_empty_settled_returns_empty(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from sqp.calibration import data as cdata
    monkeypatch.setattr(cdata, "ROOT", tmp_path)  # empty data/bets
    out = cdata.stage_calibrators_from_settled(SimpleNamespace(calibration_enabled=True))
    assert out == []


def test_stage_helper_trains_from_settled(tmp_path, monkeypatch):
    import numpy as np
    from types import SimpleNamespace
    from sqp.calibration import data as cdata
    from sqp.calibration import calibrator as cal

    monkeypatch.setattr(cdata, "ROOT", tmp_path)
    monkeypatch.setattr(cal, "MODELS_DIR", tmp_path / "models")
    rng = np.random.default_rng(1)
    wins = rng.random(200) < 0.40
    rows = [{"market": "h2h", "estimated_probability": 0.70,
             "result": "win" if w else "loss",
             "game_date": f"2026-05-{1 + i % 28:02d}", "generated_at": ""}
            for i, w in enumerate(wins)]
    _write_settled(tmp_path / "data" / "bets", "mlb", rows)

    out = cdata.stage_calibrators_from_settled(SimpleNamespace(calibration_enabled=True))
    mlb = next(r for r in out if r["league"] == "mlb" and r["market"] == "h2h")
    assert mlb["trained"] is True
    assert (tmp_path / "models" / "staging").exists()  # candidate was staged
    assert cal._load_method_registry(staging=False) == {}  # staged, not live
