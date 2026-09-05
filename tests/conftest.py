"""Configuracion comun de la suite.

Existe por una razon concreta: el CI llevaba **rojo desde el 2026-09-02** con
siete fallos que en local no se veian nunca, porque los cuatro dependian del
ENTORNO y el entorno de desarrollo los ocultaba todos. Este fichero cierra el
que se puede cerrar de una vez para toda la suite.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _identidad_git_para_los_repos_de_prueba() -> None:
    """Identidad de git para CUALQUIER commit que haga la suite.

    Varios tests construyen repositorios temporales -- y submodulos dentro de
    ellos -- para ejercitar la revision cruzada. Los helpers configuraban
    `user.name`/`user.email` en el repo EXTERIOR y se olvidaban de los
    interiores. En una maquina de desarrollo eso no se nota: git cae a la
    configuracion global del usuario. En un runner limpio no hay global, y el
    commit muere con `Author identity unknown`. Falla asi
    `test_matrix_submodule_head_move_changes_the_fingerprint` y dos de
    `test_snapshot_v2`.

    Se hace por VARIABLES DE ENTORNO y no anadiendo dos `git config` mas a cada
    helper: las variables las hereda todo subproceso, incluidos los repos que
    cree un test futuro. Arregla la clase, no las tres instancias -- que es la
    diferencia entre esto y volver a estar rojo dentro de un mes.

    `GIT_CONFIG_GLOBAL`/`SYSTEM` NO se tocan a proposito: aislar la config
    global del usuario es tentador, pero cambiaria el comportamiento de los
    tests en la maquina de desarrollo respecto al CI, que es exactamente la
    divergencia que este fichero existe para eliminar.
    """
    import os

    for var, valor in (
        ("GIT_AUTHOR_NAME", "sqp-tests"),
        ("GIT_AUTHOR_EMAIL", "tests@sqp.invalid"),
        ("GIT_COMMITTER_NAME", "sqp-tests"),
        ("GIT_COMMITTER_EMAIL", "tests@sqp.invalid"),
    ):
        os.environ.setdefault(var, valor)
