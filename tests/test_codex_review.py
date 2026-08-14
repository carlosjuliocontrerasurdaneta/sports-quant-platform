import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


AI_DIR = Path(__file__).resolve().parents[1] / "scripts" / "ai"

if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

import check_reviews  # noqa: E402
import codex_review  # noqa: E402
import review_protocol  # noqa: E402

from review_protocol import (  # noqa: E402
    ReviewOutcome,
    ReviewStatus,
    read_review,
    write_review,
)


valid_review = review_protocol.valid_review


COMPACT_FINDING = """\
ID: SQP-001
REVIEWER: CODEX
SEVERITY: HIGH
CATEGORY: functional bug
FILE: src/sqp/example.py
LINES: 10-12
CLAIM: The calculation uses the wrong input.
EVIDENCE: The function passes home odds twice.
IMPACT: Away probabilities are incorrect.
PROPOSED_FIX: Pass away odds as the second argument.
VERIFICATION: Add a regression test with asymmetric odds.
CONFIDENCE: HIGH"""


# Layout copied from .claude/reviews/CROSS_REVIEW.md: blank lines between
# fields and the markdown-escaped proposed-fix label.
CONTRACT_FINDING = r"""ID: SQP-001

REVIEWER: CODEX

SEVERITY: HIGH

CATEGORY: functional bug

FILE: src/sqp/example.py

LINES: 10-12



CLAIM: The calculation uses the wrong input.



EVIDENCE: The function passes home odds twice.



IMPACT: Away probabilities are incorrect.



PROPOSED\_FIX: Pass away odds as the second argument.



VERIFICATION: Add a regression test with asymmetric odds.



CONFIDENCE: HIGH"""


FINDINGS = (COMPACT_FINDING, CONTRACT_FINDING)

# A PASS the pipeline may accept: it states the work behind the verdict.
ATTESTED_PASS = """PASS

VERIFICATION: pytest -q -> 724 passed; ruff check src scripts tests -> clean"""


# --- contract parsing --------------------------------------------------------


@pytest.mark.parametrize("finding", FINDINGS)
def test_valid_single_finding(finding: str) -> None:
    assert valid_review(finding)


@pytest.mark.parametrize("finding", FINDINGS)
def test_valid_multiple_findings(finding: str) -> None:
    second = finding.replace("SQP-001", "SQP-002").replace(
        "SEVERITY: HIGH", "SEVERITY: LOW"
    )

    assert valid_review(f"{finding}\n\n{second}")


@pytest.mark.parametrize("finding", FINDINGS)
def test_missing_field(finding: str) -> None:
    assert not valid_review(finding.replace("CATEGORY: functional bug\n", ""))


@pytest.mark.parametrize("finding", FINDINGS)
def test_duplicated_field(finding: str) -> None:
    review = finding.replace(
        "SEVERITY: HIGH\n", "SEVERITY: HIGH\nSEVERITY: HIGH\n"
    )

    assert not valid_review(review)


@pytest.mark.parametrize("finding", FINDINGS)
def test_empty_field(finding: str) -> None:
    review = finding.replace(
        "CLAIM: The calculation uses the wrong input.", "CLAIM:"
    )

    assert not valid_review(review)


@pytest.mark.parametrize("finding", FINDINGS)
def test_wrong_reviewer(finding: str) -> None:
    assert not valid_review(finding.replace("REVIEWER: CODEX", "REVIEWER: CLAUDE"))


@pytest.mark.parametrize("finding", FINDINGS)
def test_invalid_severity(finding: str) -> None:
    assert not valid_review(finding.replace("SEVERITY: HIGH", "SEVERITY: INFO"))


@pytest.mark.parametrize("finding", FINDINGS)
def test_malformed_second_finding_after_valid_first(finding: str) -> None:
    malformed = finding.replace(
        "EVIDENCE: The function passes home odds twice.\n", ""
    )

    assert not valid_review(f"{finding}\n\n{malformed}")


@pytest.mark.parametrize("finding", FINDINGS)
def test_pass_alongside_a_finding_is_invalid(finding: str) -> None:
    assert not valid_review(f"PASS\n\n{finding}")


@pytest.mark.parametrize("finding", FINDINGS)
def test_prose_line_inside_finding_is_invalid(finding: str) -> None:
    review = finding.replace(
        "IMPACT: Away probabilities are incorrect.", "Here is some commentary."
    )

    assert not valid_review(review)


def test_field_order_must_follow_the_contract() -> None:
    review = CONTRACT_FINDING.replace(
        "SEVERITY: HIGH\n\nCATEGORY: functional bug",
        "CATEGORY: functional bug\n\nSEVERITY: HIGH",
    )

    assert not valid_review(review)


def test_escaped_label_is_normalized() -> None:
    assert valid_review(COMPACT_FINDING.replace("PROPOSED_FIX:", r"PROPOSED\_FIX:"))


def test_empty_review_is_invalid() -> None:
    assert not valid_review("")
    assert not valid_review("\n\n   \n")


# --- CLA-02: the contract never required one physical line per field ---------


def test_multiline_evidence_is_accepted() -> None:
    review = COMPACT_FINDING.replace(
        "EVIDENCE: The function passes home odds twice.",
        "EVIDENCE: The function passes home odds twice:\n"
        "    p_home = implied(home)\n"
        "    p_away = implied(home)",
    )

    findings, error = review_protocol.parse_findings(review)

    assert not error
    assert "p_away = implied(home)" in findings[0]["EVIDENCE"]


def test_findings_separated_by_a_horizontal_rule_are_accepted() -> None:
    second = COMPACT_FINDING.replace("SQP-001", "SQP-002")

    assert valid_review(f"{COMPACT_FINDING}\n\n---\n\n{second}")


def test_heading_before_findings_is_accepted() -> None:
    assert valid_review(f"# Findings\n\n{COMPACT_FINDING}")


# --- CLA-01: layout outside a field, content inside one ----------------------

# A heading, rule or fence used to end the field it appeared in, so the next
# line landed "outside a contract field" and the whole review was discarded.
# Reviewers paste diffs and source as EVIDENCE, so this destroyed exactly the
# reviews that showed their work -- while leaving a PASS untouched.


def _with_evidence(body: str) -> str:
    return COMPACT_FINDING.replace(
        "EVIDENCE: The function passes home odds twice.",
        f"EVIDENCE: {body}",
    )


@pytest.mark.parametrize(
    ("label", "body", "expected"),
    [
        (
            "comment",
            "reproduced by:\n# --- probe -----\np = implied(home)",
            "# --- probe -----",
        ),
        (
            "rule",
            "before:\n---\nafter",
            "---",
        ),
        (
            "fence",
            "```python\np_away = implied(home)\n```",
            "```python",
        ),
    ],
)
def test_structural_line_inside_evidence_is_kept(
    label: str, body: str, expected: str
) -> None:
    findings, error = review_protocol.parse_findings(_with_evidence(body))

    assert not error, error
    assert expected in findings[0]["EVIDENCE"]


# The concrete review that motivated CLA-01: the reviewer pasted the working
# tree's own test file, whose comment banner ended EVIDENCE and made the next
# line unexpected text. Read from disk so the regression tracks the real file.
ODDS_TEST_SOURCE = Path(__file__).with_name("test_odds.py").read_text(encoding="utf-8")


def test_real_test_file_pasted_as_evidence_is_accepted() -> None:
    review = _with_evidence(f"the suite covering the guard:\n{ODDS_TEST_SOURCE}")

    findings, error = review_protocol.parse_findings(review)

    assert not error, error

    evidence = findings[0]["EVIDENCE"]

    assert "# --- invariante de valor finito" in evidence
    assert 'NAN, INF = float("nan"), float("inf")' in evidence
    assert findings[0]["IMPACT"] == "Away probabilities are incorrect."


# SQP-CR-001, found by Codex in a real run: keying on the label alone repeated
# CLA-01 one level down. A reviewer quoting a contract label inside EVIDENCE --
# pasting a diff, an error message, another finding -- opened a second field and
# lost the whole review to INVALID_OUTPUT.
def test_contract_labels_quoted_inside_evidence_stay_evidence() -> None:
    quoted = (
        "the parser mis-reads pasted output such as:\n"
        "FILE: generated.py\n"
        "CATEGORY: fake\n"
        "SEVERITY: CRITICAL\n"
        "ID: NOT-A-FINDING\n"
        "REVIEWER: NOBODY\n"
        "CONFIDENCE: none\n"
        "end of paste"
    )

    findings, error = review_protocol.parse_findings(_with_evidence(quoted))

    assert not error, error
    assert len(findings) == 1

    finding = findings[0]
    evidence = finding["EVIDENCE"]

    for line in ("FILE: generated.py", "CATEGORY: fake", "ID: NOT-A-FINDING"):
        assert line in evidence

    # The real fields kept their own values; none was overwritten by the paste.
    assert finding["ID"] == "SQP-001"
    assert finding["FILE"] == "src/sqp/example.py"
    assert finding["CATEGORY"] == "functional bug"
    assert finding["SEVERITY"] == "HIGH"
    assert finding["REVIEWER"] == "CODEX"
    assert finding["CONFIDENCE"] == "HIGH"
    assert finding["IMPACT"] == "Away probabilities are incorrect."


# CLA-A1: the contract used to offer "alter or indent its tail" as the escape
# from the paste boundary. Indenting does nothing -- parse_field_line strips the
# line before matching -- so the document described a mitigation that does not
# exist. This ties the text to the property instead of trusting either alone.
CONTRACT_TEXT = (
    Path(__file__).resolve().parents[1] / ".claude" / "reviews" / "CROSS_REVIEW.md"
).read_text(encoding="utf-8")


def test_indenting_a_label_is_not_an_escape() -> None:
    """The property itself: indentation changes nothing."""
    pasted = COMPACT_FINDING.replace(
        "IMPACT: Away probabilities are incorrect.", "IMPACT: PASTED"
    )
    indented = "\n".join(f"    {line}" for line in pasted.splitlines())

    flat, flat_error = review_protocol.parse_findings(
        _with_evidence(f"paste:\n{pasted}")
    )
    deep, deep_error = review_protocol.parse_findings(
        _with_evidence(f"paste:\n{indented}")
    )

    assert not flat_error and not deep_error
    assert flat == deep
    assert deep[0]["IMPACT"] == "PASTED"


# CLA-B2: the document claimed only a whole-contract paste was ambiguous. One
# quoted line matching the next expected field is enough, and the two are the
# same text -- so the contract must say so rather than the parser pretend.
def test_one_quoted_line_is_already_the_boundary() -> None:
    hijacked, error = review_protocol.parse_findings(
        _with_evidence("my evidence:\nIMPACT: HIJACKED\nstill my evidence")
    )

    assert not error
    assert hijacked[0]["EVIDENCE"] == "my evidence:"
    assert hijacked[0]["IMPACT"].startswith("HIJACKED")


def test_the_contract_states_the_single_line_boundary() -> None:
    assert "A single quoted line" in CONTRACT_TEXT
    assert "limit of the format" in CONTRACT_TEXT


def test_the_contract_does_not_promise_indenting_as_an_escape() -> None:
    """The document may only describe mitigations that work."""
    assert "alter or indent" not in CONTRACT_TEXT
    assert "Indenting does not help." in CONTRACT_TEXT

    # Whatever the document does offer must not rest on indentation.
    for line in CONTRACT_TEXT.splitlines():
        if "indent" in line.lower():
            assert "does not help" in line or "exactly as" in line, line


def test_the_escape_the_contract_does_offer_actually_works() -> None:
    """Altering the label text is the documented escape; it must hold."""
    pasted = COMPACT_FINDING.replace("IMPACT:", "IMPACT(quoted):").replace(
        "PROPOSED_FIX:", "PROPOSED_FIX(quoted):"
    )

    findings, error = review_protocol.parse_findings(
        _with_evidence(f"paste:\n{pasted}")
    )

    assert not error, error
    assert findings[0]["IMPACT"] == "Away probabilities are incorrect."
    assert "IMPACT(quoted):" in findings[0]["EVIDENCE"]


def test_a_verbatim_contract_paste_is_the_known_boundary() -> None:
    """Pinned limitation, not an oversight.

    The rule above cannot separate a pasted contract from the real
    continuation: the paste's `IMPACT:` line IS the label the parser is waiting
    for. Resolving it would mean ignoring a label once EVIDENCE quotes earlier
    ones -- which is precisely the case the test above requires to work. The
    two are indistinguishable without an explicit delimiter in the contract.

    The cost is real and worth stating: for this one input shape the failure
    turned quiet. It used to be INVALID_OUTPUT; now the finding parses with the
    paste's values in the fields after EVIDENCE.
    """
    pasted = COMPACT_FINDING.replace(
        "IMPACT: Away probabilities are incorrect.", "IMPACT: PASTED"
    )

    findings, error = review_protocol.parse_findings(
        _with_evidence(f"the reviewer pasted a whole contract:\n{pasted}")
    )

    assert not error
    assert len(findings) == 1
    # The paste's tail supplied the real fields. This is the boundary.
    assert findings[0]["IMPACT"] == "PASTED"
    # Everything before the hijack point is still held as evidence.
    assert "ID: SQP-001" in findings[0]["EVIDENCE"]
    assert "CLAIM: The calculation uses the wrong input." in findings[0]["EVIDENCE"]


def test_out_of_order_labels_are_still_rejected() -> None:
    """The fix must not turn a malformed finding into a valid one."""
    swapped = COMPACT_FINDING.replace(
        "SEVERITY: HIGH\nCATEGORY: functional bug",
        "CATEGORY: functional bug\nSEVERITY: HIGH",
    )

    assert not valid_review(swapped)


# The documented cost of the rule above: after the twelfth field a separator is
# indistinguishable from content, so it joins that field. Pinned because it is a
# trade, not an oversight -- the findings still parse, which is what matters.
def test_rule_after_the_last_field_joins_it() -> None:
    second = COMPACT_FINDING.replace("SQP-001", "SQP-002")

    findings, error = review_protocol.parse_findings(
        f"{COMPACT_FINDING}\n\n---\n\n{second}"
    )

    assert not error, error
    assert len(findings) == 2
    assert findings[0]["CONFIDENCE"] == "HIGH\n---"
    assert findings[1]["CONFIDENCE"] == "HIGH"


# --- ADJ-09: PASS alone is not evidence that a review happened ---------------


def test_bare_pass_is_rejected() -> None:
    for text in ("PASS", "\n PASS \n"):
        status, _, detail = review_protocol.parse_review_body(text, "CODEX")

        assert status is ReviewStatus.INVALID_OUTPUT
        assert "VERIFICATION" in detail


def test_attested_pass_is_clean() -> None:
    status, findings, detail = review_protocol.parse_review_body(
        ATTESTED_PASS, "CODEX"
    )

    assert status is ReviewStatus.CLEAN
    assert findings == ()
    assert "724 passed" in detail


# CLA-A3: the mirror of SQP-CR-001. A reviewer pastes the commands it ran, and
# that output routinely quotes contract labels; treating them as structure
# killed the body as INVALID_OUTPUT.

QUOTED_LABELS = (
    "SEVERITY: HIGH",
    "FILE: src/sqp/markets/odds.py",
    "ID: SQP-001",
    "CATEGORY: functional bug",
    "CONFIDENCE: HIGH",
)


@pytest.mark.parametrize("verdict", ["PASS", "EXECUTION_FAILED"])
def test_quoted_labels_inside_verification_stay_content(verdict: str) -> None:
    quoted = "\n".join(QUOTED_LABELS)
    body = (
        f"{verdict}\n\nVERIFICATION: reran the suite; the failing finding read:\n"
        f"{quoted}\nend of quote."
    )

    status, findings, detail = review_protocol.parse_review_body(body, "CODEX")

    assert status is not ReviewStatus.INVALID_OUTPUT
    assert findings == ()

    for line in QUOTED_LABELS:
        assert line in detail


def test_a_pass_quoting_labels_is_still_clean() -> None:
    body = (
        "PASS\n\nVERIFICATION: pytest -q -> 817 passed. The finding I checked "
        "and dismissed read:\nSEVERITY: HIGH\nFILE: src/sqp/markets/odds.py"
    )

    status, _, _ = review_protocol.parse_review_body(body, "CODEX")

    assert status is ReviewStatus.CLEAN


def test_a_label_before_verification_opens_is_still_rejected() -> None:
    """The guard that keeps a verdict from smuggling findings must survive."""
    for verdict in ("PASS", "EXECUTION_FAILED"):
        status, _, detail = review_protocol.parse_review_body(
            f"{verdict}\n\nSEVERITY: HIGH\n\nVERIFICATION: pytest -q -> 817 passed",
            "CODEX",
        )

        assert status is ReviewStatus.INVALID_OUTPUT
        assert "may not carry finding fields" in detail


# ADJ-C1: making the value unconditional went one step too far. A PASS trailed
# by a complete finding was absorbed whole and returned CLEAN, where it used to
# be INVALID_OUTPUT -- a malformed body resolving *upward*, which the module
# forbids. Only EXECUTION_FAILED may be self-assigned, because it is monotonic
# downward.

CRITICAL_FINDING = """ID: X-1
REVIEWER: CODEX
SEVERITY: CRITICAL
CATEGORY: data loss
FILE: src/sqp/markets/odds.py
LINES: 1-40
CLAIM: the conversion silently drops stakes.
EVIDENCE: reproduced with a probe.
IMPACT: money is lost.
PROPOSED_FIX: guard the conversion.
VERIFICATION: pytest -q -> 833 passed
CONFIDENCE: HIGH"""


def test_a_pass_carrying_a_complete_finding_is_invalid() -> None:
    """The exact ADJ-C1 body: PASS + VERIFICATION + a full CRITICAL finding."""
    body = (
        "PASS\n\nVERIFICATION: I ran the gates and they were green.\n"
        f"{CRITICAL_FINDING}"
    )

    status, findings, detail = review_protocol.parse_review_body(body, "CODEX")
    outcome = ReviewOutcome("CODEX", status, detail, findings)

    assert status is ReviewStatus.INVALID_OUTPUT
    assert status is not ReviewStatus.CLEAN
    assert not outcome.is_clean
    assert not outcome.executed
    assert not review_protocol.valid_review(body)
    assert "may not carry a complete finding" in detail


def test_the_full_finding_test_is_exact_not_a_keyword_scan() -> None:
    """Eleven of twelve labels, or the right labels out of order, are prose."""
    eleven = "\n".join(CRITICAL_FINDING.splitlines()[:-1])
    shuffled = CRITICAL_FINDING.replace(
        "ID: X-1\nREVIEWER: CODEX", "REVIEWER: CODEX\nID: X-1"
    )

    assert review_protocol.carries_full_finding(CRITICAL_FINDING)
    assert not review_protocol.carries_full_finding(eleven)
    assert not review_protocol.carries_full_finding(shuffled)
    assert not review_protocol.carries_full_finding("SEVERITY: HIGH\nFILE: a.py")


# CLA-C2: the twelve empty labels are the contract's own skeleton -- the list
# this document and the launcher's prompt hand every reviewer. Quoting it
# carries no claim and was being punished as a smuggled finding.

SKELETON = "\n".join(f"{field}:" for field in review_protocol.REVIEW_FIELDS)


def test_the_empty_skeleton_is_not_a_finding() -> None:
    assert not review_protocol.carries_full_finding(SKELETON)
    assert not review_protocol.carries_full_finding(CONTRACT_TEXT)
    assert not review_protocol.carries_full_finding(codex_review.PROMPT_TEMPLATE)


def test_a_pass_quoting_the_contract_skeleton_is_clean() -> None:
    body = (
        "PASS\n\nVERIFICATION: pytest -q -> 839 passed. The contract asks for:\n"
        f"{SKELETON}\nI found nothing to report."
    )

    status, _, _ = review_protocol.parse_review_body(body, "CODEX")

    assert status is ReviewStatus.CLEAN


# The exemption is all-or-nothing on purpose: per-field relaxation would let a
# populated CRITICAL finding through by blanking one label, reopening ADJ-C1.
@pytest.mark.parametrize("blanked", ["ID: X-1", "SEVERITY: CRITICAL", "IMPACT: money is lost."])
def test_blanking_one_label_does_not_smuggle_a_finding(blanked: str) -> None:
    label = blanked.split(":", 1)[0]
    body = (
        "PASS\n\nVERIFICATION: gates green.\n"
        f"{CRITICAL_FINDING.replace(blanked, label + ':')}"
    )

    status, _, _ = review_protocol.parse_review_body(body, "CODEX")

    assert status is ReviewStatus.INVALID_OUTPUT


def test_a_blocked_verdict_keeps_its_diagnostic() -> None:
    """EXECUTION_FAILED already blocks consensus; rejecting it loses the why."""
    body = f"EXECUTION_FAILED\n\nVERIFICATION: nothing ran.\n{CRITICAL_FINDING}"

    status, _, detail = review_protocol.parse_review_body(body, "CODEX")

    assert status is ReviewStatus.EXECUTION_FAILED
    assert status not in review_protocol.EXECUTED
    assert "nothing ran." in detail


def test_quoting_labels_cannot_manufacture_findings() -> None:
    """A verdict body never becomes FINDINGS, however many labels it quotes."""
    body = f"PASS\n\nVERIFICATION: I ran the gates. Quoted:\n{COMPACT_FINDING}"

    status, findings, _ = review_protocol.parse_review_body(body, "CODEX")

    assert status is not ReviewStatus.FINDINGS
    assert findings == ()


def test_pass_with_empty_verification_is_rejected() -> None:
    status, _, _ = review_protocol.parse_review_body("PASS\n\nVERIFICATION:", "CODEX")

    assert status is ReviewStatus.INVALID_OUTPUT


# --- ADJ-01: a stated verification is not a performed one --------------------

# Verbatim from the run that exposed this: Codex exited 0, wrote an accurate
# VERIFICATION saying its interpreter and test runner were unavailable and its
# fallbacks denied, and the gate printed CONSENSUS: AVAILABLE anyway.
CODEX_UNVERIFIABLE_PASS = """PASS

VERIFICATION: Independently inspected `AGENTS.md`, `.claude/reviews/CROSS_REVIEW.md`,
`git status --short`, `git diff --stat`, `git diff`, and all changed files. No
substantive defect was identified. Automated validation could not run: `pytest`
and `python` were unavailable, while `py -m pytest -q`, `py -m ruff check src
scripts tests`, and `py -m mypy src` were denied access when launching the
installed Python 3.11 executable."""


def test_the_observed_codex_pass_is_not_clean() -> None:
    status, findings, detail = review_protocol.parse_review_body(
        CODEX_UNVERIFIABLE_PASS, "CODEX"
    )

    assert status is ReviewStatus.EXECUTION_FAILED
    assert status is not ReviewStatus.CLEAN
    assert findings == ()
    assert "unavailable" in detail
    assert not valid_review(CODEX_UNVERIFIABLE_PASS)


def test_the_observed_codex_pass_blocks_consensus(tmp_path: Path) -> None:
    outcomes = [
        read_review(_write(tmp_path, CODEX_UNVERIFIABLE_PASS), "CODEX"),
        ReviewOutcome("CLAUDE", ReviewStatus.FINDINGS),
    ]

    assert outcomes[0].status is ReviewStatus.EXECUTION_FAILED
    assert not outcomes[0].executed
    assert not outcomes[0].is_clean
    assert not review_protocol.consensus_available(outcomes)


@pytest.mark.parametrize("marker", review_protocol.UNVERIFIABLE_MARKERS)
def test_every_declared_marker_downgrades_a_pass(marker: str) -> None:
    review = f"PASS\n\nVERIFICATION: I attempted the suite; {marker.upper()}."

    status, _, _ = review_protocol.parse_review_body(review, "CODEX")

    assert status is ReviewStatus.EXECUTION_FAILED


def test_marker_split_across_lines_is_still_caught() -> None:
    review = "PASS\n\nVERIFICATION: the test runner was\nunavailable in the sandbox"

    status, _, _ = review_protocol.parse_review_body(review, "CODEX")

    assert status is ReviewStatus.EXECUTION_FAILED


def test_the_longest_matching_marker_is_reported() -> None:
    assert review_protocol.unverifiable_marker("mypy: permission denied") == (
        "permission denied"
    )


def test_a_verification_that_ran_is_still_clean() -> None:
    status, _, _ = review_protocol.parse_review_body(ATTESTED_PASS, "CODEX")

    assert status is ReviewStatus.CLEAN
    assert review_protocol.unverifiable_marker(ATTESTED_PASS) is None


def test_findings_are_not_downgraded_by_the_words_they_report() -> None:
    """A defect report may legitimately quote 'permission denied'."""
    review = COMPACT_FINDING.replace(
        "EVIDENCE: The function passes home odds twice.",
        "EVIDENCE: the provider call fails with 'permission denied'.",
    )

    status, findings, _ = review_protocol.parse_review_body(review, "CODEX")

    assert status is ReviewStatus.FINDINGS
    assert len(findings) == 1


# --- the reviewer may disclaim its run, never attest it ----------------------

# Observed end to end: Codex could not reach the interpreter, said so under an
# EXECUTION_FAILED heading, and the parser filed it as INVALID_OUTPUT -- the
# same state as garbage, so the honest report told the operator nothing.
CODEX_BLOCKED_BODY = """EXECUTION_FAILED

VERIFICATION: Static inspection completed for `git status`, `git diff`, changed
source files, review-protocol scripts, and relevant tests. All required quality
gates failed to launch because the mandated interpreter path was not recognized:

- `"...python.exe" -m pytest -q` -> interpreter not found
- `"...python.exe" -m ruff check src scripts tests` -> interpreter not found
- `"...python.exe" -m mypy src` -> interpreter not found

No verified clean verdict can be issued."""


def test_the_observed_blocked_body_is_execution_failed() -> None:
    status, findings, detail = review_protocol.parse_review_body(
        CODEX_BLOCKED_BODY, "CODEX"
    )

    assert status is ReviewStatus.EXECUTION_FAILED
    assert status is not ReviewStatus.INVALID_OUTPUT
    assert findings == ()
    assert "interpreter not found" in detail


def test_a_blocked_body_never_counts_as_a_review(tmp_path: Path) -> None:
    outcome = read_review(_write(tmp_path, CODEX_BLOCKED_BODY), "CODEX")

    assert outcome.status is ReviewStatus.EXECUTION_FAILED
    assert not outcome.executed
    assert not outcome.is_clean
    assert not review_protocol.consensus_available(
        [ReviewOutcome("CLAUDE", ReviewStatus.FINDINGS), outcome]
    )
    assert "interpreter not found" in str(outcome.provenance["failure"])  # type: ignore[index]


def test_a_bare_blocked_verdict_is_rejected() -> None:
    status, _, detail = review_protocol.parse_review_body("EXECUTION_FAILED", "CODEX")

    assert status is ReviewStatus.INVALID_OUTPUT
    assert "VERIFICATION" in detail


def test_a_blocked_verdict_may_not_smuggle_findings() -> None:
    status, _, _ = review_protocol.parse_review_body(
        f"EXECUTION_FAILED\n\n{COMPACT_FINDING}", "CODEX"
    )

    assert status is ReviewStatus.INVALID_OUTPUT


def test_the_reviewer_can_only_declare_itself_downward() -> None:
    """The one self-assigned verdict must be a non-review state."""
    status, _, _ = review_protocol.parse_review_body(
        f"{review_protocol.BLOCKED_VERDICT}\n\nVERIFICATION: nothing ran.", "CODEX"
    )

    assert status not in review_protocol.EXECUTED

    for forged in ("CLEAN", "FINDINGS"):
        assert (
            review_protocol.parse_review_body(
                f"{forged}\n\nVERIFICATION: pytest -q -> 792 passed", "CODEX"
            )[0]
            is ReviewStatus.INVALID_OUTPUT
        )


def test_the_launcher_reports_a_blocked_body_as_execution_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, output, _ = _run_main(monkeypatch, tmp_path, 0, CODEX_BLOCKED_BODY)

    assert code == 2
    assert read_review(output, "CODEX").status is ReviewStatus.EXECUTION_FAILED


# --- review states -----------------------------------------------------------


def _write(tmp_path: Path, body: str, **kwargs: object) -> Path:
    path = tmp_path / "codex-review.md"
    defaults: dict[str, object] = {
        "launched": True,
        "exit_code": 0,
        "command": "codex exec -",
        "duration_s": 1.0,
    }
    defaults.update(kwargs)
    write_review(path, "CODEX", body, **defaults)  # type: ignore[arg-type]

    return path


def test_state_findings_after_successful_execution(tmp_path: Path) -> None:
    outcome = read_review(_write(tmp_path, COMPACT_FINDING), "CODEX")

    assert outcome.status is ReviewStatus.FINDINGS
    assert outcome.executed
    assert len(outcome.findings) == 1


def test_state_clean_after_successful_execution(tmp_path: Path) -> None:
    outcome = read_review(_write(tmp_path, ATTESTED_PASS), "CODEX")

    assert outcome.status is ReviewStatus.CLEAN
    assert outcome.executed


def test_state_missing_file(tmp_path: Path) -> None:
    outcome = read_review(tmp_path / "absent.md", "CODEX")

    assert outcome.status is ReviewStatus.MISSING
    assert not outcome.executed


def test_state_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "codex-review.md"
    path.write_text("   \n\n", encoding="utf-8")

    outcome = read_review(path, "CODEX")

    assert outcome.status is ReviewStatus.EMPTY
    assert not outcome.executed


def test_state_reviewer_never_launched(tmp_path: Path) -> None:
    path = _write(tmp_path, "", launched=False, exit_code=None, failure="no CLI")

    outcome = read_review(path, "CODEX")

    assert outcome.status is ReviewStatus.EXECUTION_FAILED
    assert not outcome.executed


def test_state_nonzero_exit(tmp_path: Path) -> None:
    path = _write(tmp_path, "PASS", exit_code=7, failure="sandbox denied execution")

    outcome = read_review(path, "CODEX")

    assert outcome.status is ReviewStatus.EXECUTION_FAILED
    assert not outcome.executed


def test_state_invalid_output(tmp_path: Path) -> None:
    outcome = read_review(_write(tmp_path, "looks fine to me"), "CODEX")

    assert outcome.status is ReviewStatus.INVALID_OUTPUT
    assert not outcome.executed


# The exact ADJ-09 laundering path: text that says PASS but that no launcher
# ever produced -- a stale file, a hand-written one, an agent that never ran.
def test_unstamped_pass_file_is_not_a_review(tmp_path: Path) -> None:
    path = tmp_path / "codex-review.md"
    path.write_text("PASS\n", encoding="utf-8")

    outcome = read_review(path, "CODEX")

    assert outcome.status is ReviewStatus.NOT_EXECUTED
    assert not outcome.executed
    assert not outcome.is_clean


def test_unstamped_attested_pass_is_still_not_a_review(tmp_path: Path) -> None:
    path = tmp_path / "codex-review.md"
    path.write_text(ATTESTED_PASS, encoding="utf-8")

    assert read_review(path, "CODEX").status is ReviewStatus.NOT_EXECUTED


def test_stamp_for_another_reviewer_does_not_count(tmp_path: Path) -> None:
    path = _write(tmp_path, ATTESTED_PASS)

    assert read_review(path, "CLAUDE").status is ReviewStatus.NOT_EXECUTED


def test_tampered_header_cannot_declare_a_bad_body_clean(tmp_path: Path) -> None:
    path = _write(tmp_path, "looks fine to me")
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            f'"{ReviewStatus.INVALID_OUTPUT.value}"',
            f'"{ReviewStatus.CLEAN.value}"',
        ),
        encoding="utf-8",
    )

    assert read_review(path, "CODEX").status is ReviewStatus.INVALID_OUTPUT


# --- CLA-02: the failure text must survive the round trip --------------------

# write_review accepted a `failure` argument and dropped it, so read_review's
# provenance.get("failure") was always None and the fallback stringified a list:
# the operator saw `['[EXECUTION_FAILED] Unable to start...']` with the stderr
# that explained the failure cut off after the first line.

MULTILINE_FAILURE = (
    "Codex exited with code 42. STDERR:\n"
    "Traceback (most recent call last):\n"
    '  File "codex", line 1, in <module>\n'
    "RuntimeError: sandbox refused to spawn the interpreter"
)


def test_failure_text_round_trips_intact(tmp_path: Path) -> None:
    path = _write(tmp_path, "", exit_code=42, failure=MULTILINE_FAILURE)

    outcome = read_review(path, "CODEX")

    assert outcome.status is ReviewStatus.EXECUTION_FAILED
    assert outcome.detail == MULTILINE_FAILURE


# CLA-A2: raw stderr goes verbatim into a header framed as an HTML comment, so
# a failure containing `-->` closed it early. The tail leaked into the body, the
# JSON stopped parsing, and a file stamped EXECUTION_FAILED was re-read as
# NOT_EXECUTED with the diagnostic thrown away. The fixture above passed only
# because it happens to contain no `-->`.

ARROW_FAILURE = "Codex exited 1. STDERR: parser said a --> b, not a -> b"

COMMENT_FAILURE = "Codex exited 1. STDERR: unexpected <!-- in template output"

REALISTIC_TRACEBACK = """Codex exited with code 1. STDERR:
Traceback (most recent call last):
  File "C:\\repo\\tool.py", line 12, in <module>
    render(node)  # arrow --> in a comment
  File "C:\\repo\\tool.py", line 7, in render
    raise RuntimeError("<!-- unterminated --> marker")
RuntimeError: <!-- unterminated --> marker"""


@pytest.mark.parametrize(
    "failure",
    [ARROW_FAILURE, COMMENT_FAILURE, REALISTIC_TRACEBACK, MULTILINE_FAILURE],
    ids=["arrow", "comment-open", "traceback", "multiline"],
)
def test_arbitrary_failure_text_survives_the_round_trip(
    tmp_path: Path, failure: str
) -> None:
    path = _write(tmp_path, "", exit_code=42, failure=failure)

    outcome = read_review(path, "CODEX")

    assert outcome.status is ReviewStatus.EXECUTION_FAILED
    assert outcome.status is not ReviewStatus.NOT_EXECUTED
    assert outcome.detail == failure
    assert outcome.provenance is not None
    assert outcome.provenance["failure"] == failure


def test_the_header_cannot_contain_its_own_terminator(tmp_path: Path) -> None:
    """The payload is made unrepresentable, not merely escaped."""
    path = _write(tmp_path, "", exit_code=42, failure=REALISTIC_TRACEBACK)
    text = path.read_text(encoding="utf-8")

    framed, separator, _ = text.partition(review_protocol.PROVENANCE_CLOSE)

    assert separator == review_protocol.PROVENANCE_CLOSE

    # The opener itself is `<!--`; the invariant is about the JSON payload.
    payload = framed[len(review_protocol.PROVENANCE_OPEN):]

    assert "--" not in payload
    assert review_protocol.JSON_DASH in payload
    assert json.loads(payload)["failure"] == REALISTIC_TRACEBACK


def test_a_tampered_header_still_cannot_lift_the_status(tmp_path: Path) -> None:
    """Escaping must not turn the header into something worth trusting."""
    path = _write(tmp_path, "looks fine to me", exit_code=0)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            f'"{ReviewStatus.INVALID_OUTPUT.value}"', f'"{ReviewStatus.CLEAN.value}"'
        ),
        encoding="utf-8",
    )

    assert read_review(path, "CODEX").status is ReviewStatus.INVALID_OUTPUT


def test_failure_detail_is_not_a_stringified_list(tmp_path: Path) -> None:
    path = _write(tmp_path, "", launched=False, exit_code=None, failure="no CLI")

    detail = read_review(path, "CODEX").detail

    assert detail == "no CLI"
    assert not detail.startswith("[")


def test_failure_is_persisted_in_the_header(tmp_path: Path) -> None:
    path = _write(tmp_path, "", exit_code=42, failure=MULTILINE_FAILURE)

    assert read_review(path, "CODEX").provenance["failure"] == MULTILINE_FAILURE  # type: ignore[index]


def test_unverifiable_pass_records_why_it_failed(tmp_path: Path) -> None:
    """The ADJ-01 path reaches EXECUTION_FAILED with no `failure` argument."""
    detail = read_review(_write(tmp_path, CODEX_UNVERIFIABLE_PASS), "CODEX").detail

    assert "unavailable" in detail
    assert "VERIFICATION" in detail


# --- consensus ---------------------------------------------------------------


def _outcome(status: ReviewStatus, reviewer: str = "CODEX") -> ReviewOutcome:
    return ReviewOutcome(reviewer, status)


def test_consensus_needs_both_reviewers() -> None:
    both = [_outcome(ReviewStatus.CLEAN, "CLAUDE"), _outcome(ReviewStatus.FINDINGS)]

    assert review_protocol.consensus_available(both)


@pytest.mark.parametrize(
    "absent",
    [
        ReviewStatus.MISSING,
        ReviewStatus.EMPTY,
        ReviewStatus.NOT_EXECUTED,
        ReviewStatus.EXECUTION_FAILED,
        ReviewStatus.INVALID_OUTPUT,
    ],
)
def test_no_consensus_when_only_one_reviewer_ran(absent: ReviewStatus) -> None:
    outcomes = [_outcome(ReviewStatus.CLEAN, "CLAUDE"), _outcome(absent)]

    assert not review_protocol.consensus_available(outcomes)


def test_single_reviewer_alone_is_not_consensus() -> None:
    alone = [_outcome(ReviewStatus.CLEAN, "CLAUDE")]

    assert not review_protocol.consensus_available(alone)


# --- the gate ----------------------------------------------------------------


def _runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(check_reviews, "RUNTIME", tmp_path)

    return tmp_path


def test_gate_passes_when_both_reviewers_ran(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    write_review(
        runtime / "claude-review.md", "CLAUDE",
        COMPACT_FINDING.replace("REVIEWER: CODEX", "REVIEWER: CLAUDE"),
        launched=True, exit_code=0, command="agent", duration_s=1.0,
    )
    write_review(
        runtime / "codex-review.md", "CODEX", ATTESTED_PASS,
        launched=True, exit_code=0, command="codex", duration_s=1.0,
    )

    assert check_reviews.main([]) == 0
    assert "CONSENSUS: AVAILABLE" in capsys.readouterr().out


def test_gate_blocks_adjudication_when_a_review_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    write_review(
        runtime / "claude-review.md", "CLAUDE", ATTESTED_PASS.replace("PASS", "PASS"),
        launched=True, exit_code=0, command="agent", duration_s=1.0,
    )

    assert check_reviews.main([]) == 1

    out = capsys.readouterr().out

    assert "CONSENSUS: BLOCKED" in out
    assert "MISSING" in out
    assert "CODEX" in out


def test_gate_blocks_on_an_unstamped_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    write_review(
        runtime / "claude-review.md", "CLAUDE", ATTESTED_PASS,
        launched=True, exit_code=0, command="agent", duration_s=1.0,
    )
    (runtime / "codex-review.md").write_text("PASS\n", encoding="utf-8")

    assert check_reviews.main([]) == 1
    assert "NOT_EXECUTED" in capsys.readouterr().out


def test_gate_blocks_on_the_observed_codex_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """End to end, the run that printed CONSENSUS: AVAILABLE must now block."""
    runtime = _runtime(monkeypatch, tmp_path)
    write_review(
        runtime / "claude-review.md", "CLAUDE",
        COMPACT_FINDING.replace("REVIEWER: CODEX", "REVIEWER: CLAUDE"),
        launched=True, exit_code=0, command="agent", duration_s=1.0,
    )
    write_review(
        runtime / "codex-review.md", "CODEX", CODEX_UNVERIFIABLE_PASS,
        launched=True, exit_code=0, command="codex", duration_s=1.0,
    )

    assert check_reviews.main([]) == 1

    out = capsys.readouterr().out

    assert "CONSENSUS: BLOCKED" in out
    assert "EXECUTION_FAILED" in out
    assert "CONSENSUS: AVAILABLE" not in out


def test_gate_reset_clears_stale_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = _runtime(monkeypatch, tmp_path)
    (runtime / "codex-review.md").write_text("PASS\n", encoding="utf-8")

    assert check_reviews.main(["--reset"]) == 0
    assert not list(runtime.glob("*.md"))
    assert check_reviews.main([]) == 1


# --- launcher ----------------------------------------------------------------

# Characters a Windows cp1252 console cannot encode: they used to crash the
# script after a valid review had already been saved (ADJ-07).
UNENCODABLE_DIAGNOSTIC = "Codex diagnostics: ✅ → \x8d"


def _cp1252_stream() -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252")


def _console_text(stream: io.TextIOWrapper) -> str:
    stream.flush()

    return stream.buffer.getvalue().decode("cp1252")  # type: ignore[attr-defined]


#: The prompt of the most recent _run_main() launch, or None if none happened.
LAST_PROMPT: list[str] = []


def _run_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    returncode: int,
    stdout: str,
) -> tuple[int, Path, io.TextIOWrapper]:
    """Run main() against a fake Codex on a cp1252 console.

    ROOT is pinned to tmp_path. Without it these tests ran the launcher's
    scratch handling against the real repository -- deleting `.codex-tmp`,
    including the basetemp of the very pytest session executing them (CLA-B1).

    The launch is asserted, not assumed. When main() aborted early these tests
    stayed green while never reaching build_prompt(): the ones asserting a
    non-zero exit passed for the wrong reason, and three of them are the
    ADJ-01/ADJ-09 regressions.

    The console is patched here, not in a fixture, because pytest reinstalls
    its own sys.stdout when the call phase starts.
    """
    output = tmp_path / "codex-review.md"
    console = _cp1252_stream()
    LAST_PROMPT.clear()

    def fake_run(*args: object, **kwargs: object) -> object:
        LAST_PROMPT.append(str(kwargs["input"]))

        return subprocess.CompletedProcess(
            ["codex"], returncode, stdout, UNENCODABLE_DIAGNOSTIC
        )

    monkeypatch.setattr(codex_review, "ROOT", tmp_path)
    monkeypatch.setattr(codex_review, "OUTPUT", output)
    monkeypatch.setattr(codex_review, "codex_command", lambda: Path("codex"))
    monkeypatch.setattr(codex_review.subprocess, "run", fake_run)
    monkeypatch.setattr(codex_review.sys, "stdout", console)
    monkeypatch.setattr(codex_review.sys, "stderr", console)

    code = codex_review.main()

    assert LAST_PROMPT, "main() never reached the launch: this test proves nothing"
    assert codex_review.INTERPRETER_PLACEHOLDER not in LAST_PROMPT[0]

    return code, output, console


def test_safe_print_replaces_unencodable_characters() -> None:
    stream = _cp1252_stream()

    review_protocol.safe_print(UNENCODABLE_DIAGNOSTIC, stream)

    assert "Codex diagnostics:" in _console_text(stream)


def test_valid_review_survives_unencodable_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, output, console = _run_main(monkeypatch, tmp_path, 0, CONTRACT_FINDING)

    assert code == 0
    assert read_review(output, "CODEX").status is ReviewStatus.FINDINGS
    assert "Codex diagnostic output:" in _console_text(console)


def test_codex_nonzero_exit_stays_nonzero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, output, _ = _run_main(monkeypatch, tmp_path, 42, "")

    assert code != 0
    assert read_review(output, "CODEX").status is ReviewStatus.EXECUTION_FAILED


def test_invalid_review_is_still_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, output, _ = _run_main(monkeypatch, tmp_path, 0, "not a review")

    assert code == 3
    assert read_review(output, "CODEX").status is ReviewStatus.INVALID_OUTPUT


def test_launcher_rejects_a_bare_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The observed ADJ-09 incident, end to end: Codex exits 0 saying PASS
    after every verification command it attempted failed inside its sandbox."""
    code, output, _ = _run_main(monkeypatch, tmp_path, 0, "PASS")

    assert code != 0

    outcome = read_review(output, "CODEX")

    assert outcome.status is ReviewStatus.INVALID_OUTPUT
    assert not outcome.executed
    assert not outcome.is_clean


def test_launcher_rejects_a_pass_that_could_not_verify(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Codex exits 0 with the PASS it actually produced; the run is not clean."""
    code, output, _ = _run_main(monkeypatch, tmp_path, 0, CODEX_UNVERIFIABLE_PASS)

    assert code != 0

    outcome = read_review(output, "CODEX")

    assert outcome.status is ReviewStatus.EXECUTION_FAILED
    assert not outcome.executed
    assert not outcome.is_clean


def test_launcher_accepts_an_attested_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, output, _ = _run_main(monkeypatch, tmp_path, 0, ATTESTED_PASS)

    assert code == 0
    assert read_review(output, "CODEX").status is ReviewStatus.CLEAN


# --- interpreter discovery ---------------------------------------------------

# Inside the Codex sandbox `python`, `pytest`, `ruff` and `mypy` do not resolve
# through PATH and `py.exe` hits the WindowsApps stub and is denied, so the
# reviewer reported it could verify nothing. The launcher's own interpreter
# works, so the prompt names it instead of letting the reviewer guess.

GATE_TAILS = (
    "-m pytest -q -p no:cacheprovider --basetemp=.codex-tmp/pytest",
    "-m ruff check src scripts tests",
    "-m mypy src --cache-dir=.codex-tmp/mypy",
)

SPACED_PATHS = (
    r"C:\Program Files\Python 3.14\python.exe",
    "/opt/my tools/venv/bin/python",
)


# A -- the prompt actually sent to Codex carries this process's interpreter.
def test_the_prompt_sent_to_codex_names_the_running_interpreter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, str] = {}

    def fake_run(*args: object, **kwargs: object) -> object:
        captured["input"] = str(kwargs["input"])

        return subprocess.CompletedProcess(["codex"], 0, ATTESTED_PASS, "")

    # ROOT first: main() prunes under ROOT/.codex-tmp, and the real repo's is
    # where the launcher puts pytest's basetemp and TEMP (CLA-C1).
    monkeypatch.setattr(codex_review, "ROOT", tmp_path)
    monkeypatch.setattr(codex_review, "OUTPUT", tmp_path / "codex-review.md")
    monkeypatch.setattr(codex_review, "codex_command", lambda: Path("codex"))
    monkeypatch.setattr(codex_review.subprocess, "run", fake_run)

    assert codex_review.main() == 0

    interpreter = codex_review.resolve_interpreter()

    assert interpreter == Path(os.path.abspath(sys.executable))
    assert f'"{interpreter}"' in captured["input"]
    assert codex_review.INTERPRETER_PLACEHOLDER not in captured["input"]


def test_the_interpreter_is_normalized_without_following_symlinks() -> None:
    """A venv's python is a link to the base one, which lacks its packages."""
    messy = os.path.join(os.path.dirname(sys.executable), ".", os.path.basename(sys.executable))

    assert codex_review.resolve_interpreter(messy) == Path(os.path.abspath(sys.executable))


# PowerShell reads a quoted path as a string, not a command, so Windows gates
# must carry the call operator. POSIX shells have no `&` of that kind.
def _expected(interpreter: Path, windows: bool) -> tuple[str, ...]:
    prefix = "& " if windows else ""

    return tuple(f'{prefix}"{interpreter}" {tail}' for tail in GATE_TAILS)


# B -- a path with spaces survives as one argument, on either shell.
@pytest.mark.parametrize("windows", [True, False])
@pytest.mark.parametrize("executable", SPACED_PATHS)
def test_a_path_with_spaces_is_quoted(executable: str, windows: bool) -> None:
    interpreter = Path(executable)
    prompt = codex_review.build_prompt(interpreter, windows=windows)
    commands = codex_review.verification_commands(interpreter, windows=windows)

    # Path renders separators for the host OS, so compare against its own text.
    rendered = str(interpreter)

    assert " " in rendered
    assert commands == _expected(interpreter, windows)

    for command in commands:
        assert command in prompt
        # The interpreter stays one argument: nothing follows it before -m.
        assert command.split('"')[2].strip().startswith("-m ")


# The literal Windows PowerShell lines the reviewer is told to run.
def test_the_windows_prompt_uses_the_call_operator() -> None:
    interpreter = codex_review.resolve_interpreter()
    prompt = codex_review.build_prompt(interpreter, windows=True)

    assert f'& "{interpreter}" -m pytest -q' in prompt
    assert f'& "{interpreter}" -m ruff check src scripts tests' in prompt
    assert f'& "{interpreter}" -m mypy src' in prompt
    assert "call operator" in prompt


# --- workspace-local temp and cache ------------------------------------------

# Observed inside the sandbox: pytest's tmp_path fixtures died on
# `%TEMP%\pytest-of-Richard` with WinError 5, and mypy's sqlite metastore could
# not open its database under `.mypy_cache`, surfacing as INTERNAL ERROR. Both
# were writes outside a directory the current sandbox session owns.


def test_pytest_and_mypy_are_pinned_to_the_workspace_scratch() -> None:
    interpreter = codex_review.resolve_interpreter()
    pytest_gate, ruff_gate, mypy_gate = codex_review.verification_commands(interpreter)

    assert f"--basetemp={codex_review.SCRATCH}/pytest" in pytest_gate
    assert f"--cache-dir={codex_review.SCRATCH}/mypy" in mypy_gate
    # .pytest_cache outlives a sandbox session and its write ACE names a stale
    # principal, so pytest warned on every run. It has no cache to redirect.
    assert "-p no:cacheprovider" in pytest_gate
    # Ruff was never affected; it keeps its default cache.
    assert "--cache-dir" not in ruff_gate
    assert codex_review.SCRATCH not in ruff_gate


@pytest.mark.parametrize("windows", [True, False])
def test_the_scratch_paths_are_relative_to_the_workspace(windows: bool) -> None:
    """An absolute host path would point outside the sandbox's writable tree."""
    for command in codex_review.verification_commands(Path("py"), windows=windows):
        for flag in ("--basetemp=", "--cache-dir="):
            if flag in command:
                value = command.split(flag, 1)[1].split()[0]

                assert value.startswith(f"{codex_review.SCRATCH}/")
                assert not os.path.isabs(value)


def test_the_windows_setup_redirects_temp_with_powershell_syntax() -> None:
    setup = codex_review.scratch_setup(windows=True)

    assert "$env:TEMP" in setup
    assert "$env:TMP" in setup
    assert "New-Item -ItemType Directory -Force" in setup
    assert "export " not in setup
    assert setup in codex_review.build_prompt(Path("py"), windows=True)


def test_the_posix_setup_redirects_tmpdir_with_posix_syntax() -> None:
    setup = codex_review.scratch_setup(windows=False)

    assert "export TMPDIR=" in setup
    assert f"mkdir -p {codex_review.SCRATCH}/pytest" in setup
    assert "$env:" not in setup
    assert "New-Item" not in setup
    assert setup in codex_review.build_prompt(Path("py"), windows=False)


def test_the_setup_creates_every_directory_the_gates_use() -> None:
    for windows in (True, False):
        setup = codex_review.scratch_setup(windows)
        separator = "\\" if windows else "/"

        for leaf in ("pytest", "mypy"):
            assert f"{codex_review.SCRATCH}{separator}{leaf}" in setup


# --- CLA-B1: a scratch path per run, never reused ----------------------------

# Reusing one path was the mistake. The sandbox bakes an ephemeral per-session
# principal into a directory's ACL as it creates it, and the launcher provably
# cannot delete what the sandbox made -- WinError 5 on the reviewer's own pytest
# basetemp. Deleting first therefore made a *successful* review guarantee the
# next one aborted. A fresh path makes staleness unrepresentable instead.


# CLA-C1: one main() call site patched OUTPUT but not ROOT, so prune_scratch
# ran against the real repository -- the directory the launcher itself uses for
# pytest's basetemp and TEMP. A convention gets forgotten; this checks it.
def test_no_test_calls_main_without_pinning_root() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    bodies = re.split(r"\ndef (test_[a-z0-9_]+)", source)
    offenders = []

    for name, body in zip(bodies[1::2], bodies[2::2]):
        if "codex_review.main()" not in body:
            continue
        if '"ROOT"' in body or "_run_main(" in body or "_unremovable(" in body:
            continue

        offenders.append(name)

    assert not offenders, (
        f"these tests run main() against the real repository: {offenders}. "
        'Add monkeypatch.setattr(codex_review, "ROOT", tmp_path).'
    )


# ADJ-N3: deleting every sibling reintroduced the cross-run interference that
# per-run paths exist to remove -- a second launcher wiped the TEMP and mypy
# cache of a review in flight.
def test_pruning_spares_a_run_in_flight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(codex_review, "ROOT", tmp_path)

    in_flight = tmp_path / codex_review.new_scratch()
    in_flight.mkdir(parents=True)
    ancient = tmp_path / codex_review.SCRATCH / "run-20200101T000000-deadbeef"
    ancient.mkdir(parents=True)
    os.utime(ancient, (0, 0))

    codex_review.prune_scratch(codex_review.new_scratch())

    assert in_flight.exists(), "a concurrent reviewer's scratch was deleted"
    assert not ancient.exists(), "an old run should still be cleaned up"


def test_pruning_only_touches_directories_it_could_have_created(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(codex_review, "ROOT", tmp_path)

    foreign = tmp_path / codex_review.SCRATCH / "someone-elses-data"
    foreign.mkdir(parents=True)
    os.utime(foreign, (0, 0))

    codex_review.prune_scratch(codex_review.new_scratch())

    assert foreign.exists()


def test_every_run_gets_its_own_scratch_path() -> None:
    paths = {codex_review.new_scratch() for _ in range(50)}

    assert len(paths) == 50

    for path in paths:
        assert path.startswith(f"{codex_review.SCRATCH}/run-")
        assert not os.path.isabs(path)


def test_the_run_scratch_reaches_every_consumer() -> None:
    scratch = codex_review.new_scratch()
    interpreter = codex_review.resolve_interpreter()
    prompt = codex_review.build_prompt(interpreter, windows=True, scratch=scratch)
    native = scratch.replace("/", "\\")

    # pytest basetemp, mypy cache, TEMP/TMP and the prompt: all the same path.
    assert f"--basetemp={scratch}/pytest" in prompt
    assert f"--cache-dir={scratch}/mypy" in prompt
    assert f'$env:TEMP = (Resolve-Path "{native}").Path' in prompt
    assert "$env:TMP  = $env:TEMP" in prompt
    assert codex_review.SCRATCH + "/pytest" not in prompt

    posix = codex_review.build_prompt(interpreter, windows=False, scratch=scratch)

    assert f"--basetemp={scratch}/pytest" in posix
    assert f'export TMPDIR="$(cd {scratch} && pwd)"' in posix


def _unremovable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """An earlier run's scratch that rmtree cannot delete, deterministically."""
    monkeypatch.setattr(codex_review, "ROOT", tmp_path)
    monkeypatch.setattr(codex_review.shutil, "rmtree", lambda *a, **k: None)

    stale = tmp_path / codex_review.SCRATCH / "run-20260101T000000-deadbeef"
    (stale / "pytest").mkdir(parents=True)
    (stale / "pytest" / "held.db").write_text("locked", encoding="utf-8")

    return stale


def test_pruning_never_raises_on_a_tree_it_cannot_remove(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stale = _unremovable(monkeypatch, tmp_path)

    codex_review.prune_scratch(codex_review.new_scratch())

    assert stale.exists()


def test_pruning_keeps_this_run_and_survives_an_absent_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(codex_review, "ROOT", tmp_path)

    codex_review.prune_scratch(codex_review.new_scratch())  # no parent yet

    keep = codex_review.new_scratch()
    (tmp_path / keep).mkdir(parents=True)
    old = tmp_path / codex_review.SCRATCH / "run-20260101T000000-deadbeef"
    old.mkdir(parents=True)
    os.utime(old, (0, 0))

    codex_review.prune_scratch(keep)

    assert (tmp_path / keep).exists()
    assert not old.exists()


def test_an_unremovable_old_scratch_cannot_block_a_new_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The exact CLA-B1 regression: the previous design aborted here."""
    stale = _unremovable(monkeypatch, tmp_path)
    monkeypatch.setattr(codex_review, "OUTPUT", tmp_path / "codex-review.md")
    monkeypatch.setattr(codex_review, "codex_command", lambda: Path("codex"))

    launched: list[str] = []

    def fake_run(*args: object, **kwargs: object) -> object:
        launched.append(str(kwargs["input"]))

        return subprocess.CompletedProcess(["codex"], 0, ATTESTED_PASS, "")

    monkeypatch.setattr(codex_review.subprocess, "run", fake_run)

    assert codex_review.main() == 0
    assert launched, "the launcher must reach Codex despite the stale tree"
    assert stale.exists(), "cleanup is best-effort, not a precondition"
    # The prompt names a fresh run, never the tree that could not be removed.
    assert stale.name not in launched[0]


def test_the_launcher_never_touches_the_real_repository_scratch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Pruning must stay inside the ROOT under test."""
    removed: list[str] = []
    monkeypatch.setattr(codex_review, "ROOT", tmp_path)
    monkeypatch.setattr(
        codex_review.shutil, "rmtree", lambda p, **k: removed.append(str(p))
    )

    old = tmp_path / codex_review.SCRATCH / "run-old"
    old.mkdir(parents=True)
    os.utime(old, (0, 0))
    codex_review.prune_scratch(codex_review.new_scratch())

    assert removed
    for path in removed:
        assert str(tmp_path) in path


def test_the_posix_prompt_has_no_powershell_call_operator() -> None:
    interpreter = codex_review.resolve_interpreter()
    prompt = codex_review.build_prompt(interpreter, windows=False)

    for command in codex_review.verification_commands(interpreter, windows=False):
        assert command in prompt
        assert not command.startswith("&")

    assert f'& "{interpreter}"' not in prompt
    assert "call operator" not in prompt


def test_the_shell_form_follows_the_host_by_default() -> None:
    interpreter = codex_review.resolve_interpreter()

    assert codex_review.verification_commands(interpreter) == _expected(
        interpreter, os.name == "nt"
    )


# C -- the gates are module invocations of that interpreter, never PATH lookups.
@pytest.mark.parametrize("windows", [True, False])
def test_the_gates_do_not_depend_on_path(windows: bool) -> None:
    interpreter = codex_review.resolve_interpreter()
    prompt = codex_review.build_prompt(interpreter, windows=windows)
    prefix = "& " if windows else ""

    for command in codex_review.verification_commands(interpreter, windows=windows):
        assert command.startswith(f'{prefix}"{interpreter}" -m ')
        assert command in prompt

    # No line of the prompt offers a bare, PATH-resolved gate as an alternative.
    lines = {line.strip() for line in prompt.splitlines()}

    for bare in ("pytest -q", "ruff check src scripts tests", "mypy src"):
        assert bare not in lines

    for launcher in ("py -m pytest", "python -m pytest"):
        assert launcher not in prompt


# D -- nothing about this machine is baked into the source.
CODEX_REVIEW_SOURCE = (AI_DIR / "codex_review.py").read_text(encoding="utf-8")


# An absolute path to a python binary inside a string literal. Deliberately
# narrower than "any drive letter": the source legitimately contains `RECEIVED:\n`.
HARDCODED_INTERPRETER = re.compile(
    r"""["'](?:[A-Za-z]:[\\/]|/)[^"'\n]*python""", re.IGNORECASE
)


def test_the_source_hardcodes_no_interpreter_path() -> None:
    assert HARDCODED_INTERPRETER.search(CODEX_REVIEW_SOURCE) is None

    for machine_specific in ("Richard", "Python314", "Programs\\Python"):
        assert machine_specific not in CODEX_REVIEW_SOURCE

    assert "sys.executable" in CODEX_REVIEW_SOURCE


# E -- an interpreter that cannot be used never becomes a clean review.
@pytest.mark.parametrize(
    "unusable",
    ["", "/nonexistent/python", "relative/python.exe"],
)
def test_an_unusable_interpreter_is_rejected(unusable: str) -> None:
    with pytest.raises(codex_review.InterpreterUnavailable):
        codex_review.resolve_interpreter(unusable)


def test_a_directory_is_not_an_interpreter() -> None:
    with pytest.raises(codex_review.InterpreterUnavailable):
        codex_review.resolve_interpreter(str(AI_DIR))


def test_launcher_fails_instead_of_reviewing_without_an_interpreter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "codex-review.md"
    monkeypatch.setattr(codex_review, "ROOT", tmp_path)

    def unusable() -> Path:
        raise codex_review.InterpreterUnavailable("interpreter does not exist: X")

    def must_not_run(*args: object, **kwargs: object) -> object:
        raise AssertionError("Codex must not be launched without an interpreter")

    monkeypatch.setattr(codex_review, "OUTPUT", output)
    monkeypatch.setattr(codex_review, "resolve_interpreter", unusable)
    monkeypatch.setattr(codex_review.subprocess, "run", must_not_run)

    assert codex_review.main() == 2

    outcome = read_review(output, "CODEX")

    assert outcome.status is ReviewStatus.EXECUTION_FAILED
    assert not outcome.executed
    assert not outcome.is_clean
    assert "interpreter does not exist" in outcome.detail

    capsys.readouterr()


def test_the_real_prompt_carries_the_whole_interpreter_path() -> None:
    """The launcher's actual prompt, inspected as text (no ellipsis anywhere).

    The reviewer reported the gates as `"...python.exe"`. That ellipsis is the
    reviewer abbreviating in prose: the prompt never contained one.
    """
    prompt = codex_review.build_prompt(codex_review.resolve_interpreter())
    interpreter = str(codex_review.resolve_interpreter())

    assert interpreter in prompt
    assert interpreter == os.path.abspath(sys.executable)
    assert "..." not in prompt
    assert "python.exe" not in prompt.replace(interpreter, "")

    for command in _expected(Path(interpreter), os.name == "nt"):
        assert command in prompt


def test_a_pass_blaming_the_interpreter_is_not_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Second layer: if Codex still answers PASS, the protocol catches it."""
    body = (
        "PASS\n\nVERIFICATION: the interpreter I was given is not installed, "
        "so the gates could not run."
    )

    code, output, _ = _run_main(monkeypatch, tmp_path, 0, body)

    assert code != 0
    assert read_review(output, "CODEX").status is ReviewStatus.EXECUTION_FAILED
