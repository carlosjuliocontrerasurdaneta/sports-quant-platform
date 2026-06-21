"""Pruning of obsolete (out-of-season, already-settled) pick files."""
import pandas as pd

from sqp.pipeline.cleanup import prune_stale_candidates


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
