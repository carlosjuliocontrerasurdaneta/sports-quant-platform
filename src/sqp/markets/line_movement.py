"""Pregame line movement from OddsStore snapshots for the pick pipeline.

At pick-generation time: load all captured odds for a league once, then for
each (event_id, market, selection, point) compute how the consensus implied
probability moved from the first to the most recent snapshot, and how fast.

movement_pp > 0         = market moved TOWARD the pick (implied prob rose)
movement_pp < 0         = market moved AGAINST the pick (implied prob fell)
velocity_pp_per_h > 0   = fast move toward; < 0 = fast move against
None                    = fewer than 2 distinct snapshots or no consensus price.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from sqp.audit.clv_movement import snapshot_consensus_price
from sqp.evaluation.labels import instantes_utc


@dataclass(frozen=True)
class LineMovement:
    movement_pp: float
    velocity_pp_per_h: float  # movement_pp / lookback_h; 0 when lookback_h == 0
    n_snapshots: int
    lookback_h: float


def load_league_odds(league: str, odds_dir: Path) -> pd.DataFrame:
    """Load all captured odds for a league from data/odds/ CSVs.

    Returns an empty DataFrame when no files exist (e.g. demo mode or new league).
    """
    files = sorted(odds_dir.glob(f"odds_{league}_*.csv"))
    if not files:
        return pd.DataFrame()
    return pd.concat(
        [pd.read_csv(f, low_memory=False) for f in files],
        ignore_index=True,
    )


def event_line_movement(
    league_odds: pd.DataFrame,
    event_id: str,
    market: str,
    selection: str,
    point: float | None,
) -> LineMovement | None:
    """Return movement and velocity from oldest to newest snapshot.

    movement_pp: implied-prob delta in pp (negative = adverse for pick).
    velocity_pp_per_h: movement_pp / hours between first and last snapshot.
    None when <2 snapshots or no consensus price at one or both ends.
    """
    if league_odds.empty:
        return None
    event_odds = league_odds[league_odds["event_id"].astype(str) == str(event_id)]
    if event_odds.empty:
        return None
    # Parser CANONICO (`labels.instantes_utc`), no `pd.to_datetime` a pelo
    # (auditoria integral 2026-09-07, AUD-LOW-005). Habia TRES parseos de la
    # misma columna, ninguno con `format="ISO8601"`.
    #
    # Sin ese formato pandas infiere UNO SOLO para toda la serie y convierte en
    # `NaT` toda variante ISO que no encaje. Aqui eso no lanzaba nada: el
    # `errors="coerce"` del primer parseo se tragaba las filas discrepantes y el
    # evento perdia snapshots EN SILENCIO. Medido sobre `["...T11:00:00Z",
    # "...T11:00:00"]` (con zona + naive, ambos ISO validos): la version anterior
    # se quedaba con UN snapshot de dos y devolvia `None` -- "no hay movimiento"
    # -- en vez de medir los +12,5 pp que habia. El fallo se presentaba como
    # ausencia de dato, que es la forma mas dificil de notar.
    #
    # No es un fallo alcanzable HOY: los dos escritores de `captured_at` sellan
    # siempre con zona (`odds_store.append_snapshot` usa `datetime.now(
    # timezone.utc)`, y el backfill copia el sello `Z` del proveedor), asi que la
    # mezcla peligrosa no se produce. La mezcla que `roi_engine` SI documenta --
    # `+00:00` frente a `Z`, ambos con zona -- pandas la resuelve bien. Es, por
    # tanto, un candado, no una reparacion.
    #
    # `instantes_utc` existe justo para que este parseo viva en un solo sitio: su
    # docstring dice que no se puede saltar, y aqui se estaba saltando. De paso
    # se parsea UNA vez en lugar de tres.
    ts = instantes_utc(event_odds["captured_at"])
    valid_ts = ts[ts.notna()]
    if valid_ts.empty:
        return None
    valid = event_odds.loc[valid_ts.index]
    stamps = sorted(valid_ts.unique())
    if len(stamps) < 2:
        return None
    ref = snapshot_consensus_price(
        valid[valid_ts == stamps[0]], market, selection, point
    )
    last = snapshot_consensus_price(
        valid[valid_ts == stamps[-1]], market, selection, point
    )
    if ref is None or last is None:
        return None
    movement_pp = (1.0 / last - 1.0 / ref) * 100.0
    lookback_h = float((stamps[-1] - stamps[0]).total_seconds() / 3600.0)
    velocity_pp_per_h = movement_pp / lookback_h if lookback_h > 0.0 else 0.0
    return LineMovement(
        movement_pp=movement_pp,
        velocity_pp_per_h=velocity_pp_per_h,
        n_snapshots=len(stamps),
        lookback_h=lookback_h,
    )
