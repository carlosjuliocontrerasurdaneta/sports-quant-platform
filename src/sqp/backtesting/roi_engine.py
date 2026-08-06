"""Realized-ROI backtest over captured historical odds + final results.

Unlike the calibration backtest (engine.py), this measures REALIZED ROI: it
replays the core single-league staking logic against the odds as they stood
before each game (the last captured snapshot strictly before commence_time) and
grades the resulting bets with the production settlement code.

No lookahead: ratings are built strictly walk-forward (each game estimated
before it is observed), and only odds snapshots dated before commence are used.
Coverage is limited to games for which historical odds were captured.

This replays market-shrink, edge penalties, Kelly staking and the per-league
daily exposure cap, but intentionally does NOT apply today's live calibrator to
past rows (that would leak a model trained with later outcomes). The global
cross-league cap, dynamic bankroll, shadow mode and CLV gate are also outside
this single-league benchmark. It is therefore not an exact reconstruction of
live capital deployment and cannot prove a production edge.

Realized ROI is the field truth that calibration cannot provide; it is still a
backtest (selection, regime change, single closing snapshot rather than true
closing line) and never a profit guarantee.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.markets.edge import adjusted_edge
from sqp.pipeline.daily import (_consensus_counts, _consensus_lines, _novig_probs,
                                _pick_main_lines, _spread_novig)
from sqp.pipeline.probabilities import build_model_map
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


def load_closing_odds(root: Path, league: str,
                      max_age_min: float | None = None) -> dict[str, EventOdds]:
    """event_id -> EventOdds built from the last snapshot strictly before each
    event's commence_time (the captured proxy for closing odds).

    ``max_age_min`` drops events whose last pre-commence snapshot is older than
    that many minutes before commence: a morning snapshot is a valid *entry*
    proxy for the ROI backtest (default, None) but not a *closing* proxy for
    CLV — when entry and "close" come from the same snapshot, CLV is 0 by
    construction and dilutes the median toward zero."""
    odds_dir = root / "data" / "odds"
    files = sorted(odds_dir.glob(f"odds_{league}_*.csv"))
    if not files:
        return {}
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    out: dict[str, EventOdds] = {}
    for eid, g in df.groupby("event_id"):
        # Compare as timestamps, not strings: captured_at mixes '+00:00' and 'Z'
        # suffixes across files and lexicographic order is not temporal order
        # (audit 2026-07-24, M-30).
        cap_ts = pd.to_datetime(g["captured_at"], utc=True, errors="coerce")
        # El proveedor CORRIGE la hora de inicio sobre la marcha, así que vale
        # la última reportada, no la de una fila arbitraria: con la obsoleta un
        # snapshot ya EN VIVO pasaba el filtro y se tomaba como cierre, con un
        # precio que refleja el partido en curso (KI-019, 2026-08-05).
        latest = cap_ts.idxmax() if cap_ts.notna().any() else g.index[0]
        commence = str(g.loc[latest, "commence_time"])
        commence_ts = pd.to_datetime(commence, utc=True, errors="coerce")
        if pd.isna(commence_ts):
            continue
        pre_mask = cap_ts < commence_ts
        pre = g[pre_mask]
        if pre.empty:
            continue
        last = cap_ts[pre_mask].max()
        if max_age_min is not None:
            age_min = (commence_ts - last).total_seconds() / 60.0
            if age_min > max_age_min:
                continue
        snap = pre[cap_ts[pre_mask] == last]
        lines = [MarketLine(market=str(r.market), bookmaker=str(r.bookmaker),
                            outcome=str(r.outcome), price_decimal=float(r.price_decimal),
                            point=(None if pd.isna(r.point) else float(r.point)))
                 for r in snap.itertuples()]
        ev = Event(event_id=str(eid), sport_key="bt", league=league,
                   home=str(snap["home"].iloc[0]), away=str(snap["away"].iloc[0]),
                   start_time=commence, data_label="real")
        out[str(eid)] = EventOdds(event=ev, lines=lines)
    return out


def _pair_key(home: str, away: str, order_insensitive: bool):
    """Match key for a (home, away) pair. Team sports keep orientation (home
    advantage distinguishes the two games of a series); tennis has no home/away,
    so players match order-insensitively (frozenset)."""
    a, b = normalize_key(home), normalize_key(away)
    return frozenset((a, b)) if order_insensitive else (a, b)


def _match_index(odds_by_id: dict[str, EventOdds], order_insensitive: bool = False) -> dict:
    idx: dict = defaultdict(list)
    for eo in odds_by_id.values():
        idx[_pair_key(eo.event.home, eo.event.away, order_insensitive)].append(
            (str(eo.event.start_time)[:10], eo))
    return idx


def _match_result(r: dict, idx: dict, used: set[str],
                  order_insensitive: bool = False) -> EventOdds | None:
    """Match a result row to its odds event by normalized players/teams and a
    commence date within +-1 day (UTC vs local date drift). Each odds event is
    consumed at most once. Tennis matches order-insensitively (no home/away).

    Picks the candidate with the SMALLEST day distance (exact date first),
    breaking ties by commence_time: taking the first candidate within the
    window could pair a bet's odds with the score of the adjacent day's game
    in consecutive-day series and doubleheaders (audit 2026-07-24, I-4)."""
    cands = idx.get(_pair_key(r["home"], r["away"], order_insensitive))
    if not cands:
        return None
    rday = str(r.get("date", ""))[:10]
    best = None
    best_rank: tuple[int, str] | None = None
    for day, eo in cands:
        if eo.event.event_id in used:
            continue
        dist = abs(_day_diff(day, rday))
        if dist > 1:
            continue
        rank = (dist, str(eo.event.start_time))
        if best_rank is None or rank < best_rank:
            best, best_rank = eo, rank
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


def _apply_backtest_daily_cap(candidates: pd.DataFrame, bankroll: float,
                              cap_pct: float) -> pd.DataFrame:
    """Apply the production per-league exposure cap independently per game day."""
    if candidates.empty or cap_pct <= 0 or bankroll <= 0 or "date" not in candidates:
        return candidates
    out = candidates.copy()
    cap = bankroll * cap_pct
    for _day, idx in out.groupby("date").groups.items():
        total = float(out.loc[idx, "stake"].clip(lower=0).sum())
        if total > cap and total > 0:
            out.loc[idx, "stake"] = (out.loc[idx, "stake"] * (cap / total)).round(2)
    return out


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
    # Orden determinista: el emparejamiento resultado<->cuotas es codicioso con
    # consumo (`used`), asi que el reparto depende del ORDEN de entrada. Con
    # dobles jornadas o series en dias consecutivos dos resultados compiten por
    # las mismas cuotas y barajar la entrada cambiaba el ROI: el backtest no era
    # reproducible bit a bit (auditoria 2026-08-05, F-11).
    # La clave debe determinar el orden por CONTENIDO. Con solo
    # (fecha, home, away) los dos partidos de una doble jornada empatan, y
    # `sorted` es estable: preservaba el orden de entrada y el defecto seguia.
    results = sorted(results, key=lambda r: (str(r.get("date", "")),
                                             str(r.get("home", "")),
                                             str(r.get("away", "")),
                                             str(r.get("game_id", "")),
                                             str(r.get("home_score", "")),
                                             str(r.get("away_score", ""))))
    order_insensitive = family == "tennis"  # players have no home/away orientation
    idx = _match_index(odds_by_id, order_insensitive)
    used: set[str] = set()
    cand_rows: list[dict] = []
    scores: dict[str, tuple[int, int, str]] = {}
    n_matched = 0
    for i, r in enumerate(results):
        in_window = bet_from_date is None or str(r.get("date", ""))[:10] >= bet_from_date
        if i >= warmup and in_window:
            eo = _match_result(r, idx, used, order_insensitive)
            if eo is not None:
                n_matched += 1
                ev = Event(event_id=eo.event.event_id, sport_key="bt", league=league,
                           home=eo.event.home, away=eo.event.away,
                           start_time=eo.event.start_time, data_label="real",
                           home_pitcher=r.get("home_starter"), away_pitcher=r.get("away_starter"))
                spread, total = _pick_main_lines(eo)
                est = adapter.estimate(ev, spread, total)
                cons = _consensus_lines(eo)
                cons_n = _consensus_counts(eo)
                # Map final score to the odds' home/away orientation.
                if normalize_key(r["home"]) == normalize_key(eo.event.home):
                    hs, as_ = int(r["home_score"]), int(r["away_score"])
                else:
                    hs, as_ = int(r["away_score"]), int(r["home_score"])
                scores[eo.event.event_id] = (hs, as_, eo.event.home)
                for key, p_model in build_model_map(est, ev, spread, total).items():
                    price = cons.get(key)
                    if price is None or p_model is None:
                        continue
                    if key[0] == "spreads":
                        fair = _spread_novig(cons, ev.home, ev.away, spread).get(key[1])
                    else:
                        fair = _novig_probs(cons, key[0], key[2],
                                            three_way=(family == "soccer")).get(key[1])
                    if fair is None:
                        continue  # incomplete market: the live pipeline cannot remove vig
                    s = risk.market_shrink
                    p_used = (1.0 - s) * p_model + s * fair if (fair is not None and s > 0) else p_model
                    e = edge(p_used, price)
                    # Same EV penalty as the live pipeline (no-op when off), so the
                    # realized-ROI backtest replays the actual staking. Calibration
                    # is still excluded here by design (see module docstring).
                    adj = adjusted_edge(p_used, price, fair, cons_n.get(key),
                                        uncertainty_penalty=risk.uncertainty_penalty,
                                        anomaly_edge_gap=risk.anomaly_edge_gap,
                                        anomaly_extra_penalty=risk.anomaly_extra_penalty,
                                        low_book_penalty=risk.low_book_penalty,
                                        min_books_for_consensus=risk.min_books_for_consensus)
                    stake, _pct = kelly_fraction_stake(
                        adj.effective_probability, price, bankroll, risk.kelly_fraction,
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
    if not cands.empty:
        cands = _apply_backtest_daily_cap(
            cands, bankroll, getattr(risk, "max_daily_exposure_pct", 0.0))
    settled = (settle_candidates(cands, scores, three_way=(family == "soccer"))
               if not cands.empty else pd.DataFrame())
    out = _summarize(league, settled, n_matched)
    out["settled"] = settled  # per-bet detail (team, side, result) for history/audit
    return out


def _summarize(league: str, settled: pd.DataFrame, n_matched: int) -> dict:
    if settled.empty:
        return {"league": league, "n_events_matched": n_matched, "n_bets": 0,
                "by_market": pd.DataFrame(), "note": "no graded bets"}
    graded_mask = settled["result"].isin(["win", "loss"])
    graded = settled[graded_mask]
    staked = float(graded["stake"].sum())
    pnl = float(settled["pnl"].sum())
    # Denominador por mercado = stake REALMENTE arriesgado (win/loss), igual
    # que el ROI global: incluir stakes de push/void deflactaba el ROI de los
    # mercados con empates/cancelados (auditoria 2026-07-24, M-29).
    by_market = (settled.assign(stake_graded=settled["stake"].where(graded_mask, 0.0))
                 .groupby("market")
                 .agg(n=("result", "size"),
                      wins=("result", lambda s: (s == "win").sum()),
                      staked=("stake_graded", "sum"), pnl=("pnl", "sum"),
                      mean_edge=("estimated_edge", "mean")).reset_index())
    by_market["realized_roi"] = (by_market["pnl"]
                                 / by_market["staked"].where(by_market["staked"] > 0)).round(4)
    by_market["mean_edge"] = by_market["mean_edge"].round(4)
    return {"league": league, "n_events_matched": n_matched, "n_bets": int(len(settled)),
            "n_graded": int(len(graded)), "staked": round(staked, 2),
            "pnl": round(pnl, 2),
            "realized_roi": round(pnl / staked, 4) if staked else 0.0,
            "mean_estimated_edge": round(float(settled["estimated_edge"].mean()), 4),
            "by_market": by_market,
            "note": ("Realized ROI over captured pre-game odds; single snapshot "
                     "proxy for closing, limited coverage. Not a profit guarantee.")}
