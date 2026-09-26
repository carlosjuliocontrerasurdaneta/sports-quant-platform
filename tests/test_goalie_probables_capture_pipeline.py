"""`sqp.pipeline.goalie_probables_capture.run`: only not-yet-started events are
captured, and the capture NEVER writes anywhere except its own store. Fully
mocked ESPN scoreboard (no network, no `data/`).
"""
import os
from datetime import datetime, timedelta, timezone


from sqp.pipeline import goalie_probables_capture as capture
from sqp.providers.date_window import utc_today


def _payload_for(date_str, event_id, commence_time, completed, goalie_id="1"):
    return {
        "events": [{
            "id": event_id,
            "date": commence_time,
            "status": {"type": {"completed": completed}},
            "competitions": [{
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": "Buffalo Sabres"},
                     "probables": [{"name": "probableStartingGoalie",
                                    "athlete": {"id": goalie_id, "fullName": "Portero"},
                                    "status": {"name": "Confirmed", "type": "confirmed"}}]},
                    {"homeAway": "away", "team": {"displayName": "Vancouver Canucks"},
                     "probables": [{"name": "probableStartingGoalie",
                                    "athlete": {"id": "2", "fullName": "Otro"},
                                    "status": {"name": "Expected", "type": "expected"}}]},
                ]
            }],
        }]
    }


def _todos_los_ficheros(root):
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            out.append(os.path.relpath(os.path.join(dirpath, f), root))
    return out


def test_captura_solo_eventos_no_comenzados_y_no_escribe_fuera_de_su_store(tmp_path, monkeypatch):
    now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
    today = utc_today()
    tomorrow_str = f"{today + timedelta(days=1):%Y%m%d}"
    today_str = f"{today:%Y%m%d}"

    future_ok = _payload_for(today_str, "E-FUTURO",
                              (now + timedelta(hours=8)).isoformat().replace("+00:00", "Z"),
                              completed=False)
    ya_empezado = _payload_for(today_str, "E-EMPEZADO",
                                (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                                completed=False)
    ya_jugado = _payload_for(today_str, "E-JUGADO",
                              (now - timedelta(hours=5)).isoformat().replace("+00:00", "Z"),
                              completed=True)

    def fake_fetch_scoreboard(date_str, session):
        if date_str == today_str:
            return {"events": (future_ok["events"] + ya_empezado["events"]
                               + ya_jugado["events"])}
        if date_str == tomorrow_str:
            return {"events": []}
        raise AssertionError(f"fecha inesperada: {date_str}")

    monkeypatch.setattr(capture, "fetch_scoreboard", fake_fetch_scoreboard)

    seen, appended = capture.run("capture", root=tmp_path, now=now)

    # Solo el evento futuro y no comenzado cuenta (2 lados: home + away).
    assert seen == 2
    assert appended == 2

    ficheros = _todos_los_ficheros(tmp_path)
    assert ficheros == [os.path.join("data", "historical", "goalie_probables_nhl.csv")]

    import pandas as pd
    df = pd.read_csv(tmp_path / "data" / "historical" / "goalie_probables_nhl.csv")
    assert set(df["event_id"]) == {"E-FUTURO"}
    assert set(df["source_run"]) == {"capture"}


def test_captura_sin_eventos_no_escribe_nada(tmp_path, monkeypatch):
    monkeypatch.setattr(capture, "fetch_scoreboard", lambda date_str, session: {"events": []})
    seen, appended = capture.run("capture", root=tmp_path)
    assert (seen, appended) == (0, 0)
    assert not (tmp_path / "data").exists()


def test_captura_marca_source_run_daily(tmp_path, monkeypatch):
    now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
    today_str = f"{utc_today():%Y%m%d}"
    payload = _payload_for(today_str, "E-DAILY",
                            (now + timedelta(hours=8)).isoformat().replace("+00:00", "Z"),
                            completed=False)

    def fake_fetch_scoreboard(date_str, session):
        return payload if date_str == today_str else {"events": []}

    monkeypatch.setattr(capture, "fetch_scoreboard", fake_fetch_scoreboard)
    capture.run("daily", root=tmp_path, now=now)

    import pandas as pd
    df = pd.read_csv(tmp_path / "data" / "historical" / "goalie_probables_nhl.csv")
    assert set(df["source_run"]) == {"daily"}


def test_captura_descarta_commence_time_no_parseable(tmp_path, monkeypatch):
    """Menor (revision independiente de Fable): un `commence_time` que no se
    puede parsear se DESCARTA, no se conserva -- adivinar que sigue por venir
    podria loguear un probable de un partido ya en curso o terminado."""
    now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
    today_str = f"{utc_today():%Y%m%d}"
    payload = _payload_for(today_str, "E-MALFORMADO", "fecha-no-iso", completed=False)

    def fake_fetch_scoreboard(date_str, session):
        return payload if date_str == today_str else {"events": []}

    monkeypatch.setattr(capture, "fetch_scoreboard", fake_fetch_scoreboard)
    seen, appended = capture.run("capture", root=tmp_path, now=now)
    assert (seen, appended) == (0, 0)
    assert not (tmp_path / "data").exists()


def test_captura_registra_retiro_cuando_el_evento_sigue_activo_sin_probable(tmp_path, monkeypatch):
    """C1 end-to-end: un evento capturado con probable en una pasada, y sin
    ninguno en la siguiente (mientras sigue sin comenzar), debe registrar una
    fila de retiro en vez de desaparecer sin dejar rastro."""
    now1 = datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)
    now2 = datetime(2026, 9, 26, 10, 30, tzinfo=timezone.utc)
    today_str = f"{utc_today():%Y%m%d}"
    con_probable = _payload_for(today_str, "E-RETIRO", "2026-09-26T20:00:00Z", completed=False)

    def _sin_probable_para(event_id, commence_time):
        return {
            "events": [{
                "id": event_id,
                "date": commence_time,
                "status": {"type": {"completed": False}},
                "competitions": [{
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": "Buffalo Sabres"},
                         "probables": []},
                        {"homeAway": "away", "team": {"displayName": "Vancouver Canucks"},
                         "probables": []},
                    ]
                }],
            }]
        }

    def fake_fetch_scoreboard_1(date_str, session):
        return con_probable if date_str == today_str else {"events": []}

    monkeypatch.setattr(capture, "fetch_scoreboard", fake_fetch_scoreboard_1)
    capture.run("capture", root=tmp_path, now=now1)

    def fake_fetch_scoreboard_2(date_str, session):
        return (_sin_probable_para("E-RETIRO", "2026-09-26T20:00:00Z")
                if date_str == today_str else {"events": []})

    monkeypatch.setattr(capture, "fetch_scoreboard", fake_fetch_scoreboard_2)
    seen2, appended2 = capture.run("capture", root=tmp_path, now=now2)
    assert seen2 == 0  # ya no hay ningun probable publicado
    assert appended2 == 2  # pero SI se registra el retiro de home y away

    import pandas as pd
    df = pd.read_csv(tmp_path / "data" / "historical" / "goalie_probables_nhl.csv",
                      dtype=str, keep_default_na=False)
    retiros = df[df["event_id"] == "E-RETIRO"]
    assert set(retiros["status"]) == {"Confirmed", "Expected", "none"}
    ultimas = (retiros.sort_values("captured_at_utc")
               .drop_duplicates(subset=["team_side"], keep="last"))
    assert set(ultimas["status"]) == {"none"}
    assert set(ultimas["goalie_espn_id"]) == {""}
