"""Segundo pase pre-partido: re-validacion del edge contra la linea vigente.

Correccion de la desventaja de timing (diagnostico 2026-07-14): los picks se
generan por la manana pero se liquidan contra una realidad que el cierre ya
preciaba (lineups, abridores, clima). Este pase corre tras cada captura de
cierre horaria (CAPTURE_CLOSE, sin cuota extra: reusa el snapshot recien
persistido) y, para los picks del dia cuyo evento comienza dentro de la
ventana, recalcula el edge al consenso vigente; si el pick ya NO se generaria
(edge actual < min_edge), lo REVOCA: stake y kelly a 0, flag
"stale_edge_revoked" y rastro en data/bets/revalidation_log.csv.

Reglas conservadoras:
- Un revoke es FINAL (no se deshace aunque el precio se recupere); un "keep"
  se re-evalua en cada pase posterior hasta el comienzo.
- Sin snapshot fresco (<= price_max_age_min) no se actua: sin datos no hay
  accion, nunca se revoca a ciegas.
- Solo toca filas generadas HOY (scoping por dia, como el resto del pipeline)
  y solo baja stakes, nunca los sube.
- Bajo shadow mode (stakes ya 0) el efecto es de MEDICION: la etiqueta
  reval_action=revoke|keep viaja al settled via la persistencia por union de
  columnas, y permite comparar CLV/ROI de revocados vs mantenidos antes de
  que el pase tenga efecto economico real.

La probabilidad base re-usa la del pick ((adjusted_edge+1)/precio de entrada,
que preserva la penalizacion de EV; fallback a estimated_probability): este
pase re-valida el PRECIO, no re-estima el modelo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from sqp.audit.clv import _point
from sqp.audit.clv_movement import snapshot_consensus_price
from sqp.logging_config import get_logger
from sqp.pipeline.closing_capture import _parse_utc

log = get_logger("sqp.revalidation")

REVAL_FLAG = "stale_edge_revoked"
REVAL_LOG_FILENAME = "revalidation_log.csv"
DEFAULT_WINDOW_MIN = 120
DEFAULT_PRICE_MAX_AGE_MIN = 90.0


def _start_times(predictions_dir: Path, league: str) -> dict[str, str]:
    pf = predictions_dir / f"predictions_{league}.csv"
    if not pf.exists() or pf.stat().st_size <= 1:
        return {}
    try:
        preds = pd.read_csv(pf, usecols=lambda c: c in ("event_id", "start_time"))
    except (pd.errors.EmptyDataError, ValueError):
        return {}
    if "start_time" not in preds.columns:
        return {}
    return {str(r.event_id): str(r.start_time) for r in preds.itertuples()}


def _league_odds(root: Path, league: str) -> pd.DataFrame:
    files = sorted((root / "data" / "odds").glob(f"odds_{league}_*.csv"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def _fresh_snapshot(event_odds: pd.DataFrame, now: datetime,
                    max_age_min: float) -> pd.DataFrame:
    """Filas del ultimo snapshot <= now si tiene a lo sumo max_age_min de
    antiguedad; DataFrame vacio si no hay captura fresca."""
    if event_odds.empty:
        return pd.DataFrame()
    ts = pd.to_datetime(event_odds["captured_at"], errors="coerce", utc=True)
    pre = event_odds[ts.notna() & (ts <= pd.Timestamp(now))]
    if pre.empty:
        return pd.DataFrame()
    latest = pd.to_datetime(pre["captured_at"], utc=True).max()
    if (pd.Timestamp(now) - latest).total_seconds() / 60.0 > max_age_min:
        return pd.DataFrame()
    return pre[pd.to_datetime(pre["captured_at"], utc=True) == latest]


def _prob_basis(row) -> float | None:
    """Probabilidad con la que se re-valida el precio: la efectiva del pick
    ((adjusted_edge+1)/entrada, preserva la penalizacion de EV) o la estimada."""
    entry = pd.to_numeric(pd.Series([getattr(row, "price_decimal", None)]),
                          errors="coerce").iloc[0]
    adj = pd.to_numeric(pd.Series([getattr(row, "adjusted_edge", None)]),
                        errors="coerce").iloc[0]
    if pd.notna(adj) and pd.notna(entry) and entry > 1.0:
        return float((adj + 1.0) / entry)
    est = pd.to_numeric(pd.Series([getattr(row, "estimated_probability", None)]),
                        errors="coerce").iloc[0]
    return float(est) if pd.notna(est) else None


def revalidate_candidates(predictions_dir: Path, root: Path, *,
                          min_edge: float,
                          window_min: int = DEFAULT_WINDOW_MIN,
                          price_max_age_min: float = DEFAULT_PRICE_MAX_AGE_MIN,
                          now: datetime | None = None) -> dict:
    """Re-valida los picks del dia con evento en (now, now+window_min] contra
    el consenso del ultimo snapshot fresco. Devuelve el resumen del pase."""
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    summary: dict[str, Any] = {"evaluated": 0, "revoked": 0, "kept": 0,
                               "skipped_no_price": 0, "leagues": []}
    log_rows: list[dict] = []
    for cf in sorted(Path(predictions_dir).glob("candidates_*.csv")):
        league = cf.stem.replace("candidates_", "")
        try:
            df = pd.read_csv(cf)
        except (pd.errors.EmptyDataError, ValueError):
            continue
        if df.empty or "event_id" not in df.columns:
            continue
        starts = _start_times(Path(predictions_dir), league)
        odds = _league_odds(root, league)
        if odds.empty:
            continue
        by_event = {str(eid): eo for eid, eo in odds.groupby("event_id")}
        changed = False
        for col, default in (("reval_action", ""), ("reval_price", float("nan")),
                             ("reval_edge", float("nan")),
                             ("revalidated_at", "")):
            if col not in df.columns:
                df[col] = default
        # flags llega float64 (todo NaN) cuando ninguna fila tiene flag
        df["flags"] = (df["flags"].fillna("").astype(str).replace("nan", "")
                       if "flags" in df.columns else "")
        df["reval_action"] = df["reval_action"].fillna("").astype(str)
        df["revalidated_at"] = df["revalidated_at"].fillna("").astype(str)
        for idx, r in enumerate(df.itertuples()):
            gen = str(getattr(r, "generated_at", ""))[:10]
            if gen != today:
                continue
            if str(getattr(r, "reval_action", "")) == "revoke":
                continue                       # final: nunca se deshace
            st = _parse_utc(starts.get(str(r.event_id), ""))
            if st is None or not (now < st <= now + pd.Timedelta(minutes=window_min)):
                continue
            snap = _fresh_snapshot(by_event.get(str(r.event_id), pd.DataFrame()),
                                   now, price_max_age_min)
            if snap.empty:
                summary["skipped_no_price"] += 1
                continue
            price = snapshot_consensus_price(
                snap, str(r.market), str(r.selection),
                _point(str(r.market), getattr(r, "line", None)))
            p = _prob_basis(r)
            if price is None or p is None:
                summary["skipped_no_price"] += 1
                continue
            reval_edge = p * price - 1.0
            summary["evaluated"] += 1
            stamp = now.isoformat()
            df.loc[df.index[idx], ["reval_price", "reval_edge",
                                   "revalidated_at"]] = [price, reval_edge, stamp]
            if reval_edge < min_edge:
                summary["revoked"] += 1
                df.loc[df.index[idx], "reval_action"] = "revoke"
                flags = str(getattr(r, "flags", "") or "")
                flags = "" if flags == "nan" else flags
                if REVAL_FLAG not in flags:
                    df.loc[df.index[idx], "flags"] = (
                        f"{flags};{REVAL_FLAG}" if flags else REVAL_FLAG)
                for col in ("stake", "kelly_stake_pct"):
                    if col in df.columns:
                        df.loc[df.index[idx], col] = 0.0
                log_rows.append({
                    "timestamp": stamp, "league": league,
                    "event_id": str(r.event_id), "market": str(r.market),
                    "selection": str(r.selection),
                    "line": getattr(r, "line", ""),
                    "entry_price": getattr(r, "price_decimal", ""),
                    "reval_price": price, "reval_edge": round(reval_edge, 4),
                })
                log.info("[%s] revoked %s %s %s: edge %.4f < %.4f at close %.3f",
                         league, r.event_id, r.market, r.selection,
                         reval_edge, min_edge, price)
            else:
                summary["kept"] += 1
                df.loc[df.index[idx], "reval_action"] = "keep"
            changed = True
        if changed:
            tmp = cf.with_suffix(".csv.tmp")
            df.to_csv(tmp, index=False)
            tmp.replace(cf)
            summary["leagues"].append(league)
    if log_rows:
        bets_dir = Path(root) / "data" / "bets"
        bets_dir.mkdir(parents=True, exist_ok=True)
        out = bets_dir / REVAL_LOG_FILENAME
        pd.DataFrame(log_rows).to_csv(out, mode="a",
                                      header=not out.exists(), index=False)
    return summary
