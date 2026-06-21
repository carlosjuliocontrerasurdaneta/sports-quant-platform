#!/usr/bin/env bash
# PostToolUse (Edit|Write): corre pytest SOLO si se editó código en src/ o tests/.
# exit 2 => devuelve el fallo a Claude para que lo corrija.
set -uo pipefail
input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "${file:-}" ] && exit 0
case "$file" in
  *src/*.py|*tests/*.py) ;;
  *) exit 0 ;;
esac
command -v pytest >/dev/null 2>&1 || exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
log=$(mktemp)
if ! PYTHONPATH=src pytest tests/ -q -x --maxfail=1 >"$log" 2>&1; then
  echo "Tests fallaron tras editar $file:" >&2
  tail -25 "$log" >&2
  rm -f "$log"
  exit 2
fi
rm -f "$log"
exit 0
