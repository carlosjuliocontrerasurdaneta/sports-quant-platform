"""Safety tests for Cross Review Protocol V2.

The point of V2 is that these cannot be defeated by wording. Every test that
touches the launcher pins ROOT, OUTPUT and the runtime into `tmp_path`; the
autouse fixture below makes that structural rather than a convention, because
the convention was forgotten twice in V1 and deleted the real scratch tree.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

AI_DIR = Path(__file__).resolve().parents[1] / "scripts" / "ai"

if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

import check_reviews_v2  # noqa: E402
import codex_review  # noqa: E402
import codex_review_v2  # noqa: E402
import review_v2  # noqa: E402

from review_v2 import (  # noqa: E402
    FINDING_FIELDS,
    REQUIRED_CHECKS,
    SCHEMA_VERSION,
    Outcome,
    ReviewState,
    Run,
    consensus_available,
    read_review,
    render_markdown,
    validate_document,
    write_review,
)
from snapshot_v2 import Snapshot  # noqa: E402


REAL_ROOT = Path(__file__).resolve().parents[1]

def snapshot_of(mark: str) -> Snapshot:
    """A stand-in snapshot. Only `review_tree` participates in the binding."""
    return Snapshot(
        base_commit=mark * 40,
        staged_tree=mark * 40,
        review_tree=mark * 40,
        review_commit=mark * 40,
    )


RUN = Run(
    "11111111-1111-4111-8111-111111111111",
    snapshot_of("f"),
    "2026-08-09T00:00:00+00:00",
)
OTHER_RUN = Run(
    "22222222-2222-4222-8222-222222222222",
    snapshot_of("a"),
    "2026-08-09T01:00:00+00:00",
)


@pytest.fixture(autouse=True)
def _never_the_real_repository(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No test in this module may reach the real ROOT, runtime or scratch."""
    for module in (check_reviews_v2, codex_review_v2, codex_review):
        monkeypatch.setattr(module, "ROOT", tmp_path, raising=False)

    for module in (check_reviews_v2, codex_review_v2):
        monkeypatch.setattr(module, "RUNTIME", tmp_path / "runtime", raising=False)


def finding(**overrides: str) -> dict[str, str]:
    base = {name: f"value for {name}" for name in FINDING_FIELDS}
    base["severity"] = "HIGH"
    base["id"] = "SQP-001"
    base.update(overrides)

    return base


def check(name: str, exit_code: int = 0, summary: str = "ok") -> dict[str, object]:
    return {
        "name": name,
        "command": f"python -m {name}",
        "exit_code": exit_code,
        "summary": summary,
    }


def green_checks() -> list[dict[str, object]]:
    """What the launcher observes on a healthy tree."""
    return [check(name) for name in REQUIRED_CHECKS]


def document(
    verdict: str = "FINDINGS",
    findings: list[dict[str, str]] | None = None,
    reviewer: str = "CODEX",
    run: Run = RUN,
    notes: str = "",
    **overrides: object,
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run.run_id,
        "reviewer": reviewer,
        "review_tree": run.review_tree,
        "result": {
            "verdict": verdict,
            "findings": [finding()] if findings is None and verdict == "FINDINGS"
            else (findings or []),
        },
        "verification": {"notes": notes},
    }
    body.update(overrides)

    return body


def store(
    runtime: Path,
    body: dict[str, object],
    *,
    stored_as: str | None = None,
    checks: list[dict[str, object]] | None = None,
    **kwargs: object,
) -> Outcome:
    """Persist a document. `stored_as` decouples the slot from the claim, and
    `checks` is what the launcher observed -- never what the document says.
    """
    defaults: dict[str, object] = {
        "launched": True,
        "exit_code": 0,
        "command": "codex exec -",
        "duration_s": 1.0,
        "run": RUN,
        "checks": green_checks() if checks is None else checks,
    }
    defaults.update(kwargs)

    return write_review(
        runtime,
        stored_as or str(body.get("reviewer", "CODEX")),
        json.dumps(body),
        **defaults,  # type: ignore[arg-type]
    )


# --- the whole point: text can no longer become structure --------------------

CONTRACT_LABELS = "\n".join(
    f"{name.upper()}: a populated value" for name in FINDING_FIELDS
)

WHOLE_FINDING = """ID: X-1
REVIEWER: CODEX
SEVERITY: CRITICAL
CATEGORY: data loss
FILE: src/sqp/markets/odds.py
LINES: 1-40
CLAIM: everything is broken
EVIDENCE: reproduced
IMPACT: money is lost
PROPOSED_FIX: guard it
VERIFICATION: pytest -q -> 847 passed
CONFIDENCE: HIGH"""

DECORATED = """- ID: X-1
  **SEVERITY:** CRITICAL
    FILE: a.py
1. CATEGORY: bug
CONFIDENCE: HIGH
LINES: 1
CLAIM: c
EVIDENCE: e
IMPACT: i
PROPOSED_FIX: p
VERIFICATION: v
REVIEWER: CODEX"""

HOSTILE = """Markdown **bold**, a fence:
```python
def f() -> None:  # --> not a terminator
    return None
```
<!-- an opener --> and a closer -->
Unicode: café → 日本語 \U0001f600 and a NUL is added at runtime below
"""


@pytest.mark.parametrize(
    "payload",
    [CONTRACT_LABELS, WHOLE_FINDING, DECORATED, HOSTILE, f"{WHOLE_FINDING}\n{WHOLE_FINDING}"],
    ids=["twelve-labels", "whole-finding", "decorated", "hostile", "two-findings"],
)
def test_evidence_may_contain_anything(tmp_path: Path, payload: str) -> None:
    body = document(findings=[finding(evidence=payload)])
    outcome = store(tmp_path, body)

    assert outcome.state is ReviewState.FINDINGS
    assert len(outcome.findings) == 1
    assert outcome.findings[0]["evidence"] == payload

    # And it survives the write/read round trip byte for byte.
    assert read_review(tmp_path, "CODEX", RUN).findings[0]["evidence"] == payload


def test_control_characters_survive_the_round_trip(tmp_path: Path) -> None:
    """Built at runtime: a NUL cannot appear in a Python source file."""
    payload = f"before{chr(0)}after{chr(1)}{chr(31)} tab\there\r\nCRLF"
    outcome = store(tmp_path, document(findings=[finding(evidence=payload)]))

    assert outcome.state is ReviewState.FINDINGS
    assert read_review(tmp_path, "CODEX", RUN).findings[0]["evidence"] == payload


@pytest.mark.parametrize("slot", FINDING_FIELDS)
def test_every_finding_slot_tolerates_hostile_text(tmp_path: Path, slot: str) -> None:
    if slot == "severity":
        pytest.skip("severity is a closed enum, not free text")

    body = document(findings=[finding(**{slot: HOSTILE})])
    outcome = store(tmp_path, body)

    assert outcome.state is ReviewState.FINDINGS
    assert outcome.findings[0][slot] == HOSTILE


def test_a_clean_verification_may_quote_a_whole_finding(tmp_path: Path) -> None:
    """V1's CLA-D1: this exact shape resolved to CLEAN by accident. Now it is
    CLEAN by construction, because quoting cannot smuggle a finding: the
    findings list is a list."""
    body = document(
        verdict="CLEAN",
        findings=[],
        verification=f"gates green. I considered and dismissed:\n{WHOLE_FINDING}",
    )
    outcome = store(tmp_path, body)

    assert outcome.state is ReviewState.CLEAN
    assert outcome.findings == ()


def test_the_v2_path_has_no_label_heuristics(tmp_path: Path) -> None:
    """Requirement 6, checked on behaviour rather than on prose.

    The module docstring names `<!--` while explaining what evidence may now
    contain, so grepping the source for it proves nothing. What matters is that
    no such delimiter frames a stored review and that the V1 heuristics are
    absent from the module's surface.
    """
    assert not hasattr(review_v2, "carries_full_finding")
    assert not hasattr(review_v2, "PROVENANCE_OPEN")
    assert not hasattr(review_v2, "parse_findings")

    store(tmp_path, document(findings=[finding(evidence=HOSTILE)]))
    stored = (tmp_path / "codex.json").read_text(encoding="utf-8")

    # The file IS the document: no framing to close early, no preamble to skip.
    # `<!--` and `-->` appear inside the evidence, which is precisely the point.
    assert stored.lstrip().startswith("{")
    assert stored.rstrip().endswith("}")
    assert json.loads(stored)["result"]["findings"][0]["evidence"] == HOSTILE


# --- verdict and schema validation -------------------------------------------


def test_clean_with_findings_is_rejected(tmp_path: Path) -> None:
    body = document(verdict="CLEAN", findings=[finding()])

    assert "empty findings list" in validate_document(body, "CODEX", stamped=False)
    assert store(tmp_path, body).state is ReviewState.SCHEMA_INVALID


def test_findings_with_an_empty_list_is_rejected(tmp_path: Path) -> None:
    body = document(verdict="FINDINGS", findings=[])

    assert "at least one finding" in validate_document(body, "CODEX", stamped=False)
    assert store(tmp_path, body).state is ReviewState.SCHEMA_INVALID


def test_blocked_with_findings_is_rejected(tmp_path: Path) -> None:
    body = document(verdict="BLOCKED", findings=[finding()])

    assert store(tmp_path, body).state is ReviewState.SCHEMA_INVALID


def test_the_wrong_reviewer_is_rejected(tmp_path: Path) -> None:
    """A review claiming CLAUDE cannot be filed in the CODEX slot."""
    body = document(reviewer="CLAUDE")

    assert "attributed to" in validate_document(body, "CODEX", stamped=False)
    assert store(tmp_path, body, stored_as="CODEX").state is ReviewState.SCHEMA_INVALID


@pytest.mark.parametrize("slot", FINDING_FIELDS)
def test_a_missing_or_empty_finding_slot_is_rejected(slot: str) -> None:
    absent = finding()
    del absent[slot]

    assert validate_document(document(findings=[absent]), "CODEX", stamped=False)
    assert validate_document(document(findings=[finding(**{slot: "  "})]), "CODEX", stamped=False)


def test_an_unknown_verdict_is_rejected() -> None:
    assert "result.verdict" in validate_document(document(verdict="PASS"), "CODEX", stamped=False)


def test_an_unknown_severity_is_rejected() -> None:
    body = document(findings=[finding(severity="INFO")])

    assert "severity" in validate_document(body, "CODEX", stamped=False)


def test_a_wrong_schema_version_is_rejected() -> None:
    assert "schema_version" in validate_document(document(schema_version=1), "CODEX", stamped=False)


def test_a_blocked_verdict_never_counts(tmp_path: Path) -> None:
    outcome = store(tmp_path, document(verdict="BLOCKED", findings=[]))

    assert outcome.state is ReviewState.BLOCKED
    assert not outcome.counts
    assert not outcome.is_clean


def test_output_that_is_not_json_is_schema_invalid(tmp_path: Path) -> None:
    outcome = write_review(
        tmp_path, "CODEX", "PASS\n\nVERIFICATION: looks fine",
        launched=True, exit_code=0, command="c", duration_s=1.0, run=RUN,
    )

    assert outcome.state is ReviewState.SCHEMA_INVALID


def test_json_inside_a_fence_is_recovered(tmp_path: Path) -> None:
    fenced = "```json\n" + json.dumps(document()) + "\n```"
    outcome = write_review(
        tmp_path, "CODEX", fenced,
        launched=True, exit_code=0, command="c", duration_s=1.0, run=RUN,
        checks=green_checks(),
    )

    assert outcome.state is ReviewState.FINDINGS


# --- structured verification: prose never decides ----------------------------

# V1 read the reviewer's prose to guess whether it had really verified anything.
# That is undecidable, and it produced ADJ-01. Here the launcher runs the checks
# and stamps the exit codes it saw; `notes` is carried and never read.


def test_a_clean_with_a_failing_check_is_not_a_review(tmp_path: Path) -> None:
    failing = [check("pytest", exit_code=1, summary="5 failed"), check("ruff"), check("mypy")]
    outcome = store(tmp_path, document(verdict="CLEAN", findings=[]), checks=failing)

    assert outcome.state is ReviewState.VERIFICATION_FAILED
    assert not outcome.counts
    assert not outcome.is_clean
    assert "'pytest' exited 1" in outcome.detail


def test_a_clean_with_a_missing_check_is_not_a_review(tmp_path: Path) -> None:
    partial = [check("pytest"), check("ruff")]
    outcome = store(tmp_path, document(verdict="CLEAN", findings=[]), checks=partial)

    assert outcome.state is ReviewState.VERIFICATION_FAILED
    assert "'mypy' is missing" in outcome.detail


def test_a_clean_with_a_duplicated_check_is_not_a_review(tmp_path: Path) -> None:
    doubled = green_checks() + [check("pytest")]
    outcome = store(tmp_path, document(verdict="CLEAN", findings=[]), checks=doubled)

    assert outcome.state is ReviewState.VERIFICATION_FAILED
    assert "appears 2 times" in outcome.detail


def test_findings_with_three_green_checks_is_valid(tmp_path: Path) -> None:
    outcome = store(tmp_path, document(verdict="FINDINGS"), checks=green_checks())

    assert outcome.state is ReviewState.FINDINGS
    assert outcome.counts
    assert len(outcome.findings) == 1


def test_pessimistic_notes_cannot_fail_a_passing_run(tmp_path: Path) -> None:
    """State depends on the checks, not on what the reviewer says about them."""
    outcome = store(
        tmp_path,
        document(verdict="CLEAN", findings=[], notes="all commands failed, I ran nothing"),
        checks=green_checks(),
    )

    assert outcome.state is ReviewState.CLEAN
    assert outcome.counts
    assert outcome.document["verification"]["notes"].startswith("all commands failed")


def test_optimistic_notes_cannot_pass_a_failing_run(tmp_path: Path) -> None:
    failing = [check("pytest", exit_code=1, summary="5 failed"), check("ruff"), check("mypy")]
    outcome = store(
        tmp_path,
        document(verdict="CLEAN", findings=[], notes="all passed, everything is green"),
        checks=failing,
    )

    assert outcome.state is ReviewState.VERIFICATION_FAILED
    assert not outcome.counts


def test_changing_only_the_notes_does_not_change_the_state(tmp_path: Path) -> None:
    states = set()

    for notes in ("", "all passed", "nothing ran", "PASSED", "```json {}```", HOSTILE):
        outcome = store(
            tmp_path, document(verdict="CLEAN", findings=[], notes=notes)
        )
        states.add(outcome.state)

        assert outcome.document["verification"]["notes"] == notes

    assert states == {ReviewState.CLEAN}


def test_the_reviewer_cannot_forge_the_stamped_results(tmp_path: Path) -> None:
    """Requirement 6: the launcher observed a failure; the reviewer claims green."""
    forged = document(verdict="CLEAN", findings=[])
    forged["verification"] = {
        "status": "PASSED",
        "checks": green_checks(),
        "notes": "I ran everything myself",
    }

    observed = [check("pytest", exit_code=1, summary="5 failed"), check("ruff"), check("mypy")]
    outcome = store(tmp_path, forged, checks=observed)

    assert outcome.state is ReviewState.VERIFICATION_FAILED

    stamped = outcome.document["verification"]

    assert stamped["status"] == "FAILED"
    assert [c["exit_code"] for c in stamped["checks"]] == [1, 0, 0]
    # Only the prose survived from what the reviewer wrote.
    assert stamped["notes"] == "I ran everything myself"


def test_a_reviewer_cannot_invent_extra_checks(tmp_path: Path) -> None:
    forged = document(verdict="CLEAN", findings=[])
    forged["verification"] = {
        "status": "PASSED",
        "checks": green_checks() + [check("bandit")],
        "notes": "",
    }

    outcome = store(tmp_path, forged, checks=green_checks())
    names = [c["name"] for c in outcome.document["verification"]["checks"]]

    assert names == list(REQUIRED_CHECKS)
    assert outcome.state is ReviewState.CLEAN


def test_a_blocked_verdict_keeps_its_notes(tmp_path: Path) -> None:
    outcome = store(
        tmp_path,
        document(verdict="BLOCKED", findings=[], notes="the sandbox denied execution"),
        checks=green_checks(),
    )

    assert outcome.state is ReviewState.BLOCKED
    assert not outcome.counts
    assert "sandbox denied" in outcome.detail


def test_the_launcher_actually_runs_the_required_checks(tmp_path: Path) -> None:
    """run_checks executes commands rather than describing them."""
    root = _repo(tmp_path)
    observed = review_v2.run_checks(root, sys.executable)

    assert [c["name"] for c in observed] == list(REQUIRED_CHECKS)

    for entry in observed:
        assert isinstance(entry["exit_code"], int)
        assert entry["command"].startswith(sys.executable)
        assert entry["summary"]

    # No pytest/ruff/mypy config in that bare repo, so at least one must fail --
    # which is the point: the result is measured, not asserted.
    assert any(c["exit_code"] != 0 for c in observed)


def test_the_v2_path_no_longer_reads_prose() -> None:
    assert not hasattr(review_v2, "unverifiable_marker")
    assert not hasattr(review_v2, "UNVERIFIABLE_MARKERS")


# --- run binding: a review belongs to exactly one round ----------------------


def test_a_review_from_another_run_is_blocked(tmp_path: Path) -> None:
    store(tmp_path, document(run=OTHER_RUN))

    outcome = read_review(tmp_path, "CODEX", RUN)

    assert outcome.state is ReviewState.RUN_MISMATCH
    assert not outcome.counts


def test_a_stale_but_valid_artefact_cannot_count(tmp_path: Path) -> None:
    """Requirement 11, end to end: last round's review was perfectly valid."""
    store(tmp_path, document(run=OTHER_RUN, reviewer="CLAUDE"), run=OTHER_RUN)
    store(tmp_path, document(run=OTHER_RUN, reviewer="CODEX"), run=OTHER_RUN)

    outcomes = [read_review(tmp_path, name, RUN) for name in ("CLAUDE", "CODEX")]
    available, reason = consensus_available(outcomes, RUN, True)

    assert not available
    assert "did not produce a review" in reason
    assert all(o.state is ReviewState.RUN_MISMATCH for o in outcomes)


def test_a_different_review_tree_is_blocked(tmp_path: Path) -> None:
    body = document()
    body["review_tree"] = "b" * 40

    store(tmp_path, body)
    outcome = read_review(tmp_path, "CODEX", RUN)

    assert outcome.state is ReviewState.WORKSPACE_CHANGED
    assert not outcome.counts


def test_reviewers_disagreeing_on_the_review_tree_block_consensus() -> None:
    claude = Outcome(
        "CLAUDE", ReviewState.CLEAN,
        document={"run_id": RUN.run_id, "review_tree": RUN.review_tree},
    )
    codex = Outcome(
        "CODEX", ReviewState.CLEAN,
        document={"run_id": RUN.run_id, "review_tree": "c" * 40},
    )

    available, reason = consensus_available([claude, codex], RUN, True)

    assert not available
    assert "review_tree" in reason


def test_a_tree_changed_after_the_reviews_blocks_consensus() -> None:
    both = [
        Outcome(
            name, ReviewState.CLEAN,
            document={"run_id": RUN.run_id, "review_tree": RUN.review_tree},
        )
        for name in ("CLAUDE", "CODEX")
    ]

    assert consensus_available(both, RUN, True)[0]

    available, reason = consensus_available(
        both, RUN, False, "review_tree: aaa -> bbb"
    )

    assert not available
    assert "changed after the round started" in reason
    assert "review_tree: aaa -> bbb" in reason


def test_consensus_needs_both_reviewers() -> None:
    one = [
        Outcome(
            "CLAUDE", ReviewState.CLEAN,
            document={"run_id": RUN.run_id, "review_tree": RUN.review_tree},
        )
    ]

    assert not consensus_available(one, RUN, True)[0]


def test_consensus_without_a_manifest_is_impossible() -> None:
    assert not consensus_available([], None, "")[0]


# --- workspace fingerprint ---------------------------------------------------


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()

    for args in (
        ["init", "-q"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "t"],
        # Determinismo entre plataformas: en Linux el defecto es `true` y git
        # deduce el modo del fichero EN DISCO, pisando el que fija el indice.
        # En Windows ya es `false`, que es por lo que en local nunca se vio.
        ["config", "core.fileMode", "false"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    (root / "tracked.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "base"], cwd=root, check=True, capture_output=True
    )

    return root


def _write(root: Path, name: str, content: str) -> None:
    (root / name).write_bytes(content.encode("utf-8"))


def _stage(root: Path, name: str) -> None:
    subprocess.run(["git", "add", name], cwd=root, check=True, capture_output=True)


def _status(root: Path) -> str:
    """Porcelain as the fingerprint sees it: `-uall`, so plain directories are
    expanded per file and only a repository boundary keeps a trailing slash."""
    return subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


# The HIGH Codex found in the first V2 round: the digest covered HEAD and the
# working tree but not the index, so on an `MM` path the staged blob could be
# replaced wholesale without moving the fingerprint -- while `git diff`, which
# is working tree *against the index*, showed something different to reviewers.


def test_a_staged_only_change_moves_the_fingerprint(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = review_v2.workspace_fingerprint(root)

    _write(root, "tracked.py", "x = 2\n")
    _stage(root, "tracked.py")

    assert _status(root).startswith("M ")
    assert review_v2.workspace_fingerprint(root) != before


def test_a_worktree_only_change_moves_the_fingerprint(tmp_path: Path) -> None:
    """Staged content held constant, working tree edited."""
    root = _repo(tmp_path)

    _write(root, "tracked.py", "x = 2\n")
    _stage(root, "tracked.py")
    staged_only = review_v2.workspace_fingerprint(root)

    _write(root, "tracked.py", "x = 3\n")

    assert _status(root).startswith("MM")
    assert review_v2.workspace_fingerprint(root) != staged_only


def test_an_mm_path_distinguishes_two_staged_blobs(tmp_path: Path) -> None:
    """staged A + working B versus staged C + working B."""
    root = _repo(tmp_path)
    prints = []

    for staged in ("staged-A\n", "staged-C-entirely-different\n"):
        _write(root, "tracked.py", staged)
        _stage(root, "tracked.py")
        _write(root, "tracked.py", "working-B\n")  # identical both times
        prints.append(review_v2.workspace_fingerprint(root))

    assert _status(root).startswith("MM")
    assert (root / "tracked.py").read_bytes() == b"working-B\n"
    assert prints[0] != prints[1]


def test_the_index_digest_carries_stage_mode_and_oid(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    _write(root, "tracked.py", "x = 2\n")
    _stage(root, "tracked.py")

    digests = review_v2.index_digests(root)
    stage, mode, oid = digests["tracked.py"].split(":")

    assert (stage, mode) == ("0", "100644")
    assert len(oid) == 40


def test_an_untracked_file_has_no_index_entry(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    _write(root, "loose.py", "y = 1\n")

    assert "loose.py" not in review_v2.index_digests(root)
    # It still moves the fingerprint, through its working-tree bytes.
    before = review_v2.workspace_fingerprint(root)
    _write(root, "loose.py", "y = 2\n")

    assert review_v2.workspace_fingerprint(root) != before


def test_the_fingerprint_uses_no_timestamps(tmp_path: Path) -> None:
    """Touching mtime must not move a content digest."""
    root = _repo(tmp_path)

    _write(root, "loose.py", "y = 1\n")
    before = review_v2.workspace_fingerprint(root)

    os.utime(root / "loose.py", (0, 0))
    os.utime(root / "tracked.py", (0, 0))

    assert review_v2.workspace_fingerprint(root) == before


# --- the state matrix --------------------------------------------------------

# One case per row of the specification, not one per known bug. Three defects
# reached production because 930 green tests asked about none of these states.


def _git_in(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )

    return result.stdout


def _nested_repo(root: Path, where: str) -> Path:
    inner = root / where
    inner.mkdir(parents=True)

    for args in (
        ("init", "-q"),
        ("config", "user.email", "t@example.com"),
        ("config", "user.name", "t"),
        ("config", "core.autocrlf", "false"),
        # Mismo motivo que `core.autocrlf`: determinismo entre plataformas.
        # En Linux el defecto es `true` y git deduce el modo del disco,
        # pisando el del indice (fallo exclusivo del CI).
        ("config", "core.fileMode", "false"),
    ):
        subprocess.run(["git", *args], cwd=inner, check=True, capture_output=True)

    return inner


def _moves(root: Path, mutate: object) -> bool:
    """True when `mutate` changes the fingerprint."""
    before = review_v2.workspace_fingerprint(root)
    mutate()  # type: ignore[operator]

    return review_v2.workspace_fingerprint(root) != before


# Rows 2-8, 12-13, 17, 20: ordinary states, one assertion each.
def test_matrix_of_ordinary_git_states(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    for name in ("del_staged.py", "del_unstaged.py", "ren_src.py", "mm.py"):
        _write(root, name, f"base {name}\n")

    _stage(root, ".")
    subprocess.run(["git", "commit", "-qm", "more"], cwd=root, check=True,
                   capture_output=True)

    cases: list[tuple[str, object]] = [
        ("modified unstaged", lambda: _write(root, "tracked.py", "x = 2\n")),
        ("modified staged", lambda: (_write(root, "mm.py", "s\n"),
                                     _stage(root, "mm.py"))),
        ("MM worktree half", lambda: _write(root, "mm.py", "w\n")),
        ("added staged", lambda: (_write(root, "added.py", "new\n"),
                                  _stage(root, "added.py"))),
        ("deleted staged", lambda: _git_in(root, "rm", "-q", "del_staged.py")),
        ("deleted unstaged", lambda: (root / "del_unstaged.py").unlink()),
        ("renamed", lambda: _git_in(root, "mv", "ren_src.py", "ren_dst.py")),
        ("untracked file", lambda: _write(root, "loose.py", "y\n")),
        ("untracked dir", lambda: (
            (root / "d").mkdir(), _write(root, "d/inside.py", "z\n"))),
        ("exotic names", lambda: [
            _write(root, name, "x\n")
            for name in ("con espacio.py", "café_ñ.py", "a[1].py")
        ]),
    ]

    for label, mutate in cases:
        assert _moves(root, mutate), f"{label} did not move the fingerprint"


def test_matrix_ignored_paths_never_move_the_fingerprint(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write(root, ".gitignore", "ignored.py\nbuild/\n")

    before = review_v2.workspace_fingerprint(root)

    _write(root, "ignored.py", "noise\n")
    (root / "build").mkdir()
    _write(root, "build/out.bin", "noise\n")

    assert review_v2.workspace_fingerprint(root) == before


def test_matrix_head_only_change(tmp_path: Path) -> None:
    """Row 22: identical working tree, different base commit."""
    root = _repo(tmp_path)
    _write(root, "loose.py", "y\n")
    before = review_v2.workspace_fingerprint(root)

    _write(root, "second.py", "s\n")
    _stage(root, "second.py")
    subprocess.run(["git", "commit", "-qm", "second"], cwd=root, check=True,
                   capture_output=True)

    assert review_v2.workspace_fingerprint(root) != before


def test_matrix_mode_change_moves_the_fingerprint(tmp_path: Path) -> None:
    """Row 9: same blob, different index mode."""
    root = _repo(tmp_path)
    _write(root, "tracked.py", "x = 2\n")
    _stage(root, "tracked.py")

    assert _moves(root, lambda: _git_in(root, "add", "--chmod=+x", "tracked.py"))
    assert "100755" in review_v2.index_digests(root)["tracked.py"]


def test_matrix_symlink_mode_moves_the_fingerprint(tmp_path: Path) -> None:
    """Row 10: a 120000 entry, created through plumbing so Windows can run it."""
    root = _repo(tmp_path)
    oid = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=root, input="target/path", capture_output=True, text=True, check=True,
    ).stdout.strip()

    assert _moves(
        root,
        lambda: _git_in(root, "update-index", "--cacheinfo",
                        f"120000,{oid},tracked.py"),
    )
    assert "120000" in review_v2.index_digests(root)["tracked.py"]


def test_matrix_conflict_records_all_three_stages(tmp_path: Path) -> None:
    """Row 11: stages 1, 2 and 3 all reach the digest."""
    root = _repo(tmp_path)
    _write(root, "c.py", "base\n")
    _stage(root, "c.py")
    subprocess.run(["git", "commit", "-qm", "c"], cwd=root, check=True,
                   capture_output=True)
    start = _git_in(root, "rev-parse", "--abbrev-ref", "HEAD").strip()

    _git_in(root, "checkout", "-qb", "other")
    _write(root, "c.py", "theirs\n")
    subprocess.run(["git", "commit", "-qam", "theirs"], cwd=root, check=True,
                   capture_output=True)
    _git_in(root, "checkout", "-q", start)
    _write(root, "c.py", "ours\n")
    subprocess.run(["git", "commit", "-qam", "ours"], cwd=root, check=True,
                   capture_output=True)
    _git_in(root, "merge", "other")

    assert _status(root).startswith("UU")

    stages = review_v2.index_digests(root)["c.py"].split("|")

    assert [s.split(":")[0] for s in stages] == ["1", "2", "3"]
    assert len({s.split(":")[2] for s in stages}) == 3
    assert review_v2.workspace_fingerprint(root)


# Rows 14-16: repository boundaries. These are the states git refuses to look
# inside, and the ones that hashed to a constant before (CLA-V2-02).


def test_matrix_nested_repo_tracked_change_moves_the_fingerprint(
    tmp_path: Path
) -> None:
    root = _repo(tmp_path)
    inner = _nested_repo(root, "vendor/inner")
    _write(inner, "code.py", "v1\n")
    subprocess.run(["git", "add", "-A"], cwd=inner, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "v1"], cwd=inner, check=True,
                   capture_output=True)

    assert "?? vendor/inner/" in _status(root)
    assert _moves(root, lambda: _write(inner, "code.py", "v2 entirely\n"))


def test_matrix_nested_repo_untracked_change_moves_the_fingerprint(
    tmp_path: Path
) -> None:
    root = _repo(tmp_path)
    inner = _nested_repo(root, "vendor/inner")
    _write(inner, "code.py", "v1\n")

    assert _moves(root, lambda: _write(inner, "brand_new.py", "hello\n"))


def test_matrix_nested_repo_ignored_file_does_not_move_the_fingerprint(
    tmp_path: Path
) -> None:
    """The inner repository's own ignore rules are respected, because its own
    git is what reports its state."""
    root = _repo(tmp_path)
    inner = _nested_repo(root, "vendor/inner")
    _write(inner, ".gitignore", "noise.log\n")
    before = review_v2.workspace_fingerprint(root)

    _write(inner, "noise.log", "ignored output\n")

    assert review_v2.workspace_fingerprint(root) == before


def test_matrix_inner_worktree_change_moves_the_fingerprint(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    added = subprocess.run(
        ["git", "worktree", "add", "-q", "sidewt", "HEAD"],
        cwd=root, capture_output=True, text=True, check=False,
    )

    if added.returncode != 0:
        pytest.skip(f"git worktree unavailable: {added.stderr.strip()}")

    assert "?? sidewt/" in _status(root)
    assert _moves(root, lambda: _write(root / "sidewt", "tracked.py", "changed\n"))


def _submodule(tmp_path: Path) -> tuple[Path, Path]:
    for holder in ("upstream_holder", "outer_holder"):
        (tmp_path / holder).mkdir()

    upstream = _repo(tmp_path / "upstream_holder")
    root = _repo(tmp_path / "outer_holder")
    added = subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "add", "-q",
         upstream.as_posix(), "sub"],
        cwd=root, capture_output=True, text=True, check=False,
    )

    if added.returncode != 0:
        pytest.skip(f"git submodule unavailable: {added.stderr.strip()}")

    return root, root / "sub"


def test_matrix_submodule_head_move_changes_the_fingerprint(tmp_path: Path) -> None:
    root, sub = _submodule(tmp_path)

    assert "160000" in review_v2.index_digests(root)["sub"]

    def advance() -> None:
        _write(sub, "new.py", "x\n")
        subprocess.run(["git", "add", "-A"], cwd=sub, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "advance"], cwd=sub, check=True,
                       capture_output=True)

    assert _moves(root, advance)


def test_matrix_submodule_dirty_worktree_changes_the_fingerprint(
    tmp_path: Path
) -> None:
    """A submodule must not be represented by its recorded commit alone."""
    root, sub = _submodule(tmp_path)

    assert _moves(root, lambda: _write(sub, "tracked.py", "locally dirty\n"))


def test_matrix_recursion_terminates_on_a_visited_tree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    added = subprocess.run(
        ["git", "worktree", "add", "-q", "sidewt", "HEAD"],
        cwd=root, capture_output=True, text=True, check=False,
    )

    if added.returncode != 0:
        pytest.skip("git worktree unavailable")

    # A worktree shares its git dir with the outer repo; the digest must still
    # terminate and stay deterministic.
    assert review_v2.workspace_fingerprint(root) == review_v2.workspace_fingerprint(
        root
    )


# Row 19 and the failure modes.


def test_matrix_thousands_of_paths_do_not_grow_argv(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "many").mkdir()

    for number in range(1200):
        _write(root, f"many/f{number:05d}.py", f"x = {number}\n")

    calls: list[int] = []
    real = review_v2.subprocess.run

    def spy(argv: object, **kwargs: object) -> object:
        assert isinstance(argv, list)
        calls.append(sum(len(str(a)) for a in argv))

        return real(argv, **kwargs)  # type: ignore[arg-type]

    review_v2.subprocess.run = spy  # type: ignore[assignment]

    try:
        digest = review_v2.workspace_fingerprint(root)
    finally:
        review_v2.subprocess.run = real  # type: ignore[assignment]

    assert digest
    assert len(review_v2.changed_entries(root)) >= 1200
    # 503 paths used to fit and 504 raised WinError 206. No command line here
    # may come anywhere near that, however many paths there are.
    assert max(calls) < 500, f"argv grew to {max(calls)} chars"


def test_matrix_a_spawn_failure_becomes_a_fingerprint_error(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    def explode(*args: object, **kwargs: object) -> object:
        raise OSError(206, "The filename or extension is too long")

    real = review_v2.subprocess.run
    review_v2.subprocess.run = explode  # type: ignore[assignment]

    try:
        with pytest.raises(review_v2.FingerprintError) as raised:
            review_v2.workspace_fingerprint(root)
    finally:
        review_v2.subprocess.run = real  # type: ignore[assignment]

    assert "could not run" in str(raised.value)


def test_matrix_a_nonzero_git_exit_becomes_a_fingerprint_error(
    tmp_path: Path
) -> None:
    with pytest.raises(review_v2.FingerprintError) as raised:
        review_v2.workspace_fingerprint(tmp_path / "not_a_repo")

    assert "could not run" in str(raised.value) or "failed" in str(raised.value)


def test_matrix_a_directory_never_becomes_absent(tmp_path: Path) -> None:
    """The invariant CLA-V2-02 broke: no entry may hash to a constant."""
    root = _repo(tmp_path)
    plain = root / "plain_dir"
    plain.mkdir()
    _write(root, "plain_dir/inside.py", "x\n")

    # git expands a plain untracked directory, so nothing is opaque here.
    entries = {path: code for code, path, _ in review_v2.changed_entries(root)}

    assert "plain_dir/inside.py" in entries
    assert "plain_dir/" not in entries

    # And a collapsed entry that is not a repository is refused, not guessed.
    with pytest.raises(review_v2.FingerprintError) as raised:
        review_v2._worktree_component(root, "??", "plain_dir/", "", set(), 0)

    assert "not a repository" in str(raised.value)


def test_matrix_an_unreadable_file_is_not_absent(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    def denied(self: object) -> bytes:
        raise PermissionError(13, "Permission denied")

    original = Path.read_bytes
    Path.read_bytes = denied  # type: ignore[assignment,method-assign]

    try:
        with pytest.raises(review_v2.FingerprintError) as raised:
            review_v2._worktree_component(root, " M", "tracked.py", "", set(), 0)
    finally:
        Path.read_bytes = original  # type: ignore[method-assign]

    assert "could not read" in str(raised.value)


def test_matrix_a_missing_file_is_absent_only_when_git_says_deleted(
    tmp_path: Path
) -> None:
    root = _repo(tmp_path)

    assert review_v2._worktree_component(
        root, " D", "gone.py", "", set(), 0
    ) == "absent"

    with pytest.raises(review_v2.FingerprintError) as raised:
        review_v2._worktree_component(root, " M", "gone.py", "", set(), 0)

    assert "not a deletion" in str(raised.value)


# --- the differential matrix -------------------------------------------------

# Every test above this point asks an existential question: "does this change
# move the digest?" That is the weaker property, and it is why 952 green tests
# were consistent with a HIGH. A rename does move the digest -- the destination
# is a new record -- while two *different* renames onto the same destination
# collided (CLA-V3-01).
#
# These ask the differential question instead: two states a reviewer can tell
# apart must not share a fingerprint. Each case is built to share as much as
# possible between A and B, so only the property under test separates them.


def _reset_hard(root: Path) -> None:
    subprocess.run(["git", "reset", "--hard", "-q"], cwd=root, check=True,
                   capture_output=True)
    subprocess.run(["git", "clean", "-qfd"], cwd=root, check=True,
                   capture_output=True)


def _assert_distinct(root: Path, states: list[tuple[str, object]]) -> dict[str, str]:
    """The general invariant of Phase B.

    Distinct reviewer-visible states must not collapse onto one fingerprint.
    This does not attempt to prove SHA-256 collision resistance; it proves that
    the serialization fed to the hash keeps these states apart.
    """
    seen: dict[str, str] = {}

    for label, build in states:
        build()  # type: ignore[operator]
        digest = review_v2.workspace_fingerprint(root)

        assert digest not in seen, (
            f"states {seen[digest]!r} and {label!r} collapse onto the same "
            f"fingerprint {digest[:16]}..."
        )
        seen[digest] = label

    return {label: digest for digest, label in seen.items()}


def _matrix_repo(tmp_path: Path) -> Path:
    """A base commit rich enough to build every differential pair from."""
    root = _repo(tmp_path)

    (root / "src").mkdir()
    (root / ".claude" / "reviews" / "runtime").mkdir(parents=True)
    _write(root, "src/money.py", "BALANCE = 1000\n")
    # Two tracked paths sharing one blob: the CLA-V3-01 precondition, which
    # holds in the real repository too (six files share the empty blob).
    _write(root, "keep_a", "")
    _write(root, "keep_b", "")
    _stage(root, ".")
    subprocess.run(["git", "commit", "-qm", "matrix base"], cwd=root, check=True,
                   capture_output=True)

    return root


# 1. Two renames onto the same destination, from sources sharing a blob.
def test_differential_two_renames_onto_one_destination(tmp_path: Path) -> None:
    root = _matrix_repo(tmp_path)

    def rename(source: str) -> object:
        def build() -> None:
            _reset_hard(root)
            _git_in(root, "mv", source, "moved")

        return build

    _assert_distinct(root, [("from keep_a", rename("keep_a")),
                            ("from keep_b", rename("keep_b"))])


# 2. A tracked path renamed into an excluded prefix must not look like a clean
#    tree. An exclusion may hide our own artefacts; it may not erase the fact
#    that a reviewable path left.
def test_differential_rename_into_an_excluded_prefix(tmp_path: Path) -> None:
    root = _matrix_repo(tmp_path)

    def clean() -> None:
        _reset_hard(root)

    def into_exclusion() -> None:
        _reset_hard(root)
        # `git clean -fd` removes the empty untracked directory, so recreate it.
        (root / ".claude" / "reviews" / "runtime").mkdir(parents=True, exist_ok=True)
        moved = _git_in(root, "mv", "src/money.py",
                        ".claude/reviews/runtime/stolen.py")

        assert not (root / "src" / "money.py").exists(), f"git mv failed: {moved}"

    _assert_distinct(root, [("clean", clean), ("moved into exclusion", into_exclusion)])


# 3. The reverse direction: a path arriving from an excluded prefix.
def test_differential_rename_out_of_an_excluded_prefix(tmp_path: Path) -> None:
    root = _matrix_repo(tmp_path)
    _write(root, ".claude/reviews/runtime/art.txt", "recovered\n")
    _git_in(root, "add", "-f", ".claude/reviews/runtime/art.txt")
    subprocess.run(["git", "commit", "-qm", "artefact"], cwd=root, check=True,
                   capture_output=True)

    def clean() -> None:
        _reset_hard(root)

    def out_of_exclusion() -> None:
        _reset_hard(root)
        _git_in(root, "mv", ".claude/reviews/runtime/art.txt", "src/recovered.py")

    _assert_distinct(root, [("clean", clean), ("moved out", out_of_exclusion)])


# 4. Copy detection. Measured on git 2.55: a copy is reported as a plain add,
#    even with status.renames=copies, so the protocol does not depend on it.
def test_differential_a_copy_is_reported_as_an_add(tmp_path: Path) -> None:
    root = _matrix_repo(tmp_path)
    _write(root, "src/copy.py", (root / "src" / "money.py").read_text())
    _stage(root, "src/copy.py")

    assert "A  src/copy.py" in _status(root)
    assert "C" not in {code[0] for code, _, _ in review_v2.changed_entries(root)}


# 5. A deletion and a rename into an excluded prefix both remove the path from
#    the reviewable tree, but they are different events.
def test_differential_deleted_versus_renamed_into_exclusion(tmp_path: Path) -> None:
    root = _matrix_repo(tmp_path)

    def deleted() -> None:
        _reset_hard(root)
        _git_in(root, "rm", "-q", "src/money.py")

    def hidden() -> None:
        _reset_hard(root)
        (root / ".claude" / "reviews" / "runtime").mkdir(parents=True, exist_ok=True)
        _git_in(root, "mv", "src/money.py", ".claude/reviews/runtime/stolen.py")

        assert not (root / "src" / "money.py").exists()

    _assert_distinct(root, [("deleted", deleted), ("renamed into exclusion", hidden)])


# 6. Gitlink: present, replaced by two different files, and removed.
def test_differential_gitlink_states(tmp_path: Path) -> None:
    root, sub = _submodule(tmp_path)

    def present() -> None:
        pass

    def replaced_with(text: str) -> object:
        def build() -> None:
            if sub.is_dir():
                shutil.rmtree(sub, ignore_errors=True)

            sub.write_text(text, encoding="utf-8")

        return build

    def removed() -> None:
        if sub.is_file():
            sub.unlink()
        elif sub.is_dir():
            shutil.rmtree(sub, ignore_errors=True)

    _assert_distinct(root, [
        ("submodule present", present),
        ("replaced by file A", replaced_with("contents A\n")),
        ("replaced by file B", replaced_with("something else entirely\n")),
        ("removed", removed),
    ])


# 7-11: one property each, everything else held constant.
def test_differential_index_mode(tmp_path: Path) -> None:
    root = _matrix_repo(tmp_path)
    _write(root, "src/money.py", "BALANCE = 2\n")
    _stage(root, "src/money.py")

    _assert_distinct(root, [
        ("100644", lambda: _git_in(root, "update-index", "--chmod=-x", "src/money.py")),
        ("100755", lambda: _git_in(root, "update-index", "--chmod=+x", "src/money.py")),
    ])


def test_differential_symlink_target(tmp_path: Path) -> None:
    root = _matrix_repo(tmp_path)

    def point_at(target: str) -> object:
        def build() -> None:
            oid = subprocess.run(
                ["git", "hash-object", "-w", "--stdin"], cwd=root, input=target,
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            _git_in(root, "update-index", "--cacheinfo",
                    f"120000,{oid},src/money.py")

        return build

    _assert_distinct(root, [("target A", point_at("some/where/A")),
                            ("target B", point_at("elsewhere/entirely/B"))])


def test_differential_conflict_stages(tmp_path: Path) -> None:
    """Same working tree bytes, different stage 3."""
    root = _matrix_repo(tmp_path)
    digests = []

    for theirs in ("theirs one\n", "theirs two, different\n"):
        _reset_hard(root)
        _git_in(root, "checkout", "-q", "-B", "base", "HEAD")
        _write(root, "c.py", "base\n")
        _stage(root, "c.py")
        subprocess.run(["git", "commit", "-qm", "c"], cwd=root, check=True,
                       capture_output=True)
        _git_in(root, "checkout", "-q", "-B", "other")
        _write(root, "c.py", theirs)
        subprocess.run(["git", "commit", "-qam", "theirs"], cwd=root, check=True,
                       capture_output=True)
        _git_in(root, "checkout", "-q", "base")
        _write(root, "c.py", "ours\n")
        subprocess.run(["git", "commit", "-qam", "ours"], cwd=root, check=True,
                       capture_output=True)
        _git_in(root, "merge", "other")
        _write(root, "c.py", "resolved identically\n")  # worktree held constant

        assert _status(root).startswith("UU")
        digests.append(review_v2.workspace_fingerprint(root))

    assert digests[0] != digests[1], "different stage 3 collapsed onto one digest"


def test_differential_staged_content_with_one_worktree(tmp_path: Path) -> None:
    root = _matrix_repo(tmp_path)

    def stage(text: str) -> object:
        def build() -> None:
            _write(root, "src/money.py", text)
            _stage(root, "src/money.py")
            _write(root, "src/money.py", "one worktree for both\n")

        return build

    _assert_distinct(root, [("staged A", stage("staged A\n")),
                            ("staged B", stage("staged B, different\n"))])


def test_differential_untracked_bytes(tmp_path: Path) -> None:
    root = _matrix_repo(tmp_path)

    _assert_distinct(root, [
        ("bytes A", lambda: _write(root, "loose.py", "A\n")),
        ("bytes B", lambda: _write(root, "loose.py", "B, different\n")),
    ])


# 12. Repository boundaries: same HEAD different tree, and same tree different HEAD.
def test_differential_nested_repo_same_head_different_worktree(
    tmp_path: Path
) -> None:
    root = _repo(tmp_path)
    inner = _nested_repo(root, "vendor/inner")
    _write(inner, "code.py", "committed\n")
    subprocess.run(["git", "add", "-A"], cwd=inner, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "v1"], cwd=inner, check=True,
                   capture_output=True)

    _assert_distinct(root, [
        ("dirty A", lambda: _write(inner, "code.py", "dirty A\n")),
        ("dirty B", lambda: _write(inner, "code.py", "dirty B, different\n")),
    ])


def test_differential_nested_repo_same_worktree_different_head(
    tmp_path: Path
) -> None:
    root = _repo(tmp_path)
    inner = _nested_repo(root, "vendor/inner")
    _write(inner, "code.py", "same bytes everywhere\n")
    subprocess.run(["git", "add", "-A"], cwd=inner, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "first"], cwd=inner, check=True,
                   capture_output=True)
    before = review_v2.workspace_fingerprint(root)

    # A second commit with no worktree change: HEAD moves, bytes do not.
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "second"],
                   cwd=inner, check=True, capture_output=True)

    assert (inner / "code.py").read_text() == "same bytes everywhere\n"
    assert review_v2.workspace_fingerprint(root) != before


# --- named regressions for the three adjudicated findings --------------------


def test_regression_cla_v3_01_rename_source_reaches_the_digest(
    tmp_path: Path
) -> None:
    """CLA-V3-01: the source token was consumed and thrown away."""
    root = _matrix_repo(tmp_path)
    _git_in(root, "mv", "keep_a", "moved")

    entries = review_v2.changed_entries(root)
    by_code = {code: (path, other) for code, path, other in entries}

    assert review_v2.RENAME_SOURCE in by_code, entries
    assert by_code[review_v2.RENAME_SOURCE] == ("keep_a", "moved")
    assert "keep_a" in review_v2.changed_paths(root)


def test_regression_adj_v3_a_departure_into_an_exclusion_is_recorded(
    tmp_path: Path
) -> None:
    """ADJ-V3-A: a tracked file left the reviewable tree with no trace."""
    root = _matrix_repo(tmp_path)
    clean = review_v2.workspace_fingerprint(root)

    _git_in(root, "mv", "src/money.py", ".claude/reviews/runtime/stolen.py")

    assert not (root / "src" / "money.py").exists()
    assert review_v2.changed_entries(root) == [
        (review_v2.RENAME_SOURCE, "src/money.py",
         ".claude/reviews/runtime/stolen.py")
    ]
    assert review_v2.workspace_fingerprint(root) != clean


def test_regression_the_exclusion_still_hides_our_own_artefacts(
    tmp_path: Path
) -> None:
    """The fix must not turn the exclusion off: writing runtime files is inert."""
    root = _matrix_repo(tmp_path)
    before = review_v2.workspace_fingerprint(root)

    (root / ".codex-tmp" / "run-x").mkdir(parents=True)
    _write(root, ".codex-tmp/run-x/pytest.log", "noise\n")
    _write(root, ".claude/reviews/runtime/codex.json", "{}\n")

    assert review_v2.workspace_fingerprint(root) == before


def test_regression_cla_v3_02_gitlink_states_are_distinguishable(
    tmp_path: Path
) -> None:
    """CLA-V3-02: every non-live shape returned the constant gitlink:absent."""
    root, sub = _submodule(tmp_path)
    index_entry = review_v2.index_digests(root)["sub"]

    assert review_v2._is_gitlink(index_entry)

    live = review_v2._worktree_component(root, "M ", "sub", index_entry, set(), 0)

    shutil.rmtree(sub, ignore_errors=True)
    sub.write_text("A\n", encoding="utf-8")
    file_a = review_v2._worktree_component(root, "T ", "sub", index_entry, set(), 0)

    sub.write_text("B, different\n", encoding="utf-8")
    file_b = review_v2._worktree_component(root, "T ", "sub", index_entry, set(), 0)

    sub.unlink()
    gone = review_v2._worktree_component(root, "D ", "sub", index_entry, set(), 0)

    assert len({live, file_a, file_b, gone}) == 4, (live, file_a, file_b, gone)
    assert gone == "gitlink:absent"


def test_regression_gitlink_routing_is_parsed_not_substring_matched() -> None:
    """A 160000 substring inside an object id must not route as a gitlink."""
    assert review_v2._is_gitlink("0:160000:aaaa")
    assert review_v2._is_gitlink("1:100644:aa|2:160000:bb")
    assert not review_v2._is_gitlink("0:100644:deadbeef160000cafe")
    assert not review_v2._is_gitlink("none")


def test_matrix_start_refuses_a_workspace_it_cannot_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half of ADJ-V2-05: --start died on a raw traceback."""
    monkeypatch.setattr(check_reviews_v2, "ROOT", tmp_path / "not_a_repo")
    monkeypatch.setattr(check_reviews_v2, "RUNTIME", tmp_path / "runtime")

    assert check_reviews_v2.main(["--start"]) == 2
    assert "cannot snapshot the workspace" in capsys.readouterr().out
    assert not (tmp_path / "runtime" / "run.json").exists()


def test_matrix_the_digest_is_versioned(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _write(root, "loose.py", "x\n")
    before = review_v2.workspace_fingerprint(root)

    original = review_v2.FINGERPRINT_VERSION
    review_v2.FINGERPRINT_VERSION = "fpv-other"

    try:
        assert review_v2.workspace_fingerprint(root) != before
    finally:
        review_v2.FINGERPRINT_VERSION = original


def test_matrix_paths_cannot_forge_a_record_boundary(tmp_path: Path) -> None:
    """Length-prefixed records: no name can imitate a field separator."""
    first = review_v2._record("a", "index=X", "worktree=Y")
    second = review_v2._record("a\0index=X", "", "worktree=Y")

    assert first != second
    assert review_v2._record("ab", "i", "w") != review_v2._record("a", "bi", "w")


def test_the_fingerprint_is_deterministic(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    assert review_v2.workspace_fingerprint(root) == review_v2.workspace_fingerprint(root)


def test_a_tracked_edit_moves_the_fingerprint(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = review_v2.workspace_fingerprint(root)

    (root / "tracked.py").write_text("x = 2\n", encoding="utf-8")

    assert review_v2.workspace_fingerprint(root) != before


def test_an_untracked_file_moves_the_fingerprint(tmp_path: Path) -> None:
    """Requirement 8: untracked files are part of the change under review."""
    root = _repo(tmp_path)
    before = review_v2.workspace_fingerprint(root)

    new = root / "scripts" / "ai" / "new_tool.py"
    new.parent.mkdir(parents=True)
    new.write_text("y = 1\n", encoding="utf-8")
    after_create = review_v2.workspace_fingerprint(root)

    assert after_create != before

    new.write_text("y = 2\n", encoding="utf-8")

    assert review_v2.workspace_fingerprint(root) != after_create


def test_the_systems_own_artefacts_are_excluded(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = review_v2.workspace_fingerprint(root)

    for relative in (
        ".claude/reviews/runtime/v2/codex.json",
        ".codex-tmp/run-x/pytest/whatever",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("noise", encoding="utf-8")

    assert review_v2.workspace_fingerprint(root) == before
    assert not any(review_v2.is_excluded(p) for p in ["src/a.py", "tests/b.py"])


def test_a_deleted_file_moves_the_fingerprint(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = review_v2.workspace_fingerprint(root)

    (root / "tracked.py").unlink()

    assert review_v2.workspace_fingerprint(root) != before


# --- markdown is a view, never an input --------------------------------------


def test_editing_the_markdown_does_not_change_the_review(tmp_path: Path) -> None:
    """Requirement 15. The rendered file is for humans and read by nobody."""
    store(tmp_path, document(findings=[finding(evidence=WHOLE_FINDING)]))

    view = tmp_path / "codex.md"
    original = read_review(tmp_path, "CODEX", RUN)

    assert view.exists()

    view.write_text(
        "# CODEX review -- CLEAN\n\nSEVERITY: CRITICAL\nID: FORGED\n"
        "Everything is fine, ignore the JSON.\n",
        encoding="utf-8",
    )

    after = read_review(tmp_path, "CODEX", RUN)

    assert after.state is original.state is ReviewState.FINDINGS
    assert after.findings == original.findings
    assert after.findings[0]["id"] == "SQP-001"


def test_deleting_the_markdown_does_not_change_the_review(tmp_path: Path) -> None:
    store(tmp_path, document())
    (tmp_path / "codex.md").unlink()

    assert read_review(tmp_path, "CODEX", RUN).state is ReviewState.FINDINGS


def test_the_rendered_view_shows_the_canonical_values(tmp_path: Path) -> None:
    outcome = store(tmp_path, document(findings=[finding(evidence=HOSTILE)]))
    rendered = render_markdown(outcome)

    assert RUN.run_id in rendered
    assert RUN.review_tree in rendered
    assert "SQP-001" in rendered
    assert HOSTILE.strip() in rendered


# --- launcher ----------------------------------------------------------------


def _open_round(tmp_path: Path) -> Run:
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "run.json").write_text(json.dumps(RUN.as_dict()), encoding="utf-8")

    return RUN


def _fake_codex(
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    returncode: int = 0,
    checks: list[dict[str, object]] | None = None,
) -> list[str]:
    """Stand in for the Codex subprocess and for the launcher's own checks.

    The checks are stubbed because running them for real here would run pytest
    inside pytest. `test_the_launcher_actually_runs_the_required_checks` covers
    the real execution against a throwaway repo.
    """
    prompts: list[str] = []

    def fake_run(*args: object, **kwargs: object) -> object:
        # Only the Codex launch is fed a prompt on stdin.
        if "input" in kwargs:
            prompts.append(str(kwargs["input"]))

        return subprocess.CompletedProcess(["codex"], returncode, stdout, "")

    monkeypatch.setattr(codex_review_v2, "codex_command", lambda: Path("codex"))
    monkeypatch.setattr(codex_review_v2.subprocess, "run", fake_run)
    monkeypatch.setattr(
        codex_review_v2,
        "run_checks",
        lambda root, interpreter: green_checks() if checks is None else checks,
    )

    return prompts


def test_the_launcher_hands_the_reviewer_the_round_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run = _open_round(tmp_path)
    prompts = _fake_codex(monkeypatch, json.dumps(document(verdict="CLEAN", findings=[])))

    assert codex_review_v2.main() == 0
    assert prompts, "main() never reached the launcher: this test proves nothing"
    assert run.run_id in prompts[0]
    assert run.review_tree in prompts[0]
    assert f'"schema_version": {SCHEMA_VERSION}' in prompts[0]


def test_the_launcher_records_a_findings_review(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _open_round(tmp_path)
    prompts = _fake_codex(monkeypatch, json.dumps(document()))

    assert codex_review_v2.main() == 0
    assert prompts

    outcome = read_review(tmp_path / "runtime", "CODEX", RUN)

    assert outcome.state is ReviewState.FINDINGS


def test_the_launcher_rejects_a_review_for_another_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _open_round(tmp_path)
    prompts = _fake_codex(monkeypatch, json.dumps(document(run=OTHER_RUN)))

    code = codex_review_v2.main()

    assert prompts
    assert code == codex_review_v2.EXIT_CODES[ReviewState.RUN_MISMATCH]


def test_the_launcher_refuses_without_an_open_round(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def must_not_run(*args: object, **kwargs: object) -> object:
        raise AssertionError("Codex must not be launched outside a round")

    monkeypatch.setattr(codex_review_v2.subprocess, "run", must_not_run)

    assert codex_review_v2.main() == 5


def test_a_nonzero_exit_is_an_execution_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _open_round(tmp_path)
    prompts = _fake_codex(monkeypatch, "", returncode=42)

    assert codex_review_v2.main() == 2
    assert prompts

    outcome = read_review(tmp_path / "runtime", "CODEX", RUN)

    assert outcome.state is ReviewState.EXECUTION_FAILED
    assert "42" in outcome.detail


def test_two_concurrent_launchers_do_not_share_a_scratch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Requirement 12: per-run scratch, and neither run prunes the other."""
    _open_round(tmp_path)
    prompts = _fake_codex(monkeypatch, json.dumps(document(verdict="CLEAN", findings=[])))

    assert codex_review_v2.main() == 0
    assert codex_review_v2.main() == 0
    assert len(prompts) == 2

    def scratch_of(prompt: str) -> str:
        line = next(row for row in prompt.splitlines() if "--basetemp=" in row)

        return line.split("--basetemp=", 1)[1].split("/pytest", 1)[0]

    first, second = scratch_of(prompts[0]), scratch_of(prompts[1])

    assert first != second, "two runs must not share a scratch path"
    # Neither reviewer is told about the other's scratch, so neither can write
    # into it, and pruning by name cannot reach a run in flight.
    assert second not in prompts[0]
    assert first not in prompts[1]


def test_no_launcher_test_can_reach_the_real_repository() -> None:
    """The autouse fixture is the mechanism; this proves it is wired in."""
    for module in (check_reviews_v2, codex_review_v2, codex_review):
        assert module.ROOT != REAL_ROOT, f"{module.__name__}.ROOT is the real repo"

    assert check_reviews_v2.RUNTIME != REAL_ROOT / ".claude" / "reviews" / "runtime"


# --- phase 0 and the gate ----------------------------------------------------


def test_phase_zero_mints_a_unique_round(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    runtime = tmp_path / "runtime"

    first = review_v2.start_run(runtime, root)
    second = review_v2.start_run(runtime, root)

    assert first.run_id != second.run_id
    assert first.review_tree == second.review_tree
    assert review_v2.load_run(runtime) == second


def test_the_gate_blocks_until_both_reviewers_ran(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(check_reviews_v2, "ROOT", root)
    monkeypatch.setattr(check_reviews_v2, "RUNTIME", runtime)

    run = review_v2.start_run(runtime, root)

    assert check_reviews_v2.main([]) == 1
    assert "CONSENSUS: BLOCKED" in capsys.readouterr().out

    for name in ("CLAUDE", "CODEX"):
        store(runtime, document(reviewer=name, run=run), run=run)

    assert check_reviews_v2.main([]) == 0
    assert "CONSENSUS: AVAILABLE" in capsys.readouterr().out


def test_the_gate_blocks_when_the_tree_moves_mid_round(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Requirement 10: the reviews describe a state that no longer exists."""
    root = _repo(tmp_path)
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(check_reviews_v2, "ROOT", root)
    monkeypatch.setattr(check_reviews_v2, "RUNTIME", runtime)

    run = review_v2.start_run(runtime, root)

    for name in ("CLAUDE", "CODEX"):
        store(runtime, document(reviewer=name, run=run), run=run)

    assert check_reviews_v2.main([]) == 0

    (root / "tracked.py").write_text("x = 999\n", encoding="utf-8")

    assert check_reviews_v2.main([]) == 1
    assert "changed after the round started" in capsys.readouterr().out


def test_reset_discards_the_round(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = _repo(tmp_path)
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(check_reviews_v2, "ROOT", root)
    monkeypatch.setattr(check_reviews_v2, "RUNTIME", runtime)

    review_v2.start_run(runtime, root)
    store(runtime, document(), run=review_v2.load_run(runtime) or RUN)

    assert check_reviews_v2.main(["--reset"]) == 0
    assert not runtime.exists()
    assert review_v2.load_run(runtime) is None
