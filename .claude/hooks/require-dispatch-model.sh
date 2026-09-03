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
