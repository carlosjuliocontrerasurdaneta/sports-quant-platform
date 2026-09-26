"""`sqp.pipeline.goalie_backfill.run`: matching, deduplication and resumable
checkpointing, with the NHL API fully mocked (no network, no `data/`)."""
from datetime import date

import pytest
import requests

from sqp.pipeline import goalie_backfill
from sqp.storage.goalies import GoalieAppearanceStore
from sqp.storage.results_store import ResultsStore


def _seed_results(root):
    ResultsStore(root).upsert("nhl", [{
        "date": "2024-10-10", "home": "Boston Bruins", "away": "Montreal Canadiens",
        "game_id": "ESPN-1", "home_score": 6, "away_score": 4, "neutral": False,
    }])


_SCORE_BY_DATE = {
    "2024-10-10": {"games": [{
        "id": 111, "gameType": 2, "startTimeUTC": "2024-10-10T23:00:00Z",
        "homeTeam": {"name": {"default": "Bruins"}},
        "awayTeam": {"name": {"default": "Canadiens"}},
    }]},
    "2024-10-09": {"games": []},
}

_BOXSCORE_BY_ID = {
    "111": {
        "gameType": 2, "startTimeUTC": "2024-10-10T23:00:00Z", "gameState": "OFF",
        "playerByGameStats": {
            "awayTeam": {"goalies": [
                {"playerId": 1, "name": {"default": "A"}, "starter": True,
                 "toi": "60:00", "shotsAgainst": 30, "saves": 26, "goalsAgainst": 4},
                {"playerId": 2, "name": {"default": "B"}, "starter": False,
                 "toi": "00:00", "shotsAgainst": 0, "saves": 0, "goalsAgainst": 0},
            ]},
            "homeTeam": {"goalies": [
                {"playerId": 3, "name": {"default": "C"}, "starter": True,
                 "toi": "60:00", "shotsAgainst": 24, "saves": 20, "goalsAgainst": 4},
                {"playerId": 4, "name": {"default": "D"}, "starter": False,
                 "toi": "00:00", "shotsAgainst": 0, "saves": 0, "goalsAgainst": 0},
            ]},
        },
    },
}


@pytest.fixture(autouse=True)
def _mock_nhl_api(monkeypatch):
    calls = {"score": [], "boxscore": []}

    def fake_fetch_score(date_str, session):
        calls["score"].append(date_str)
        return _SCORE_BY_DATE.get(date_str, {"games": []})

    def fake_fetch_boxscore(game_id, session):
        calls["boxscore"].append(game_id)
        return _BOXSCORE_BY_ID[str(game_id)]

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score)
    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_boxscore", fake_fetch_boxscore)
    return calls


def test_run_empareja_y_guarda_apariciones(tmp_path, _mock_nhl_api):
    _seed_results(tmp_path)
    counts = goalie_backfill.run(date(2024, 10, 10), date(2024, 10, 10),
                                  sleep_s=0.0, root=tmp_path)
    assert counts.days == 1
    assert counts.games_total == 1
    assert counts.games_matched == 1
    assert counts.appearance_rows_seen == 4
    assert counts.appearance_rows_added == 4
    assert counts.starters_seen == 2
    assert counts.unmatched == []

    df = GoalieAppearanceStore(tmp_path).load()
    assert len(df) == 4
    assert set(df["espn_game_id"]) == {"ESPN-1"}
    assert set(df["matched"].astype(str)) <= {"True", "1"}


def test_run_reanuda_desde_checkpoint_sin_repetir_peticiones(tmp_path, _mock_nhl_api):
    _seed_results(tmp_path)
    start = end = date(2024, 10, 10)
    goalie_backfill.run(start, end, sleep_s=0.0, root=tmp_path)
    n_score_calls = len(_mock_nhl_api["score"])
    n_box_calls = len(_mock_nhl_api["boxscore"])
    assert n_score_calls > 0 and n_box_calls > 0

    # Segunda pasada, mismo rango: el checkpoint ya cubre el unico dia pedido,
    # asi que NO debe volver a pedir nada.
    counts2 = goalie_backfill.run(start, end, sleep_s=0.0, root=tmp_path)
    assert counts2.days == 0
    assert counts2.games_total == 0
    assert len(_mock_nhl_api["score"]) == n_score_calls
    assert len(_mock_nhl_api["boxscore"]) == n_box_calls

    # El store no gano filas duplicadas.
    assert len(GoalieAppearanceStore(tmp_path).load()) == 4


def test_run_rango_distinto_ignora_el_checkpoint_anterior(tmp_path, _mock_nhl_api):
    _seed_results(tmp_path)
    goalie_backfill.run(date(2024, 10, 10), date(2024, 10, 10), sleep_s=0.0, root=tmp_path)
    # Un rango que EMPIEZA distinto no reanuda desde el checkpoint anterior:
    # se vuelve a pedir el mismo dia (idempotente por el dedup del store).
    counts = goalie_backfill.run(date(2024, 10, 10), date(2024, 10, 11), sleep_s=0.0, root=tmp_path)
    assert counts.days == 2
    assert len(GoalieAppearanceStore(tmp_path).load()) == 4  # 2024-10-11 no tiene partidos


def test_run_para_tras_fallos_consecutivos(tmp_path, monkeypatch):
    _seed_results(tmp_path)

    def siempre_falla(date_str, session):
        raise requests.ConnectionError("caida simulada")

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", siempre_falla)
    counts = goalie_backfill.run(date(2024, 10, 10), date(2024, 10, 20),
                                  sleep_s=0.0, root=tmp_path)
    # Se detiene tras 3 fallos seguidos de /v1/score, sin completar el rango.
    assert counts.days == 0
    assert counts.games_total == 0
    assert counts.stopped_by_failures is True


def _make_score_map_b1():
    ids = {"2024-10-10": 310, "2024-10-11": 311, "2024-10-12": 312, "2024-10-13": 313}
    out: dict = {}
    for d, gid in ids.items():
        out[d] = {"games": [{
            "id": gid, "gameType": 2, "startTimeUTC": f"{d}T23:00:00Z",
            "homeTeam": {"name": {"default": "Bruins"}},
            "awayTeam": {"name": {"default": "Canadiens"}},
        }]}
    return out, ids


def _make_boxscore_b1(start):
    return {
        "gameType": 2, "startTimeUTC": start, "gameState": "OFF",
        "playerByGameStats": {
            "awayTeam": {"goalies": [
                {"playerId": 1, "name": {"default": "A"}, "starter": True,
                 "toi": "60:00", "shotsAgainst": 30, "saves": 26, "goalsAgainst": 4},
                {"playerId": 2, "name": {"default": "B"}, "starter": False,
                 "toi": "00:00", "shotsAgainst": 0, "saves": 0, "goalsAgainst": 0},
            ]},
            "homeTeam": {"goalies": [
                {"playerId": 3, "name": {"default": "C"}, "starter": True,
                 "toi": "60:00", "shotsAgainst": 24, "saves": 20, "goalsAgainst": 4},
                {"playerId": 4, "name": {"default": "D"}, "starter": False,
                 "toi": "00:00", "shotsAgainst": 0, "saves": 0, "goalsAgainst": 0},
            ]},
        },
    }


def test_run_no_avanza_checkpoint_mas_alla_del_primer_dia_incompleto(tmp_path, monkeypatch):
    """B1 (revision independiente de Fable, NO APTO): rango 10..13 UTC, con un
    fallo del /v1/score del 11 y del boxscore del 12. Un dia POSTERIOR
    correcto (13) no debe hacer avanzar el checkpoint por delante del hueco:
    al reanudar sin fallos, el store debe terminar con los 4 dias completos,
    no solo el 10 y el 13."""
    score_map, ids = _make_score_map_b1()
    score_11_calls = {"n": 0}

    def fake_fetch_score_con_fallo(date_str, session):
        if date_str == "2024-10-11":
            score_11_calls["n"] += 1
            if score_11_calls["n"] == 1:
                raise requests.ConnectionError("caida simulada del score del 11")
        return score_map.get(date_str, {"games": []})

    def fake_fetch_boxscore_con_fallo(game_id, session):
        if str(game_id) == "312":
            raise requests.ConnectionError("caida simulada del boxscore del 12")
        for d, gid in ids.items():
            if gid == int(game_id):
                return _make_boxscore_b1(f"{d}T23:00:00Z")
        raise AssertionError(f"game_id inesperado: {game_id}")

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score_con_fallo)
    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_boxscore", fake_fetch_boxscore_con_fallo)

    counts1 = goalie_backfill.run(date(2024, 10, 10), date(2024, 10, 13),
                                   sleep_s=0.0, root=tmp_path)
    # Solo 2 fallos, no consecutivos hasta el limite: el backfill no se para.
    assert counts1.stopped_by_failures is False
    # Con el bug, el checkpoint quedaria en el 13 (por delante del hueco del
    # 11/12) y una reanudacion posterior ya no volveria a pedirlos.
    tras_primer_run = GoalieAppearanceStore(tmp_path).load()
    assert "2024-10-11" not in set(tras_primer_run["date"])
    assert "2024-10-12" not in set(tras_primer_run["date"])

    # Reanudar SIN fallos.
    def fake_fetch_score_ok(date_str, session):
        return score_map.get(date_str, {"games": []})

    def fake_fetch_boxscore_ok(game_id, session):
        for d, gid in ids.items():
            if gid == int(game_id):
                return _make_boxscore_b1(f"{d}T23:00:00Z")
        raise AssertionError(f"game_id inesperado: {game_id}")

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score_ok)
    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_boxscore", fake_fetch_boxscore_ok)
    goalie_backfill.run(date(2024, 10, 10), date(2024, 10, 13), sleep_s=0.0, root=tmp_path)

    df = GoalieAppearanceStore(tmp_path).load()
    assert set(df["date"]) == {"2024-10-10", "2024-10-11", "2024-10-12", "2024-10-13"}
    assert len(df) == 16  # 4 dias x 4 filas de aparicion (titular+suplente x 2 lados)


def test_run_no_ingiere_partido_no_finalizado_ni_congela_stats_parciales(tmp_path, monkeypatch):
    """B2 (revision independiente de Fable, NO APTO): un boxscore con
    `gameState` distinto de OFF/FINAL se trata como pendiente -- sin filas, sin
    JSON crudo, sin avanzar el checkpoint -- para que, una vez FINAL, no quede
    congelado con la primera fila PARCIAL que `GoalieAppearanceStore.save`
    veria (dedup `keep=\"first\"`)."""
    score = {
        "2024-10-15": {"games": [{
            "id": 415, "gameType": 2, "startTimeUTC": "2024-10-15T23:00:00Z",
            "homeTeam": {"name": {"default": "Bruins"}},
            "awayTeam": {"name": {"default": "Canadiens"}},
        }]},
        "2024-10-14": {"games": []},
    }
    box_live = {
        "gameType": 2, "startTimeUTC": "2024-10-15T23:00:00Z", "gameState": "LIVE",
        "playerByGameStats": {
            "awayTeam": {"goalies": [
                {"playerId": 1, "name": {"default": "A"}, "starter": True,
                 "toi": "20:00", "shotsAgainst": 10, "saves": 9, "goalsAgainst": 1},
            ]},
            "homeTeam": {"goalies": []},
        },
    }
    box_final = {
        "gameType": 2, "startTimeUTC": "2024-10-15T23:00:00Z", "gameState": "OFF",
        "playerByGameStats": {
            "awayTeam": {"goalies": [
                {"playerId": 1, "name": {"default": "A"}, "starter": True,
                 "toi": "60:00", "shotsAgainst": 30, "saves": 27, "goalsAgainst": 3},
            ]},
            "homeTeam": {"goalies": [
                {"playerId": 3, "name": {"default": "C"}, "starter": True,
                 "toi": "60:00", "shotsAgainst": 24, "saves": 20, "goalsAgainst": 4},
            ]},
        },
    }
    calls = {"n": 0}

    def fake_fetch_score(date_str, session):
        return score.get(date_str, {"games": []})

    def fake_fetch_boxscore(game_id, session):
        calls["n"] += 1
        return box_live if calls["n"] == 1 else box_final

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score)
    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_boxscore", fake_fetch_boxscore)

    counts1 = goalie_backfill.run(date(2024, 10, 15), date(2024, 10, 15),
                                   sleep_s=0.0, root=tmp_path)
    assert counts1.pending_games  # el partido LIVE queda marcado como pendiente
    assert GoalieAppearanceStore(tmp_path).load().empty
    assert not (tmp_path / "data" / "historical" / "nhl_goalies_raw").exists()

    counts2 = goalie_backfill.run(date(2024, 10, 15), date(2024, 10, 15),
                                   sleep_s=0.0, root=tmp_path)
    assert counts2.pending_games == []
    df = GoalieAppearanceStore(tmp_path).load()
    assert len(df) == 2  # titular visitante + titular local, ya FINAL
    fila_visitante = df[df["goalie_player_id"] == "1"].iloc[0]
    assert int(fila_visitante["saves"]) == 27  # las stats FINALES, no las 9 parciales
