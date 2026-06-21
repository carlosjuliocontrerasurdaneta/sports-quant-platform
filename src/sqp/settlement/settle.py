"""Settlement: grade bet candidates against final scores, compute realized ROI.

Sources: The Odds API /scores for leagues with has_scores=True. Tennis has no
scores in this API -> requires a secondary results provider (explicit gap).
Audit trail: settled rows are appended, never overwritten.
"""
from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd


def _grade(row: pd.Series, hs: int, as_: int, home: str) -> str:
    m, sel, line = row["market"], row["selection"], row["line"]
    margin, total = hs - as_, hs + as_
    if m == "h2h":
        if margin == 0 and sel == "Draw": return "win"
        if margin == 0: return "loss"
        return "win" if (sel == home) == (margin > 0) and sel != "Draw" else "loss"
    if m == "spreads":
        adj = margin + line if sel == home else -margin + line
        return "win" if adj > 0 else ("push" if adj == 0 else "loss")
    if m == "totals":
        if total == line: return "push"
        return "win" if (total > line) == (sel == "Over") else "loss"
    return "void"


def settle_candidates(candidates: pd.DataFrame, scores: dict[str, tuple[int, int, str]]) -> pd.DataFrame:
    """scores: event_id -> (home_score, away_score, home_team_name)."""
    rows = []
    for _, row in candidates.iterrows():
        sc = scores.get(row["event_id"])
        if sc is None:
            continue
        hs, as_, home = sc
        result = _grade(row, hs, as_, home)
        pnl = {"win": row["stake"] * (row["price_decimal"] - 1),
               "loss": -row["stake"], "push": 0.0, "void": 0.0}[result]
        rows.append({**row.to_dict(), "result": result, "pnl": round(pnl, 2),
                     "settled_at": datetime.now(timezone.utc).isoformat()})
    out = pd.DataFrame(rows)
    if not out.empty:
        staked = out.loc[out.result.isin(["win", "loss"]), "stake"].sum()
        out.attrs["realized_roi"] = float(out["pnl"].sum() / staked) if staked else 0.0
    return out
