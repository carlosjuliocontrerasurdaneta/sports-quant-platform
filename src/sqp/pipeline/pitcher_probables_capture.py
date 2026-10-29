"""Captura prospectiva de los lanzadores abridores probables de MLB, con
NUESTRA marca de hora UTC (la API de MLB no da la hora del anuncio).

Escribe SOLO en `data/historical/pitcher_probables_mlb.csv` (via
`sqp.storage.pitchers_capture.log_pitcher_probable_capture`), una fila por
(game_pk, lado), anadida solo cuando cambia el lanzador (retirada incluida).
No sustituye ni modifica `pitcher_confirmation_log_mlb.csv` (resolucion
diaria, run diario). Nunca lee resultados ni toca probabilidades o picks.

Consulta el calendario MLB de hoy y manana (UTC), descarta los partidos ya
comenzados o terminados y registra los lados con y sin lanzador (los sin
lanzador solo importan para detectar una retirada).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.providers.date_window import utc_today
from sqp.providers.mlb_statsapi import MLBStatsProvider
from sqp.storage.pitchers_capture import log_pitcher_probable_capture

log = get_logger("sqp.pipeline.pitcher_probables_capture")

# Estados que indican partido ya en curso o terminado (detailedState de MLB).
_STARTED_STATES = ("final", "game over", "in progress", "completed", "live")
# Aplazados/cancelados/suspendidos: no se juegan a esa hora; un aplazado conserva
# su gamePk y reaparece en otra fecha, asi que no deben registrarse.
_DEAD_STATES = ("postponed", "cancelled", "canceled", "suspended")


def _parse_utc(s: object) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _not_yet_started(games: list[dict], as_of: datetime) -> list[dict]:
    """Conserva solo los partidos que no han comenzado en `as_of`. Un
    `commence` no parseable se DESCARTA (no se adivina que sigue por venir)."""
    out = []
    for g in games:
        status = str(g.get("status") or "").strip().lower()
        if status.startswith(_STARTED_STATES + _DEAD_STATES):
            continue
        commence = _parse_utc(g.get("commence"))
        if commence is None or commence <= as_of:
            continue
        out.append(g)
    return out


def _side_rows(games: list[dict]) -> list[dict]:
    rows = []
    for g in games:
        for side in ("home", "away"):
            rows.append({
                "game_pk": g.get("game_pk"),
                "game_date": g.get("date"),
                "commence_time": g.get("commence"),
                "team_side": side,
                "team": g.get(side),
                "pitcher_id": g.get(f"{side}_pitcher_id"),
                "pitcher_name": g.get(f"{side}_pitcher"),
            })
    return rows


def _is_dead(g: dict) -> bool:
    return str(g.get("status") or "").strip().lower().startswith(_DEAD_STATES)


def _dedupe_by_game_pk(items: list[tuple[datetime, dict]]) -> list[tuple[datetime, dict]]:
    """Un partido (gamePk) puede salir en varias fechas (aplazado + reprogramado):
    se conserva una sola aparicion, prefiriendo la no aplazada y, si empatan, la de
    `commence` mas tardio. Sin gamePk no se puede deduplicar: se conservan."""
    best: dict[str, tuple[datetime, dict]] = {}
    sin_pk: list[tuple[datetime, dict]] = []
    for item in items:
        pk = item[1].get("game_pk")
        if pk in (None, ""):
            sin_pk.append(item)
            continue
        key = str(pk)
        cur = best.get(key)
        if cur is None:
            best[key] = item
            continue
        def rank(it: tuple[datetime, dict]) -> tuple[bool, datetime]:
            return (not _is_dead(it[1]),
                    _parse_utc(it[1].get("commence")) or datetime.min.replace(tzinfo=timezone.utc))
        if rank(item) > rank(cur):
            best[key] = item
    return sin_pk + list(best.values())


def run(source_run: str = "capture", root: Path = ROOT,
        now: datetime | None = None, provider: Any = None) -> tuple[int, int]:
    """Consulta ayer, hoy y manana (UTC), filtra los no comenzados y registra los
    cambios. Devuelve (lados_con_lanzador_vistos, filas_anadidas).

    `/schedule date=` es la fecha LOCAL oficial del partido: uno nocturno de la
    fecha local de ayer puede empezar despues de 00:00 UTC, por eso se incluye
    ayer. Los partidos de todas las fechas se reunen y se deduplican por gamePk
    ANTES de registrar (cada gamePk va en una sola llamada al almacen).

    `captured_at` de cada partido es el instante tras recibir la respuesta de SU
    fecha. `now` (solo tests) fija ese instante y el corte de "no comenzado".
    `provider` (inyectable en tests) debe exponer `fetch_probable_pitchers`."""
    prov = provider if provider is not None else MLBStatsProvider()
    today = utc_today()
    items: list[tuple[datetime, dict]] = []
    for d in (today - timedelta(days=1), today, today + timedelta(days=1)):
        try:
            games = prov.fetch_probable_pitchers(d.isoformat())
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            log.warning("Fallo consultando probables MLB de %s (%s): %s",
                        d.isoformat(), exc.__class__.__name__, exc)
            continue
        captured_at = now if now is not None else datetime.now(timezone.utc)
        items.extend((captured_at, g) for g in games)

    by_ts: dict[datetime, list[dict]] = {}
    for ts, g in _dedupe_by_game_pk(items):
        by_ts.setdefault(ts, []).append(g)

    seen = 0
    appended = 0
    for ts, games in by_ts.items():
        rows = _side_rows(_not_yet_started(games, ts))
        seen += sum(1 for r in rows if r["pitcher_id"] or r["pitcher_name"])
        appended += log_pitcher_probable_capture(
            root, rows, source_run=source_run, captured_at=ts)
    return seen, appended
