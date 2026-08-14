"""Stamp an in-process reviewer's V2 JSON with launcher provenance.

    python scripts/ai/record_review_v2.py CLAUDE --body <path-to-json>
    python scripts/ai/record_review_v2.py CLAUDE --failed "agent returned nothing"

The Codex reviewer attests itself because a subprocess launcher observes its
exit code. An agent dispatched inside the orchestrator has no such launcher, so
the orchestrator records what it observed here instead. The guarantee is weaker
-- it rests on the orchestrator reporting honestly -- but the states are the
same, the run binding is enforced identically, and an agent that never returned
still cannot become a review: with no body there is nothing to stamp.
"""

from pathlib import Path
import argparse
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_v2 import (  # noqa: E402
    REQUIRED_CHECKS,
    load_run,
    run_checks,
    write_review,
)


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".claude" / "reviews" / "runtime" / "v2"


def safe_print(text: str) -> None:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"

    print(text.encode(encoding, "replace").decode(encoding, "replace"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reviewer", help="reviewer name, e.g. CLAUDE")
    parser.add_argument("--body", type=Path, help="file holding the review JSON")
    parser.add_argument("--failed", help="record that the reviewer did not run")
    args = parser.parse_args(argv)

    reviewer = args.reviewer.upper()
    run = load_run(RUNTIME)

    if run is None:
        safe_print(
            "[NO RUN] No V2 round is open. Start one with: "
            "python scripts/ai/check_reviews_v2.py --start"
        )

        return 5

    # Same rule as the subprocess launcher: whoever records the review runs the
    # checks. The agent's prose never decides the state (requirement 6).
    safe_print(f"Running {', '.join(REQUIRED_CHECKS)} to stamp the verification...")
    observed = run_checks(ROOT, sys.executable)

    for check in observed:
        safe_print(f"  {check['name']:7} exit {check['exit_code']}  {check['summary']}")

    common = {
        "command": f"in-process agent {reviewer}",
        "duration_s": 0.0,
        "run": run,
        "checks": observed,
    }

    if args.failed or args.body is None:
        outcome = write_review(
            RUNTIME, reviewer, "",
            launched=False, exit_code=None,
            failure=args.failed or "no review body was provided",
            **common,  # type: ignore[arg-type]
        )
    elif not args.body.exists():
        outcome = write_review(
            RUNTIME, reviewer, "",
            launched=False, exit_code=None,
            failure=f"reviewer produced no output at {args.body}",
            **common,  # type: ignore[arg-type]
        )
    else:
        outcome = write_review(
            RUNTIME, reviewer,
            args.body.read_text(encoding="utf-8", errors="replace"),
            launched=True, exit_code=0,
            **common,  # type: ignore[arg-type]
        )

    safe_print(f"{reviewer}: {outcome.summary()}")

    return 0 if outcome.counts else 1


if __name__ == "__main__":
    raise SystemExit(main())
