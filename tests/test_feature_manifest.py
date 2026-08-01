"""El manifest de features debe versionar la CONFIG del builder (D-10, 2026-07-31).

`dataset_is_current` decidia reutilizar el CSV cacheado comparando solo el hash
del archivo de resultados. Consecuencia: cambiar `rolling_windows`, `ewm_span` o
`pts_default` -- o el propio codigo del builder -- NO invalidaba la cache, y el
sistema seguia sirviendo un dataset que ya no correspondia al builder vigente.

Es un fallo silencioso y dificil de diagnosticar: no hay error, no hay aviso, y
las features simplemente dejan de significar lo que su nombre dice. Se arregla
metiendo una huella de la configuracion en el manifest.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from sqp.storage.feature_store import (build_training_dataset, builder_fingerprint,
                                       dataset_is_current)


def _sembrar(root, liga="nba", n=140):
    """Resultados minimos para que el builder produzca un dataset."""
    d = root / "data" / "historical"
    d.mkdir(parents=True, exist_ok=True)
    equipos = ["A", "B", "C", "D"]
    filas = []
    for i in range(n):
        h, a = equipos[i % 4], equipos[(i + 1) % 4]
        filas.append({"date": f"2025-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}",
                      "home": h, "away": a,
                      "home_score": 100 + (i % 30), "away_score": 95 + (i % 25),
                      "game_id": f"g{i}", "neutral": False})
    pd.DataFrame(filas).to_csv(d / f"results_{liga}.csv", index=False)


# --- la huella ---------------------------------------------------------------

def test_the_fingerprint_is_stable_for_the_same_config():
    assert builder_fingerprint("nba") == builder_fingerprint("nba")


def test_different_leagues_have_different_fingerprints():
    assert builder_fingerprint("nba") != builder_fingerprint("nfl")


def _reconfig(monkeypatch, liga="nba", **cambios):
    """CONFIGS guarda dataclasses CONGELADOS (buen diseno), asi que se sustituye
    la entrada del diccionario por una copia modificada."""
    import dataclasses

    from sqp.features import builders
    nuevo = dict(builders.CONFIGS)
    nuevo[liga] = dataclasses.replace(builders.CONFIGS[liga], **cambios)
    monkeypatch.setattr(builders, "CONFIGS", nuevo, raising=True)
    monkeypatch.setattr("sqp.storage.feature_store.CONFIGS", nuevo, raising=True)


def test_the_fingerprint_changes_when_the_config_changes(monkeypatch):
    from sqp.features import builders
    antes = builder_fingerprint("nba")
    _reconfig(monkeypatch, ewm_span=builders.CONFIGS["nba"].ewm_span + 1)
    assert builder_fingerprint("nba") != antes, (
        "cambiar ewm_span debe cambiar la huella; si no, la cache no se invalida")


def test_the_fingerprint_changes_when_the_windows_change(monkeypatch):
    antes = builder_fingerprint("nba")
    _reconfig(monkeypatch, rolling_windows=[3, 6, 9])
    assert builder_fingerprint("nba") != antes


def test_mlb_has_its_own_fingerprint_from_its_own_builder(monkeypatch):
    """MLB no usa CONFIGS: tiene constantes propias en features/mlb.py."""
    from sqp.features import mlb as mlb_features
    antes = builder_fingerprint("mlb")
    monkeypatch.setattr(mlb_features, "EWM_SPAN", mlb_features.EWM_SPAN + 1, raising=True)
    assert builder_fingerprint("mlb") != antes


# --- invalidacion de la cache ------------------------------------------------

def test_a_freshly_built_dataset_is_current(tmp_path):
    _sembrar(tmp_path)
    build_training_dataset("nba", root=tmp_path)
    assert dataset_is_current(tmp_path, "nba")


def test_changing_the_builder_config_invalidates_the_cache(tmp_path, monkeypatch):
    """El corazon de D-10: mismos resultados, otra config -> hay que reconstruir."""
    _sembrar(tmp_path)
    build_training_dataset("nba", root=tmp_path)
    assert dataset_is_current(tmp_path, "nba")

    from sqp.features import builders
    _reconfig(monkeypatch, ewm_span=builders.CONFIGS["nba"].ewm_span + 1)
    assert not dataset_is_current(tmp_path, "nba"), (
        "la cache sigue viendose vigente tras cambiar el builder: es D-10")


def test_changing_the_results_still_invalidates_the_cache(tmp_path):
    """No-regresion: la comprobacion original por hash de resultados sigue viva."""
    _sembrar(tmp_path)
    build_training_dataset("nba", root=tmp_path)
    _sembrar(tmp_path, n=180)
    assert not dataset_is_current(tmp_path, "nba")


def test_the_manifest_records_the_fingerprint(tmp_path):
    _sembrar(tmp_path)
    build_training_dataset("nba", root=tmp_path)
    m = json.loads((tmp_path / "data" / "feature_store" / "nba_manifest.json")
                   .read_text(encoding="utf-8"))
    assert m.get("builder_fingerprint") == builder_fingerprint("nba")
    assert m.get("source_hash"), "el hash de resultados debe seguir presente"


def test_an_old_manifest_without_fingerprint_forces_a_rebuild(tmp_path):
    """Manifests escritos antes de este arreglo no llevan huella: deben tratarse
    como caducados en vez de darse por vigentes."""
    _sembrar(tmp_path)
    build_training_dataset("nba", root=tmp_path)
    p = tmp_path / "data" / "feature_store" / "nba_manifest.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    m.pop("builder_fingerprint", None)
    p.write_text(json.dumps(m), encoding="utf-8")
    assert not dataset_is_current(tmp_path, "nba")


def test_a_corrupt_manifest_degrades_to_rebuild(tmp_path):
    _sembrar(tmp_path)
    build_training_dataset("nba", root=tmp_path)
    (tmp_path / "data" / "feature_store" / "nba_manifest.json").write_text(
        "{ esto no es json", encoding="utf-8")
    assert not dataset_is_current(tmp_path, "nba")


@pytest.mark.parametrize("liga", ["nba", "nfl", "nhl", "mlb"])
def test_every_supported_league_can_produce_a_fingerprint(liga):
    assert isinstance(builder_fingerprint(liga), str)
    assert len(builder_fingerprint(liga)) >= 8
