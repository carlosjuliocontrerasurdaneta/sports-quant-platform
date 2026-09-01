"""Launch the Codex reviewer for Cross Review Protocol V2.

The reviewer is handed this round's ``run_id`` and Snapshot V2 ``review_tree``
and must echo both in its JSON. That is what binds a review to a round: an
artefact from an earlier cycle carries the wrong id and cannot be counted, and
a tree edited mid-round no longer rebuilds to the ``review_tree`` both
reviewers signed.

Sandbox handling (interpreter discovery, per-run scratch, shell syntax) is
imported from the V1 launcher rather than copied. Those parts were expensive to
get right -- they encode a Windows ACL problem, a PowerShell call-operator
problem and a stale-scratch problem -- and none of them is what V2 changes.
"""

from pathlib import Path
import os
import subprocess
import sys
import time


sys.path.insert(0, str(Path(__file__).resolve().parent))

from codex_review import (  # noqa: E402
    InterpreterUnavailable,
    codex_command,
    new_scratch,
    prune_scratch,
    resolve_interpreter,
    scratch_setup,
    verification_commands,
)
from review_v2 import (  # noqa: E402
    CODEX_TIMEOUT_S,
    FINDING_FIELDS,
    REQUIRED_CHECKS,
    SCHEMA_VERSION,
    ReviewState,
    Run,
    load_run,
    run_checks,
    write_review,
)


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".claude" / "reviews" / "runtime" / "v2"
REVIEWER = "CODEX"

EXIT_CODES = {
    ReviewState.FINDINGS: 0,
    ReviewState.CLEAN: 0,
    ReviewState.BLOCKED: 2,
    ReviewState.EXECUTION_FAILED: 2,
    ReviewState.VERIFICATION_FAILED: 2,
    ReviewState.SCHEMA_INVALID: 3,
    ReviewState.EMPTY: 3,
    ReviewState.RUN_MISMATCH: 4,
    ReviewState.WORKSPACE_CHANGED: 4,
}


def safe_print(text: str, stream: object = None) -> None:
    target = sys.stderr if stream == "err" else sys.stdout
    encoding = getattr(target, "encoding", None) or "utf-8"

    print(text.encode(encoding, "replace").decode(encoding, "replace"), file=target)


def build_prompt(interpreter: Path, scratch: str, run: Run) -> str:
    fields = "\n".join(f'      "{name}": "<text>"{"," if i < 10 else ""}'
                       for i, name in enumerate(FINDING_FIELDS))

    return f"""
You are REVIEWER B, the independent Codex reviewer for Sports Quant Platform.

Read AGENTS.md first.

Review the current uncommitted git changes independently.

IMPORTANT:

- Do NOT modify files.
- Do NOT commit, push or merge.
- Do NOT read any file under .claude/reviews/runtime/.
- Do NOT trust conclusions from another AI agent.
- Inspect the repository and git diff yourself.

{interpreter_block(interpreter, scratch)}

WHAT TO LOOK FOR

Demonstrable problems only, each backed by output you actually produced:
functional bugs, regressions, wrong assumptions, exception handling, typing,
concurrency, security, missing or incorrect tests. For quantitative code also:
temporal leakage, look-ahead bias, target leakage, train/test contamination,
probability and calibration errors, timestamp errors, stale odds handling,
invalid backtesting methodology.

OUTPUT FORMAT -- READ CAREFULLY

Reply with ONE JSON object and nothing else. No prose before or after, no
markdown fence. The object must be exactly this shape:

{{
  "schema_version": {SCHEMA_VERSION},
  "run_id": "{run.run_id}",
  "reviewer": "CODEX",
  "review_tree": "{run.review_tree}",
  "result": {{
    "verdict": "<CLEAN | FINDINGS | BLOCKED>",
    "findings": [
      {{
{fields}
      }}
    ]
  }},
  "verification": {{ "notes": "<optional free text; see below>" }}
}}

Copy `run_id` and `review_tree` exactly as given above. `review_tree` is the
Snapshot V2 identity of the tree you are reviewing; echoing it is what binds
this review to this round.

Rules:

- verdict FINDINGS requires a non-empty findings list.
- verdict CLEAN and verdict BLOCKED both require an EMPTY findings list.
- severity is one of CRITICAL, HIGH, MEDIUM, LOW.
- every finding field is a non-empty string.
- `verification.notes` is optional prose. It is stored verbatim and read by
  humans only. It has NO effect on the recorded state: this launcher runs
  {", ".join(REQUIRED_CHECKS)} itself and stamps the observed exit codes over
  anything you write there. Writing "all passed" cannot make a failing check
  pass, and writing "everything failed" cannot make a passing one fail.

Because this is JSON, any field may contain absolutely anything: contract
labels, a whole finding, markdown, fenced code, `-->`, `<!--`, Unicode. Paste
real command output and real source verbatim into `evidence`. Do not abbreviate
it, do not escape it by hand -- JSON string encoding handles all of it.

Use verdict BLOCKED, with `verification.notes` explaining what you attempted and
what happened, if you could not complete the review. A review you could not
verify is a failed run, never CLEAN.

The review target is the current uncommitted git diff.
"""


def interpreter_block(interpreter: Path, scratch: str) -> str:
    gates = "\n".join(verification_commands(interpreter, scratch=scratch))

    return f"""PYTHON INTERPRETER AND SCRATCH

Use this exact interpreter for every Python command, quotes included:

"{interpreter}"

Your shell is Windows PowerShell when running on Windows: a quoted path there
is a string, not a command, so start every invocation with the call operator
`&`, exactly as written below.

FIRST, in the shell session you will run the gates in, redirect every temporary
file into this run's scratch. Nothing outside the workspace is writable:

{scratch_setup(scratch=scratch)}

THEN run the quality gates, in that same session:

{gates}"""


def main() -> int:
    command = "codex exec -"
    started = time.monotonic()
    run = load_run(RUNTIME)

    if run is None:
        safe_print(
            "[NO RUN] No V2 round is open. Start one with: "
            "python scripts/ai/check_reviews_v2.py --start",
            "err",
        )

        return 5

    try:
        interpreter = resolve_interpreter()
    except InterpreterUnavailable as exc:
        outcome = write_review(
            RUNTIME,
            REVIEWER,
            "",
            launched=False,
            exit_code=None,
            command=command,
            duration_s=time.monotonic() - started,
            run=run,
            failure=f"Cannot name a Python interpreter for the reviewer: {exc}",
        )

        safe_print(f"[{outcome.state.value}] {outcome.detail}", "err")

        return EXIT_CODES[ReviewState.EXECUTION_FAILED]

    scratch = new_scratch()
    prune_scratch(scratch)

    try:
        codex = codex_command()
        command = f"{codex} exec -"

        # `timeout` obligatorio: sin el, un Codex colgado deja la ronda abierta
        # y `check_reviews_v2.py --start` se niega a abrir otra mientras no
        # pueda cerrar la anterior, con lo que el protocolo queda atascado hasta
        # intervencion manual (auditoria 2026-09-01, F-09). El
        # `subprocess.TimeoutExpired` lo recoge el `except` de abajo y se
        # registra como run fallido, que es exactamente el estado correcto: un
        # reviewer que no termino no es un reviewer limpio.
        result = subprocess.run(
            [str(codex), "exec", "-"],
            input=build_prompt(interpreter, scratch, run),
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=(os.name == "nt"),
            check=False,
            timeout=CODEX_TIMEOUT_S,
        )
    except Exception as exc:  # noqa: BLE001 - recorded as a failed run
        outcome = write_review(
            RUNTIME,
            REVIEWER,
            "",
            launched=False,
            exit_code=None,
            command=command,
            duration_s=time.monotonic() - started,
            run=run,
            failure=f"Unable to start Codex: {exc}",
        )

        safe_print(f"[{outcome.state.value}] {outcome.detail}", "err")

        return 127

    stdout, stderr = result.stdout.strip(), result.stderr.strip()

    # The launcher verifies, the reviewer does not. Running these here is what
    # makes exit_code an observation instead of a claim (requirement 6).
    safe_print(f"Running {', '.join(REQUIRED_CHECKS)} to stamp the verification...")
    observed = run_checks(ROOT, str(interpreter))

    for check in observed:
        safe_print(f"  {check['name']:7} exit {check['exit_code']}  {check['summary']}")

    outcome = write_review(
        RUNTIME,
        REVIEWER,
        stdout,
        launched=True,
        exit_code=result.returncode,
        command=command,
        duration_s=time.monotonic() - started,
        run=run,
        checks=observed,
        failure=(
            ""
            if result.returncode == 0
            else f"Codex exited with code {result.returncode}. "
            f"STDERR: {stderr or '[empty]'}"
        ),
    )

    if not outcome.counts:
        safe_print(f"[{outcome.state.value}] {outcome.detail}", "err")

        if stdout:
            safe_print(f"\nOUTPUT RECEIVED:\n{stdout}", "err")

        return EXIT_CODES.get(outcome.state, 1) or 1

    safe_print(f"CODEX: {outcome.summary()}")
    safe_print(f"Saved to: {RUNTIME / 'codex.json'}")

    if stderr:
        safe_print("")
        safe_print("Codex diagnostic output:")
        safe_print(stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
