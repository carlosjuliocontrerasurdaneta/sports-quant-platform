"""Toda clave de `configs/default.yaml` debe tener un consumidor real.

Auditoria integral 2026-09-07, AUD-MED-003. `configs/default.yaml` declaraba dos
bloques que `Settings.load()` NUNCA recorria:

    odds:        regions / markets / odds_format
    simulation:  n_sims / seed

Editarlos no cambiaba nada, y peor: `odds.regions` decia `"us,eu"` mientras
`RUN_DIARIO_ALL.bat` fija `ODDS_API_REGIONS=us,us2,uk,eu,au`. Como el coste por
liga es `(markets x regions) + 1`, el unico fichero VERSIONADO que describia la
configuracion de cuotas declaraba 7 creditos/liga/dia donde produccion gasta 16.
Nadie lo detecto porque nada obligaba a que una clave declarada se leyera.

Es la misma enfermedad que `_warn_risk_divergence` existe para hacer audible --
"el yaml versionado NO describe esta produccion" --, pero esa funcion solo cubre
las ocho claves de `risk`. Este modulo cubre el fichero entero, y por CLASE: una
clave nueva sin cablear deja la suite en rojo el mismo dia que se escribe, no en
la auditoria de dentro de tres meses.

La lista de claves consumidas NO se escribe a mano: se DERIVA del fuente de
`sqp.config`. Una lista literal es otro artefacto que puede derivar, que es
justo el modo de fallo dominante de este repositorio.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from sqp.config import CONFIG_DIR, load_yaml

CONFIG_SRC = Path(__file__).resolve().parents[1] / "src" / "sqp" / "config.py"

# Las tres formas con las que `Settings.load()` toca el mapa del yaml:
#   cfg.get("x")      /  cfg["x"]  /  "x" in cfg
_ACCESOS = (
    re.compile(r'cfg\.get\(\s*"([a-z_]+)"'),
    re.compile(r'cfg\[\s*"([a-z_]+)"\s*\]'),
    re.compile(r'"([a-z_]+)"\s+in\s+cfg\b'),
)


def _claves_consumidas() -> set[str]:
    src = CONFIG_SRC.read_text(encoding="utf-8")
    return {m for pat in _ACCESOS for m in pat.findall(src)}


def test_the_extraction_actually_finds_the_known_keys():
    """Premisa: si el regex dejara de encontrar nada, el test de abajo pasaria
    vacio y seria decorativo. Se ancla en claves que existen desde hace meses."""
    consumidas = _claves_consumidas()
    for clave in ("risk", "bankroll", "calibration", "prediction_gate", "weather"):
        assert clave in consumidas, (
            f"la extraccion no ve `{clave}` en config.py: el patron de acceso "
            "cambio y este candado dejo de medir nada")


def test_every_declared_yaml_key_has_a_consumer_in_settings_load():
    cfg = load_yaml(CONFIG_DIR / "default.yaml")
    inertes = sorted(set(cfg) - _claves_consumidas())
    assert not inertes, (
        f"claves declaradas en configs/default.yaml que `Settings.load()` NO "
        f"lee: {inertes}. Una clave inerte no es documentacion: es una trampa "
        "-- alguien la edita esperando cambiar produccion y no cambia nada. "
        "Cablea la clave en `Settings.load()`, o retirala del yaml dejando "
        "escrito donde vive el valor de verdad.")


def test_the_retired_blocks_do_not_come_back_silently():
    """`odds:` y `simulation:` fueron los dos casos reales. Vuelven solo con
    consumidor: si alguien los re-declara sin cablearlos, el test de arriba ya
    lo caza; este deja el precedente nombrado en el diff."""
    cfg = load_yaml(CONFIG_DIR / "default.yaml")
    consumidas = _claves_consumidas()
    for clave in ("odds", "simulation"):
        if clave in cfg:
            assert clave in consumidas, (
                f"`{clave}:` vuelve a estar en default.yaml sin que "
                "`Settings.load()` lo lea. Es exactamente AUD-MED-003.")


@pytest.mark.parametrize("clave", ["regions", "markets", "odds_format"])
def test_the_real_source_of_the_odds_configuration_is_documented(clave):
    """Retirar una clave sin decir donde vive el valor deja al operador peor que
    antes. El comentario del yaml tiene que nombrar la fuente real."""
    texto = (CONFIG_DIR / "default.yaml").read_text(encoding="utf-8")
    assert clave in texto, (
        f"el yaml ya no explica donde se fija `{clave}` de verdad (env var, BAT "
        "o literal del codigo): la retirada de AUD-MED-003 perdio su rastro")
