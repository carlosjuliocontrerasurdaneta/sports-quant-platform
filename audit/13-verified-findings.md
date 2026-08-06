# 13 - Verified findings only

This list contains only findings independently classified as **Confirmed** or
**Partially confirmed** in `audit/12-verification-report.md`. False positives
(DAT-01, DAT-07) and the environment-blocked DAT-04 are excluded.

Ordering uses corrected severity first, then estimated likelihood, impact, and
lower remediation effort. "Likelihood" describes practical reachability, not
confidence in the verification status.

| Rank | Finding | Status | Corrected severity | Likelihood | Impact | Effort | Prioritized next action |
|---:|---|---|---|---|---|---|---|
| 1 | QNT-03 | Confirmed | High | Medium | High | Medium | Reject non-finite prices through one shared usable-line predicate and add discard telemetry. |
| 2 | TST-01 | Confirmed | High | Low | Critical after shadow transition | Small | Make production shadow-mode deactivation fail unless an explicit approval invariant is met. |
| 3 | QNT-04 | Confirmed | High (latent) | Low while shadowed | Critical after shadow transition | Small | Require finite CLV metrics in aggregation and gate decisions before allowing shadow exit. |
| 4 | COR-03 | Confirmed | Medium | High | Medium | Small | Apply the consensus usable-line predicate to `books_count`. |
| 5 | COR-05 | Confirmed | Medium | High | Medium | Small/Medium | Separate served-stream recording from warning-based stake exclusion; measure warning frequency. |
| 6 | QNT-01 | Confirmed | Medium | High | Medium | Small | Document the effective 0.175 coupling; preserve behavior unless revalidated. |
| 7 | QNT-02 | Confirmed | Medium | High | Medium | Small | Decide and document whether plausibility applies to raw-model or post-shrink edge. |
| 8 | OPS-03 | Confirmed | Medium | High | Medium | Small | Correct YAML comments for shrink/penalty coupling without changing values. |
| 9 | OPS-01 | Confirmed | Medium | High | Medium | Small | Add Python 3.14 to CI or run production on a tested version. |
| 10 | TST-02 | Confirmed | Medium | High (coverage gap) | Medium | Small | Add non-finite spread/total grading tests before changing settlement. |
| 11 | ARCH-03 | Confirmed | Medium | High (duplication exists) | Medium | Small | Share the `_model_map` helper and add parity coverage. |
| 12 | ARCH-01 | Confirmed | Medium | High (structure exists) | Medium | Medium | Extract the market-scoring loop only after behavior-locking tests. |
| 13 | DAT-03 | Partially confirmed | Medium | High | Medium | Medium | Preserve bookmaker quote provenance and model executable-price availability. |
| 14 | DAT-05 | Confirmed | Medium | Medium | Medium | Small | Make result-to-odds assignment order-independent or explicitly sorted. |
| 15 | ARCH-02 | Partially confirmed | Medium | Medium | Medium | Medium | Unify `clv_movement` consensus behavior; backtest/live already share the main helper. |
| 16 | QNT-05 | Confirmed | Medium | Medium after real staking | High | Medium | Measure and then cap aggregate stake by event if concentration is material. |
| 17 | PRF-01 | Confirmed | Medium | Low/Medium | High | Small | Persist degraded-lock status and revisit fail-open before real staking. |
| 18 | COR-04 | Confirmed | Medium | Low | High availability impact | Small | Enforce deadline and sleep when lock `stat()` raises persistently. |
| 19 | PRF-02 | Confirmed | Medium | Low | High availability impact | Small | Track with COR-04 as the same defect, not a separate remediation. |
| 20 | COR-01 | Partially confirmed | Medium | Low/unmeasured | High data-integrity impact | Small plus data audit | Void non-finite totals lines; first measure persisted reachability with authorization. |
| 21 | COR-02 | Partially confirmed | Medium | Low/unmeasured | High data-integrity impact | Small plus data audit | Use the same finite-line guard as COR-01 and measure exposure. |
| 22 | TST-03 | Partially confirmed | Low | High | Low | Small | Pin `pytest-cov` locally if reproducible coverage is desired; CI already reports it. |
| 23 | TST-04 | Partially confirmed | Low | High (remaining gaps exist) | Medium | Small | Add only persistent-stat and atomic failure-path tests; retain existing lock tests. |
| 24 | TST-05 | Confirmed | Low | High (strategy gap exists) | Low/Medium | Medium | Add dependency-free invariant/fuzz loops before considering a new property-test dependency. |
| 25 | QNT-06 | Partially confirmed | Low | Medium | Medium | Medium | Strengthen CLV inference first; assess degradation and promotion thresholds separately. |
| 26 | DAT-02 | Partially confirmed | Low | Low | Medium only for a future combined portfolio | Medium | Add a global cap only when a combined multi-league portfolio backtest exists. |
| 27 | OPS-06 | Partially confirmed | Informational / closed | Historical | High historical process impact | None | Mark closed and retain the existing automated evidence-contract tests. |

## Excluded after verification

- **DAT-01 - False positive:** backtest calls the shared production consensus filter.
- **DAT-07 - False positive:** `validate_oos.py` tunes strictly on the pre-cutoff train set.
- **DAT-04 - Blocked by environment:** current pending-row count requires prohibited project-data access.
