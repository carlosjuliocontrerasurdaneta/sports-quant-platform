"""Prune obsolete pick files so the consolidated report never aggregates stale
candidates from leagues that have gone out of season.

A ``candidates_<league>.csv`` is pruned only when BOTH conditions hold:

  1. the league is no longer in season (not in the active set), so the daily run
     will never refresh it again, and
  2. EVERY pick in it is already graded in ``settled_<league>.csv``.

Condition 2 protects settlement: an out-of-season league that still has
ungraded bets keeps its file so SETTLE_ALL can grade it later. Pruning a file
also removes the matching ``predictions_<league>.csv``; both are archived first.

Condition 2 used to look only at *actionable* picks (stake>0, unflagged), on the
premise that those were "the only ones that get settled". That premise was false
(audit 2026-08-31, N-A-1): ``settle_candidates`` iterates EVERY candidate row and
persists it -- a stake-0 row just settles with ``pnl 0``. Settleable is not the
same as stakeable. With the prediction gate denying every market (0 of 39 allowed
on 2026-08-31) no row anywhere was actionable, so the check degenerated to an
unconditional True and any league leaving the active set had its files deleted
without any settlement check at all -- and with no recovery path, since
``_archive_existing`` only copies before an overwrite and an out-of-season league
is never overwritten again.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from sqp.logging_config import get_logger
from sqp.pipeline.daily import _archive_existing
from sqp.settlement.runner import DEDUP_KEY

log = get_logger("sqp.cleanup")

# Retencion de artefactos regenerables/expirados (auditoria 2026-07-12): sin
# purga, archive/ crece 2 archivos/liga/dia y los reportes clv_*.md y los
# contadores .closing_credits_* se acumulan sin limite.
PURGE_RETENTION_DAYS = 90


# Markers that describe HOW a pick was selected, not a reason to block it.
# `flags` used to hold at most one blocking reason, so `_actionable` tested it
# for emptiness. `pick_mode: accuracy` (2026-07-28) stamps every pick with
# `accuracy_mode`, which would make the emptiness test drop all of them once
# shadow mode is lifted -- pruning candidate files whose picks are still
# pending settlement (audit 2026-07-29, B-01 class).
INFORMATIONAL_FLAGS = frozenset({"accuracy_mode"})


def _actionable(cands: pd.DataFrame) -> pd.DataFrame:
    """Stakeable rows carrying no blocking flag -- the ones the picks report ranks.

    NOT the set that settlement grades: ``settle_candidates`` grades every row,
    stake-0 included (audit 2026-08-31, N-A-1). Do not use this to decide whether
    a file is safe to delete; use `_all_settled`.
    """
    if "stake" not in cands.columns:
        return cands.iloc[0:0]
    if "flags" not in cands.columns:
        return cands[cands["stake"] > 0]
    blocking = cands["flags"].fillna("").astype(str).apply(
        lambda f: [t for t in (x.strip() for x in f.split(";"))
                   if t and t not in INFORMATIONAL_FLAGS])
    return cands[(cands["stake"] > 0) & (blocking.str.len() == 0)]


def _all_settled(cands: pd.DataFrame, settled_path: Path) -> bool:
    """True when EVERY pick in ``cands`` is already present in the league's settled
    file (matched on DEDUP_KEY) -- the same set ``settle_candidates`` grades.

    Errs on the safe side in every branch: an unreadable settled file, a schema
    that does not carry DEDUP_KEY, or a single unmatched row all return False so
    the candidate file is kept. Deleting is irreversible; keeping is not.
    """
    if not set(DEDUP_KEY).issubset(cands.columns) or not settled_path.exists():
        return False
    try:
        settled = pd.read_csv(settled_path)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return False
    if not set(DEDUP_KEY).issubset(settled.columns):
        return False
    have = {tuple(map(str, r)) for r in settled[DEDUP_KEY].values.tolist()}
    need = (tuple(map(str, r)) for r in cands[DEDUP_KEY].values.tolist())
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
        if not cands.empty and not _all_settled(cands, bets_dir / f"settled_{league}.csv"):
            log.info("[%s] fuera de temporada pero con apuestas sin liquidar; se conserva.", league)
            continue
        # Archive before deleting: an out-of-season league is never overwritten
        # again, so the daily run's pre-overwrite archive never fires for it and
        # this unlink would be the only, unrecoverable copy (N-A-1).
        pf = predictions_dir / f"predictions_{league}.csv"
        _archive_existing(cf)
        cf.unlink()
        if pf.exists():
            _archive_existing(pf)
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
        # `event_id` is validated on BOTH frames: the merge below joins on it, so
        # a file missing it raised an uncaught KeyError. This guard runs in
        # run_all BEFORE the league loop and outside any try, so that exception
        # aborted the whole day's pick generation -- for every league, not just
        # the malformed one (audit 2026-08-31, N-M-6).
        if (cands.empty or "stake" not in cands.columns
                or "event_id" not in cands.columns
                or "start_time" not in preds.columns
                or "event_id" not in preds.columns):
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
