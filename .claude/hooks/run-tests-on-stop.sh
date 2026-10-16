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
# SUITE RAPIDA + VEREDICTO EN TRES ESTADOS (CLAUDE-005 / H-2, 2026-10-14). El
# subconjunto `not slow` volvio a llenar el presupuesto entero: 2946 passed en
# 1080,43 s medidos el 2026-10-14 contra el autoacotado de 1080 s, asi que el
# `timeout` cortaba siempre. Y sin `pytest` en el PATH este script BORRABA el
# centinela sin comprobar nada. La logica vive ahora en `_stop_tests.py` (Python
# se puede probar directamente; `subprocess` en esta maquina resuelve el bash de
# WSL): suite rapida obligatoria `-m "not slow and not heavy"`, los `heavy`
# relacionados con los ficheros modificados, y tres veredictos -- PASS, FAIL y
# NO VERIFICADO --. NO VERIFICADO sale con 0 y NO BLOQUEA el cierre del turno
# (bloquear solo produciria un bucle: el modelo no puede acortar la suite), pero
# CONSERVA el centinela pendiente y lo anuncia; nunca es una validacion
# satisfactoria. CI sigue corriendo la suite COMPLETA (`pytest -q`).
set -uo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
if ! command -v python >/dev/null 2>&1; then
  # Sin interprete no hay veredicto: se anuncia y el centinela se CONSERVA.
  if [ -f ".claude/.tests-pending" ]; then
    echo "Tests locales: NO VERIFICADO. python no esta disponible; el centinela .claude/.tests-pending sigue pendiente. Esto NO es una validacion satisfactoria." >&2
  fi
  exit 0
fi
exec python ".claude/hooks/_stop_tests.py"
