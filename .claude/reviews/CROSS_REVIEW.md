# Cross Review Contract (Protocol V2)

Each reviewer must work independently.

Do not read another review before completing your own, and do not read anything
under `.claude/reviews/runtime/`.

## The review is JSON

V1 asked a Markdown parser to tell structure from quoted content while both used
the same twelve labels. That ambiguity lives in the format, not the parser:
`IMPACT:` opening a field and `IMPACT:` inside quoted evidence are the same
bytes. V2 deletes the question. A review is one JSON document; every value sits
in a slot, so evidence may contain contract labels, whole findings, fences,
`-->`, `<!--` or any Unicode without touching the parse. Paste real command
output and real source verbatim — do not abbreviate it and do not escape it by
hand, because JSON string encoding already handles all of it.

Reply with ONE JSON object and nothing else: no prose before or after, no
markdown fence.

```json
{
  "schema_version": 3,
  "run_id": "<given to you>",
  "reviewer": "CLAUDE | CODEX",
  "review_tree": "<given to you>",
  "result": {
    "verdict": "CLEAN | FINDINGS | BLOCKED",
    "findings": []
  },
  "verification": { "notes": "<optional prose>" }
}
```

`run_id` and `review_tree` are issued once per round and must be copied
verbatim. `review_tree` is the Snapshot V2 identity of the tree you are
reviewing; echoing it is what binds this review to this round. A valid review
from an earlier round carries the wrong values and cannot be counted, and a tree
edited mid-round no longer rebuilds to the `review_tree` both reviewers signed.

### Findings

Every finding is an object with exactly these eleven fields, each a non-empty
string, and no others:

`id`, `severity`, `category`, `file`, `lines`, `claim`, `evidence`, `impact`,
`proposed_fix`, `verification`, `confidence`

`lines` is a string, e.g. `"120-134"`. `severity` is one of `CRITICAL`, `HIGH`,
`MEDIUM`, `LOW`.

There are no ordering rules: a JSON object has no line order to get wrong.

### Verdicts

| Verdict | Findings list | Meaning |
| --- | --- | --- |
| `FINDINGS` | non-empty | you found demonstrable defects |
| `CLEAN` | empty | you looked and the change is sound |
| `BLOCKED` | empty | you could not complete the review |

`CLEAN` is a positive claim that the work was done, not the absence of an
opinion. If your tooling could not run, answer `BLOCKED` and say what happened
in `verification.notes`. An unverifiable review is recorded as a failed run,
never as a clean second opinion.

Only report demonstrable problems: ones where you can point at the code and name
the input or sequence that exposes it.

## Verification is observed, not declared

`verification.notes` is optional prose. It is stored verbatim, read by humans
only, and has **no effect** on the recorded state.

The launcher runs `pytest`, `ruff` and `mypy` itself and stamps the exit codes
it observed over anything you write. Writing "all passed" cannot make a failing
check pass; writing "everything failed" cannot make a passing one fail. This
replaces V1's phrase-matching heuristic, which read the reviewer's prose and so
could only ever be a mitigation: it caught the honest reviewer that admitted
nothing ran, and could not catch one that invented plausible output.

A verdict counts only if all three checks were observed to exit 0.

## Review states

A review file is not the reviewer's text alone. `scripts/ai/review_v2.py` stamps
every run with what the launcher observed, and consumers read that stamp:

| State | Meaning | Counts as a review? |
| --- | --- | --- |
| `FINDINGS` | ran, reported defects | yes |
| `CLEAN` | ran, verified, no defects | yes |
| `BLOCKED` | reviewer declared it could not finish | no |
| `MISSING` | no file | no |
| `EMPTY` | file with no content | no |
| `NOT_EXECUTED` | no launcher attestation: nobody ran this reviewer | no |
| `EXECUTION_FAILED` | launcher observed a failure or non-zero exit | no |
| `VERIFICATION_FAILED` | a required check did not pass | no |
| `SCHEMA_INVALID` | ran, but the document breaks this contract | no |
| `RUN_MISMATCH` | belongs to a different round | no |
| `WORKSPACE_CHANGED` | describes a different tree than the round froze | no |

Only `FINDINGS` and `CLEAN` may participate in consensus or adjudication. The
others must never be reported as a clean second opinion, and a reviewer that did
not run is not agreement.

Check the states with:

    python scripts/ai/check_reviews_v2.py

## Scope of the guarantee

The round is bound by Snapshot Protocol V2 (`scripts/ai/snapshot_v2.py`), which
stores the reviewed tree as a git tree object built from the bytes on disk. It
therefore detects changes that `git status` is silent about — a path under
`--skip-worktree` or `--assume-unchanged`, an emptied or substituted gitlink —
which the previous fingerprint could not.

What it does **not** claim: this is not a defence against an adversary who can
write arbitrary files into `.claude/reviews/runtime/`. That directory is
excluded from the snapshot by construction, since it changes while the round
runs, so a hand-written review document there is not detected by these
mechanisms. The guarantee is against staleness, omission and accident, and for
the in-process reviewer it rests additionally on the orchestrator recording
honestly what it observed. It is a mitigation, not a proof.

---

# Legacy: Protocol V1 (superseded)

`/cross-review` no longer runs this pipeline. The V1 launchers
(`scripts/ai/check_reviews.py`, `codex_review.py`, `record_review.py`,
`review_protocol.py`) are still present, so what follows remains accurate for
anyone invoking them directly. Do not use it for a new round.

## Output format

For every finding:

ID:
REVIEWER:
SEVERITY:
CATEGORY:
FILE:
LINES:

CLAIM:

EVIDENCE:

IMPACT:

PROPOSED\_FIX:

VERIFICATION:

CONFIDENCE:

The twelve fields must appear in that order, each one non-empty. A value may
span several lines, so paste real command output or code as EVIDENCE rather
than compressing it onto one line. Blank lines, horizontal rules and markdown
headings between fields are ignored.

A line opens a field only when its label is the next one the contract expects,
so quoting `FILE:` or `SEVERITY:` inside EVIDENCE is almost always safe -- the
parser reads it as content.

The exception is narrow and worth knowing exactly. **A single quoted line whose
label happens to be the next field the parser is waiting for will open that
field.** Quote `IMPACT:` while EVIDENCE is open and your EVIDENCE ends there,
with the rest of the quote becoming IMPACT. Pasting a whole finding is only the
loudest case of this: its trailing `IMPACT:`, `PROPOSED_FIX:`, `VERIFICATION:`
and `CONFIDENCE:` lines arrive in exactly the order the parser expects, so they
are read as your real fields and yours end up buried in CONFIDENCE.

This is a limit of the format, not a bug to route around: the quoted line and
the real one are the same text, and nothing in the document distinguishes them.

Indenting does not help. Labels are matched after the line is stripped, so
`    IMPACT:` opens the field exactly as `IMPACT:` does. The only reliable
escape is to alter the label text itself -- write `IMPACT(quoted):`, or drop
the colon -- so it is no longer the label the parser is waiting for.

This whole class of ambiguity is why V2 stores the review as JSON: there, a
value in a slot cannot be mistaken for the structure around it.

Allowed severity:

CRITICAL
HIGH
MEDIUM
LOW

## Clean result

If no substantive issue is found, answer:

PASS

VERIFICATION: <the commands you actually executed, and their results>

A bare `PASS` is rejected. A clean verdict is a claim about work performed, and
the pipeline cannot tell an honest one from a reviewer that verified nothing
unless the verification is stated. If your tooling could not run -- no
interpreter, no test runner, a sandbox that denies execution -- say so in
VERIFICATION rather than answering PASS: an unverifiable review must be
recorded as a failed run, not as a clean second opinion.

That last rule is enforced, not merely requested. A `PASS` whose VERIFICATION
reports that its commands could not run -- `could not run`, `unable to run`,
`unavailable`, `denied`, `permission denied`, `access denied`, `command not
found`, `not installed`, `no interpreter`, `failed to launch`, `executable not
found`, matched case-insensitively -- is recorded as `EXECUTION_FAILED` and
cannot enter consensus (ADJ-01).

The check reads the reviewer's own prose, so it is a mitigation and not a
proof. It catches the honest reviewer that says nothing ran; it cannot catch
one that invents plausible output, and it will downgrade a review that
mentions a tool being unavailable in passing even though the work was done.
Rerunning a wrongly failed review is cheap; a wrongly clean one is the incident
this exists to prevent. If a phrase costs you a legitimate PASS, restate the
VERIFICATION with the commands you did run.

In V2 this heuristic is gone: the launcher runs the checks itself, so the
reviewer's prose has nothing to overrule.

## Blocked result

If you could not run the verification at all, do not answer `PASS`. Answer:

EXECUTION_FAILED

VERIFICATION: <what you attempted, the exact commands, and what happened>

This is the only verdict a reviewer may declare about its own run, and it is
accepted for one reason: it can only take authority away. The run counts as no
review, blocks consensus, and cannot be used to fabricate anything. `CLEAN` and
`FINDINGS` remain earned by satisfying the contract, never by asserting them.

A bare `EXECUTION_FAILED` with no VERIFICATION is rejected: the point of the
verdict is to record what stopped you.

## V1 review states

`scripts/ai/review_protocol.py` stamps every run with what the launcher
observed:

| State | Meaning | Counts as a review? |
| --- | --- | --- |
| `FINDINGS` | ran, reported defects | yes |
| `CLEAN` | ran, attested PASS | yes |
| `MISSING` | no file | no |
| `EMPTY` | file with no content | no |
| `NOT_EXECUTED` | no launcher attestation: nobody ran this reviewer | no |
| `EXECUTION_FAILED` | launcher observed a failure or non-zero exit | no |
| `INVALID_OUTPUT` | ran, but the output breaks this contract | no |

Only `FINDINGS` and `CLEAN` may participate in consensus or adjudication. The
other five must never be reported as a clean second opinion.

Check the V1 states with:

    python scripts/ai/check_reviews.py
