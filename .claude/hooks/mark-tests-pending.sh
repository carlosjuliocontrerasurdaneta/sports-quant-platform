#!/usr/bin/env bash
# PostToolUse (Edit|Write|Bash): marca que hay codigo Python modificado en src/,
# tests/ o scripts/ creando un archivo centinela. NO corre tests (eso lo hace
# run-tests-on-stop.sh en el evento Stop, una sola vez por turno, en vez de la
# suite completa tras CADA edicion — ver auditoria 2026-07-02, hallazgo M1).
#
# `scripts/` entro el 2026-09-04 (auditoria integral, AUD-MED-001). El ambito
# era src/ + tests/, pero los tests cargan los scripts DIRECTAMENTE:
# tests/test_daily_picks.py los importa via importlib desde scripts/daily_picks.py
# y tests/test_codex_review.py mete scripts/ai en sys.path. Editar el CLI que
# materializa la REGLA FUNDAMENTAL no armaba el centinela, asi que el gate de
# tests ni se intentaba. El CI ya lintea scripts/ por la misma razon, y la tiene
# escrita en el workflow: un F821 ahi mato en silencio el staging de calibracion
# el 2026-07-01.
#
# `Bash` entro el 2026-09-07 (auditoria integral, AUD-MED-002). El matcher filtra
# por NOMBRE DE HERRAMIENTA, asi que un fichero editado con `sed -i`, un heredoc
# o una redireccion no llegaba aqui NUNCA y el gate de tests no se intentaba, con
# la suite entera creyendose vigilada. Las rutas ya no salen de `file_path` --que
# una llamada Bash no aporta-- sino de `_targets.py`, que las deriva del comando
# y, como red de seguridad, de `git status`. Sobre-disparar aqui es barato:
# significa correr la suite de mas. No dispararse costaba una regresion
# invisible, que es la unica de las dos que hace dano.
set -uo pipefail
input=$(cat)
proyecto="${CLAUDE_PROJECT_DIR:-.}"
# `--with-git`: este hook solo hace `touch`, asi que fallar hacia el lado
# conservador no cuesta nada. Ver la cabecera de `_targets.py` para el reparto.
ficheros=$(printf '%s' "$input" | python "$proyecto/.claude/hooks/_targets.py" --with-git 2>/dev/null)
[ -z "${ficheros:-}" ] && exit 0
while IFS= read -r file; do
  [ -z "$file" ] && continue
  # RECORTE DEL RETORNO DE CARRO (2026-09-07). En Windows `print()` emite CRLF,
  # asi que cada ruta llegaba con un CR final: el glob `*src/*.py` no emparejaba
  # --la cadena ya no acaba en `.py`-- y el bucle las saltaba TODAS en silencio,
  # con exit 0. Un control que parece cableado y no mira nada es exactamente
  # KI-033 otra vez. Se detecto ejercitando el hook con `bash -x`, no leyendolo.
  # `_targets.py` ya fuerza LF; esto es el segundo candado.
  file="${file%$'\r'}"
  # NORMALIZACION DE SEPARADOR (2026-09-05, AUD-001 colateral). En Windows el
  # harness pasa la ruta con CONTRABARRA y los patrones de abajo usan barra
  # normal, asi que NUNCA emparejaban: este hook llevaba meses sin hacer nada.
  # El fallo se escondio porque probarlo a mano con una ruta de barra normal
  # --que el harness no produce nunca-- lo daba por bueno.
  # Se normaliza SOLO para emparejar; $file conserva la ruta original.
  ruta="${file//\\//}"
  case "$ruta" in
    *src/*.py|*tests/*.py|*scripts/*.py)
      touch "$proyecto/.claude/.tests-pending"
      exit 0
      ;;
  esac
done <<< "$ficheros"
exit 0
