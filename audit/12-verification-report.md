# 12 - Independent verification report

Date: 2026-08-05 (America/Santiago)  
Branch: `audit/full-project`  
Base commit cited by the audited reports: `7871bdb148d174f0ed74cabfa0fa6596638e33f5`

## Scope and method

This report independently verifies every Critical, High, and Medium finding in
`audit/02-architecture.md` through `audit/10-findings-index.md`. The index has no
Critical findings, 11 High findings, and 19 Medium findings: 30 findings total.

No production or test code was modified. No project datasets, environment files,
logs, or secrets were read. No network calls or dependencies were used. Behavioral
checks live only in `audit/reproductions/verify_high_medium.py`.

Disposition:

| Status | Count |
|---|---:|
| Confirmed | 18 |
| Partially confirmed | 9 |
| False positive | 2 |
| Blocked by environment | 1 |
| Not reproduced | 0 |

## Commands and relevant output

The following command identifiers are referenced by each finding.

### V1 - Required graph query

```powershell
graphify query "What validation commands, CI checks, coverage, packaging, linting, typing, and dependency checks are configured?"
```

Exit 0. The query located the relevant pipeline, audit, test, and prior-audit nodes.

### V2 - Direct source inspection

The cited files were read with PowerShell `Get-Content`. Numbered excerpts used
this exact helper followed by the invocations named per finding:

```powershell
function Show-Lines($Path,$Start,$End){$x=Get-Content -LiteralPath $Path; for($i=$Start;$i -le [Math]::Min($End,$x.Count);$i++){"{0,4}: {1}" -f $i,$x[$i-1]}}
```

### V3 - Call-path and counter-evidence searches

```powershell
rg -n '_consensus_lines\(|load_closing_odds\(' src scripts tests
rg -n --glob 'tests/**/*.py' 'sqp\.storage\.lock|sqp\.storage\.atomic|sqp\.sports\.base|sqp\.models\.ml_predict|sqp\.providers\.base|sqp\.logging_config|from sqp\.storage import lock|from sqp\.storage import atomic'
rg -n --glob 'tests/**/*.py' '\blocked\b|atomic_write_csv|\.lock|lock timeout|stale_s|timeout_s' tests
rg -n --hidden -g '!data/**' -g '!historical/**' -g '!logs/**' -g '!exports/**' -g '!.git/**' 'current-task|Result:\s*PASS|commands_executed|observable evidence|STATES' tests .claude audit/latest/FINDINGS.md
rg -n 'shadow_mode|clv_gate|min_n|auto_promote|degradation_monitor' configs/default.yaml
rg -n 'max_event|event.*cap|exposure.*event|groupby\("event_id"|groupby\(\[.*event_id' src tests
```

All commands exited 0 except searches with no match, which produced no output.
Key counter-evidence: `roi_engine.py:218` calls the same `_consensus_lines` used by
production; three lock tests exercise `locked` through `odds_store._locked`; and
`test_claude_system_contract.py:126-149` enforces PASS evidence.

### V4 - Minimal reproductions

```powershell
$env:PYTHONPATH='src'; python audit/reproductions/verify_high_medium.py
```

Exit 0. Relevant output:

```text
COR-01/COR-02: totals Under NaN=win; totals Over NaN=loss; spread NaN=loss
COR-03: consensus_home=1.9; count_home=2
COR-04/PRF-02: alive after 0.5s with timeout_s=0.05 -> true
QNT-01: decision_probability=0.55; penalty=0.0175; effective coefficient=0.175
QNT-03: consensus and both fair probabilities are NaN
QNT-04: n=30; median=inf; allowed=true
DAT-03: odd-book median offered=true; even-book median offered=false
DAT-05: reversing results swaps early/late event assignments
```

### V5 - Existing targeted tests

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/settlement/test_settle_grade.py tests/test_vig.py tests/test_clv.py tests/test_clv_gate.py tests/test_odds_store.py tests/test_roi_engine.py tests/test_backtest_tuning.py tests/test_claude_system_contract.py tests/test_audit_2026_07_29.py tests/test_daily_exposure.py tests/test_kelly.py tests/test_edge.py -q
```

Exit 0: `129 passed in 14.27s`.

## Per-finding verification

### ARCH-01

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** `run_league` spans `daily.py:476-740` and directly performs provider
  selection/fetch, model fitting, consensus/no-vig, scoring/staking, served-stream
  persistence, per-league exposure limiting, and final persistence. Existing helpers
  reduce some complexity, but the six responsibilities and 111-line market loop remain.
- **Guards/counter-evidence:** `_finalize`, probability helpers, and cap helpers are
  already extracted; this narrows the maintainability claim but does not invalidate it.
- **Commands:** V2 (`Show-Lines 'src/sqp/pipeline/daily.py' 476 740`), V3, V5.
- **Relevant output:** Targeted pipeline/risk tests passed.
- **Next action:** Extract only after behavior-locking tests exist; no urgent correctness fix.

### ARCH-02

- **Status:** Partially confirmed.
- **Original / corrected severity:** High / Medium.
- **Evidence:** A separate consensus implementation exists in
  `audit/clv_movement.py:40-55`, so duplication and historical drift are real.
- **Counter-evidence:** The report incorrectly treats `roi_engine.py:92-95` as a
  third consensus implementation. It only deserializes `MarketLine` objects.
  `realized_roi_backtest` calls production `_consensus_lines` at `roi_engine.py:218`,
  and `audit/clv.py:77` does the same. Backtest and live therefore share the guard.
- **Commands:** V2 (`Show-Lines 'src/sqp/backtesting/roi_engine.py' 45 305`), V3, V5.
- **Relevant output:** Call search shows live at `daily.py:585`, backtest at `:218`,
  and CLV at `clv.py:77` all call `_consensus_lines`.
- **Next action:** Consider unifying only `clv_movement` with the shared predicate/helper.

### ARCH-03

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** `daily.py:602-612` and `roi_engine.py:159-170` construct the same
  h2h/spread/total probability map with the same sign conventions.
- **Guards/counter-evidence:** Existing parity tests cover outcomes indirectly, but no
  single shared helper or equality invariant prevents future drift.
- **Commands:** V2 (`Show-Lines 'src/sqp/pipeline/daily.py' 601 613` and
  `Show-Lines 'src/sqp/backtesting/roi_engine.py' 159 170`), V5.
- **Next action:** Mechanical shared-helper extraction with parity tests.

### COR-01

- **Status:** Partially confirmed.
- **Original / corrected severity:** High / Medium.
- **Evidence:** V4 reproduced `totals/Under/NaN -> win` and
  `totals/Over/NaN -> loss` at `settle.py:42-44`, independent of score.
- **Guards/counter-evidence:** Normal live candidate construction requires a non-None
  total selected by `_pick_main_lines`, and missing JSON `point` becomes `None`.
  Operational reachability of NaN/inf totals lines was not established because project
  data access is prohibited. The computational defect is real; current frequency is unknown.
- **Commands:** V2 (`Show-Lines 'src/sqp/settlement/settle.py' 21 68`), V4, V5.
- **Relevant output:** Under NaN=`win`; control Under 8.5=`loss` for a 9-run game.
- **Next action:** Add a finite-line guard and first measure affected persisted rows with
  explicit data authorization.

### COR-02

- **Status:** Partially confirmed.
- **Original / corrected severity:** High / Medium.
- **Evidence:** V4 reproduced `spreads/Home/NaN -> loss`; both comparisons on NaN are false.
- **Guards/counter-evidence:** Same reachability constraint as COR-01: ordinary candidate
  generation uses a selected spread point, while project data could not be inspected.
- **Commands:** V2 (`Show-Lines 'src/sqp/settlement/settle.py' 21 68`), V4, V5.
- **Relevant output:** `spreads_home_nan: loss`.
- **Next action:** Handle COR-01 and COR-02 with one finite-line settlement guard and tests.

### COR-03

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** `_consensus_lines` skips `price<=1.0`; `_consensus_counts` counts every
  line. V4 used one valid 1.9 quote and one invalid 1.0 quote for the same key:
  consensus 1.9, count 2.
- **Guards/counter-evidence:** `cons_n.get(key)` is consumed directly by the thin-market
  penalty and persisted. No later correction exists.
- **Commands:** V2 (`Show-Lines 'src/sqp/pipeline/probabilities.py' 17 43`), V4, V5.
- **Next action:** Apply the same usable-line predicate to price aggregation and counts.

### COR-04

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** `lock.py:46-47` continues before both the deadline check and sleep.
  V4 ran the lock in a child process with persistent `Path.stat` failure; it remained
  alive after 0.5 seconds despite `timeout_s=0.05` and had to be terminated.
- **Guards/counter-evidence:** Existing lock tests cover acquisition, stale removal, and
  ordinary timeout, but not persistent `stat()` failure.
- **Commands:** V2 (`Show-Lines 'src/sqp/storage/lock.py' 25 58`), V3, V4, V5.
- **Next action:** Check deadline and sleep on the OSError path; add a non-hanging test.

### COR-05

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** `daily.py:581` obtains a warning and `daily.py:616` continues before
  `served.append` at `:650`. Any non-empty warning excludes every market side.
- **Guards/counter-evidence:** Warnings are constrained to low-sample ratings, unknown
  baseball starters, and already-started events (`sports/base.py:50-54`,
  `sports/adapters.py:186-195`, `daily.py:582-584`). Exclusion may be intentional for
  in-play events, but it contradicts the stated complete served-distribution purpose for
  low-sample/unknown-starter cases. Material frequency was not measured.
- **Commands:** V2 (`Show-Lines 'src/sqp/pipeline/daily.py' 571 664`,
  `Show-Lines 'src/sqp/sports/base.py' 45 55`,
  `Show-Lines 'src/sqp/sports/adapters.py' 186 195`), V3.
- **Next action:** Separate recordability from stake eligibility and measure warning rates.

### QNT-01

- **Status:** Confirmed.
- **Original / corrected severity:** High / Medium.
- **Evidence:** V4 reproduced model 0.60, fair 0.50, shrink 0.50 -> decision 0.55;
  `adjusted_edge` sees gap 0.05 and applies 0.0175, an effective 0.175 coefficient
  on the original 0.10 model-market gap.
- **Guards/counter-evidence:** The composed behavior was reportedly OOS validated and is
  deterministic; this is primarily hidden parameter coupling/documentation error, not a
  demonstrated unsafe behavior. That supports reducing severity.
- **Commands:** V2 (`Show-Lines 'src/sqp/pipeline/probabilities.py' 101 124`,
  `Show-Lines 'src/sqp/markets/edge.py' 32 58`,
  `Show-Lines 'src/sqp/pipeline/daily.py' 628 640`), V4, V5.
- **Next action:** Document the effective coefficient; do not alter behavior without revalidation.

### QNT-02

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** `daily.py:630` computes edge from already-shrunk `p_decision`; `:668`
  compares that value with `max_plausible_edge`.
- **Guards/counter-evidence:** The cap still blocks sufficiently large post-shrink edges,
  and shadow mode currently zeros all stakes. No raw-model plausibility check exists.
- **Commands:** V2 (`Show-Lines 'src/sqp/pipeline/daily.py' 614 704`), V4, V5.
- **Next action:** Document and decide whether plausibility means raw-model or decision edge.

### QNT-03

- **Status:** Confirmed.
- **Original / corrected severity:** High / High.
- **Evidence:** `_consensus_lines` does not reject NaN; both vig guards use comparisons
  that are false for NaN. V4 produced NaN consensus and NaN fair probabilities for both
  outcomes, with only a misleading no-root warning.
- **Guards/counter-evidence:** Downstream comparisons generally suppress staking, limiting
  direct monetary impact, but the event disappears silently. No finite-value invariant exists.
- **Commands:** V2 (`Show-Lines 'src/sqp/pipeline/probabilities.py' 17 68`,
  `Show-Lines 'src/sqp/markets/vig.py' 14 42`), V4, V5.
- **Next action:** Central finite-price predicate plus explicit discarded-line telemetry.

### QNT-04

- **Status:** Confirmed.
- **Original / corrected severity:** High (latent) / High (latent).
- **Evidence:** V4 used 29 NaN rows plus one inf row. `clv_segments` returned n=30,
  median=inf, and `gate_decisions` returned allowed=true.
- **Guards/counter-evidence:** `shadow_mode: true` (`configs/default.yaml:100`) currently
  makes monetary impact zero, and the CLV registry is default-deny when absent. Neither
  guard validates finite gate metrics for post-shadow operation.
- **Commands:** V2 (`Show-Lines 'src/sqp/audit/clv.py' 85 136`,
  `Show-Lines 'src/sqp/risk/clv_gate.py' 20 35`), V3, V4, V5.
- **Next action:** Require finite metrics in both aggregation and gate decision before shadow exit.

### QNT-05

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** The per-event `model_map` can hold up to six sides, each independently
  passed to Kelly. Repository search found no per-event exposure cap.
- **Guards/counter-evidence:** Per-bet, per-league-day, and global-day caps bound total
  exposure; paused/suspect/shadow/CLV gates can zero stakes. None limits concentration
  within one event once real staking is enabled.
- **Commands:** V2 (`Show-Lines 'src/sqp/pipeline/daily.py' 601 725`,
  `Show-Lines 'src/sqp/risk/kelly.py' 14 27`), V3, V5.
- **Next action:** Measure aggregate candidate stake by event before choosing a policy.

### QNT-06

- **Status:** Partially confirmed.
- **Original / corrected severity:** Medium / Low.
- **Evidence:** CLV gate, degradation monitor, and calibrator promotion all use n=30;
  the CLV gate has no uncertainty interval.
- **Counter-evidence:** They are not equivalent bare decisions. Degradation also uses
  Brier/ROI margins and hysteresis; auto-promotion requires prior OOS ECE, Brier, and
  monotonicity gates and is disabled by default (`auto_promote: false`). The report
  overgeneralizes from a shared sample floor.
- **Commands:** V2 (`Show-Lines 'src/sqp/risk/clv_gate.py' 20 35`,
  `Show-Lines 'src/sqp/risk/degradation.py' 31 125`,
  `Show-Lines 'src/sqp/calibration/calibrator.py' 416 453`), V3.
- **Next action:** Strengthen the CLV gate first; review each other threshold separately.

### DAT-01

- **Status:** False positive.
- **Original / corrected severity:** High / None.
- **Evidence:** `load_closing_odds` preserves raw lines, but the actual backtest calls the
  shared production `_consensus_lines` at `roi_engine.py:218`; candidate price comes from
  that filtered consensus at `:227`. Degenerate `<=1.0` lines are therefore discarded by
  the same guard as live production.
- **Guards/counter-evidence:** This shared call is the guard omitted by the report.
- **Commands:** V2 (`Show-Lines 'src/sqp/backtesting/roi_engine.py' 187 263`), V3, V5.
- **Relevant output:** Call search directly links backtest `:218` to the shared helper.
- **Next action:** Remove or rewrite DAT-01; no parity fix is justified by this evidence.

### DAT-02

- **Status:** Partially confirmed.
- **Original / corrected severity:** Medium / Low.
- **Evidence:** `_apply_backtest_daily_cap` implements only the per-league daily cap;
  it has no cross-league portfolio cap.
- **Counter-evidence:** `realized_roi_backtest` is invoked and reported one league at a
  time. There is no combined multi-league backtest portfolio whose exposure claims to
  mirror production. The stated N-times exposure scenario requires an external aggregation
  not demonstrated in the cited code.
- **Commands:** V2 (`Show-Lines 'src/sqp/backtesting/roi_engine.py' 173 184`,
  `Show-Lines 'scripts/validate_oos.py' 130 177`), V3, V5.
- **Next action:** Add a global cap only if a combined portfolio backtest is introduced.

### DAT-03

- **Status:** Partially confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** Candidates are stored as `bookmaker=consensus_median`, not linked to an
  executable account or quote. V4 showed an even-book median can be synthetic.
- **Counter-evidence:** The categorical statement that no bookmaker offers the median is
  false: with an odd number of quotes the median is an observed quote. V4 showed
  `[1.8,2.0,2.2] -> 2.0`, offered=true. Accessibility and limits remain unmodeled.
- **Commands:** V2 (`Show-Lines 'src/sqp/pipeline/probabilities.py' 17 34`,
  `Show-Lines 'src/sqp/pipeline/daily.py' 646 725`), V4.
- **Next action:** Reframe as execution-price availability risk and retain quote provenance.

### DAT-04

- **Status:** Blocked by environment.
- **Original / corrected severity:** High / Medium pending remeasurement.
- **Evidence:** `_served_pending_expired` does count expired pending served rows, and prior
  artifact `.claude/automation/runtime/current-task.md:65` records 54. Independent current
  verification requires reading prohibited project data.
- **Guards/counter-evidence:** Pending rows are explicitly monitored and stale candidates can
  be voided; the current count and correlation with outcomes remain unknown.
- **Commands:** V2 (`Show-Lines 'src/sqp/monitoring/health.py' 78 97`,
  `Show-Lines 'src/sqp/settlement/settle.py' 79 108`). No data command was run.
- **Next action:** With explicit data authorization, rerun the health check and report current
  counts and causes; do not retain High solely from inherited count.

### DAT-05

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** `_match_result` greedily consumes event IDs in `used`. V4 created two
  same-pair/same-day odds events and two results; reversing result order swapped which
  result received `early` versus `late`.
- **Guards/counter-evidence:** Minimum day distance and start-time tie-break make selection
  deterministic for one result, but do not make the global assignment order-independent.
  Chronologically unique dates reduce practical frequency.
- **Commands:** V2 (`Show-Lines 'src/sqp/backtesting/roi_engine.py' 111 146`), V4, V5.
- **Next action:** Sort inputs explicitly and/or solve matching as a global assignment.

### DAT-07

- **Status:** False positive.
- **Original / corrected severity:** Medium / None.
- **Evidence:** `validate_oos.py:148-150` creates `train` strictly before cutoff;
  `_freeze_on_train(train,...)` at `:168` tunes only that subset; ROI is scored with
  `bet_from_date=cutoff` at `:97-100`. The script separately labels full-history params
  as optimistic rather than presenting them as frozen OOS.
- **Guards/counter-evidence:** The report explicitly said this path had not been read.
  Direct inspection resolves the uncertainty in favor of strict separation.
- **Commands:** V2 (`Show-Lines 'scripts/validate_oos.py' 55 177`,
  `Show-Lines 'src/sqp/backtesting/tuning.py' 75 220`).
- **Next action:** Close DAT-07; retain the existing train/test invariant in tests/docs.

### PRF-01

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** On ordinary timeout, `locked` logs and yields without owning a lock.
  Consumers then execute read-modify-write operations.
- **Guards/counter-evidence:** The fail-open behavior is explicitly documented and three
  tests cover acquisition, stale lock, and degraded timeout. Shadow mode reduces monetary
  impact but not lost-update/evidence risk.
- **Commands:** V2 (`Show-Lines 'src/sqp/storage/lock.py' 25 58`), V3, V5.
- **Relevant output:** All existing lock tests pass, confirming this is intentional behavior.
- **Next action:** Surface degraded locking in durable run status; reconsider fail-open before real stakes.

### PRF-02

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** Same defect and reproduction as COR-04; timeout is bypassed under persistent
  `stat()` failure and the child remained alive ten times beyond its configured timeout.
- **Commands:** V2, V4, V5.
- **Next action:** Track remediation under one canonical finding with COR-04 to avoid duplicate work.

### TST-01

- **Status:** Confirmed.
- **Original / corrected severity:** High / High.
- **Evidence:** `test_b08_production_yaml_shadow_survives_unrecognized_env` calls
  `pytest.skip` when `default.yaml` no longer has `shadow_mode: true`. That is the exact
  state the stated safety intent should fail on.
- **Guards/counter-evidence:** Other tests cover parsing and `_zero_stake_flag`, but no test
  found requires production YAML to remain shadowed or records an approved transition.
- **Commands:** V2 (`Show-Lines 'tests/test_audit_2026_07_29.py' 130 152`), V3, V5.
- **Relevant output:** The current targeted suite passes because shadow mode is currently true.
- **Next action:** Replace skip with an explicit fail/approval invariant.

### TST-02

- **Status:** Confirmed.
- **Original / corrected severity:** High / Medium.
- **Evidence:** `test_settle_grade.py` defaults line to NaN for h2h, has one finite spread
  test, and has no totals or non-finite spread/total test. V4 independently reproduces the
  uncovered defect.
- **Guards/counter-evidence:** H2h legitimately ignores line; the fixture itself is not wrong.
  Operational reachability remains unmeasured, reducing severity with COR-01/COR-02.
- **Commands:** V2 (`Show-Lines 'tests/settlement/test_settle_grade.py' 1 58`), V4, V5.
- **Next action:** Add a finite-line parameter matrix before fixing settlement.

### TST-03

- **Status:** Partially confirmed.
- **Original / corrected severity:** Medium / Low.
- **Evidence:** Local `pytest-cov` is absent and coverage has no blocking threshold.
- **Counter-evidence:** CI does produce an informational coverage table on Python 3.12 at
  `.github/workflows/ci.yml:58-62`; therefore "no measurement available" is too broad.
  The measurement is unavailable locally and non-blocking, not nonexistent.
- **Commands:** V2 (`Get-Content -LiteralPath '.github/workflows/ci.yml' -Raw`,
  `Get-Content -LiteralPath 'audit/01-baseline-results.md' -Raw`).
- **Relevant output:** Baseline coverage command rejected unrecognized `--cov` arguments.
- **Next action:** Pin `pytest-cov` in dev dependencies if local reproducibility is desired.

### TST-04

- **Status:** Partially confirmed.
- **Original / corrected severity:** Medium / Low.
- **Evidence:** The six fully qualified module names do not occur in tests, and atomic.py
  lacks targeted fault-path tests.
- **Counter-evidence:** `storage.lock` is directly exercised through the public compatibility
  alias `odds_store._locked`. `tests/test_odds_store.py:64-91` covers acquisition, stale-lock
  breaking, and degraded timeout. The report's statement that lock lacks directed tests is false;
  only persistent-stat and some cross-process paths are missing.
- **Commands:** V3, V2 (`Get-Content -LiteralPath 'tests/test_odds_store.py' -Raw`), V5.
- **Next action:** Add only the missing persistent-stat and atomic failure-path tests.

### TST-05

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Low.
- **Evidence:** No Hypothesis/property framework or `@given` usage exists; the cited pure
  modules use example tests only.
- **Guards/counter-evidence:** Existing examples already assert several core invariants:
  vig sum/bounds, Kelly cap, invalid input rejection, and nonnegative edge penalty. Absence
  of a specific testing style is a quality opportunity, not itself a production defect.
- **Commands:** V3 (`rg -n ... hypothesis|@given ...` and test inventory), V5.
- **Next action:** Add dependency-free parameterized/fuzz loops first; adopt a dependency only by decision.

### OPS-01

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** CI covers 3.11-3.13; local and batch-script runtime is Python 3.14.4,
  with batch files defaulting `SQP_PYTHON` to Python314 and falling back to `python`.
- **Guards/counter-evidence:** The full local suite passes on 3.14.4 and dependencies are
  constrained. That is useful evidence but not a CI gate on the production interpreter.
- **Commands:** V2 (`Get-Content -LiteralPath '.github/workflows/ci.yml' -Raw`), V3,
  `python --version`, and batch-file `Select-String` for `Python314|SQP_PYTHON`.
- **Relevant output:** Python 3.14.4; CI matrix `[3.11,3.12,3.13]`.
- **Next action:** Add 3.14 CI or pin production to a tested matrix version.

### OPS-03

- **Status:** Confirmed.
- **Original / corrected severity:** Medium / Medium.
- **Evidence:** `configs/default.yaml:18-26` describes 0.35 without disclosing the prior
  0.5 shrink; V4 confirms the effective 0.175 coefficient. The plausibility cap is likewise
  applied post-shrink.
- **Guards/counter-evidence:** Comments do say the penalty is model-vs-market and behavior was
  OOS measured, but they do not reveal parameter coupling.
- **Commands:** V2 (`Get-Content` numbered `configs/default.yaml:1-30`), V4.
- **Next action:** Correct comments only; do not alter validated numerical behavior.

### OPS-06

- **Status:** Partially confirmed.
- **Original / corrected severity:** High / Informational (historical, control now present).
- **Evidence:** Prior artifacts document the 2026-08-04 false PASS incident, so the historical
  process failure is supported.
- **Counter-evidence:** The actionable claim that no automatic control exists and B-1 remains
  open is false in the current tree. `scripts/claude_project_health.py:51-80,129-141`
  enforces evidence sections, and `tests/test_claude_system_contract.py:126-149` tests both
  synthetic and live `current-task.md` cases. V5 passed those tests.
- **Commands:** V2 (`Show-Lines 'scripts/claude_project_health.py' 47 141`,
  `Show-Lines 'tests/test_claude_system_contract.py' 81 149`,
  `Show-Lines 'audit/latest/FINDINGS.md' 28 44`), V3, V5.
- **Next action:** Mark the finding closed; keep the enforcement test.

## Overall conclusion

The highest-confidence unresolved risks are QNT-03 (non-finite prices poison
no-vig), QNT-04 (non-finite CLV can approve the post-shadow gate), and TST-01
(the shadow-mode safety test skips in the state it should police). The settlement
NaN behaviors are real but their live reachability is unverified. The audit index
overstates backtest consensus divergence (DAT-01), OOS tuning overlap (DAT-07),
lock test absence (TST-04), and the lack of a PASS-evidence control (OPS-06).
