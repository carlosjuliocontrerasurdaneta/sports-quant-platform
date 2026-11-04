"""AUD-018: el lock lleva identidad del dueno; no se borra el lock de otro."""
from __future__ import annotations

import os

import pytest

from sqp.exceptions import LockNoAdquiridoError
from sqp.storage import lock as lock_mod
from sqp.storage.lock import locked


def test_el_lock_lleva_pid_y_uuid(tmp_path):
    target = tmp_path / "f.csv"
    with locked(target):
        txt = (tmp_path / "f.csv.lock").read_text(encoding="utf-8")
        assert txt.startswith(f"{os.getpid()}:") and len(txt) > len(f"{os.getpid()}:")
    assert not (tmp_path / "f.csv.lock").exists()


def test_finally_no_borra_el_lock_de_otro_dueno(tmp_path):
    """Nuestro lock caduco, otro proceso lo rompio y creo el suyo: al salir NO
    se debe borrar el ajeno."""
    target = tmp_path / "f.csv"
    lock = tmp_path / "f.csv.lock"
    with locked(target):
        # (sobrescribir, no borrar: en Windows el titular tiene el fd abierto)
        lock.write_text("99999:otro-dueno", encoding="utf-8")
    assert lock.exists()
    assert lock.read_text(encoding="utf-8") == "99999:otro-dueno"


def test_romper_caducado_no_borra_un_lock_que_cambio_de_dueno(tmp_path, monkeypatch):
    """Entre el `stat` y el `unlink` otro proceso rompe el lock viejo y toma el
    suyo (fresco): el lock nuevo no se borra y se agota la espera."""
    target = tmp_path / "f.csv"
    lock = tmp_path / "f.csv.lock"
    lock.write_text("1:viejo", encoding="utf-8")
    old = os.stat(lock).st_mtime - 1000
    os.utime(lock, (old, old))

    real_read = lock_mod._read_token
    calls = {"n": 0}

    def lectura_con_carrera(p):
        calls["n"] += 1
        valor = real_read(p)
        if calls["n"] == 1:           # tras la 1.a lectura, otro dueno toma el lock
            p.write_text("2:nuevo", encoding="utf-8")
        return valor

    monkeypatch.setattr(lock_mod, "_read_token", lectura_con_carrera)
    with pytest.raises(LockNoAdquiridoError):
        with locked(target, timeout_s=0.5, stale_s=300.0):
            pass
    assert lock.read_text(encoding="utf-8") == "2:nuevo"
