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
# Tres patrones (auditoria 2026-07-29, S-9: el original exigia comillas, asi que
# `set ODDS_API_KEY=abc...` en un .bat y `key: valor` en YAML pasaban sin detectar):
#   1. asignacion con comillas   API_KEY = "valor"
#   2. asignacion sin comillas   set API_KEY=valor   /   API_KEY=valor  (.bat, .env)
#   3. separador de dos puntos   api_key: valor      (YAML)
#   4. tokens con prefijo reconocible, sin necesidad de nombre de variable
_names='(API_KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)'
hits=$(grep -niE "(${_names}[A-Z0-9_]*[[:space:]]*=[[:space:]]*[\"'][^\"']{8,}[\"'])|(${_names}[A-Z0-9_]*[[:space:]]*=[[:space:]]*[^[:space:]\"';#]{8,})|(${_names}[A-Z0-9_]*[[:space:]]*:[[:space:]]*[^[:space:]\"'#]{8,})|(sk-[A-Za-z0-9_-]{20,})|(Bearer[[:space:]]+[A-Za-z0-9._-]{20,})" "$file" 2>/dev/null \
  | grep -vE 'os\.environ|getenv|dotenv|environ\.get|\$\{|\$env:|%[A-Za-z_]+%|\bexample\b|placeholder|changeme|dummy|your_|xxx|<[A-Za-z_]+>' || true)
if [ -n "$hits" ]; then
  echo "Posible secreto hardcodeado en $file:" >&2
  echo "$hits" >&2
  echo "Usar variables de entorno (.env + os.environ), nunca literales." >&2
  exit 2
fi
exit 0
