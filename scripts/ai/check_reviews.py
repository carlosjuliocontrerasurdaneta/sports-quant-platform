"""Gate the cross-review pipeline on both reviewers having actually run.

Adjudication used to start from whatever text sat in the runtime directory. A
reviewer that never launched, or one whose file was left over from a previous
cycle, was indistinguishable from a clean second opinion, so the pipeline could
report consensus that nobody produced (ADJ-09). This gate answers one question
deterministically -- did each required reviewer run and deliberately produce a
result -- and refuses to let the run continue when the answer is no.

    python scripts/ai/check_reviews.py --reset   # before the reviewers run
    python scripts/ai/check_reviews.py           # before adjudication
"""

from pathlib import Path
import argparse
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_protocol import (  # noqa: E402
    ReviewOutcome,
    consensus_available,
    read_review,
    safe_print,
)


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".claude" / "reviews" / "runtime"
REQUIRED = (("CLAUDE", "claude-review.md"), ("CODEX", "codex-review.md"))


def reset() -> int:
    """Delete last cycle's artifacts so a stale file cannot pose as this run."""
    RUNTIME.mkdir(parents=True, exist_ok=True)
    removed = 0

    for path in RUNTIME.glob("*.md"):
        path.unlink()
        removed += 1

    safe_print(f"Cleared {removed} stale review artifact(s) from {RUNTIME}")

    return 0


def collect() -> list[ReviewOutcome]:
    return [read_review(RUNTIME / name, reviewer) for reviewer, name in REQUIRED]


def report(outcomes: list[ReviewOutcome]) -> int:
    for outcome in outcomes:
        mark = "OK  " if outcome.executed else "FAIL"
        safe_print(f"{mark} {outcome.reviewer:<7} {outcome.summary()}")

    missing = [outcome for outcome in outcomes if not outcome.executed]

    if missing:
        names = ", ".join(outcome.reviewer for outcome in missing)

        safe_print("")
        safe_print("CONSENSUS: BLOCKED")
        safe_print(
            f"{names} did not produce a review. A reviewer that did not run is "
            "not a PASS and must not be reported as a clean second opinion. "
            "Adjudicate the reviews that exist, mark the run INCOMPLETE, and "
            "state which reviewer is missing."
        )

        return 1

    safe_print("")
    safe_print(
        "CONSENSUS: AVAILABLE"
        if consensus_available(outcomes)
        else "CONSENSUS: BLOCKED"
    )

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete previous review artifacts before a new run",
    )
    args = parser.parse_args(argv)

    if args.reset:
        return reset()

    return report(collect())


if __name__ == "__main__":
    raise SystemExit(main())
