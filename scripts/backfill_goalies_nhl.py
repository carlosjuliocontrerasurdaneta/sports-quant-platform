#!/usr/bin/env python
"""Backfill NHL goalie appearances into `data/historical/goalies_nhl.csv`.
Thin CLI wrapper; see `sqp.pipeline.goalie_backfill.run` for the
implementation and docstring (testable without the CLI or the network).

Example (smoke test, per the operator's instruction to test small first):
  python scripts/backfill_goalies_nhl.py --start 2024-10-10 --end 2024-10-12

Example (full backfill, only after the smoke test and code review; operator
decision 2026-09-26, ~34,000 requests at 1/s, ~9.5h):
  python scripts/backfill_goalies_nhl.py --start 2005-09-01 --end 2026-09-26
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqp.config import ROOT
from sqp.logging_config import get_logger
from sqp.pipeline.goalie_backfill import MAX_CONSECUTIVE_FAILURES, failed_report_path, run
from sqp.providers.date_window import utc_today

log = get_logger("sqp.backfill_goalies_nhl")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True, help="Fecha UTC inicial YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="Fecha UTC final YYYY-MM-DD (incluida)")
    ap.add_argument("--sleep", type=float, default=1.0,
                     help="Segundos minimos entre peticiones (por defecto 1.0)")
    ap.add_argument("--max-consecutive-failures", type=int, default=MAX_CONSECUTIVE_FAILURES,
                     help="Fallos GENERALES consecutivos (timeout, error de conexion, o "
                          "HTTP 429 persistente) que detienen todo el backfill sin avanzar "
                          "el checkpoint (por defecto %(default)s). Un HTTP 500/502/503/504 "
                          "de UNA fecha concreta no cuenta para este limite: se registra en "
                          "'failed' dentro del checkpoint y el backfill sigue con el dia "
                          "siguiente (ver el docstring de sqp.pipeline.goalie_backfill).")
    ap.add_argument("--root", default=str(ROOT),
                     help="Raiz del arbol de datos (por defecto la raiz del "
                          "repositorio); usar un directorio temporal para "
                          "pruebas y no tocar data/ real.")
    args = ap.parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end < start:
        ap.error("--end no puede ser anterior a --start")

    # Un partido de HOY (UTC) puede seguir en juego: el boxscore de la NHL
    # solo se ingiere si `gameState` esta en {OFF, FINAL} (B2), pero pedir un
    # rango que incluya hoy solo desperdicia peticiones que quedaran
    # "pendientes" en cada pasada -- se avisa y se recorta.
    today = utc_today()
    if end >= today:
        clamped = today - timedelta(days=1)
        log.warning("--end (%s) no es anterior a hoy UTC (%s); se limita a %s.",
                    end.isoformat(), today.isoformat(), clamped.isoformat())
        end = clamped
        if end < start:
            ap.error(f"--end recortado ({end}) queda antes de --start ({start}); "
                     "elige un rango ya finalizado.")

    root = Path(args.root)
    counts = run(start, end, args.sleep, root=root,
                 max_consecutive_failures=args.max_consecutive_failures)

    match_rate = (100.0 * counts.games_matched / counts.games_total) if counts.games_total else 0.0
    log.info(
        "Backfill de porteros NHL [%s .. %s]: %d dia(s), %d partido(s) "
        "(%d emparejados, %.1f%%, %d ya completos en el store sin re-pedir), "
        "%d fila(s) de aparicion vistas / %d nuevas guardadas, %d titulares.",
        start, end, counts.days, counts.games_total, counts.games_matched,
        match_rate, counts.games_skipped_cached, counts.appearance_rows_seen,
        counts.appearance_rows_added, counts.starters_seen,
    )
    if counts.unmatched:
        log.warning("%d partido(s) sin emparejar con el historico ESPN:", len(counts.unmatched))
        for name in counts.unmatched:
            log.warning("  sin emparejar: %s", name)
    if counts.pending_games:
        log.warning("%d partido(s) aun no finalizado(s) (pendientes de reintento):",
                    len(counts.pending_games))
        for name in counts.pending_games:
            log.warning("  pendiente: %s", name)
    if counts.failed_dates:
        log.warning("%d fecha(s) quedan registradas en 'failed' (detalle en %s):",
                    len(counts.failed_dates), failed_report_path(root))
        for entry in counts.failed_dates:
            log.warning("  %s kind=%s http_status=%s intentos=%d",
                        entry["date"], entry["kind"], entry.get("http_status"),
                        entry["attempts"])
    if counts.stopped_by_failures:
        log.error("El backfill se detuvo por fallos GENERALES consecutivos "
                   "(timeout/conexion/429); revisar la conectividad antes de reanudar. "
                   "El checkpoint NO avanzo mas alla del ultimo dia completo.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
