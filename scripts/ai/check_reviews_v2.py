"""Phase 0 and the consensus gate for Cross Review Protocol V2.

    python scripts/ai/check_reviews_v2.py --start   # mint run_id + fingerprint
    python scripts/ai/check_reviews_v2.py           # gate, before adjudicating
    python scripts/ai/check_reviews_v2.py --reset   # drop the whole round

The gate answers one question: may these two artefacts be adjudicated as a
cross review? It says no unless both reviewers ran, both carry this round's
run_id, both carry the ``review_tree`` the round started with, and the tree on
disk still rebuilds to it. A review from an earlier round is therefore not
merely stale, it is unusable -- which is what V1 could only achieve by
remembering to reset.

``--start`` freezes the tree with Snapshot V2 and publishes it as
``refs/cross-review/<run_id>``; ``--reset`` drops that ref. The "still matches"
question is answered by rebuilding the tree from the bytes on disk, not by
asking ``git status`` what changed -- a path hidden behind ``--skip-worktree``
answers that question with silence.
"""

from pathlib import Path
import argparse
import shutil
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_v2 import (  # noqa: E402
    consensus_available,
    end_run,
    load_run,
    read_review,
    snapshot_state,
    start_run,
)
from snapshot_v2 import SnapshotError, ref_name  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".claude" / "reviews" / "runtime" / "v2"
REVIEWERS = ("CLAUDE", "CODEX")


def safe_print(text: str) -> None:
    """Print on a console that may not encode every character (Windows cp1252)."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"

    print(text.encode(encoding, "replace").decode(encoding, "replace"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", action="store_true", help="begin a new round")
    parser.add_argument("--reset", action="store_true", help="discard the round")
    args = parser.parse_args(argv)

    if args.reset:
        # Drop the snapshot ref before deleting the manifest that names it,
        # otherwise the ref outlives every record of which round it belonged to.
        try:
            end_run(RUNTIME, ROOT)
        except SnapshotError as exc:
            safe_print(f"WARNING: could not drop the snapshot ref: {exc}")

        if RUNTIME.exists():
            shutil.rmtree(RUNTIME, ignore_errors=True)

        safe_print(f"Cleared the V2 round at {RUNTIME}")

        return 0

    if args.start:
        # An already-open round owns a ref. Overwriting its manifest without
        # dropping that ref would leak it under a run_id nothing records.
        try:
            end_run(RUNTIME, ROOT)
        except SnapshotError as exc:
            safe_print(f"WARNING: could not drop the previous snapshot ref: {exc}")

        try:
            started = start_run(RUNTIME, ROOT)
        except SnapshotError as exc:
            # A round that cannot freeze its own tree must not open at all.
            # This path used to die on a raw traceback (ADJ-V2-05).
            safe_print(f"[NO ROUND] cannot snapshot the workspace: {exc}")

            return 2

        safe_print(f"run_id       : {started.run_id}")
        safe_print(f"base_commit  : {started.snapshot.base_commit}")
        safe_print(f"staged_tree  : {started.snapshot.staged_tree}")
        safe_print(f"review_tree  : {started.snapshot.review_tree}")
        safe_print(f"review_commit: {started.snapshot.review_commit}")
        safe_print(f"snapshot ref : {ref_name(started.run_id)}")

        return 0

    run = load_run(RUNTIME)
    outcomes = [read_review(RUNTIME, name, run) for name in REVIEWERS]

    for outcome in outcomes:
        flag = "OK  " if outcome.counts else "FAIL"
        safe_print(f"{flag} {outcome.reviewer:7} {outcome.summary()}")

    # Snapshot V2 is the authority: the round is bound to stored bytes, so this
    # asks git to rebuild the tree rather than asking status what it feels like
    # mentioning.
    tree_ok, tree_detail = snapshot_state(ROOT, run)

    if run is not None:
        safe_print("")
        safe_print(f"round run_id        : {run.run_id}")
        safe_print(f"review_tree at start: {run.review_tree}")
        safe_print(
            "tree now            : "
            + ("unchanged" if tree_ok else f"MOVED -- {tree_detail}")
        )

    available, reason = consensus_available(outcomes, run, tree_ok, tree_detail)

    safe_print("")

    if available:
        safe_print("CONSENSUS: AVAILABLE")

        return 0

    safe_print("CONSENSUS: BLOCKED")
    safe_print(reason)
    safe_print(
        "Do not report consensus and do not present a reviewer that did not run "
        "as a clean second opinion. Adjudicate what exists and mark the run "
        "INCOMPLETE."
    )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
