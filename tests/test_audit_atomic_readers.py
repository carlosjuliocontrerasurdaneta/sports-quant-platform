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
    started = time.monotonic()
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
            assert time.monotonic() - started < 4
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
