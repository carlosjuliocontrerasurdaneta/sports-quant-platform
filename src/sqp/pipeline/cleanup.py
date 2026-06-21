"""Prune obsolete pick files so the consolidated report never aggregates stale
candidates from leagues that have gone out of season.

A ``candidates_<league>.csv`` is pruned only when BOTH conditions hold:

  1. the league is no longer in season (not in the active set), so the daily run
     will never refresh it again, and
  2. every *actionable* pick in it (stake>0, unflagged) is already graded in
     ``settled_<league>.csv``.

Condition 2 protects settlement: an out-of-season league that still has
ungraded bets keeps its file so SETTLE_ALL can grade it later. Pruning a file
also removes the matching ``predictions_<league>.csv``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from sqp.logging_config import get_logger
from sqp.settlement.runner import DEDUP_KEY

log = get_logger("sqp.cleanup")


def _actionable(cands: pd.DataFrame) -> pd.DataFrame:
    """Stakeable, unflagged rows -- the only ones that get settled and that the
    picks report ranks."""
    if "stake" not in cands.columns:
        return cands.iloc[0:0]
    flags = cands["flags"].fillna("") if "flags" in cands.columns else ""
    return cands[(cands["stake"] > 0) & (flags == "")]


def _all_actionable_settled(cands: pd.DataFrame, settled_path: Path) -> bool:
    """True when every actionable pick in ``cands`` is already present in the
    league's settled file (matched on DEDUP_KEY). Errs on the safe side: if the
    settlement state cannot be verified, returns False so the file is kept."""
    actionable = _actionable(cands)
    if actionable.empty:
        return True  # nothing stakeable -> nothing to lose by pruning
    if not set(DEDUP_KEY).issubset(actionable.columns) or not settled_path.exists():
        return False
    settled = pd.read_csv(settled_path)
    if not set(DEDUP_KEY).issubset(settled.columns):
        return False
    have = {tuple(map(str, r)) for r in settled[DEDUP_KEY].values.tolist()}
    need = (tuple(map(str, r)) for r in actionable[DEDUP_KEY].values.tolist())
    return all(k in have for k in need)


def prune_stale_candidates(predictions_dir: Path, bets_dir: Path,
                           active_leagues: Iterable[str]) -> list[str]:
    """Delete obsolete candidates_/predictions_ files (see module docstring).
    Returns the pruned league ids, sorted."""
    active = set(active_leagues)
    pruned: list[str] = []
    for cf in sorted(predictions_dir.glob("candidates_*.csv")):
        league = cf.stem.replace("candidates_", "")
        if league in active:
            continue  # in season: refreshed by the daily run, never stale
        try:
            cands = pd.read_csv(cf)
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            log.warning("[%s] no se pudo leer %s para podar: %s", league, cf.name, exc)
            continue
        if not cands.empty and not _all_actionable_settled(cands, bets_dir / f"settled_{league}.csv"):
            log.info("[%s] fuera de temporada pero con apuestas sin liquidar; se conserva.", league)
            continue
        cf.unlink()
        pf = predictions_dir / f"predictions_{league}.csv"
        if pf.exists():
            pf.unlink()
        pruned.append(league)
    if pruned:
        log.info("Candidatos obsoletos podados (fuera de temporada y liquidados): %s",
                 ", ".join(pruned))
    return sorted(pruned)
