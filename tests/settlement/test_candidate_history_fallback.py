"""Liquidacion de candidatos de equipo fuera de la ventana del feed (ronda
audit-2026-09-23).

- AUD-003 (OPENAI-003 + CLAUDE-002 b) y KI-058: el fallback contra
  data/historical/ exige IDENTIDAD EXACTA (`exact_history_scores_map`): mismo
  par ordenado, la fecha que el vendor guarda para ESE partido (UTC en ESPN;
  America/New_York en MLB Stats API), resultado unico y partido empezado. La
  tolerancia de +-1 dia liquidaba el pick de hoy de una serie MLB con el
  marcador de ayer (FABLE-001) y un juego aplazado con el del anterior (KI-058).
- KI-059: MLB no se identifica por fecha sino por CALENDARIO
  (`mlb_schedule_scores_map`): el partido del par mas cercano en hora en el
  calendario de MLB Stats API (aplazados incluidos), misma fecha ET, estado no
  aplazado y marcador del mismo gamePk.
- AUD-004 (CLAUDE-002 a): un pick desplazado (`superseded`) no tenia
  `start_time` -- se buscaba solo en el `predictions` vigente --, asi que nunca
  expiraba y a los 14 dias salia del escaneo sin veredicto.
- AUD-012 (CLAUDE-004): un segundo run el mismo dia pisaba la copia de archivo
  del primero al archivarse al dia siguiente.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from sqp.config import Settings
from sqp.pipeline.daily import _archive_existing
from sqp.settlement import runner
from sqp.settlement.runner import (SUPERSEDED_FLAG, fetch_and_settle,
                                   superseded_candidates)
from sqp.storage.results_store import ResultsStore

LEAGUE = "mlb"
NOW = datetime.now(timezone.utc)
GAME = NOW - timedelta(days=5)          # fuera de la ventana del feed (3 dias)
GEN = GAME - timedelta(days=1)          # el pick se publico el dia anterior
ISO = "%Y-%m-%dT%H:%M:%SZ"


def _cand(event_id, *, selection="Home Team", stake=100.0, lg=LEAGUE):
    return {"event_id": event_id, "league": lg, "market": "h2h",
            "selection": selection, "line": float("nan"), "price_decimal": 2.0,
            "stake": stake, "data_label": "real", "flags": "",
            "home": "Home Team", "away": "Away Team",
            "generated_at": GEN.strftime("%Y-%m-%dT%H:%M:%S+00:00")}


def _pred(event_id, start=GAME):
    return {"event_id": event_id, "home": "Home Team", "away": "Away Team",
            "start_time": start.strftime(ISO)}


def _write(root, *, current_cands, current_preds, archived_cands=(),
           archived_preds=(), lg=LEAGUE):
    pred_dir = root / "data" / "predictions"
    (pred_dir / "archive").mkdir(parents=True)
    pd.DataFrame(list(current_cands), columns=list(_cand("x"))).to_csv(
        pred_dir / f"candidates_{lg}.csv", index=False)
    pd.DataFrame(list(current_preds), columns=list(_pred("x"))).to_csv(
        pred_dir / f"predictions_{lg}.csv", index=False)
    day = GEN.strftime("%Y-%m-%d")
    if archived_cands:
        pd.DataFrame(list(archived_cands)).to_csv(
            pred_dir / "archive" / f"candidates_{lg}_{day}.csv", index=False)
    if archived_preds:
        pd.DataFrame(list(archived_preds)).to_csv(
            pred_dir / "archive" / f"predictions_{lg}_{day}.csv", index=False)
    return pred_dir


class _HealthyFeed:
    """Feed sano (scores_trusted) que NO lista el partido del pick: solo otro,
    reciente. Es el caso normal pasados 3 dias."""

    def fetch_scores(self, sport_key, days_from=2):   # noqa: ARG002
        return [{"id": "otro", "completed": True, "home_team": "X",
                 "away_team": "Y", "commence_time": NOW.strftime(ISO),
                 "scores": [{"name": "X", "score": "1"},
                            {"name": "Y", "score": "0"}]}]


def _history(root, *results):
    ResultsStore(root).upsert(LEAGUE, [
        {"date": GAME.strftime("%Y-%m-%d"), "home": "Home Team",
         "away": "Away Team", "game_id": gid, "home_score": hs,
         "away_score": as_, "neutral": False,
         "ingested_at": NOW.strftime(ISO)} for gid, hs, as_ in results])


def _settle(root, lg=LEAGUE):
    return fetch_and_settle(lg, Settings(), days_from=2, client=_HealthyFeed())


# --- AUD-003 / FABLE-001 / KI-058 / FABLE-R2: identidad exacta --------------

ESPN = "wnba"   # liga con historico ESPN: fecha UTC, sin doubleheaders


def _resultado(root, dia, hs, as_, gid, lg=LEAGUE):
    ResultsStore(root).upsert(lg, [
        {"date": dia, "home": "Home Team", "away": "Away Team", "game_id": gid,
         "home_score": hs, "away_score": as_, "neutral": False,
         "ingested_at": NOW.strftime(ISO)}])


def _dia_mlb(ts):
    return ts.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _dia_utc(ts):
    return ts.strftime("%Y-%m-%d")


def test_candidato_espn_fuera_de_ventana_se_gradua_con_su_resultado_exacto(
        tmp_path, monkeypatch):
    """AUD-003: el resultado de ESE partido esta en el historico; ya no se
    anula (void irreversible) sino que se gradua."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[_cand("e1", lg=ESPN)],
           current_preds=[_pred("e1")], lg=ESPN)
    _resultado(tmp_path, _dia_utc(GAME), 70, 80, "g1", lg=ESPN)
    settled = _settle(tmp_path, ESPN)
    assert settled.iloc[0]["result"] == "loss"
    assert float(settled.iloc[0]["pnl"]) == -100.0
    assert "stale_void" not in str(settled.iloc[0]["flags"])
    assert _settle(tmp_path, ESPN).empty                # idempotente


def test_candidato_espn_con_resultado_en_otro_dia_expira(tmp_path, monkeypatch):
    """Aplazado: sin resultado en SU fecha, el del dia anterior no lo gradua."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[_cand("e1", lg=ESPN)],
           current_preds=[_pred("e1")], lg=ESPN)
    _resultado(tmp_path, _dia_utc(GAME - timedelta(days=1)), 9, 1, "g0", lg=ESPN)
    settled = _settle(tmp_path, ESPN)
    assert settled.iloc[0]["result"] == "void"
    assert "stale_void" in str(settled.iloc[0]["flags"])


def test_candidato_espn_futuro_no_se_gradua_aunque_haya_resultado_ese_dia(
        tmp_path, monkeypatch):
    """Guarda de inicio (FABLE-R2-003): sin ella, este caso SI graduaria."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    luego = NOW + timedelta(hours=3)
    _write(tmp_path, current_cands=[_cand("e1", lg=ESPN)],
           current_preds=[_pred("e1", start=luego)], lg=ESPN)
    _resultado(tmp_path, _dia_utc(luego), 70, 80, "g1", lg=ESPN)
    assert _settle(tmp_path, ESPN).empty


def test_un_pick_sin_jugar_no_se_liquida_con_el_partido_anterior_de_la_serie(
        tmp_path, monkeypatch):
    """FABLE-001 (CRITICAL, reproducido): serie MLB, el juego 1 (ayer) ya esta
    en el historico y el pick es del juego 2 (hoy, sin jugar)."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    hoy = NOW + timedelta(hours=10)
    _write(tmp_path, current_cands=[_cand("g2")],
           current_preds=[_pred("g2", start=hoy)])
    _resultado(tmp_path, _dia_mlb(hoy - timedelta(days=1)), 2, 5, "g1")
    assert _settle(tmp_path).empty


def test_doubleheader_mlb_con_un_juego_aplazado_no_toma_el_marcador_del_otro(
        tmp_path, monkeypatch):
    """FABLE-R2-001 (HIGH, reproducido): el historico de MLB solo guarda el
    juego jugado; el pick del aplazado NO puede liquidarse con su marcador.
    Los candidatos de MLB no se graduan desde el historico hasta tener
    identidad de calendario (KI-059): expiran como antes."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[_cand("G2", selection="Away Team")],
           current_preds=[_pred("G2")])
    _resultado(tmp_path, _dia_mlb(GAME), 7, 1, "g1")
    settled = _settle(tmp_path)
    assert settled.iloc[0]["result"] == "void"
    assert float(settled.iloc[0]["pnl"]) == 0.0


def test_sin_resultado_historico_se_mantiene_la_expiracion(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[_cand("e1")], current_preds=[_pred("e1")])
    settled = _settle(tmp_path)
    assert settled.iloc[0]["result"] == "void"
    assert float(settled.iloc[0]["pnl"]) == 0.0


def test_la_fecha_esperada_sigue_la_convencion_de_cada_vendor():
    """MLB Stats API: fecha oficial (local, = America/New_York). ESPN: UTC."""
    noche = "2026-09-02T01:10:00Z"          # 21:10 ET del 1 de septiembre
    assert runner.expected_result_date("mlb", noche) == "2026-09-01"
    assert runner.expected_result_date("wnba", noche) == "2026-09-02"
    tarde = "2026-09-01T17:05:00Z"
    assert runner.expected_result_date("mlb", tarde) == "2026-09-01"
    assert runner.expected_result_date("mlb", "no-es-fecha") is None


def _fila(eid, start):
    return {"event_id": eid, "home": "Home Team", "away": "Away Team",
            "start_time": start}


def test_mapa_exacto_serie_aplazado_back_to_back_y_contraprueba():
    """KI-058: el juego aplazado de una serie no toma el marcador de la
    vispera. FABLE-R3-003: con resultado del par tambien en un dia adyacente,
    la fecha no identifica el partido -> no gradua. Contraprueba: solo con su
    propio resultado, si gradua."""
    pendiente = pd.DataFrame([_fila("gN", GAME.strftime(ISO))])
    vispera = {"date": _dia_utc(GAME - timedelta(days=1)), "home": "Home Team",
               "away": "Away Team", "home_score": 2, "away_score": 5}
    propio = {"date": _dia_utc(GAME), "home": "Home Team",
              "away": "Away Team", "home_score": 3, "away_score": 1}
    assert runner.exact_history_scores_map(pendiente, [vispera], ESPN) == {}
    assert runner.exact_history_scores_map(pendiente, [vispera, propio], ESPN) == {}
    assert runner.exact_history_scores_map(pendiente, [propio], ESPN) == {
        "gN": (3, 1, "Home Team")}


def test_mapa_exacto_no_gradua_si_nuestros_registros_ven_un_doubleheader():
    """FABLE-R2-001 en el stream servido: dos eventos del par el mismo dia en
    lo que listo The Odds API -> un unico resultado no identifica cual."""
    g1, g2 = "2026-09-10T17:05:00Z", "2026-09-10T23:10:00Z"   # mismo dia UTC
    ahora = datetime(2026, 9, 15, tzinfo=timezone.utc)
    pendiente = pd.DataFrame([_fila("G2", g2)])
    conocidos = pd.DataFrame([_fila("G1", g1), _fila("G2", g2)])
    resultados = [{"date": "2026-09-10", "home": "Home Team",
                   "away": "Away Team", "home_score": 7, "away_score": 1}]
    assert runner.exact_history_scores_map(pendiente, resultados, ESPN, now=ahora,
                                           known_events=conocidos) == {}
    # Contraprueba: sin el otro evento, el unico resultado si identifica.
    assert runner.exact_history_scores_map(pendiente, resultados, ESPN,
                                           now=ahora) == {"G2": (7, 1, "Home Team")}


def _servida(lg):
    return {"league": lg, "event_id": "gN", "home": "Home Team",
            "away": "Away Team", "start_time": GAME.strftime(ISO),
            "game_date": GAME.strftime("%Y-%m-%d"), "market": "h2h",
            "selection": "Home Team", "line": "", "price_decimal": 2.0,
            "bookmaker": "test", "model_probability": 0.5,
            "estimated_probability": 0.5, "calibrated_probability": 0.5,
            "implied_probability_novig": 0.5, "estimated_edge": 0.0,
            "books_count": 3, "stake": 0.0, "data_label": "real",
            "flags": "served_stream",
            "generated_at": GEN.strftime("%Y-%m-%dT%H:%M:%S+00:00")}


def test_stream_servido_espn_usa_la_identidad_exacta(tmp_path, monkeypatch):
    """Integracion de `_grade_served_from_history`: sin resultado en SU fecha,
    la fila servida queda pendiente (luego expira), no graduada con el
    marcador de otro dia (KI-058); con su propio resultado si se gradua."""
    from sqp.storage.served_store import ServedStore
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    ServedStore(tmp_path).append_served(ESPN, [_servida(ESPN)])
    _resultado(tmp_path, _dia_utc(GAME + timedelta(days=2)), 2, 5, "otro", lg=ESPN)
    assert runner._grade_served_from_history(ESPN) == 0
    _resultado(tmp_path, _dia_utc(GAME), 3, 1, "gN", lg=ESPN)
    assert runner._grade_served_from_history(ESPN) == 1


def test_stream_servido_mlb_no_se_gradua_desde_el_historico(tmp_path, monkeypatch):
    """FABLE-R3-001: sirviendo solo el juego que luego se aplaza, el unico
    resultado del dia es el del OTRO juego del doubleheader. MLB queda fuera
    del fallback historico hasta KI-059, tambien en el stream servido."""
    from sqp.storage.served_store import ServedStore
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    ServedStore(tmp_path).append_served(LEAGUE, [_servida(LEAGUE)])
    _resultado(tmp_path, _dia_mlb(GAME), 7, 1, "g1")
    assert runner._grade_served_from_history(LEAGUE) == 0


def test_el_mapa_por_fecha_no_acepta_mlb():
    """MLB no se identifica por fecha (series, doubleheader con aplazado,
    Asia): el mapa por fecha devuelve {} y MLB usa el calendario (KI-059)."""
    pendiente = pd.DataFrame([_fila("n1", "2026-09-02T01:10:00Z")])
    resultados = [{"date": "2026-09-01", "home": "Home Team", "away": "Away Team",
                   "home_score": 6, "away_score": 2}]
    ahora = datetime(2026, 9, 10, tzinfo=timezone.utc)
    assert runner.exact_history_scores_map(pendiente, resultados, "mlb",
                                           now=ahora) == {}


def test_stream_servido_espn_no_gradua_con_el_resultado_de_la_vispera(
        tmp_path, monkeypatch):
    """REG-001 (verificacion 2): con el resultado a -1 dia, el +-1 anterior lo
    graduaba; la identidad exacta no. Este test falla si se vuelve al +-1."""
    from sqp.storage.served_store import ServedStore
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    ServedStore(tmp_path).append_served(ESPN, [_servida(ESPN)])
    _resultado(tmp_path, _dia_utc(GAME - timedelta(days=1)), 2, 5, "otro", lg=ESPN)
    assert runner._grade_served_from_history(ESPN) == 0


# --- KI-059: MLB por identidad de CALENDARIO -----------------------------------

AHORA = datetime(2026, 9, 20, tzinfo=timezone.utc)


def _cal(gid, start, state="Final", home="Home Team", away="Away Team",
         abstract="Final", tbd=False, date=None):
    # Como la API real: un aplazado tambien trae abstractGameState "Final".
    return {"game_id": gid, "date": date or start[:10], "start_time": start,
            "home": home, "away": away, "state": state, "abstract_state": abstract,
            "start_time_tbd": tbd, "double_header": "N", "game_number": 1}


def _res(gid, hs, as_, date="2026-09-10"):
    return {"game_id": gid, "date": date, "home": "Home Team", "away": "Away Team",
            "home_score": hs, "away_score": as_}


def _mapa(picks, calendario, resultados):
    return runner.mlb_schedule_scores_map(
        pd.DataFrame([_fila(e, st) for e, st in picks]), pd.DataFrame(calendario),
        resultados, now=AHORA)


def test_calendario_gradua_con_el_marcador_de_su_propio_partido():
    cal = [_cal("100", "2026-09-10T23:05:00Z")]
    assert _mapa([("e1", "2026-09-10T23:05:00Z")], cal, [_res("100", 5, 2)]) == {
        "e1": (5, 2, "Home Team")}


def test_calendario_serie_cada_pick_con_su_juego():
    """Serie en dias consecutivos: la fecha no bastaba; la hora si."""
    cal = [_cal("1", "2026-09-09T23:05:00Z"), _cal("2", "2026-09-10T23:05:00Z"),
           _cal("3", "2026-09-11T17:10:00Z")]
    res = [_res("1", 1, 0), _res("2", 2, 7), _res("3", 4, 4)]
    m = _mapa([("a", "2026-09-09T23:05:00Z"), ("b", "2026-09-10T23:06:00Z")], cal, res)
    assert m == {"a": (1, 0, "Home Team"), "b": (2, 7, "Home Team")}


def test_calendario_doubleheader_con_un_juego_aplazado_no_gradua_el_aplazado():
    """FABLE-R2-001: el juego 2 se aplaza; el unico resultado del dia es el del
    juego 1. El pick del juego 2 empareja con SU entrada (aplazada) y no
    gradua; el del juego 1 si."""
    cal = [_cal("G1", "2026-09-10T17:05:00Z"),
           _cal("G2", "2026-09-10T23:10:00Z", state="Postponed")]
    res = [_res("G1", 7, 1)]
    m = _mapa([("p1", "2026-09-10T17:05:00Z"), ("p2", "2026-09-10T23:10:00Z")], cal, res)
    assert m == {"p1": (7, 1, "Home Team")}


def test_calendario_doubleheader_jugado_cada_uno_con_su_marcador():
    cal = [_cal("G1", "2026-09-10T17:05:00Z"), _cal("G2", "2026-09-10T22:40:00Z")]
    res = [_res("G1", 7, 1), _res("G2", 0, 3)]
    m = _mapa([("p1", "2026-09-10T17:05:00Z"), ("p2", "2026-09-10T22:40:00Z")], cal, res)
    assert m == {"p1": (7, 1, "Home Team"), "p2": (0, 3, "Home Team")}


def test_calendario_serie_en_asia_nunca_toma_el_marcador_del_otro_juego():
    """FABLE-R2-002: serie en Tokio, juego 1 a las 10:10Z del 18 y juego 2 de
    dia a las 03:05Z del 19: los DOS caen el 18 en hora ET. Con un solo evento
    conocido, dos apariciones del par ese dia no se identifican (REG-002) y no
    se gradua. Con los dos reclamados uno a uno, cada uno con el suyo."""
    cal = [_cal("J1", "2026-03-18T10:10:00Z"), _cal("J2", "2026-03-19T03:05:00Z")]
    res = [_res("J1", 4, 2, "2026-03-18"), _res("J2", 1, 0, "2026-03-19")]
    ahora = datetime(2026, 3, 25, tzinfo=timezone.utc)
    m = runner.mlb_schedule_scores_map(
        pd.DataFrame([_fila("j2", "2026-03-19T03:05:00Z")]), pd.DataFrame(cal), res,
        now=ahora)
    assert m == {}
    ambos = pd.DataFrame([_fila("j1", "2026-03-18T10:10:00Z"),
                          _fila("j2", "2026-03-19T03:05:00Z")])
    m = runner.mlb_schedule_scores_map(ambos, pd.DataFrame(cal), res, now=ahora,
                                       known_events=ambos)
    assert m == {"j1": (4, 2, "Home Team"), "j2": (1, 0, "Home Team")}


def test_calendario_partido_fuera_del_calendario_no_toma_el_de_otro_dia():
    """Un pick sin entrada en el calendario (postemporada, otro tipo): el mas
    cercano es de OTRO dia ET y no se empareja."""
    cal = [_cal("100", "2026-09-05T23:05:00Z")]
    assert _mapa([("post", "2026-09-10T23:05:00Z")], cal, [_res("100", 5, 2)]) == {}


def test_calendario_empate_futuro_y_sin_marcador_no_gradua():
    cal = [_cal("A", "2026-09-10T18:00:00Z"), _cal("B", "2026-09-10T22:00:00Z")]
    res = [_res("A", 1, 0), _res("B", 0, 1)]
    # Equidistante de los dos: no identifica.
    assert _mapa([("x", "2026-09-10T20:00:00Z")], cal, res) == {}
    # Futuro respecto a `now`.
    assert runner.mlb_schedule_scores_map(
        pd.DataFrame([_fila("f", "2026-09-10T18:00:00Z")]), pd.DataFrame(cal), res,
        now=datetime(2026, 9, 10, 12, tzinfo=timezone.utc)) == {}
    # Identificado pero sin marcador con ese game_id.
    assert _mapa([("y", "2026-09-10T18:00:00Z")], cal, [_res("B", 0, 1)]) == {}


def test_sin_calendario_mlb_sigue_la_expiracion(tmp_path, monkeypatch):
    """Hasta que el backfill cree el calendario, nada cambia para MLB."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[_cand("e1")], current_preds=[_pred("e1")])
    _resultado(tmp_path, _dia_mlb(GAME), 7, 1, "g1")
    settled = _settle(tmp_path)
    assert settled.iloc[0]["result"] == "void"


def _calendario(root, gid, start, state="Final"):
    from sqp.storage.schedule_store import ScheduleStore
    ScheduleStore(root).upsert(LEAGUE, [_cal(gid, start.strftime(ISO), state=state)])


def test_candidato_mlb_con_calendario_se_gradua_de_punta_a_punta(tmp_path, monkeypatch):
    """AUD-003 en MLB (KI-059): fuera de la ventana del feed, con su partido
    identificado en el calendario, se gradua en vez de anularse."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[_cand("e1")], current_preds=[_pred("e1")])
    _calendario(tmp_path, "g1", GAME)
    _resultado(tmp_path, _dia_mlb(GAME), 70, 80, "g1")
    settled = _settle(tmp_path)
    assert settled.iloc[0]["result"] == "loss"
    assert float(settled.iloc[0]["pnl"]) == -100.0
    assert _settle(tmp_path).empty                      # idempotente


def test_candidato_mlb_del_juego_aplazado_expira_de_punta_a_punta(tmp_path, monkeypatch):
    """FABLE-R2-001 de punta a punta: el aplazado no toma el marcador del otro
    juego del doubleheader."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[_cand("G2", selection="Away Team")],
           current_preds=[_pred("G2")])
    _calendario(tmp_path, "g1", GAME - timedelta(hours=6))
    _calendario(tmp_path, "g2", GAME, state="Postponed")
    _resultado(tmp_path, _dia_mlb(GAME), 7, 1, "g1")
    settled = _settle(tmp_path)
    assert settled.iloc[0]["result"] == "void"
    assert float(settled.iloc[0]["pnl"]) == 0.0


def test_stream_servido_mlb_con_calendario_se_gradua(tmp_path, monkeypatch):
    from sqp.storage.served_store import ServedStore
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    ServedStore(tmp_path).append_served(LEAGUE, [_servida(LEAGUE)])
    _calendario(tmp_path, "gN-1", GAME - timedelta(days=1))
    _resultado(tmp_path, _dia_mlb(GAME - timedelta(days=1)), 2, 5, "gN-1")
    assert runner._grade_served_from_history(LEAGUE) == 0   # solo la vispera
    _calendario(tmp_path, "gN", GAME)
    _resultado(tmp_path, _dia_mlb(GAME), 3, 1, "gN")
    assert runner._grade_served_from_history(LEAGUE) == 1


def test_schedule_store_una_fila_por_aparicion(tmp_path):
    """FABLE-K-001: el aplazado recuperado conserva su gamePk en DOS fechas;
    ambas apariciones se guardan. Dentro de una aparicion, gana la ultima."""
    from sqp.storage.schedule_store import ScheduleStore
    st = ScheduleStore(tmp_path)
    st.upsert(LEAGUE, [_cal("9", "2026-09-10T23:05:00Z", state="Scheduled",
                            abstract="Preview")])
    st.upsert(LEAGUE, [_cal("9", "2026-09-10T23:05:00Z", state="Postponed"),
                       _cal("9", "2026-09-11T17:05:00Z")])
    df = st.load(LEAGUE).sort_values("date")
    assert list(zip(df["date"], df["state"])) == [("2026-09-10", "Postponed"),
                                                  ("2026-09-11", "Final")]
    assert ScheduleStore(tmp_path / "vacio").load(LEAGUE).empty


def _por_store(tmp_path, apariciones):
    from sqp.storage.schedule_store import ScheduleStore
    ScheduleStore(tmp_path).upsert(LEAGUE, apariciones)
    return ScheduleStore(tmp_path).load(LEAGUE)


def test_aplazado_recuperado_no_toma_el_marcador_del_otro_juego(tmp_path):
    """FABLE-K-001 con la forma de BOS-BAL 2025-05-23: juego 1 final 17:35Z,
    juego 2 (777809) aplazado 23:10Z y recuperado al dia siguiente con el MISMO
    gamePk, pasando por el store. El pick del aplazado no gradua; el de la
    recuperacion, con el marcador de SU partido."""
    cal = _por_store(tmp_path, [
        _cal("777815", "2025-05-23T17:35:00Z"),
        _cal("777809", "2025-05-23T23:10:00Z", state="Postponed"),
        _cal("777809", "2025-05-24T17:35:00Z", date="2025-05-24")])
    res = [_res("777815", 19, 5, "2025-05-23"), _res("777809", 3, 4, "2025-05-24")]
    ahora = datetime(2025, 5, 30, tzinfo=timezone.utc)
    m = runner.mlb_schedule_scores_map(
        pd.DataFrame([_fila("ev_ppd", "2025-05-23T23:10:00Z"),
                      _fila("ev_rec", "2025-05-24T17:35:00Z")]), cal, res, now=ahora)
    assert m == {"ev_rec": (3, 4, "Home Team")}


def test_suspendido_y_reanudado_se_gradua_con_el_marcador_final(tmp_path):
    """FABLE-K-002: dos apariciones Final del mismo gamePk (suspension y
    reanudacion); el pick del dia original se gradua con el marcador final."""
    cal = _por_store(tmp_path, [
        _cal("824912", "2026-06-16T23:15:00Z"),
        _cal("824912", "2026-06-17T18:00:00Z", date="2026-06-17")])
    res = [_res("824912", 1, 1, "2026-06-16"), _res("824912", 2, 7, "2026-06-17")]
    ahora = datetime(2026, 6, 25, tzinfo=timezone.utc)
    m = runner.mlb_schedule_scores_map(
        pd.DataFrame([_fila("s1", "2026-06-16T23:15:00Z")]), cal, res, now=ahora)
    assert m == {"s1": (2, 7, "Home Team")}


def test_dos_eventos_hacia_la_misma_aparicion_no_gradua_ninguno():
    """FABLE-K-003: uno a uno o nada."""
    cal = pd.DataFrame([_cal("G1", "2026-09-10T17:05:00Z")])
    conocidos = pd.DataFrame([_fila("a", "2026-09-10T17:05:00Z"),
                              _fila("b", "2026-09-10T17:06:00Z")])
    m = runner.mlb_schedule_scores_map(
        pd.DataFrame([_fila("a", "2026-09-10T17:05:00Z")]), cal, [_res("G1", 7, 1)],
        now=AHORA, known_events=conocidos)
    assert m == {}


def test_doubleheader_con_hora_por_confirmar_no_gradua():
    """FABLE-K-003: juego 2 TBD (hora del 1 mas 5 min): la hora no identifica."""
    cal = pd.DataFrame([_cal("G1", "2026-09-10T17:05:00Z"),
                        _cal("G2", "2026-09-10T17:10:00Z", tbd=True)])
    res = [_res("G1", 7, 1), _res("G2", 0, 3)]
    assert _mapa([("p1", "2026-09-10T17:05:00Z")], cal.to_dict("records"), res) == {}


def test_dos_partidos_del_par_el_mismo_dia_con_inicio_desfasado_no_gradua():
    """REG-002 (verificacion 3, reproducido con CIN-ARI 2025-06-07): juegos a
    las 18:10Z y 20:10Z. El pick del juego 2 llega desfasado -61 min (19:09Z)
    y el mas cercano pasa a ser el juego 1. Con el otro partido del dia sin
    reclamar por ningun evento conocido, no se gradua."""
    cal = [_cal("777623", "2025-06-07T18:10:00Z"), _cal("777612", "2025-06-07T20:10:00Z")]
    res = [_res("777623", 4, 3, "2025-06-07"), _res("777612", 13, 1, "2025-06-07")]
    ahora = datetime(2025, 6, 15, tzinfo=timezone.utc)
    m = runner.mlb_schedule_scores_map(
        pd.DataFrame([_fila("g2", "2025-06-07T19:09:00Z")]), pd.DataFrame(cal), res,
        now=ahora)
    assert m == {}
    # Contraprueba: con los dos juegos reclamados uno a uno, cada pick se
    # gradua con el marcador de SU juego.
    conocidos = pd.DataFrame([_fila("g1", "2025-06-07T18:10:00Z"),
                              _fila("g2", "2025-06-07T20:10:00Z")])
    m = runner.mlb_schedule_scores_map(conocidos, pd.DataFrame(cal), res, now=ahora,
                                       known_events=conocidos)
    assert m == {"g1": (4, 3, "Home Team"), "g2": (13, 1, "Home Team")}


def test_doubleheader_con_aplazado_y_pick_desfasado_no_toma_el_juego_jugado():
    """N3 (verificacion de REG-002): el aplazado CUENTA en la guarda del dia.
    Juego 1 final a las 18:10Z, juego 2 aplazado a las 20:10Z; el pick del
    juego 2 llega desfasado -61 min y el mas cercano es el juego 1. Como la
    aparicion aplazada no la reclama nadie mas, el dia no se identifica."""
    cal = [_cal("G1", "2025-06-07T18:10:00Z"),
           _cal("G2", "2025-06-07T20:10:00Z", state="Postponed")]
    res = [_res("G1", 4, 3, "2025-06-07")]
    m = runner.mlb_schedule_scores_map(
        pd.DataFrame([_fila("p2", "2025-06-07T19:09:00Z")]), pd.DataFrame(cal), res,
        now=datetime(2025, 6, 15, tzinfo=timezone.utc))
    assert m == {}


def test_los_candidatos_mlb_usan_los_eventos_servidos_como_conocidos(
        tmp_path, monkeypatch):
    """M14 (verificacion 3): el cableado de produccion de la regla uno a uno.
    Si el stream servido tiene OTRO evento que reclama la misma aparicion, el
    candidato no se gradua; sin ese cableado, se graduaria."""
    from sqp.storage.served_store import ServedStore
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[_cand("e1")], current_preds=[_pred("e1")])
    _calendario(tmp_path, "g1", GAME)
    _resultado(tmp_path, _dia_mlb(GAME), 70, 80, "g1")
    otro = _servida(LEAGUE)
    otro["event_id"] = "e-duplicado"
    otro["start_time"] = (GAME + timedelta(minutes=1)).strftime(ISO)
    ServedStore(tmp_path).append_served(LEAGUE, [otro])
    settled = _settle(tmp_path)
    assert settled.iloc[0]["result"] == "void"


def test_calendario_desactualizado_no_gradua():
    """Aparicion aun 'Scheduled' (calendario viejo) con marcador del gamePk: no
    se gradua; solo una aparicion terminada identifica un resultado."""
    cal = [_cal("100", "2026-09-10T23:05:00Z", state="Scheduled", abstract="Preview")]
    assert _mapa([("e1", "2026-09-10T23:05:00Z")], cal, [_res("100", 5, 2)]) == {}


def test_backfill_mlb_no_escribe_resultados_si_falla_el_calendario(tmp_path, monkeypatch):
    """Calendario y resultados van juntos: sin calendario, ninguno se escribe."""
    import importlib.util
    import sys
    from pathlib import Path as _P
    raiz = _P(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("backfill_k", raiz / "scripts" / "backfill_results.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    class _Prov:
        def fetch_schedule(self, days_back):  # noqa: ARG002
            raise RuntimeError("calendario caido")

        def fetch_results(self, league, days_back):  # noqa: ARG002
            return [_res("1", 1, 0)]

    monkeypatch.setattr(mod, "MLBStatsProvider", _Prov)
    monkeypatch.setattr(sys, "argv", ["backfill_results.py", "--leagues", "mlb"])
    assert mod.main() == 1
    assert not ResultsStore(tmp_path).path("mlb").exists()


def test_fetch_schedule_incluye_aplazados_con_su_hora():
    from sqp.providers.mlb_statsapi import MLBStatsProvider

    class _R:
        status_code = 200

        def json(self):
            return {"dates": [{"date": "2026-09-10", "games": [
                {"gamePk": 1, "gameDate": "2026-09-10T17:05:00Z",
                 "status": {"detailedState": "Final"}, "doubleHeader": "S",
                 "gameNumber": 1,
                 "teams": {"home": {"team": {"name": "H"}}, "away": {"team": {"name": "A"}}}},
                {"gamePk": 2, "gameDate": "2026-09-10T23:10:00Z",
                 "status": {"detailedState": "Postponed"}, "doubleHeader": "S",
                 "gameNumber": 2,
                 "teams": {"home": {"team": {"name": "H"}}, "away": {"team": {"name": "A"}}}},
                {"gamePk": 3}]}]}

        def raise_for_status(self):
            return None

    class _S:
        def get(self, url, **kwargs):  # noqa: ARG002
            return _R()

    filas = MLBStatsProvider(_S()).fetch_schedule(days_back=3)
    assert [(f["game_id"], f["state"], f["start_time"]) for f in filas] == [
        ("1", "Final", "2026-09-10T17:05:00Z"), ("2", "Postponed", "2026-09-10T23:10:00Z")]
    assert filas[0]["start_time_tbd"] is False


# --- AUD-004 ------------------------------------------------------------------


def test_desplazado_sin_marcador_expira_como_uno_vigente(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    # e2 salio de la lista: solo esta en archive/, y el `predictions` vigente
    # ya no lo describe (el partido paso).
    _write(tmp_path, current_cands=[], current_preds=[],
           archived_cands=[_cand("e2")], archived_preds=[_pred("e2")])
    settled = _settle(tmp_path)
    assert settled["event_id"].tolist() == ["e2"]
    row = settled.iloc[0]
    assert row["result"] == "void"
    assert "stale_void" in str(row["flags"])
    assert SUPERSEDED_FLAG in str(row["flags"])
    assert _settle(tmp_path).empty


def test_desplazado_con_su_resultado_exacto_se_gradua(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write(tmp_path, current_cands=[], current_preds=[],
           archived_cands=[_cand("e2", lg=ESPN)], archived_preds=[_pred("e2")],
           lg=ESPN)
    _resultado(tmp_path, _dia_utc(GAME), 5, 2, "g1", lg=ESPN)
    settled = _settle(tmp_path, ESPN)
    row = settled.iloc[0]
    assert row["result"] == "win"
    assert float(row["pnl"]) == 100.0
    assert SUPERSEDED_FLAG in str(row["flags"])


# --- AUD-012 ------------------------------------------------------------------


def test_dos_generaciones_del_mismo_dia_sobreviven_en_el_archivo(tmp_path):
    pred_dir = tmp_path / "data" / "predictions"
    pred_dir.mkdir(parents=True)
    path = pred_dir / f"candidates_{LEAGUE}.csv"
    t1 = NOW - timedelta(days=1, hours=3)
    t2 = t1 + timedelta(hours=2)            # mismo dia UTC, otro run

    def generacion(eid, ts):
        row = _cand(eid)
        row["generated_at"] = ts.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        pd.DataFrame([row]).to_csv(path, index=False)

    generacion("f1", t1)
    _archive_existing(path)                 # antes del run 2
    generacion("f2", t2)
    _archive_existing(path)                 # antes del run del dia siguiente
    _archive_existing(path)                 # idempotente: misma generacion
    archivos = sorted((pred_dir / "archive").glob(f"candidates_{LEAGUE}_*.csv"))
    assert len(archivos) == 2, [a.name for a in archivos]
    ids = set(pd.concat(pd.read_csv(a) for a in archivos)["event_id"])
    assert ids == {"f1", "f2"}
    # Y la liquidacion de desplazados los ve a los dos.
    out = superseded_candidates(LEAGUE, pd.DataFrame(), pred_dir=pred_dir, now=NOW)
    assert set(out["event_id"]) == {"f1", "f2"}
