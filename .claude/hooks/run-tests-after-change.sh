#!/usr/bin/env bash
# PostToolUse (Edit|Write): corre pytest SOLO si se editó código en src/ o tests/.
# exit 2 => devuelve el fallo a Claude para que lo corrija.
# file_path se lee del JSON de stdin con python (sin dependencia de jq).
# NOTA: corre la suite completa; si crece el tiempo, considerar acotar a los
# tests afectados o mover este hook al evento Stop.
set -uo pipefail
input=$(cat)
file=$(printf '%s' "$input" | python -c "import sys,json; print((json.load(sys.stdin).get('tool_input') or {}).get('file_path',''))" 2>/dev/null)
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
