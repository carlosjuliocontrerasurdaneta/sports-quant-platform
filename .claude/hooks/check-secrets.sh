#!/usr/bin/env bash
# PostToolUse (Edit|Write|Bash): detecta secretos hardcodeados en los archivos que
# la llamada toco. exit 2 => Claude recibe el aviso por stderr y debe corregirlo.
#
# `Bash` entro el 2026-09-07 (auditoria integral, AUD-MED-002). El matcher filtra
# por NOMBRE DE HERRAMIENTA y este hook sacaba la ruta de `tool_input.file_path`,
# que una llamada Bash no aporta: una clave escrita con `sed -i`, un heredoc o
# una redireccion NO pasaba por aqui. Un detector de secretos que solo mira una
# de las dos puertas por las que se escribe no es un detector.
#
# Usa `--with-git`: este hook solo LEE, asi que escanear de mas es barato y no
# escanear es lo caro. Ver la cabecera de `_targets.py` para el reparto.
set -uo pipefail
input=$(cat)
proyecto="${CLAUDE_PROJECT_DIR:-.}"
ficheros=$(printf '%s' "$input" | python "$proyecto/.claude/hooks/_targets.py" --with-git 2>/dev/null)
[ -z "${ficheros:-}" ] && exit 0
# Tres patrones (auditoria 2026-07-29, S-9: el original exigia comillas, asi que
# `set ODDS_API_KEY=abc...` en un .bat y `key: valor` en YAML pasaban sin detectar):
#   1. asignacion con comillas   API_KEY = "valor"
#   2. asignacion sin comillas   set API_KEY=valor   /   API_KEY=valor  (.bat, .env)
#   3. separador de dos puntos   api_key: valor      (YAML)
#   4. tokens con prefijo reconocible, sin necesidad de nombre de variable
_names='(API_KEY|APIKEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL)'
_patron="(${_names}[A-Z0-9_]*[[:space:]]*=[[:space:]]*[\"'][^\"']{8,}[\"'])|(${_names}[A-Z0-9_]*[[:space:]]*=[[:space:]]*[^[:space:]\"';#]{8,})|(${_names}[A-Z0-9_]*[[:space:]]*:[[:space:]]*[^[:space:]\"'#]{8,})|(sk-[A-Za-z0-9_-]{20,})|(Bearer[[:space:]]+[A-Za-z0-9._-]{20,})"
_ruido='os\.environ|getenv|dotenv|environ\.get|\$\{|\$env:|%[A-Za-z_]+%|\bexample\b|placeholder|changeme|dummy|your_|xxx|<[A-Za-z_]+>'
encontrado=""
while IFS= read -r file; do
  [ -z "$file" ] && continue
  # RECORTE DEL RETORNO DE CARRO (2026-09-07). En Windows `print()` emite CRLF,
  # asi que cada ruta llegaba con un CR final y `[ -f "$file" ]` fallaba: el
  # bucle recorria los ficheros y los saltaba TODOS, en silencio y con exit 0.
  # Un detector que parece cableado y no abre ni un fichero es KI-033 otra vez.
  # Se detecto ejercitando el hook con `bash -x`, no leyendolo. `_targets.py` ya
  # fuerza LF; esto es el segundo candado.
  file="${file%$'\r'}"
  [ -f "$file" ] || continue
  # NORMALIZACION DE SEPARADOR (2026-09-05, AUD-001 colateral). En Windows el
  # harness pasa la ruta con CONTRABARRA y los patrones de abajo usan barra
  # normal, asi que NUNCA emparejaban: este hook llevaba meses sin hacer nada.
  # El fallo se escondio porque probarlo a mano con una ruta de barra normal
  # --que el harness no produce nunca-- lo daba por bueno.
  # Se normaliza SOLO para emparejar; $file conserva la ruta original.
  ruta="${file//\\//}"
  # Se excluyen SOLO directorios de datos, que no se versionan. `*.md` estaba en
  # esta lista y no pinta nada aqui: `Obsidian/` (56 ficheros) y `docs/` (35) SI
  # estan rastreados por git, asi que una clave pegada en una nota o en un runbook
  # atravesaba el hook y llegaba al commit (AUD-LOW-002, 2026-09-06). El patron 4
  # de abajo -- tokens con prefijo reconocible, sin nombre de variable -- esta
  # pensado justo para texto en prosa, que es donde una clave se pega sin pensar.
  case "$ruta" in
    */data/*|*/historical/*|*/exports/*|*/logs/*) continue ;;
  esac
  hits=$(grep -niE "$_patron" "$file" 2>/dev/null | grep -vE "$_ruido" || true)
  if [ -n "$hits" ]; then
    encontrado="${encontrado}${file}:
${hits}
"
  fi
done <<< "$ficheros"
if [ -n "$encontrado" ]; then
  echo "Posible secreto hardcodeado:" >&2
  printf '%s' "$encontrado" >&2
  echo "Usar variables de entorno (.env + os.environ), nunca literales." >&2
  exit 2
fi
exit 0
