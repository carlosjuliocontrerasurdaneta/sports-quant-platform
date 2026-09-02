#!/usr/bin/env bash
# Instala los dos candados de la sesion 2026-09-02. EJECUTALO TU:  ! bash instalar-candados.sh
#
# Crea tres hooks en .claude/hooks/ y te imprime el JSON exacto que falta pegar
# en .claude/settings.json. NO toca settings.json: ese fichero decide que se
# ejecuta en cada turno y debe cambiarlo una persona que lo haya leido.
#
# Candado 1 (PreToolUse/Agent): ningun despacho de subagente sin `model`.
#            Cierra KI-023, que se registro como incerrable y es falso.
# Candado 2 (PostToolUse + Stop): si se toca codigo de riesgo, Codex revisa el
#            diff SIN que nadie lo pida y su veredicto vuelve al modelo.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .claude/hooks

cat > .claude/hooks/require-dispatch-model.sh <<'HOOK1'
#!/usr/bin/env bash
# PreToolUse (Agent): NINGUN despacho de subagente sin `model` explicito.
#
# Cierra KI-023, registrado el 2026-09-01 como NO cerrable: "el harness no ofrece
# punto de enganche para interceptar un despacho de subagente". Es FALSO. La
# documentacion oficial dice que el matcher de PreToolUse filtra por NOMBRE DE
# HERRAMIENTA, que los despachos aparecen como herramientas normales, y que
# `exit 2` BLOQUEA la llamada devolviendo stderr al modelo. La herramienta se
# llama `Agent` (67 despachos en los transcripts de este proyecto).
#
# NO CLASIFICA a proposito: la politica dice que las cinco clases del disparador
# de escalado no son lexicas, asi que ningun clasificador por palabras clave
# puede asignarlas. Este hook hace imposible la OMISION, que es el fallo real:
# el 2026-09-01 se despacharon ~13 subagentes sin pasar `model` ni una vez.
# Elegir mal sigue siendo posible; olvidarse, no.
#
# FALLA ABIERTO: si el JSON no parsea o falta python, deja pasar. Es un candado
# de proceso, no un control de seguridad, y un guard roto que paralizase toda la
# delegacion seria peor que no tenerlo.
set -uo pipefail
input=$(cat)
modelo=$(printf '%s' "$input" | python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(str((d.get('tool_input') or {}).get('model') or '').strip())
except Exception:
    print('__PARSE_FAIL__')
" 2>/dev/null || echo '__PARSE_FAIL__')
# OJO: sin `:-`. Con `${modelo:-__PARSE_FAIL__}` un `model` AUSENTE (cadena
# vacia) se confundia con un fallo de parseo y el hook no bloqueaba NUNCA.
# Detectado probando el comportamiento; la sintaxis era valida.
[ "$modelo" = "__PARSE_FAIL__" ] && exit 0
[ -n "$modelo" ] && exit 0
cat >&2 <<'MSG'
DESPACHO BLOQUEADO: falta el parametro `model`.

La REGLA DE DESPACHO de .claude/automation/MODEL_ROUTING.md exige asignar el
modelo AL DELEGAR con el parametro `model` de la herramienta Agent, que tiene
precedencia sobre el frontmatter. Sin el, el subagente hereda `opus` y "delegar
por complejidad" no ocurre.

  haiku  : busqueda o resumen acotado
  sonnet : ingenieria normal
  opus   : punto de partida por defecto
  fable  : TECHO. Las cinco clases del disparador van aqui -- trabajo
           irreversible; parametros de riesgo/modelo/estrategia/umbral/gate;
           cifras publicables; contradecir una decision registrada; cambiar el
           contrato de un artefacto persistido.

Ante la duda entre dos escalones, se sube, y se registra en
.claude/automation/runtime/current-task.md.
MSG
exit 2
HOOK1

cat > .claude/hooks/mark-crossreview-pending.sh <<'HOOK2'
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
HOOK2

cat > .claude/hooks/crossreview-on-stop.sh <<'HOOK3'
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
HOOK3

chmod +x .claude/hooks/require-dispatch-model.sh \
         .claude/hooks/mark-crossreview-pending.sh \
         .claude/hooks/crossreview-on-stop.sh 2>/dev/null || true

echo "OK: tres hooks creados en .claude/hooks/"
echo
echo "FALTA cablearlos. En .claude/settings.json -> \"hooks\":"
echo
echo "  1) Bloque NUEVO al mismo nivel que PostToolUse y Stop:"
cat <<'JSON'
     "PreToolUse": [
       { "matcher": "Agent",
         "hooks": [{ "type": "command",
           "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/require-dispatch-model.sh\"",
           "timeout": 15 }] }
     ]
JSON
echo "  2) En el PostToolUse existente (matcher Edit|Write), un hook mas:"
echo '     { "type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/mark-crossreview-pending.sh\"", "timeout": 15 }'
echo
echo "  3) En Stop, DESPUES del de tests:"
echo '     { "type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/crossreview-on-stop.sh\"", "timeout": 300 }'
echo
echo "Los hooks se releen al inicio de sesion: abre una nueva para activarlos."
echo "Para desactivar el candado 2: borra su linea de Stop, o vacia el case de"
echo "mark-crossreview-pending.sh. El candado 1 no cuesta nada y no deberia tocarse."
