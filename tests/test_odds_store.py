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
