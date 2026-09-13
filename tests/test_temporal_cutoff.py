"""Frontera train/test de la validacion fuera de muestra.

AUD-MED-018 (auditoria integral 2026-09-10). El cuerpo estaba duplicado BYTE A
BYTE en `scripts/validate_oos.py` y `scripts/oos_pitcher_mlb.py`, sin
implementacion en `src/` y sin ningun test. Es la superficie exacta donde una
correccion de contaminacion train/test se aplica a una copia y no a la otra.
"""
from __future__ import annotations

import pytest

from sqp.backtesting.tuning import temporal_cutoff


def _res(fechas):
    return [{"date": f} for f in fechas]


def test_un_corte_preregistrado_manda_sobre_la_fraccion():
    """Un corte fijado de antemano no se recalcula: eso es lo que lo hace
    pre-registro y no seleccion posterior al resultado."""
    r = _res(["2026-01-01", "2026-02-01", "2026-03-01"])
    assert temporal_cutoff(r, 0.5, "2026-08-16") == "2026-08-16"


def test_la_fraccion_deja_esa_proporcion_de_muestra_a_la_derecha():
    r = _res([f"2026-01-{d:02d}" for d in range(1, 11)])   # 10 fechas
    corte = temporal_cutoff(r, 0.2, None)                  # 20% a test
    assert corte == "2026-01-09"
    train = [x for x in r if x["date"] < corte]
    assert len(train) == 8 and len(r) - len(train) == 2


def test_sin_resultados_sigue_lanzando_indexerror():
    """CONTRATO CONSERVADO, no arreglado aqui.

    Es la causa exacta del fallo de `frauen_bundesliga` del 2026-09-01 (KI-034):
    con `results == []`, `max(0, min(-1, 0))` da 0 y `results[0]` no existe. El
    arreglo de KI-034 no fue tolerarlo en esta funcion sino NO LLEGAR:
    `validate_oos.py` detecta la liga sin resultados y se la salta. Tolerarlo
    aqui desactivaria
    `test_validate_oos_exit_code.py::test_cutoff_con_resultados_vacios_reventaba`
    y convertiria "no hay nada que validar" en un corte silencioso.

    AUD-MED-018 solo deduplico esta funcion; su contrato no entraba en el
    alcance aprobado."""
    with pytest.raises(IndexError):
        temporal_cutoff([], 0.2, None)


def test_una_sola_observacion_no_desborda():
    assert temporal_cutoff(_res(["2026-05-05"]), 0.2, None) == "2026-05-05"


@pytest.mark.parametrize("frac", [0.0, 1.0])
def test_las_fracciones_extremas_siguen_dentro_del_rango(frac):
    r = _res([f"2026-01-{d:02d}" for d in range(1, 6)])
    assert temporal_cutoff(r, frac, None) in {x["date"] for x in r}


def test_los_dos_scripts_oos_delegan_en_la_implementacion_canonica():
    """Cierra la CLASE: si alguien vuelve a copiar el cuerpo, esto lo ve."""
    import importlib.util
    from sqp.config import ROOT
    for nombre in ("validate_oos", "oos_pitcher_mlb"):
        texto = (ROOT / "scripts" / f"{nombre}.py").read_text(encoding="utf-8")
        assert "temporal_cutoff" in texto, f"{nombre} no usa la version canonica"
        assert "int(len(results) * (1.0 - test_frac))" not in texto, (
            f"{nombre} volvio a llevar su propia copia de la frontera train/test")
        assert importlib.util.find_spec("sqp.backtesting.tuning") is not None
