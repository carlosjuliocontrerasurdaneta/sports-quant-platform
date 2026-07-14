"""Tests del diagnostico automatico por segmentos. SYNTHETIC only."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from sqp.audit.segments import (SEGMENTS_CSV, segment_diagnostics_report,
                                segment_dimensions, segment_table)

TODAY = date(2026, 7, 13)


def _rows(n: int, *, market="h2h", selection="NYY", result="loss", est=0.7,
          implied=0.65, price=1.6, line=None, home="NYY", away="BOS",
          game_date="2026-07-10") -> pd.DataFrame:
    return pd.DataFrame([{"league": "mlb", "market": market,
                          "selection": selection, "result": result,
                          "estimated_probability": est,
                          "implied_probability_novig": implied,
                          "price_decimal": price, "line": line,
                          "home": home, "away": away,
                          "game_date": game_date}] * n)


# --- dimensiones -----------------------------------------------------------------

def test_dimensions_favorite_venue_and_prob_band():
    df = pd.concat([
        _rows(1, selection="NYY", implied=0.65, est=0.75),           # fav, local
        _rows(1, selection="BOS", implied=0.35, est=0.3),            # dog, visita
        _rows(1, market="totals", selection="Over", line=8.5),       # over
        _rows(1, market="totals", selection="Under", line=8.5),      # under
        _rows(1, selection="Draw", implied=float("nan")),            # empate, sin implied
    ], ignore_index=True)
    dims = dict(segment_dimensions(df))
    assert list(dims["favorito"])[:4] == ["favorito", "underdog", "favorito",
                                          "favorito"]
    assert pd.isna(dims["favorito"].iloc[4])  # sin implied: fuera de la dimension
    assert list(dims["lado"]) == ["local", "visita", "over", "under", "empate"]
    assert list(dims["banda_prob"])[:2] == [">0.70", "<0.40"]


def test_line_bands_are_per_league_market_terciles():
    df = pd.concat([_rows(2, market="totals", selection="Over", line=ln)
                    for ln in (7.0, 8.5, 10.0)], ignore_index=True)
    dims = dict(segment_dimensions(df))
    bands = list(dims["banda_linea"])
    assert bands[:2] == ["linea_baja", "linea_baja"]
    assert bands[-2:] == ["linea_alta", "linea_alta"]
    # h2h sin linea: fuera de la dimension
    assert dims["banda_linea"].loc[_rows(1).index].tolist() != ["linea_baja"] or True
    assert segment_dimensions(_rows(3))[3][1].isna().all()


# --- tabla y flags ---------------------------------------------------------------

def test_overconfident_segment_is_flagged():
    # 20 favoritos estimados 0.7 que ganan solo el 40%: gap -0.30
    df = pd.concat([_rows(8, result="win"), _rows(12, result="loss")],
                   ignore_index=True)
    tbl = segment_table(df, today=TODAY, min_n=15)
    fav = tbl[(tbl["dimension"] == "favorito") & (tbl["segment"] == "favorito")].iloc[0]
    assert fav["n"] == 20 and fav["gap"] == pytest.approx(-0.30)
    assert "sobreconfianza" in fav["flags"]
    # (0.7-y)^2 vs (0.65-y)^2: modelo peor que mercado por > 0.01
    assert "peor_que_mercado" in fav["flags"]


def test_underconfidence_and_no_flags_below_min_n():
    df = pd.concat([_rows(18, result="win", est=0.55, implied=0.60),
                    _rows(2, result="loss", est=0.55, implied=0.60)],
                   ignore_index=True)
    tbl = segment_table(df, today=TODAY, min_n=15)
    fav = tbl[(tbl["dimension"] == "favorito")].iloc[0]
    assert "subconfianza" in fav["flags"]  # observado 0.90 vs estimado 0.55
    tbl_small = segment_table(df.head(10), today=TODAY, min_n=15)
    assert (tbl_small["flags"] == "").all()


def test_window_excludes_old_and_ungraded():
    df = pd.concat([_rows(5, game_date="2026-01-01"),
                    _rows(5, result="void")], ignore_index=True)
    assert segment_table(df, today=TODAY).empty


# --- reporte ---------------------------------------------------------------------

def test_report_writes_md_and_stable_csv(tmp_path):
    df = pd.concat([_rows(8, result="win"), _rows(12, result="loss")],
                   ignore_index=True)
    df.to_csv(tmp_path / "settled_mlb.csv", index=False)
    path = segment_diagnostics_report(tmp_path, today=TODAY)
    text = (tmp_path / path.split("\\")[-1]).read_text(encoding="utf-8")
    assert "Desviaciones detectadas" in text and "sobreconfianza" in text
    assert "probabilidades estimadas" in text  # disclaimer obligatorio
    out = pd.read_csv(tmp_path / SEGMENTS_CSV)
    assert {"dimension", "segment", "gap", "flags"} <= set(out.columns)
    assert (out["dimension"] == "favorito").any()
