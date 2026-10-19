"""`requirements.lock` fija el cierre transitivo COMPLETO de runtime + dev.

Auditoria audit-2026-10-18, AUD-016: el lock decia filtrar "sqp's runtime + dev
dependency tree" pero faltaban siete paquetes del cierre, entre ellos narwhals,
dependencia de runtime de scikit-learn 1.9. El CI los instalaba sin pin y
`pip-audit -r requirements.lock` no los auditaba. Se recorre el arbol con los
metadatos del entorno INSTALADO (marcadores evaluados en este interprete), asi
que el test vale igual en la maquina de produccion que en cada pata del CI.
"""
from __future__ import annotations

import importlib.metadata as md
import re
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
_RAICES = ("numpy", "pandas", "scipy", "scikit-learn", "joblib", "requests",
           "pyyaml", "python-dotenv", "pytest", "pytest-cov", "ruff", "mypy")


def _norm(nombre: str) -> str:
    return re.sub(r"[-_.]+", "-", nombre).lower()


def _cierre_instalado() -> set[str]:
    vistos: set[str] = set()
    pila = list(_RAICES)
    while pila:
        nombre = _norm(pila.pop())
        if nombre in vistos:
            continue
        try:
            dist = md.distribution(nombre)
        except md.PackageNotFoundError:
            continue
        vistos.add(nombre)
        for crudo in dist.requires or []:
            req = Requirement(crudo)
            if req.marker is not None and not req.marker.evaluate({"extra": ""}):
                continue
            pila.append(req.name)
    return vistos


def _fijados() -> set[str]:
    texto = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    return {_norm(m.group(1)) for m in re.finditer(r"(?m)^([A-Za-z0-9_.\-]+)==", texto)}


def test_the_lock_pins_the_whole_installed_closure():
    faltan = sorted(_cierre_instalado() - _fijados())
    assert not faltan, f"requirements.lock no fija: {faltan}"
