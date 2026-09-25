"""AUD-006: native Windows readers may temporarily deny replacement."""
import os

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
    # Cota de INTENTOS, no de reloj (KI-062): `_replace` duerme >= 0,05 s entre
    # intentos durante REPLACE_RETRY_SECONDS, asi que hace como mucho ~40. La
    # carga solo puede REDUCIR el numero de intentos (cada uno tarda mas), nunca
    # aumentarlo: la cota detecta un reintento sin limite y no depende de la
    # maquina. Pasada la guarda se aborta con AssertionError para que un
    # `_replace` que reintente para siempre falle en vez de colgar la suite.
    max_intentos = int(atomic.REPLACE_RETRY_SECONDS / 0.05) + 5

    def replace_with_reader_release(source, destination):
        if len(conflicts) > 2 * max_intentos:
            raise AssertionError("_replace reintenta sin limite")
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
            with pytest.raises(PermissionError):
                publish()
            assert path.read_text() == "old"
            # La propiedad que importa es que `_replace` NO reintente
            # indefinidamente. Se comprobaba con el reloj de pared -- 4 s fijos
            # (AUD-004, 2026-09-22) y luego 3x el plazo --, y las dos versiones
            # fallaron bajo carga sin que cambiara nada: la ultima el
            # 2026-09-25, con la suite en paralelo a la revision de Codex
            # (KI-062; aislada pasaba 25/25). Contar intentos mide la propiedad
            # sin depender de la velocidad de la maquina.
            assert 1 <= len(conflicts) <= max_intentos, (
                f"_replace hizo {len(conflicts)} intentos con un plazo de "
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
