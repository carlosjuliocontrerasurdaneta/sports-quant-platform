#!/usr/bin/env bash
# Stop: corre la suite UNA vez por turno si mark-tests-pending.sh dejo el
# centinela (hubo ediciones de codigo en src/, tests/ o scripts/ durante el
# turno). exit 2 => bloquea el cierre del turno y devuelve el fallo a Claude
# para que lo corrija. Reemplaza al antiguo run-tests-after-change.sh
# (PostToolUse), que corria la suite completa tras CADA edicion (auditoria
# 2026-07-02, M1).
#
# `-m "not slow"` NO es opcional (auditoria 2026-09-04, AUD-HIGH-001). Este hook
# corria `pytest tests/` sin filtro y su timeout en settings.json era 300 s. La
# comparacion, medida el 2026-09-04 con el comando EXACTO que ejecutaba:
#
#   PYTHONPATH=src pytest tests/ -q -x --maxfail=1
#     -> 1492 passed, 1 skipped en 1028,19 s (17:08)   <-- 3,4x el timeout
#   pytest -q -m "not slow"
#     -> 1269 passed, 224 deselected en 270,73 s
#
# El harness mataba el hook a los 300 s, asi que el veredicto NUNCA llegaba y el
# turno cerraba en verde con la suite rota. Peor: `rm -f "$marker"` esta solo en
# la rama de exito, asi que el centinela tampoco se limpiaba y el candado no se
# auto-recuperaba. El comentario original decia "la suite completa (~45s)": la
# suite crecio ~23x desde julio y el presupuesto de tiempo no se movio con ella.
# Es la misma averia que este repo lleva denunciando -- un control que se cree
# activo y no lo esta -- y por la que el 2026-09-03 se subio a 600 el timeout del
# hook de Codex; este se quedo en 300 porque nadie lo midio.
#
# Los `slow` (pipeline completo, entrenamientos, walk-forward) los sigue
# ejecutando CI en las patas 3.11/3.13/3.14. Aqui se excluyen a proposito: un
# gate local que no cabe en su timeout no protege nada.
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
if ! PYTHONPATH=src pytest tests/ -q -x --maxfail=1 -m "not slow" >"$log" 2>&1; then
  echo "Tests fallaron tras las ediciones de este turno:" >&2
  tail -25 "$log" >&2
  rm -f "$log"
  exit 2
fi
rm -f "$log" "$marker"
exit 0
