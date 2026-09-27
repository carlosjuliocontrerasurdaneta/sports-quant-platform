"""`sqp.pipeline.goalie_backfill.run`: matching, deduplication and resumable
checkpointing, with the NHL API fully mocked (no network, no `data/`)."""
import json
from datetime import date

import pytest
import requests

from sqp.pipeline import goalie_backfill
from sqp.storage.goalies import GoalieAppearanceStore
from sqp.storage.results_store import ResultsStore


class _FakeHttpResponse:
    """Respuesta minima para construir un `requests.HTTPError(response=...)`
    sin una peticion real -- solo el atributo que `_classify_exception` mira."""

    def __init__(self, status_code: int):
        self.status_code = status_code


def _make_score_map(days_ids: dict[str, int]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d, gid in days_ids.items():
        out[d] = {"games": [{
            "id": gid, "gameType": 2, "startTimeUTC": f"{d}T23:00:00Z",
            "homeTeam": {"name": {"default": "Bruins"}},
            "awayTeam": {"name": {"default": "Canadiens"}},
        }]}
    return out


def _make_boxscore(start_iso: str) -> dict:
    return {
        "gameType": 2, "startTimeUTC": start_iso, "gameState": "OFF",
        "playerByGameStats": {
            "awayTeam": {"goalies": [
                {"playerId": 1, "name": {"default": "A"}, "starter": True,
                 "toi": "60:00", "shotsAgainst": 30, "saves": 26, "goalsAgainst": 4},
            ]},
            "homeTeam": {"goalies": [
                {"playerId": 3, "name": {"default": "C"}, "starter": True,
                 "toi": "60:00", "shotsAgainst": 24, "saves": 20, "goalsAgainst": 4},
            ]},
        },
    }


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


# --- Alternativa a B1 (revision independiente de Fable, 2026-09-27): registrar
# fechas fallidas en el checkpoint en vez de congelar `last_date_done` en la
# primera. Caso real: `/v1/score/2009-09-15` y `/2009-09-20` devuelven HTTP 500
# de forma estable mientras dias vecinos responden 200. ---

def test_500_persistente_de_una_fecha_no_bloquea_y_queda_en_failed(tmp_path, monkeypatch):
    ids = {"2024-11-01": 501, "2024-11-02": 502, "2024-11-03": 503}
    score_map = _make_score_map(ids)

    def fake_fetch_score(date_str, session):
        if date_str == "2024-11-02":
            raise requests.HTTPError(response=_FakeHttpResponse(500))
        return score_map.get(date_str, {"games": []})

    def fake_fetch_boxscore(game_id, session):
        for d, gid in ids.items():
            if gid == int(game_id):
                return _make_boxscore(f"{d}T23:00:00Z")
        raise AssertionError(f"game_id inesperado: {game_id}")

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score)
    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_boxscore", fake_fetch_boxscore)

    counts = goalie_backfill.run(date(2024, 11, 1), date(2024, 11, 3), sleep_s=0.0, root=tmp_path)

    # Un 500 de UNA fecha no cuenta como fallo general: el backfill no se para.
    assert counts.stopped_by_failures is False
    # 2024-11-02 (fallo propio) Y 2024-11-03 (revision independiente de Fable,
    # escenario S1, 2026-09-27: su peticion de desbordamiento pide DE NUEVO
    # /v1/score/2024-11-02, que tambien falla -- no se puede descartar que
    # 2024-11-03 tuviera un partido de desbordamiento listado ahi, asi que
    # tambien queda marcado para reintentar, aunque sus propios partidos ya
    # se hayan capturado).
    by_date = {f["date"]: f for f in counts.failed_dates}
    assert set(by_date) == {"2024-11-02", "2024-11-03"}
    assert by_date["2024-11-02"]["kind"] == "score_http"
    assert by_date["2024-11-02"]["http_status"] == 500
    assert by_date["2024-11-03"]["kind"] == "score_prev_http"
    assert by_date["2024-11-03"]["http_status"] == 500

    # El checkpoint SI avanzo hasta el ultimo dia, pasando por las fechas
    # fallidas -- porque quedaron registradas en 'failed'.
    last_date_done, failed_map = goalie_backfill._load_checkpoint(
        tmp_path, date(2024, 11, 1), date(2024, 11, 3))
    assert last_date_done == date(2024, 11, 3)
    assert "2024-11-02" in failed_map
    assert failed_map["2024-11-02"]["kind"] == "score_http"

    df = GoalieAppearanceStore(tmp_path).load()
    assert set(df["date"]) == {"2024-11-01", "2024-11-03"}


def test_reintento_de_fecha_failed_que_ahora_responde_200_sale_de_la_lista(tmp_path, monkeypatch):
    ids = {"2024-11-01": 601, "2024-11-02": 602}
    score_map = _make_score_map(ids)
    state = {"fail_11_02": True}

    def fake_fetch_score(date_str, session):
        if date_str == "2024-11-02" and state["fail_11_02"]:
            raise requests.HTTPError(response=_FakeHttpResponse(500))
        return score_map.get(date_str, {"games": []})

    def fake_fetch_boxscore(game_id, session):
        for d, gid in ids.items():
            if gid == int(game_id):
                return _make_boxscore(f"{d}T23:00:00Z")
        raise AssertionError(f"game_id inesperado: {game_id}")

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score)
    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_boxscore", fake_fetch_boxscore)

    counts1 = goalie_backfill.run(date(2024, 11, 1), date(2024, 11, 2), sleep_s=0.0, root=tmp_path)
    assert len(counts1.failed_dates) == 1
    assert counts1.failed_dates[0]["date"] == "2024-11-02"
    assert set(GoalieAppearanceStore(tmp_path).load()["date"]) == {"2024-11-01"}

    # La fecha ahora responde bien: al reanudar, se reintenta PRIMERO y sale
    # de 'failed'.
    state["fail_11_02"] = False
    counts2 = goalie_backfill.run(date(2024, 11, 1), date(2024, 11, 2), sleep_s=0.0, root=tmp_path)
    assert counts2.failed_dates == []

    df = GoalieAppearanceStore(tmp_path).load()
    assert set(df["date"]) == {"2024-11-01", "2024-11-02"}

    last_date_done, failed_map = goalie_backfill._load_checkpoint(
        tmp_path, date(2024, 11, 1), date(2024, 11, 2))
    assert failed_map == {}


def test_n_fallos_generales_consecutivos_paran_sin_avanzar(tmp_path, monkeypatch):
    """Timeouts (fallo GENERAL) SI paran el backfill entero, a diferencia de
    un 500 de una fecha concreta -- y no se registran en 'failed' (no son un
    problema de esa fecha, sino de la conexion)."""
    def siempre_timeout(date_str, session):
        raise requests.Timeout("tiempo agotado simulado")

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", siempre_timeout)
    counts = goalie_backfill.run(date(2024, 11, 1), date(2024, 11, 10), sleep_s=0.0,
                                  root=tmp_path, max_consecutive_failures=2)

    assert counts.stopped_by_failures is True
    assert counts.days == 0
    assert counts.failed_dates == []

    last_date_done, failed_map = goalie_backfill._load_checkpoint(
        tmp_path, date(2024, 11, 1), date(2024, 11, 10))
    assert last_date_done is None
    assert failed_map == {}


def test_migracion_checkpoint_formato_antiguo_sin_clave_failed(tmp_path, monkeypatch):
    """El checkpoint anterior al 2026-09-27 no tiene la clave 'failed'; debe
    poder reanudarse sin volver a empezar, y quedar migrado al guardar."""
    ckpt_dir = tmp_path / "data" / "historical"
    ckpt_dir.mkdir(parents=True)
    old_checkpoint = {
        "start": "2024-11-01", "end": "2024-11-03",
        "last_date_done": "2024-11-01",
        "updated_at": "2024-11-01T00:00:00+00:00",
    }
    (ckpt_dir / goalie_backfill.CHECKPOINT_NAME).write_text(
        json.dumps(old_checkpoint), encoding="utf-8")

    ids = {"2024-11-02": 701, "2024-11-03": 702}
    score_map = _make_score_map(ids)

    def fake_fetch_score(date_str, session):
        return score_map.get(date_str, {"games": []})

    def fake_fetch_boxscore(game_id, session):
        for d, gid in ids.items():
            if gid == int(game_id):
                return _make_boxscore(f"{d}T23:00:00Z")
        raise AssertionError(f"game_id inesperado: {game_id}")

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score)
    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_boxscore", fake_fetch_boxscore)

    counts = goalie_backfill.run(date(2024, 11, 1), date(2024, 11, 3), sleep_s=0.0, root=tmp_path)
    # Reanuda tras el checkpoint antiguo (11-01 ya cubierto): solo procesa 2 dias.
    assert counts.days == 2

    last_date_done, failed_map = goalie_backfill._load_checkpoint(
        tmp_path, date(2024, 11, 1), date(2024, 11, 3))
    assert last_date_done == date(2024, 11, 3)
    assert failed_map == {}

    raw = json.loads((ckpt_dir / goalie_backfill.CHECKPOINT_NAME).read_text(encoding="utf-8"))
    assert "failed" in raw  # el fichero migro al formato nuevo al guardar de nuevo


# --- Hallazgo de Fable (NO APTO), escenario S1, 2026-09-27: un partido
# nocturno de la costa oeste con `startTimeUTC` en el dia D solo aparece en
# `/v1/score/<D-1>` (desbordamiento horario, `games_yesterday`). Si esa
# peticion de D-1 falla mientras se procesa D, el `except` original solo
# registraba D-1 en `failed`; cuando D-1 se recuperaba y salia de `failed` por
# su cuenta, D ya habia quedado por detras del checkpoint, y su partido de
# desbordamiento se perdia en silencio -- ni en el store, ni en `failed`. La
# correccion registra TAMBIEN D (tipo `score_prev_*`) para que reintentarlo
# vuelva a pedir D-1 y recoja el desbordamiento. ---

def test_s1_partido_de_desbordamiento_no_se_pierde_tras_fallo_transitorio_del_dia_anterior(
        tmp_path, monkeypatch):
    """Reproduce exactamente el escenario S1 de Fable: `/v1/score/2024-11-10`
    falla (HTTP 500) las primeras dos veces que se pide -- una vez como 'hoy'
    al procesar el propio 2024-11-10, otra vez como desbordamiento al procesar
    2024-11-11 -- y al tercer intento (durante el reintento de la segunda
    ejecucion) responde bien con el partido 900, listado con
    `startTimeUTC=2024-11-11T01:00:00Z` (fecha UTC 2024-11-11)."""
    calls = {"2024-11-10": 0}

    def fake_fetch_score(date_str, session):
        if date_str == "2024-11-10":
            calls["2024-11-10"] += 1
            if calls["2024-11-10"] <= 2:
                raise requests.HTTPError(response=_FakeHttpResponse(500))
            return {"games": [{
                "id": 900, "gameType": 2, "startTimeUTC": "2024-11-11T01:00:00Z",
                "homeTeam": {"name": {"default": "Bruins"}},
                "awayTeam": {"name": {"default": "Canadiens"}},
            }]}
        return {"games": []}

    def fake_fetch_boxscore(game_id, session):
        assert str(game_id) == "900"
        return _make_boxscore("2024-11-11T01:00:00Z")

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score)
    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_boxscore", fake_fetch_boxscore)

    goalie_backfill.run(date(2024, 11, 10), date(2024, 11, 12), sleep_s=0.0, root=tmp_path)
    goalie_backfill.run(date(2024, 11, 10), date(2024, 11, 12), sleep_s=0.0, root=tmp_path)

    df = GoalieAppearanceStore(tmp_path).load()
    game_en_store = (not df.empty) and "900" in set(df["nhl_game_id"].astype(str))
    _, failed_map = goalie_backfill._load_checkpoint(
        tmp_path, date(2024, 11, 10), date(2024, 11, 12))
    dia_sigue_en_failed = "2024-11-11" in failed_map

    # Nunca las dos cosas a la vez ausentes: o se recogio el partido, o el dia
    # sigue marcado para reintentar -- pero jamas se pierde en silencio.
    assert game_en_store or dia_sigue_en_failed

    # Con la peticion de 2024-11-10 ya sana al reintentar, el resultado
    # concreto de estas dos ejecuciones es que el partido SI se recoge y el
    # dia SALE de 'failed' (no solo la disyuncion minima de arriba).
    assert game_en_store is True
    assert dia_sigue_en_failed is False
    assert set(df["date"]) == {"2024-11-11"}


def test_s1_dia_sigue_en_failed_si_el_dia_anterior_sigue_fallando(tmp_path, monkeypatch):
    """Caso (b): si `/v1/score/<D-1>` sigue fallando de forma persistente
    (nunca se recupera), D debe permanecer en `failed` -- nunca se pierde el
    hueco silenciosamente ni se inventa un exito."""
    def fake_fetch_score(date_str, session):
        if date_str == "2024-11-10":
            raise requests.HTTPError(response=_FakeHttpResponse(500))
        return {"games": []}

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score)

    goalie_backfill.run(date(2024, 11, 10), date(2024, 11, 12), sleep_s=0.0, root=tmp_path)
    _, failed_map_1 = goalie_backfill._load_checkpoint(
        tmp_path, date(2024, 11, 10), date(2024, 11, 12))
    assert "2024-11-11" in failed_map_1
    assert failed_map_1["2024-11-11"]["kind"] == "score_prev_http"

    # Segunda ejecucion: 2024-11-10 sigue fallando -> 2024-11-11 sigue en 'failed'.
    goalie_backfill.run(date(2024, 11, 10), date(2024, 11, 12), sleep_s=0.0, root=tmp_path)
    _, failed_map_2 = goalie_backfill._load_checkpoint(
        tmp_path, date(2024, 11, 10), date(2024, 11, 12))
    assert "2024-11-11" in failed_map_2
    assert GoalieAppearanceStore(tmp_path).load().empty


def test_s1_no_duplica_registro_espurio_del_dia_anterior_ya_marcado(tmp_path, monkeypatch):
    """Caso (d): 2024-11-10 falla en su propia iteracion (queda en 'failed',
    1 intento) y vuelve a fallar como desbordamiento al procesar 2024-11-11
    (2 intentos reales sobre esa misma peticion en esta ejecucion) -- pero eso
    actualiza la MISMA entrada de 2024-11-10 (nunca crea una segunda), y
    2024-11-11 se registra aparte, con su propio tipo `score_prev_http`."""
    def fake_fetch_score(date_str, session):
        if date_str == "2024-11-10":
            raise requests.HTTPError(response=_FakeHttpResponse(500))
        return {"games": []}

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score)

    goalie_backfill.run(date(2024, 11, 10), date(2024, 11, 11), sleep_s=0.0, root=tmp_path)

    _, failed_map = goalie_backfill._load_checkpoint(
        tmp_path, date(2024, 11, 10), date(2024, 11, 11))
    # Exactamente dos fechas registradas -- ninguna entrada duplicada.
    assert set(failed_map) == {"2024-11-10", "2024-11-11"}
    assert failed_map["2024-11-10"]["kind"] == "score_http"
    assert failed_map["2024-11-10"]["attempts"] == 2  # su propia peticion + la del desbordamiento
    assert failed_map["2024-11-11"]["kind"] == "score_prev_http"
    assert failed_map["2024-11-11"]["attempts"] == 1


def test_s1_timeout_en_desbordamiento_es_fallo_general_no_se_registra_en_failed(
        tmp_path, monkeypatch):
    """Caso (c): la clasificacion general/especifica se aplica IGUAL a la
    peticion de desbordamiento que a la del dia propio. Un timeout (fallo
    GENERAL) al pedir el dia anterior detiene TODO el backfill y NO se
    registra en 'failed' -- a diferencia de un HTTP 500 (fallo especifico de
    esa fecha), que si se registra y deja seguir."""
    ckpt_dir = tmp_path / "data" / "historical"
    ckpt_dir.mkdir(parents=True)
    (ckpt_dir / goalie_backfill.CHECKPOINT_NAME).write_text(json.dumps({
        "start": "2024-11-01", "end": "2024-11-05",
        "last_date_done": "2024-11-03", "failed": [],
        "updated_at": "2024-11-03T00:00:00+00:00",
    }), encoding="utf-8")

    def fake_fetch_score(date_str, session):
        if date_str == "2024-11-03":
            raise requests.Timeout("tiempo agotado simulado")
        return {"games": []}

    monkeypatch.setattr(goalie_backfill.nhl_api, "fetch_score", fake_fetch_score)

    counts = goalie_backfill.run(date(2024, 11, 1), date(2024, 11, 5), sleep_s=0.0,
                                  root=tmp_path, max_consecutive_failures=1)

    assert counts.stopped_by_failures is True
    last_date_done, failed_map = goalie_backfill._load_checkpoint(
        tmp_path, date(2024, 11, 1), date(2024, 11, 5))
    assert last_date_done == date(2024, 11, 3)  # no avanzo mas alla del ultimo dia sano
    assert failed_map == {}  # un fallo GENERAL no se registra en 'failed'
