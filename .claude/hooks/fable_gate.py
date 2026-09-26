#!/usr/bin/env python
"""PreToolUse (Bash|PowerShell): candado de proceso para la revision Fable
previa a un commit que toque una ruta sensible del disparador de escalado.

Motivo (2026-09-26): se commiteo un cambio de parametro de modelo
(`configs/leagues/ratings.yaml`) sin la revision previa de Fable que exige
`MODEL_ROUTING.md` (seccion "Disparador de escalado" -- las cinco clases:
parametros de riesgo/modelo/estrategia/umbral/gate, cifras publicables,
contradecir una decision registrada, y modificar el contrato de un artefacto
persistido). No hubo despacho con `model: "fable"` ni linea de registro. Este
hook no puede impedir un mal veredicto -- eso es juicio, no proceso -- pero
puede impedir OLVIDAR pedirlo, igual que `require-dispatch-model.sh` hace para
`model` en la herramienta `Agent`. Ese hook es el patron de estilo de este.

Revision independiente de Fable (2026-09-26, APTO CON CAMBIOS): esta segunda
version corrige varios escapes de deteccion y dos errores de interpretacion
que la primera version tenia. Ver cada seccion abajo.

Rutas sensibles: `.claude/automation/fable-gate.json` (patrones `fnmatch`
CASE-SENSITIVE -- `fnmatch.fnmatchcase`, no `fnmatch.fnmatch` -- sobre rutas
POSIX relativas a la raiz del repo). Cobertura exigida: una linea

    FABLE-REVIEW: YYYY-MM-DD | veredicto: <texto> | rutas: <ruta1>, <ruta2>, ...

en `.claude/automation/runtime/current-task.md`, con la fecha de HOY en hora
local, un veredicto cuyo texto EMPIECE por la palabra "APTO" (sin distinguir
mayusculas/minusculas; p.ej. "APTO CON CAMBIOS", "APTO; no hace falta
revertir nada" cuentan -- el contenido posterior no se inspecciona por
substring, asi que un APTO que mencione de pasada "revertir" o "rechazar"
sigue contando, y en cambio un veredicto como "BLOQUEANTE, no commitear" que
no empieza por APTO NO cuenta aunque no contenga ninguna palabra prohibida:
la lista blanca anclada al inicio sustituye a la lista negra por substring de
la primera version, que dejaba pasar cualquier veredicto que no citara
textualmente "no apto"/"revertir"/"rechaz"), y una lista de rutas que cubra
cada ruta sensible del commit por coincidencia exacta o por prefijo de
directorio terminado en "/".

Preprocesado del texto del comando, ANTES de trocear en segmentos:
  1. Se eliminan los cuerpos de heredoc (desde `<<-?['"]?DELIM['"]?` hasta la
     linea que cierra ese delimitador exacto), para que un heredoc informativo
     (p.ej. `cat > notas.md <<'EOF' ... git commit ... EOF`, o el cuerpo de un
     mensaje de commit via `git commit -F - <<'EOF' ...`) no se trocee por sus
     saltos de linea internos ni aporte texto literal "git commit" que no es
     una invocacion real.
  2. Se unen las continuaciones de linea `\\` + salto de linea en un solo
     espacio, para que una invocacion de `git` partida en varias lineas siga
     tokenizando como un unico segmento.

Segmentacion en "segmentos" (una invocacion de `git` cada uno), consciente de
comillas: los operadores de encadenamiento `&&`, `||`, `;` y el salto de linea
separan segmentos SOLO fuera de comillas simples/dobles -- un `;` dentro de un
mensaje de commit citado (`git commit -m "fix; luego X"`) no rompe el
comando en dos.

Deteccion de la invocacion de `git` dentro de cada segmento: no basta con que
el PRIMER token del segmento sea `git` (eso deja pasar un prefijo de variable
de entorno como `SQP_FABLE_GATE=off git commit ...`, el operador de llamada de
PowerShell dentro de `if ($?) { git commit ... }`, o un grupo `{ git commit
...; }`). Se saltan, en orden, los tokens que sean una asignacion de entorno
(`^[A-Za-z_][A-Za-z0-9_]*=`), las palabras `env`/`command`/`if`, y los tokens
exactos `&`, `{`, `(` o que empiecen por `(` (p.ej. `($?)`); el primer token
que no encaje en ninguna de esas categorias corta el salteo. Si tras eso no se
ha encontrado `git`, como ultimo recurso se busca el token `git` en
CUALQUIER posicion del segmento. Ademas, si el segmento es una invocacion de
`bash -c '...'`, `sh -c '...'` o `pwsh -Command '...'` (o `-c` en pwsh) y la
cadena pasada contiene la subcadena "git", esa cadena se analiza
recursivamente con el mismo pipeline (heredocs, continuaciones, segmentacion
consciente de comillas, deteccion de `git`), compartiendo el acumulado de
`git add` con el resto del comando.

Deteccion de rutas del commit, en el ORDEN en que aparecen en el comando:

1. `git diff --cached --name-only` de la raiz del repo (lo YA staged).
2. + `git diff --name-only` si el propio `git commit` lleva `-a`, `--all` o
   una combinacion corta que incluya `a` (p.ej. `-am`). Al buscar esa `a` se
   saltan primero el propio flag y el VALOR de `-m`, `-F`, `-C`, `-c`, `-t`,
   `--author` y `--date` (que toman un argumento separado): sin este salto,
   un mensaje como `-m "- actualiza README"` se leia como si fuera un flag
   corto con `a` dentro (por la palabra "actualiza") y activaba `-a` por
   error, tirando de cambios sin stagear que no venian al caso.
3. + las rutas de cada `git add <rutas>` que aparezca ANTES del `git commit`
   en el mismo comando (en el instante en que corre este hook, PreToolUse,
   esas rutas todavia no estan en el indice real). Estas rutas, y las de
   `git commit -- <pathspecs>` / `-i` / `-o` / rutas sueltas tras las
   opciones, se resuelven contra el arbol real del repo -- `git add
   --dry-run <mismos argumentos>` para `git add` (cubre `.`, `-A`, `-u`,
   directorios y globs), `git ls-files -m -o --exclude-standard --
   <pathspec>` para los pathspecs de `git commit` -- en vez de tratar el
   texto tal cual: un `git add configs/` antes solo se comparaba el string
   "configs/" contra los patrones, y nunca resolvia a los ficheros reales
   dentro. Si la resolucion por git falla (parseo de argumentos raro,
   pathspec sin coincidencias, etc.) se cae de vuelta al troceo textual
   anterior en vez de bloquear el hook entero.

Todas las llamadas a `git` de este hook usan `-c core.quotePath=false` (para
que una ruta no ASCII no llegue entre comillas octales) y corren con
`GIT_OPTIONAL_LOCKS=0` y un timeout de unos 8 segundos cada una.

FALLA ABIERTO ante cualquier fallo (JSON ilegible, git ausente, excepcion no
prevista, `fable-gate.json` o `current-task.md` no legibles, o un
`UnicodeEncodeError` al escribir el aviso de bloqueo en una consola con una
codificacion de caracteres limitada): exit 0 con aviso en stderr. Es un
candado de PROCESO, no un control de seguridad -- no puede verificar que la
revision Fable ocurrio de verdad, solo que alguien escribio la linea que la
declara. Un guard roto que paralizase todo commit seria peor que no tenerlo.

Escape para el OPERADOR unicamente: `SQP_FABLE_GATE=off` fijada como variable
de ENTORNO DE SESION al arrancar Claude Code (o, equivalentemente, commitear
desde una terminal propia del operador -- este hook solo se dispara dentro de
Claude Code) deja pasar sin mirar nada. NUNCA es un prefijo del propio
comando: un `SQP_FABLE_GATE=off git commit ...` escrito DENTRO de `command`
no desactiva nada, porque solo se consulta `os.environ`, nunca el texto del
comando -- no es una forma de "pasar la revision", es una forma de desactivar
el candado a proposito; dejarlo dicho en el propio aviso para que no se
confunda con una excepcion silenciosa.

Sin dependencias fuera de la biblioteca estandar.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import date
from pathlib import Path

GATE_CONFIG_REL = ".claude/automation/fable-gate.json"
CURRENT_TASK_REL = ".claude/automation/runtime/current-task.md"

# Timeout por llamada a git y variable de entorno para no competir por locks
# del indice con el propio comando que el operador esta a punto de ejecutar.
_GIT_TIMEOUT_SEGUNDOS = 8

# Formato exigido de la linea de cobertura. `re.MULTILINE` para que `^`/`$`
# aten a cada linea del fichero, no al fichero entero.
_FABLE_REVIEW_RE = re.compile(
    r"^FABLE-REVIEW:\s*(?P<fecha>\d{4}-\d{2}-\d{2})\s*\|\s*"
    r"veredicto:\s*(?P<veredicto>.*?)\s*\|\s*rutas:\s*(?P<rutas>.*?)\s*$",
    re.MULTILINE,
)

# Lista blanca anclada al INICIO del veredicto (no una lista negra por
# substring en cualquier posicion): un veredicto vale como cobertura solo si
# EMPIEZA por la palabra "APTO", sin distinguir mayusculas/minusculas.
_VEREDICTO_APTO_RE = re.compile(r"^\s*APTO\b", re.IGNORECASE)

_GIT_GLOBAL_OPTS_CON_VALOR = ("-C", "-c", "--git-dir", "--work-tree", "--namespace")

# Flags de `git commit` que consumen el SIGUIENTE token como su valor (no
# fusionado con `=`). Su valor nunca debe inspeccionarse como si fuera un
# flag: un mensaje de commit puede empezar por "-" y contener cualquier letra.
_FLAGS_CON_VALOR_SEPARADA = frozenset({"-m", "-F", "-C", "-c", "-t", "--author", "--date"})

# Interpretes que pueden envolver una invocacion real de git en una cadena de
# `-c`/`-Command`. Se analiza esa cadena de forma recursiva solo si contiene
# la subcadena "git" (evita trabajo/recursion innecesarios en el resto).
_WRAPPERS_SHELL_POSIX = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_WRAPPERS_POWERSHELL = frozenset({"pwsh", "powershell"})

_PROFUNDIDAD_MAXIMA_RECURSION = 5

# --- Preprocesado: heredocs y continuaciones de linea ------------------------

_HEREDOC_INICIO_RE = re.compile(r"<<(-?)\s*(['\"]?)(\w+)\2")
_CONTINUACION_LINEA_RE = re.compile(r"\\\r?\n")


def _quita_heredocs(texto: str) -> str:
    """Elimina el CUERPO de cada heredoc (desde la linea siguiente al marcador
    de apertura hasta -- e incluyendo -- la linea que repite el delimitador
    exacto). El propio marcador (`<<'EOF'`) se conserva: solo estorba su
    contenido, no la parte de la invocacion de git que lo precede."""
    resultado = []
    pos = 0
    while True:
        m = _HEREDOC_INICIO_RE.search(texto, pos)
        if not m:
            resultado.append(texto[pos:])
            break
        resultado.append(texto[pos:m.end()])
        con_guion, delimitador = m.group(1), m.group(3)
        salto = texto.find("\n", m.end())
        if salto == -1:
            # No hay cuerpo real que trocear (nada tras el marcador).
            pos = m.end()
            continue
        inicio_cuerpo = salto + 1
        if con_guion:
            patron_fin = re.compile(r"^[ \t]*" + re.escape(delimitador) + r"[ \t]*\r?$", re.MULTILINE)
        else:
            patron_fin = re.compile(r"^" + re.escape(delimitador) + r"[ \t]*\r?$", re.MULTILINE)
        m2 = patron_fin.search(texto, inicio_cuerpo)
        if m2 is None:
            # Heredoc sin cerrar: se descarta el resto (mejor no colgar el
            # hook analizando un comando truncado o mal formado).
            pos = len(texto)
            continue
        fin = m2.end()
        if fin < len(texto) and texto[fin] == "\n":
            fin += 1
        pos = fin
    return "".join(resultado)


def _prepara_texto(command: str) -> str:
    sin_heredocs = _quita_heredocs(command)
    return _CONTINUACION_LINEA_RE.sub(" ", sin_heredocs)


# --- Segmentacion consciente de comillas --------------------------------------


def _segmenta_nivel_superior(texto: str) -> list[str]:
    """Trocea `texto` por `&&`, `||`, `;` y salto de linea, pero SOLO fuera de
    comillas simples/dobles -- un `;` dentro de un `-m "fix; algo"` no debe
    partir el comando en dos. No es un parser de shell completo: basta con
    llevar la cuenta de si estamos dentro de una comilla."""
    segmentos: list[str] = []
    actual: list[str] = []
    comilla: str | None = None
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]
        if comilla is not None:
            actual.append(c)
            if c == comilla:
                comilla = None
            elif comilla == '"' and c == "\\" and i + 1 < n:
                i += 1
                actual.append(texto[i])
            i += 1
            continue
        if c in ("'", '"'):
            comilla = c
            actual.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            actual.append(c)
            actual.append(texto[i + 1])
            i += 2
            continue
        if texto.startswith("&&", i) or texto.startswith("||", i):
            segmentos.append("".join(actual))
            actual = []
            i += 2
            continue
        if c in (";", "\n"):
            segmentos.append("".join(actual))
            actual = []
            i += 1
            continue
        if c == "\r":
            i += 1
            continue
        actual.append(c)
        i += 1
    segmentos.append("".join(actual))
    return segmentos


def _tokeniza(segmento: str) -> list[str]:
    """Tokeniza un segmento de comando. Si `shlex` no puede (comillas sin
    cerrar, etc.) se hace un split ingenuo: mejor una deteccion imprecisa que
    tumbar el hook entero por un fallo de parseo en un solo segmento."""
    try:
        return shlex.split(segmento, posix=True)
    except ValueError:
        return segmento.split()


# --- Deteccion de la invocacion de git dentro de un segmento ------------------

_ASIGNACION_ENTORNO_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PALABRAS_SALTABLES = frozenset({"env", "command", "if"})
_TOKENS_SALTABLES_EXACTOS = frozenset({"&", "{", "("})


def _es_git(token: str) -> bool:
    base = os.path.basename(token).lower()
    return base in ("git", "git.exe")


def _localiza_git(partes: list[str]) -> int | None:
    """Indice del token `git` real dentro de `partes`. Primero salta, en
    orden, prefijos conocidos que hoy se escapaban (asignacion de entorno,
    `env`/`command`/`if`, `&`, `{`, `(` o un token que empiece por `(` como
    `($?)`); si el primer token no reconocido no es `git`, se prueba, como
    ultimo recurso, a buscar `git` en cualquier posicion del segmento."""
    i, n = 0, len(partes)
    while i < n:
        t = partes[i]
        if _es_git(t):
            return i
        if _ASIGNACION_ENTORNO_RE.match(t):
            i += 1
            continue
        if t.lower() in _PALABRAS_SALTABLES:
            i += 1
            continue
        if t in _TOKENS_SALTABLES_EXACTOS or t.startswith("("):
            i += 1
            continue
        break
    for j, t in enumerate(partes):
        if _es_git(t):
            return j
    return None


def _parsea_invocacion_git_desde(partes: list[str], idx: int) -> tuple[str, list[str]] | None:
    """Devuelve (subcomando, resto) para la invocacion de `git` que empieza en
    `partes[idx]`. Salta las opciones globales de `git` (`-C ruta`, `-c
    clave=valor`, ...) para llegar al subcomando real (`add`, `commit`, ...)."""
    i = idx + 1
    n = len(partes)
    while i < n:
        t = partes[i]
        if t in _GIT_GLOBAL_OPTS_CON_VALOR:
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        break
    if i >= n:
        return None
    return partes[i], partes[i + 1:]


def _extrae_cadena_wrapper(partes: list[str]) -> str | None:
    """Si `partes` es `bash -c '...'`, `sh -c '...'` o `pwsh -Command '...'`
    (tambien `-c` para pwsh), devuelve la cadena pasada a esa opcion."""
    if not partes:
        return None
    base = os.path.basename(partes[0]).lower()
    if base.endswith(".exe"):
        base = base[:-4]
    es_shell = base in _WRAPPERS_SHELL_POSIX
    es_ps = base in _WRAPPERS_POWERSHELL
    if not es_shell and not es_ps:
        return None
    for i in range(1, len(partes)):
        t = partes[i]
        low = t.lower()
        # `-c` suelto o combinado al final (`bash -lc`, `sh -ec`): hueco A de la
        # verificacion de Fable (2026-09-26).
        coincide = (bool(re.fullmatch(r"-[A-Za-z]*c", t)) and not t.startswith("--"))             or (es_ps and low in ("-c", "-command"))
        if coincide and i + 1 < len(partes):
            return partes[i + 1]
    return None


# --- Flags de `git commit` ----------------------------------------------------


def _tiene_flag_all(args: list[str]) -> bool:
    """`-a`, `--all`, o cualquier combinacion corta que incluya `a`
    (`-am`, `-av`...). `--amend` y otras opciones largas con `a` dentro del
    nombre NO cuentan: solo se comprueba la pertenencia exacta a `--all`. Se
    saltan primero el propio flag y el VALOR de las opciones que toman un
    argumento separado (`-m`, `-F`, `-C`, `-c`, `-t`, `--author`, `--date`):
    de lo contrario un mensaje como `-m "- actualiza README"` se leia como un
    flag corto con `a` (por "actualiza") y activaba `-a` por error."""
    i, n = 0, len(args)
    while i < n:
        a = args[i]
        if a == "--":
            break
        if a in _FLAGS_CON_VALOR_SEPARADA:
            i += 2
            continue
        if a == "--all":
            return True
        if a.startswith("--"):
            i += 1
            continue
        if a.startswith("-"):
            # Grupo corto: se recorre letra a letra y se para en la primera
            # que consume valor (`-m"arregla"` -> `-m` + mensaje): hueco B de la
            # verificacion de Fable (2026-09-26).
            for ch in a[1:]:
                if ch == "a":
                    return True
                if ch in "mFCct":
                    break
        i += 1
    return False


def _pathspecs_de_commit(args: list[str]) -> list[str]:
    """Rutas sueltas de `git commit`: tras `--`, tras `-i`/`-o`, o cualquier
    token sin `-` que no sea el valor de un flag que lo consume. Se pasan tal
    cual a `git ls-files -- <pathspec>` para que sea git quien las resuelva."""
    rutas: list[str] = []
    i, n = 0, len(args)
    tras_doble_guion = False
    while i < n:
        a = args[i]
        if tras_doble_guion:
            rutas.append(a)
            i += 1
            continue
        if a == "--":
            tras_doble_guion = True
            i += 1
            continue
        if a in _FLAGS_CON_VALOR_SEPARADA:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        rutas.append(a)
        i += 1
    return rutas


def _rutas_de_add_textual(args: list[str]) -> list[str]:
    """Troceo textual de respaldo (sin consultar a git) para `git add`."""
    rutas = []
    fin_flags = False
    for a in args:
        if a == "--":
            fin_flags = True
            continue
        if not fin_flags and a.startswith("-"):
            continue
        rutas.append(a)
    return rutas


def _normaliza_ruta(ruta: str) -> str:
    limpia = ruta.strip().strip('"').strip("'").replace("\\", "/")
    while limpia.startswith("./"):
        limpia = limpia[2:]
    return limpia


def _repo_root() -> Path:
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root)
    return Path.cwd()


# --- Llamadas a git ------------------------------------------------------------


def _entorno_git() -> dict[str, str]:
    entorno = dict(os.environ)
    entorno["GIT_OPTIONAL_LOCKS"] = "0"
    return entorno


def _git_name_only(root: Path, args: list[str]) -> set[str]:
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotePath=false", "-C", str(root), *args],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT_SEGUNDOS,
            check=False, env=_entorno_git(),
        )
    except Exception:
        return set()
    if proc.returncode != 0:
        return set()
    return {
        linea.strip().replace("\\", "/")
        for linea in proc.stdout.splitlines()
        if linea.strip()
    }


_ADD_DRY_RUN_LINEA_RE = re.compile(r"^add\s+'(.*)'\s*$")


def _git_add_dry_run(root: Path, args: list[str]) -> set[str] | None:
    """Resuelve `git add <args>` a las rutas exactas que tocaria, via
    `git add --dry-run`. Devuelve `None` (en vez de un conjunto vacio) cuando
    la llamada falla, para que el llamador sepa que debe caer al troceo
    textual en vez de asumir "ningun fichero"."""
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotePath=false", "-C", str(root),
             "add", "--dry-run", *args],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT_SEGUNDOS,
            check=False, env=_entorno_git(),
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    rutas: set[str] = set()
    for linea in proc.stdout.splitlines():
        m = _ADD_DRY_RUN_LINEA_RE.match(linea)
        if m:
            rutas.add(m.group(1).replace("\\", "/"))
    return rutas


def _resuelve_rutas_add(root: Path, args: list[str]) -> set[str]:
    rutas = _git_add_dry_run(root, args)
    if rutas is not None:
        return rutas
    return {_normaliza_ruta(r) for r in _rutas_de_add_textual(args)}


# --- Recorrido del comando: acumula rutas de `add` y una entrada por `commit` -


def _procesa_texto(
    texto: str, root: Path, acumulado_add: set[str], resultados: list[set[str]],
    profundidad: int = 0,
) -> None:
    if profundidad > _PROFUNDIDAD_MAXIMA_RECURSION:
        return
    preparado = _prepara_texto(texto)
    for segmento in _segmenta_nivel_superior(preparado):
        partes = _tokeniza(segmento)
        if not partes:
            continue
        idx = _localiza_git(partes)
        if idx is not None:
            invocacion = _parsea_invocacion_git_desde(partes, idx)
            if invocacion is None:
                continue
            subcomando, args = invocacion
            if subcomando == "add":
                acumulado_add.update(_resuelve_rutas_add(root, args))
            elif subcomando == "commit":
                rutas = set(acumulado_add)
                rutas |= _git_name_only(root, ["diff", "--cached", "--name-only"])
                if _tiene_flag_all(args):
                    rutas |= _git_name_only(root, ["diff", "--name-only"])
                pathspecs = _pathspecs_de_commit(args)
                if pathspecs:
                    rutas |= _git_name_only(
                        root,
                        ["ls-files", "-m", "-o", "--exclude-standard", "--", *pathspecs],
                    )
                resultados.append(rutas)
            continue
        cadena_anidada = _extrae_cadena_wrapper(partes)
        if cadena_anidada and "git" in cadena_anidada:
            _procesa_texto(cadena_anidada, root, acumulado_add, resultados, profundidad + 1)


def _conjuntos_de_rutas_por_commit(command: str, root: Path) -> list[set[str]]:
    """Un elemento por cada `git commit` hallado en `command` (incluidos los
    envueltos en `bash -c`/`sh -c`/`pwsh -Command`), en el orden en que
    aparece. Cada elemento es el conjunto de rutas candidatas para ESE
    commit: lo ya staged, mas lo modificado si lleva `-a`/`--all`, mas lo
    acumulado por los `git add` que lo preceden en el mismo comando, mas los
    pathspecs propios del `git commit`."""
    acumulado_add: set[str] = set()
    resultados: list[set[str]] = []
    _procesa_texto(command, root, acumulado_add, resultados)
    return resultados


# --- Patrones sensibles y linea de cobertura ----------------------------------


def _patrones_sensibles(root: Path) -> list[str]:
    cfg = json.loads((root / GATE_CONFIG_REL).read_text(encoding="utf-8"))
    patrones = cfg.get("patrones")
    if not isinstance(patrones, list):
        raise ValueError(f"{GATE_CONFIG_REL} no define una lista 'patrones'")
    return [str(p) for p in patrones]


def _es_sensible(ruta: str, patrones: list[str]) -> bool:
    # `fnmatchcase`, no `fnmatch`: las rutas de un repo git son sensibles a
    # mayusculas/minusculas aunque el sistema de ficheros local no lo sea.
    return any(fnmatch.fnmatchcase(ruta, p) for p in patrones)


def _lineas_fable_review(task_file: Path) -> list[tuple[str, str, str]]:
    if not task_file.exists():
        return []
    texto = task_file.read_text(encoding="utf-8")
    return [
        (m.group("fecha"), m.group("veredicto"), m.group("rutas"))
        for m in _FABLE_REVIEW_RE.finditer(texto)
    ]


def _parsea_rutas_listadas(campo: str) -> list[str]:
    return [
        r.strip().strip('"').strip("'").replace("\\", "/")
        for r in campo.split(",")
        if r.strip()
    ]


def _ruta_cubierta(ruta: str, rutas_listadas: list[str]) -> bool:
    for listada in rutas_listadas:
        if ruta == listada:
            return True
        if listada.endswith("/") and ruta.startswith(listada):
            return True
    return False


def _veredicto_valido(veredicto: str) -> bool:
    return bool(_VEREDICTO_APTO_RE.match(veredicto))


def _revision_cubre(ruta: str, lineas: list[tuple[str, str, str]], hoy: str) -> bool:
    for fecha, veredicto, rutas_campo in lineas:
        if fecha != hoy:
            continue
        if not _veredicto_valido(veredicto):
            continue
        if _ruta_cubierta(ruta, _parsea_rutas_listadas(rutas_campo)):
            return True
    return False


def _mensaje_bloqueo(rutas_sin_cubrir: list[str], hoy: str) -> str:
    lista = "\n".join(f"  - {r}" for r in rutas_sin_cubrir)
    return f"""COMMIT BLOQUEADO por fable_gate: rutas sensibles sin revision Fable de hoy ({hoy}) en {CURRENT_TASK_REL}:
{lista}

La politica de escalado de MODEL_ROUTING.md exige, para estas rutas, despachar
la revision con el parametro `model: "fable"` de la herramienta `Agent` (REGLA
DE DESPACHO) ANTES de comprometer el cambio, y anotar el resultado con una
linea de este formato exacto:

  FABLE-REVIEW: {hoy} | veredicto: <texto> | rutas: <ruta1>, <ruta2>, ...

Condiciones: la fecha debe ser la de HOY; el veredicto debe EMPEZAR por la
palabra "APTO" (sin distinguir mayusculas/minusculas -- lo que venga despues
no se inspecciona, asi que "APTO CON CAMBIOS" o "APTO; no hace falta revertir
nada" cuentan, y "BLOQUEANTE", "NO APTO" o "SE RECHAZA" no cuentan aunque no
citen ninguna palabra concreta); y la lista de rutas debe cubrir cada ruta de
arriba por coincidencia exacta o por un prefijo de directorio terminado en
"/".

Escape SOLO para el operador: la variable de ENTORNO DE SESION
`SQP_FABLE_GATE=off`, fijada al arrancar Claude Code (o commitear desde una
terminal propia, fuera de Claude Code) -- nunca un prefijo dentro del propio
comando, que no tiene ningun efecto aqui.

Es un candado de PROCESO, no un control de seguridad: no puede verificar que
la revision Fable ocurrio de verdad, solo que alguien escribio la linea que la
declara. Impide OLVIDARSE de pedirla; no impide elegir mal el veredicto.
"""


def _run(payload: dict) -> int:
    tool_name = str((payload or {}).get("tool_name") or "")
    if tool_name not in ("Bash", "PowerShell"):
        return 0

    command = str(((payload or {}).get("tool_input") or {}).get("command") or "")
    if not command.strip():
        return 0

    root = _repo_root()
    conjuntos = _conjuntos_de_rutas_por_commit(command, root)
    if not conjuntos:
        return 0

    try:
        patrones = _patrones_sensibles(root)
    except Exception as exc:
        print(
            f"fable_gate: no se pudo leer {GATE_CONFIG_REL} ({exc!r}); "
            "fail-open (no bloquea).",
            file=sys.stderr,
        )
        return 0

    todas_las_rutas: set[str] = set()
    for conjunto in conjuntos:
        todas_las_rutas |= conjunto

    sensibles = sorted(r for r in todas_las_rutas if _es_sensible(r, patrones))
    if not sensibles:
        return 0

    hoy = date.today().isoformat()
    lineas = _lineas_fable_review(root / CURRENT_TASK_REL)
    sin_cubrir = [r for r in sensibles if not _revision_cubre(r, lineas, hoy)]
    if not sin_cubrir:
        return 0

    print(_mensaje_bloqueo(sin_cubrir, hoy), file=sys.stderr)
    return 2


def main() -> int:
    # Un `UnicodeEncodeError` al imprimir el aviso de bloqueo (p.ej. una
    # consola con codificacion limitada y una ruta no ASCII) no debe
    # convertirse en un fail-open silencioso por una excepcion no capturada
    # en el `print` mismo: se reconfigura stderr para sustituir caracteres
    # no representables en vez de lanzar.
    try:
        sys.stderr.reconfigure(errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

    # Escape del OPERADOR unicamente, comprobado antes de tocar stdin o git:
    # dilo en el propio hook, no solo en el mensaje de bloqueo, para que
    # quede claro que es una decision explicita y no un fallo silencioso.
    # Es una variable de ENTORNO DE SESION (fijada al arrancar Claude Code, o
    # el operador commitea desde su propia terminal fuera de Claude Code) --
    # NUNCA un prefijo dentro del propio `command`: solo se mira
    # `os.environ`, jamas el texto del comando que se esta analizando.
    if os.environ.get("SQP_FABLE_GATE", "").strip().lower() == "off":
        print(
            "fable_gate: SQP_FABLE_GATE=off -- candado desactivado a proposito "
            "para este comando (variable de entorno de sesion del operador, "
            "no una forma de aprobar la revision, y nunca un prefijo dentro "
            "del comando mismo).",
            file=sys.stderr,
        )
        return 0

    try:
        crudo = sys.stdin.read()
    except Exception as exc:
        print(f"fable_gate: no se pudo leer stdin ({exc!r}); fail-open.", file=sys.stderr)
        return 0

    try:
        payload = json.loads(crudo)
    except Exception:
        print(
            "fable_gate: JSON de entrada ilegible; fail-open. Candado de "
            "proceso, no control de seguridad: no puede verificar nada aqui, "
            "asi que no bloquea.",
            file=sys.stderr,
        )
        return 0

    try:
        return _run(payload)
    except Exception as exc:
        print(
            f"fable_gate: fallo inesperado ({exc!r}); fail-open. No puede "
            "verificar que la revision Fable ocurrio; solo evita el olvido "
            "cuando funciona sin errores.",
            file=sys.stderr,
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
