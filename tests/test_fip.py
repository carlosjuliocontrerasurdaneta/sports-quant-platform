"""v2 starter signal: FIP math, store attach, and the adapter FIP rating path."""
from sqp.models.fip import fip_from_line, innings_to_float
from sqp.sports.adapters import BaseballAdapter
from sqp.storage.starter_fip import StarterFIPStore


def test_innings_to_float_counts_outs_not_tenths():
    assert innings_to_float("6.0") == 6.0
    assert abs(innings_to_float("5.2") - (5 + 2 / 3)) < 1e-9
    assert abs(innings_to_float("0.1") - (1 / 3)) < 1e-9
    assert innings_to_float("bad") == 0.0


def test_fip_from_line():
    # Dominant start (Rasmussen-like): 7 IP, 0 HR, 1 BB, 1 HBP, 13 K -> very low FIP.
    fip = fip_from_line(hr=0, bb=1, hbp=1, k=13, ip="7.0")
    assert abs(fip - ((13 * 0 + 3 * 2 - 2 * 13) / 7 + 3.10)) < 1e-9
    assert fip < 1.0
    assert fip_from_line(0, 0, 0, 0, "0.0") is None  # no outs -> no rate


def test_starter_fip_store_save_and_attach(tmp_path):
    store = StarterFIPStore(tmp_path)
    store.save("mlb", [
        {"game_id": "1", "date": "2026-06-10", "home_starter": "Ace",
         "home_starter_fip": 2.1, "away_starter": "Bad", "away_starter_fip": 6.4},
    ])
    results = [{"game_id": "1", "home": "X", "away": "Y", "home_score": 3, "away_score": 2}]
    n = store.attach("mlb", results)
    assert n == 1
    assert results[0]["home_starter_fip"] == 2.1
    assert results[0]["away_starter_fip"] == 6.4
    assert results[0]["home_starter"] == "Ace"  # name filled when missing


def _params():
    return {"avg_total": 8.7, "tilt_scale": 0.4, "max_score": 25,
            "home_scoring_bonus": 0.10, "elo_k": 6, "elo_home_adv": 25,
            "pitcher_signal": "fip", "pitcher_bound": 0.35,
            "pitcher_min_starts": 2, "pitcher_prior_starts": 1.0}


def test_fip_signal_moves_factor_in_right_direction():
    adapter = BaseballAdapter("mlb", _params())
    rows = []
    for i in range(3):  # Ace (low FIP) and Bad (high FIP) each get 3 starts
        rows.append({"home": f"H{i}", "away": f"A{i}", "home_score": 3, "away_score": 2,
                     "home_starter": "Ace", "away_starter": "Bad",
                     "home_starter_fip": 2.0, "away_starter_fip": 6.0})
    adapter.fit_results(rows)
    assert adapter.starters.factor("Ace") < 1.0   # good pitcher suppresses opponent
    assert adapter.starters.factor("Bad") > 1.0   # bad pitcher inflates opponent


def test_ra_signal_is_default_and_ignores_fip():
    p = _params()
    p["pitcher_signal"] = "ra"
    adapter = BaseballAdapter("mlb", p)
    rows = [{"home": f"H{i}", "away": f"A{i}", "home_score": 0, "away_score": 5,
             "home_starter": "Leaky", "away_starter": "Stingy",
             "home_starter_fip": 1.0, "away_starter_fip": 9.0} for i in range(3)]
    adapter.fit_results(rows)
    # RA mode: Leaky allowed 5 (away_score) each start -> factor > 1; FIP ignored.
    assert adapter.starters.factor("Leaky") > 1.0
    assert adapter.starters.factor("Stingy") < 1.0
