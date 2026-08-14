Perform a complete independent cross-model review under Cross Review Protocol V2.

Follow this exact sequence. Every script below is the `_v2` one; the V1 scripts
beside them are superseded and must not be used for a round.

## Phase 0 — Open the round

Inspect first:

    git status
    git diff

If there are no relevant changes, stop.

Then discard the previous cycle and open a new one:

    python scripts/ai/check_reviews_v2.py --reset
    python scripts/ai/check_reviews_v2.py --start

`--start` mints a `run_id` and freezes the working tree with Snapshot Protocol
V2, publishing it as `refs/cross-review/<run_id>`. It prints `base_commit`,
`staged_tree`, `review_tree` and `review_commit`. **`review_tree` is the
round's identity**: both reviewers must echo it, and the gate rebuilds the tree
from disk to check it still matches.

If `--start` fails it prints `[NO ROUND]` and exits 2. There is no round; do not
proceed.

**From here until adjudication is finished, do not modify the repository.** The
round is bound to the bytes on disk. Any edit outside
`.claude/reviews/runtime/` and `.codex-tmp/` moves `review_tree`, and the gate
will correctly refuse to adjudicate reviews that describe a tree that no longer
exists. This includes "harmless" fixes, formatting and new files.

## Phase 1 — Claude independent review

Use:

    .claude/agents/independent-code-reviewer.md

Complete the review WITHOUT reading any Codex review, and without reading
anything under `.claude/reviews/runtime/`.

The agent writes ONE JSON document to:

    .claude/reviews/runtime/v2/claude-body.json

Hand the agent this round's `run_id` and `review_tree`; it must copy both
verbatim. The schema is in `.claude/reviews/CROSS_REVIEW.md`.

Then stamp it with the provenance of this run:

    python scripts/ai/record_review_v2.py CLAUDE --body .claude/reviews/runtime/v2/claude-body.json

This runs pytest, ruff and mypy itself and stamps the observed exit codes. What
the agent wrote about its own verification is not consulted.

If the agent returned nothing, record that instead — never leave the state to be
inferred:

    python scripts/ai/record_review_v2.py CLAUDE --failed "<what happened>"

## Phase 2 — Codex independent review

Run:

    python scripts/ai/codex_review_v2.py

Do not modify the Codex output. A non-zero exit means Codex did not produce a
review; do not retry silently and do not substitute your own judgement for it.

## Phase 3 — The gate

    python scripts/ai/check_reviews_v2.py

It reports, per reviewer, one of FINDINGS, CLEAN, BLOCKED, MISSING, EMPTY,
NOT_EXECUTED, EXECUTION_FAILED, VERIFICATION_FAILED, SCHEMA_INVALID,
RUN_MISMATCH, WORKSPACE_CHANGED. **Only FINDINGS and CLEAN are reviews.**

It also reports whether the tree still matches the snapshot. `MOVED` means the
repository changed after the round opened.

If it exits non-zero, do NOT report consensus and do NOT present a missing
reviewer as clean. Adjudicate whatever reviews exist and mark the run
INCOMPLETE, naming the missing reviewer and its state.

## Phase 4 — Adjudication

Use:

    .claude/agents/review-adjudicator.md

Compare:

    .claude/reviews/runtime/v2/claude.md
    .claude/reviews/runtime/v2/codex.md

The JSON beside each is the review; the Markdown is a rendering of it. Verify
each finding against the actual code — a reviewer's silence is never
corroboration, and two reviewers agreeing is not evidence.

Save the result to:

    .claude/reviews/runtime/v2/adjudication.md

## Phase 5 — Verification

The launcher already ran pytest, ruff and mypy once per reviewer and stamped
what it observed. Read those results out of the reviews rather than trusting
prose. Re-run only if the tree changed, which would in any case have blocked the
gate:

    pytest -q
    ruff check src scripts tests
    mypy src

## Final response

Report:

- Claude findings
- Codex findings
- confirmed findings
- rejected findings
- uncertain findings
- test results as observed by the launcher
- the state of each reviewer as reported by `check_reviews_v2.py`, and whether
  consensus was available
- the round's `run_id` and `review_tree`

Never describe a reviewer that did not run as a clean review or as agreement.

The round's snapshot stays reachable at `refs/cross-review/<run_id>` until the
next `--reset`, so the reviewed tree can be diffed after the fact:

    git diff <base_commit> <review_commit>

Do not commit.
Do not push.
Do not merge.
