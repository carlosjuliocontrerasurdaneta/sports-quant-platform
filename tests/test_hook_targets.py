"""Los hooks PostToolUse tienen que cubrir TAMBIEN las escrituras hechas por Bash.

AUDITORIA INTEGRAL 2026-09-07, AUD-MED-002. Los cuatro hooks `PostToolUse`
estaban cableados con `"matcher": "Edit|Write"` y los cuatro sacaban la ruta de
`tool_input.file_path`. El matcher filtra por NOMBRE DE HERRAMIENTA -- es el
hecho sobre el que `require-dispatch-model.sh` construyo el cierre de KI-023 --,
asi que una llamada de la herramienta `Bash` no emparejaba con ninguno y ademas
no trae `file_path`. Un fichero editado con `sed -i`, un heredoc o una
redireccion no armaba el centinela de tests, no armaba el de revision cruzada y
no pasaba por el detector de secretos: tres controles en silencio, y no por una
ruta hipotetica -- hay modos de operacion del agente que instruyen preferir Bash
para editar.

Es la MISMA enfermedad que KI-033 un piso mas arriba: alli no casaba el PATRON
(contrabarra de Windows contra globs con barra), aqui no casa la HERRAMIENTA.

Y al arreglarlo aparecio la tercera capa de lo mismo, que estos tests fijan: en
Windows `print()` emite CRLF, asi que cada ruta llegaba al bucle con un CR final
-- `[ -f "$file" ]` fallaba y `*src/*.py` no emparejaba porque la cadena ya no
acaba en `.py` --, y los hooks recorrian los ficheros saltandolos TODOS, en
silencio y con codigo 0. Se detecto ejercitandolos con `bash -x`, no leyendolos.

Estos tests NO invocan bash: `subprocess` en esta maquina resuelve el bash de
WSL --sin distro instalada-- y eso ya produjo un diagnostico equivocado el
2026-09-05 (ver `test_the_normalisation_actually_maps_windows_paths`). Se
comprueba la estructura del cableado y la SEMANTICA del derivador de rutas
importandolo, que es lo que si se puede afirmar sin ambiguedad.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"
SETTINGS = ROOT / ".claude" / "settings.json"

BS = chr(92)    # contrabarra, construida asi para que ninguna herramienta
                # intermedia se la coma al escribir este fichero
CR = chr(13)

# Reparto declarado en la cabecera de `_targets.py`. Los que solo LEEN o hacen
# `touch` cubren Bash; el que MUTA (`ruff check --fix`) no, para que una lectura
# no pueda disparar una escritura.
CUBREN_BASH = ("check-secrets.sh", "mark-tests-pending.sh",
               "mark-crossreview-pending.sh")
SOLO_EDIT_WRITE = ("post-edit-format.sh",)


def _targets():
    spec = importlib.util.spec_from_file_location("_targets", HOOKS / "_targets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _matchers() -> dict[str, str]:
    cfg = json.loads(SETTINGS.read_text(encoding="utf-8"))
    fuera = {}
    for grupo in cfg["hooks"]["PostToolUse"]:
        for h in grupo["hooks"]:
            fuera[h["command"].rsplit("/", 1)[-1].strip('"')] = grupo["matcher"]
    return fuera


# --- 1. Cableado -------------------------------------------------------------

@pytest.mark.parametrize("hook", CUBREN_BASH)
def test_the_control_hooks_are_wired_for_bash_writes_too(hook):
    matcher = _matchers().get(hook)
    assert matcher is not None, f"{hook} dejo de estar cableado en PostToolUse"
    assert "Bash" in matcher, (
        f"{hook} solo empareja con {matcher!r}: una escritura hecha con `sed`, "
        "un heredoc o una redireccion no lo dispara y el control queda en "
        "silencio (AUD-MED-002)")


@pytest.mark.parametrize("hook", SOLO_EDIT_WRITE)
def test_the_mutating_hook_deliberately_stays_out_of_bash(hook):
    """No es un olvido: es la asimetria documentada. `post-edit-format` MUTA
    ficheros, y con Bash la ruta habria que deducirla del comando -- un simple
    `cat src/x.py` dispararia un `ruff check --fix` sobre algo que solo se
    leyo. Su garantia la da `ruff check` como puerta bloqueante de CI."""
    matcher = _matchers().get(hook)
    assert matcher is not None, f"{hook} dejo de estar cableado"
    assert "Bash" not in matcher, (
        f"{hook} MUTA ficheros: cubrir Bash convertiria una lectura en una "
        "escritura. Si la decision cambia, cambia tambien este test y su razon.")


@pytest.mark.parametrize("hook", CUBREN_BASH)
def test_every_bash_capable_hook_derives_its_targets(hook):
    """Un hook que empareja con Bash y sigue leyendo `file_path` no ve nada:
    Bash no aporta ese campo. La combinacion es la averia, no cada mitad."""
    texto = (HOOKS / hook).read_text(encoding="utf-8")
    assert "_targets.py" in texto, (
        f"{hook} empareja con Bash pero no deriva rutas con `_targets.py`: "
        "`tool_input.file_path` viene vacio en toda llamada Bash")


# --- 2. El retorno de carro --------------------------------------------------

@pytest.mark.parametrize("hook", CUBREN_BASH)
def test_every_hook_reading_a_path_list_trims_the_carriage_return(hook):
    """Cierra la CLASE, no la instancia. Cualquier hook que consuma la lista de
    `_targets.py` y no recorte el CR volveria a saltarse todos los ficheros en
    silencio."""
    texto = (HOOKS / hook).read_text(encoding="utf-8")
    recorte = '${file%$' + "'" + BS + "r'" + '}'
    assert recorte in texto, (
        f"{hook} no recorta el retorno de carro. En Windows `print()` emite "
        "CRLF y el bucle saltaria TODOS los ficheros con exit 0.")


def test_the_target_helper_emits_only_line_feeds():
    """La otra punta del mismo candado: el productor no debe emitir CRLF."""
    texto = (HOOKS / "_targets.py").read_text(encoding="utf-8")
    assert 'reconfigure(newline="' + BS + 'n")' in texto, (
        "_targets.py dejo de forzar LF en stdout: en Windows volveria a emitir "
        "CRLF y los hooks recibirian rutas con un CR final")


def test_the_carriage_return_actually_breaks_the_glob():
    """Que la regla de arriba no se cumpla con una linea decorativa: se mide la
    semantica del glob, igual que hace el test hermano de la contrabarra."""
    import fnmatch
    ruta = "C:/dev/3/sqp/src/sqp/config.py"
    assert fnmatch.fnmatchcase(ruta, "*src/*.py")
    assert not fnmatch.fnmatchcase(ruta + CR, "*src/*.py"), (
        "premisa: con un CR final la cadena ya no acaba en `.py`")


# --- 3. Semantica del derivador ----------------------------------------------

def _correr(mod, payload: dict, *argv: str) -> list[str]:
    """Ejecuta `main()` con un payload, sin subprocess ni bash."""
    import io
    import sys
    stdin, stdout, args = sys.stdin, sys.stdout, sys.argv
    sys.stdin = io.StringIO(json.dumps(payload))
    sys.stdout = io.StringIO()
    sys.argv = ["_targets.py", *argv]
    try:
        rc = mod.main()
        salida = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout, sys.argv = stdin, stdout, args
    assert rc == 0, "el derivador nunca debe salir distinto de 0"
    return [ln for ln in salida.splitlines() if ln]


def test_an_explicit_file_path_wins_and_is_returned_verbatim():
    """La ruta de Edit/Write manda y llega SIN tocar: los hooks normalizan el
    separador por su cuenta y esperan la ruta tal cual la dio el harness."""
    mod = _targets()
    ruta = "C:" + BS + "dev" + BS + "sqp" + BS + "src" + BS + "sqp" + BS + "config.py"
    salida = _correr(mod, {"tool_input": {"file_path": ruta,
                                          "command": "no-mirar-esto.py"}})
    assert salida == [ruta]


def test_a_broken_payload_fails_open_with_no_targets():
    """Falla ABIERTO, como el resto de la cadena de hooks: un JSON ilegible no
    puede paralizar cada llamada a herramienta."""
    import io
    import sys
    mod = _targets()
    stdin, stdout, args = sys.stdin, sys.stdout, sys.argv
    sys.stdin = io.StringIO('{"tool_input": {"file_path"')
    sys.stdout = io.StringIO()
    sys.argv = ["_targets.py"]
    try:
        rc, salida = mod.main(), sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout, sys.argv = stdin, stdout, args
    assert rc == 0 and salida.strip() == ""


def test_a_bash_command_yields_the_paths_it_names(tmp_path):
    m = _targets()
    (tmp_path / "src").mkdir()
    objetivo = tmp_path / "src" / "cosa.py"
    objetivo.write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "otro.txt").write_text("x", encoding="utf-8")
    hallados = m._del_comando("sed -i s/x/y/ src/cosa.py && cat otro.txt", tmp_path)
    assert [Path(p).name for p in hallados] == ["cosa.py"], (
        "el derivador debe ver el .py NOMBRADO en el comando y solo ese")


def test_a_command_naming_nothing_yields_nothing(tmp_path):
    assert _targets()._del_comando("ls -la", tmp_path) == []


def test_a_named_path_that_does_not_exist_is_not_invented(tmp_path):
    """Precision: el derivador no puede fabricar ficheros. Un hook que actua
    sobre una ruta inexistente es ruido, y `check-secrets` la abriria."""
    assert _targets()._del_comando("sed -i s/x/y/ src/fantasma.py", tmp_path) == []


def test_the_result_is_capped_so_a_huge_diff_cannot_hang_a_hook(tmp_path):
    m = _targets()
    assert isinstance(m._MAX, int) and 0 < m._MAX <= 200, (
        "el techo de ficheros desaparecio: un `git status` con cientos de "
        "cambios convertiria un hook de 30 s en uno que no termina")
