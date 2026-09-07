#!/usr/bin/env python
"""Ficheros sobre los que debe actuar un hook PostToolUse, en una sola linea.

AUDITORIA INTEGRAL 2026-09-07, AUD-MED-002. Los cuatro hooks `PostToolUse`
estaban cableados con `"matcher": "Edit|Write"` y los cuatro sacaban el fichero
de `tool_input.file_path`. El matcher filtra por NOMBRE DE HERRAMIENTA -- lo dice
la cabecera de `require-dispatch-model.sh`, que cerro KI-023 apoyandose en ese
mismo hecho --, asi que una llamada de la herramienta `Bash` no emparejaba con
ninguno, y ademas no trae `file_path`.

Consecuencia: un fichero modificado con `sed -i`, un heredoc o una redireccion
desde Bash no armaba el centinela de tests, no armaba el de revision cruzada y
no pasaba por el detector de secretos. Tres controles en silencio. Y no es una
ruta teorica: hay modos de operacion del agente que instruyen preferir Bash
sobre Edit/Write precisamente para editar ficheros.

Es la MISMA enfermedad que KI-033 -- hooks que se creian activos y llevaban
meses sin emparejar por la contrabarra de Windows -- un piso mas arriba: alli no
casaba el PATRON, aqui no casa la HERRAMIENTA.

Vive en un solo modulo, y no copiado en cada hook, porque el modo de fallo
dominante de este repositorio es la deriva entre artefactos duplicados
(F-10/F-15, KI-027): tres copias de esta logica serian tres oportunidades de que
una se quede atras.

Es `.py` y no `.sh` a proposito: `test_every_hook_script_is_actually_wired_in_
settings` exige que todo `.sh` de `.claude/hooks/` este cableado en
`settings.json`, y esto es una biblioteca, no un hook.

    uso:  python _targets.py [--with-git]        (JSON del hook por stdin)
    sale: una ruta por linea; codigo 0 siempre (un fallo suyo no puede
          tumbar el hook que lo llama)

FUENTES, en orden:

1. `tool_input.file_path`  -- Edit/Write. Si esta, manda y no se mira nada mas.
2. `tool_input.command`    -- Bash. Rutas con extension de codigo NOMBRADAS en el
                              comando, que existan en disco. Preciso: no inventa
                              ficheros que el comando no menciona.
3. `git status --porcelain` -- solo con `--with-git`. Red de seguridad para el
                              comando que escribe en una ruta calculada en
                              tiempo de ejecucion, que (2) no puede ver.

Por que (3) NO es para todos los hooks: sobre-disparar es barato en un hook que
solo LEE o solo hace `touch`, y caro en uno que MUTA ficheros o que cuesta
dinero. `check-secrets` y `mark-tests-pending` lo usan (fallar hacia el lado
seguro: escanear de mas, correr tests de mas). `mark-crossreview-pending` no,
porque cada disparo es una llamada de pago a Codex. Y `post-edit-format` ni
siquiera entra en Bash: es el unico que MUTA (`ruff check --fix`), y disparar una
mutacion desde un comando que quiza solo LEIA el fichero seria un modo de fallo
nuevo que nadie pidio -- su garantia ya la da `ruff check` como puerta de CI.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Extensiones cuyo contenido le importa a algun hook. `.md` entra por
# `check-secrets`: `Obsidian/` y `docs/` estan rastreados por git y una clave se
# pega en una nota sin pensar (AUD-LOW-002, 2026-09-06).
_SUFIJOS = ("py", "sh", "bat", "cmd", "yaml", "yml", "json", "toml", "ps1", "md")
_RUTA = re.compile(r"[A-Za-z0-9_.:/\\-]+\.(?:" + "|".join(_SUFIJOS) + r")\b")

# Techo de ficheros devueltos. Un `git status` con cientos de cambios no puede
# convertir un hook de 30 s en uno que no termina.
_MAX = 50


def _repo() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()


def _del_comando(cmd: str, raiz: Path) -> list[str]:
    fuera = []
    for bruto in _RUTA.findall(cmd or ""):
        ruta = bruto.strip("\"'")
        p = Path(ruta)
        candidato = p if p.is_absolute() else raiz / ruta
        try:
            if candidato.is_file():
                fuera.append(str(candidato))
        except OSError:
            continue
    return fuera


def _de_git(raiz: Path) -> list[str]:
    try:
        r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                           cwd=raiz, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    fuera = []
    for linea in r.stdout.splitlines():
        if len(linea) < 4:
            continue
        ruta = linea[3:].strip().strip('"')
        # Renombrado: "R  viejo -> nuevo"; interesa el destino.
        if " -> " in ruta:
            ruta = ruta.split(" -> ", 1)[1]
        if not ruta.lower().endswith(tuple("." + s for s in _SUFIJOS)):
            continue
        p = raiz / ruta
        if p.is_file():
            fuera.append(str(p))
    return fuera


def main() -> int:
    # SALTO DE LINEA LF, SIEMPRE. En Windows el modo texto traduce `\n` a
    # `\r\n`, asi que cada ruta llegaba al hook con un `\r` final: `[ -f
    # "$file" ]` fallaba y el glob `*src/*.py` no emparejaba porque la cadena ya
    # no terminaba en `.py`. El bucle recorria los ficheros y los saltaba TODOS,
    # en silencio y con codigo de salida 0 -- un control que parece cableado y no
    # mira nada, que es exactamente KI-033 otra vez. Detectado ejercitando el
    # hook con `bash -x` antes de darlo por bueno, no leyendolo.
    # Los hooks ademas recortan el `\r` por su cuenta: dos candados, porque este
    # fallo ya se ha colado dos veces por sitios distintos.
    try:
        sys.stdout.reconfigure(newline="\n")
    except (AttributeError, ValueError):
        pass
    con_git = "--with-git" in sys.argv[1:]
    try:
        datos = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, OSError):
        return 0                      # falla ABIERTO, como el resto de hooks
    entrada = datos.get("tool_input") or {}
    explicito = str(entrada.get("file_path") or "").strip()
    if explicito:
        print(explicito)
        return 0
    raiz = _repo()
    vistos: list[str] = []
    for ruta in _del_comando(str(entrada.get("command") or ""), raiz):
        if ruta not in vistos:
            vistos.append(ruta)
    if con_git:
        for ruta in _de_git(raiz):
            if ruta not in vistos:
                vistos.append(ruta)
    for ruta in vistos[:_MAX]:
        print(ruta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
