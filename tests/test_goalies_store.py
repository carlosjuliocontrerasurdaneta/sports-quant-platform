"""GoalieAppearanceStore (backfill) and log_goalie_probable_capture
(prospective capture): dedup, resumability and raw-JSON preservation.
Always against `tmp_path`, never `data/`.
"""
import gzip
import json

import pandas as pd

from sqp.storage.goalies import (
    GoalieAppearanceStore,
    log_goalie_probable_capture,
    raw_boxscore_path,
    save_raw_boxscore,
)


def _appearance_row(nhl_game_id="G1", team_side="home", goalie_player_id="1"):
    return {
        "nhl_game_id": nhl_game_id, "espn_game_id": "E1", "date": "2024-10-10",
        "game_type": 2, "start_time_utc": "2024-10-10T23:00:00Z",
        "team_side": team_side, "team_nhl": "Bruins", "team_espn": "Boston Bruins",
        "matched": True, "goalie_player_id": goalie_player_id, "goalie_name": "J. Swayman",
        "starter": True, "shots_against": 24, "saves": 20, "goals_against": 4,
        "toi": "60:00",
    }


def test_save_es_append_only_y_deduplica_por_partido_lado_y_portero(tmp_path):
    store = GoalieAppearanceStore(tmp_path)
    added1 = store.save([_appearance_row()])
    assert added1 == 1
    # Reingerir la MISMA fila (simula un backfill reanudado o re-ejecutado):
    # no debe duplicarse.
    added2 = store.save([_appearance_row()])
    assert added2 == 0
    df = store.load()
    assert len(df) == 1

    # Una fila NUEVA (otro portero, mismo partido y lado) SI se anade.
    added3 = store.save([_appearance_row(goalie_player_id="2")])
    assert added3 == 1
    assert len(store.load()) == 2


def test_save_existente_gana_no_se_sobrescribe(tmp_path):
    """A diferencia de StartersStore (anuncios mutables), un boxscore ya
    guardado NUNCA se sobrescribe: es dato pasado e inmutable."""
    store = GoalieAppearanceStore(tmp_path)
    store.save([_appearance_row()])
    fila_distinta = _appearance_row()
    fila_distinta["saves"] = 999  # si esto ganara, seria mutacion oculta
    store.save([fila_distinta])
    df = store.load()
    assert len(df) == 1
    assert int(df.iloc[0]["saves"]) == 20


def test_save_vacio_no_escribe_nada(tmp_path):
    store = GoalieAppearanceStore(tmp_path)
    assert store.save([]) == 0
    assert not store.path().exists()


def test_save_raw_boxscore_preserva_json_bruto_gzip(tmp_path):
    payload = {"id": 123, "starter": True}
    out = save_raw_boxscore(tmp_path, "G1", payload)
    assert out == raw_boxscore_path(tmp_path, "G1")
    with gzip.open(out, "rt", encoding="utf-8") as fh:
        assert json.loads(fh.read()) == payload


def _probable_row(event_id="E1", team_side="home", goalie_espn_id="1", status="Confirmed"):
    return {
        "event_id": event_id, "commence_time": "2026-09-26T19:00:00+00:00",
        "team_side": team_side, "team": "Buffalo Sabres",
        "goalie_espn_id": goalie_espn_id, "goalie_name": "U. Luukkonen",
        "status": status, "status_type": status.lower(),
    }


def test_log_goalie_probable_capture_solo_anade_al_cambiar(tmp_path):
    n1 = log_goalie_probable_capture(tmp_path, [_probable_row()], source_run="capture")
    assert n1 == 1
    # Misma identidad y estado: no se repite en cada pasada de 30 min.
    n2 = log_goalie_probable_capture(tmp_path, [_probable_row()], source_run="capture")
    assert n2 == 0
    # Cambio de estado (Confirmed -> otra cosa): SI se anade.
    n3 = log_goalie_probable_capture(
        tmp_path, [_probable_row(status="Expected")], source_run="capture")
    assert n3 == 1
    # Cambio de portero: SI se anade.
    n4 = log_goalie_probable_capture(
        tmp_path, [_probable_row(goalie_espn_id="2")], source_run="capture")
    assert n4 == 1

    df = pd.read_csv(tmp_path / "data" / "historical" / "goalie_probables_nhl.csv")
    assert len(df) == 3
    assert set(df["source_run"]) == {"capture"}


def test_log_goalie_probable_capture_ignora_filas_sin_portero(tmp_path):
    fila = _probable_row()
    fila["goalie_espn_id"] = ""
    assert log_goalie_probable_capture(tmp_path, [fila], source_run="capture") == 0
    assert not (tmp_path / "data" / "historical" / "goalie_probables_nhl.csv").exists()


def test_log_goalie_probable_capture_daily_siempre_anade_aunque_no_cambie(tmp_path):
    """C1 (revision independiente de Fable, NO APTO): `source_run=\"daily\"`
    es el ancla diaria que el run diario necesita presente para cada evento
    que cubre, no un log de cambios -- debe anadirse SIEMPRE, aunque sea
    identica a la ultima captura."""
    log_goalie_probable_capture(tmp_path, [_probable_row()], source_run="capture")
    n_daily_1 = log_goalie_probable_capture(tmp_path, [_probable_row()], source_run="daily")
    assert n_daily_1 == 1
    n_daily_2 = log_goalie_probable_capture(tmp_path, [_probable_row()], source_run="daily")
    assert n_daily_2 == 1  # identica a la anterior, pero SIEMPRE se anade

    df = pd.read_csv(tmp_path / "data" / "historical" / "goalie_probables_nhl.csv")
    assert len(df) == 3
    assert list(df["source_run"])[-2:] == ["daily", "daily"]


def test_log_goalie_probable_capture_registra_retiro_cuando_deja_de_publicarse(tmp_path):
    """C1 (revision independiente de Fable, NO APTO): si un probable que
    existia deja de publicarse mientras el evento sigue activo, se registra
    una fila explicita de retiro (portero vacio, status \"none\") en vez de
    descartarse en silencio -- de lo contrario la ultima fila del CSV sigue
    diciendo que ese portero es el probable, indefinidamente."""
    log_goalie_probable_capture(tmp_path, [_probable_row()], source_run="capture")
    active = [{"event_id": "E1", "team_side": "home", "team": "Buffalo Sabres",
               "commence_time": "2026-09-26T19:00:00+00:00"}]

    n = log_goalie_probable_capture(tmp_path, [], source_run="capture", active_pairs=active)
    assert n == 1
    df = pd.read_csv(
        tmp_path / "data" / "historical" / "goalie_probables_nhl.csv",
        dtype=str, keep_default_na=False,
    )
    assert len(df) == 2
    retiro = df.iloc[-1]
    assert retiro["status"] == "none"
    assert retiro["goalie_espn_id"] == ""

    # Retirar dos veces seguidas (el evento sigue sin probable) no duplica la
    # fila de retiro: ya esta reflejado como retirado.
    n2 = log_goalie_probable_capture(tmp_path, [], source_run="capture", active_pairs=active)
    assert n2 == 0


def test_log_goalie_probable_capture_no_retira_un_par_que_nunca_tuvo_probable(tmp_path):
    active = [{"event_id": "E-SIN-PROBABLE", "team_side": "away", "team": "X",
               "commence_time": "2026-09-26T19:00:00+00:00"}]
    n = log_goalie_probable_capture(tmp_path, [], source_run="capture", active_pairs=active)
    assert n == 0
    assert not (tmp_path / "data" / "historical" / "goalie_probables_nhl.csv").exists()


def test_log_goalie_probable_capture_status_nulo_no_repite_cada_pase(tmp_path):
    """Menor (revision independiente de Fable): un `status` None no debe
    compararse como distinto de si mismo tras el redondeo por CSV (None vs
    NaN), o la fila se repetiria en cada pase aunque nada haya cambiado."""
    fila = _probable_row()
    fila["status"] = None
    fila["status_type"] = None
    n1 = log_goalie_probable_capture(tmp_path, [fila], source_run="capture")
    assert n1 == 1
    n2 = log_goalie_probable_capture(tmp_path, [dict(fila)], source_run="capture")
    assert n2 == 0
