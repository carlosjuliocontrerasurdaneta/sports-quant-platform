"""Filas de linea de cuarto graduadas ANTES del arreglo de su liquidacion.

Auditoria audit-2026-10-18, AUD-008. Una linea asiatica de cuarto (+-x.25 /
+-x.75) liquida a medias (`half_win`/`half_loss`) cuando el resultado cae en la
mitad entera. Antes del arreglo, la produccion las graduaba `win`/`loss`
enteras. El stream servido es append-only, asi que esas filas siguen ahi: 92
graduadas mal (re-graduadas por Fable con el `_grade` actual), 58 dentro de la
ventana del gate. Medido el 2026-10-18 sobre `data/calibration/graded_*.csv`:
antes del corte apenas hay medias liquidaciones (8 de 572 filas de cuarto);
despues, 80 de 284.

No se re-gradua el stream (los datos crudos no se mutan; re-graduar exige una
autorizacion aparte). Lo que se hace es dejar de CONTAR esas filas, igual que
`prediction_gate.INVALID_BEFORE`: el corte es el instante del commit que trajo
el arreglo a produccion (`c578f52`, 2026-09-13), fijado por el codigo y no por
ningun resultado. Excluye tambien las filas de cuarto de antes del corte que
estaban bien graduadas: se pierde muestra, nunca se cuenta una mal graduada.
Filas sin `generated_at` legible en una linea de cuarto tampoco cuentan
(default-deny).
"""
from __future__ import annotations

import pandas as pd

from sqp.markets.settlement_math import is_quarter_line

QUARTER_LINE_GRADING_FIXED_AT = "2026-09-13T12:36:34+00:00"
_LINE_MARKETS = ("totals", "spreads")


def pre_fix_quarter_line_mask(df: pd.DataFrame) -> pd.Series:
    """True en las filas de linea de cuarto generadas antes del arreglo."""
    if df.empty or not {"market", "line"} <= set(df.columns):
        return pd.Series(False, index=df.index)
    line = pd.to_numeric(df["line"], errors="coerce")
    quarter = df["market"].astype(str).isin(_LINE_MARKETS) & line.map(
        lambda x: bool(pd.notna(x) and is_quarter_line(float(x))))
    if "generated_at" in df.columns:
        gen = pd.to_datetime(df["generated_at"], utc=True, errors="coerce", format="mixed")
    else:
        gen = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    before = (gen < pd.Timestamp(QUARTER_LINE_GRADING_FIXED_AT)) | gen.isna()
    return (quarter & before).astype(bool)


def drop_pre_fix_quarter_lines(df: pd.DataFrame) -> pd.DataFrame:
    """`df` sin las filas de `pre_fix_quarter_line_mask`."""
    if df.empty:
        return df
    return df[~pre_fix_quarter_line_mask(df)]
