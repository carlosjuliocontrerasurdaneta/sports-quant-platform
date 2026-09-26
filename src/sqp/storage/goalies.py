"""NHL goalie data: two independent, append-only stores.

- `GoalieAppearanceStore` (`data/historical/goalies_nhl.csv`): one row per
  (game, side, goalie) from the NHL's own boxscore (`sqp.providers.nhl_api`),
  matched where possible to the ESPN-sourced results history
  (`ResultsStore('nhl')`). Backfill-only; the boxscore of a completed game
  never changes, so re-ingesting a game is a no-op (append-only, deduplicated
  by game + side + goalie -- existing rows always win, like `ResultsStore`,
  never like `StartersStore`'s "newest wins" for mutable announcements).
- `log_goalie_probable_capture` (`data/historical/goalie_probables_nhl.csv`):
  the prospective capture of ESPN's `probables` (section 12 of the
  pre-registro), one row per (event, side) appended only when the probable
  goalie or its status CHANGES relative to the last logged row for that
  (event, side) -- mirrors `sqp.storage.starters.log_pitcher_confirmation`.
  `source_run="daily"` rows are the exception: always appended, as the daily
  run's anchor row rather than a change log. A pair that had a probable and
  stops publishing one gets an explicit WITHDRAWAL row (empty goalie,
  status "none") when the caller passes `active_pairs`, instead of silently
  vanishing from the capture. This store is written ONLY by the capture
  path; it never reads or writes `goalies_nhl.csv`, results, candidates,
  stakes or any gate/calibration file.

Raw boxscore JSON is preserved separately (gzip, one file per NHL game id)
via `save_raw_boxscore`/`raw_boxscore_path`, per the project's data-integrity
rule (raw data preserved, never mutated) and the pre-registro's own
requirement (section 3.2: "el JSON bruto comprimido (gzip), para preservar
los datos brutos").
"""
from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sqp.logging_config import get_logger
from sqp.storage.atomic import atomic_write_bytes, atomic_write_csv
from sqp.storage.lock import locked

log = get_logger("sqp.storage.goalies")

APPEARANCE_COLUMNS = [
    "nhl_game_id", "espn_game_id", "date", "game_type", "start_time_utc",
    "team_side", "team_nhl", "team_espn", "matched",
    "goalie_player_id", "goalie_name", "starter",
    "shots_against", "saves", "goals_against", "toi",
    "fetched_at",
]
APPEARANCE_KEY = ["nhl_game_id", "team_side", "goalie_player_id"]

PROBABLE_COLUMNS = [
    "captured_at_utc", "event_id", "commence_time", "team_side", "team",
    "goalie_espn_id", "goalie_name", "status", "status_type", "source_run",
]


class GoalieAppearanceStore:
    """`data/historical/goalies_nhl.csv`: append-only, deduplicated by
    (nhl_game_id, team_side, goalie_player_id). A completed game's boxscore is
    immutable, so unlike starter announcements this never needs "newest wins"
    semantics -- the FIRST ingestion of a given appearance is kept, matching
    `ResultsStore.upsert`'s convention (raw data is never mutated)."""

    def __init__(self, root: Path):
        self.dir = root / "data" / "historical"

    def path(self) -> Path:
        return self.dir / "goalies_nhl.csv"

    def load(self) -> pd.DataFrame:
        p = self.path()
        if not p.exists():
            return pd.DataFrame(columns=APPEARANCE_COLUMNS)
        return pd.read_csv(p, dtype={
            "nhl_game_id": str, "espn_game_id": str, "goalie_player_id": str,
            "date": str,
        })

    def save(self, rows: list[dict]) -> int:
        """Append new appearance rows; returns how many were actually added
        (duplicates against already-stored rows, by key, are silently
        skipped -- this is what makes the backfill resumable: re-running over
        an already-fetched date range costs the network calls again, but
        never double-counts or corrupts the store)."""
        if not rows:
            return 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new = pd.DataFrame(rows)
        for col in APPEARANCE_KEY:
            if col in new.columns:
                new[col] = new[col].astype(str)
        new["fetched_at"] = now
        new = new.reindex(columns=APPEARANCE_COLUMNS)
        p = self.path()
        self.dir.mkdir(parents=True, exist_ok=True)
        # Transaccion bajo lock (mismo criterio que ResultsStore.upsert /
        # StartersStore.save): un backfill reanudado y otro proceso escritor
        # no deben poder pisarse en un read-modify-write.
        with locked(p):
            if p.exists():
                cur = pd.read_csv(p, dtype={
                    "nhl_game_id": str, "espn_game_id": str,
                    "goalie_player_id": str, "date": str})
                before = len(cur)
                merged = pd.concat([cur, new], ignore_index=True).drop_duplicates(
                    subset=APPEARANCE_KEY, keep="first")
            else:
                before = 0
                merged = new.drop_duplicates(subset=APPEARANCE_KEY, keep="first")
            merged = merged.sort_values(["date", "nhl_game_id"], kind="stable")
            atomic_write_csv(merged, p)
            added = len(merged) - before
        return added


def raw_boxscore_dir(root: Path) -> Path:
    return root / "data" / "historical" / "nhl_goalies_raw"


def raw_boxscore_path(root: Path, nhl_game_id: str) -> Path:
    return raw_boxscore_dir(root) / f"{nhl_game_id}.json.gz"


def save_raw_boxscore(root: Path, nhl_game_id: str, payload: dict) -> Path:
    """Preserve the raw boxscore JSON (gzip), one file per NHL game id.
    Idempotent: re-saving the same game id overwrites with identical content
    (the boxscore of a completed game never changes)."""
    out = raw_boxscore_path(root, nhl_game_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(gzip.compress(json.dumps(payload).encode("utf-8")), out)
    return out


def _norm_str(v: object) -> str:
    """Normalizes `None`/NaN/"nan"/"None" to "" before comparing captured
    values. Without this, a genuinely null `status` compares as the Python
    string "None" against pandas' "nan" (or vice versa) on every pass, and a
    row that never actually changed gets re-appended forever (revision
    independiente de Fable, menor, 2026-09-26)."""
    if v is None:
        return ""
    s = str(v)
    return "" if s.lower() in ("nan", "none") else s


def log_goalie_probable_capture(
    root: Path,
    rows: list[dict],
    source_run: str,
    captured_at: datetime | None = None,
    active_pairs: list[dict] | None = None,
) -> int:
    """Append probable-goalie captures for events not yet started.

    Each row must contain: event_id, team_side, team, goalie_espn_id,
    goalie_name, status, status_type, commence_time. `captured_at` is the
    instant this information became available -- the caller (the capture
    pipeline) is expected to pass the instant it RECEIVED that row's
    scoreboard response, not the instant it started the request; when
    omitted, "now" is used, which is only correct for a single-row/batch call
    made right after its own fetch.

    Deduplication (avoiding a duplicate row on every ~30-minute pass) works
    per (event_id, team_side), comparing the NEW (goalie_espn_id, status)
    against the last logged row for that pair -- EXCEPT rows whose
    `source_run` is "daily", which are always appended even if identical to
    the last capture: "daily" is the once-a-day anchor row the daily run
    relies on being present for every event it covers, not a change log
    (revision independiente de Fable, C1, 2026-09-26).

    `active_pairs`, when given, lists every (event_id, team_side) considered
    IN SCOPE this pass (whether or not it currently carries a probable) as
    dicts with event_id/team_side/team/commence_time. Any pair that is in
    `active_pairs` but has no row in `rows` this pass, and whose last logged
    row had a real goalie, gets a WITHDRAWAL row appended (empty goalie,
    status "none") instead of being silently dropped -- otherwise a probable
    that ESPN stops publishing looks, from the CSV alone, identical to one
    that was simply never re-fetched (revision independiente de Fable, C1,
    2026-09-26). A pair that never had a probable logged is left alone: there
    is nothing to withdraw.

    Returns the number of rows appended (changes + withdrawals).

    This function ONLY ever touches `goalie_probables_nhl.csv`. It does not
    read or write `goalies_nhl.csv`, results, candidates, stakes or any
    gate/calibration file."""
    ts = (captured_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    p = root / "data" / "historical" / "goalie_probables_nhl.csv"

    def _mk(event_id: str, commence_time: str, team_side: object, team: object,
            goalie_espn_id: str, goalie_name: object, status: object,
            status_type: object) -> dict:
        return {
            "captured_at_utc": ts,
            "event_id": event_id,
            "commence_time": commence_time,
            "team_side": team_side,
            "team": team,
            "goalie_espn_id": goalie_espn_id,
            "goalie_name": goalie_name,
            "status": status,
            "status_type": status_type,
            "source_run": source_run,
        }

    new_rows = [
        _mk(str(r.get("event_id", "")), str(r.get("commence_time", "")),
            r.get("team_side"), r.get("team"), str(r.get("goalie_espn_id", "")),
            r.get("goalie_name"), r.get("status"), r.get("status_type"))
        for r in rows
        if r.get("goalie_espn_id")
    ]
    seen_pairs = {(row["event_id"], row["team_side"]) for row in new_rows}

    if not new_rows and not active_pairs:
        return 0

    p.parent.mkdir(parents=True, exist_ok=True)
    with locked(p):
        if p.exists():
            existing = pd.read_csv(p, dtype={"event_id": str, "goalie_espn_id": str})
        else:
            existing = pd.DataFrame(columns=PROBABLE_COLUMNS)

        last_by_pair: dict[tuple, dict] = {}
        if not existing.empty:
            last = (existing.sort_values("captured_at_utc")
                    .drop_duplicates(subset=["event_id", "team_side"], keep="last"))
            for _, r in last.iterrows():
                last_by_pair[(str(r["event_id"]), r["team_side"])] = r.to_dict()

        to_append: list[dict] = []
        for row in new_rows:
            if row["source_run"] == "daily":
                to_append.append(row)
                continue
            prev = last_by_pair.get((row["event_id"], row["team_side"]))
            if prev is None:
                to_append.append(row)
            elif (_norm_str(prev.get("goalie_espn_id")) != _norm_str(row["goalie_espn_id"])
                  or _norm_str(prev.get("status")) != _norm_str(row["status"])):
                to_append.append(row)

        for ap in active_pairs or []:
            pair = (str(ap.get("event_id", "")), ap.get("team_side"))
            if pair in seen_pairs:
                continue  # sigue publicando un probable en esta pasada
            prev = last_by_pair.get(pair)
            if prev is None or not _norm_str(prev.get("goalie_espn_id")):
                continue  # nunca tuvo probable, o ya estaba retirado
            to_append.append(_mk(
                pair[0], str(ap.get("commence_time", "")), pair[1], ap.get("team"),
                "", None, "none", "none",
            ))

        if not to_append:
            return 0
        appended = pd.DataFrame(to_append)[PROBABLE_COLUMNS]
        combined = pd.concat([existing, appended], ignore_index=True)
        atomic_write_csv(combined.sort_values("captured_at_utc", kind="stable"), p)
    n = len(to_append)
    log.info("goalie_probables_nhl: %d fila(s) nueva(s)/cambiada(s)/retirada(s).", n)
    return n
