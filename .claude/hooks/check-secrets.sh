#!/usr/bin/env bash
# PostToolUse (Edit|Write): detecta secretos hardcodeados SOLO en el archivo editado.
# exit 2 => Claude recibe el aviso por stderr y debe corregirlo.
set -uo pipefail
input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
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
