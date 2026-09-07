"""Movimiento de linea prepartido: contrato y robustez del parseo de instantes.

Este modulo NO tenia ni una prueba directa hasta el 2026-09-07 (auditoria
integral): ningun test referenciaba `event_line_movement` ni `load_league_odds`,
pese a que `pipeline.daily` los llama por CADA seleccion de CADA evento del run
diario y su salida alimenta las penalizaciones de movimiento y velocidad de
`adjusted_edge`. Que los coeficientes esten hoy a 0 hace el TERMINO inocuo, no
la LLAMADA: la funcion se ejecuta igual, y una excepcion suya sube hasta el
`try/except` por liga de `run_all` y le cuesta a esa liga los picks del dia.

El caso que motiva el fichero es AUD-LOW-005: habia tres parseos de
`captured_at`, el primero con `errors="coerce"` y los otros dos sin `errors` y
sin `format="ISO8601"`.
"""
from __future__ import annotations

import pandas as pd
import pytest

from sqp.markets.line_movement import event_line_movement, load_league_odds


def _fila(captured_at: str, price: float, *, event_id: str = "e1",
          outcome: str = "A", market: str = "h2h", point=None,
          bookmaker: str = "bk1") -> dict:
    return {"captured_at": captured_at, "event_id": event_id,
            "commence_time": "2026-09-20T23:00:00+00:00", "home": "A", "away": "B",
            "market": market, "outcome": outcome, "point": point,
            "price_decimal": price, "bookmaker": bookmaker}


def _odds(*filas: dict) -> pd.DataFrame:
    return pd.DataFrame(list(filas))


# --- 1. Contrato basico -------------------------------------------------------

def test_sin_snapshots_no_hay_movimiento():
    assert event_line_movement(pd.DataFrame(), "e1", "h2h", "A", None) is None


def test_un_solo_snapshot_no_es_movimiento():
    df = _odds(_fila("2026-09-05T11:00:00+00:00", 2.00))
    assert event_line_movement(df, "e1", "h2h", "A", None) is None


def test_un_evento_ajeno_no_contamina():
    df = _odds(_fila("2026-09-05T11:00:00+00:00", 2.00, event_id="otro"),
               _fila("2026-09-06T11:00:00+00:00", 1.80, event_id="otro"))
    assert event_line_movement(df, "e1", "h2h", "A", None) is None


def test_el_mercado_se_mueve_a_favor_del_pick():
    """El precio BAJA -> la probabilidad implicita SUBE -> movimiento positivo."""
    df = _odds(_fila("2026-09-05T11:00:00+00:00", 2.00),
               _fila("2026-09-06T11:00:00+00:00", 1.60))
    lm = event_line_movement(df, "e1", "h2h", "A", None)
    assert lm is not None
    # 1/1.60 - 1/2.00 = 0.625 - 0.500 = +12.5 pp en 24 h
    assert lm.movement_pp == pytest.approx(12.5)
    assert lm.lookback_h == pytest.approx(24.0)
    assert lm.velocity_pp_per_h == pytest.approx(12.5 / 24.0)
    assert lm.n_snapshots == 2


def test_el_mercado_se_mueve_en_contra_del_pick():
    df = _odds(_fila("2026-09-05T11:00:00+00:00", 1.60),
               _fila("2026-09-06T11:00:00+00:00", 2.00))
    lm = event_line_movement(df, "e1", "h2h", "A", None)
    assert lm is not None and lm.movement_pp == pytest.approx(-12.5)
    assert lm.velocity_pp_per_h < 0


def test_el_consenso_de_cada_extremo_es_la_mediana_entre_casas():
    df = _odds(_fila("2026-09-05T11:00:00+00:00", 1.90, bookmaker="bk1"),
               _fila("2026-09-05T11:00:00+00:00", 2.10, bookmaker="bk2"),
               _fila("2026-09-06T11:00:00+00:00", 1.90, bookmaker="bk1"),
               _fila("2026-09-06T11:00:00+00:00", 1.90, bookmaker="bk2"))
    lm = event_line_movement(df, "e1", "h2h", "A", None)
    assert lm is not None
    # extremos: mediana 2.00 -> mediana 1.90
    assert lm.movement_pp == pytest.approx((1 / 1.90 - 1 / 2.00) * 100.0)


# --- 2. AUD-LOW-005: el parseo no puede reventar ------------------------------

def test_un_captured_at_ilegible_se_descarta_sin_reventar():
    df = _odds(_fila("no-es-una-fecha", 2.00),
               _fila("2026-09-05T11:00:00+00:00", 2.00),
               _fila("2026-09-06T11:00:00+00:00", 1.60))
    lm = event_line_movement(df, "e1", "h2h", "A", None)
    assert lm is not None and lm.n_snapshots == 2


def test_mezcla_de_sufijos_Z_y_offset_no_revienta():
    """`roi_engine` documenta que `captured_at` mezcla `Z` y `+00:00` entre
    ficheros: el store en vivo escribe offset y el backfill escribe `Z`."""
    df = _odds(_fila("2026-09-05T11:00:00Z", 2.00),
               _fila("2026-09-06T11:00:00+00:00", 1.60))
    lm = event_line_movement(df, "e1", "h2h", "A", None)
    assert lm is not None and lm.movement_pp == pytest.approx(12.5)


def test_una_marca_naive_junto_a_una_con_zona_no_pierde_el_snapshot():
    """EL CASO DE AUD-LOW-005, y el unico que la version anterior fallaba.

    Sin `format="ISO8601"`, pandas infiere UN formato para toda la serie y manda
    a `NaT` la variante ISO que no encaja. Con `errors="coerce"` eso no lanzaba
    nada: el snapshot desaparecia EN SILENCIO. Medido sobre este mismo fixture
    con la implementacion anterior -- se quedaba con 1 snapshot de 2, caia en
    `len(stamps) < 2` y devolvia `None`, es decir "no hay movimiento", en vez de
    los +12,5 pp que si habia.

    El sintoma era ausencia de dato, no una excepcion, que es justo la forma
    dificil de notar: `daily` pasa `movement_pp`/`velocity` a `adjusted_edge`, y
    un `None` desactiva la penalizacion por movimiento adverso de ese evento sin
    dejar rastro.

    Latente con los escritores de hoy -- `odds_store` y el backfill sellan
    siempre con zona --, asi que esto es un candado y no una reparacion. Por eso
    la asercion es sobre el snapshot conservado y el movimiento MEDIDO, no sobre
    "no levanta": no levantaba antes tampoco.
    """
    df = _odds(_fila("2026-09-05T11:00:00Z", 2.00),
               _fila("2026-09-06T11:00:00", 1.60))
    lm = event_line_movement(df, "e1", "h2h", "A", None)
    assert lm is not None, (
        "se perdio el snapshot naive: es exactamente AUD-LOW-005")
    assert lm.n_snapshots == 2
    assert lm.movement_pp == pytest.approx(12.5)


def test_el_helper_usa_el_parser_canonico_del_proyecto():
    """Fija la CLASE, no el sintoma: si alguien vuelve a `pd.to_datetime` a pelo
    en este modulo, esto queda en rojo. `labels.instantes_utc` existe justo para
    que el parseo de instantes viva en un solo sitio."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1]
           / "src" / "sqp" / "markets" / "line_movement.py").read_text(encoding="utf-8")
    ejecutable = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
    assert any("instantes_utc(" in ln for ln in ejecutable), (
        "line_movement dejo de usar el parser canonico")
    assert not any("pd.to_datetime" in ln for ln in ejecutable), (
        "vuelve a haber un `pd.to_datetime` a pelo en line_movement: es "
        "AUD-LOW-005 otra vez")


# --- 3. load_league_odds ------------------------------------------------------

def test_sin_ficheros_devuelve_un_frame_vacio(tmp_path):
    assert load_league_odds("mlb", tmp_path).empty


def test_concatena_todos_los_meses_de_la_liga_y_solo_esa(tmp_path):
    _odds(_fila("2026-08-05T11:00:00+00:00", 2.00)).to_csv(
        tmp_path / "odds_mlb_202608.csv", index=False)
    _odds(_fila("2026-09-05T11:00:00+00:00", 1.90)).to_csv(
        tmp_path / "odds_mlb_202609.csv", index=False)
    _odds(_fila("2026-09-05T11:00:00+00:00", 3.00)).to_csv(
        tmp_path / "odds_nba_202609.csv", index=False)
    df = load_league_odds("mlb", tmp_path)
    assert len(df) == 2
    assert sorted(df["price_decimal"]) == [1.90, 2.00]
