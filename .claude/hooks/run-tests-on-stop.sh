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
#
# VOLVIO A NO CABER (auditoria integral 2026-09-22, AUD-007). El presupuesto se
# fijo en 600 s contra una medicion de 270,73 s, y la suite siguio creciendo sin
# que nadie volviera a medir. Serie del MISMO subconjunto, con el comando exacto
# de abajo:
#
#   2026-09-04  1269 pruebas  270,73 s   45 % del presupuesto
#   2026-09-18  1967 pruebas  489,76 s   82 %
#   2026-09-22  2040 pruebas  796,09 s   133 %   <-- el harness lo mataba
#
# Dos cambios, porque el fallo tenia dos mitades. (1) El presupuesto del hook
# sube a 1200 s en settings.json. (2) Y sobre todo: el script se AUTOACOTA con
# `timeout`, porque un proceso que mata el harness no ejecuta ni una linea mas
# -- ni el `rm -f "$marker"`, ni un mensaje de error --, asi que la puerta moria
# MUDA y el turno cerraba en verde. Con un presupuesto propio por debajo del del
# harness, el script siempre gana la carrera y puede decir lo que paso. Es la
# misma disciplina que `crossreview-on-stop.sh`: un fallo de infraestructura se
# anuncia como tal, nunca se disfraza de veredicto ni de silencio.
set -uo pipefail
# Por debajo del timeout del hook (1200 s en settings.json) para que el aviso
# salga de aqui y no del harness. Con 796 s medidos deja ~35 % de margen.
PRESUPUESTO_S=1080
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
# `timeout` acota el trabajo DENTRO del script. Si no esta disponible se corre
# igual: perder el auto-acotado es peor que no correr la suite.
if command -v timeout >/dev/null 2>&1; then
  PYTHONPATH=src timeout "$PRESUPUESTO_S" pytest tests/ -q -x --maxfail=1 -m "not slow" >"$log" 2>&1
else
  PYTHONPATH=src pytest tests/ -q -x --maxfail=1 -m "not slow" >"$log" 2>&1
fi
rc=$?

# 124 = `timeout` corto la ejecucion. NO son tests en rojo: la suite no llego a
# terminar, asi que no hay veredicto. Se dice en voz alta y se sale sin bloquear
# (el modelo no puede acortar la suite a mitad de turno), pero el centinela se
# DEJA puesto: "no se pudo comprobar" no es "esta bien", y olvidarlo en silencio
# es exactamente la averia que este bloque existe para impedir.
if [ "$rc" -eq 124 ]; then
  { echo "LA SUITE NO CABE EN SU PRESUPUESTO (${PRESUPUESTO_S}s): NO HAY VEREDICTO."
    echo "Los cambios de este turno se quedan SIN comprobar por la suite local."
    echo "Ultimas lineas antes del corte:"
    tail -15 "$log"
    echo
    echo "Volver a medir y subir PRESUPUESTO_S y el timeout del hook en"
    echo ".claude/settings.json, o acotar el alcance de la suite del hook."
    echo "Ver audit/latest/FINDINGS.md AUD-007 (ronda audit-2026-09-22)."; } >&2
  rm -f "$log"
  exit 0
fi

if [ "$rc" -ne 0 ]; then
  echo "Tests fallaron tras las ediciones de este turno:" >&2
  tail -25 "$log" >&2
  rm -f "$log"
  exit 2
fi
rm -f "$log" "$marker"
exit 0
