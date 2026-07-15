"""Observatorio de edge intradia: medicion pura para decidir la fase ofensiva.

Diagnostico 2026-07-14: el danio dominante del sistema es la seleccion adversa
por desventaja de timing (picks de las 11:00 contra un mercado que sigue
incorporando informacion). La correccion estructural seria generar/re-preciar
picks intradia — pero implementarla sin evidencia repetiria el error que este
proyecto no comete. Este modulo construye esa evidencia: en cada pase de
captura re-evalua el edge de las probabilidades SERVIDAS a las 11:00 (stream
served_*, la misma probabilidad de decision del pipeline, calibracion y shrink
incluidos) contra el consenso del snapshot fresco, y lo appendea a
data/bets/intraday_edge_log.csv.

El analisis posterior responde: los edges que "aparecen" durante el dia
(would_generate=True sin ser pick de las 11:00), ¿tienen CLV positivo o son
el mercado moviendose por informacion que el modelo no tiene? La respuesta
decide la #4 ofensiva con datos, no con especulacion.

Reglas:
- Solo h2h en v1 (sin linea movil; unico mercado con calibrador live).
- NUNCA crea candidates, no toca stakes ni archivos del pipeline: solo log.
- Mismo criterio de frescura que la revalidacion (sin snapshot fresco, nada).
- La probabilidad NO se re-estima: se aisla la variable timing (mismo modelo,
  precio posterior).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from sqp.audit.clv_movement import snapshot_consensus_price
from sqp.logging_config import get_logger
from sqp.pipeline.closing_capture import _parse_utc
from sqp.pipeline.revalidation import _append_log, _fresh_snapshot, _league_odds

log = get_logger("sqp.intraday_scan")

INTRADAY_LOG_FILENAME = "intraday_edge_log.csv"


def _candidate_keys(predictions_dir: Path, league: str) -> set[tuple[str, str, str]]:
    """(event_id, market, selection) de los picks vigentes de la liga."""
    cf = Path(predictions_dir) / f"candidates_{league}.csv"
    if not cf.exists():
        return set()
    try:
        df = pd.read_csv(cf)
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return set()
    if df.empty or not {"event_id", "market", "selection"} <= set(df.columns):
        return set()
    return {(str(r.event_id), str(r.market), str(r.selection))
            for r in df.itertuples()}


def log_intraday_edges(predictions_dir: Path, root: Path, *,
                       min_edge: float, window_min: int = 120,
                       price_max_age_min: float = 90.0,
                       now: datetime | None = None) -> dict:
    """Re-evalua el edge h2h de las probabilidades servidas hoy contra el
    consenso del snapshot fresco para eventos en (now, now+window_min] y
    appendea el resultado al log intradia. Devuelve el resumen del pase."""
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    stamp = now.isoformat()
    summary: dict[str, Any] = {"scanned": 0, "would_generate": 0, "leagues": []}
    rows: list[dict] = []
    cal_dir = Path(root) / "data" / "calibration"
    for sf in sorted(cal_dir.glob("served_*.csv")):
        league = sf.stem.replace("served_", "")
        try:
            served = pd.read_csv(sf)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        need = {"event_id", "market", "selection", "generated_at", "start_time"}
        if served.empty or not need <= set(served.columns):
            continue
        mask = ((served["generated_at"].astype(str).str[:10] == today)
                & (served["market"].astype(str) == "h2h"))
        if not mask.any():
            continue
        odds = _league_odds(root, league)
        if odds.empty:
            continue
        by_event = {str(eid): eo for eid, eo in odds.groupby("event_id")}
        snap_cache: dict[str, pd.DataFrame] = {}
        picks = _candidate_keys(predictions_dir, league)
        n_league = 0
        for r in served[mask].itertuples():
            st = _parse_utc(str(getattr(r, "start_time", "")))
            if st is None or not (now < st <= now + pd.Timedelta(minutes=window_min)):
                continue
            eid = str(r.event_id)
            if eid not in snap_cache:
                snap_cache[eid] = _fresh_snapshot(
                    by_event.get(eid, pd.DataFrame()), now, price_max_age_min)
            snap = snap_cache[eid]
            if snap.empty:
                continue
            price = snapshot_consensus_price(snap, "h2h", str(r.selection), None)
            p = pd.to_numeric(pd.Series(
                [getattr(r, "calibrated_probability", None)]),
                errors="coerce").iloc[0]
            if pd.isna(p):
                p = pd.to_numeric(pd.Series(
                    [getattr(r, "estimated_probability", None)]),
                    errors="coerce").iloc[0]
            if price is None or pd.isna(p):
                continue
            edge_now = float(p) * price - 1.0
            would = edge_now >= min_edge
            summary["scanned"] += 1
            summary["would_generate"] += int(would)
            n_league += 1
            rows.append({
                "timestamp": stamp, "league": league, "event_id": eid,
                "market": "h2h", "selection": str(r.selection),
                "minutes_to_start": round((st - now).total_seconds() / 60.0, 1),
                "prob_basis": round(float(p), 4),
                "entry_price": getattr(r, "price_decimal", float("nan")),
                "entry_edge": getattr(r, "estimated_edge", float("nan")),
                "price_now": price, "edge_now": round(edge_now, 4),
                "would_generate": would,
                "is_candidate": (eid, "h2h", str(r.selection)) in picks,
            })
        if n_league:
            summary["leagues"].append(league)
            log.info("[%s] intraday scan: %d h2h sides evaluated", league, n_league)
    _append_log(rows, root, filename=INTRADAY_LOG_FILENAME)
    return summary
