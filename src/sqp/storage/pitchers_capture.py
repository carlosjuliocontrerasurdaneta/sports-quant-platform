"""Captura prospectiva de los lanzadores abridores probables de MLB con NUESTRA
marca de hora UTC (`data/historical/pitcher_probables_mlb.csv`).

Complementa -sin tocarlo- a `sqp.storage.starters.log_pitcher_confirmation`
(una fila al dia desde el run diario): aqui la resolucion es la de la captura
(~30 min), para medir mas adelante CUANDO se conoce cada abridor frente a
cuando se mueve la linea. Una fila por (game_pk, lado), anadida solo cuando
el lanzador cambia respecto a la ultima fila de ese (game_pk, lado); la
retirada (lanzador vacio tras haber tenido uno) tambien es una fila. La
primera vez que un lado aparece sin lanzador NO se registra. Solo escribe su
propio CSV; nunca lee resultados, picks ni probabilidades.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from sqp.logging_config import get_logger
from sqp.storage.atomic import atomic_write_csv
from sqp.storage.goalies import _norm_str
from sqp.storage.lock import locked

log = get_logger("sqp.storage.pitchers_capture")

PITCHER_PROBABLE_COLUMNS = [
    "captured_at_utc", "game_pk", "game_date", "commence_time", "team_side",
    "team", "pitcher_id", "pitcher_name", "source_run",
]


def _norm_id(v: object) -> str:
    """Normaliza un id de lanzador a texto: None/NaN/"" -> "", 123.0 -> "123"
    (un id leido como float por pandas no debe parecer un cambio)."""
    s = _norm_str(v)
    if s.endswith(".0") and s[:-2].isdigit():
        return s[:-2]
    return s


def log_pitcher_probable_capture(
    root: Path,
    rows: list[dict],
    *,
    source_run: str,
    captured_at: datetime | None = None,
) -> int:
    """Anade capturas de abridores probables de MLB; devuelve las filas anadidas.

    Cada fila de entrada lleva: game_pk, game_date, commence_time, team_side
    ("home"/"away"), team, pitcher_id, pitcher_name. `captured_at` es el
    instante en que se RECIBIO la respuesta (por defecto, ahora).

    Dedup por (game_pk, team_side) contra la ULTIMA fila registrada: se anade
    si cambia el pitcher_id (o, sin id, el nombre). Un lado sin lanzador cuyo
    ultimo registro SI tenia uno genera una fila de retirada (id y nombre
    vacios); si nunca tuvo lanzador, no se registra nada."""
    ts = (captured_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    p = root / "data" / "historical" / "pitcher_probables_mlb.csv"
    if not rows:
        return 0

    candidates: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for r in rows:
        pk = _norm_str(r.get("game_pk"))
        side = _norm_str(r.get("team_side"))
        if not pk or side not in ("home", "away") or (pk, side) in seen:
            continue
        seen.add((pk, side))
        candidates.append({
            "captured_at_utc": ts,
            "game_pk": pk,
            "game_date": _norm_str(r.get("game_date")),
            "commence_time": _norm_str(r.get("commence_time")),
            "team_side": side,
            "team": _norm_str(r.get("team")),
            "pitcher_id": _norm_id(r.get("pitcher_id")),
            "pitcher_name": _norm_str(r.get("pitcher_name")),
            "source_run": source_run,
        })

    p.parent.mkdir(parents=True, exist_ok=True)
    with locked(p):
        if p.exists():
            existing = pd.read_csv(p, dtype=str, keep_default_na=False)
        else:
            existing = pd.DataFrame(columns=PITCHER_PROBABLE_COLUMNS)

        last_by_pair: dict[tuple[str, str], dict] = {}
        if not existing.empty:
            last = (existing.sort_values("captured_at_utc", kind="stable")
                    .drop_duplicates(subset=["game_pk", "team_side"], keep="last"))
            for rec in last.to_dict("records"):
                last_by_pair[(_norm_str(rec["game_pk"]), _norm_str(rec["team_side"]))] = rec

        to_append: list[dict] = []
        for row in candidates:
            prev = last_by_pair.get((row["game_pk"], row["team_side"]))
            has_new = bool(row["pitcher_id"] or row["pitcher_name"])
            if prev is None:
                if has_new:
                    to_append.append(row)
                continue
            if (_norm_id(prev.get("pitcher_id")) != row["pitcher_id"]
                    or _norm_str(prev.get("pitcher_name")) != row["pitcher_name"]):
                # Cambio de lanzador o retirada (nuevo vacio tras uno previo);
                # un vacio sobre un vacio ya queda cubierto por la igualdad.
                to_append.append(row)

        if not to_append:
            return 0
        appended = pd.DataFrame(to_append)[PITCHER_PROBABLE_COLUMNS]
        combined = pd.concat([existing, appended], ignore_index=True)
        atomic_write_csv(combined.sort_values("captured_at_utc", kind="stable"), p)
    n = len(to_append)
    log.info("pitcher_probables_mlb: %d fila(s) nueva(s)/cambiada(s)/retirada(s).", n)
    return n
