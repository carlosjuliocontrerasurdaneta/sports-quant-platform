"""Matchup-specific totals (fixes the league-constant total bug) and the
edge-plausibility cap that flags miscalibrated selections instead of staking them.
"""
import pandas as pd
import pytest
from sqp.config import ROOT, RiskConfig, Settings
from sqp.domain.models import Event
from sqp.models.team_scoring import TeamScoringRates
from sqp.pipeline.daily import run_league
from sqp.sports.registry import get_adapter


def _ev(home: str, away: str) -> Event:
    return Event(event_id="x", sport_key="bt", league="nba", home=home, away=away,
                 start_time="2099-01-01T00:00:00Z")


def test_scoring_rates_cold_start_falls_back_to_league_constant():
    sr = TeamScoringRates()
    assert sr.expected_total("A", "B", fallback_total=224.0) == 224.0


def test_scoring_rates_are_matchup_specific():
    sr = TeamScoringRates(prior_games=6.0)
    for _ in range(15):
        sr.update("A", "B", 130, 128)   # high-scoring pair
        sr.update("C", "D", 95, 92)     # low-scoring pair
    assert sr.expected_total("A", "B", 224.0) > sr.expected_total("C", "D", 224.0)


def test_scoring_rates_recency_decay_weights_recent_era():
    # Two eras for the same pair: old low-scoring games, then a recent
    # high-scoring era. Without decay the rate is the blended career mean; with
    # a 180-day half-life the 2-year-old games weigh <1%, so the estimate
    # tracks the current era. Regression guard for the 2026-07-04 finding:
    # WNBA totals ran ~9 pts under the market because 2023-25 games weighed
    # the same as last week's.
    no_decay = TeamScoringRates(prior_games=0.0)
    decay = TeamScoringRates(prior_games=0.0, half_life_days=180.0)
    for sr in (no_decay, decay):
        for i in range(20):
            sr.update("A", "B", 75, 75, date=f"2024-01-{i+1:02d}")   # total 150
        for i in range(20):
            sr.update("A", "B", 90, 85, date=f"2026-06-{i+1:02d}")   # total 175
    assert abs(no_decay.expected_total("A", "B", 0.0) - 162.5) < 1.0
    assert decay.expected_total("A", "B", 0.0) > 172.0


def test_scoring_rates_decay_is_noop_without_dates_or_half_life():
    plain = TeamScoringRates(prior_games=6.0)
    with_hl = TeamScoringRates(prior_games=6.0, half_life_days=180.0)
    for sr in (plain, with_hl):
        sr.update("A", "B", 100, 90)          # no date -> decay must be a no-op
        sr.update("A", "B", 102, 88, date=None)
    assert plain.expected_total("A", "B", 200.0) == \
        with_hl.expected_total("A", "B", 200.0)


def test_wnba_adapter_enables_scoring_recency_decay():
    # The WNBA override must plumb scoring_half_life_days into the adapter;
    # other leagues default to 0 (legacy cumulative behavior, byte-identical).
    assert get_adapter("wnba", "basketball").scoring.half_life_days > 0
    assert get_adapter("nba", "basketball").scoring.half_life_days == 0


def test_normal_adapter_total_is_matchup_specific():
    adapter = get_adapter("nba", "basketball")
    rows = []
    for i in range(15):
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "A", "away": "B",
                     "home_score": 130, "away_score": 128})
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "C", "away": "D",
                     "home_score": 95, "away_score": 92})
    adapter.fit_results(rows)
    line = 224.0
    ab = adapter.estimate(_ev("A", "B"), None, line)
    cd = adapter.estimate(_ev("C", "D"), None, line)
    # The old league-constant model returned identical totals for every game.
    assert ab.over_estimated_probability != cd.over_estimated_probability
    assert ab.over_estimated_probability > cd.over_estimated_probability


def _nhl_ev(home: str, away: str) -> Event:
    return Event(event_id="x", sport_key="bt", league="nhl", home=home, away=away,
                 start_time="2099-01-01T00:00:00Z")


def test_poisson_adapter_total_is_matchup_specific():
    adapter = get_adapter("nhl", "hockey")
    rows = []
    for i in range(15):
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "A", "away": "B",
                     "home_score": 6, "away_score": 5})   # high-scoring pair
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "C", "away": "D",
                     "home_score": 1, "away_score": 0})   # low-scoring pair
    adapter.fit_results(rows)
    line = 6.0
    ab = adapter.estimate(_nhl_ev("A", "B"), None, line)
    cd = adapter.estimate(_nhl_ev("C", "D"), None, line)
    assert ab.over_estimated_probability > cd.over_estimated_probability


def test_poisson_scoring_totals_toggle_off_is_league_constant():
    # With the feature off, the total no longer depends on the matchup.
    adapter = get_adapter("nhl", "hockey", {"scoring_totals": False})
    rows = []
    for i in range(15):
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "A", "away": "B",
                     "home_score": 6, "away_score": 5})
        rows.append({"date": f"2026-01-{i+1:02d}", "home": "C", "away": "D",
                     "home_score": 1, "away_score": 0})
    adapter.fit_results(rows)
    ab = adapter.estimate(_nhl_ev("A", "B"), None, 6.0)
    cd = adapter.estimate(_nhl_ev("C", "D"), None, 6.0)
    assert abs(ab.over_estimated_probability - cd.over_estimated_probability) < 1e-9


def _fit_neutral(adapter, n: int = 20):
    """Dos equipos identicos: Elo igualado -> tilt = 0, asi el bonus queda aislado."""
    adapter.fit_results([{"date": f"2026-01-{i%28+1:02d}", "home": "A", "away": "B",
                          "home_score": 3, "away_score": 3} for i in range(n)])
    return adapter


def test_home_scoring_bonus_shifts_the_split_without_inflating_the_total():
    """El bonus de localia reparte carreras entre los dos lados, no las crea.

    Hasta el 2026-08-18 `lam_home` sumaba el bonus entero y `lam_away` no restaba
    nada, asi que `lam_home + lam_away = avg_total + bonus`: TODOS los partidos de
    las tres familias Poisson salian con el total inflado por el bonus completo.
    Medido walk-forward sobre el historico, producia sesgo Over sistematico
    (mlb +0,194 carreras, epl +0,285 goles) y hasta +4,79 pp de sesgo en la
    probabilidad de Over de la EPL a linea 2,5.
    """
    adapter = _fit_neutral(get_adapter("nhl", "hockey"))
    assert adapter.params["home_scoring_bonus"] > 0, "el test no prueba nada sin bonus"
    lam_h, lam_a = adapter._rates(_nhl_ev("A", "B"))
    expected_total = adapter.scoring.expected_total("A", "B", adapter.params["avg_total"])
    assert abs((lam_h + lam_a) - expected_total) < 1e-9


def test_home_scoring_bonus_still_favors_the_home_side():
    """Arreglar el total no puede costar la ventaja de localia.

    Contra la misma pareja: subir el bonus debe abrir la brecha local-visitante
    exactamente en su valor, y dejar el total intacto.
    """
    h0, a0 = _fit_neutral(get_adapter("nhl", "hockey", {"home_scoring_bonus": 0.0}))._rates(
        _nhl_ev("A", "B"))
    h1, a1 = _fit_neutral(get_adapter("nhl", "hockey", {"home_scoring_bonus": 0.4}))._rates(
        _nhl_ev("A", "B"))
    assert (h1 - a1) - (h0 - a0) == pytest.approx(0.4, abs=1e-9)
    assert h1 + a1 == pytest.approx(h0 + a0, abs=1e-9)


def test_risk_config_has_plausibility_cap_default():
    assert RiskConfig().max_plausible_edge == 0.15


def test_edge_cap_flags_and_unstakes_implausible_candidates():
    settings = Settings.load()
    settings.risk.market_shrink = 0.0  # isolate the cap from the shrink dampener
    settings.pick_mode = "edge"  # el cap de plausibilidad es mecanica del modo edge
    run_league("nba", settings, mode="demo")
    f = ROOT / "data" / "predictions" / "demo" / "candidates_nba.csv"
    c = pd.read_csv(f)
    c["flags"] = c["flags"].fillna("")
    # Every staked candidate is within the plausibility cap.
    staked = c[c["stake"] > 0]
    assert (staked["estimated_edge"] <= settings.risk.max_plausible_edge + 1e-9).all()
    # Flagged candidates are recorded for audit but never staked.
    flagged = c[c["flags"] != ""]
    assert len(flagged) >= 1
    assert (flagged["stake"] == 0).all()
    assert (flagged["estimated_edge"] > settings.risk.max_plausible_edge).all()


def test_market_shrink_blends_model_toward_market():
    settings = Settings.load()
    s = settings.risk.market_shrink
    assert 0.0 <= s <= 1.0
    settings.pick_mode = "edge"  # necesita candidatos multi-mercado del selector por edge
    run_league("nba", settings, mode="demo")
    c = pd.read_csv(ROOT / "data" / "predictions" / "demo" / "candidates_nba.csv")
    # Where a market anchor exists, the used probability is the convex blend
    # (1-s)*model + s*market, so it lies between the two and matches the formula.
    anchored = c[c["implied_probability_novig"].notna()]
    assert len(anchored) >= 1
    expected = (1 - s) * anchored["model_probability"] + s * anchored["implied_probability_novig"]
    assert (expected - anchored["estimated_probability"]).abs().max() < 1e-3
    # Shrinking toward market never increases the edge vs the raw model.
    raw_edge = anchored["model_probability"] * anchored["price_decimal"] - 1
    assert (anchored["estimated_edge"] <= raw_edge + 1e-9).all()
