"""AUD-005: force a second append while the first writer holds its snapshot."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pandas as pd

from sqp.pipeline import revalidation as rv


def test_concurrent_appends_preserve_rows_and_schema(tmp_path, monkeypatch):
    rv._append_log([dict(event_id="initial")], tmp_path)
    snapshot_ready, release, second_started = Event(), Event(), Event()
    original = rv.atomic_write_csv

    def paused_write(frame, path):
        if "first_only" in frame and "second_only" not in frame:
            snapshot_ready.set()
            assert release.wait(5)
        original(frame, path)

    def second_append():
        second_started.set()
        rv._append_log([dict(event_id="second", second_only=2)], tmp_path)

    monkeypatch.setattr(rv, "atomic_write_csv", paused_write)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(rv._append_log, [dict(event_id="first", first_only=1)], tmp_path)
        try:
            assert snapshot_ready.wait(5)
            second = pool.submit(second_append)
            assert second_started.wait(5)
            # A writer without the transaction lock completes here, then gets
            # overwritten by the first writer's stale snapshot.
            try:
                second.result(timeout=.3)
            except TimeoutError:
                pass
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)
    frame = pd.read_csv(tmp_path / "data/bets/revalidation_log.csv")
    assert set(frame.event_id) == {"initial", "first", "second"}
    assert frame.set_index("event_id").loc["first", "first_only"] == 1
    assert frame.set_index("event_id").loc["second", "second_only"] == 2
