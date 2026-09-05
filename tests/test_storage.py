"""Tests para storage/atomic.py y storage/lock.py.

Auditoría 2026-08-19 (T4): primitivas de integridad y concurrencia usadas
por daily.py::_finalize sin cobertura directa.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import pytest

from sqp.storage.atomic import atomic_write_csv
from sqp.exceptions import LockNoAdquiridoError
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


class TestElTimeoutNoEntraSinLock:
    """AUD-002 (Codex, 2026-09-05). CONTRATO INVERTIDO.

    Sustituye a `test_lock_timeout_degrades_with_warning`, que fijaba lo
    contrario: entrar sin exclusion y avisar. El razonamiento era "bloquear el
    pipeline diario seria peor que el riesgo de intercalado", y tenia un
    agujero: la degradacion se activa justo cuando HAY contencion -- es decir,
    cuando el intercalado no es un riesgo teorico sino el escenario en curso.
    Y el modo de fallo no era un error visible, era una escritura perdida.
    """

    def test_agotar_la_espera_lanza_en_vez_de_entrar(self, tmp_path):
        target = tmp_path / "resource.csv"
        target.with_suffix(target.suffix + ".lock").write_text("")  # nunca se libera
        entro = False
        with pytest.raises(LockNoAdquiridoError):
            with locked(target, timeout_s=0.2, stale_s=9999):
                entro = True
        assert not entro, "no se debe ejecutar el cuerpo de la seccion critica"

    def test_una_actualizacion_concurrente_ya_no_se_pierde(self, tmp_path):
        """La reproduccion del hallazgo, como regresion.

        Antes: A lee "old"; B entra degradado y escribe "new"; A persiste su
        copia y "new" desaparece. Ahora B no puede entrar, asi que no hay
        escritura que perder -- y quien no obtiene exclusion se entera."""
        csv = tmp_path / "candidates.csv"
        atomic_write_csv(pd.DataFrame([{"pick": "old"}]), csv)
        with locked(csv):
            leido_por_A = pd.read_csv(csv)
            with pytest.raises(LockNoAdquiridoError):
                with locked(csv, timeout_s=0):
                    atomic_write_csv(pd.DataFrame([{"pick": "new"}]), csv)
            atomic_write_csv(leido_por_A, csv)
        assert pd.read_csv(csv)["pick"].tolist() == ["old"]

    def test_el_lock_huerfano_sigue_rescatando_sin_lanzar(self, tmp_path):
        """Discriminacion, y la razon de que fallar sea aceptable: un proceso
        MUERTO no bloquea a nadie, su lock se rompe por antiguedad. La excepcion
        significa que otro proceso VIVO lo retiene."""
        import os
        import time
        target = tmp_path / "resource.csv"
        lock = target.with_suffix(target.suffix + ".lock")
        lock.write_text("")
        viejo_t = time.time() - 400
        os.utime(lock, (viejo_t, viejo_t))
        with locked(target, timeout_s=0.2, stale_s=300):
            pass   # adquiere rompiendo el huerfano, sin excepcion

    def test_el_timeout_por_defecto_supera_la_seccion_critica_mas_lenta(self):
        """`revalidate_pitchers` retiene el lock durante `fetch_probables` (MLB
        Stats API, llamadas de hasta 60 s). Con el timeout en 30 s -- el valor
        de cuando se degradaba -- dejar de degradar habria convertido en fallo
        duro lo que antes era una escritura perdida. Y debe seguir MUY por
        debajo de `LOCK_STALE_S`, que es quien rescata de un huerfano."""
        from sqp.storage.lock import LOCK_STALE_S, LOCK_TIMEOUT_S
        assert LOCK_TIMEOUT_S >= 120.0
        assert LOCK_TIMEOUT_S < LOCK_STALE_S


def test_el_temporal_atomico_es_unico_por_proceso(tmp_path, monkeypatch):
    """Con el nombre fijo `.csv.tmp`, dos escritores sobre el mismo destino
    compartian temporal: uno podia renombrar el fichero a medio escribir del
    otro, y `os.replace` daba atomicidad sobre datos ya corruptos. El lock lo
    hace improbable, no imposible -- hay escritores que no pasan por `locked`."""
    vistos = []
    real = pd.DataFrame.to_csv

    def espia(self, path_or_buf=None, *a, **kw):
        if path_or_buf is not None:
            vistos.append(Path(path_or_buf).name)
        return real(self, path_or_buf, *a, **kw)

    monkeypatch.setattr(pd.DataFrame, "to_csv", espia)
    destino = tmp_path / "x.csv"
    atomic_write_csv(pd.DataFrame([{"a": 1}]), destino)
    atomic_write_csv(pd.DataFrame([{"a": 2}]), destino)
    assert len(vistos) == 2 and vistos[0] != vistos[1], (
        f"los dos temporales deben diferir: {vistos}")
    assert all(n.endswith(".tmp") for n in vistos)


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
