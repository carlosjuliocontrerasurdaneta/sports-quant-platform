#!/usr/bin/env bash
# Instala los dos candados de la sesion 2026-09-02. EJECUTALO TU:  ! bash instalar-candados.sh
#
# Habilita los tres hooks versionados en .claude/hooks/ y te imprime el JSON exacto que falta pegar
# en .claude/settings.json. NO toca settings.json: ese fichero decide que se
# ejecuta en cada turno y debe cambiarlo una persona que lo haya leido.
#
# Candado 1 (PreToolUse/Agent): ningun despacho de subagente sin `model`.
#            Cierra KI-023, que se registro como incerrable y es falso.
# Candado 2 (PostToolUse + Stop): si se toca codigo de riesgo, Codex revisa el
#            diff SIN que nadie lo pida y su veredicto vuelve al modelo.
set -euo pipefail
cd "$(dirname "$0")"
# Los hooks versionados son la unica fuente. No regenerar copias antiguas
# ni sobrescribir ajustes locales al reinstalar. Un paquete incompleto falla
# explicitamente antes de cambiar permisos o sugerir el cableado.
for _h in require-dispatch-model.sh mark-crossreview-pending.sh crossreview-on-stop.sh _targets.py; do
  if [ ! -f ".claude/hooks/${_h}" ]; then
    echo "Falta .claude/hooks/${_h}; restaura el archivo desde la misma version del paquete." >&2
    exit 1
  fi
done

chmod +x .claude/hooks/require-dispatch-model.sh \
         .claude/hooks/mark-crossreview-pending.sh \
         .claude/hooks/crossreview-on-stop.sh 2>/dev/null || true

echo "OK: tres hooks versionados habilitados en .claude/hooks/"
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
echo "  2) En el PostToolUse existente (matcher Edit|Write|Bash), un hook mas:"
echo '     { "type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/mark-crossreview-pending.sh\"", "timeout": 15 }'
echo
echo "  3) En Stop, DESPUES del de tests:"
echo '     { "type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/crossreview-on-stop.sh\"", "timeout": 300 }'
echo
echo "Los hooks se releen al inicio de sesion: abre una nueva para activarlos."
echo "Para desactivar el candado 2: borra su linea de Stop, o vacia el case de"
echo "mark-crossreview-pending.sh. El candado 1 no cuesta nada y no deberia tocarse."
