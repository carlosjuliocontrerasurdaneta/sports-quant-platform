"""Settlement: grade bet candidates against final scores, compute realized ROI.

Sources: The Odds API /scores for leagues with has_scores=True. Tennis has no
scores in this API -> requires a secondary results provider (explicit gap).
Audit trail: settled rows are appended, never overwritten.
"""
from __future__ import annotations
from datetime import datetime, timezone
import pandas as pd

from sqp.sports.team_names import normalize_key

# Un partido cancelado/pospuesto nunca entrega score: sin expiracion, su pick
# quedaria abierto para siempre y (post-shadow, stake > 0) la regla de
# "picks comenzados sin liquidar" excluiria su liga del run diario
# INDEFINIDAMENTE (auditoria 2026-07-12). Pasados estos dias desde el
# comienzo sin resultado, el pick se liquida como void (pnl 0, flag).
STALE_VOID_DAYS = 3


def _grade(row: pd.Series, hs: int, as_: int, home: str,
           three_way: bool = False) -> str:
    m, sel, line = row["market"], row["selection"], row["line"]
    margin, total = hs - as_, hs + as_
    # Compare side identity (selection vs home) by normalized key, not raw string:
    # the winner match upstream already normalizes, so a selection spelled
    # differently than `home` (accents, casing) must not silently misgrade a
    # home-side bet (2026-06-28 WTA Wimbledon review).
    sel_is_home = normalize_key(sel) == normalize_key(home)
    if m == "h2h":
        if margin == 0:
            if sel == "Draw": return "win"
            # 2-way (el empate no se cotiza): los books gradan PUSH y devuelven
            # el stake; gradarlo "loss" sesgaba las etiquetas de calibracion y
            # el ROI realizado (auditoria 2026-07-24, M-9). En 1X2 (three_way)
            # el empate solo lo gana la seleccion Draw.
            return "loss" if three_way else "push"
        return "win" if sel_is_home == (margin > 0) and sel != "Draw" else "loss"
    if m == "spreads":
        adj = margin + line if sel_is_home else -margin + line
        return "win" if adj > 0 else ("push" if adj == 0 else "loss")
    if m == "totals":
        if total == line: return "push"
        return "win" if (total > line) == (sel == "Over") else "loss"
    return "void"


def settle_candidates(candidates: pd.DataFrame, scores: dict[str, tuple[int, int, str]],
                      three_way: bool = False) -> pd.DataFrame:
    """scores: event_id -> (home_score, away_score, home_team_name).
    ``three_way``: liga con mercado 1X2 (empate cotizado); gobierna el grading
    de empates en h2h (push en 2-way, loss para equipos en 1X2)."""
    rows = []
    for _, row in candidates.iterrows():
        sc = scores.get(row["event_id"])
        if sc is None:
            continue
        hs, as_, home = sc
        result = _grade(row, hs, as_, home, three_way)
        pnl = {"win": row["stake"] * (row["price_decimal"] - 1),
               "loss": -row["stake"], "push": 0.0, "void": 0.0}[result]
        rows.append({**row.to_dict(), "result": result, "pnl": round(pnl, 2),
                     "settled_at": datetime.now(timezone.utc).isoformat()})
    out = pd.DataFrame(rows)
    if not out.empty:
        staked = out.loc[out.result.isin(["win", "loss"]), "stake"].sum()
        out.attrs["realized_roi"] = float(out["pnl"].sum() / staked) if staked else 0.0
    return out


def _parse_start(s: object) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def void_stale_candidates(candidates: pd.DataFrame,
                          scores: dict[str, tuple[int, int, str]],
                          start_times: dict[str, str], *,
                          now: datetime | None = None,
                          stale_days: int = STALE_VOID_DAYS) -> pd.DataFrame:
    """Void por expiracion: candidatos comenzados hace mas de ``stale_days``
    dias que siguen sin score (partido cancelado/pospuesto sin reprogramar).

    Devuelve filas con result='void', pnl 0.0 y flag ``stale_void`` (mismo
    formato que ``settle_candidates``, listas para ``_persist_settled``). Sin
    ``start_time`` conocido el candidato se deja abierto (nunca adivinar)."""
    if candidates.empty:
        return pd.DataFrame()
    now = now or datetime.now(timezone.utc)
    scored = {str(k) for k in scores}
    rows = []
    for _, row in candidates.iterrows():
        eid = str(row["event_id"])
        if eid in scored:
            continue
        start = _parse_start(start_times.get(eid))
        if start is None or (now - start).total_seconds() < stale_days * 86400:
            continue
        raw_flags = row.get("flags", "")
        flags = "" if pd.isna(raw_flags) else str(raw_flags)
        rows.append({**row.to_dict(),
                     "flags": f"{flags};stale_void" if flags else "stale_void",
                     "result": "void", "pnl": 0.0,
                     "settled_at": now.isoformat()})
    return pd.DataFrame(rows)
