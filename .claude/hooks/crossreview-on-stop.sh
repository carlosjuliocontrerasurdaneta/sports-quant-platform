#!/usr/bin/env bash
# Stop: si se toco codigo de riesgo, Codex revisa el diff SIN que nadie lo pida y
# su veredicto vuelve al modelo. `exit 2` impide cerrar el turno.
#
# Automatiza lo que durante cinco iteraciones de auditoria no se hizo: la fase 2
# se cumplio con subagentes Claude revisando a subagentes Claude. Cuando por fin
# se invoco a Codex, evito tres errores -- un `abs(line)` que habria fusionado 20
# mercados distintos, un falso positivo en model_vs_market, y dos defectos de
# parseo que dejaban pasar justo los partidos que el cambio filtraba.
set -uo pipefail
input=$(cat)
active=$(printf '%s' "$input" | python -c "import sys,json; print(json.load(sys.stdin).get('stop_hook_active', False))" 2>/dev/null)
[ "$active" = "True" ] && exit 0
cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
marker=".claude/.crossreview-pending"
[ -f "$marker" ] || exit 0
rm -f "$marker"   # se limpia SIEMPRE, antes de nada: nunca bloquear en bucle
command -v codex >/dev/null 2>&1 || exit 0
out=$(codex review --uncommitted \
  "Revisor independiente segun AGENTS.md. Solo defectos sustantivos: fallos
   funcionales, fugas temporales, contaminacion train/test, probabilidades
   invalidas, errores de calibracion o de backtesting, timestamps incorrectos.
   Usa los estados de evidencia y la severidad de AGENTS.md. Si no hay defectos
   confirmados, responde PASS." 2>&1) || true
[ -z "${out:-}" ] && exit 0
{ echo "REVISION CRUZADA AUTOMATICA (Codex) sobre los cambios de este turno:"
  echo
  printf '%s\n' "$out" | tail -60
  echo
  echo "Atiende o REFUTA cada hallazgo antes de cerrar. Refutar es una respuesta"
  echo "valida: Codex ya se ha equivocado antes en este repositorio."; } >&2
exit 2
