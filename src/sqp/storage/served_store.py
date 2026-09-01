"""Per-event served-probability stream (data/calibration/).

Every daily run serves a model probability for EVERY priced market side it
evaluates, but only the few that pass the edge floor become candidates. The
calibrator that trains on those placed picks alone learns from a small,
adversely-selected tail. This store captures the full serve distribution so
calibration can train on an unbiased per-event sample:

- ``served_{league}.csv``  -- append-only capture of every served probability
  (one row per event/market/selection/line per run day). Raw rows are never
  mutated.
- ``graded_{league}.csv``  -- append-only outcomes, written by settlement once
  final scores exist. Idempotent: a served row is never graded twice.

Demo runs are isolated under ``data/calibration/demo/`` (same rule as
``data/predictions/demo``): synthetic rows must never feed a real calibrator.
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from sqp.logging_config import get_logger
from sqp.storage.atomic import atomic_write_csv as _atomic_write_csv

log = get_logger("sqp.served_store")

COLUMNS = ["league", "event_id", "home", "away", "start_time", "game_date",
           "market", "selection", "line", "price_decimal", "bookmaker",
           "model_probability", "adjusted_probability",
           "estimated_probability", "calibrated_probability",
           "implied_probability_novig", "estimated_edge", "books_count",
           "stake", "data_label", "flags", "generated_at"]

# One row per market side per run DAY: a re-run the same day must not duplicate,
# while serving the same event on consecutive days keeps both genuine serves
# (mirrors settled_* semantics, whose dedup key carries generated_at).
KEY_COLS = ["event_id", "market", "selection", "line", "generated_at"]


def _serve_keys(df: pd.DataFrame) -> set[tuple[str, ...]]:
    """Day-truncated dedup keys, robust to the None -> NaN CSV round-trip of
    ``line`` (h2h rows have no point)."""
    line = pd.to_numeric(df["line"], errors="coerce")
    day = df["generated_at"].astype(str).str[:10]
    return {(str(e), str(m), str(s), str(ln), d)
            for e, m, s, ln, d in zip(df["event_id"].astype(str),
                                      df["market"].astype(str),
                                      df["selection"].astype(str),
                                      line, day)}


def _header(p: Path) -> list[str]:
    with p.open(newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh), [])



class ServedStore:
    def __init__(self, root: Path, demo: bool = False):
        base = root / "data" / "calibration"
        self.dir = base / "demo" if demo else base

    def served_path(self, league: str) -> Path:
        return self.dir / f"served_{league}.csv"

    def graded_path(self, league: str) -> Path:
        return self.dir / f"graded_{league}.csv"

    def leagues(self) -> list[str]:
        return sorted(p.stem.replace("served_", "")
                      for p in self.dir.glob("served_*.csv"))

    def graded_leagues(self) -> list[str]:
        """Ligas con stream GRADUADO. No coincide con ``leagues()``: esa lista
        los servidos, y una liga puede tener servidos sin graduar todavia."""
        return sorted(p.stem.replace("graded_", "")
                      for p in self.dir.glob("graded_*.csv"))

    def load_all_graded(self) -> pd.DataFrame:
        """Todas las filas graduadas de todas las ligas, con columna ``league``.

        Base SIN sesgo de seleccion para evaluar la prediccion: son todos los
        lados priceados, no solo los apostados. La consumen el gate de
        prediccion, su script y el analisis de reproducciones; vive aqui para
        que las tres no puedan divergir."""
        frames = []
        for league in self.graded_leagues():
            df = self._load(self.graded_path(league))
            if df.empty:
                continue
            df["league"] = league
            frames.append(df)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    @staticmethod
    def _quarantine(path: Path) -> Path | None:
        """Move a corrupt CSV aside so the store can start a clean file.

        Never raises: quarantine is a repair path, and failing to repair must not
        take settlement down with it. Returns the new path, or None on failure.
        """
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = path.with_suffix(f"{path.suffix}.corrupt.{stamp}")
        try:
            path.rename(target)
        except OSError as exc:
            log.error("could not quarantine %s (it will keep being read as "
                      "empty until moved by hand): %s", path, exc)
            return None
        log.error("quarantined %s -> %s. Inspect and re-import by hand if the "
                  "rows matter.", path, target.name)
        return target

    def _load(self, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame(columns=COLUMNS)
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=COLUMNS)
        except pd.errors.ParserError as exc:
            # "Degraded until repaired" was never true: nothing repaired it and
            # nothing quarantined it, so the damage was PERMANENT and silent
            # (audit 2026-08-31, N-A-2). Treating the file as empty skips the
            # dedup in `append_served`, and because the header is still intact
            # that method takes its cheap-append branch and keeps writing behind
            # the corrupt line; meanwhile `pending()` returns empty forever, so
            # the league never grades another served row and vanishes from the
            # calibrator and the prediction gate with only a warning.
            #
            # Quarantine instead: move the file aside so the next write starts a
            # clean one and the damage is bounded to what is already broken. The
            # rename is best-effort -- a failure here must not break settlement.
            log.error("corrupt CSV at %s: quarantining. Rows already written to "
                      "it are NOT lost, but they are no longer read: %s", path, exc)
            self._quarantine(path)
            return pd.DataFrame(columns=COLUMNS)

    def append_served(self, league: str, rows: list[dict]) -> int:
        """Persist served rows, skipping any (event, market, selection, line)
        already captured the same run day. Returns rows written."""
        if not rows:
            return 0
        df = pd.DataFrame(rows).reindex(columns=COLUMNS)
        p = self.served_path(league)
        self.dir.mkdir(parents=True, exist_ok=True)
        prior = self._load(p)
        if not prior.empty and set(KEY_COLS).issubset(prior.columns):
            have = _serve_keys(prior)
            keep = [k not in have for k in _keys_in_order(df)]
            df = df[keep]
        if df.empty:
            return 0
        # Schema-drift guard (KI-011 failure mode): a header that no longer
        # matches COLUMNS gets reconciled by column union and rewritten aligned;
        # the normal case stays a cheap append.
        if p.exists() and _header(p) != COLUMNS:
            cols = list(prior.columns) + [c for c in COLUMNS if c not in prior.columns]
            combined = pd.concat([prior.reindex(columns=cols), df.reindex(columns=cols)],
                                 ignore_index=True)
            _atomic_write_csv(combined, p)
        else:
            df.to_csv(p, mode="a", header=not p.exists(), index=False)
        return len(df)

    def pending(self, league: str, max_age_days: int = 7,
                now: datetime | None = None) -> pd.DataFrame:
        """Served rows not yet graded, whose event has commenced and is recent
        enough for the scores window to still cover it. Rows older than
        ``max_age_days`` are dropped from the scan (never gradeable: the scores
        feed no longer lists them), so the pending set stays bounded."""
        served = self._load(self.served_path(league))
        if served.empty:
            return served
        graded = self._load(self.graded_path(league))
        if not graded.empty and set(KEY_COLS).issubset(graded.columns):
            done = _serve_keys(graded)
            served = served[[k not in done for k in _keys_in_order(served)]]
        if served.empty:
            return served
        now = now or datetime.now(timezone.utc)
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        floor_iso = (now - timedelta(days=max_age_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        st = served["start_time"].astype(str)
        return served[(st <= now_iso) & (st >= floor_iso)].reset_index(drop=True)

    def append_graded(self, league: str, graded: pd.DataFrame) -> pd.DataFrame:
        """Dedup against prior graded rows and persist (idempotent, atomic).
        Returns the NEWLY graded rows."""
        if graded.empty:
            return graded
        p = self.graded_path(league)
        self.dir.mkdir(parents=True, exist_ok=True)
        prior = self._load(p)
        if not prior.empty and set(KEY_COLS).issubset(prior.columns):
            have = _serve_keys(prior)
            graded = graded[[k not in have for k in _keys_in_order(graded)]]
        if graded.empty:
            return graded
        if prior.empty:
            _atomic_write_csv(graded, p)
        else:
            cols = list(prior.columns) + [c for c in graded.columns if c not in prior.columns]
            combined = pd.concat([prior.reindex(columns=cols),
                                  graded.reindex(columns=cols)], ignore_index=True)
            _atomic_write_csv(combined, p)
        return graded


def _keys_in_order(df: pd.DataFrame) -> list[tuple[str, ...]]:
    """Row-aligned dedup keys (same normalization as ``_serve_keys``)."""
    line = pd.to_numeric(df["line"], errors="coerce")
    day = df["generated_at"].astype(str).str[:10]
    return [(str(e), str(m), str(s), str(ln), d)
            for e, m, s, ln, d in zip(df["event_id"].astype(str),
                                      df["market"].astype(str),
                                      df["selection"].astype(str),
                                      line, day)]
