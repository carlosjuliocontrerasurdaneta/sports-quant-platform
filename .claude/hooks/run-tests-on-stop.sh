#!/usr/bin/env bash
# Stop: corre la suite completa UNA vez por turno si mark-tests-pending.sh dejo
# el centinela (hubo ediciones de codigo en src/ o tests/ durante el turno).
# exit 2 => bloquea el cierre del turno y devuelve el fallo a Claude para que
# lo corrija. Reemplaza al antiguo run-tests-after-change.sh (PostToolUse), que
# corria la suite completa (~45s) tras CADA edicion (auditoria 2026-07-02, M1).
set -uo pipefail
input=$(cat)
# Guard anti-bucle: si este Stop ya fue provocado por un hook Stop previo y los
# tests vuelven a fallar, no bloquear indefinidamente.
active=$(printf '%s' "$input" | python -c "import sys,json; print(json.load(sys.stdin).get('stop_hook_active', False))" 2>/dev/null)
[ "$active" = "True" ] && exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
marker=".claude/.tests-pending"
[ -f "$marker" ] || exit 0
command -v pytest >/dev/null 2>&1 || { rm -f "$marker"; exit 0; }
log=$(mktemp)
if ! PYTHONPATH=src pytest tests/ -q -x --maxfail=1 >"$log" 2>&1; then
  echo "Tests fallaron tras las ediciones de este turno:" >&2
  tail -25 "$log" >&2
  rm -f "$log"
  exit 2
fi
rm -f "$log" "$marker"
exit 0
