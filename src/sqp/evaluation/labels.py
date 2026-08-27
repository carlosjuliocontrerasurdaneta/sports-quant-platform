"""Como se NOMBRA un partido en todas las vistas de picks.

Existe para que haya una sola definicion. Sin ella, "Picks del Dia" mostraba el
partido y las otras tres vistas (dashboard "Todos los Picks", `daily_picks.py`,
`tipster_report.py`) no: en `totals` la seleccion es literalmente "Over" o
"Under", asi que una fila decia `mlb | totals | Over | 8.5` sin decir de QUE
partido (operador, 2026-08-26). Los datos siempre estuvieron ahi -- `home` y
`away` viven en el stream servido; simplemente no se arrastraban a la tabla.
"""
from __future__ import annotations

import pandas as pd

SEPARADOR = " @ "  # visitante @ local, la convencion que ya usaba "Picks del Dia"


def match_label(df: pd.DataFrame, *, fallback: str = "event_id") -> pd.Series:
    """Serie `"visitante @ local"` alineada con `df`.

    Si faltan `home`/`away` cae a `fallback` (por defecto `event_id`): un
    identificador feo identifica el partido, una celda vacia no.
    """
    if "home" in df.columns and "away" in df.columns:
        return (df["away"].fillna("").astype(str) + SEPARADOR
                + df["home"].fillna("").astype(str))
    if fallback in df.columns:
        return df[fallback].fillna("").astype(str)
    return pd.Series("", index=df.index, dtype=str)
