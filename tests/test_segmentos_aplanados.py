"""Deteccion de segmentos servidos con la probabilidad calibrada aplanada.

Un calibrador colapsado en produccion no solo estropea los picks del dia: deja
su huella en el stream servido, y cualquier medicion posterior sobre esas filas
puntua una CONSTANTE creyendo que puntua al modelo.

Medido el 2026-08-28: `wnba_totals` sirvio asi del 2026-07-22 al 2026-08-27 (34
dias, 412 filas) y `mlb_totals` del 2026-07-28 al 2026-08-23 (14 dias, 342
filas). 754 filas del stream con veredicto por segmento sin significado.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sqp.evaluation.model_vs_market import flattened_segments


def _dia(liga: str, mercado: str, dia: str, *, cal, mod, n: int = 10) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "league": liga, "market": mercado,
        "generated_at": f"{dia}T11:00:00+00:00",
        "calibrated_probability": np.full(n, cal) if np.isscalar(cal)
        else rng.uniform(*cal, n),
        "model_probability": rng.uniform(*mod, n),
    })


def test_detecta_un_segmento_aplanado():
    df = pd.concat([_dia("wnba", "totals", "2026-08-2%d" % d,
                         cal=0.49, mod=(0.30, 0.70)) for d in range(1, 5)])
    out = flattened_segments(df)
    assert len(out) == 1
    fila = out.iloc[0]
    assert fila["league"] == "wnba" and fila["market"] == "totals"
    assert fila["dias"] == 4 and fila["filas"] == 40
    assert fila["desde"] == "2026-08-21" and fila["hasta"] == "2026-08-24"


def test_un_segmento_sano_no_se_reporta():
    df = pd.concat([_dia("mlb", "h2h", "2026-08-2%d" % d,
                         cal=(0.35, 0.65), mod=(0.30, 0.70)) for d in range(1, 5)])
    assert flattened_segments(df).empty


def test_no_acusa_cuando_el_MODELO_es_el_plano():
    """Si el modelo tampoco discrimina, el calibrado plano no prueba que haya un
    calibrador colapsado: no hay nada que aplanar. Acusar ahi seria un falso
    positivo permanente en mercados de poca senal."""
    df = pd.concat([_dia("liga", "totals", "2026-08-2%d" % d,
                         cal=0.49, mod=(0.49, 0.51)) for d in range(1, 5)])
    assert flattened_segments(df).empty


def test_un_frame_sin_las_columnas_no_revienta():
    """Lo consume un script de informe: un esquema viejo no debe tumbarlo."""
    out = flattened_segments(pd.DataFrame({"league": ["mlb"]}))
    assert out.empty
    assert list(out.columns) == ["league", "market", "dias", "filas",
                                "desde", "hasta"]
