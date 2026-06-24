#!/usr/bin/env bash
# PostToolUse (Edit|Write): detecta secretos hardcodeados SOLO en el archivo editado.
# exit 2 => Claude recibe el aviso por stderr y debe corregirlo.
# file_path se lee del JSON de stdin con python (sin dependencia de jq).
set -uo pipefail
input=$(cat)
file=$(printf '%s' "$input" | python -c "import sys,json; print((json.load(sys.stdin).get('tool_input') or {}).get('file_path',''))" 2>/dev/null)
[ -z "${file:-}" ] && exit 0
[ -f "$file" ] || exit 0
case "$file" in
  */data/*|*/historical/*|*/exports/*|*/logs/*|*.md) exit 0 ;;
esac
hits=$(grep -nE '(API_KEY|APIKEY|SECRET|TOKEN|PASSWORD)[A-Z0-9_]*[[:space:]]*=[[:space:]]*["'"'"'][^"'"'"']{8,}["'"'"']' "$file" 2>/dev/null \
  | grep -vE 'os\.environ|getenv|dotenv|\$\{|\bexample\b|placeholder|changeme|dummy' || true)
if [ -n "$hits" ]; then
  echo "Posible secreto hardcodeado en $file:" >&2
  echo "$hits" >&2
  echo "Usar variables de entorno (.env + os.environ), nunca literales." >&2
  exit 2
fi
exit 0
