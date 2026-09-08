"""Served-probability stream: store dedup/pending/grading, training loaders,
and the settlement hook that grades the stream without candidates."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from sqp.storage.served_store import COLUMNS, ServedStore

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _row(event_id="ev1", market="h2h", selection="Team A", line=None,
         start_time="2026-07-06T23:00:00Z", generated_at="2026-07-06T15:00:00+00:00",
         **extra):
    base = {"league": "wnba", "event_id": event_id, "home": "Team A", "away": "Team B",
            "start_time": start_time, "game_date": start_time[:10],
            "market": market, "selection": selection, "line": line,
            "price_decimal": 1.9, "bookmaker": "consensus_median",
            "model_probability": 0.61, "estimated_probability": 0.58,
            "calibrated_probability": 0.58, "implied_probability_novig": 0.52,
            "estimated_edge": 0.06, "books_count": 3, "stake": 0.0,
            "data_label": "real", "flags": "served_stream", "generated_at": generated_at}
    base.update(extra)
    return base


def test_append_served_is_idempotent_same_run_day(tmp_path):
    store = ServedStore(tmp_path)
    assert store.append_served("wnba", [_row()]) == 1
    # Same event/market/selection/line, same run day, later timestamp: skipped.
    assert store.append_served("wnba", [_row(generated_at="2026-07-06T18:30:00+00:00")]) == 0
    df = pd.read_csv(store.served_path("wnba"))
    assert len(df) == 1
    assert list(df.columns) == COLUMNS


def test_append_served_next_day_serve_persists_again(tmp_path):
    store = ServedStore(tmp_path)
    store.append_served("wnba", [_row()])
    n = store.append_served("wnba", [_row(generated_at="2026-07-07T15:00:00+00:00")])
    assert n == 1  # a genuine next-day serve of the same event is new evidence
    assert len(pd.read_csv(store.served_path("wnba"))) == 2


def test_h2h_none_line_survives_csv_nan_roundtrip(tmp_path):
    # h2h rows have line=None; after CSV write it reads back as NaN. The dedup
    # key must treat both as the same line.
    store = ServedStore(tmp_path)
    store.append_served("wnba", [_row(line=None)])
    assert store.append_served("wnba", [_row(line=None)]) == 0
    assert store.append_served("wnba", [_row(line=float("nan"))]) == 0


def test_pending_only_commenced_recent_ungraded(tmp_path):
    store = ServedStore(tmp_path)
    store.append_served("wnba", [
        _row(event_id="commenced", start_time="2026-07-06T23:00:00Z"),
        _row(event_id="future", start_time="2026-07-08T23:00:00Z"),
        _row(event_id="stale", start_time="2026-06-01T23:00:00Z",
             generated_at="2026-06-01T15:00:00+00:00"),
    ])
    pending = store.pending("wnba", max_age_days=7, now=NOW)
    assert list(pending["event_id"]) == ["commenced"]  # future + stale excluded


def test_grading_is_idempotent_and_pending_shrinks(tmp_path):
    store = ServedStore(tmp_path)
    store.append_served("wnba", [_row(event_id="ev1"), _row(event_id="ev2")])
    pending = store.pending("wnba", now=NOW)
    graded = pending[pending["event_id"] == "ev1"].assign(result="win", pnl=0.0)
    assert len(store.append_graded("wnba", graded)) == 1
    # Re-grading the same served row is a no-op (append-only, never twice).
    assert store.append_graded("wnba", graded).empty
    assert list(store.pending("wnba", now=NOW)["event_id"]) == ["ev2"]


def test_demo_rows_are_isolated_from_real_store(tmp_path):
    ServedStore(tmp_path, demo=True).append_served("wnba", [_row(data_label="demo_synthetic")])
    real = ServedStore(tmp_path)
    assert not real.served_path("wnba").exists()
    assert real.leagues() == []
    demo_path = tmp_path / "data" / "calibration" / "demo" / "served_wnba.csv"
    assert demo_path.exists()


def test_schema_drift_reconciled_by_column_union(tmp_path):
    # A served file written by an older schema (missing new columns) must be
    # rewritten aligned, not appended blind (KI-011 failure mode).
    store = ServedStore(tmp_path)
    store.dir.mkdir(parents=True)
    old_cols = [c for c in COLUMNS if c != "books_count"]
    old = {k: v for k, v in _row(event_id="old").items() if k in old_cols}
    pd.DataFrame([old]).to_csv(store.served_path("wnba"), index=False)

    assert store.append_served("wnba", [_row(event_id="new")]) == 1
    df = pd.read_csv(store.served_path("wnba"))
    assert len(df) == 2
    assert "books_count" in df.columns
    # The old row's values stay under their own headers (no misalignment).
    old_row = df[df["event_id"] == "old"].iloc[0]
    assert old_row["market"] == "h2h" and old_row["data_label"] == "real"


def test_leagues_lists_served_files(tmp_path):
    store = ServedStore(tmp_path)
    store.append_served("wnba", [_row()])
    store.append_served("mlb", [_row(league="mlb")])
    assert store.leagues() == ["mlb", "wnba"]


# ---------------------------------------------------------------------------
# Training loaders (sqp.calibration.data) over the graded stream
# ---------------------------------------------------------------------------

def test_served_training_history_projects_graded_stream(tmp_path):
    from sqp.calibration.data import TRAINING_COLS, load_served_training_history
    cal_dir = tmp_path / "data" / "calibration"
    cal_dir.mkdir(parents=True)
    pd.DataFrame([
        {**_row(event_id="g1"), "result": "win", "pnl": 0.0},
        {**_row(event_id="g2", data_label="demo_synthetic"), "result": "loss", "pnl": 0.0},
    ]).to_csv(cal_dir / "graded_wnba.csv", index=False)

    out = load_served_training_history(cal_dir)
    assert list(out.columns) == TRAINING_COLS
    assert len(out) == 1  # the non-'real' row is filtered defensively
    assert out.loc[0, "market"] == "h2h"
    assert out.loc[0, "model_probability"] == pytest.approx(0.61)


def test_combined_history_dedups_pick_against_served(tmp_path):
    # A placed pick exists in BOTH settled_* and the graded stream (capture
    # happens before the stake filter): the union must count it once.
    from sqp.calibration.data import load_calibration_training_history
    bets = tmp_path / "data" / "bets"
    cal = tmp_path / "data" / "calibration"
    bets.mkdir(parents=True); cal.mkdir(parents=True)
    shared = dict(event_id="ev1", market="h2h", selection="Team A", line=None,
                  generated_at="2026-07-06T15:00:00+00:00")
    pd.DataFrame([{**_row(**shared), "stake": 10.0, "result": "win", "pnl": 9.0}]) \
        .to_csv(bets / "settled_wnba.csv", index=False)
    pd.DataFrame([
        {**_row(**shared), "result": "win", "pnl": 0.0},              # duplicate of the pick
        {**_row(event_id="ev2"), "result": "loss", "pnl": 0.0},       # served-only row
    ]).to_csv(cal / "graded_wnba.csv", index=False)

    out = load_calibration_training_history(bets, cal)
    assert len(out) == 2  # ev1 once + ev2, not 3


# ---------------------------------------------------------------------------
# Settlement hook: the stream grades even with no candidates that day
# ---------------------------------------------------------------------------

class _FakeScoresClient:
    def __init__(self, raw): self.raw = raw
    def fetch_scores(self, sport_key, days_from=2): return self.raw


def test_fetch_and_settle_grades_served_without_candidates(tmp_path, monkeypatch):
    import sqp.settlement.runner as runner
    from sqp.config import Settings

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    store = ServedStore(tmp_path)
    store.append_served("wnba", [_row(event_id="ev1", selection="Team A")])

    raw = [{"id": "ev1", "completed": True, "home_team": "Team A", "away_team": "Team B",
            "commence_time": "2026-07-06T23:00:00Z",
            "scores": [{"name": "Team A", "score": "80"}, {"name": "Team B", "score": "70"}]}]
    fixed_now = NOW

    class _Now(datetime):
        @classmethod
        def now(cls, tz=None): return fixed_now

    monkeypatch.setattr("sqp.storage.served_store.datetime", _Now)
    settled = runner.fetch_and_settle("wnba", Settings.load(),
                                      client=_FakeScoresClient(raw))
    assert settled.empty  # no candidates file: no real picks settled
    graded = pd.read_csv(store.graded_path("wnba"))
    assert len(graded) == 1
    assert graded.loc[0, "result"] == "win"  # home moneyline, home won
    assert graded.loc[0, "pnl"] == 0.0       # stake-0 calibration row
    assert store.pending("wnba", now=fixed_now).empty


def test_corrupt_served_csv_is_quarantined_not_read_as_empty_forever(tmp_path):
    """A corrupt CSV used to be swallowed as empty on every read: dedup went off,
    `append_served` kept writing behind the bad line (the header is intact, so it
    takes the cheap-append branch), and `pending()` returned empty forever, so the
    league silently stopped grading (N-A-2). Quarantine bounds the damage."""
    store = ServedStore(tmp_path)
    assert store.append_served("wnba", [_row(event_id="ev1")]) == 1
    p = store.served_path("wnba")
    with p.open("a", encoding="utf-8") as f:
        f.write("a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v,w,x,y,z\n")

    # First read trips the parser, quarantines and starts clean.
    assert store._load(p).empty
    assert not p.exists()
    quarantined = list(tmp_path.glob("**/served_wnba.csv.corrupt.*"))
    assert len(quarantined) == 1

    # The store is usable again: a new append rebuilds a valid, readable file.
    assert store.append_served("wnba", [_row(event_id="ev2")]) == 1
    reread = store._load(store.served_path("wnba"))
    assert list(reread["event_id"]) == ["ev2"]


def test_quarantine_failure_does_not_raise(tmp_path, monkeypatch):
    """Quarantine is a repair path; failing to repair must not take settlement
    down with it."""
    store = ServedStore(tmp_path)
    store.append_served("wnba", [_row()])
    p = store.served_path("wnba")
    with p.open("a", encoding="utf-8") as f:
        f.write("a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v,w,x,y,z\n")

    def _boom(self, target):
        raise OSError("locked by another process")
    monkeypatch.setattr("pathlib.Path.rename", _boom)
    assert store._load(p).empty      # degrades, does not raise
    assert p.exists()                # left in place for manual repair


# --- Exclusion de los escritores (AUD-MED-002, auditoria integral 2026-09-08) --
#
# `append_graded` es un read-modify-write que REEMPLAZA el fichero entero, y
# corria sin lock: la misma carrera que Codex reprodujo en `_persist_settled`
# (AUD-20260906-02) y que alli se corrigio. Se activa al solapar una liquidacion
# manual con la programada.

@pytest.mark.parametrize("metodo", ["append_graded", "append_served"])
def test_la_escritura_ocurre_con_el_lock_del_fichero_TOMADO(tmp_path, monkeypatch,
                                                            metodo):
    """La transaccion entera -- leer, deduplicar, combinar y escribir -- corre
    dentro de la seccion critica.

    Se comprueba en el INSTANTE de la escritura, que es la unica forma de
    distinguir "toma el lock" de "toma el lock demasiado tarde": leer fuera y
    escribir dentro no arregla la carrera, porque el estado puede cambiar entre
    ambos (es la correccion que `revalidation.py` ya habia aplicado y que
    `_persist_settled` repitió).

    Un intercalado real exige un SEGUNDO PROCESO: el lock no es reentrante y
    llamar al store desde dentro de su propia seccion critica aborta con
    `LockNoAdquiridoError` a los 120 s -- comprobado al escribir esta prueba, y
    es el comportamiento correcto.
    """
    import sqp.storage.served_store as ss
    store = ServedStore(tmp_path)
    ruta = (store.graded_path("wnba") if metodo == "append_graded"
            else store.served_path("wnba"))
    visto = {}

    original = ss._atomic_write_csv

    def espiar(df, out):
        visto["lock"] = ruta.with_suffix(ruta.suffix + ".lock").exists()
        original(df, out)

    monkeypatch.setattr(ss, "_atomic_write_csv", espiar)
    if metodo == "append_graded":
        store.append_graded("wnba", pd.DataFrame([_row(event_id="evA")])
                            .reindex(columns=COLUMNS))
    else:
        # La rama de reconciliacion de esquema es la que reemplaza el fichero
        # entero; se fuerza con una cabecera que ya no coincide con COLUMNS.
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("event_id,market\nviejo,h2h\n", encoding="utf-8")
        store.append_served("wnba", [_row(event_id="evA")])
    monkeypatch.undo()
    assert visto.get("lock") is True, (
        f"{metodo} escribio SIN el lock del fichero tomado: vuelve a haber un "
        f"read-modify-write sin exclusion")


def test_append_graded_sigue_siendo_idempotente_bajo_el_lock(tmp_path):
    store = ServedStore(tmp_path)
    fila = pd.DataFrame([_row(event_id="evX")]).reindex(columns=COLUMNS)
    assert len(store.append_graded("wnba", fila)) == 1
    assert len(store.append_graded("wnba", fila)) == 0
    assert len(pd.read_csv(store.graded_path("wnba"))) == 1


def test_append_served_sigue_siendo_idempotente_bajo_el_lock(tmp_path):
    store = ServedStore(tmp_path)
    assert store.append_served("wnba", [_row(event_id="evY")]) == 1
    assert store.append_served("wnba", [_row(event_id="evY")]) == 0
    assert len(pd.read_csv(store.served_path("wnba"))) == 1


def test_el_lock_se_libera_aunque_la_escritura_falle(tmp_path, monkeypatch):
    """Un fallo dentro de la seccion critica no puede dejar el candado puesto:
    el siguiente pase se quedaria esperando hasta agotar el timeout."""
    import sqp.storage.served_store as ss
    store = ServedStore(tmp_path)
    fila = pd.DataFrame([_row(event_id="evZ")]).reindex(columns=COLUMNS)

    def revienta(df, out):
        raise OSError("disco lleno")

    monkeypatch.setattr(ss, "_atomic_write_csv", revienta)
    with pytest.raises(OSError):
        store.append_graded("wnba", fila)
    monkeypatch.undo()
    lock = store.graded_path("wnba")
    assert not lock.with_suffix(lock.suffix + ".lock").exists()
    assert len(store.append_graded("wnba", fila)) == 1
