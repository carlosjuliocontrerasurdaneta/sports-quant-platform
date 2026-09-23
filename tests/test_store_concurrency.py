"""Escrituras concurrentes en los stores historicos (AUD-009, ronda
audit-2026-09-23; OPENAI-006, reproducido).

`atomic_write_csv` protege el FICHERO, no la transaccion leer/fusionar/escribir.
Dos backfills solapados leian el mismo estado, y el ultimo en escribir borraba
en silencio las filas que el otro acababa de guardar: `['seed','A','B']`
terminaba como `['seed','A']` en los tres stores.
"""
from __future__ import annotations

import threading

import pandas as pd
import pytest

from sqp.storage import results_store, starter_fip, starters


def _result(gid):
    return {"date": "2026-09-01", "home": f"H{gid}", "away": f"A{gid}",
            "game_id": gid, "home_score": 1, "away_score": 0, "neutral": False}


def _starter(gid):
    return {"game_id": gid, "date": "2026-09-01", "home_starter": f"p{gid}",
            "away_starter": f"q{gid}"}


def _fip(gid):
    return {"game_id": gid, "date": "2026-09-01", "home_starter": f"p{gid}",
            "home_starter_fip": 3.2, "away_starter": f"q{gid}",
            "away_starter_fip": 4.1}


CASOS = [
    pytest.param(results_store, lambda r: results_store.ResultsStore(r),
                 "upsert", _result, id="ResultsStore"),
    pytest.param(starters, lambda r: starters.StartersStore(r),
                 "save", _starter, id="StartersStore"),
    pytest.param(starter_fip, lambda r: starter_fip.StarterFIPStore(r),
                 "save", _fip, id="StarterFIPStore"),
]


@pytest.mark.parametrize("modulo, fabrica, metodo, fila", CASOS)
def test_dos_escritores_solapados_conservan_la_union(tmp_path, monkeypatch,
                                                     modulo, fabrica, metodo, fila):
    store = fabrica(tmp_path)
    getattr(store, metodo)("mlb", [fila("seed")])

    a_preparado = threading.Event()
    b_termino = threading.Event()
    escribir = modulo.atomic_write_csv

    def escritura_con_pausa(df, path):
        if threading.current_thread().name == "A":
            a_preparado.set()
            # Sin lock, B completa su escritura dentro de esta espera y A la
            # pisa. Con lock, B espera a A, la espera vence y A sigue.
            b_termino.wait(timeout=2.0)
        return escribir(df, path)

    monkeypatch.setattr(modulo, "atomic_write_csv", escritura_con_pausa)
    errores: list[BaseException] = []

    def a():
        try:
            getattr(fabrica(tmp_path), metodo)("mlb", [fila("A")])
        except BaseException as exc:  # noqa: BLE001
            errores.append(exc)

    def b():
        try:
            a_preparado.wait(timeout=10)
            getattr(fabrica(tmp_path), metodo)("mlb", [fila("B")])
            b_termino.set()
        except BaseException as exc:  # noqa: BLE001
            errores.append(exc)

    hilos = [threading.Thread(target=a, name="A"), threading.Thread(target=b, name="B")]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=60)
    assert not errores, errores
    ids = set(pd.read_csv(store.path("mlb"), dtype={"game_id": str})["game_id"])
    assert ids == {"seed", "A", "B"}
