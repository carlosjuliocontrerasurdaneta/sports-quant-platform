# /verification-gate

Before declaring completion:

1. Re-read acceptance criteria in `.claude/automation/runtime/current-task.md`.
2. Map every criterion to concrete evidence.
3. Run focused tests and the smallest relevant regression suite.
4. Run lint/type checks when affected.
5. Apply the active loop's domain gates.
6. Inspect `git diff --check` and the scoped diff.
7. Verify no secrets, debug code, generated artifacts, or unrelated changes were added.
8. Update required Obsidian and memory records.
9. Mark unverified claims explicitly.
10. Stop for approval if commit, release, deployment, promotion, deletion, or production access is next.
