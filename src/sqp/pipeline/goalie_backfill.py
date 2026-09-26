"""Backfill NHL goalie appearances (starter + backup, per game) from the
public NHL API into `data/historical/goalies_nhl.csv`, matched to the
ESPN-sourced results history (`ResultsStore('nhl')`).

Implements the backfill described in
`docs/research/2026-09-26-preregistro-portero-nhl.md`, section 3.3: one
request per second, `timeout=20` (`sqp.providers.nhl_api`), up to 3 retries
respecting `Retry-After`, stop after 3 CONSECUTIVE failures, single-threaded,
resumable via a checkpoint file
(`data/historical/.goalies_nhl_backfill_checkpoint.json`).

Full authorized scope (operator decision, 2026-09-26): 2005-06 season through
2025-26 plus the current preseason (~34,000 requests, ~9.5h). This module
does not choose that range on its own; the caller (the CLI script) requires
explicit `--start`/`--end`.

Checkpoint invariant (revision independiente de Fable, B1, 2026-09-26): the
checkpoint's `last_date_done` never advances past the FIRST incomplete day in
a run -- a day is incomplete if its `/v1/score` fetch failed, one of its
boxscore fetches failed, or one of its games was not yet final (see B2
below). A day AFTER the gap that completes cleanly still has its rows saved
to the store (append-only, deduplicated by key -- safe to redo), it just does
not move the resume pointer past the gap, so resuming later re-covers it
instead of skipping it forever.

Only FINAL games are ingested (B2): a boxscore whose `gameState` is not
`OFF`/`FINAL` (`sqp.providers.nhl_api.is_final_game_state`) is treated as
pending -- no raw JSON, no appearance rows, day left incomplete -- because
`GoalieAppearanceStore.save` keeps the FIRST row it ever sees per key, and a
LIVE/CRIT snapshot saved once would freeze partial stats forever.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.providers import nhl_api
from sqp.sports.nhl_goalie_matching import build_results_index, match_espn_game
from sqp.storage.atomic import atomic_write_json, read_json_retrying
from sqp.storage.goalies import GoalieAppearanceStore, save_raw_boxscore
from sqp.storage.results_store import ResultsStore

log = get_logger("sqp.pipeline.goalie_backfill")

CHECKPOINT_NAME = ".goalies_nhl_backfill_checkpoint.json"
MAX_CONSECUTIVE_FAILURES = 3


def checkpoint_path(root: Path) -> Path:
    return root / "data" / "historical" / CHECKPOINT_NAME


class _RateLimiter:
    """Enforces a minimum interval between requests (courtesy pacing against
    an undocumented public API); NOT a burst limiter, just spacing."""

    def __init__(self, min_interval_s: float):
        self.min_interval_s = min_interval_s
        self._last: float | None = None

    def wait(self) -> None:
        if self._last is not None:
            elapsed = time.monotonic() - self._last
            remaining = self.min_interval_s - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last = time.monotonic()


@dataclass
class Counts:
    days: int = 0
    games_total: int = 0
    games_matched: int = 0
    appearance_rows_seen: int = 0
    appearance_rows_added: int = 0
    starters_seen: int = 0
    unmatched: list[str] = field(default_factory=list)
    pending_games: list[str] = field(default_factory=list)
    stopped_by_failures: bool = False


def _load_checkpoint(root: Path, start: date, end: date) -> date | None:
    """Last fully-completed date for THIS (start, end) range, or None if no
    checkpoint applies (first run, or the range changed)."""
    p = checkpoint_path(root)
    if not p.exists():
        return None
    try:
        data = read_json_retrying(p)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("start") != start.isoformat() or data.get("end") != end.isoformat():
        return None
    last = data.get("last_date_done")
    if not last:
        return None
    try:
        return date.fromisoformat(str(last))
    except ValueError:
        return None


def _save_checkpoint(root: Path, start: date, end: date, last_date_done: date) -> None:
    p = checkpoint_path(root)
    # Un rango sin ningun partido (por ejemplo, dias de descanso al principio
    # de temporada) nunca pasa por `GoalieAppearanceStore.save`, que es lo
    # unico que hasta ahora creaba `data/historical/` -- sin este mkdir, el
    # primer dia sin partidos de un `root` recien creado hacia fallar el
    # propio checkpoint (detectado al probar en un directorio temporal, sin
    # sembrar resultados de antemano).
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(
        {"start": start.isoformat(), "end": end.isoformat(),
         "last_date_done": last_date_done.isoformat(),
         "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        p,
    )


def run(start: date, end: date, sleep_s: float = 1.0, root: Path = ROOT) -> Counts:
    counts = Counts()
    session = requests.Session()
    limiter = _RateLimiter(sleep_s)
    store = GoalieAppearanceStore(root)
    results_index = build_results_index(ResultsStore(root).load("nhl"))

    resume_after = _load_checkpoint(root, start, end)
    cursor = start if resume_after is None else resume_after + timedelta(days=1)
    if resume_after is not None:
        log.info("Reanudando backfill de porteros NHL tras %s (checkpoint).", resume_after)

    score_cache: dict[str, list[dict]] = {}
    consecutive_failures = 0
    # Una vez que un dia queda incompleto (fallo de red, o un partido aun no
    # finalizado), el checkpoint deja de avanzar para el resto de esta
    # ejecucion: de lo contrario un dia POSTERIOR correcto lo guardaria por
    # delante del hueco y ese dia se perderia para siempre, sin aparecer en
    # `unmatched` (revision independiente de Fable, B1, 2026-09-26). Los datos
    # de dias posteriores SI se guardan en el store (append-only, deduplicado
    # por clave), solo el puntero de reanudacion se congela.
    first_incomplete: date | None = None

    def _fetch_score(local_date: date) -> list[dict]:
        key = local_date.isoformat()
        if key not in score_cache:
            limiter.wait()
            payload = nhl_api.fetch_score(key, session)
            score_cache[key] = nhl_api.parse_score_games(payload)
            # Solo se conservan los dias en juego: evita crecer sin limite en
            # un backfill de anios (cache "cada dia se pide una sola vez").
            if len(score_cache) > 3:
                for old_key in sorted(score_cache)[:-3]:
                    del score_cache[old_key]
        return score_cache[key]

    day = cursor
    while day <= end:
        try:
            games_today = [g for g in _fetch_score(day) if g["date_utc"] == day.isoformat()]
            games_yesterday = [g for g in _fetch_score(day - timedelta(days=1))
                               if g["date_utc"] == day.isoformat()]
        except (requests.RequestException, ValueError) as exc:
            consecutive_failures += 1
            if first_incomplete is None:
                first_incomplete = day
            log.warning("Fallo consultando /v1/score para %s (%s): %s",
                        day.isoformat(), exc.__class__.__name__, exc)
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                log.error("%d fallos consecutivos; se detiene el backfill en %s.",
                          consecutive_failures, day.isoformat())
                counts.stopped_by_failures = True
                break
            day += timedelta(days=1)
            continue

        games = games_today + games_yesterday
        appearance_rows: list[dict] = []
        for g in games:
            counts.games_total += 1
            match = match_espn_game(g["date_utc"], g["home_name"], g["away_name"], results_index)
            if match is not None:
                counts.games_matched += 1
            else:
                counts.unmatched.append(f"{g['date_utc']} {g['away_name']} @ {g['home_name']}")

            try:
                limiter.wait()
                box = nhl_api.fetch_boxscore(g["nhl_game_id"], session)
            except (requests.RequestException, ValueError) as exc:
                consecutive_failures += 1
                if first_incomplete is None:
                    first_incomplete = day
                log.warning("Fallo consultando boxscore %s (%s): %s",
                            g["nhl_game_id"], exc.__class__.__name__, exc)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    log.error("%d fallos consecutivos; se detiene el backfill.",
                              consecutive_failures)
                    counts.stopped_by_failures = True
                    if appearance_rows:
                        counts.appearance_rows_added += store.save(appearance_rows)
                    return counts
                continue
            consecutive_failures = 0

            if not nhl_api.is_final_game_state(box):
                # Partido en juego / aun no arrancado (LIVE, CRIT, FUT, PRE...):
                # se trata como pendiente. No se guarda el JSON crudo (dejaria
                # de ser un snapshot inmutable) ni las filas de aparicion (el
                # store se queda con la PRIMERA fila que ve por clave, y una
                # parcial congelada nunca se corregiria), y el dia queda
                # incompleto para el checkpoint.
                counts.pending_games.append(
                    f"{g['date_utc']} {g['away_name']} @ {g['home_name']} "
                    f"(gameState={box.get('gameState')!r})")
                if first_incomplete is None:
                    first_incomplete = day
                continue

            save_raw_boxscore(root, g["nhl_game_id"], box)

            for row in nhl_api.parse_boxscore_goalies(box, g["nhl_game_id"]):
                counts.appearance_rows_seen += 1
                if row["starter"]:
                    counts.starters_seen += 1
                row["date"] = g["date_utc"]
                row["team_nhl"] = g["home_name"] if row["team_side"] == "home" else g["away_name"]
                if match is not None:
                    row["espn_game_id"] = match["espn_game_id"]
                    row["team_espn"] = (match["home_espn"] if row["team_side"] == "home"
                                        else match["away_espn"])
                    row["matched"] = True
                else:
                    row["espn_game_id"] = ""
                    row["team_espn"] = ""
                    row["matched"] = False
                appearance_rows.append(row)

        if appearance_rows:
            counts.appearance_rows_added += store.save(appearance_rows)
        counts.days += 1
        if first_incomplete is None:
            _save_checkpoint(root, start, end, day)
        day += timedelta(days=1)

    return counts
