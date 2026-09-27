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

Correccion KI-069 (2026-09-26, agujero confirmado): `_quita_heredocs` borraba
el CUERPO de cada heredoc pero tambien el salto de linea que separaba el
marcador (`<<'EOF'`) de lo que le seguia en el comando original -- casi
siempre la siguiente linea del script. Sin ese salto de linea, el cierre de
comillas del delimitador quedaba pegado sin espacio al primer token de la
linea siguiente (`<<'EOF'git add ...`), y `shlex` los fundia en un unico
token falso (`<<EOFgit`) que `_localiza_git` no reconoce como `git`: una
invocacion de `git add` completa se volvia invisible sin que ningun error lo
avisara. Asi se colo el commit `58330c7` (varios heredocs seguidos, uno de
ellos con un cuerpo Python con comillas triples). Ahora, tras eliminar cada cuerpo de
heredoc, se repone un `\n` sintetico en su lugar (mas cualquier resto de la
propia linea del marcador antes del salto), preservando la separacion de
lineas que el resto del pipeline (segmentacion, tokenizado) da por sentada.

Defensa en profundidad (KI-069, la UNICA excepcion deliberada al fail-open de
mas abajo): si, tras quitar los cuerpos de heredoc, el texto contiene el
patron `git ... commit` en la misma linea pero el analizador estructurado no
identifico NINGUNA invocacion de `git commit`, no se asume que no hay nada
que commitear. Se reconstruye un conjunto de rutas de respaldo con `git diff
--cached --name-only` mas lo que ya se hubiera acumulado de cualquier `git
add` si detectado, y se trata como un commit mas (mismo chequeo de
sensibilidad y de cobertura que un commit identificado normalmente). Si ni
siquiera se puede preguntar a git (el propio `git diff --cached` falla), el
hook BLOQUEA con un mensaje que explica que no pudo analizar el comando y
pide separar `git add` y `git commit` en comandos simples -- fallar abierto
en silencio ante un patron de commit no identificado es exactamente el modo
de fallo que este candado existe para impedir, asi que aqui, y solo aqui, no
se aplica el fail-open general de la seccion siguiente.

Revision independiente de Fable (2026-09-26, APTO CON CAMBIOS) sobre esta
misma defensa: la version anterior de la red (`\bgit\b[^\n]*\bcommit\b` sobre
el texto crudo) daba falso positivo con comandos de solo lectura que nunca
comprometen nada -- `git log --grep commit`, `git commit-tree`, `echo "usa
git para hacer commit"`, `grep -rn 'git commit' ...` --, porque (a) el guion
de `commit-tree` no es caracter de palabra y `\bcommit\b` lo casaba igual,
(b) una linea que YA fue reconocida estructuralmente como una invocacion real
de `git` con OTRO subcomando (`log`, `commit-tree`, `show`, `grep`...) no
debe activar ademas la red textual -- el analizador estructurado ya dijo lo
que hay, y no era `commit` --, y (c) `git`/`commit` mencionados como TEXTO
LITERAL dentro de una cadena entre comillas (el argumento de `echo` o de
`grep`) no son una invocacion, son datos. Ahora: 1) el patron exige que
`commit` no vaya pegado a un guion o letra/digito/guion-bajo
(`\bcommit\b(?![-\\w])`, que descarta `commit-tree`); 2) cada segmento de
nivel superior que el analizador SI supo interpretar como una invocacion real
de `git` (encontro `git` y le siguio un subcomando, sea cual sea) se retira
del texto antes de aplicar la red, asi que un `git log ...` o `git
commit-tree ...` reconocido no deja ningun rastro que la red pueda malinterpretar;
3) el contenido de las cadenas entre comillas simples/dobles del texto
restante se blanquea (se sustituye por espacios, preservando comillas y
saltos de linea) antes de buscar el patron, para que un `git`/`commit`
citado como argumento de otro comando no cuente. La red sigue existiendo
solo para el caso que la motivo: una invocacion real pero NO reconocible por
el analizador estructurado (p.ej. `git+commit`, un unico token sin espacio
que ningun tokenizador de shell separa).

Verificacion de Fable (2026-09-26), segunda ronda -- NO APTO, dos agujeros
confirmados en la propia defensa en profundidad de la ronda anterior:

1. Agujero (c) -- blanqueo indiscriminado de comillas: `_texto_para_defensa`
   blanqueaba las comillas de CUALQUIER segmento no reconocido antes de
   aplicar la red, no solo las de un argumento citado de texto plano. Eso
   ocultaba invocaciones reales envueltas en un interprete que el analizador
   estructurado no sabe interpretar: `cmd /c "git add x && git commit -m
   m"`, `cmd.exe /c "..."`, `eval "..."`, `env bash -c "..."`, `timeout 60
   bash -c "..."`, `nohup sh -c "..."`, `echo x | xargs -I{} sh -c "git add
   {} && git commit -m m"`, `Invoke-Expression "..."`, `iex "..."` y `python
   -c "...subprocess.run(['git','commit',...])"`. Correccion: el blanqueo
   ahora es una lista BLANCA por segmento (`_COMANDOS_SOLO_LECTURA_BLANQUEABLES`
   -- `echo`, `printf`, `grep`, `rg`, `Select-String`, `Write-Output`,
   `Write-Host`), decidida por el primer token real de CADA segmento no
   reconocido (`_segmento_es_de_solo_lectura`); cualquier otro segmento
   (incluidos `-c`, `-Command`, `/c`, `eval`, `iex`, `xargs`) se protege con
   un marcador opaco antes de blanquear el resto y se repone intacto despues
   (`_texto_para_defensa`), asi que la red sigue viendo su texto, comillas
   incluidas.
2. Agujero (b) -- las tuberias no partian segmentos: en `git diff --cached
   --name-only | xargs git commit -m m --` y en `git status | sh -c "git
   commit -m m"`, `_localiza_git` encontraba el primer `git` (el de la
   izquierda de la tuberia), marcaba TODO el segmento como reconocido -- ya
   que antes una tuberia era un unico segmento de principio a fin -- y la
   etapa real de la derecha, donde ocurria el commit, quedaba invisible tanto
   al analizador (ya "consumido") como a la red (retirada junto con el
   segmento reconocido). Correccion: `_segmenta_nivel_superior` ahora parte
   tambien por `|` suelto (no `||`, que ya se trataba aparte); cada etapa
   pasa, por separado, por `_localiza_git` (incluida la busqueda de ultimo
   recurso) y por la recursion de wrappers, asi que ambos casos citados
   quedan resueltos por el propio analisis ESTRUCTURADO (no hace falta ni la
   red): la etapa `xargs git commit -m m --` resuelve `git` por busqueda de
   ultimo recurso, y la etapa `sh -c "git commit -m m"` se recursiona como
   wrapper igual que si `sh -c '...'` apareciera sola.

Verificacion de Fable (2026-09-26), tercera ronda -- NO APTO, dos agujeros mas
en la propia lista blanca de comandos de solo lectura (`_COMANDOS_SOLO_LECTURA_BLANQUEABLES`)
que la ronda anterior introdujo:

1. Sustitucion de comandos DENTRO de una cadena entre comillas DOBLES de un
   segmento ya blanqueable: `echo "$(git commit -m m)"`, ``echo "`git commit -m
   m`"``, `grep "$(git commit -m m)" f`, `Write-Output "$(git commit -m m)"`.
   `_blanquea_comillas` vaciaba el contenido de CUALQUIER cadena entre comillas
   de un segmento de la lista blanca sin mirar si ese contenido era, el mismo,
   una invocacion real (`$(...)`/`` `...` ``) en vez de texto plano -- exactamente
   el mismo error de fondo que el agujero (c) de la ronda anterior, ahora un
   nivel mas adentro. Correccion: dentro de una cadena entre comillas DOBLES,
   si el contenido contiene la subcadena `$(` o una comilla invertida, no se
   vacia -- se conserva integro, comillas fuera incluidas, para que la red
   textual lo siga viendo. El contenido de una cadena entre comillas SIMPLES
   se sigue vaciando siempre, contenga o no `$(`/backtick: ni bash ni
   PowerShell expanden una sustitucion de comandos dentro de comillas simples,
   asi que ahi no hay invocacion real que preservar.
2. Tuberia de un segmento de la lista blanca HACIA un interprete:
   `echo "git commit -m m" | sh`, `printf 'git commit -m m' | bash`,
   `Write-Output "git commit -m m" | iex`. Antes, `_segmento_es_de_solo_lectura`
   decidia blanquear un segmento SOLO por su primer token, sin mirar si a ese
   segmento le seguia una tuberia hacia otra etapa -- un `echo`/`printf`/
   `Write-Output` cuya SALIDA se interpreta como codigo en la siguiente etapa
   deja de ser "de solo lectura" en ese contexto, aunque el comando en si no
   escriba nada. Correccion: `_segmenta_nivel_superior` ahora devuelve, junto a
   cada segmento de nivel superior, si le sigue inmediatamente una tuberia
   (`|` suelto, no `||`); un segmento de la lista blanca seguido de tuberia se
   protege igual que un segmento no reconocido (nunca se le vacian las
   comillas), mientras que uno que SI es la ultima etapa (`git status | grep
   modified`, `git log | grep -E 'fix|commit'`) se sigue blanqueando como
   antes -- la regla se aplica a la etapa de la lista blanca que va ANTES del
   pipe, nunca a la etapa que lo recibe.

Limitaciones conocidas, deliberadamente NO cerradas con una regla ad hoc
(riesgo de falsos positivos/negativos mayor que el beneficio, a juicio de
esta revision): `git -c alias.ci=commit ci -m m` -- un alias de git definido
en la propia invocacion (`-c alias.ci=commit`) resuelve un subcomando `ci`
que ni el analizador reconoce como `commit` ni la red ve, porque el segmento
SI se reconocio como una invocacion real de `git` (con subcomando `ci`) y
por tanto se retira por completo del texto de la red; resolver esto exigiria
interpretar semantica de alias de git, no solo tokenizar. Y `Start-Process
git -ArgumentList "commit -m m"` -- el cmdlet de PowerShell separa el
ejecutable (`git`, que SI aparece como token exacto y por tanto se reconoce
por busqueda de ultimo recurso) de sus argumentos (`-ArgumentList "commit -m
m"`, un unico string que `_parsea_invocacion_git_desde` toma tal cual como
"subcomando" sin espacios, sin casar con `commit`); igual que el caso
anterior, el segmento se da por reconocido y desaparece de la red. Ambos
casos pasarian con exit 0 sin cobertura Fable; se documentan aqui en vez de
forzar una deteccion especifica de `Start-Process`/alias de git que podria
introducir sus propios falsos positivos.

Observabilidad (KI-069): cada vez que el hook falla abierto por una excepcion
(stdin illegible, JSON illegible, `fable-gate.json` no legible, o cualquier
excepcion no prevista), ademas del aviso por stderr se anade una linea con
marca de tiempo UTC y el motivo a `.claude/automation/runtime/fable_gate.log`,
para poder auditar despues cuantas veces -- y por que -- el candado dejo
pasar un comando sin poder verificarlo. Escribir ese log nunca puede, a su
vez, convertirse en un fallo: cualquier error al escribirlo se ignora en
silencio (el aviso por stderr ya se hizo aparte).

FALLA ABIERTO ante cualquier otro fallo (JSON ilegible, git ausente, excepcion
no prevista, `fable-gate.json` o `current-task.md` no legibles, o un
`UnicodeEncodeError` al escribir el aviso de bloqueo en una consola con una
codificacion de caracteres limitada): exit 0 con aviso en stderr (y una linea
en el log de observabilidad de arriba). Es un candado de PROCESO, no un
control de seguridad -- no puede verificar que la revision Fable ocurrio de
verdad, solo que alguien escribio la linea que la declara. Un guard roto que
paralizase todo commit seria peor que no tenerlo. La defensa en profundidad de
arriba es la unica zona deliberadamente exenta de este fail-open.

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
from datetime import date, datetime, timezone
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
    contenido, no la parte de la invocacion de git que lo precede.

    KI-069: el CUERPO eliminado incluye, por construccion, el salto de linea
    que separaba el marcador de lo que le seguia en el comando original (casi
    siempre la siguiente linea del script). Ese salto de linea NO es parte
    del "contenido que estorba" -- es la separacion entre esta invocacion y
    la siguiente -- asi que se repone aqui como un `\n` sintetico (junto con
    cualquier resto de la propia linea del marcador anterior al salto, p.ej.
    una redireccion extra tras `<<EOF`). Sin reponerlo, el cierre de comillas
    del delimitador queda pegado sin separador al primer caracter de la
    siguiente linea (`<<'EOF'git add ...`), y el tokenizador de `_tokeniza`
    los funde en un unico token falso que oculta una invocacion de `git`
    real -- la causa raiz confirmada del agujero KI-069 (commit 58330c7)."""
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
        # Resto de la propia linea del marcador, si lo hubiera, ANTES de
        # perder el salto de linea que la termina.
        resultado.append(texto[m.end():salto])
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
        # Repone el salto de linea que el cuerpo eliminado se llevaba
        # consigo (ver docstring de esta funcion -- KI-069).
        resultado.append("\n")
    return "".join(resultado)


def _prepara_texto(command: str) -> str:
    sin_heredocs = _quita_heredocs(command)
    return _CONTINUACION_LINEA_RE.sub(" ", sin_heredocs)


# --- Segmentacion consciente de comillas --------------------------------------


def _segmenta_nivel_superior(texto: str) -> list[tuple[str, bool]]:
    """Trocea `texto` por `&&`, `||`, `;`, `|` suelto (no `||`) y salto de
    linea, pero SOLO fuera de comillas simples/dobles -- un `;` dentro de un
    `-m "fix; algo"` no debe partir el comando en dos. No es un parser de
    shell completo: basta con llevar la cuenta de si estamos dentro de una
    comilla.

    Devuelve una lista de `(segmento, seguido_de_pipe)`: `seguido_de_pipe` es
    `True` solo cuando el separador que cerro ESE segmento fue un `|` suelto
    (otra etapa de la misma tuberia le sigue), y `False` para `&&`, `||`, `;`,
    salto de linea, o el ultimo segmento del texto (sin separador). Lo usa
    `_procesa_texto` (verificacion de Fable 2026-09-26, tercera ronda) para
    decidir si un segmento de la lista blanca de solo lectura (`echo`,
    `printf`, `Write-Output`, ...) debe blanquearse igual que siempre o
    protegerse como cualquier segmento no reconocido: una etapa de la lista
    blanca cuya SALIDA se canaliza hacia otra etapa (`echo "git commit -m m" |
    sh`) deja de ser inocua en ese contexto, aunque ella misma no escriba
    nada, mientras que la misma etapa como ULTIMO eslabon de la tuberia
    (`git status | grep modified`) sigue sin serlo.

    Verificacion de Fable (2026-09-26), hallazgo 2 (segunda ronda): antes, una
    tuberia (`git diff --cached --name-only | xargs git commit -m m --`, `git
    status | sh -c "git commit -m m"`) NO partia el comando en etapas.
    `_localiza_git` tomaba el PRIMER `git` de todo el segmento (el de la
    izquierda de la tuberia), lo marcaba como reconocido, y la etapa real de
    la derecha (donde de verdad ocurria el commit) quedaba oculta tanto al
    analizador -- que ya habia "consumido" el segmento -- como a la red de la
    defensa en profundidad -- que retira los segmentos reconocidos antes de
    buscar el patron textual. Partir tambien por `|` hace que cada etapa de la
    tuberia pase, por separado, por `_localiza_git` (incluida la busqueda de
    ultimo recurso) y por la recursion de wrappers (`sh -c`, `pwsh -Command`,
    ...), y que (b) -- la exclusion de segmentos reconocidos de la red -- solo
    retire la etapa que de verdad se interpreto, no el resto de la tuberia."""
    segmentos: list[tuple[str, bool]] = []
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
            segmentos.append(("".join(actual), False))
            actual = []
            i += 2
            continue
        if c in (";", "\n"):
            segmentos.append(("".join(actual), False))
            actual = []
            i += 1
            continue
        if c == "|":
            # `||` ya se consumio arriba (startswith de 2 caracteres); si
            # llegamos aqui con `c == "|"` es un pipe suelto de una etapa.
            segmentos.append(("".join(actual), True))
            actual = []
            i += 1
            continue
        if c == "\r":
            i += 1
            continue
        actual.append(c)
        i += 1
    segmentos.append(("".join(actual), False))
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


# Verificacion de Fable (2026-09-26), hallazgo 1: comandos de SOLO LECTURA
# cuyo primer token real (tras los mismos prefijos que `_localiza_git` salta)
# esta en esta lista blanca. Solo para estos se blanquea el contenido de sus
# cadenas entre comillas antes de aplicar la red textual de la defensa en
# profundidad (ver `_texto_para_defensa`) -- exactamente como ya se hacia,
# desde antes, para el resto del texto no reconocido estructuralmente. Para
# CUALQUIER OTRO segmento no reconocido (`-c`, `-Command`, `/c`, `eval`,
# `iex`, `xargs`, `python -c`, ...) la cadena se deja intacta: blanquear ahi
# tambien es precisamente el agujero (c) que permitia que un `cmd /c "git add
# x && git commit -m m"` o un `python -c "...subprocess.run(['git',
# 'commit'...])"` pasaran desapercibidos tanto para el analizador como para la
# red.
_COMANDOS_SOLO_LECTURA_BLANQUEABLES = frozenset({
    "echo", "printf", "grep", "rg", "select-string",
    "write-output", "write-host",
})


def _primer_token_efectivo(partes: list[str]) -> str | None:
    """Primer token de un segmento tras saltar los mismos prefijos que
    `_localiza_git` salta (asignacion de entorno, `env`/`command`/`if`, `&`,
    `{`, `(` o un token que empiece por `(`). A diferencia de `_localiza_git`,
    aqui NO se hace busqueda de ultimo recurso: solo interesa el primer
    comando real del segmento, para decidir si es de solo lectura."""
    for t in partes:
        if _ASIGNACION_ENTORNO_RE.match(t):
            continue
        if t.lower() in _PALABRAS_SALTABLES:
            continue
        if t in _TOKENS_SALTABLES_EXACTOS or t.startswith("("):
            continue
        return t
    return None


def _segmento_es_de_solo_lectura(partes: list[str]) -> bool:
    """True si el primer token real de `partes` (ya tokenizado) es uno de los
    comandos de solo lectura de `_COMANDOS_SOLO_LECTURA_BLANQUEABLES`. Se
    compara por nombre base sin extension `.exe`, en minusculas (igual que
    `_es_git`/`_extrae_cadena_wrapper`)."""
    primero = _primer_token_efectivo(partes)
    if primero is None:
        return False
    base = os.path.basename(primero).lower()
    if base.endswith(".exe"):
        base = base[:-4]
    return base in _COMANDOS_SOLO_LECTURA_BLANQUEABLES


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


def _git_diff_cached_o_none(root: Path) -> set[str] | None:
    """Como `_git_name_only(root, ["diff", "--cached", "--name-only"])` pero
    devuelve `None` (nunca un conjunto vacio ambiguo) cuando la llamada a git
    falla de verdad -- proceso ausente, timeout, `returncode != 0` -- para que
    la defensa en profundidad (KI-069, ver docstring del modulo) pueda
    distinguir "nada esta staged" de "no se pudo ni preguntar"."""
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotePath=false", "-C", str(root),
             "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT_SEGUNDOS,
            check=False, env=_entorno_git(),
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return {
        linea.strip().replace("\\", "/")
        for linea in proc.stdout.splitlines()
        if linea.strip()
    }


# --- Recorrido del comando: acumula rutas de `add` y una entrada por `commit` -


def _procesa_texto(
    texto: str, root: Path, acumulado_add: set[str], resultados: list[set[str]],
    profundidad: int = 0, segmentos_reconocidos: list[str] | None = None,
    segmentos_sin_blanquear: list[str] | None = None,
) -> None:
    if profundidad > _PROFUNDIDAD_MAXIMA_RECURSION:
        return
    preparado = _prepara_texto(texto)
    for segmento, seguido_de_pipe in _segmenta_nivel_superior(preparado):
        partes = _tokeniza(segmento)
        if not partes:
            continue
        idx = _localiza_git(partes)
        if idx is not None:
            invocacion = _parsea_invocacion_git_desde(partes, idx)
            if invocacion is None:
                continue
            # Revision Fable 2026-09-26: este segmento de nivel superior SI
            # fue interpretado como una invocacion real de `git` (con
            # cualquier subcomando, no solo `add`/`commit`) -- se recuerda
            # tal cual para que la defensa en profundidad de mas abajo lo
            # retire de su busqueda textual y no lo malinterprete como un
            # patron de commit no analizable (p.ej. `git log --grep commit`
            # o `git commit-tree ...`, ninguno de los cuales commitea nada).
            # Solo tiene sentido al nivel superior: la defensa opera sobre el
            # texto preparado de nivel superior, no sobre cadenas anidadas de
            # `bash -c`/`pwsh -Command` (esas ya se analizan aparte, de forma
            # recursiva, y si contienen un commit real ya aparece en
            # `resultados`).
            if profundidad == 0 and segmentos_reconocidos is not None:
                segmentos_reconocidos.append(segmento)
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
            _procesa_texto(cadena_anidada, root, acumulado_add, resultados, profundidad + 1, None, None)
        # Verificacion de Fable 2026-09-26, hallazgo 1 (segunda ronda): este
        # segmento de nivel superior NO se reconocio como una invocacion real
        # de `git` (ni directamente ni via wrapper). Si tampoco es de solo
        # lectura, se protege de por vida de la red (nunca se le blanquean
        # las comillas en `_texto_para_defensa`) -- ver esa funcion para el
        # porque.
        #
        # Verificacion de Fable 2026-09-26, hallazgo 2 (tercera ronda): un
        # segmento de la lista blanca de solo lectura tambien se protege,
        # igual que uno no reconocido, cuando le sigue una tuberia (`|`
        # suelto) -- su salida se canaliza hacia otra etapa, asi que ya no es
        # inocuo blanquear lo que "dice" (`echo "git commit -m m" | sh`,
        # `printf 'git commit -m m' | bash`). La ULTIMA etapa de una tuberia
        # (sin `seguido_de_pipe`) se sigue blanqueando como siempre si es de
        # solo lectura (`git status | grep modified` sigue en 0).
        if profundidad == 0 and segmentos_sin_blanquear is not None:
            es_lista_blanca = _segmento_es_de_solo_lectura(partes)
            if not es_lista_blanca or seguido_de_pipe:
                segmentos_sin_blanquear.append(segmento)


def _conjuntos_de_rutas_por_commit(
    command: str, root: Path,
) -> tuple[list[set[str]], set[str], list[str], list[str]]:
    """Un elemento por cada `git commit` hallado en `command` (incluidos los
    envueltos en `bash -c`/`sh -c`/`pwsh -Command`), en el orden en que
    aparece. Cada elemento es el conjunto de rutas candidatas para ESE
    commit: lo ya staged, mas lo modificado si lleva `-a`/`--all`, mas lo
    acumulado por los `git add` que lo preceden en el mismo comando, mas los
    pathspecs propios del `git commit`. Devuelve tambien el acumulado final de
    `git add` (aunque no se haya encontrado ningun `git commit`): lo usa la
    defensa en profundidad de KI-069 cuando el analizador no localizo NINGUNA
    invocacion de `git commit`, para no partir de cero si al menos el `git
    add` si se reconocio. Y devuelve, ademas, dos listas de segmentos de nivel
    superior para esa misma defensa en profundidad (verificacion de Fable
    2026-09-26, ver `_texto_para_defensa`): los que SI se reconocieron como
    una invocacion real de `git` (con cualquier subcomando), que la red
    textual debe excluir por completo de su busqueda; y los que NO se
    reconocieron y ADEMAS no son de solo lectura (`_segmento_es_de_solo_lectura`),
    que la red debe dejar intactos -- sin blanquear el contenido de sus
    comillas -- porque una invocacion real de `git commit` pudo quedar
    envuelta ahi dentro sin que el analizador estructurado supiera
    interpretarla (`cmd /c "..."`, `eval "..."`, `python -c "..."`, ...)."""
    acumulado_add: set[str] = set()
    resultados: list[set[str]] = []
    segmentos_reconocidos: list[str] = []
    segmentos_sin_blanquear: list[str] = []
    _procesa_texto(command, root, acumulado_add, resultados, 0,
                    segmentos_reconocidos, segmentos_sin_blanquear)
    return resultados, acumulado_add, segmentos_reconocidos, segmentos_sin_blanquear


# --- Defensa en profundidad (KI-069): unica excepcion deliberada al fail-open -

# Patron laxo, deliberadamente simple: `git` y `commit` como palabras
# completas en la misma linea (sin cruzar saltos de linea, que ya separan
# comandos distintos), sobre el texto YA sin cuerpos de heredoc. No sustituye
# al analisis estructurado de arriba -- es la red que se tiende SOLO cuando
# ese analisis no encontro ninguna invocacion de `git commit` en absoluto.
#
# Revision Fable 2026-09-26: `(?![-\w])` tras `commit` para que no case con
# `commit-tree` (el guion no es caracter de palabra, asi que `\bcommit\b` a
# secas SI casaba ahi). Ver `_texto_para_defensa` para las otras dos
# correcciones (exclusion de segmentos ya reconocidos, blanqueo de comillas).
_GIT_COMMIT_TEXTUAL_RE = re.compile(r"\bgit\b[^\n]*\bcommit\b(?![-\w])")

# Centinela: la defensa en profundidad no pudo ni siquiera preguntarle a git
# que hay staged (`git diff --cached` fallo). Distinto de `None` (que
# significa "no hizo falta ninguna red, no hay patron de commit").
_ANALISIS_FALLIDO = object()


def _blanquea_comillas(texto: str) -> str:
    """Sustituye por espacios el CONTENIDO de las cadenas entre comillas
    simples/dobles (conserva las comillas mismas, los saltos de linea dentro
    de ellas, y todo lo que quede fuera de comillas). Revision Fable
    2026-09-26 (segunda ronda): `git`/`commit` mencionados como TEXTO LITERAL
    dentro del argumento citado de otro comando (`grep -rn 'git commit' ...`,
    `echo "usa git para hacer commit"`) no son una invocacion -- son datos --,
    asi que no deben poder disparar la red textual de mas abajo. Mismo
    rastreo de comillas, caracter a caracter, que `_segmenta_nivel_superior`.

    Verificacion de Fable 2026-09-26 (tercera ronda): una cadena entre
    comillas DOBLES puede, ella misma, contener una invocacion real via
    sustitucion de comandos -- `$(...)` o `` `...` `` -- que bash SI expande
    y ejecuta antes de que el comando exterior (`echo`, `grep`, `Write-Output`,
    ...) vea el resultado: `echo "$(git commit -m m)"`, ``echo "`git commit -m
    m`"``, `grep "$(git commit -m m)" f`, `Write-Output "$(git commit -m
    m)"`. Vaciar ese contenido por igual que un argumento de texto plano
    ocultaba la invocacion real a la red. Ahora, al cerrar una cadena entre
    comillas DOBLES, si su contenido crudo (antes de blanquear) contiene la
    subcadena `$(` o una comilla invertida, se conserva integro en vez de
    blanquearse. El contenido de una cadena entre comillas SIMPLES se sigue
    blanqueando siempre, tenga o no `$(`/backtick: ni bash ni PowerShell
    expanden una sustitucion de comandos dentro de comillas simples, asi que
    ahi nunca hay una invocacion real que preservar."""
    resultado: list[str] = []
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]
        if c in ("'", '"'):
            comilla = c
            j = i + 1
            crudo: list[str] = []
            while j < n and texto[j] != comilla:
                if comilla == '"' and texto[j] == "\\" and j + 1 < n:
                    crudo.append(texto[j])
                    crudo.append(texto[j + 1])
                    j += 2
                    continue
                crudo.append(texto[j])
                j += 1
            cuerpo = "".join(crudo)
            resultado.append(comilla)
            if comilla == '"' and ("$(" in cuerpo or "`" in cuerpo):
                resultado.append(cuerpo)
            else:
                resultado.extend("\n" if ch == "\n" else " " for ch in cuerpo)
            cerrada = j < n
            if cerrada:
                resultado.append(comilla)
                i = j + 1
            else:
                i = j
            continue
        if c == "\\" and i + 1 < n:
            resultado.append(c)
            resultado.append(texto[i + 1])
            i += 2
            continue
        resultado.append(c)
        i += 1
    return "".join(resultado)


def _texto_para_defensa(
    texto_preparado: str, segmentos_reconocidos: list[str],
    segmentos_sin_blanquear: list[str] | None = None,
) -> str:
    """Texto sobre el que corre la red textual de la defensa en profundidad,
    NUNCA el texto crudo. Revision Fable 2026-09-26: retira primero cada
    segmento de nivel superior que el analisis estructurado SI supo
    interpretar como una invocacion real de `git` (cualquier subcomando --
    ver `_procesa_texto`), para que un `git log ...`/`git commit-tree ...`/
    `git show ...` ya entendido no deje ningun rastro que la red pueda
    malinterpretar; despues blanquea el contenido de las cadenas entre
    comillas del resto, para que una mencion literal de `git`/`commit` dentro
    del argumento citado de otro comando tampoco cuente.

    Verificacion de Fable 2026-09-26, hallazgo 1 (agujero (c)): blanquear TODO
    el resto por igual es demasiado agresivo -- vaciaba tambien las comillas
    de segmentos como `cmd /c "git add x && git commit -m m"` o `python -c
    "...subprocess.run(['git','commit'...])"`, donde el contenido citado NO
    es un argumento de texto sino la invocacion real que el analizador
    estructurado no supo interpretar. Ahora solo se blanquean las comillas de
    los segmentos de `_COMANDOS_SOLO_LECTURA_BLANQUEABLES` (`echo`, `printf`,
    `grep`, `rg`, `Select-String`, `Write-Output`, `Write-Host`); el resto de
    segmentos no reconocidos (`segmentos_sin_blanquear`, calculado por
    `_procesa_texto`) se protege temporalmente con un marcador opaco antes de
    blanquear, y se repone tal cual despues -- asi la red sigue viendo su
    texto intacto, comillas incluidas."""
    restante = texto_preparado
    for segmento in segmentos_reconocidos:
        restante = restante.replace(segmento, "", 1)
    marcadores: dict[str, str] = {}
    for n, segmento in enumerate(segmentos_sin_blanquear or []):
        marcador = f"\x00FABLE_GATE_SIN_BLANQUEAR_{n}\x00"
        if segmento in restante:
            restante = restante.replace(segmento, marcador, 1)
            marcadores[marcador] = segmento
    blanqueado = _blanquea_comillas(restante)
    for marcador, segmento in marcadores.items():
        blanqueado = blanqueado.replace(marcador, segmento, 1)
    return blanqueado


def _defensa_en_profundidad(
    texto_preparado: str, root: Path, acumulado_add: set[str],
    segmentos_reconocidos: list[str], segmentos_sin_blanquear: list[str] | None = None,
) -> list[set[str]] | None | object:
    """Ultima red de seguridad -- ver "Defensa en profundidad" en el docstring
    del modulo. Solo se invoca cuando el analisis estructurado no encontro
    NINGUN `git commit`. Si el texto (heredocs ya fuera, segmentos ya
    reconocidos excluidos, comillas ya blanqueadas -- ver
    `_texto_para_defensa`) no contiene ni remotamente el patron `git ...
    commit`, no hay nada que hacer (`None`: fail-open normal, no hay indicio
    de commit). Si lo contiene, se reconstruye un conjunto de rutas de
    respaldo (`git diff --cached` mas lo acumulado de `git add`) y se
    devuelve como si fuera un commit detectado normalmente -- pasa por el
    mismo chequeo de sensibilidad y de cobertura, asi que solo bloquea si de
    verdad hay algo sensible sin cubrir. Si ni siquiera se puede preguntar a
    git, devuelve el centinela `_ANALISIS_FALLIDO` para que el llamador
    bloquee explicando la limitacion, en vez de fallar abierto en silencio."""
    texto_red = _texto_para_defensa(texto_preparado, segmentos_reconocidos, segmentos_sin_blanquear)
    if not _GIT_COMMIT_TEXTUAL_RE.search(texto_red):
        return None
    diff_cached = _git_diff_cached_o_none(root)
    if diff_cached is None:
        return _ANALISIS_FALLIDO
    return [set(acumulado_add) | diff_cached]


def _mensaje_no_analizable() -> str:
    return (
        "COMMIT BLOQUEADO por fable_gate: el comando contiene el patron "
        "'git ... commit', pero el candado no pudo interpretar la invocacion "
        "NI preguntarle a git que hay ya staged (fallo 'git diff --cached'). "
        "Es la unica excepcion deliberada al fail-open de este hook (ver "
        "docstring del modulo, seccion 'Defensa en profundidad'): un commit "
        "que no se puede analizar no se puede dar por inocuo en silencio.\n\n"
        "Separa 'git add' y 'git commit' en comandos Bash/PowerShell simples "
        "(sin heredocs anidados ni envoltorios de shell dificiles de "
        "trocear) y vuelve a intentarlo. Si de verdad no hay nada sensible "
        "que commitear, SQP_FABLE_GATE=off (variable de ENTORNO DE SESION "
        "del operador, nunca un prefijo dentro del propio comando) sigue "
        "disponible como escape."
    )


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


_FAIL_OPEN_LOG_REL = ".claude/automation/runtime/fable_gate.log"


def _registra_fallo_abierto(root: Path, motivo: str) -> None:
    """Observabilidad KI-069: ademas del aviso por stderr, deja una linea con
    marca de tiempo UTC y el motivo en `_FAIL_OPEN_LOG_REL`, para poder
    auditar despues cuantas veces -- y por que -- el candado dejo pasar un
    comando sin poder verificarlo. Nunca debe ser esta funcion la que rompa
    el fail-open: cualquier error al escribir el log (permisos, disco lleno,
    ruta no creable) se ignora en silencio, porque el aviso por stderr ya se
    hizo aparte."""
    try:
        ruta_log = root / _FAIL_OPEN_LOG_REL
        ruta_log.parent.mkdir(parents=True, exist_ok=True)
        marca = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with ruta_log.open("a", encoding="utf-8") as fh:
            fh.write(f"{marca} fail-open: {motivo}\n")
    except Exception:
        pass


def _run(payload: dict, root: Path) -> int:
    tool_name = str((payload or {}).get("tool_name") or "")
    if tool_name not in ("Bash", "PowerShell"):
        return 0

    command = str(((payload or {}).get("tool_input") or {}).get("command") or "")
    if not command.strip():
        return 0

    (conjuntos, acumulado_add, segmentos_reconocidos,
     segmentos_sin_blanquear) = _conjuntos_de_rutas_por_commit(command, root)
    if not conjuntos:
        texto_preparado = _prepara_texto(command)
        respaldo = _defensa_en_profundidad(
            texto_preparado, root, acumulado_add, segmentos_reconocidos, segmentos_sin_blanquear)
        if respaldo is None:
            return 0
        if respaldo is _ANALISIS_FALLIDO:
            print(_mensaje_no_analizable(), file=sys.stderr)
            return 2
        conjuntos = respaldo  # type: ignore[assignment]

    try:
        patrones = _patrones_sensibles(root)
    except Exception as exc:
        motivo = f"no se pudo leer {GATE_CONFIG_REL} ({exc!r})"
        print(f"fable_gate: {motivo}; fail-open (no bloquea).", file=sys.stderr)
        _registra_fallo_abierto(root, motivo)
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

    root = _repo_root()

    try:
        crudo = sys.stdin.read()
    except Exception as exc:
        motivo = f"no se pudo leer stdin ({exc!r})"
        print(f"fable_gate: {motivo}; fail-open.", file=sys.stderr)
        _registra_fallo_abierto(root, motivo)
        return 0

    try:
        payload = json.loads(crudo)
    except Exception as exc:
        motivo = f"JSON de entrada ilegible ({exc!r})"
        print(
            "fable_gate: JSON de entrada ilegible; fail-open. Candado de "
            "proceso, no control de seguridad: no puede verificar nada aqui, "
            "asi que no bloquea.",
            file=sys.stderr,
        )
        _registra_fallo_abierto(root, motivo)
        return 0

    try:
        return _run(payload, root)
    except Exception as exc:
        motivo = f"fallo inesperado ({exc!r})"
        print(
            f"fable_gate: {motivo}; fail-open. No puede "
            "verificar que la revision Fable ocurrio; solo evita el olvido "
            "cuando funciona sin errores.",
            file=sys.stderr,
        )
        _registra_fallo_abierto(root, motivo)
        return 0


if __name__ == "__main__":
    sys.exit(main())
