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


def test_out_of_season_only_flagged_rows_is_kept_until_settled(tmp_path):
    """Zero-stake/flagged rows ARE settled, so they are not free to delete.

    This test used to assert the opposite ("nothing actionable -> safe to drop").
    That premise was refuted on 2026-08-31 (N-A-1): `settle_candidates` grades
    every candidate row, stake-0 included. Since the prediction gate zeroes every
    stake, the old rule deleted whole leagues without any settlement check.
    """
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    _write(preds, "nba", [_cand_row(stake=0.0, flags="edge_exceeds_max_plausible")])
    pruned = prune_stale_candidates(preds, bets, active_leagues=set())
    assert pruned == []
    assert (preds / "candidates_nba.csv").exists()


def test_out_of_season_zero_stake_rows_are_pruned_once_settled(tmp_path):
    """The counterpart: once graded, the same file IS prunable. The fix delays
    pruning until settlement, it does not disable it."""
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    rows = [_cand_row(stake=0.0, flags="prediction_gate")]
    _write(preds, "nba", rows)
    _settle(bets, "nba", rows)
    pruned = prune_stale_candidates(preds, bets, active_leagues=set())
    assert pruned == ["nba"]
    assert not (preds / "candidates_nba.csv").exists()


def test_pruned_files_are_archived_before_deletion(tmp_path):
    """An out-of-season league is never overwritten again, so the daily run's
    pre-overwrite archive never fires for it: the prune must archive itself or
    the deletion is unrecoverable (N-A-1)."""
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    rows = [_cand_row(event_id="e1", generated_at="2026-06-20T11:00:00+00:00")]
    _write(preds, "nba", rows)
    _settle(bets, "nba", rows)
    assert prune_stale_candidates(preds, bets, active_leagues=set()) == ["nba"]
    archived = sorted(p.name for p in (preds / "archive").glob("*.csv"))
    # Candidates carry `generated_at`, so the archive key is the run day. The
    # predictions fixture has no such column, so `_archive_existing` falls back
    # to mtime -- hence only the prefix is pinned here.
    assert len(archived) == 2
    assert archived[0] == "candidates_nba_2026-06-20.csv"
    assert archived[1].startswith("predictions_nba_")
    # The archived copy is the real content, not an empty placeholder.
    assert len(pd.read_csv(preds / "archive" / archived[0])) == 1


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


# --- purge_old_artifacts -----------------------------------------------------

def _touch(p, content=""):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_purge_deletes_only_old_allowlisted_artifacts(tmp_path):
    from datetime import datetime, timezone
    from sqp.pipeline.cleanup import purge_old_artifacts
    now = datetime(2026, 7, 12, tzinfo=timezone.utc)
    arch = tmp_path / "data" / "predictions" / "archive"
    bets = tmp_path / "data" / "bets"
    odds = tmp_path / "data" / "odds"
    old_a = _touch(arch / "candidates_mlb_20260301.csv")   # 133d -> fuera
    new_a = _touch(arch / "candidates_mlb_20260710.csv")   # 2d   -> se queda
    old_r = _touch(bets / "clv_20260215.md")
    new_r = _touch(bets / "clv_20260711.md")
    old_c = _touch(odds / ".closing_credits_20260101")
    # Fuera de la allowlist: viejos pero INTOCABLES.
    settled = _touch(bets / "settled_mlb.csv", "event_id\n")
    gate = _touch(bets / "clv_gate.json", "{}")
    raw = _touch(odds / "odds_mlb_202603.csv", "captured_at\n")

    out = purge_old_artifacts(tmp_path, days=90, now=now)

    assert out == {"archive": 1, "clv_reports": 1, "closing_credits": 1}
    assert not old_a.exists() and not old_r.exists() and not old_c.exists()
    assert new_a.exists() and new_r.exists()
    assert settled.exists() and gate.exists() and raw.exists()


def test_purge_missing_dirs_is_noop(tmp_path):
    from sqp.pipeline.cleanup import purge_old_artifacts
    assert purge_old_artifacts(tmp_path, days=90) == {
        "archive": 0, "clv_reports": 0, "closing_credits": 0}


def test_purge_falls_back_to_mtime_when_name_has_no_date(tmp_path):
    import os
    import time
    from datetime import datetime, timezone
    from sqp.pipeline.cleanup import purge_old_artifacts
    now = datetime.now(timezone.utc)
    arch = tmp_path / "data" / "predictions" / "archive"
    stale = _touch(arch / "sin_fecha.csv")
    old = time.time() - 120 * 86400
    os.utime(stale, (old, old))
    fresh = _touch(arch / "reciente.csv")  # mtime actual -> se queda
    out = purge_old_artifacts(tmp_path, days=90, now=now)
    assert out["archive"] == 1
    assert not stale.exists() and fresh.exists()


def test_missing_event_id_skips_the_league_instead_of_raising(tmp_path):
    """`unsettled_completed_picks` runs in run_all BEFORE the league loop and
    outside any try. A predictions file without `event_id` used to raise KeyError
    from the merge and abort the whole day's generation, for every league, not
    just the malformed one (N-M-6). Its docstring promises the opposite: skip the
    league it cannot read."""
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    rows = [_cand_row(event_id="e1")]
    pd.DataFrame(rows).to_csv(preds / "candidates_mlb.csv", index=False)
    # start_time present, event_id absent: passes the old guard, breaks the merge
    pd.DataFrame([{"start_time": _PAST, "home": "A"}]).to_csv(
        preds / "predictions_mlb.csv", index=False)
    assert unsettled_completed_picks(preds, bets, ["mlb"], now=_NOW) == {}


def test_missing_event_id_on_candidates_also_skips(tmp_path):
    preds, bets = tmp_path / "p", tmp_path / "b"
    preds.mkdir(); bets.mkdir()
    rows = [{k: v for k, v in _cand_row().items() if k != "event_id"}]
    pd.DataFrame(rows).to_csv(preds / "candidates_mlb.csv", index=False)
    pd.DataFrame([{"event_id": "e1", "start_time": _PAST}]).to_csv(
        preds / "predictions_mlb.csv", index=False)
    assert unsettled_completed_picks(preds, bets, ["mlb"], now=_NOW) == {}
