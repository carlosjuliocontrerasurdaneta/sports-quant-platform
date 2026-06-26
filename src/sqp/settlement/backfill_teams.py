"""Backfill home/away/game_date on already-settled bets from captured odds.

The odds snapshots (data/odds/odds_<league>_*.csv) carry the same The Odds API
event_id as settled bets, so the join is exact. Idempotent: only empty cells are
filled; existing values are preserved. Reads no API (stored data only).
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd


def teams_from_odds(odds_dir: Path, league: str) -> dict[str, dict]:
    """event_id -> {home, away, game_date} from odds_<league>_*.csv snapshots."""
    out: dict[str, dict] = {}
    for f in sorted(odds_dir.glob(f"odds_{league}_*.csv")):
        df = pd.read_csv(f, usecols=lambda c: c in ("event_id", "home", "away", "commence_time"))
        for r in df.itertuples():
            eid = str(r.event_id)
            if eid in out:
                continue
            out[eid] = {"home": str(r.home), "away": str(r.away),
                        "game_date": str(r.commence_time)[:10]}
    return out


def backfill_settled_file(settled_path: Path, meta: dict[str, dict]) -> tuple[int, int]:
    """Fill empty home/away/game_date rows in one settled file. Returns
    (filled, unresolved). Writes only if something changed (idempotent)."""
    df = pd.read_csv(settled_path).fillna("")
    if df.empty:
        return 0, 0
    for col in ("home", "away", "game_date"):
        if col not in df.columns:
            df[col] = ""
    filled = unresolved = 0
    for i in df.index:
        if str(df.at[i, "home"]).strip():
            continue
        m = meta.get(str(df.at[i, "event_id"]))
        if not m:
            unresolved += 1
            continue
        df.at[i, "home"], df.at[i, "away"], df.at[i, "game_date"] = (
            m["home"], m["away"], m["game_date"])
        filled += 1
    if filled:
        df.to_csv(settled_path, index=False)
    return filled, unresolved
