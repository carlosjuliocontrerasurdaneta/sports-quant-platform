#!/usr/bin/env bash
# PostToolUse (Edit|Write): marca que hay codigo Python modificado en src/,
# tests/ o scripts/ creando un archivo centinela. NO corre tests (eso lo hace
# run-tests-on-stop.sh en el evento Stop, una sola vez por turno, en vez de la
# suite completa tras CADA edicion — ver auditoria 2026-07-02, hallazgo M1).
# file_path se lee del JSON de stdin con python (sin dependencia de jq).
#
# `scripts/` entro el 2026-09-04 (auditoria integral, AUD-MED-001). El ambito
# era src/ + tests/, pero los tests cargan los scripts DIRECTAMENTE:
# tests/test_daily_picks.py los importa via importlib desde scripts/daily_picks.py
# y tests/test_codex_review.py mete scripts/ai en sys.path. Editar el CLI que
# materializa la REGLA FUNDAMENTAL no armaba el centinela, asi que el gate de
# tests ni se intentaba. El CI ya lintea scripts/ por la misma razon, y la tiene
# escrita en el workflow: un F821 ahi mato en silencio el staging de calibracion
# el 2026-07-01.
set -uo pipefail
input=$(cat)
file=$(printf '%s' "$input" | python -c "import sys,json; print((json.load(sys.stdin).get('tool_input') or {}).get('file_path',''))" 2>/dev/null)
[ -z "${file:-}" ] && exit 0
case "$file" in
  *src/*.py|*tests/*.py|*scripts/*.py) ;;
  *) exit 0 ;;
esac
touch "${CLAUDE_PROJECT_DIR:-.}/.claude/.tests-pending"
exit 0
