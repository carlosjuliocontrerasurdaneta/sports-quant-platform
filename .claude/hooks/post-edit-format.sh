#!/usr/bin/env bash
# PostToolUse (Edit|Write): formatea SOLO el archivo editado si es Python.
set -uo pipefail
input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "${file:-}" ] && exit 0
case "$file" in
  *.py)
    if command -v ruff >/dev/null 2>&1; then
      ruff format "$file" >/dev/null 2>&1 || true
    fi
    ;;
esac
exit 0
