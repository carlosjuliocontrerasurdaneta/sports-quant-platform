"""Test directo de `atomic_write_bytes` (`sqp.storage.atomic`): escritura
atomica de bytes crudos y ausencia de temporales tras publicar -- mismo
criterio de `atomic_write_csv`/`atomic_write_json`, pedido explicitamente por
la revision independiente de Fable (menor, 2026-09-26) porque hasta ahora
solo se ejercitaba indirectamente via `sqp.storage.goalies.save_raw_boxscore`.
"""
from sqp.storage.atomic import atomic_write_bytes


def test_atomic_write_bytes_escribe_el_contenido_exacto(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    out = sub / "payload.json.gz"
    payload = b"\x1f\x8b\x00contenido binario arbitrario"

    atomic_write_bytes(payload, out)

    assert out.read_bytes() == payload
    assert not list(tmp_path.glob("**/*.tmp"))


def test_atomic_write_bytes_sobrescribe_atomicamente_sin_dejar_temporales(tmp_path):
    out = tmp_path / "payload.bin"
    atomic_write_bytes(b"version-1", out)
    atomic_write_bytes(b"version-2-mas-larga-que-la-anterior", out)

    assert out.read_bytes() == b"version-2-mas-larga-que-la-anterior"
    assert not list(tmp_path.glob("*.tmp"))


def test_atomic_write_bytes_no_deja_temporal_si_falla_a_mitad(tmp_path, monkeypatch):
    from sqp.storage import atomic

    out = tmp_path / "payload.bin"

    def falla(source, destination):
        raise OSError("fallo simulado en os.replace")

    monkeypatch.setattr(atomic.os, "replace", falla)
    try:
        atomic_write_bytes(b"dato", out)
    except OSError:
        pass
    assert not out.exists()
    assert not list(tmp_path.glob("*.tmp"))
