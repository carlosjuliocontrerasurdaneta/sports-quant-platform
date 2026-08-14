"""Execution-attested protocol for the cross-review pipeline.

A file is only a review if the launcher that ran the reviewer stamped it. Text
alone proves nothing: before this protocol, a stale file left by a previous
cycle, a reviewer that never started, and a reviewer that genuinely finished
clean were all byte-identical -- the string ``PASS`` -- so the pipeline could
present the absence of a review as a clean second opinion (ADJ-09).

Two rules follow from that:

1. Only :func:`write_review` produces the provenance header, and it records
   what the launcher observed (whether the process started, its exit code, how
   long it ran). A file without that header is NOT_EXECUTED, never CLEAN.
2. ``PASS`` on its own is no longer a review body. A clean verdict must state
   the verification behind it, because the incident that motivated this module
   was a reviewer whose every verification command failed inside its sandbox
   and which then answered ``PASS`` anyway.
3. A stated verification is not the same as a performed one. Demanding the text
   only moved the incident one step: the reviewer wrote down, accurately, that
   its interpreter and test runner were unavailable, and the pipeline still
   read that as a clean second opinion (ADJ-01). A VERIFICATION that reports
   its own commands could not run is now EXECUTION_FAILED, not CLEAN.

:func:`read_review` re-derives the status from the body instead of trusting the
recorded one, so a hand-edited header cannot declare a garbage body clean.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TextIO
import json
import re
import sys


REVIEW_FIELDS = (
    "ID",
    "REVIEWER",
    "SEVERITY",
    "CATEGORY",
    "FILE",
    "LINES",
    "CLAIM",
    "EVIDENCE",
    "IMPACT",
    "PROPOSED_FIX",
    "VERIFICATION",
    "CONFIDENCE",
)
ALLOWED_SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})

PROVENANCE_OPEN = "<!-- cross-review-provenance"
PROVENANCE_CLOSE = "-->"

#: The JSON escape for a hyphen, built from its code point so this source file
#: never contains the sequence it exists to keep out of the header.
JSON_DASH = chr(92) + "u002d"

_STRUCTURAL = re.compile(r"^(-{3,}|\*{3,}|_{3,}|#{1,6}\s.*|(?:```|~~~).*)$")

#: The one verdict a reviewer may assert about its own run. See the note on
#: authority in :func:`parse_review_body`.
BLOCKED_VERDICT = "EXECUTION_FAILED"

#: Phrases that mean a VERIFICATION is describing commands that never ran.
UNVERIFIABLE_MARKERS = (
    "could not run",
    "unable to run",
    "unavailable",
    "permission denied",
    "access denied",
    "denied",
    "command not found",
    "not installed",
    "no interpreter",
    "failed to launch",
    "executable not found",
)


class ReviewStatus(str, Enum):
    """The states the pipeline must be able to tell apart."""

    # The reviewer ran and deliberately produced a result.
    FINDINGS = "FINDINGS"
    CLEAN = "CLEAN"

    # No usable review exists. None of these may count as PASS.
    MISSING = "MISSING"
    EMPTY = "EMPTY"
    NOT_EXECUTED = "NOT_EXECUTED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    INVALID_OUTPUT = "INVALID_OUTPUT"


#: Only these two states may participate in consensus or adjudication.
EXECUTED = frozenset({ReviewStatus.FINDINGS, ReviewStatus.CLEAN})


@dataclass(frozen=True)
class ReviewOutcome:
    reviewer: str
    status: ReviewStatus
    detail: str = ""
    findings: tuple[dict[str, str], ...] = ()
    provenance: dict[str, object] | None = None

    @property
    def executed(self) -> bool:
        """True only when the reviewer ran and produced a deliberate result."""
        return self.status in EXECUTED

    @property
    def is_clean(self) -> bool:
        return self.status is ReviewStatus.CLEAN

    def summary(self) -> str:
        detail = f" -- {self.detail}" if self.detail else ""

        if self.status is ReviewStatus.FINDINGS:
            return f"{self.status.value} ({len(self.findings)}){detail}"

        return f"{self.status.value}{detail}"


def safe_print(text: str, stream: TextIO | None = None) -> None:
    """Print text on a console that may not encode every character.

    Windows consoles default to cp1252 and reviewer diagnostics can contain
    characters outside that range. Unencodable characters are replaced so a
    completed review is never turned into a failure by the terminal (ADJ-07).
    """
    target = sys.stdout if stream is None else stream
    encoding = getattr(target, "encoding", None) or "utf-8"

    print(text.encode(encoding, "replace").decode(encoding, "replace"), file=target)


def parse_field_line(line: str) -> tuple[str, str] | None:
    """Split a contract line into its label and value.

    The contract renders the proposed-fix label markdown-escaped
    (``PROPOSED\\_FIX:``), so backslashes are dropped from the label. Returns
    None when the line carries no label separator.
    """
    label, separator, value = line.partition(":")

    if not separator:
        return None

    return label.replace("\\", "").strip(), value.strip()


def _field_label(line: str) -> str | None:
    """Return the contract field this line opens, if any."""
    parsed = parse_field_line(line)

    if parsed is None or parsed[0] not in REVIEW_FIELDS:
        return None

    return parsed[0]


def parse_findings(text: str) -> tuple[list[dict[str, str]], str]:
    """Parse contract findings. Returns (findings, error); error empty if valid.

    Field values may span several lines: a line that does not open a contract
    field continues the value of the one in progress. The previous validator
    required exactly one physical line per field, a rule absent from the
    contract, so any finding carrying a code snippet as EVIDENCE -- or two
    findings separated by a horizontal rule -- was discarded as malformed
    (CLA-02).

    A heading, rule or code fence counts as layout only while no field is open.
    Inside a field it is content and is kept verbatim: reviewers paste diffs and
    source, and a single ``# comment`` line used to end the field and turn the
    whole review into INVALID_OUTPUT (CLA-01). The cost is that a rule placed
    after the twelfth field, rather than before the next ``ID:``, joins that
    field's value -- harmless, since the field is already non-empty.

    A line only opens a field when its label is the *next* one the contract
    expects. The twelve fields are ordered and appear once, so at any point
    exactly one label can legitimately follow; anything else is content. Keying
    on the label alone had the same shape of bug as CLA-01 one level down: a
    reviewer quoting ``FILE: generated.py`` inside EVIDENCE opened a second FILE
    field and lost the review to INVALID_OUTPUT (SQP-CR-001). Out-of-order and
    duplicated labels are still rejected -- they simply fail later, when the
    finding is closed without its twelve fields.
    """
    findings: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    order: list[str] = []
    open_field: str | None = None

    def close() -> str:
        if current is None:
            return ""

        if tuple(order) != REVIEW_FIELDS:
            return (
                f"finding {current.get('ID', '?')!r} does not carry the twelve "
                f"contract fields in order; got: {', '.join(order) or '(none)'}"
            )

        if not all(current[name] for name in REVIEW_FIELDS):
            empty = [name for name in REVIEW_FIELDS if not current[name]]
            return f"finding {current['ID']!r} has empty field(s): {', '.join(empty)}"

        if current["SEVERITY"] not in ALLOWED_SEVERITIES:
            return (
                f"finding {current['ID']!r} has severity {current['SEVERITY']!r}; "
                f"allowed: {', '.join(sorted(ALLOWED_SEVERITIES))}"
            )

        findings.append(current)

        return ""

    for raw in text.splitlines():
        stripped = raw.strip()
        label = _field_label(raw)
        expected = (
            REVIEW_FIELDS[len(order)]
            if current is not None and len(order) < len(REVIEW_FIELDS)
            else REVIEW_FIELDS[0]
        )

        if label == expected:
            if label == "ID":
                error = close()

                if error:
                    return [], error

                current, order, open_field = {}, [], None

            assert current is not None
            value = parse_field_line(raw)
            assert value is not None
            current[label] = value[1]
            order.append(label)
            open_field = label
            continue

        if not stripped:
            continue

        if current is not None and open_field is not None:
            # Includes a line that merely looks like a label: only the next
            # contract field can open one, so this is quoted content.
            current[open_field] = f"{current[open_field]}\n{stripped}".strip()
            continue

        if _STRUCTURAL.match(stripped):
            # Layout between findings; inside a field it is already content.
            continue

        if label is not None:
            return [], f"{label!r} appears before any 'ID:' line"

        return [], f"unexpected text outside a contract field: {stripped!r}"

    error = close()

    if error:
        return [], error

    if not findings:
        return [], "no finding found"

    return findings, ""


def carries_full_finding(text: str) -> bool:
    """True when the text spells out a populated finding: twelve fields, in
    order, at least one of them carrying a value.

    Deliberately exact: it advances through :data:`REVIEW_FIELDS` and only
    reports a hit on the twelfth. One quoted label, or eleven of them, is prose.

    A run of twelve *empty* labels is the contract's own skeleton -- the list
    this document and the launcher's prompt hand every reviewer -- so quoting it
    was being punished as if it were a smuggled finding (CLA-C2). It carries no
    claim, so it is exempt. The exemption is all-or-nothing on purpose: relaxing
    it per-field would let a fully populated CRITICAL finding pass by blanking a
    single label, which is the ADJ-C1 hole reopened from the other side.
    """
    remaining = list(REVIEW_FIELDS)
    values: list[str] = []

    for raw in text.splitlines():
        parsed = parse_field_line(raw)

        if parsed is not None and parsed[0] == remaining[0]:
            values.append(parsed[1])
            remaining.pop(0)

            if not remaining:
                return any(values)

    return False


def _verdict_verification(lines: list[str], verdict: str) -> tuple[str, str]:
    """Read the VERIFICATION backing a bare verdict. Returns (value, error).

    Once VERIFICATION opens, every remaining line is its value -- including one
    that merely looks like a contract label. A reviewer pastes the commands and
    output it ran, and that output routinely quotes ``FILE:`` or ``SEVERITY:``;
    treating those as structure killed the body as INVALID_OUTPUT, the mirror
    image of the defect fixed in :func:`parse_findings` (CLA-A3).

    Before VERIFICATION opens, a contract label still means the body is a
    finding wearing a verdict's clothes, and is rejected. That is what keeps
    the verdict honest: the reviewer gains a free-text field, never a way to
    assert CLEAN or FINDINGS, both of which are decided elsewhere.

    Making the value unconditional went one step too far on its own: a PASS
    trailed by a complete finding was absorbed whole and returned CLEAN, where
    it used to be INVALID_OUTPUT -- a malformed body resolving *upward*, which
    the module forbids (ADJ-C1). A full twelve-field sequence inside the value
    is therefore rejected. The test is structural and exact, so isolated quotes
    such as ``SEVERITY:`` remain what a reviewer needs them to be: content.
    """
    value_lines: list[str] = []
    inside = False

    for raw in lines:
        stripped = raw.strip()
        label = _field_label(raw)

        if inside:
            if stripped:
                value_lines.append(stripped)

            continue

        if label == "VERIFICATION":
            parsed = parse_field_line(raw)
            assert parsed is not None
            value_lines.append(parsed[1])
            inside = True
            continue

        if label is not None:
            return "", (
                f"a {verdict} review may not carry finding fields; found {label!r}"
            )

        if not stripped:
            continue

        if _STRUCTURAL.match(stripped):
            continue

        return "", (
            f"unexpected text between {verdict} and VERIFICATION: {stripped!r}"
        )

    value = "\n".join(part for part in value_lines if part).strip()

    if not value:
        return "", (
            f"{verdict} must be backed by 'VERIFICATION: <what you actually "
            f"attempted, and what happened>'; a bare {verdict} is "
            f"indistinguishable from a reviewer that did nothing"
        )

    return value, ""


def unverifiable_marker(verification: str) -> str | None:
    """Return the phrase showing a VERIFICATION reports nothing could be run.

    Matching is case-insensitive and whitespace-insensitive, so a phrase split
    across lines is still caught. The longest matching phrase is returned, so
    the detail names ``permission denied`` rather than ``denied``.

    This is a mitigation, not a cryptographic proof, and it cannot become one:
    it reads the reviewer's own prose about its own work. A reviewer that
    invents plausible command output is still classified CLEAN, and an honest
    reviewer writing "mypy is unavailable in CI so I ran it locally" is
    downgraded although it did verify -- a deliberate bias, since a false
    EXECUTION_FAILED only costs a rerun while a false CLEAN is the ADJ-01
    incident. Real attestation requires the launcher to observe the commands,
    not the reviewer to describe them; until the launcher does, treat CLEAN as
    "claimed verification that does not contradict itself".
    """
    haystack = " ".join(verification.lower().split())

    for marker in sorted(UNVERIFIABLE_MARKERS, key=len, reverse=True):
        if marker in haystack:
            return marker

    return None


def parse_review_body(
    text: str, reviewer: str
) -> tuple[ReviewStatus, tuple[dict[str, str], ...], str]:
    """Classify a reviewer's own output. Returns (status, findings, detail).

    Who may assert what
    -------------------
    The reviewer never assigns its own status: this function derives it, and
    :func:`read_review` re-derives it from the body rather than trusting the
    header. The reviewer only supplies text.

    ``EXECUTION_FAILED`` is the single exception, and it is safe because it is
    monotonic downward. It is the one verdict that costs the reviewer all of
    its authority: the state blocks consensus, counts as no review at all, and
    can be reached anyway by the launcher observing a crash. A reviewer cannot
    use it to fabricate anything, only to disqualify itself -- so accepting it
    adds no attack surface, while refusing it produced the opposite failure:
    a reviewer that correctly reported it could not run the gates was filed as
    INVALID_OUTPUT, indistinguishable from garbage.

    Upward claims stay unforgeable. ``CLEAN`` and ``FINDINGS`` are still earned
    by satisfying the contract, and a ``PASS`` whose VERIFICATION contradicts
    itself is pushed back down to EXECUTION_FAILED.
    """
    normalized = text.strip()

    if not normalized:
        return ReviewStatus.EMPTY, (), "review body is empty"

    lines = normalized.splitlines()
    head = next((line.strip() for line in lines if line.strip()), "")

    if head == BLOCKED_VERDICT:
        index = lines.index(next(line for line in lines if line.strip() == head))
        verification, error = _verdict_verification(lines[index + 1:], head)

        if error:
            return ReviewStatus.INVALID_OUTPUT, (), error

        return ReviewStatus.EXECUTION_FAILED, (), verification

    if head == "PASS":
        index = lines.index(next(line for line in lines if line.strip() == "PASS"))
        verification, error = _verdict_verification(lines[index + 1:], "PASS")

        if error:
            return ReviewStatus.INVALID_OUTPUT, (), error

        if carries_full_finding(verification):
            # Only PASS needs this. EXECUTION_FAILED already blocks consensus,
            # so absorbing a finding there cannot resolve upward, and rejecting
            # it would discard the diagnostic that verdict exists to preserve.
            return ReviewStatus.INVALID_OUTPUT, (), (
                "a PASS may not carry a complete finding; its VERIFICATION "
                "spells out all twelve contract fields, populated, in order. "
                "Report findings as findings, not inside a clean verdict"
            )

        marker = unverifiable_marker(verification)

        if marker is not None:
            return ReviewStatus.EXECUTION_FAILED, (), (
                f"PASS is not a clean review: its own VERIFICATION reports "
                f"{marker!r}, so the verdict rests on commands that never "
                f"ran -- {verification}"
            )

        return ReviewStatus.CLEAN, (), verification

    findings, error = parse_findings(normalized)

    if error:
        return ReviewStatus.INVALID_OUTPUT, (), error

    for finding in findings:
        if finding["REVIEWER"].upper() != reviewer.upper():
            return ReviewStatus.INVALID_OUTPUT, (), (
                f"finding {finding['ID']!r} is attributed to "
                f"{finding['REVIEWER']!r}, expected {reviewer.upper()!r}"
            )

    return ReviewStatus.FINDINGS, tuple(findings), ""


def valid_review(text: str, reviewer: str = "CODEX") -> bool:
    """True when a reviewer's raw output satisfies the contract."""
    status, _, _ = parse_review_body(text, reviewer)

    return status in EXECUTED


def render_review(provenance: dict[str, object], body: str) -> str:
    """Serialize the provenance header so no payload can terminate it.

    The header is framed as an HTML comment and carries raw reviewer stderr,
    which is arbitrary text. A failure message containing ``-->`` used to close
    the comment early: the tail of the header leaked into the body, the JSON no
    longer parsed, and a file stamped EXECUTION_FAILED was re-read as
    NOT_EXECUTED with the diagnostic discarded (CLA-A2).

    Escaping the delimiter is not enough on its own -- the fix has to make the
    sequence unrepresentable. Every ``--`` is emitted as ``\\u002d\\u002d``,
    which JSON decodes back to ``--`` exactly, so the round trip is lossless
    while ``-->`` cannot occur. The substitution is safe across the whole
    document because valid JSON can only contain ``--`` inside a string: two
    minus signs outside one would need a separator between them.
    """
    header = json.dumps(provenance, indent=2, sort_keys=True)

    safe = header.replace("--", JSON_DASH + JSON_DASH)

    return f"{PROVENANCE_OPEN}\n{safe}\n{PROVENANCE_CLOSE}\n\n{body.strip()}\n"


def write_review(
    path: Path,
    reviewer: str,
    body: str,
    *,
    launched: bool,
    exit_code: int | None,
    command: str,
    duration_s: float,
    failure: str = "",
) -> ReviewOutcome:
    """Stamp and persist a review from what the launcher actually observed.

    This is the only function that produces a provenance header, so a file
    without one is by construction a review nobody ran.
    """
    if not launched or exit_code != 0:
        status: ReviewStatus = ReviewStatus.EXECUTION_FAILED
        detail = failure or f"reviewer exited with code {exit_code}"
        findings: tuple[dict[str, str], ...] = ()
    else:
        status, findings, detail = parse_review_body(body, reviewer)

    provenance: dict[str, object] = {
        "reviewer": reviewer.upper(),
        "status": status.value,
        "launched": launched,
        "exit_code": exit_code,
        "command": command,
        "duration_s": round(duration_s, 3),
        "recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "findings": len(findings),
    }

    if status is ReviewStatus.EXECUTION_FAILED:
        # Persisted whole: read_review reports this to the operator, and a
        # truncated stderr is the half of the message that says why (CLA-02).
        provenance["failure"] = failure or detail

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_review(provenance, body.strip() or f"[{status.value}] {detail}"),
        encoding="utf-8",
    )

    return ReviewOutcome(reviewer.upper(), status, detail, findings, provenance)


def _split_provenance(text: str) -> tuple[dict[str, object] | None, str]:
    if not text.lstrip().startswith(PROVENANCE_OPEN):
        return None, text

    header, separator, body = text.lstrip()[len(PROVENANCE_OPEN):].partition(
        PROVENANCE_CLOSE
    )

    if not separator:
        return None, text

    try:
        parsed = json.loads(header)
    except json.JSONDecodeError:
        return None, body

    if not isinstance(parsed, dict):
        return None, body

    return parsed, body


def read_review(path: Path, reviewer: str) -> ReviewOutcome:
    """Classify a review file for consumers that must fail safe.

    The body is re-parsed rather than trusting the recorded status, so editing
    the header cannot turn an invalid body into a clean review.
    """
    name = reviewer.upper()

    if not path.exists():
        return ReviewOutcome(name, ReviewStatus.MISSING, f"no file at {path}")

    text = path.read_text(encoding="utf-8", errors="replace")

    if not text.strip():
        return ReviewOutcome(name, ReviewStatus.EMPTY, f"{path} is empty")

    provenance, body = _split_provenance(text)

    if provenance is None:
        return ReviewOutcome(
            name,
            ReviewStatus.NOT_EXECUTED,
            "no launcher attestation: this file was not produced by a review run",
        )

    if str(provenance.get("reviewer", "")).upper() != name:
        return ReviewOutcome(
            name,
            ReviewStatus.NOT_EXECUTED,
            f"attested for {provenance.get('reviewer')!r}, expected {name!r}",
        )

    if provenance.get("status") == ReviewStatus.EXECUTION_FAILED.value:
        recorded = str(provenance.get("failure") or "").strip()

        return ReviewOutcome(
            name,
            ReviewStatus.EXECUTION_FAILED,
            recorded or body.strip(),
            (),
            provenance,
        )

    if not provenance.get("launched") or provenance.get("exit_code") != 0:
        return ReviewOutcome(
            name,
            ReviewStatus.EXECUTION_FAILED,
            f"attested exit_code={provenance.get('exit_code')!r}",
            (),
            provenance,
        )

    status, findings, detail = parse_review_body(body, name)

    return ReviewOutcome(name, status, detail, findings, provenance)


def consensus_available(outcomes: list[ReviewOutcome]) -> bool:
    """Consensus needs at least two reviewers that actually ran."""
    executed = [outcome for outcome in outcomes if outcome.executed]

    return len(executed) >= 2 and len(executed) == len(outcomes)
