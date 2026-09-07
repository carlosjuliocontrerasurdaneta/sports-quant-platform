"""El codigo de salida de `scripts/validate_oos.py` distingue "nada que validar"
de "algo se rompio" (KI-034).

Hasta el 2026-09-06 ambas cosas sumaban al mismo contador `failures` y el script
salia con 1. Daba igual mientras nadie mirara ese codigo: la tarea mensual
`SQP_Validate_OOS_Cdev` terminaba con `LastTaskResult = 1` y nadie se enteraba.

Desde AUD-MED-003 el centinela SI lo mira y lo eleva a ERROR en el health check,
asi que un 1 fabricado por una liga sin backfill encenderia una alarma sobre una
condicion normal. Y una alarma que suena cuando no pasa nada se aprende a
ignorar -- que es exactamente como el CI de este repositorio llego a estar 75
runs seguidos en rojo sin que nadie mirara.

No hay fichero de tests previo para este script: se crea con el arreglo.
"""
from __future__ import annotations

import importlib.util

import pytest

from sqp.config import ROOT


def _cargar():
    """Carga el script como modulo. Es un CLI, no un paquete importable."""
    spec = importlib.util.spec_from_file_location(
        "validate_oos_cli", ROOT / "scripts" / "validate_oos.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cli():
    return _cargar()


def test_una_liga_sin_cuotas_de_cierre_no_es_un_fallo(cli, monkeypatch, capsys):
    """El caso que encendia la alarma sin motivo: una liga descubierta cuyo
    backfill de cuotas todavia no existe."""
    monkeypatch.setattr(cli, "load_closing_odds", lambda root, lg: {})
    monkeypatch.setattr(cli.sys, "argv", ["validate_oos.py", "--leagues", "mlb", "nba"])
    assert cli.main() == 0
    salida = capsys.readouterr().out
    assert "0 liga(s) validada(s) de 2" in salida
    assert "Nada que validar en: mlb, nba" in salida


def test_sin_ninguna_liga_descubierta_tampoco_es_un_fallo(cli, monkeypatch):
    """Rama que ya salia con 0; se fija para que no derive con el cambio."""
    monkeypatch.setattr(cli, "discover_leagues_with_odds", lambda root: [])
    monkeypatch.setattr(cli.sys, "argv", ["validate_oos.py"])
    assert cli.main() == 0


def test_un_error_de_verdad_sigue_saliendo_distinto_de_cero(cli, monkeypatch):
    """Contraprueba obligatoria: sin ella, "devolver 0 siempre" pasaria los dos
    tests de arriba y el script no podria avisar de nada.

    Un fallo real propaga la excepcion y `SystemExit(main())` la convierte en un
    codigo distinto de cero. Lo que se elimino es el 1 FABRICADO por una
    condicion normal, no la capacidad de fallar.
    """
    def revienta(root, lg):
        raise RuntimeError("el store de cuotas esta corrupto")

    monkeypatch.setattr(cli, "load_closing_odds", revienta)
    monkeypatch.setattr(cli.sys, "argv", ["validate_oos.py", "--leagues", "mlb"])
    with pytest.raises(RuntimeError):
        cli.main()


def test_no_declara_fallo_por_una_liga_sin_backfill(cli, monkeypatch):
    """Version explicita del contrato, dicha como invariante: el numero de ligas
    sin cuotas no puede cambiar el codigo de salida."""
    for n in (1, 5, 33):
        monkeypatch.setattr(cli, "load_closing_odds", lambda root, lg: {})
        monkeypatch.setattr(cli.sys, "argv",
                            ["validate_oos.py", "--leagues", *[f"l{i}" for i in range(n)]])
        assert cli.main() == 0, f"{n} ligas sin cuotas devolvieron un fallo"
