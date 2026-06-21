"""Consolidated pick history + performance-pattern analysis.

Replays the realized-ROI backtest over every league with captured historical
odds and produces ONE consolidated per-bet history (team, side home/away or
Over/Under, result) at ``data/processed/pick_history.csv``. From that history it
derives hit-rate / ROI breakdowns used by both the CLI
(``scripts/build_pick_history.py``) and the daily HTML dashboard:

  - by market (moneyline / handicap / totals)
  - by situation (market x side), highest hit-rate first
  - moneyline & handicap: home vs away (frequency = ``n`` and hit rate)
  - totals: Over vs Under (frequency = ``n`` and hit rate)
  - per-team wins/losses (moneyline + handicap selections)

This is a BACKTEST over a single pre-game snapshot proxy for closing odds
(limited coverage). Hit rate is realized but NOT a profit guarantee, and the
estimated edge is NOT realized ROI. Audit before operating.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sqp.backtesting.roi_engine import (discover_leagues_with_odds,
                                        load_closing_odds, realized_roi_backtest)
from sqp.config import ROOT, Settings
from sqp.logging_config import get_logger
from sqp.pipeline.daily import _league_meta
from sqp.storage.results_store import ResultsStore
from sqp.storage.starters import StartersStore

log = get_logger("sqp.patterns")

MARKET_LABEL = {"h2h": "moneyline", "spreads": "handicap", "totals": "totals"}
HISTORY_COLS = ["league", "date", "event_id", "away", "home", "market",
                "market_label", "selection", "side", "line", "price_decimal",
                "estimated_probability", "estimated_edge", "stake", "result", "pnl"]
MIN_N_SITUATION = 30   # min graded bets to trust a situational hit rate
MIN_N_TEAM = 20        # min graded bets to list a team

PICK_HISTORY_PATH = ROOT / "data" / "processed" / "pick_history.csv"


def build_pick_history(settings: Settings | None = None, *, write: bool = True,
                       path: Path | None = None) -> pd.DataFrame:
    """Replay the realized-ROI backtest over every league with captured odds and
    return the consolidated per-bet history. When ``write`` is True the frame is
    persisted to ``path`` (default ``data/processed/pick_history.csv``).

    Returns an empty frame (with ``HISTORY_COLS``) when no league has captured
    odds yet; callers must treat that as "no history", never as an error.
    """
    settings = settings or Settings.load()
    leagues = discover_leagues_with_odds(ROOT)
    if not leagues:
        log.warning("No leagues with captured odds; run backfill_historical_odds.py.")
        return pd.DataFrame(columns=HISTORY_COLS)

    frames: list[pd.DataFrame] = []
    for league in leagues:
        odds = load_closing_odds(ROOT, league)
        if not odds:
            continue
        results = ResultsStore(ROOT).load(league)
        meta = _league_meta(league)
        if meta["family"] == "baseball":
            StartersStore(ROOT).attach(league, results)
        res = realized_roi_backtest(results, odds, league, meta["family"],
                                    meta.get("league_params"), risk=settings.risk,
                                    bankroll=settings.bankroll, warmup=60)
        settled = res.get("settled", pd.DataFrame())
        if not settled.empty:
            frames.append(settled)

    if not frames:
        log.warning("No settled bets produced; pick history is empty.")
        return pd.DataFrame(columns=HISTORY_COLS)

    hist = pd.concat(frames, ignore_index=True)
    hist["market_label"] = hist["market"].map(MARKET_LABEL).fillna(hist["market"])
    cols = [c for c in HISTORY_COLS if c in hist.columns]
    hist = hist[cols].sort_values(["league", "date"]).reset_index(drop=True)

    if write:
        out = Path(path) if path else PICK_HISTORY_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        hist.to_csv(out, index=False)
        log.info("Historial consolidado de picks -> %s (%d picks)", out, len(hist))
    return hist


def load_pick_history(path: Path | None = None) -> pd.DataFrame:
    """Load the consolidated pick history CSV; empty frame if absent."""
    p = Path(path) if path else PICK_HISTORY_PATH
    if not p.exists() or p.stat().st_size < 2:
        return pd.DataFrame(columns=HISTORY_COLS)
    return pd.read_csv(p)


def hit_rate(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Hit rate / ROI over GRADED bets only (win/loss; push & void excluded).

    ``n`` is the number of graded picks in the group -- i.e. the frequency the
    user asks about (home vs away, Over vs Under).
    """
    g = df[df["result"].isin(["win", "loss"])]
    if g.empty:
        return pd.DataFrame()
    agg = (g.groupby(by)
           .agg(n=("result", "size"), wins=("result", lambda s: (s == "win").sum()),
                staked=("stake", "sum"), pnl=("pnl", "sum"),
                mean_edge=("estimated_edge", "mean")).reset_index())
    agg["losses"] = agg["n"] - agg["wins"]
    agg["hit_rate_%"] = (agg["wins"] / agg["n"] * 100).round(1)
    agg["roi_%"] = (agg["pnl"] / agg["staked"] * 100).round(2)
    agg["mean_edge"] = agg["mean_edge"].round(4)
    return agg


def _by_hit_rate(df: pd.DataFrame, *, ascending: bool = False) -> pd.DataFrame:
    """Sort by hit rate, tolerating the column-less empty frame ``hit_rate``
    returns when a group (e.g. an absent market) has no graded bets."""
    if df is None or df.empty or "hit_rate_%" not in df.columns:
        return df if df is not None else pd.DataFrame()
    return df.sort_values("hit_rate_%", ascending=ascending)


def pattern_breakdowns(hist: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return the labelled breakdown tables for the dashboard / CLI.

    Keys: ``by_market``, ``by_situation``, ``moneyline_side``, ``handicap_side``,
    ``totals_side``, ``team_top``, ``team_bottom``. Empty input yields ``{}``.
    """
    if hist is None or hist.empty:
        return {}
    h = hist.copy()
    if "market_label" not in h.columns:
        h["market_label"] = h["market"].map(MARKET_LABEL).fillna(h["market"])

    by_market = _by_hit_rate(hit_rate(h, ["market_label"]))

    situation = hit_rate(h, ["market_label", "side"])
    if not situation.empty:
        situation = _by_hit_rate(situation[situation["n"] >= MIN_N_SITUATION])

    ml = _by_hit_rate(hit_rate(h[h["market"] == "h2h"], ["side"]))
    sp = _by_hit_rate(hit_rate(h[h["market"] == "spreads"], ["side"]))
    to = _by_hit_rate(hit_rate(h[h["market"] == "totals"], ["side"]))

    team = hit_rate(h[h["market"].isin(["h2h", "spreads"])], ["selection"])
    if not team.empty:
        team = team[team["n"] >= MIN_N_TEAM].rename(columns={"selection": "team"})
    team_top = _by_hit_rate(team).head(10)
    team_bottom = _by_hit_rate(team, ascending=True).head(10)

    return {"by_market": by_market, "by_situation": situation,
            "moneyline_side": ml, "handicap_side": sp, "totals_side": to,
            "team_top": team_top, "team_bottom": team_bottom}


def _freq_leader(side_df: pd.DataFrame) -> tuple[str, int] | None:
    """(side, n) of the most frequently picked side, or None if no data."""
    if side_df is None or side_df.empty:
        return None
    row = side_df.loc[side_df["n"].idxmax()]
    return str(row["side"]), int(row["n"])


def conclusions(breaks: dict[str, pd.DataFrame]) -> list[str]:
    """Short, data-driven reading of the breakdowns (Spanish, for the dashboard).

    Frequency answers come from the ``n`` column (graded picks per side).
    """
    if not breaks:
        return ["Sin historial suficiente para concluir patrones todavia."]
    out: list[str] = []
    bm = breaks.get("by_market")
    if bm is not None and not bm.empty:
        best = bm.iloc[0]
        out.append(f"Mercado con mayor tasa de acierto: **{best['market_label']}** "
                   f"({best['hit_rate_%']}% en {int(best['n'])} picks, "
                   f"ROI {best['roi_%']}%).")
    sit = breaks.get("by_situation")
    if sit is not None and not sit.empty:
        s = sit.iloc[0]
        out.append(f"Situacion con mayor acierto: **{s['market_label']} / {s['side']}** "
                   f"({s['hit_rate_%']}% en {int(s['n'])} picks).")
    ml = _freq_leader(breaks.get("moneyline_side"))
    if ml:
        out.append(f"Moneyline: mas frecuente en **{ml[0]}** ({ml[1]} picks graduados).")
    sp = _freq_leader(breaks.get("handicap_side"))
    if sp:
        out.append(f"Handicap: mas frecuente en **{sp[0]}** ({sp[1]} picks graduados).")
    to = _freq_leader(breaks.get("totals_side"))
    if to:
        out.append(f"Totales: mas frecuente en **{to[0]}** ({to[1]} picks graduados).")
    return out
