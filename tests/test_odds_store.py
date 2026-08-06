"""Odds snapshot store: append, schema, accumulation across runs, lock."""

import os
import time

import pandas as pd
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.storage.odds_store import COLUMNS, OddsStore, _locked


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


def test_locked_creates_and_removes_sidecar(tmp_path):
    target = tmp_path / "odds_x_202607.csv"
    lock = target.with_suffix(target.suffix + ".lock")
    with _locked(target):
        assert lock.exists()
    assert not lock.exists()


def test_locked_breaks_stale_lock_from_dead_process(tmp_path):
    target = tmp_path / "odds_x_202607.csv"
    lock = target.with_suffix(target.suffix + ".lock")
    lock.write_text("")
    old = time.time() - 3600
    os.utime(lock, (old, old))  # lock huerfano de un proceso muerto
    with _locked(target, timeout_s=5.0, stale_s=300.0):
        assert lock.exists()  # lo rompio y lo re-adquirio
    assert not lock.exists()


def test_locked_times_out_and_degrades_without_removing_foreign_lock(tmp_path):
    target = tmp_path / "odds_x_202607.csv"
    lock = target.with_suffix(target.suffix + ".lock")
    lock.write_text("")  # lock vivo de OTRO proceso (mtime fresco)
    t0 = time.monotonic()
    with _locked(target, timeout_s=0.4, stale_s=300.0):
        pass  # degrada: procede sin lock tras el timeout
    assert time.monotonic() - t0 >= 0.4
    assert lock.exists()  # el lock ajeno NO se borra al salir


def test_concurrent_appends_do_not_interleave_rows(tmp_path):
    """Con el lock, dos appends secuenciales (mismo archivo) quedan integros;
    smoke de la invariante que el lock protege entre procesos."""
    store = OddsStore(tmp_path)
    captured = "2026-06-13T01:00:00+00:00"
    assert store.append_snapshot("wnba", _events(), captured_at=captured) == 3
    assert store.append_snapshot("wnba", _events(), captured_at=captured) == 3
    df = pd.read_csv(store.path("wnba", "202606"))
    assert len(df) == 6 and list(df.columns) == COLUMNS
    assert not store.path("wnba", "202606").with_suffix(".csv.lock").exists()


def test_locked_honours_timeout_when_stat_fails_persistently(tmp_path, monkeypatch):
    """Un fallo PERSISTENTE de stat() no puede colgar el run diario.

    La rama `except OSError` hacia `continue`, saltandose tanto la comprobacion
    de deadline como el sleep: el bucle giraba sin salida al 100% de CPU y
    `timeout_s` no rescataba. Reproducido en la verificacion independiente (el
    proceso hijo seguia vivo diez veces pasado su timeout) antes de corregirlo
    (auditoria 2026-08-05, F-08)."""
    import time as _time
    from pathlib import Path as _Path

    target = tmp_path / "odds_x_202607.csv"
    lock = target.with_suffix(target.suffix + ".lock")
    lock.write_text("")                      # ocupado por "otro proceso"
    real_stat = _Path.stat

    def _boom(self, *a, **kw):
        if self == lock:
            raise OSError("stat falla de forma persistente (permisos/disco/red)")
        return real_stat(self, *a, **kw)

    monkeypatch.setattr(_Path, "stat", _boom)
    t0 = _time.monotonic()
    with _locked(target, timeout_s=0.2, stale_s=300.0):
        pass
    # Degrada (sin lock) pero RETORNA. Antes no llegaba nunca a esta linea.
    assert _time.monotonic() - t0 < 10.0
