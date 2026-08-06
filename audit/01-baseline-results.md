# 01 - Baseline validation results

Date: 2026-08-05 (America/Santiago)  
Branch: `audit/full-project`  
Commit: `7871bdb148d174f0ed74cabfa0fa6596638e33f5`  
Runtime: Python 3.14.4 on Windows, pip 26.0.1

## Scope and repository state

This was a read-only baseline verification. No application code, test code,
dependencies, or formatting were changed. The only persistent file created by
this verification is this report.

The worktree was already dirty before verification:

- Modified: `src/sqp/audit/clv.py`, `tests/test_clv.py`.
- Untracked: `PLAN.md`, `REVIEW.md`, `audit/00-audit-plan.md`,
  `observaciones bloqueantes e importantes que sean validas.`, `rc`, `t`, and
  `tatus`.

Those pre-existing files were not modified by this baseline run. The packaging
fallback temporarily created `build/`; it was removed after the command, after
verifying its resolved path was exactly the repository's generated `build/`
directory.

Configuration evidence:

- Test discovery and `src` import path: `pyproject.toml:30-31`.
- MyPy configuration: `pyproject.toml:33-35`.
- Setuptools build backend: `pyproject.toml:22-24`.
- Ruff formatting is explicitly not adopted: `pyproject.toml:41-46`.
- Local aggregate gate: `Makefile:15` (`check: lint types test`).
- CI lint and typing: `.github/workflows/ci.yml:41,49`.
- CI informational coverage: `.github/workflows/ci.yml:58-62`.
- CI dependency audit: `.github/workflows/ci.yml:69-72`.

## Summary

| Check | Exit | Result | Classification |
|---|---:|---|---|
| Full pytest suite | 0 | 637 passed, 0 failed, 0 skipped | Pass |
| Ruff lint | 0 | All checks passed | Pass |
| Ruff format check | 1 | 191 files would be reformatted; 17 already formatted | Expected configuration state; formatter is not adopted |
| MyPy | 0 | No issues in 89 source files | Pass |
| `pip check` | 0 | No broken requirements | Pass |
| `pip-audit` | 0 | No known vulnerabilities | Pass |
| Coverage | 1 | `--cov` arguments unavailable because `pytest-cov` is not installed | Environmental / unavailable tooling |
| Standard `python -m build` | 1 | `No module named build` | Environmental / unavailable tooling |
| Pip wheel fallback | 0 | Built `sqp-1.0.0-py3-none-any.whl` | Pass |
| `make check` | Not run | `make` executable unavailable | Environmental / unavailable tooling |

## Command results

### 1. Full test suite

Exact command:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/ -q
```

- Exit code: `0`.
- Output summary: `637 passed in 65.13s`.
- Test count: 637 passed, 0 failed, 0 skipped.
- Failing tests/checks: none.
- Relevant paths/lines: none; no failures were reported.
- Classification: pass. This validates the current dirty worktree, not a clean
  checkout of the commit named above.

### 2. Ruff linting

Exact command:

```powershell
ruff check src scripts tests
```

- Exit code: `0`.
- Output summary: `All checks passed!`.
- Failing checks: none.
- Relevant paths/lines: none.
- Classification: pass.

### 3. Ruff formatting check

Exact command:

```powershell
ruff format --check src scripts tests
```

- Exit code: `1`.
- Output summary: 191 files would be reformatted; 17 files are already
  formatted.
- Failing checks: formatting differences across `src/`, `scripts/`, and
  `tests/`; Ruff reports file paths but no line numbers for this command.
- Representative paths: `src/sqp/audit/clv.py`, `src/sqp/pipeline/daily.py`,
  `scripts/run_all.py`, and `tests/test_clv.py`.
- Classification: pre-existing/configuration-related, not a configured project
  gate. `pyproject.toml:41-46` explicitly says `ruff format` is not adopted and
  must not be applied. No files were formatted.

### 4. MyPy type checking

Exact command:

```powershell
mypy src
```

- Exit code: `0`.
- Output summary: `Success: no issues found in 89 source files`.
- Failing checks: none.
- Relevant paths/lines: none.
- Classification: pass.

### 5. Installed dependency consistency

Exact command:

```powershell
python -m pip check
```

- Exit code: `0`.
- Output summary: `No broken requirements found.`
- Failing checks: none.
- Classification: pass for the currently installed Python 3.14 environment.

### 6. Dependency vulnerability audit

Exact command:

```powershell
pip-audit -r requirements.lock
```

- Exit code: `0`.
- Output summary: `No known vulnerabilities found`.
- Vulnerability count: 0.
- Failing checks: none.
- Classification: pass against the pinned constraints in `requirements.lock`.

### 7. Coverage reporting

Exact command:

```powershell
$env:PYTHONPATH='src'; python -m pytest tests/ -q --cov=sqp --cov-report=term
```

