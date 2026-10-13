"""Columna `market_shrink` del stream servido (2026-10-13).

La probabilidad servida es ``(1-s)*cal(p_adj) + s*fair``. Los pre-registros que
reconstruyen ``p_cal`` asumian s = 0,5; si ``s`` cambia (p. ej. ``MARKET_SHRINK``
en un `.env` no versionado) la reconstruccion queda ciega salvo que la fila
lleve el ``s`` con el que se calculo."""
import pandas as pd
import pytest

from sqp.storage.served_store import COLUMNS, ServedStore
from test_served_store import NOW, _row


def test_market_shrink_es_la_ultima_columna():
    assert COLUMNS[-1] == "market_shrink"
    assert COLUMNS.count("market_shrink") == 1


def test_la_fila_nueva_lleva_el_valor(tmp_path):
    store = ServedStore(tmp_path)
    store.append_served("wnba", [_row(market_shrink=0.35)])
    df = pd.read_csv(store.served_path("wnba"))
    assert list(df.columns) == COLUMNS
    assert df.loc[0, "market_shrink"] == pytest.approx(0.35)


def test_cabecera_antigua_migra_sin_perdida_ni_reordenacion(tmp_path):
    store = ServedStore(tmp_path)
    store.dir.mkdir(parents=True)
    old_cols = [c for c in COLUMNS if c != "market_shrink"]
    olds = [{k: v for k, v in _row(event_id=f"old{i}").items() if k in old_cols}
            for i in range(3)]
    pd.DataFrame(olds).reindex(columns=old_cols).to_csv(store.served_path("wnba"), index=False)
    antes = pd.read_csv(store.served_path("wnba"))

    assert store.append_served("wnba", [_row(event_id="new", market_shrink=0.5)]) == 1
    df = pd.read_csv(store.served_path("wnba"))
    assert list(df.columns) == COLUMNS               # market_shrink al final
    assert list(df["event_id"]) == ["old0", "old1", "old2", "new"]  # mismo orden
    # Las filas historicas conservan TODOS sus valores y quedan con shrink vacio.
    pd.testing.assert_frame_equal(df.iloc[:3][old_cols].reset_index(drop=True),
                                  antes[old_cols], check_dtype=False)
    assert df.iloc[:3]["market_shrink"].isna().all()
    assert df.loc[3, "market_shrink"] == pytest.approx(0.5)


def test_propagacion_a_graded_y_cabecera_antigua_de_graded(tmp_path):
    store = ServedStore(tmp_path)
    store.append_served("wnba", [_row(event_id="ev1", market_shrink=0.3),
                                 _row(event_id="ev2", market_shrink=0.0)])
    pending = store.pending("wnba", now=NOW)
    graded = pending.assign(result="win", pnl=0.0)
    assert len(store.append_graded("wnba", graded)) == 2
    g = pd.read_csv(store.graded_path("wnba")).set_index("event_id")
    assert g.loc["ev1", "market_shrink"] == pytest.approx(0.3)
    assert g.loc["ev2", "market_shrink"] == pytest.approx(0.0)

    # Un graded con cabecera antigua (sin la columna) se une por columnas y las
    # filas historicas quedan en NaN; las nuevas llevan su valor.
    store2 = ServedStore(tmp_path / "otro")
    store2.dir.mkdir(parents=True)
    viejo = pd.DataFrame([{**_row(event_id="h1"), "result": "loss", "pnl": 0.0}])
    viejo.to_csv(store2.graded_path("wnba"), index=False)
    nuevo = pd.DataFrame([{**_row(event_id="h2", market_shrink=0.4),
                           "result": "win", "pnl": 0.0}])
    assert len(store2.append_graded("wnba", nuevo)) == 1
    g2 = pd.read_csv(store2.graded_path("wnba")).set_index("event_id")
    assert list(g2.index) == ["h1", "h2"]
    assert pd.isna(g2.loc["h1", "market_shrink"])
    assert g2.loc["h2", "market_shrink"] == pytest.approx(0.4)


def test_daily_registra_el_shrink_efectivo(tmp_path, monkeypatch):
    """Con MARKET_SHRINK=0.3 las filas con no-vig llevan 0.3 (no el 0.5 del
    yaml/default); las que no se mezclaron (sin no-vig) llevan 0.0."""
    from test_line_shopping import _run_live
    monkeypatch.setenv("MARKET_SHRINK", "0.3")
    df = _run_live(tmp_path, monkeypatch, books=())
    assert "market_shrink" in df.columns
    assert df["market_shrink"].notna().all()
    con_fair = df["implied_probability_novig"].notna()
    assert con_fair.any()
    assert df.loc[con_fair, "market_shrink"].to_numpy() == pytest.approx(0.3)
    assert (df.loc[~con_fair, "market_shrink"] == 0.0).all()


def test_daily_con_shrink_cero_registra_cero(tmp_path, monkeypatch):
    """Con MARKET_SHRINK=0 no hay mezcla: toda fila lleva 0.0 (revision Fable,
    2026-10-13: el test anterior no ejercita la rama sin no-vig, este si la
    condicion `shrink > 0`)."""
    from test_line_shopping import _run_live
    monkeypatch.setenv("MARKET_SHRINK", "0")
    df = _run_live(tmp_path, monkeypatch, books=())
    assert len(df) > 0
    assert (df["market_shrink"] == 0.0).all()
