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

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from sqp.logging_config import get_logger
from sqp.settlement.runner import DEDUP_KEY

log = get_logger("sqp.cleanup")

# Retencion de artefactos regenerables/expirados (auditoria 2026-07-12): sin
# purga, archive/ crece 2 archivos/liga/dia y los reportes clv_*.md y los
# contadores .closing_credits_* se acumulan sin limite.
PURGE_RETENTION_DAYS = 90


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


def unsettled_completed_picks(predictions_dir: Path, bets_dir: Path,
                              leagues: Iterable[str], *,
                              now: str | None = None) -> dict[str, int]:
    """Per-league count of staked, real picks whose game has ALREADY commenced but
    that are not yet present in ``settled_<league>.csv``.

    These are the picks the daily run would make ungradeable by overwriting
    ``candidates_<league>.csv``: the settlement dedup key includes ``generated_at``,
    so once the file is regenerated the old, commenced-but-unsettled pick can never
    be matched to a final score (the M2 loss window). Future-game picks are
    excluded -- refreshing them is the normal daily behavior, not a loss.

    Restricted to ``leagues`` (the ones about to be overwritten). Returns only
    leagues with a positive count. Errs on the safe side: when a league's start
    times or settlement state cannot be read, that league is skipped (not blocked),
    since `_archive_existing` still keeps an overwritten file recoverable.

    Start times are not on the candidates rows (BetCandidate has no start_time), so
    they are joined from ``predictions_<league>.csv`` by event_id.
    """
    now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    at_risk: dict[str, int] = {}
    for league in leagues:
        cf = predictions_dir / f"candidates_{league}.csv"
        pf = predictions_dir / f"predictions_{league}.csv"
        if not cf.exists() or not pf.exists() or pf.stat().st_size <= 1:
            continue
        try:
            cands = pd.read_csv(cf)
            preds = pd.read_csv(pf, usecols=lambda c: c in ("event_id", "start_time"))
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
            continue
        if cands.empty or "stake" not in cands.columns or "start_time" not in preds.columns:
            continue
        staked = cands[cands["stake"] > 0]
        if "data_label" in staked.columns:
            staked = staked[staked["data_label"].astype(str) == "real"]
        if staked.empty:
            continue
        merged = staked.merge(preds, on="event_id", how="left")
        st = merged["start_time"].astype(str)
        commenced = merged[(st != "nan") & (st != "") & (st <= now)]
        if commenced.empty:
            continue
        n = len(commenced)
        settled_path = bets_dir / f"settled_{league}.csv"
        if settled_path.exists() and set(DEDUP_KEY).issubset(commenced.columns):
            try:
                settled = pd.read_csv(settled_path)
            except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
                settled = None
            if settled is not None and set(DEDUP_KEY).issubset(settled.columns):
                have = {tuple(map(str, r)) for r in settled[DEDUP_KEY].values.tolist()}
                n = sum(tuple(map(str, r)) not in have
                        for r in commenced[DEDUP_KEY].values.tolist())
        if n > 0:
            at_risk[league] = int(n)
    return at_risk


def _artifact_date(name: str) -> datetime | None:
    """Fecha YYYYMMDD embebida en el nombre del artefacto (None si no hay)."""
    m = re.search(r"(20\d{6})", name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def purge_old_artifacts(root: Path, *, days: int = PURGE_RETENTION_DAYS,
                        now: datetime | None = None) -> dict[str, int]:
    """Borra artefactos regenerables/expirados con mas de ``days`` dias.

    Allowlist ESTRICTA — solo tres familias, nunca datos crudos ni settled:

    - ``data/predictions/archive/*.csv``: copias de seguridad de candidates/
      predictions ya sobrescritos (la ventana util de recuperacion es dias).
    - ``data/bets/clv_*.md``: reportes diarios de CLV (regenerables con
      ``scripts/clv_analysis.py``; el registro vivo es clv_gate.json).
    - ``data/odds/.closing_credits_*``: contadores diarios de creditos.

    La edad sale de la fecha YYYYMMDD del nombre; sin fecha parseable se usa
    mtime. Best-effort: un archivo imborrable se loguea y no aborta. Devuelve
    conteo de borrados por familia."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    families = {
        "archive": (root / "data" / "predictions" / "archive", "*.csv"),
        "clv_reports": (root / "data" / "bets", "clv_*.md"),
        "closing_credits": (root / "data" / "odds", ".closing_credits_*"),
    }
    out: dict[str, int] = {}
    for kind, (folder, pattern) in families.items():
        n = 0
        for f in (folder.glob(pattern) if folder.is_dir() else ()):
            when = _artifact_date(f.name)
            if when is None:
                try:
                    when = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                except OSError:
                    continue
            if when >= cutoff:
                continue
            try:
                f.unlink()
                n += 1
            except OSError as exc:
                log.warning("purge: no se pudo borrar %s: %s", f, exc)
        out[kind] = n
    if any(out.values()):
        log.info("purge: %s artefactos borrados (retencion %dd): %s",
                 sum(out.values()), days, out)
    return out
