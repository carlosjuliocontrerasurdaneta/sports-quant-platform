# Cross Review Adjudication (Protocol V2) — INCOMPLETE

- **run_id**: `32a572de-c55e-4ca5-ba9d-55c35e46bb79`
- **review_tree (round start)**: `d8b1a41a2741b1661a6d0ed19dee09ac286bbe19`
- **Gate (`scripts/ai/check_reviews_v2.py`) exit code**: 1 (non-zero)
- **Reviewer states**: CLAUDE = `VERIFICATION_FAILED`, CODEX = `VERIFICATION_FAILED`
- **Consensus**: **BLOCKED / NOT ESTABLISHED.** Under the V2 contract a verdict
  counts only if pytest, ruff and mypy were all observed to exit 0. Both
  launchers observed `pytest` exit 1 (`tests/test_tennis_params.py::test_no_code_actually_handles_surface`,
  1 failed / 2097 passed / 1 skipped, identical on both runs; ruff 0, mypy 0).
  Neither reviewer's `FINDINGS` verdict is counted as a review under the
  contract. This is not two reviewers agreeing — it is two reviewers whose
  required verification gate both failed for the same reason, and that
  reason is itself one of the findings below (B-002). Per the adjudicator
  contract (ADJ-09), I am **not** reporting a clean second opinion from
  either side and I am **not** treating their overlap on B-002 as
  corroboration by agreement — I independently reproduced every finding
  below against the code.

**Tree state: MOVED.** `check_reviews_v2.py` could not rebuild `review_tree`
because `git -c core.excludesFile= add -A -- .` failed (exit 128) on
`.rev-tmp/pytest/.../results_nba_<hash>.csv` — a Windows `MAX_PATH` failure
("Filename too long") on a reviewer-generated pytest temp fixture under
`--basetemp=.rev-tmp/pytest`, not an edit to any tracked/versioned file. I
confirmed `git status --short` shows only the round's 28 expected staged
files (`M`/`A`) plus the untracked `.rev-tmp/` directory that caused the
failure — no versioned file was touched during the round. I am flagging this
prominently per the adjudicator contract, but I assess it as tooling noise
from the review runs, not as evidence the reviewed bytes changed. All
findings below were checked against the same 28-file `git diff --cached`
(`+10871/-125`) both reviewers describe.

Despite the gate being BLOCKED, the task requires verifying each reported
finding against the real code so main can be corrected. That verification
follows; it does not manufacture a consensus the gate did not produce.

---

## REV-A-001 (CLAUDE, HIGH) — MLB comparator built without starting-pitcher identity

**Claim**: for `family == "baseball"`, `build_research_dataset`'s own
baseline/"operational" comparator is computed with the starting pitcher
permanently absent, because `research.py`'s `Event(...)` call never sets
`home_pitcher`/`away_pitcher` and `feature_shadow.py`'s `train()`/`capture()`
never join `StartersStore` before calling `build_research_dataset`.

**Verification performed** (read-only, this worktree):
- `src/sqp/features/research.py:181` — `Event(str(r.event_id), "research", league, r.home, r.away, day)`:
  exactly 6 positional args. `Event.home_pitcher`/`away_pitcher`
  (`src/sqp/domain/models.py:16-17`) default to `None` and are never set here,
  for any family.
- `src/sqp/features/research.py:233/245` — `pending` holds `r.to_dict()`
  (the row from the combined results/fixtures frame `d`), later passed as
  `result` to `adapter.observe(result)`. Nothing upstream ever adds
  `home_starter`/`away_starter` to that frame for MLB.
- `src/sqp/storage/results_store.py:13` — `ResultsStore.COLUMNS = ["date",
  "home", "away", "game_id", "home_score", "away_score", "neutral",
  "ingested_at"]`. `data/historical/results_{league}.csv` never carries a
  starter column for any league; starter identity lives only in a separate
  `starters_{league}.csv`, merged in-memory only via `StartersStore.attach()`
  (`src/sqp/storage/starters.py:141-149`, confirmed by direct read).
- `src/sqp/evaluation/feature_shadow.py` — grepped `train()` (line 77) and
  `capture()` (line 175) in full: `raw = pd.read_csv(archived, ...)` (line
  121) and `history = pd.read_csv(BytesIO(history_bytes), ...)` (line 215)
  read the results CSV directly. There is no reference to `StartersStore`,
  `.attach(`, `home_starter` or `away_starter` anywhere in this file (grep
  confirmed zero hits). So the frame handed to `build_research_dataset` for
  MLB structurally has no starter columns, matching the claim exactly.
- `src/sqp/sports/adapters.py:131-138` — `BaseballAdapter`'s own docstring:
  "The starter is the largest single factor". `_rates()` (line 174-176 in
  this worktree) reads `self.starters.factor(event.away_pitcher)` /
  `factor(event.home_pitcher)`.
- `src/sqp/models/starters.py:34-41` — `StarterRatings.factor()`: `if not
  pitcher ... return 1.0` — confirmed the adjustment silently collapses to a
  no-op (neutral multiplier) whenever `pitcher` is `None`, exactly as
  claimed.
- `docs/FEATURE-SHADOW.md:33` (own read) — "Cada candidato se compara con su
  referencia aprendida **y el adaptador operativo**" ("...and the operational
  adapter"). This is a documented contract, not an implementation detail.
- Contrast within this same diff: `src/sqp/evaluation/compare.py`'s own
  `_sim_probs` (line 34, this diff) does `hp, ap = pitcher_name(getattr(r,
  "home_pitcher", None)), pitcher_name(getattr(r, "away_pitcher", None))`
  then `Event(..., home_pitcher=hp, away_pitcher=ap)` (lines 47-49) and feeds
  `"home_starter": hp, "away_starter": ap` back into `observe()` (line 53).
  `src/sqp/backtesting/engine.py:77-80` (pre-existing, unmodified by this
  diff) does the same: `home_pitcher=r.get("home_starter"),
  away_pitcher=r.get("away_starter")`. Both prove the correct pattern is
  known and used correctly elsewhere in the very same commit, which is what
  makes the omission in `research.py` a real, demonstrable oversight rather
  than a considered scope decision.
- I independently re-ran the reviewer's exact repro logic conceptually (not
  re-executed verbatim, since the reviewer already pasted concrete before/after
  numeric output showing `base_home` byte-identical with vs. without
  `home_starter`/`away_starter` present on the input frame, and a real
  0.553 vs 0.279 probability swing on `BaseballAdapter.estimate()` with vs.
  without pitcher identity on the `Event`); the static trace above
  independently establishes the same conclusion without needing to trust
  that pasted output.
- Scope check confirmed independently: `audit/feature_candidates_20260915.json`
  lists leagues `['atp', 'nba', 'ncaab', 'ncaaf', 'nfl', 'nhl', 'wncaab',
  'wta']` — zero MLB candidates in the currently-running
  `feature_shadow_20260915_v2` protocol. So this defect has not yet
  corrupted a live frozen result, but the code path is merged and live.

**Ruling**: **CONFIRMED**, severity **HIGH** (unchanged from CLAUDE's rating —
the static trace, the documented contract in `docs/FEATURE-SHADOW.md:33`,
and the correct pattern present twice elsewhere in this same diff together
leave no real uncertainty).

**Is this a defect or a documentable limitation?** A **defect**, not a scope
limitation to be merely documented. `docs/FEATURE-SHADOW.md:33` explicitly
promises comparison against "el adaptador operativo" for every candidate the
protocol covers, and the protocol's own stated scope is all eight
league/family combinations it trains for plus whatever leagues get added
later — MLB is `family: "baseball"`, a first-class supported family
(`SPORTING_INPUTS["baseball"]`, `PoissonAdapter`/`BaseballAdapter`,
`pitching_*` feature block all exist in this same diff). The code already
knows how to thread pitcher identity correctly (`compare.py`, same diff;
`backtesting/engine.py`, pre-existing) — this is an omission in one call
site, not an intentional simplification. Because `FROZEN_SHADOW_ONLY`
protocols freeze code and comparator methodology for a full calendar year
(`fingerprint()`-gated), an MLB candidate trained under the current code
cannot be corrected in place later; the run would have to be discarded and
restarted. No test in the diff catches this (confirmed: `grep -n
"starter\|pitcher\|mlb" tests/test_feature_shadow.py
tests/test_feature_integration.py` returns only one unrelated
`@pytest.mark.parametrize` hit).

**Proposed fix for main**: as CLAUDE proposed — (1) have `train()`/`capture()`
join `StartersStore` onto the results/history frame before calling
`build_research_dataset` for `family == "baseball"` (mirroring how
`compare.py`'s `_sim_probs` and `backtesting/engine.py` already source
`home_starter`/`away_starter`), (2) pass `home_pitcher=r.get("home_starter")`,
`away_pitcher=r.get("away_starter")` into the `Event(...)` call at
`research.py:181`, (3) include `home_starter`/`away_starter` in the dict
appended to `pending`/passed to `adapter.observe()` at `research.py:233/245`,
and (4) either extend `capture()`'s fixtures CSV schema to carry a
probable/confirmed starter for prospective MLB fixtures, or explicitly scope
MLB prospective `capture()` out until it can. Add a regression test
(CLAUDE's repro is a ready template) asserting `base_home`/`base_total`
change when starter identity changes for `family == "baseball"`, so this
cannot regress silently. This should be fixed before any MLB candidate is
ever registered in a `FROZEN_SHADOW_ONLY` protocol; it does not need to
block the already-running `feature_shadow_20260915_v2` protocol, which has
zero MLB candidates today.

---

## B-001 (CODEX, MEDIUM) — `capture_store()` `IndexError` on multi-league concat with `event_horizon_days > 0`

**Claim**: `feature_shadow.py:302-307`, `capture_store()` crashes with
`IndexError` when eligible rows from more than one per-league odds CSV share
index labels and `event_horizon_days > 0`, because `pd.concat(frames)` does
not reset the index.

**Verification performed**:
- Read `capture_store()` in full (`src/sqp/evaluation/feature_shadow.py:279-316`).
  Confirmed the exact code at lines 301-307:
  ```
  301  if frames:
  302      fixtures = pd.concat(frames).sort_values("_observed").drop_duplicates(["league", "source", "game_id"], keep="last")
  303      fixtures = fixtures.loc[[tuple(r) not in seen for r in fixtures[["league", "source", "game_id"]].to_numpy()], cols]
  304      start = pd.to_datetime(fixtures.start_time, utc=True)
  305      fixtures = fixtures.loc[(start >= pd.Timestamp(p["start"])) & (start < pd.Timestamp(p["end_exclusive"]))]
  306      if p["event_horizon_days"] > 0:
  307          fixtures = fixtures.loc[start.loc[fixtures.index] <= now + pd.Timedelta(days=p["event_horizon_days"])]
  ```
  `frames` is built per-league in the preceding loop (line 286-299), one
  `DataFrame` per `glob()`-matched `data/odds/odds_{league}_*.csv` file, each
  with pandas' default 0-based `RangeIndex` from `pd.read_csv`. `pd.concat`
  without `ignore_index=True` preserves those per-file labels verbatim, so
  two different leagues' first eligible rows both land on index label `0`.
- **Independently reproduced** (own script, not the reviewer's, in
  `.../scratchpad/repro_b001.py`, against synthetic in-memory frames
  mirroring the exact per-league shape produced by `capture_store()`'s loop,
  with `event_horizon_days = 7`, the production default from
  `src/sqp/config.py:251`): after the concat/sort/dedup/seen-filter/window
  steps the surviving index is `[0, 0]` (two distinct events, duplicate
  label), and `start.loc[fixtures.index]` at line 307 then raises
  `IndexError: indices are out-of-bounds` — the same exception class and
  message CODEX reported. Output:
  ```
  index after concat+sort+dedup: [0, 0]
  index after seen-filter: [0, 0]
  index after window filter: [0, 0]
  EXCEPTION: IndexError indices are out-of-bounds
  ```
  Root cause matches CODEX's diagnosis exactly: `.loc[]` on a duplicate-label
  index performs a label lookup that expands each repeated label to every
  matching row, producing a boolean/positional mismatch against `fixtures`.
- Confirmed `event_horizon_days` defaults to `7` in production
  (`src/sqp/config.py:251`: `int(os.getenv("MAX_EVENT_HORIZON_DAYS", "7"))`),
  i.e. the buggy branch (`if p["event_horizon_days"] > 0`) is the default
  path, not an opt-in edge case.
- Confirmed `capture_store()` is the function the long-running `watch`
  subcommand calls every 60 seconds for the life of the protocol
  (`scripts/feature_shadow.py:64-76`), and the currently-running
  `feature_shadow_20260915_v2` protocol spans **eight** leagues/circuits
  (`atp, nba, ncaab, ncaaf, nfl, nhl, wncaab, wta` — confirmed above from
  `audit/feature_candidates_20260915.json`). Any `watch` cycle where two or
  more of those leagues each have at least one freshly-eligible local odds
  row is enough to trigger this. `scripts/feature_shadow.py:78-81` shows an
  uncaught exception from `capture_store()` writes an `ERROR` heartbeat and
  then re-raises, killing the watcher process for the remainder of the
  frozen year unless something external restarts it.

**Ruling**: **CONFIRMED**. I am **raising the severity from MEDIUM to HIGH**:
the crash sits on the default configuration (`event_horizon_days=7 > 0`), in
the exact function the protocol's unattended, year-long collector calls
every minute, across a protocol that already spans eight leagues in
production today — this is not a rare or contrived input, it is close to the
common case for the tool's own stated use, and an uncaught crash here stops
prospective collection for the rest of the frozen window with no automatic
recovery shown in this diff.

**Proposed fix for main**: as CODEX proposed — `pd.concat(frames,
ignore_index=True)` at line 302. Verified this does not break the
subsequent logic: `drop_duplicates`, the `seen`-membership boolean list
(already positional, not index-dependent), and the two later `.loc[boolean]`
filters all remain correct with a fresh unique `RangeIndex`; `start.loc[fixtures.index]`
then performs an unambiguous 1:1 label lookup. Add a regression test in
`tests/test_feature_shadow.py` covering `capture_store()` (or the concat
step it depends on) with two-or-more-league overlapping-source fixtures and
`event_horizon_days > 0`, asserting every eligible fixture reaches capture
exactly once — CODEX's own verification note names the right test to add.

---

## B-002 (CODEX, MEDIUM) — `research.py:31` (`surface_elo`) breaks `test_no_code_actually_handles_surface`

**Claim**: adding the `surface_elo` name to tennis's `SPORTING_INPUTS` in
`research.py` trips the pre-existing guard test
`tests/test_tennis_params.py::test_no_code_actually_handles_surface`, which
source-scans every `.py` file under `sqp` for the literal substrings
`surface_elo`, `por_superficie`, `surface_rating` and fails if any are found
outside its own allow-list.

**Verification performed**:
- `src/sqp/features/research.py:31-32` (own read): `"tennis": ("surface_elo",
  "serve_points_won_rate", "return_points_won_rate", "minutes_played_7d")` —
  confirmed the literal string `surface_elo` is present.
- `tests/test_tennis_params.py:80-90` (own read): confirmed the test does
  exactly what is claimed — `raiz.rglob("*.py")`, substring-scans file text
  (case-folded) for `("surface_elo", "por_superficie", "surface_rating")`,
  and asserts zero hits with no exemption for research-only/inventory files.
- The gate's own `pytest` output (both reviewers, identical, and my own gate
  run above) confirms this deterministically fails: `AssertionError: ya hay
  manejo de superficie en ['research.py']: ...`, `1 failed, 2097 passed, 1
  skipped`. This is not a flaky or environment-dependent failure.

**Ruling**: **CONFIRMED**, severity **MEDIUM** (unchanged). This is a real,
deterministic regression introduced by this diff against an existing
production-contract guard test, correctly classified by CODEX as
`NEW_REGRESSION` and not a pre-existing failure — I confirmed `research.py`
is itself a new file added by this diff (`git status --short` shows `A
src/sqp/features/research.py`), so the guard could not have failed before
this commit.

**Context given for this adjudication, not independently re-verified in
this worktree** (this scratch tree's base is `96a4749`, which predates both
the merge of this content into `origin/main` and any follow-up fix commit,
so I cannot read a later commit's content from inside this tree without
leaving read-only/worktree-scope bounds): the round's brief states that
`origin/main` commit `f93bdc1` (2026-09-17) already updated this test to
treat `features/research.py` as an inventory-only exemption, so the test
currently passes on `main`. I report this as given context, not as
something I personally read from a diff — it is plausible and consistent
with the finding (the fix described is exactly the kind of narrow exemption
CODEX's own proposed fix calls for), but I did not open commit `f93bdc1`
myself. **If that context is accurate, no further action is needed for
B-002 beyond confirming `f93bdc1`'s exemption text actually scopes to
research-only usage** (i.e. that it doesn't just delete the guard outright,
which would silently re-open the original surface-modeling contract the
test protects). That one check — reading `f93bdc1`'s diff to
`tests/test_tennis_params.py` — is what would fully close this item; it is
outside what this scratch worktree can see.

---

## Findings not raised by either reviewer

None identified. This adjudication did not go looking for a fourth
independent finding beyond the three reported; it verified the three that
were reported.

---

## Summary

| ID | Reviewer | Reported severity | Ruling | Final severity |
|---|---|---|---|---|
| REV-A-001 | CLAUDE | HIGH | CONFIRMED | HIGH (unchanged) |
| B-001 | CODEX | MEDIUM | CONFIRMED | **HIGH** (raised — default config, default collector path, live 8-league protocol) |
| B-002 | CODEX | MEDIUM | CONFIRMED | MEDIUM (unchanged; likely already fixed in `main` via `f93bdc1`, not independently verified here) |

**CONFIRMED, by severity**:
- **HIGH**: REV-A-001 (MLB comparator built without starting-pitcher
  identity, contradicting `docs/FEATURE-SHADOW.md:33`'s stated contract);
  B-001 (`capture_store()` `IndexError` under default config, in the
  unattended collector's default code path).
- **MEDIUM**: B-002 (`research.py:31`'s `surface_elo` breaks the tennis
  no-surface-modeling guard test) — reported as likely already remediated on
  `main` by a later commit; that remediation was not independently verified
  from this worktree.

**Consensus was NOT established for this round.** Both CLAUDE and CODEX are
in state `VERIFICATION_FAILED` per `check_reviews_v2.py`; under Protocol V2
neither reviewer's `FINDINGS` verdict counts as a review, and per the
adjudicator contract a reviewer that did not produce a counted review cannot
contribute to consensus and must not be reported as a clean or agreeing
second opinion. The three findings above were adjudicated on their evidentiary
merits — direct code reads plus one independent reproduction (B-001) — not
because two reviewers happened to agree; B-002 in particular is not
corroboration-by-agreement so much as both reviewers hitting the same
already-failing gate the diff itself causes. **This round should be recorded
as INCOMPLETE, and, since the reviewed content (commit `72d07d8`'s tree) is
already merged into `origin/main` (via `31cfdb0`) and already running in
production since the 2026-09-17 12:00 run, the two HIGH-severity CONFIRMED
defects (REV-A-001, B-001) are live-in-production items to fix on `main`,
not blockers to merging this round's already-merged content.**
