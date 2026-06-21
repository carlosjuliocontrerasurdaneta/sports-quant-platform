"""Realized-ROI backtest over captured historical odds + final results.

Unlike the calibration backtest (engine.py), this measures REALIZED ROI: it
replays the live pipeline's exact staking logic against the odds as they stood
before each game (the last captured snapshot strictly before commence_time) and
grades the resulting bets with the production settlement code.

No lookahead: ratings are built strictly walk-forward (each game estimated
before it is observed), and only odds snapshots dated before commence are used.
Coverage is limited to games for which historical odds were captured.

Realized ROI is the field truth that calibration cannot provide; it is still a
backtest (selection, regime change, single closing snapshot rather than true
closing line) and never a profit guarantee.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.pipeline.daily import (_consensus_lines, _novig_probs, _pick_main_lines,
                                _spread_novig)
from sqp.risk.kelly import edge, kelly_fraction_stake
from sqp.settlement.settle import settle_candidates
from sqp.sports.registry import get_adapter
from sqp.sports.team_names import normalize_key


def discover_leagues_with_odds(root: Path) -> list[str]:
    """Leagues that have captured odds snapshots (data/odds/odds_<league>_<YYYYMM>.csv).
    League ids carry no underscore, so the league is everything between the
    'odds_' prefix and the final '_<month>' segment."""
    leagues: set[str] = set()
    for f in (root / "data" / "odds").glob("odds_*.csv"):
        core = f.stem[len("odds_"):]
        if "_" in core:
            leagues.add(core.rsplit("_", 1)[0])
    return sorted(leagues)


def load_closing_odds(root: Path, league: str) -> dict[str, EventOdds]:
    """event_id -> EventOdds built from the last snapshot strictly before each
    event's commence_time (the captured proxy for closing odds)."""
    odds_dir = root / "data" / "odds"
    files = sorted(odds_dir.glob(f"odds_{league}_*.csv"))
    if not files:
        return {}
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    out: dict[str, EventOdds] = {}
    for eid, g in df.groupby("event_id"):
        commence = str(g["commence_time"].iloc[0])
        pre = g[g["captured_at"].astype(str) < commence]
        if pre.empty:
            continue
        snap = pre[pre["captured_at"] == pre["captured_at"].max()]
        lines = [MarketLine(market=str(r.market), bookmaker=str(r.bookmaker),
                            outcome=str(r.outcome), price_decimal=float(r.price_decimal),
                            point=(None if pd.isna(r.point) else float(r.point)))
                 for r in snap.itertuples()]
        ev = Event(event_id=str(eid), sport_key="bt", league=league,
                   home=str(snap["home"].iloc[0]), away=str(snap["away"].iloc[0]),
                   start_time=commence, data_label="real")
        out[str(eid)] = EventOdds(event=ev, lines=lines)
    return out


def _match_index(odds_by_id: dict[str, EventOdds]) -> dict[tuple[str, str], list]:
    idx: dict[tuple[str, str], list] = defaultdict(list)
    for eo in odds_by_id.values():
        key = (normalize_key(eo.event.home), normalize_key(eo.event.away))
        idx[key].append((str(eo.event.start_time)[:10], eo))
    return idx


def _match_result(r: dict, idx: dict[tuple[str, str], list], used: set[str]) -> EventOdds | None:
    """Match a result row to its odds event by normalized (home, away) and a
    commence date within +-1 day (UTC vs local date drift). Each odds event is
    consumed at most once."""
    key = (normalize_key(r["home"]), normalize_key(r["away"]))
    cands = idx.get(key)
    if not cands:
        return None
    rday = str(r.get("date", ""))[:10]
    best = None
    for day, eo in cands:
        if eo.event.event_id in used:
            continue
        if abs(_day_diff(day, rday)) <= 1:
            best = eo
            break
    if best is not None:
        used.add(best.event.event_id)
    return best


def _day_diff(a: str, b: str) -> int:
    from datetime import date
    try:
        da = date.fromisoformat(a[:10])
        db = date.fromisoformat(b[:10])
        return (da - db).days
    except ValueError:
        return 99


def _model_map(est, event: Event, spread, total) -> dict:
    mm = {("h2h", event.home, None): est.home_win_estimated_probability,
          ("h2h", event.away, None): est.away_win_estimated_probability}
    if est.draw_estimated_probability is not None:
        mm[("h2h", "Draw", None)] = est.draw_estimated_probability
    if est.home_cover_estimated_probability is not None and spread is not None:
        mm[("spreads", event.home, spread)] = est.home_cover_estimated_probability
        mm[("spreads", event.away, -spread)] = est.away_cover_estimated_probability
    if est.over_estimated_probability is not None and total is not None:
        mm[("totals", "Over", total)] = est.over_estimated_probability
        mm[("totals", "Under", total)] = est.under_estimated_probability
    return mm


def realized_roi_backtest(results: list[dict], odds_by_id: dict[str, EventOdds],
                          league: str, family: str, league_params: dict | None,
                          risk, bankroll: float, warmup: int = 60,
                          bet_from_date: str | None = None) -> dict:
    """Replay staking against pre-game odds and grade against final scores.
    `risk` is a RiskConfig (kelly_fraction, max_stake_pct, min_edge,
    max_plausible_edge, market_shrink).

    `bet_from_date` ('YYYY-MM-DD'): when set, only games on or after this date
    are bet and counted; earlier games still feed the walk-forward ratings.
    This is the out-of-sample evaluation window: parameters frozen on the train
    period (date < bet_from_date) are scored only on later, unseen games."""
    adapter = get_adapter(league, family, league_params)
    idx = _match_index(odds_by_id)
    used: set[str] = set()
    cand_rows: list[dict] = []
    scores: dict[str, tuple[int, int, str]] = {}
    n_matched = 0
    for i, r in enumerate(results):
        in_window = bet_from_date is None or str(r.get("date", ""))[:10] >= bet_from_date
        if i >= warmup and in_window:
            eo = _match_result(r, idx, used)
            if eo is not None:
                n_matched += 1
                ev = Event(event_id=eo.event.event_id, sport_key="bt", league=league,
                           home=eo.event.home, away=eo.event.away,
                           start_time=eo.event.start_time, data_label="real",
                           home_pitcher=r.get("home_starter"), away_pitcher=r.get("away_starter"))
                spread, total = _pick_main_lines(eo)
                est = adapter.estimate(ev, spread, total)
                cons = _consensus_lines(eo)
                # Map final score to the odds' home/away orientation.
                if normalize_key(r["home"]) == normalize_key(eo.event.home):
                    hs, as_ = int(r["home_score"]), int(r["away_score"])
                else:
                    hs, as_ = int(r["away_score"]), int(r["home_score"])
                scores[eo.event.event_id] = (hs, as_, eo.event.home)
                for key, p_model in _model_map(est, ev, spread, total).items():
                    price = cons.get(key)
                    if price is None or p_model is None:
                        continue
                    if key[0] == "spreads":
                        fair = _spread_novig(cons, ev.home, ev.away, spread).get(key[1])
                    else:
                        fair = _novig_probs(cons, key[0], key[2]).get(key[1])
                    s = risk.market_shrink
                    p_used = (1.0 - s) * p_model + s * fair if (fair is not None and s > 0) else p_model
                    e = edge(p_used, price)
                    stake, _pct = kelly_fraction_stake(
                        p_used, price, bankroll, risk.kelly_fraction,
                        risk.max_stake_pct, risk.min_edge)
                    if stake <= 0 or e > risk.max_plausible_edge:
                        continue  # below edge floor or flagged as implausible: not bet
                    side = key[1] if key[0] == "totals" else (
                        "home" if key[1] == ev.home else "away")
                    cand_rows.append({
                        "league": league, "date": str(r.get("date", ""))[:10],
                        "event_id": eo.event.event_id, "home": ev.home, "away": ev.away,
                        "market": key[0], "selection": key[1], "side": side,
                        "line": key[2], "price_decimal": price,
                        "stake": stake, "estimated_edge": round(e, 4),
                        "estimated_probability": round(p_used, 4)})
        adapter.observe(r)
    cands = pd.DataFrame(cand_rows)
    settled = settle_candidates(cands, scores) if not cands.empty else pd.DataFrame()
    out = _summarize(league, settled, n_matched)
    out["settled"] = settled  # per-bet detail (team, side, result) for history/audit
    return out


def _summarize(league: str, settled: pd.DataFrame, n_matched: int) -> dict:
    if settled.empty:
        return {"league": league, "n_events_matched": n_matched, "n_bets": 0,
                "by_market": pd.DataFrame(), "note": "no graded bets"}
    graded = settled[settled["result"].isin(["win", "loss"])]
    staked = float(graded["stake"].sum())
    pnl = float(settled["pnl"].sum())
    by_market = (settled.assign(graded=settled["result"].isin(["win", "loss"]))
                 .groupby("market")
                 .agg(n=("result", "size"),
                      wins=("result", lambda s: (s == "win").sum()),
                      staked=("stake", "sum"), pnl=("pnl", "sum"),
                      mean_edge=("estimated_edge", "mean")).reset_index())
    by_market["realized_roi"] = (by_market["pnl"] / by_market["staked"]).round(4)
    by_market["mean_edge"] = by_market["mean_edge"].round(4)
    return {"league": league, "n_events_matched": n_matched, "n_bets": int(len(settled)),
            "n_graded": int(len(graded)), "staked": round(staked, 2),
            "pnl": round(pnl, 2),
            "realized_roi": round(pnl / staked, 4) if staked else 0.0,
            "mean_estimated_edge": round(float(settled["estimated_edge"].mean()), 4),
            "by_market": by_market,
            "note": ("Realized ROI over captured pre-game odds; single snapshot "
                     "proxy for closing, limited coverage. Not a profit guarantee.")}
