"""Odds snapshot store: append, schema, accumulation across runs."""
import pandas as pd
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.storage.odds_store import COLUMNS, OddsStore


def _events() -> list[EventOdds]:
    ev = Event(event_id="e1", sport_key="basketball_wnba", league="wnba",
               home="Las Vegas Aces", away="Minnesota Lynx",
               start_time="2026-06-13T02:00:00Z")
    lines = [MarketLine("h2h", "pinnacle", "Las Vegas Aces", 1.87),
             MarketLine("h2h", "pinnacle", "Minnesota Lynx", 1.95),
             MarketLine("totals", "draftkings", "Over", 1.91, point=162.5)]
    return [EventOdds(event=ev, lines=lines)]


def test_append_snapshot_schema_and_accumulation(tmp_path):
    store = OddsStore(tmp_path)
    assert store.append_snapshot("wnba", _events()) == 3
    assert store.append_snapshot("wnba", _events()) == 3  # second run accumulates
    files = list((tmp_path / "data" / "odds").glob("odds_wnba_*.csv"))
    assert len(files) == 1
    df = pd.read_csv(files[0])
    assert list(df.columns) == COLUMNS
    assert len(df) == 6
    assert df["captured_at"].notna().all()
    assert set(df["market"]) == {"h2h", "totals"}


def test_append_snapshot_empty_events(tmp_path):
    store = OddsStore(tmp_path)
    assert store.append_snapshot("ligamx", []) == 0
    assert not (tmp_path / "data" / "odds").exists()


def test_append_realigns_file_with_stale_schema(tmp_path):
    """Un archivo escrito por un esquema viejo (menos columnas) NO debe recibir
    filas del esquema nuevo apendadas a ciegas bajo el header viejo (mismo modo
    de corrupcion que KI-011 en settled_*.csv): el store debe reconciliar por
    union de columnas y reescribir alineado."""
    store = OddsStore(tmp_path)
    captured = "2026-06-13T01:00:00+00:00"
    p = store.path("wnba", captured[:7].replace("-", ""))
    p.parent.mkdir(parents=True, exist_ok=True)
    old_cols = [c for c in COLUMNS if c != "bookmaker"]  # esquema previo sin 'bookmaker'
    p.write_text(",".join(old_cols) + "\n" +
                 f"{captured},e0,2026-06-13T02:00:00Z,Las Vegas Aces,Minnesota Lynx,"
                 "h2h,Las Vegas Aces,,1.80\n", encoding="utf-8")
    assert store.append_snapshot("wnba", _events(), captured_at=captured) == 3
    df = pd.read_csv(p)
    assert set(df.columns) == set(COLUMNS)
    assert len(df) == 4
    # Fila vieja conserva sus valores bajo las columnas correctas.
    old = df[df["event_id"] == "e0"].iloc[0]
    assert old["price_decimal"] == 1.80 and pd.isna(old["bookmaker"])
    # Filas nuevas alineadas: bookmaker cae en su columna, no desplazado.
    assert set(df[df["event_id"] == "e1"]["bookmaker"]) == {"pinnacle", "draftkings"}
