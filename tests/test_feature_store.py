"""Tests for the ported feature store + generic builder. SYNTHETIC data only."""
from __future__ import annotations

import pytest

from sqp.features.builders import CONFIGS, build_team_rolling_dataset
from sqp.storage import feature_store as fs
from sqp.storage.results_store import ResultsStore


def _seed_results(root, league="nba"):
    """A small chronological set of games (base CSV schema: home/away)."""
    games = [
        {"date": "2024-01-01", "home": "LAL", "away": "BOS", "game_id": "1",
         "home_score": 110, "away_score": 100},
        {"date": "2024-01-03", "home": "BOS", "away": "LAL", "game_id": "2",
         "home_score": 105, "away_score": 108},
        {"date": "2024-01-05", "home": "LAL", "away": "MIA", "game_id": "3",
         "home_score": 99, "away_score": 101},
        {"date": "2024-01-07", "home": "MIA", "away": "BOS", "game_id": "4",
         "home_score": 120, "away_score": 115},
        {"date": "2024-01-09", "home": "BOS", "away": "MIA", "game_id": "5",
         "home_score": 98, "away_score": 97},
    ]
    ResultsStore(root).upsert(league, games)
    return games


def test_builder_is_temporal_and_complete(tmp_path):
    df = fs._results_df(tmp_path, "nba")  # empty -> seed first
    _seed_results(tmp_path, "nba")
    df = fs._results_df(tmp_path, "nba")
    out, state = build_team_rolling_dataset(df, CONFIGS["nba"])

    assert len(out) == 5
    # core label/columns present
    for col in ("home_win", "total_pts", "home_win_rate", "home_pts_l5", "diff_rest_days"):
        assert col in out.columns
    # temporal correctness: earliest game has no prior games for either team
    first = out.sort_values("date").iloc[0]
    assert first["home_games"] == 0 and first["away_games"] == 0
    # a team that has played shows accumulated games later
    assert out["home_games"].max() >= 1
    assert set(state) == {"LAL", "BOS", "MIA"}


def test_build_training_dataset_persists_and_reuses(tmp_path):
    _seed_results(tmp_path, "nba")
    out = fs.build_training_dataset("nba", root=tmp_path)
    assert len(out) == 5
    assert fs._feature_path(tmp_path, "nba").exists()
    assert fs._manifest_path(tmp_path, "nba").exists()
    assert (tmp_path / "data" / "feature_store" / "nba_team_state.csv").exists()
    # unchanged source -> reused (current)
    assert fs.dataset_is_current(tmp_path, "nba")


def test_unknown_league_rejected(tmp_path):
    with pytest.raises(ValueError):
        fs.build_training_dataset("epl", root=tmp_path)  # no ML builder for soccer


def test_nhl_uses_total_goals(tmp_path):
    _seed_results(tmp_path, "nhl")
    out = fs.build_training_dataset("nhl", root=tmp_path)
    assert "total_goals" in out.columns and "total_pts" not in out.columns


class TestLaHuellaCubreTodasLasFuentes:
    """AUD-20260906-05 (Codex, MEDIUM, REPRODUCED).

    `_mlb_results_df` une resultados Y abridores, pero `_source_hash` solo
    hasheaba el fichero de resultados. Corregir un abridor cambiaba el dataset y
    dejaba la huella IDENTICA, asi que `dataset_is_current` seguia diciendo True
    y el entrenamiento reutilizaba identidad y estadisticas obsoletas sin aviso.

    Reproducido: con el mismo `results_mlb.csv`, el cuarto partido pasaba de
    "Pitcher H" a "New starter" en el dataset y la huella no se movia.
    """

    @staticmethod
    def _seed(root):
        ResultsStore(root).upsert("mlb", [
            {"date": f"2026-0{m}-01", "home": "A", "away": "B", "game_id": f"g{m}",
             "home_score": 3, "away_score": 1} for m in (1, 2, 3, 4)])

    @staticmethod
    def _abridor(gid, quien):
        return {"game_id": gid, "date": f"2026-0{gid[-1]}-01",
                "home_starter": quien, "away_starter": "Pitcher A"}

    def test_corregir_un_abridor_invalida_la_cache(self, tmp_path):
        from sqp.storage.starters import StartersStore
        self._seed(tmp_path)
        St = StartersStore(tmp_path)
        St.save("mlb", [self._abridor(f"g{m}", "Pitcher H") for m in (1, 2, 3, 4)])
        antes = fs._source_hash(tmp_path, "mlb")
        # El dataset SI cambia: es lo que hace que la huella deba cambiar.
        assert fs._mlb_results_df(tmp_path).iloc[3]["home_pitcher"] == "Pitcher H"
        St.save("mlb", [self._abridor("g4", "New starter")])
        assert fs._mlb_results_df(tmp_path).iloc[3]["home_pitcher"] == "New starter"
        assert fs._source_hash(tmp_path, "mlb") != antes

    def test_anadir_el_fichero_de_abridores_que_faltaba_invalida(self, tmp_path):
        """Presencia y ausencia son estados distintos: sin el byte de presencia,
        "no existe" y "existe vacio" tendrian la misma huella."""
        from sqp.storage.starters import StartersStore
        self._seed(tmp_path)
        sin = fs._source_hash(tmp_path, "mlb")
        StartersStore(tmp_path).save("mlb", [self._abridor("g1", "Pitcher H")])
        assert fs._source_hash(tmp_path, "mlb") != sin

    def test_sin_cambios_la_huella_es_estable(self, tmp_path):
        """Contraprueba obligatoria: una huella que cambiara siempre pasaria los
        dos tests de arriba y reconstruiria el dataset en cada ejecucion."""
        from sqp.storage.starters import StartersStore
        self._seed(tmp_path)
        StartersStore(tmp_path).save("mlb", [self._abridor("g1", "Pitcher H")])
        assert fs._source_hash(tmp_path, "mlb") == fs._source_hash(tmp_path, "mlb")

    def test_sin_resultados_no_hay_huella(self, tmp_path):
        """El fichero de resultados sigue siendo la fuente obligatoria: sin el no
        hay dataset posible, y la huella es None (cache no vigente)."""
        assert fs._source_hash(tmp_path, "mlb") is None

    def test_una_liga_sin_abridores_solo_depende_de_sus_resultados(self, tmp_path):
        """El ambito por liga: escribir abridores de MLB no puede invalidar el
        dataset de la NBA."""
        from sqp.storage.starters import StartersStore
        _seed_results(tmp_path, "nba")
        antes = fs._source_hash(tmp_path, "nba")
        StartersStore(tmp_path).save("mlb", [self._abridor("g1", "Pitcher H")])
        assert fs._source_hash(tmp_path, "nba") == antes

    def test_las_fuentes_declaradas_son_las_que_lee_el_builder(self, tmp_path):
        """Fija la correspondencia que el defecto rompio: `_source_paths` y lo
        que el builder consume son la misma cosa dicha dos veces."""
        paths = fs._source_paths(tmp_path, "mlb")
        nombres = [p.name for p in paths]
        assert nombres == ["results_mlb.csv", "starters_mlb.csv"]
        assert fs._source_paths(tmp_path, "nba") == [ResultsStore(tmp_path).path("nba")]
