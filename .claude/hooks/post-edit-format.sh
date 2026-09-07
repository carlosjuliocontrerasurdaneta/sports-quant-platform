#!/usr/bin/env bash
# PostToolUse (Edit|Write): auto-fix lint on the edited file if it is Python.
# Uses `ruff check --fix` (NOT `ruff format`): the project uses a deliberate
# compact style (pyproject ignores E701/E702) that `ruff format` would rewrite;
# `ruff check --fix` matches CI and only applies safe lint autofixes. Non-blocking.
# file_path is read from the hook's JSON stdin via python (no jq dependency).
#
# SE QUEDA EN `Edit|Write` A PROPOSITO (auditoria integral 2026-09-07,
# AUD-MED-002). Los otros tres hooks de este grupo se ampliaron a `Bash` porque
# son CONTROLES que estaban en silencio; este no lo es y ademas es el unico que
# MUTA ficheros. Con Bash no hay `file_path`: habria que deducir la ruta del
# comando, y entonces un simple `cat src/x.py` -- que solo LEE -- dispararia un
# `ruff check --fix` sobre ese fichero. Convertir una lectura en una escritura es
# un modo de fallo nuevo que nadie pidio, y el precio de no cubrir Bash aqui es
# bajo: `ruff check` es puerta BLOQUEANTE de CI y `run-tests-on-stop.sh` corre la
# suite en cada turno con ediciones, asi que un autofix omitido se convierte en
# un hallazgo visible, no en un agujero silencioso. La asimetria es deliberada:
# los hooks que solo leen fallan hacia escanear de mas; el que escribe, no.
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
