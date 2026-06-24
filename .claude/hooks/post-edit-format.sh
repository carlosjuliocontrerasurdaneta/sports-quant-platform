#!/usr/bin/env bash
# PostToolUse (Edit|Write): auto-fix lint on the edited file if it is Python.
# Uses `ruff check --fix` (NOT `ruff format`): the project uses a deliberate
# compact style (pyproject ignores E701/E702) that `ruff format` would rewrite;
# `ruff check --fix` matches CI and only applies safe lint autofixes. Non-blocking.
# file_path is read from the hook's JSON stdin via python (no jq dependency).
set -uo pipefail
input=$(cat)
file=$(printf '%s' "$input" | python -c "import sys,json; print((json.load(sys.stdin).get('tool_input') or {}).get('file_path',''))" 2>/dev/null)
[ -z "${file:-}" ] && exit 0
case "$file" in
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff check --fix --quiet "$file" >/dev/null 2>&1 || true
    fi
    ;;
esac
exit 0
