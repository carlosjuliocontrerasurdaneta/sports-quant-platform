from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import os
import shutil
import subprocess
import sys
import time


sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_protocol import ReviewStatus, safe_print, write_review  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / ".claude" / "reviews" / "runtime" / "codex-review.md"
REVIEWER = "CODEX"

#: Workspace-local scratch tree for the reviewer's temporary files and caches.
SCRATCH = ".codex-tmp"

#: Prefix of a per-run scratch directory. Only these are ever pruned.
RUN_PREFIX = "run-"

#: How old a run's scratch must be before cleanup may remove it. Comfortably
#: longer than a review, so a reviewer in flight is never the victim.
PRUNE_AFTER_S = 6 * 60 * 60


INTERPRETER_PLACEHOLDER = "__INTERPRETER_SECTION__"

PROMPT_TEMPLATE = """
You are REVIEWER B, the independent Codex reviewer for Sports Quant Platform.

Read AGENTS.md first.

Review the current uncommitted git changes independently.

IMPORTANT:

- Do NOT modify files.
- Do NOT commit.
- Do NOT push.
- Do NOT merge.
- Do NOT read .claude/reviews/runtime/claude-review.md.
- Do NOT trust conclusions from another AI agent.
- Inspect the repository and git diff yourself.

__INTERPRETER_SECTION__

Inspect:

- git status
- git diff
- changed source files
- relevant surrounding implementation
- relevant tests

Look for demonstrable:

- functional bugs
- regressions
- incorrect assumptions
- exception handling problems
- typing problems
- concurrency issues
- security issues
- missing tests
- incorrect tests

For quantitative code also inspect:

- temporal leakage
- look-ahead bias
- target leakage
- train/test contamination
- probability calculation errors
- calibration errors
- timestamp errors
- stale odds handling
- invalid backtesting methodology

Use the contract defined in:

.claude/reviews/CROSS_REVIEW.md

Every finding must contain:

ID:
REVIEWER:
SEVERITY:
CATEGORY:
FILE:
LINES:
CLAIM:
EVIDENCE:
IMPACT:
PROPOSED_FIX:
VERIFICATION:
CONFIDENCE:

Field values may span several lines, so paste real command output or code as
EVIDENCE rather than compressing it.

Use:

REVIEWER: CODEX

Allowed severities:

CRITICAL
HIGH
MEDIUM
LOW

Only report problems supported by concrete evidence.

If, after a complete review, no substantive defect exists, answer with PASS and
the verification behind it, in exactly this shape:

PASS

VERIFICATION: <the commands you actually executed, and their results>

A bare PASS is rejected.

If your tooling could not run -- no interpreter, no test runner, a sandbox that
denies execution -- do not answer PASS. Answer in exactly this shape instead:

EXECUTION_FAILED

VERIFICATION: <what you attempted, the exact commands, and what happened>

That is the only verdict you may declare about your own run, and it records the
review as a failed run rather than a clean second opinion.

Do not ask the user what to review.

The review target is the current uncommitted git diff.
"""


class InterpreterUnavailable(RuntimeError):
    """The launcher cannot name a Python interpreter for the reviewer."""




def resolve_interpreter(executable: str | None = None) -> Path:
    """Return the interpreter the reviewer must use for Python verification.

    The reviewer runs in a sandbox where ``python``, ``pytest``, ``ruff`` and
    ``mypy`` do not resolve through PATH, and where ``py.exe`` reaches the
    WindowsApps stub and is denied. The interpreter running this launcher does
    work, so we name it explicitly rather than letting the reviewer guess.

    The path is made absolute and normalized but symlinks are deliberately NOT
    followed: inside a virtualenv ``sys.executable`` is a link to the base
    interpreter, and resolving it would hand the reviewer a Python without the
    environment's pytest, ruff or mypy -- reintroducing the failure from the
    other side.
    """
    raw = sys.executable if executable is None else executable

    if not raw:
        raise InterpreterUnavailable(
            "sys.executable is empty, so this launcher cannot tell the reviewer "
            "which Python to use"
        )

    path = Path(os.path.abspath(raw))

    if not path.is_file():
        raise InterpreterUnavailable(f"interpreter does not exist: {path}")

    if not os.access(path, os.X_OK):
        raise InterpreterUnavailable(f"interpreter is not executable: {path}")

    return path


def new_scratch() -> str:
    """A scratch path for this run alone, relative to the workspace root.

    Reusing one path was the mistake. The sandbox bakes an ephemeral
    per-session principal into a directory's ACL when it creates it, so a tree
    left by an earlier review is owned by a SID the next run is not -- which is
    how mypy's cache started failing. Deleting it first cannot be the answer
    either: the launcher provably cannot remove what the sandbox created
    (WinError 5 on the reviewer's own pytest basetemp), so a successful review
    guaranteed the next one aborted (CLA-B1).

    A fresh path per run makes staleness unrepresentable rather than detected.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    return f"{SCRATCH}/{RUN_PREFIX}{stamp}-{uuid4().hex[:8]}"


def prune_scratch(keep: str, now: float | None = None) -> None:
    """Best-effort removal of earlier runs' scratch trees.

    Never raises and never gates the launch: an old tree the launcher cannot
    delete is exactly the situation this design tolerates instead of treating
    as fatal.

    Only trees this function's own naming scheme could have produced are
    touched, and only once they are older than :data:`PRUNE_AFTER_S`. Deleting
    every sibling unconditionally reintroduced the cross-run interference that
    per-run paths exist to remove: a second launcher started while a review was
    in flight wiped the running reviewer's ``$env:TEMP`` and mypy cache
    (ADJ-N3). Age is the only signal available here -- the launcher cannot see
    another launcher -- so it is deliberately generous.
    """
    parent = ROOT / SCRATCH
    keep_name = Path(keep).name
    cutoff = (time.time() if now is None else now) - PRUNE_AFTER_S

    try:
        entries = list(parent.iterdir())
    except OSError:
        return

    for entry in entries:
        if entry.name == keep_name or not entry.name.startswith(RUN_PREFIX):
            continue

        try:
            stale = entry.stat().st_mtime < cutoff
        except OSError:
            continue

        if stale:
            shutil.rmtree(entry, ignore_errors=True)


def verification_commands(
    interpreter: Path, windows: bool | None = None, scratch: str = SCRATCH
) -> tuple[str, ...]:
    """The quality gates, expressed so they cannot fall back to PATH.

    PowerShell treats a quoted path as a string expression, not a command, so
    on Windows every invocation is prefixed with the call operator ``&``. POSIX
    shells execute a quoted path directly and have no such operator, so adding
    one there would break the command.
    """
    if windows is None:
        windows = os.name == "nt"

    python = f'& "{interpreter}"' if windows else f'"{interpreter}"'

    return (
        f"{python} -m pytest -q -p no:cacheprovider --basetemp={scratch}/pytest",
        f"{python} -m ruff check src scripts tests",
        f"{python} -m mypy src --cache-dir={scratch}/mypy",
    )


def scratch_setup(windows: bool | None = None, scratch: str = SCRATCH) -> str:
    """Commands that put every temporary artefact inside this run's scratch.

    Two failures made this necessary, both from writing outside a directory the
    current sandbox session owns. pytest's ``tmp_path`` fixtures died on
    ``%TEMP%\\pytest-of-<user>`` with WinError 5, and mypy's sqlite metastore
    could not open its database in ``.mypy_cache``, surfacing as an
    ``INTERNAL ERROR``. The workspace is the one tree the sandbox may write.
    """
    if windows is None:
        windows = os.name == "nt"

    if windows:
        native = scratch.replace("/", "\\")

        return (
            f'New-Item -ItemType Directory -Force -Path "{native}\\pytest" | Out-Null\n'
            f'New-Item -ItemType Directory -Force -Path "{native}\\mypy" | Out-Null\n'
            f'$env:TEMP = (Resolve-Path "{native}").Path\n'
            "$env:TMP  = $env:TEMP"
        )

    return (
        f"mkdir -p {scratch}/pytest {scratch}/mypy\n"
        f'export TMPDIR="$(cd {scratch} && pwd)"'
    )


def interpreter_section(
    interpreter: Path, windows: bool | None = None, scratch: str = SCRATCH
) -> str:
    if windows is None:
        windows = os.name == "nt"

    gates = "\n".join(verification_commands(interpreter, windows, scratch))
    setup = scratch_setup(windows, scratch)
    shell = (
        "Your shell is Windows PowerShell. A quoted path there is a string, not "
        "a command, so start every invocation with the call operator `&`, "
        "exactly as written below. Use this form and no other."
        if windows
        else "Your shell is POSIX: invoke the quoted path directly, exactly as "
        "written below. Use this form and no other."
    )

    return f"""PYTHON INTERPRETER

Use this exact interpreter for every Python command, quotes included:

"{interpreter}"

{shell}

Run tools as modules of it. Do NOT invoke `python`, `pytest`, `ruff`, `mypy` or
`py` by name: in this sandbox they do not resolve through PATH, and `py.exe`
reaches the WindowsApps stub and is denied. The path above is the interpreter
running this launcher, and it works.

FIRST, in the shell session you will run the gates in, redirect every temporary
file into the workspace. Nothing outside it is writable by this sandbox:

{setup}

THEN run the quality gates, in that same session:

{gates}

If that interpreter itself fails, say so in VERIFICATION, quoting the command
you ran and the verbatim error. A review you could not verify is a failed run,
never a PASS."""


def build_prompt(
    interpreter: Path, windows: bool | None = None, scratch: str = SCRATCH
) -> str:
    return PROMPT_TEMPLATE.replace(
        INTERPRETER_PLACEHOLDER, interpreter_section(interpreter, windows, scratch)
    )


def codex_command() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")

        if not appdata:
            raise RuntimeError(
                "APPDATA environment variable is unavailable."
            )

        codex = Path(appdata) / "npm" / "codex.cmd"

        if not codex.exists():
            raise FileNotFoundError(
                f"Codex npm CLI was not found at: {codex}"
            )

        return codex

    return Path("codex")


EXIT_CODES = {
    ReviewStatus.FINDINGS: 0,
    ReviewStatus.CLEAN: 0,
    ReviewStatus.EXECUTION_FAILED: 2,
    ReviewStatus.INVALID_OUTPUT: 3,
    ReviewStatus.EMPTY: 3,
}


def main() -> int:
    command = "codex exec -"
    started = time.monotonic()

    try:
        interpreter = resolve_interpreter()
    except InterpreterUnavailable as exc:
        # Codex is not launched at all: a reviewer handed an interpreter that
        # cannot run reports an unverifiable PASS, and preventing those is the
        # whole point of naming the interpreter here.
        outcome = write_review(
            OUTPUT,
            REVIEWER,
            "",
            launched=False,
            exit_code=None,
            command=command,
            duration_s=time.monotonic() - started,
            failure=f"Cannot prepare the review environment: {exc}",
        )

        safe_print(f"[{outcome.status.value}] {outcome.detail}", sys.stderr)

        return EXIT_CODES[ReviewStatus.EXECUTION_FAILED]

    scratch = new_scratch()
    prune_scratch(scratch)

    try:
        codex = codex_command()
        command = f"{codex} exec -"

        result = subprocess.run(
            [
                str(codex),
                "exec",
                "-",
            ],
            input=build_prompt(interpreter, scratch=scratch),
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=(os.name == "nt"),
            check=False,
        )

    except Exception as exc:
        outcome = write_review(
            OUTPUT,
            REVIEWER,
            "",
            launched=False,
            exit_code=None,
            command=command,
            duration_s=time.monotonic() - started,
            failure=f"Unable to start Codex: {exc}",
        )

        safe_print(f"[{outcome.status.value}] {outcome.detail}", sys.stderr)

        return 127

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    outcome = write_review(
        OUTPUT,
        REVIEWER,
        stdout,
        launched=True,
        exit_code=result.returncode,
        command=command,
        duration_s=time.monotonic() - started,
        failure=(
            ""
            if result.returncode == 0
            else f"Codex exited with code {result.returncode}. "
            f"STDERR: {stderr or '[empty]'}"
        ),
    )

    if not outcome.executed:
        safe_print(f"[{outcome.status.value}] {outcome.detail}", sys.stderr)

        if stdout:
            safe_print(f"\nOUTPUT RECEIVED:\n{stdout}", sys.stderr)

        return EXIT_CODES.get(outcome.status, 1) or 1

    safe_print(stdout)
    safe_print("")
    safe_print(f"Codex review saved to: {OUTPUT} [{outcome.summary()}]")

    if stderr:
        safe_print("")
        safe_print("Codex diagnostic output:")
        safe_print(stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
