#!/usr/bin/env bash
# PostToolUse (Edit|Write|Bash): centinela si se toco codigo donde un error cuesta
# dinero. Mismo patron que mark-tests-pending.sh: marcar aqui, exigir en Stop.
# Ambito ESTRECHO a proposito -- cada disparo es una llamada de pago a Codex.
#
# `Bash` entro el 2026-09-07 (auditoria integral, AUD-MED-002): el matcher filtra
# por NOMBRE DE HERRAMIENTA, asi que editar `configs/`, `src/sqp/risk/` o
# `src/sqp/calibration/` con `sed` o un heredoc no armaba nada y la revision
# cruzada del codigo del dinero no llegaba a pedirse.
#
# A DIFERENCIA de mark-tests-pending, aqui NO se usa `--with-git`: esa red de
# seguridad sobre-dispara a proposito, y sobre-disparar este hook gasta cuota de
# pago de Codex en turnos que no tocaron codigo de riesgo. Solo se atiende a lo
# que el comando NOMBRA. Correr tests de mas es gratis; pedir una revision de
# pago de mas, no.
set -uo pipefail
input=$(cat)
proyecto="${CLAUDE_PROJECT_DIR:-.}"
ficheros=$(printf '%s' "$input" | python "$proyecto/.claude/hooks/_targets.py" 2>/dev/null)
[ -z "${ficheros:-}" ] && exit 0
while IFS= read -r file; do
  [ -z "$file" ] && continue
  # RECORTE DEL RETORNO DE CARRO (2026-09-07). En Windows `print()` emite CRLF,
  # asi que cada ruta llegaba con un CR final y el glob no emparejaba nunca: el
  # bucle las saltaba TODAS en silencio, con exit 0 (misma clase que KI-033).
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
    *configs/*|*src/sqp/risk/*|*src/sqp/calibration/*)
      touch "$proyecto/.claude/.crossreview-pending"
      exit 0
      ;;
  esac
done <<< "$ficheros"
exit 0
