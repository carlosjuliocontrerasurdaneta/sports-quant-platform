#!/usr/bin/env bash
# PostToolUse (Edit|Write): centinela si se toco codigo donde un error cuesta
# dinero. Mismo patron que mark-tests-pending.sh: marcar aqui, exigir en Stop.
# Ambito ESTRECHO a proposito -- cada disparo es una llamada de pago a Codex.
set -uo pipefail
input=$(cat)
file=$(printf '%s' "$input" | python -c "import sys,json; print((json.load(sys.stdin).get('tool_input') or {}).get('file_path',''))" 2>/dev/null)
[ -z "${file:-}" ] && exit 0
case "$file" in
  *configs/*|*src/sqp/risk/*|*src/sqp/calibration/*) ;;
  *) exit 0 ;;
esac
touch "${CLAUDE_PROJECT_DIR:-.}/.claude/.crossreview-pending"
exit 0
