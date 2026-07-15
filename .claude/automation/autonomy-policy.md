# Autonomy Policy

## Allowed without additional approval

- Read repository files allowed by settings.
- Search code and documentation.
- Create plans and task records.
- Modify source, tests, local documentation and `.claude` instructions within task scope.
- Run local lint, type checks, tests and non-production scripts that do not consume paid services.
- Create local reports.

## Approval required

- Git commit, push, merge, reset, tag or branch publication.
- Deployment, release, package publication or model/calibration promotion.
- Production database/API access.
- Paid API calls or large remote downloads.
- Deleting data, migrations with destructive potential, secret rotation.
- Increasing risk/staking/exposure limits.
- Broad changes outside the approved scope.

## Bounded operation

- Default: at most 8 implementation iterations.
- At most 3 materially different hypotheses for one blocker.
- At most one broad full-suite run after focused tests unless evidence requires another.
- Never claim success when a command was not run.
