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
from sqp.sports.team_names import normalize_key

log = get_logger("sqp.revalidation")

REVAL_FLAG = "stale_edge_revoked"
PITCHER_CHANGED_FLAG = "pitcher_changed"
STARTER_PULLED_FLAG = "starter_pulled"
REVAL_LOG_FILENAME = "revalidation_log.csv"
DEFAULT_WINDOW_MIN = 120
DEFAULT_PRICE_MAX_AGE_MIN = 90.0


def _append_log(rows: list[dict], root: Path,
                filename: str = REVAL_LOG_FILENAME) -> None:
    """Append a un rastro CSV en data/bets reconciliando columnas (union), para
    que un esquema viejo en disco nunca desalinee filas nuevas (patron KI-011)."""
    if not rows:
        return
    bets_dir = Path(root) / "data" / "bets"
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / filename
    new = pd.DataFrame(rows)
    if path.exists():
        try:
            prior = pd.read_csv(path)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            prior = pd.DataFrame()
        if not prior.empty:
            cols = list(prior.columns) + [c for c in new.columns
                                          if c not in prior.columns]
            new = pd.concat([prior.reindex(columns=cols),
                             new.reindex(columns=cols)], ignore_index=True)
    tmp = path.with_suffix(".csv.tmp")
    new.to_csv(tmp, index=False)
    tmp.replace(path)


def _revoke_row(df: pd.DataFrame, idx: int, flag: str, stamp: str) -> None:
    """Marca la fila como revocada: accion final, flag informativo, stake y
    kelly a 0 (nunca al reves), sello temporal."""
    df.loc[df.index[idx], ["reval_action", "revalidated_at"]] = ["revoke", stamp]
    flags = str(df.loc[df.index[idx], "flags"] or "")
    flags = "" if flags == "nan" else flags
    if flag not in flags:
        df.loc[df.index[idx], "flags"] = f"{flags};{flag}" if flags else flag
    for col in ("stake", "kelly_stake_pct"):
        if col in df.columns:
            df.loc[df.index[idx], col] = 0.0


def _prepare_reval_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col, default in (("reval_action", ""), ("reval_price", float("nan")),
                         ("reval_edge", float("nan")), ("revalidated_at", "")):
        if col not in df.columns:
            df[col] = default
    # flags llega float64 (todo NaN) cuando ninguna fila tiene flag
    df["flags"] = (df["flags"].fillna("").astype(str).replace("nan", "")
                   if "flags" in df.columns else "")
    df["reval_action"] = df["reval_action"].fillna("").astype(str)
    df["revalidated_at"] = df["revalidated_at"].fillna("").astype(str)
    return df


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
        df = _prepare_reval_columns(df)
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
                _revoke_row(df, idx, REVAL_FLAG, stamp)
                log_rows.append({
                    "timestamp": stamp, "league": league,
                    "event_id": str(r.event_id), "market": str(r.market),
                    "selection": str(r.selection),
                    "line": getattr(r, "line", ""),
                    "entry_price": getattr(r, "price_decimal", ""),
                    "reval_price": price, "reval_edge": round(reval_edge, 4),
                    "reason": "edge_below_min",
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
    _append_log(log_rows, root)
    return summary


def revalidate_pitchers(predictions_dir: Path, root: Path, league: str, *,
                        fetch_probables, normalize=None,
                        now: datetime | None = None,
                        window_min: int = DEFAULT_WINDOW_MIN) -> dict:
    """Guard de informacion temprana (beisbol): revoca picks del dia cuyo
    ABRIDOR anunciado cambio despues de generarse el pick, o fue retirado sin
    reemplazo anunciado. El estimado quedo condicionado a un abridor que ya no
    lanza — extension temporal de la regla "Starter unknown" (sin abridor no
    hay candidatos). La linea base son los home_pitcher/away_pitcher del
    momento del pick (predictions_<liga>.csv); el estado actual se re-consulta
    a la MLB Stats API (gratis) en cada pase horario, solo para eventos en
    (now, now+window_min].

    Conservador como el pase de precio: fallo de fetch o partido no emparejado
    = sin accion (nunca revoca a ciegas); solo baja stakes; revoke final.
    ``fetch_probables(day)`` y ``normalize`` son inyectables (tests); nombres
    de pitcher comparados con normalize_key (acentos/mayusculas)."""
    from sqp.pipeline.daily import _closest_probable, _parse_iso_utc, _prior_day
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    nk = normalize or normalize_key
    summary: dict[str, Any] = {"checked": 0, "revoked": 0,
                               "skipped_unmatched": 0}
    cf = Path(predictions_dir) / f"candidates_{league}.csv"
    pf = Path(predictions_dir) / f"predictions_{league}.csv"
    if not cf.exists() or not pf.exists():
        return summary
    try:
        df = pd.read_csv(cf)
        preds = pd.read_csv(pf)
    except (pd.errors.EmptyDataError, ValueError):
        return summary
    if df.empty or "event_id" not in df.columns or preds.empty:
        return summary
    if not {"home_pitcher", "away_pitcher"} <= set(preds.columns):
        return summary                      # sin linea base (picks pre-feature)
    pred_by_event = {str(p.event_id): p for p in preds.itertuples()}

    # eventos del dia en ventana con linea base de abridores
    targets: dict[str, tuple] = {}
    for idx, r in enumerate(df.itertuples()):
        if str(getattr(r, "generated_at", ""))[:10] != today:
            continue
        if str(getattr(r, "reval_action", "")) == "revoke":
            continue
        p = pred_by_event.get(str(r.event_id))
        if p is None:
            continue
        st = _parse_utc(str(getattr(p, "start_time", "")))
        if st is None or not (now < st <= now + pd.Timedelta(minutes=window_min)):
            continue
        base_hp = str(getattr(p, "home_pitcher", "") or "")
        base_ap = str(getattr(p, "away_pitcher", "") or "")
        if base_hp in ("", "nan") and base_ap in ("", "nan"):
            continue                        # sin abridores base: nada que vigilar
        targets.setdefault(str(r.event_id), (p, []))[1].append(idx)
    if not targets:
        return summary

    fetch_days: set[str] = set()
    for p, _idxs in targets.values():
        day = str(getattr(p, "start_time", ""))[:10]
        fetch_days.add(day)
        if (prior := _prior_day(day)) is not None:
            fetch_days.add(prior)
    by_pair: dict[tuple, list[dict]] = {}
    try:
        for day in sorted(fetch_days):
            for g in fetch_probables(day):
                by_pair.setdefault((nk(g["home"]), nk(g["away"])), []).append(g)
    except Exception as exc:
        log.warning("[%s] pitcher revalidation fetch failed (no action): %s",
                    league, exc)
        return summary

    df = _prepare_reval_columns(df)
    stamp = now.isoformat()
    log_rows: list[dict] = []
    changed = False
    for eid, (p, idxs) in targets.items():
        cands = by_pair.get((nk(str(p.home)), nk(str(p.away))), [])
        g = _closest_probable(cands, _parse_iso_utc(str(p.start_time)))
        if g is None:
            summary["skipped_unmatched"] += 1
            continue
        summary["checked"] += 1
        flag = None
        detail = ""
        for side, base in (("home", str(getattr(p, "home_pitcher", "") or "")),
                           ("away", str(getattr(p, "away_pitcher", "") or ""))):
            if base in ("", "nan"):
                continue
            current = g.get(f"{side}_pitcher")
            if current is None or str(current).strip() == "":
                flag, detail = STARTER_PULLED_FLAG, f"{side}: {base} -> (none)"
                break
            if normalize_key(str(current)) != normalize_key(base):
                flag = PITCHER_CHANGED_FLAG
                detail = f"{side}: {base} -> {current}"
                break
        if flag is None:
            continue
        for idx in idxs:
            r = df.iloc[idx]
            _revoke_row(df, idx, flag, stamp)
            log_rows.append({
                "timestamp": stamp, "league": league, "event_id": eid,
                "market": str(r.get("market", "")),
                "selection": str(r.get("selection", "")),
                "line": r.get("line", ""), "entry_price": r.get("price_decimal", ""),
                "reval_price": float("nan"), "reval_edge": float("nan"),
                "reason": ("pitcher_changed" if flag == PITCHER_CHANGED_FLAG
                           else "starter_pulled"), "detail": detail,
            })
            summary["revoked"] += 1
        log.info("[%s] %s revoked %d pick(s) for %s (%s)", league, flag,
                 len(idxs), eid, detail)
        changed = True
    if changed:
        tmp = cf.with_suffix(".csv.tmp")
        df.to_csv(tmp, index=False)
        tmp.replace(cf)
    _append_log(log_rows, root)
    return summary
