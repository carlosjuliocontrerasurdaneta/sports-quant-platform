"""Stamp an in-process reviewer's output with launcher provenance.

The Codex reviewer attests itself because a subprocess launcher observes its
exit code. A reviewer dispatched inside the orchestrator has no such launcher,
so the orchestrator records what it observed here instead. The guarantee is
weaker -- it rests on the orchestrator reporting honestly -- but the states are
the same, and an agent that never returned still cannot become a clean review:
with no body file there is nothing to stamp.

    python scripts/ai/record_review.py CLAUDE --body <path>
    python scripts/ai/record_review.py CLAUDE --failed "agent returned no review"
"""

from pathlib import Path
import argparse
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_protocol import safe_print, write_review  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".claude" / "reviews" / "runtime"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reviewer", help="reviewer name, e.g. CLAUDE")
    parser.add_argument("--body", type=Path, help="file holding the review text")
    parser.add_argument("--failed", help="record that the reviewer did not run")
    args = parser.parse_args(argv)

    reviewer = args.reviewer.upper()
    output = RUNTIME / f"{reviewer.lower()}-review.md"

    if args.failed or args.body is None:
        outcome = write_review(
            output,
            reviewer,
            "",
            launched=False,
            exit_code=None,
            command=f"in-process agent {reviewer}",
            duration_s=0.0,
            failure=args.failed or "no review body was provided",
        )
    elif not args.body.exists():
        outcome = write_review(
            output,
            reviewer,
            "",
            launched=False,
            exit_code=None,
            command=f"in-process agent {reviewer}",
            duration_s=0.0,
            failure=f"reviewer produced no output at {args.body}",
        )
    else:
        outcome = write_review(
            output,
            reviewer,
            args.body.read_text(encoding="utf-8", errors="replace"),
            launched=True,
            exit_code=0,
            command=f"in-process agent {reviewer}",
            duration_s=0.0,
        )

    safe_print(f"{reviewer}: {outcome.summary()} -> {output}")

    return 0 if outcome.executed else 1


if __name__ == "__main__":
    raise SystemExit(main())
