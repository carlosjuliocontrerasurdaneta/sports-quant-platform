"""RestModel wired into PoissonAdapter (hockey/baseball/soccer), section 4 of
docs/research/2026-09-27-preregistro-descanso-nhl.md.

`rest_elo_per_day` shifts the Elo DIFFERENCE that decides the home/away split
(`diff_eff = rating_diff + c * delta_r`); the scale (`avg`, hence the total)
is untouched -- see section 1.2/1.3. Default 0.0 must reproduce the previous
`self.elo.expected_home_win(...)` call byte for byte: this is what actually
ships live for hockey/baseball/soccer today, so it must never move.

Deliberately does NOT re-test RestModel's own day-arithmetic (tests/test_rest.py
already covers cap/first-game/unparseable-date at the RestModel level); these
tests exercise the same guarantees THROUGH PoissonAdapter, in the four leagues
that inherit the mechanism.
"""
from __future__ import annotations

import math

import pytest

from sqp.backtesting.engine import walk_forward_backtest
from sqp.domain.models import Event
from sqp.models import distributions as dist
from sqp.sports.adapters import PoissonAdapter
from sqp.sports.registry import get_adapter

FAMILIES = ("hockey", "baseball", "soccer")


def _synthetic_results(n_teams: int = 6, n_rounds: int = 6,
                       start: str = "2026-01-01") -> list[dict]:
    """Small deterministic round-robin schedule, one game per team per day,
    with varied scorelines so Elo separates the teams (exercises the tilt
    away from 0, including near its +-0.30 clip)."""
    import datetime as _dt
    teams = [f"T{i}" for i in range(n_teams)]
    day = _dt.date.fromisoformat(start)
    rows = []
    gid = 0
    for rnd in range(n_rounds):
        for i in range(0, n_teams, 2):
            home, away = teams[i], teams[(i + rnd + 1) % n_teams]
            if home == away:
                continue
            # Deterministic pseudo-random-looking but reproducible scoreline.
            hs = 1 + (gid * 7 + i * 3) % 6
            aws = 1 + (gid * 5 + rnd * 2) % 5
            rows.append({"game_id": f"g{gid}", "date": day.isoformat(),
                        "home": home, "away": away,
                        "home_score": float(hs), "away_score": float(aws),
                        "home_starter": f"P{i}", "away_starter": f"P{i + 1}",
                        "neutral": False})
            gid += 1
        day += _dt.timedelta(days=1)
    return rows


def _base_params(family: str) -> dict:
    if family == "hockey":
        return {"avg_total": 6.1, "tilt_scale": 0.9, "max_score": 15,
               "home_scoring_bonus": 0.10, "elo_k": 10, "elo_home_adv": 15}
    if family == "soccer":
        return {"avg_total": 2.7, "tilt_scale": 1.0, "max_score": 10,
               "home_scoring_bonus": 0.15, "elo_k": 18, "elo_home_adv": 48}
    return {"avg_total": 8.9, "tilt_scale": 0.5, "max_score": 20,
           "home_scoring_bonus": 0.10, "elo_k": 6, "elo_home_adv": 24}  # baseball


# ---- 1) rest_elo_per_day == 0.0 (default) is byte-identical -----------------

@pytest.mark.parametrize("family", FAMILIES)
def test_zero_coefficient_matches_expected_home_win_oracle(family):
    """Independent oracle: `EloRatings.expected_home_win`, unchanged by this
    change, is the formula `_rates` used to call directly. With
    rest_elo_per_day == 0.0, `_rates`'s implied p_home must equal that oracle
    EXACTLY (0.0 addition is a no-op in IEEE-754), across a short walk-forward
    so ratings (and the tilt) vary game to game."""
    results = _synthetic_results()
    params = _base_params(family)
    adapter = get_adapter("test_" + family, family, params)
    for i, r in enumerate(sorted(results, key=lambda x: x["date"])):
        ev = Event(event_id=r["game_id"], sport_key="bt", league="test_" + family,
                   home=r["home"], away=r["away"], start_time=r["date"],
                   home_pitcher=r.get("home_starter"), away_pitcher=r.get("away_starter"))
        if i > 0:  # first game: both ratings at base, oracle trivially 0.5
            oracle = adapter.elo.expected_home_win(ev.home, ev.away)
            # `PoissonAdapter._rates` unbound: BaseballAdapter overrides
            # `_rates` to layer the starter/park factors on TOP of it (an
            # orthogonal mechanism, section 1.2's "el canal del reparto" vs.
            # the starter's lambda-factor channel -- section 1.2 alternativas
            # descartadas). This test is only about the rest-affected base
            # formula, so it calls the base implementation directly.
            lam_h, lam_a = PoissonAdapter._rates(adapter, ev)
            # `_rates` scales by TeamScoringRates.expected_total (scoring_totals
            # defaults True), not the raw avg_total constant -- same stateful
            # object the adapter already carries, queried the same way.
            avg = adapter.scoring.expected_total(ev.home, ev.away, params["avg_total"])
            tilt = max(-0.30, min(0.30, (oracle - 0.5) * params["tilt_scale"]))
            exp_h = max(0.1, avg * (0.5 + tilt) + params["home_scoring_bonus"])
            exp_a = max(0.1, avg * (0.5 - tilt))
            assert lam_h == exp_h
            assert lam_a == exp_a
        adapter.observe(r)


@pytest.mark.parametrize("family", FAMILIES)
def test_zero_coefficient_walk_forward_is_byte_identical_with_and_without_the_key(family):
    """`rest_elo_per_day` absent vs explicit 0.0 must produce IDENTICAL
    walk_forward_backtest output (moneyline AND totals): this is the
    regression guard for the four production leagues (hockey/baseball incl.
    F5/soccer) that inherit PoissonAdapter and ship with the key absent
    today."""
    results = _synthetic_results()
    params = _base_params(family)
    ref = walk_forward_backtest(results, "test_" + family, family, params,
                                warmup=0, total_lines=(params["avg_total"],))
    explicit = walk_forward_backtest(results, "test_" + family, family,
                                     {**params, "rest_elo_per_day": 0.0},
                                     warmup=0, total_lines=(params["avg_total"],))
    assert ref["binary_probs"] == explicit["binary_probs"]
    assert ref["binary_outcomes"] == explicit["binary_outcomes"]
    key = f"totals@{params['avg_total']}"
    assert ref["markets"][key]["probs"] == explicit["markets"][key]["probs"]


# ---- 2) rest_elo_per_day != 0.0 moves the split, not the total --------------

@pytest.mark.parametrize("family", FAMILIES)
def test_nonzero_coefficient_leaves_the_lambda_sum_exactly_invariant(family):
    """Section 1.3: `lam_home + lam_away = avg + home_scoring_bonus` does not
    depend on the tilt, hence not on `c` -- algebraically exact (not merely
    approximate) as long as neither lambda hits the 0.1 floor."""
    params = _base_params(family)
    adapter0 = get_adapter("test_" + family, family, {**params, "rest_elo_per_day": 0.0})
    adapterc = get_adapter("test_" + family, family, {**params, "rest_elo_per_day": 25.0})
    for a in (adapter0, adapterc):
        a.observe({"home": "Home", "away": "Away", "home_score": 3.0, "away_score": 1.0,
                  "date": "2026-01-01", "neutral": False,
                  "home_starter": "PH", "away_starter": "PA"})
    ev = Event(event_id="e", sport_key="bt", league="test_" + family,
              home="Rested", away="Tired", start_time="2026-01-06",
              home_pitcher="P1", away_pitcher="P2")
    for a in (adapter0, adapterc):
        a.observe({"home": "Rested", "away": "X", "home_score": 2.0, "away_score": 0.0,
                  "date": "2026-01-01", "neutral": False, "home_starter": "P1", "away_starter": "PX"})
        a.observe({"home": "Tired", "away": "Y", "home_score": 2.0, "away_score": 0.0,
                  "date": "2026-01-04", "neutral": False, "home_starter": "P2", "away_starter": "PY"})
    lam_h0, lam_a0 = adapter0._rates(ev)
    lam_hc, lam_ac = adapterc._rates(ev)
    assert lam_hc != pytest.approx(lam_h0)  # the split DID move
    assert (lam_h0 + lam_a0) == pytest.approx(lam_hc + lam_ac, abs=0.0, rel=0.0) or \
        math.isclose(lam_h0 + lam_a0, lam_hc + lam_ac, rel_tol=0, abs_tol=1e-12)


@pytest.mark.parametrize("family", FAMILIES)
def test_totals_move_only_by_grid_truncation(family):
    """Section 1.3/9: the Over/Under probability itself may move by the
    truncation/floor residual the pre-registro quantifies as ~1e-7 per 10 Elo
    points of shift; generous 1e-4 bound so the test is about ORDER of
    magnitude, not the exact figure (which the measurement script reports)."""
    params = _base_params(family)
    diff_base = 40.0
    avg = params["avg_total"]
    tilt = max(-0.30, min(0.30, (1.0 / (1.0 + 10 ** (-diff_base / 400.0)) - 0.5)
                          * params["tilt_scale"]))
    lam_h0 = max(0.1, avg * (0.5 + tilt) + params["home_scoring_bonus"])
    lam_a0 = max(0.1, avg * (0.5 - tilt))
    diff_c = diff_base + 25.0  # ~1 day of a generous c
    tilt_c = max(-0.30, min(0.30, (1.0 / (1.0 + 10 ** (-diff_c / 400.0)) - 0.5)
                           * params["tilt_scale"]))
    lam_hc = max(0.1, avg * (0.5 + tilt_c) + params["home_scoring_bonus"])
    lam_ac = max(0.1, avg * (0.5 - tilt_c))
    p0 = dist.poisson_match_probs(lam_h0, lam_a0, None, avg, max_goals=params["max_score"])["over"]
    pc = dist.poisson_match_probs(lam_hc, lam_ac, None, avg, max_goals=params["max_score"])["over"]
    assert abs(p0 - pc) < 1e-4


# ---- 3) a known back-to-back shifts the split in the expected direction ----

def test_known_back_to_back_shifts_home_win_probability_up():
    params = {**_base_params("hockey"), "rest_elo_per_day": 10.0}
    adapter = get_adapter("test_hockey_b2b", "hockey", params)
    adapter.observe({"home": "Rested", "away": "X", "home_score": 3.0, "away_score": 1.0,
                     "date": "2026-01-01", "neutral": False})
    adapter.observe({"home": "Tired", "away": "Y", "home_score": 3.0, "away_score": 1.0,
                     "date": "2026-01-04", "neutral": False})
    # 2026-01-05: Rested has 4 days (capped), Tired has 1 day -> delta_r = +3
    # for a game where Rested is home.
    ev = Event(event_id="e", sport_key="bt", league="test_hockey_b2b",
              home="Rested", away="Tired", start_time="2026-01-05")
    p_rest = adapter.estimate(ev, None, None).home_win_estimated_probability
    base = get_adapter("test_hockey_b2b", "hockey", {**params, "rest_elo_per_day": 0.0})
    base.observe({"home": "Rested", "away": "X", "home_score": 3.0, "away_score": 1.0,
                 "date": "2026-01-01", "neutral": False})
    base.observe({"home": "Tired", "away": "Y", "home_score": 3.0, "away_score": 1.0,
                 "date": "2026-01-04", "neutral": False})
    p_base = base.estimate(ev, None, None).home_win_estimated_probability
    assert p_rest > p_base
    assert adapter.rest.margin_adjustment("Rested", "Tired", "2026-01-05") == pytest.approx(30.0)


def test_first_game_has_no_adjustment():
    params = {**_base_params("hockey"), "rest_elo_per_day": 10.0}
    adapter = get_adapter("test_hockey_first", "hockey", params)
    ev = Event(event_id="e", sport_key="bt", league="test_hockey_first",
              home="A", away="B", start_time="2026-01-01")
    assert adapter.rest.margin_adjustment("A", "B", "2026-01-01") == 0.0
    p = adapter.estimate(ev, None, None).home_win_estimated_probability
    base = get_adapter("test_hockey_first", "hockey", {**params, "rest_elo_per_day": 0.0})
    assert p == base.estimate(ev, None, None).home_win_estimated_probability


def test_only_past_days_feed_the_rest_state():
    """`observe` must not leak the day BEING estimated into `RestModel`'s
    per-team date history: this is enforced by walk_forward_backtest's
    day-batched `pending` buffer (engine.py), not by `RestModel.observe`
    itself, which only records whatever it is told (KI-070's protection is in
    `rest_days`, which skips a date equal to `game_date` -- it does not stop
    `observe` from being called with it in the first place). Exercised here
    through the adapter/engine pairing that section 4 relies on for
    paridad."""
    params = {**_base_params("hockey"), "rest_elo_per_day": 10.0}
    results = [
        {"game_id": "1", "date": "2026-01-01", "home": "A", "away": "X",
         "home_score": 3.0, "away_score": 1.0, "neutral": False},
        {"game_id": "2", "date": "2026-01-04", "home": "B", "away": "Y",
         "home_score": 3.0, "away_score": 1.0, "neutral": False},
        # Bet game: A (4 days rest) vs B (1 day rest) on 2026-01-05.
        {"game_id": "3", "date": "2026-01-05", "home": "A", "away": "B",
         "home_score": 3.0, "away_score": 2.0, "neutral": False},
    ]
    ref = walk_forward_backtest(results, "test_hockey_past", "hockey", params, warmup=2)
    assert ref["binary_dates"] == ["2026-01-05"]
    # Manual replay matching the engine's day-batching: observe games 1 and 2
    # (both strictly before 2026-01-05) before estimating game 3.
    adapter = get_adapter("test_hockey_past", "hockey", params)
    adapter.observe(results[0])
    adapter.observe(results[1])
    ev = Event(event_id="3", sport_key="bt", league="test_hockey_past",
              home="A", away="B", start_time="2026-01-05")
    p = adapter.estimate(ev, None, None).home_win_estimated_probability
    assert p == ref["binary_probs"][0]
    assert adapter.rest.margin_adjustment("A", "B", "2026-01-05") == pytest.approx(30.0)


# ---- 4) same UTC day: engine parity vs. today's production entry point -----

def test_engine_day_batching_never_sees_zero_rest_for_a_same_day_pair():
    """Section 3.1/13.4: a team playing twice the same UTC day (afternoon
    second leg) must NOT see the earlier same-day game as "yesterday" (r=0);
    `walk_forward_backtest` defers `adapter.observe` until the whole UTC day
    is done (engine.py's `pending` buffer), so the later game still sees
    whatever rest state existed BEFORE that day. This is "the same rule as
    the engine" (operator decision 4, section 16) and is what the measurement
    script relies on for its own parity (section 5)."""
    params = {**_base_params("hockey"), "rest_elo_per_day": 10.0}
    results = [
        {"game_id": "0", "date": "2025-12-30", "home": "A", "away": "Z",
         "home_score": 2.0, "away_score": 1.0, "neutral": False},
        # A plays TWICE on 2026-01-01 (UTC): an early game and a late one.
        {"game_id": "1", "date": "2026-01-01", "home": "A", "away": "X",
         "home_score": 3.0, "away_score": 1.0, "neutral": False},
        {"game_id": "2", "date": "2026-01-01", "home": "A", "away": "Y",
         "home_score": 1.0, "away_score": 0.0, "neutral": False},
    ]
    ref = walk_forward_backtest(results, "test_hockey_sameday", "hockey", params,
                                warmup=1)
    # Both games on 2026-01-01 are evaluated (i>=warmup=1); the SECOND one
    # must see A's rest computed from 2025-12-30 (2 days), not from the first
    # game of that same day (which would be 0).
    adapter = get_adapter("test_hockey_sameday", "hockey", params)
    adapter.observe(results[0])
    r_second_game = adapter.rest.rest_days("A", "2026-01-01")
    assert r_second_game == 2
    assert ref["binary_probs"][1] != pytest.approx(0.5)  # sanity: game estimated


def test_current_production_entry_point_now_matches_that_parity():
    """KI-070 (fixed in `RestModel`, not in `fit_results`): production's
    warm-up path (`SportAdapter.fit_results`, `src/sqp/sports/base.py`,
    the entry point `pipeline.daily` actually calls) calls `observe()` per
    row in plain chronological order -- it does NOT defer same-UTC-day rows
    the way `backtesting.engine.walk_forward_backtest` and
    `backtesting.roi_engine.realized_roi_backtest` do. Before KI-070, that
    ordering gap meant a later same-day game could see an earlier same-day
    game (already `observe`d) as "yesterday" and compute r=0 -- a value the
    engine's own walk-forward never produces (previous test: it computes
    r=2 for the exact same fixture, because the engine defers a day's
    `observe` calls until that whole day is done).

    `RestModel.rest_days` now skips any stored date equal to `game_date`
    itself and falls back to the true previous distinct date, so it
    reproduces the engine's semantics regardless of the order rows are fed
    to it -- the day-batching gap in `fit_results` no longer matters for
    this mechanism, and no separate activation change to `fit_results` is
    needed (contrast with the previous, now-superseded version of this
    test, which pinned the r=0 gap as a known, unfixed limitation)."""
    params = {**_base_params("hockey"), "rest_elo_per_day": 10.0}
    results = [
        {"game_id": "0", "date": "2025-12-30", "home": "A", "away": "Z",
         "home_score": 2.0, "away_score": 1.0, "neutral": False},
        {"game_id": "1", "date": "2026-01-01", "home": "A", "away": "X",
         "home_score": 3.0, "away_score": 1.0, "neutral": False},
    ]
    adapter = get_adapter("test_hockey_gap", "hockey", params)
    adapter.fit_results(results)  # today's production warm-up path
    # `fit_results` already consumed BOTH rows (including the same-day one),
    # but `rest_days` skips the stored "2026-01-01" entry (it equals
    # `game_date`) and falls back to "2025-12-30" -- 2 days, matching the
    # engine (previous test: r=2), not the 0 a naive "last observed date"
    # lookup would give.
    assert adapter.rest.rest_days("A", "2026-01-01") == 2
