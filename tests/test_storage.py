"""Tests para storage/atomic.py y storage/lock.py.

Auditoría 2026-08-19 (T4): primitivas de integridad y concurrencia usadas
por daily.py::_finalize sin cobertura directa.
"""
from __future__ import annotations

import os
import time

import pandas as pd

from sqp.storage.atomic import atomic_write_csv
from sqp.storage.lock import locked


# --- atomic_write_csv ---------------------------------------------------------

def test_atomic_write_creates_file(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    out = tmp_path / "data.csv"
    atomic_write_csv(df, out)
    assert out.exists()


def test_atomic_write_roundtrip(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    out = tmp_path / "data.csv"
    atomic_write_csv(df, out)
    loaded = pd.read_csv(out)
    assert list(loaded.columns) == ["a", "b"]
    assert len(loaded) == 2


def test_atomic_write_leaves_no_tmp_file(tmp_path):
    out = tmp_path / "data.csv"
    atomic_write_csv(pd.DataFrame({"x": [1]}), out)
    assert not (tmp_path / "data.csv.tmp").exists()


def test_atomic_write_replaces_existing(tmp_path):
    out = tmp_path / "data.csv"
    atomic_write_csv(pd.DataFrame({"a": [1]}), out)
    atomic_write_csv(pd.DataFrame({"a": [2, 3]}), out)
    loaded = pd.read_csv(out)
    assert loaded["a"].tolist() == [2, 3]


# --- locked -------------------------------------------------------------------

def test_lock_file_exists_while_held(tmp_path):
    target = tmp_path / "resource.csv"
    lock = target.with_suffix(target.suffix + ".lock")
    with locked(target):
        assert lock.exists()


def test_lock_file_removed_after_release(tmp_path):
    target = tmp_path / "resource.csv"
    lock = target.with_suffix(target.suffix + ".lock")
    with locked(target):
        pass
    assert not lock.exists()


def test_lock_stale_is_cleared(tmp_path):
    target = tmp_path / "resource.csv"
    lock = target.with_suffix(target.suffix + ".lock")
    lock.write_text("")
    old_time = time.time() - 400  # más viejo que stale_s=300
    os.utime(lock, (old_time, old_time))
    # Debe adquirir limpiando el lock huérfano sin bloquear
    with locked(target, stale_s=300):
        pass


def test_lock_timeout_degrades_with_warning(tmp_path, caplog):
    import logging
    target = tmp_path / "resource.csv"
    lock = target.with_suffix(target.suffix + ".lock")
    lock.write_text("")  # lock que nunca se libera
    with caplog.at_level(logging.WARNING, logger="sqp.storage.lock"):
        with locked(target, timeout_s=0.35, stale_s=9999):
            pass  # degrada en vez de bloquear
    assert any("degraded" in r.getMessage()
               for r in caplog.records if r.name == "sqp.storage.lock")


def test_atomic_write_csv_fsyncs_before_replace(tmp_path, monkeypatch):
    """COR-07 (auditoria 2026-08-05, cerrado 2026-08-25).

    `os.replace` da atomicidad, no durabilidad: sin fsync el rename puede
    aplicarse mientras el contenido sigue en cache del SO. Se afirma el ORDEN
    (fsync antes que replace), que es lo que hace la escritura recuperable.
    """
    import os as os_mod

    from sqp.storage.atomic import atomic_write_csv

    calls: list[str] = []
    real_fsync, real_replace = os_mod.fsync, os_mod.replace
    monkeypatch.setattr(os_mod, "fsync",
                        lambda fd: (calls.append("fsync"), real_fsync(fd))[1])
    monkeypatch.setattr(os_mod, "replace",
                        lambda a, b: (calls.append("replace"), real_replace(a, b))[1])

    out = tmp_path / "x.csv"
    atomic_write_csv(pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}), out)

    assert calls == ["fsync", "replace"]
    assert pd.read_csv(out)["a"].tolist() == [1, 2]
    assert not (tmp_path / "x.csv.tmp").exists()
