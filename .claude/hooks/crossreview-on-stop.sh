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

# SIN prompt inline (2026-09-05). `--uncommitted`, `--base`, `--commit` y el
# [PROMPT] posicional son selectores de ALCANCE mutuamente excluyentes:
# combinarlos aborta con "the argument '--uncommitted' cannot be used with
# '[PROMPT]'". Este hook llevaba desde que se escribio con esa invocacion
# invalida y nunca se supo, porque tampoco llegaba a dispararse (KI-031, bug del
# separador de rutas). Dos averias apiladas: la de fuera escondia la de dentro.
#
# Las instrucciones del revisor NO se pierden: viven en AGENTS.md, que Codex
# carga solo. El prompt inline las duplicaba, que es justo la deriva entre
# copias que este repositorio lleva meses pagando.

# QUE revisar. El hook corre en el Stop, y para entonces el trabajo del turno
# puede estar ya commiteado -- con `--uncommitted` a secas la revision saldria
# vacia justo en los turnos que mas importan. Se mira si queda algo sin
# commitear DENTRO del ambito vigilado (el mismo de mark-crossreview-pending);
# si no, se revisa el ultimo commit. `NOTAS.md` y demas ficheros del operador
# quedan fuera del ambito a proposito: estan siempre modificados y elegirian
# `--uncommitted` para siempre.
pendiente=$(git status --porcelain -- configs src/sqp/risk src/sqp/calibration 2>/dev/null)
if [ -n "$pendiente" ]; then
  alcance="--uncommitted"
else
  alcance="--commit HEAD"
fi
# El codigo de salida se CONSERVA. Antes se tiraba con `|| true` y cualquier
# salida no vacia se presentaba bajo el encabezado de hallazgos, asi que un fallo
# de INFRAESTRUCTURA llegaba disfrazado de veredicto (KI-035). Paso dos veces el
# 2026-09-06: primero con la cuota de Codex agotada, y el mensaje "You've hit
# your usage limit" aparecio bajo "Atiende o REFUTA cada hallazgo"; despues con
# 65 PermissionError sobre el tmpdir de pytest.
#
# El riesgo no es cosmetico: invita al modelo a "atender o refutar" hallazgos que
# no existen, y en un repositorio cuya enfermedad cronica es que un control diga
# algo distinto de lo que mide, esto es esa enfermedad dentro del propio control.
out=$(codex review $alcance 2>&1)
rc=$?
[ -z "${out:-}" ] && exit 0

# Fallo de infraestructura: la revision NO se ejecuto. Se detecta por codigo de
# salida Y por patrones conocidos, porque `codex review` puede salir con 0
# habiendo abortado (la cuota agotada del 2026-09-06 lo hizo).
if [ "$rc" -ne 0 ] || printf '%s' "$out" | grep -qiE \
     "usage limit|Review was interrupted|failed to refresh available models|rate.?limit|401 Unauthorized|ECONNREFUSED"; then
  { echo "LA REVISION CRUZADA NO SE EJECUTO (fallo de entorno, codigo $rc)."
    echo
    printf '%s\n' "$out" | tail -25
    echo
    echo "Esto NO son hallazgos: no hay nada que atender ni que refutar. El"
    echo "cambio de este turno se queda SIN revisar por un tercero."
    echo "El centinela se deja puesto para reintentarlo en el turno siguiente."; } >&2
  # Se restaura el centinela: la revision queda APLAZADA, no saltada en silencio.
  # No hay riesgo de bucle porque esta rama NO bloquea (exit 0): el turno cierra
  # y el siguiente vuelve a intentarlo cuando la cuota o el entorno se recuperen.
  #
  # Bloquear aqui no serviria de nada -- el modelo no puede arreglar una cuota
  # agotada -- y dejaria el turno sin salida.
  touch "$marker" 2>/dev/null || true
  exit 0
fi

{ echo "REVISION CRUZADA AUTOMATICA (Codex) sobre los cambios de este turno:"
  echo
  printf '%s\n' "$out" | tail -60
  echo
  echo "Atiende o REFUTA cada hallazgo antes de cerrar. Refutar es una respuesta"
  echo "valida: Codex ya se ha equivocado antes en este repositorio."; } >&2
exit 2
