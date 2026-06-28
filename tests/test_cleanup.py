"""Pruning of obsolete (out-of-season, already-settled) pick files."""
import pandas as pd

from sqp.pipeline.cleanup import (prune_stale_candidates,
                                  unsettled_completed_picks)

_NOW = "2026-06-28T12:00:00Z"
_PAST = "2026-06-27T23:00:00Z"   # already commenced relative to _NOW
_FUTURE = "2026-06-29T18:00:00Z"  # not yet commenced


def _cand_row(event_id="e1", market="h2h", selection="A", line="",
              stake=9.0, flags="", generated_at="2026-01-01T00:00:00+00:00"):
    return {"event_id": event_id, "market": market, "selection": selection,
            "line": line, "price_decimal": 2.0, "estimated_probability": 0.55,
            "implied_probability_novig": 0.50, "estimated_edge": 0.10,
            "kelly_stake_pct": 0.01, "stake": stake, "data_label": "real",
            "flags": flags, "generated_at": generated_at}


def _write(predictions_dir, league, rows):
    pd.DataFrame(rows).to_csv(predictions_dir / f"candidates_{league}.csv", index=False)
    pd.DataFrame([{"event_id": r["event_id"], "home": "A", "away": "B"} for r in rows]).to_csv(
        predictions_dir / f"predictions_{league}.csv", index=False)


def _settle(bets_dir, league, rows):
    settled = [{**r, "result": "win", "pnl": 1.0} for r in rows]
    pd.DataFrame(settled).to_csv(bets_dir / f"settled_{league}.csv", index=False)


def test_in_season_league_is_kept(tmp_path):
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    _write(preds, "wnba", [_cand_row()])
    pruned = prune_stale_candidates(preds, bets, active_leagues={"wnba"})
    assert pruned == []
    assert (preds / "candidates_wnba.csv").exists()


def test_out_of_season_fully_settled_is_pruned(tmp_path):
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    rows = [_cand_row(event_id="e1"), _cand_row(event_id="e2", selection="C")]
    _write(preds, "nba", rows)
    _settle(bets, "nba", rows)
    pruned = prune_stale_candidates(preds, bets, active_leagues={"wnba"})
    assert pruned == ["nba"]
    assert not (preds / "candidates_nba.csv").exists()
    assert not (preds / "predictions_nba.csv").exists()


def test_out_of_season_with_unsettled_bet_is_kept(tmp_path):
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    rows = [_cand_row(event_id="e1"), _cand_row(event_id="e2", selection="C")]
    _write(preds, "nba", rows)
    _settle(bets, "nba", rows[:1])  # only e1 graded; e2 still pending
    pruned = prune_stale_candidates(preds, bets, active_leagues=set())
    assert pruned == []
    assert (preds / "candidates_nba.csv").exists()


def test_out_of_season_no_settled_file_is_kept(tmp_path):
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    _write(preds, "nba", [_cand_row()])
    pruned = prune_stale_candidates(preds, bets, active_leagues=set())
    assert pruned == []  # cannot verify settlement -> keep


def test_out_of_season_only_flagged_rows_is_pruned(tmp_path):
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    # no actionable picks (flagged + zero stake): nothing to settle, safe to drop
    _write(preds, "nba", [_cand_row(stake=0.0, flags="edge_exceeds_max_plausible")])
    pruned = prune_stale_candidates(preds, bets, active_leagues=set())
    assert pruned == ["nba"]
    assert not (preds / "candidates_nba.csv").exists()


# --- M2 guard: commenced-but-unsettled picks about to be overwritten ----------

def _write_with_times(predictions_dir, league, rows, start_times):
    pd.DataFrame(rows).to_csv(predictions_dir / f"candidates_{league}.csv", index=False)
    pd.DataFrame([{"event_id": r["event_id"], "home": "A", "away": "B",
                   "start_time": st} for r, st in zip(rows, start_times)]).to_csv(
        predictions_dir / f"predictions_{league}.csv", index=False)


def test_commenced_unsettled_pick_is_flagged(tmp_path):
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    _write_with_times(preds, "mlb", [_cand_row(event_id="e1")], [_PAST])
    at_risk = unsettled_completed_picks(preds, bets, ["mlb"], now=_NOW)
    assert at_risk == {"mlb": 1}


def test_commenced_settled_pick_is_not_flagged(tmp_path):
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    rows = [_cand_row(event_id="e1")]
    _write_with_times(preds, "mlb", rows, [_PAST])
    _settle(bets, "mlb", rows)
    assert unsettled_completed_picks(preds, bets, ["mlb"], now=_NOW) == {}


def test_future_game_is_not_flagged(tmp_path):
    # Overwriting a not-yet-commenced pick is the normal daily refresh, not a loss.
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    _write_with_times(preds, "mlb", [_cand_row(event_id="e1")], [_FUTURE])
    assert unsettled_completed_picks(preds, bets, ["mlb"], now=_NOW) == {}


def test_scaled_pick_with_flag_still_counts(tmp_path):
    # A globally/daily-scaled pick has flags set but a real positive stake; it is
    # settled like any other, so it must NOT be excluded by the flag.
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    _write_with_times(preds, "mlb",
                      [_cand_row(event_id="e1", flags="global_exposure_scaled")], [_PAST])
    assert unsettled_completed_picks(preds, bets, ["mlb"], now=_NOW) == {"mlb": 1}


def test_demo_and_zero_stake_picks_are_ignored(tmp_path):
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    demo = _cand_row(event_id="e1"); demo["data_label"] = "demo_synthetic"
    zero = _cand_row(event_id="e2", stake=0.0, flags="market_paused")
    _write_with_times(preds, "mlb", [demo, zero], [_PAST, _PAST])
    assert unsettled_completed_picks(preds, bets, ["mlb"], now=_NOW) == {}


def test_missing_predictions_file_does_not_block(tmp_path):
    # No start_time source -> cannot tell which games commenced; skip, never block
    # (archive/ still makes an overwrite recoverable).
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    pd.DataFrame([_cand_row(event_id="e1")]).to_csv(
        preds / "candidates_mlb.csv", index=False)
    assert unsettled_completed_picks(preds, bets, ["mlb"], now=_NOW) == {}


def test_default_now_uses_wall_clock(tmp_path):
    # now=None must resolve to the current UTC time (regression: the datetime
    # import was once stripped, which only blew up on this default path).
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    _write_with_times(preds, "mlb", [_cand_row(event_id="e1")], ["2000-01-01T00:00:00Z"])
    assert unsettled_completed_picks(preds, bets, ["mlb"]) == {"mlb": 1}


def test_only_requested_leagues_are_checked(tmp_path):
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    _write_with_times(preds, "mlb", [_cand_row(event_id="e1")], [_PAST])
    _write_with_times(preds, "nba", [_cand_row(event_id="x1")], [_PAST])
    # nba holds an at-risk pick but is not in the overwrite set -> not reported.
    assert unsettled_completed_picks(preds, bets, ["mlb"], now=_NOW) == {"mlb": 1}
