#!/usr/bin/env bash
# PostToolUse (Edit|Write): marca que hay codigo Python modificado en src/ o
# tests/ creando un archivo centinela. NO corre tests (eso lo hace
# run-tests-on-stop.sh en el evento Stop, una sola vez por turno, en vez de la
# suite completa tras CADA edicion — ver auditoria 2026-07-02, hallazgo M1).
# file_path se lee del JSON de stdin con python (sin dependencia de jq).
set -uo pipefail
input=$(cat)
file=$(printf '%s' "$input" | python -c "import sys,json; print((json.load(sys.stdin).get('tool_input') or {}).get('file_path',''))" 2>/dev/null)
[ -z "${file:-}" ] && exit 0
case "$file" in
  *src/*.py|*tests/*.py) ;;
  *) exit 0 ;;
esac
touch "${CLAUDE_PROJECT_DIR:-.}/.claude/.tests-pending"
exit 0
