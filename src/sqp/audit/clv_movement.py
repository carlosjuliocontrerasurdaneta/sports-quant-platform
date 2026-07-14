"""CLV condicionado al movimiento de linea previo al pick.

Analisis retrospectivo del filtro de confirmacion (2026-07-14). Hipotesis: la
seleccion adversa del sistema (CLV mediano ~0, beat-close ~40%) deberia
concentrarse en los picks cuyo desacuerdo con el mercado va CONTRA el
movimiento previo de la linea; si el CLV condicionado a "el mercado venia
moviendose hacia nuestro lado" separa con muestra suficiente, un filtro de
confirmacion por movimiento es candidato a gate de generacion (esa seria una
fase posterior, validada aparte — este modulo NO toca el pipeline).

Movimiento = prob. implicita del consenso (mediana entre books) de NUESTRA
seleccion en el ultimo snapshot <= generated_at, menos la del snapshot mas
antiguo disponible del evento, en puntos porcentuales. "hacia" = la prob.
implicita subio (el mercado se movio en nuestra direccion antes del pick).
Cobertura limitada a eventos con >= 2 snapshots pre-pick capturados.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from sqp.audit.clv import CLOSE_MAX_AGE_MIN, _point, compute_clv

# |movimiento| <= este umbral (pp de prob. implicita) se clasifica "plano":
# absorbe ruido de redondeo de cuotas y cambios de composicion de books.
MOVEMENT_FLAT_PP = 0.5


def movement_direction(movement_pp: float,
                       flat_pp: float = MOVEMENT_FLAT_PP) -> str:
    """"hacia" (el mercado vino a nuestro lado), "contra" o "plano"."""
    if movement_pp > flat_pp:
        return "hacia"
    if movement_pp < -flat_pp:
        return "contra"
    return "plano"


def _consensus_price(snap: pd.DataFrame, market: str, selection: str,
                     point: float | None) -> float | None:
    """Mediana del precio decimal entre books para (market, selection, point)
    dentro de un snapshot; None sin filas validas. Mismo criterio de consenso
    que _consensus_lines (mediana real), sobre las filas crudas del store."""
    m = snap[(snap["market"].astype(str) == market)
             & (snap["outcome"].astype(str) == selection)]
    if m.empty:
        return None
    pts = pd.to_numeric(m.get("point"), errors="coerce")
    m = m[pts.isna()] if point is None else m[pts == point]
    prices = pd.to_numeric(m.get("price_decimal"), errors="coerce").dropna()
    prices = prices[prices > 1.0]
    return float(prices.median()) if not prices.empty else None


def pre_pick_movement(event_odds: pd.DataFrame, *, market: str, selection: str,
                      point: float | None, picked_at: str) -> dict | None:
    """Movimiento del consenso de la seleccion entre el snapshot mas antiguo
    del evento y el ultimo <= picked_at. None si no hay >= 2 snapshots
    distintos pre-pick o falta consenso en alguno de los dos extremos."""
    if event_odds.empty or not picked_at:
        return None
    ts = pd.to_datetime(event_odds["captured_at"], errors="coerce", utc=True)
    try:
        pick_ts = pd.Timestamp(picked_at)
        if pick_ts.tzinfo is None:
            pick_ts = pick_ts.tz_localize("UTC")
    except (ValueError, TypeError):
        return None
    pre = event_odds[ts.notna() & (ts <= pick_ts)]
    if pre.empty:
        return None
    stamps = sorted(pd.to_datetime(pre["captured_at"], utc=True).unique())
    if len(stamps) < 2:
        return None
    pre_ts = pd.to_datetime(pre["captured_at"], utc=True)
    ref = _consensus_price(pre[pre_ts == stamps[0]], market, selection, point)
    at_pick = _consensus_price(pre[pre_ts == stamps[-1]], market, selection,
                               point)
    if ref is None or at_pick is None:
        return None
    return {
        "movement_pp": (1.0 / at_pick - 1.0 / ref) * 100.0,
        "n_snapshots": len(stamps),
        "lookback_h": float((stamps[-1] - stamps[0]).total_seconds() / 3600.0),
    }


def clv_by_movement(bets_dir: Path, root: Path, *,
                    max_age_min: float | None = CLOSE_MAX_AGE_MIN,
                    flat_pp: float = MOVEMENT_FLAT_PP,
                    ) -> tuple[pd.DataFrame, dict]:
    """Filas de CLV (compute_clv, mismo filtro de frescura del gate) enriquecidas
    con el movimiento pre-pick y su direccion. Devuelve (df, cobertura):
    los picks sin generated_at o sin >= 2 snapshots pre-pick quedan fuera del
    df pero contados en la cobertura."""
    clv_df, unmatched = compute_clv(bets_dir, root, max_age_min=max_age_min)
    coverage = {"n_unmatched_close": int(unmatched),
                "n_matched_close": int(len(clv_df)), "n_with_movement": 0}
    if clv_df.empty:
        return pd.DataFrame(), coverage
    odds_dir = root / "data" / "odds"
    rows: list[dict] = []
    for lg, g in clv_df.groupby("league"):
        files = sorted(odds_dir.glob(f"odds_{lg}_*.csv"))
        if not files:
            continue
        odds = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
        by_event = {str(eid): eo for eid, eo in odds.groupby("event_id")}
        for r in g.itertuples():
            eo = by_event.get(str(r.event_id))
            if eo is None:
                continue
            mov = pre_pick_movement(
                eo, market=str(r.market), selection=str(r.selection),
                point=_point(str(r.market), r.line),
                picked_at=str(r.generated_at))
            if mov is None:
                continue
            rows.append({**r._asdict(), **mov,
                         "direction": movement_direction(mov["movement_pp"],
                                                         flat_pp)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.drop(columns=["Index"], errors="ignore")
    coverage["n_with_movement"] = int(len(df))
    return df, coverage


def movement_segments(df: pd.DataFrame,
                      by: list[str] | None = None) -> pd.DataFrame:
    """n, CLV mediano/medio, % que batio el cierre, hit-rate y ROI a stake
    plano por direccion del movimiento (o por by+direccion)."""
    if df.empty:
        return pd.DataFrame()
    won = (df["result"].astype(str) == "win")
    tmp = df.assign(_pnl_flat=(pd.to_numeric(df["entry"], errors="coerce")
                               - 1.0).where(won, -1.0),
                    _won=won.astype(float))
    out = (tmp.groupby((by or []) + ["direction"])
              .agg(n=("clv_pct", "size"),
                   median_clv_pct=("clv_pct", "median"),
                   mean_clv_pct=("clv_pct", "mean"),
                   beat_close_rate=("beat_close", "mean"),
                   hit_rate=("_won", "mean"),
                   roi_flat=("_pnl_flat", "mean"))
              .reset_index())
    for c in ("median_clv_pct", "mean_clv_pct", "beat_close_rate", "hit_rate",
              "roi_flat"):
        out[c] = out[c].round(4)
    return out
