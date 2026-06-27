#!/usr/bin/env python
"""Closing Line Value (CLV) on the real settled bets.

CLV is the field-standard test for whether a betting operation has genuine edge:
it compares the price you BET at against the market's CLOSING consensus for the
same event/market/selection/line. Beating the close consistently (positive CLV)
predicts long-run profit; negative CLV means you are systematically getting bad
numbers (the loss is structural, not variance).

This isolates PRICE/timing from the model: it asks "given the picks the model
made, were the prices any good?" Uses only stored data (data/bets + data/odds),
no API quota.

  python scripts/clv_analysis.py

Single consensus-median proxy for the closing line; limited coverage; not a
profit guarantee. CLV is diagnostic, not a promise.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sqp.audit.report import load_all_settled
from sqp.backtesting.roi_engine import load_closing_odds
from sqp.config import ROOT
from sqp.pipeline.daily import _consensus_lines


def _point(market: str, line) -> float | None:
    if market == "h2h":
        return None
    try:
        return None if pd.isna(line) else float(line)
    except (TypeError, ValueError):
        return None


def _close_price(cons: dict, market: str, selection: str, point: float | None):
    """Closing consensus price for this exact selection/line, or None if the
    line is no longer in the closing book (e.g. the main spread/total moved)."""
    return cons.get((market, selection, point))


def main() -> int:
    settled = load_all_settled(ROOT / "data" / "bets")
    if settled.empty:
        print("No settled bets.")
        return 0
    settled = settled[settled["result"].isin(["win", "loss"])].copy()

    rows = []
    closing_cache: dict[str, dict] = {}
    for lg in sorted(settled["league"].unique()):
        odds = load_closing_odds(ROOT, lg)
        cons_by_event = {eid: _consensus_lines(eo) for eid, eo in odds.items()}
        closing_cache[lg] = cons_by_event

    matched = no_close = 0
    for r in settled.itertuples():
        cons = closing_cache.get(r.league, {}).get(str(r.event_id))
        if not cons:
            no_close += 1
            continue
        point = _point(str(r.market), r.line)
        close = _close_price(cons, str(r.market), str(r.selection), point)
        if close is None or close <= 1.0:
            no_close += 1
            continue
        entry = float(r.price_decimal)
        matched += 1
        rows.append({
            "league": r.league, "market": r.market, "result": r.result,
            "entry": entry, "close": close,
            # CLV%: how much better your odds were than the close (positive = beat it)
            "clv_pct": entry / close - 1.0,
            "beat_close": entry >= close,
        })

    if not rows:
        print(f"No bets could be matched to a closing price "
              f"(no_close={no_close}). Captured odds may not cover these events.")
        return 0
    df = pd.DataFrame(rows)

    def summary(label: str, d: pd.DataFrame) -> None:
        n = len(d)
        mean_clv = d["clv_pct"].mean() * 100
        beat = d["beat_close"].mean() * 100
        print(f"{label:24} n={n:4d}  CLV_medio={mean_clv:+6.2f}%  "
              f"%batio_cierre={beat:5.1f}%")

    print("========== CLV sobre apuestas liquidadas ==========")
    print(f"emparejadas a precio de cierre: {matched} | sin cierre disponible: {no_close}\n")
    print(">>> CLV positivo = entraste a MEJOR precio que el cierre (edge real).")
    print(">>> CLV negativo = entraste a PEOR precio que el cierre (sin edge / timing malo).\n")
    summary("GLOBAL", df)
    print("--- por resultado (ganadores deberian tener mejor CLV si hay edge) ---")
    for res in ("win", "loss"):
        summary(res, df[df["result"] == res])
    print("--- por liga ---")
    for lg in sorted(df["league"].unique()):
        summary(lg, df[df["league"] == lg])
    print("--- por mercado ---")
    for m in sorted(df["market"].unique()):
        summary(m, df[df["market"] == m])
    print("\nCLV es el mejor predictor de rentabilidad a largo plazo: si es "
          "negativo, el problema es el precio/timing, no la varianza. Proxy de "
          "cierre = consenso mediano; cobertura limitada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
