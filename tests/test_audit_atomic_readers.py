"""AUD-006: native Windows readers may temporarily deny replacement."""
import os
import time

import pandas as pd
import pytest

from sqp.storage import atomic


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing semantics")
@pytest.mark.parametrize("kind", ["csv", "json"])
@pytest.mark.parametrize("transient", [False, True])
def test_reader_contention_preserves_atomicity(tmp_path, monkeypatch, kind, transient):
    path = tmp_path / f"published.{kind}"
    path.write_text("old", encoding="utf-8")
    reader = path.open()
    conflicts = []
    original_replace = atomic.os.replace

    def replace_with_reader_release(source, destination):
        try:
            return original_replace(source, destination)
        except PermissionError:
            conflicts.append(True)
            if transient:
                # Release only AFTER observing a real sharing failure. A
                # wall-clock timer could close before a slow writer reaches
                # replace, letting the unfixed implementation pass.
                reader.close()
            raise

    monkeypatch.setattr(atomic.os, "replace", replace_with_reader_release)
    try:
        def publish():
            if kind == "csv":
                atomic.atomic_write_csv(pd.DataFrame([dict(value="new")]), path)
            else:
                atomic.atomic_write_json({"value": "new"}, path)
        if transient:
            publish()
            assert "new" in path.read_text()
            assert len(conflicts) == 1
        else:
            started = time.monotonic()
            with pytest.raises(PermissionError):
                publish()
            transcurrido = time.monotonic() - started
            assert path.read_text() == "old"
            # La propiedad que importa es que `_replace` NO reintente
            # indefinidamente: se acota contra SU plazo, no contra un numero de
            # reloj de pared elegido a ojo. El limite anterior eran 4 s fijos
            # -- 2x el plazo -- y medido desde antes de `publish()`, asi que
            # incluia la serializacion y los fixtures: bajo carga la suite se
            # ponia en rojo sin que hubiera cambiado nada (fallo observado a
            # 4,485 s en la auditoria integral 2026-09-22, AUD-004; la misma
            # prueba pasaba 5/5 aislada). Ahora solo se mide la llamada, y el
            # margen es explicito y proporcional al plazo que se comprueba.
            assert transcurrido < 3 * atomic.REPLACE_RETRY_SECONDS, (
                f"_replace tardo {transcurrido:.2f}s con un plazo de "
                f"{atomic.REPLACE_RETRY_SECONDS}s: esta reintentando de mas")
    finally:
        reader.close()
    assert not list(tmp_path.glob("*.tmp"))


def test_nonsharing_errors_are_not_retried(tmp_path, monkeypatch):
    calls = []

    def fail(*args):
        calls.append(args)
        raise PermissionError("ordinary access denial")

    monkeypatch.setattr(atomic.os, "replace", fail)
    with pytest.raises(PermissionError, match="ordinary"):
        atomic.atomic_write_json({}, tmp_path / "a.json")
    assert len(calls) == 1
    assert not list(tmp_path.glob("*.tmp"))
