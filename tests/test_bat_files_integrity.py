"""Integridad byte a byte de los .bat de produccion.

El 2026-09-26 un heredoc de Bash se comio un nivel de contrabarras al editar
DIARIO_COMPLETO.bat: `logs\\backfill` llego como `logs<BS>ackfill` (0x08) y los
tests existentes de los .bat siguieron en verde. cmd.exe no avisa de un caracter
de control en una ruta: la linea simplemente escribe en otro sitio o falla.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BATS = sorted(ROOT.glob("*.bat"))
PERMITIDOS = {9, 10, 13}  # tab, LF, CR


@pytest.mark.parametrize("bat", BATS, ids=[b.name for b in BATS])
def test_bat_has_no_control_characters(bat: Path):
    data = bat.read_bytes()
    malos = sorted({c for c in data if c < 32 and c not in PERMITIDOS})
    assert not malos, f"{bat.name}: caracteres de control {malos}"


@pytest.mark.parametrize("bat", BATS, ids=[b.name for b in BATS])
def test_bat_line_endings_are_uniform(bat: Path):
    lineas = bat.read_bytes().split(b"\n")[:-1]
    crlf = sum(1 for linea in lineas if linea.endswith(b"\r"))
    assert crlf in (0, len(lineas)), f"{bat.name}: mezcla de CRLF y LF"


def test_there_are_bat_files_to_check():
    assert BATS, "no se encontro ningun .bat en la raiz"
