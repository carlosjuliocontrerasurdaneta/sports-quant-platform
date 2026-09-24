"""Liquidacion de candidatos de equipo fuera de la ventana del feed (ronda
audit-2026-09-23).

- AUD-003 (OPENAI-003 + CLAUDE-002 b) y KI-058: el fallback contra
  data/historical/ exige IDENTIDAD EXACTA (`exact_history_scores_map`): mismo
  par ordenado, la fecha que el vendor guarda para ESE partido (UTC en ESPN;
  America/New_York en MLB Stats API), resultado unico y partido empezado. La
  tolerancia de +-1 dia liquidaba el pick de hoy de una serie MLB con el
  marcador de ayer (FABLE-001) y un juego aplazado con el del anterior (KI-058).
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


def test_mapa_exacto_nocturno_mlb_usa_la_fecha_del_este():
    """Partido de 01:10Z: su resultado esta en la fecha ET del dia anterior;
    la fecha UTC NO debe emparejar (discrimina ET frente a UTC)."""
    pendiente = pd.DataFrame([_fila("n1", "2026-09-02T01:10:00Z")])
    base = {"home": "Home Team", "away": "Away Team"}
    ahora = datetime(2026, 9, 10, tzinfo=timezone.utc)
    assert runner.exact_history_scores_map(
        pendiente, [{**base, "date": "2026-09-01", "home_score": 6, "away_score": 2}],
        "mlb", now=ahora) == {"n1": (6, 2, "Home Team")}
    assert runner.exact_history_scores_map(
        pendiente, [{**base, "date": "2026-09-02", "home_score": 6, "away_score": 2}],
        "mlb", now=ahora) == {}


def test_mapa_exacto_no_gradua_si_nuestros_registros_ven_un_doubleheader():
    """FABLE-R2-001 en el stream servido: dos eventos del par el mismo dia en
    lo que listo The Odds API -> un unico resultado no identifica cual."""
    g1, g2 = "2026-09-10T17:05:00Z", "2026-09-10T23:10:00Z"   # mismo dia ET
    ahora = datetime(2026, 9, 15, tzinfo=timezone.utc)
    pendiente = pd.DataFrame([_fila("G2", g2)])
    conocidos = pd.DataFrame([_fila("G1", g1), _fila("G2", g2)])
    resultados = [{"date": "2026-09-10", "home": "Home Team",
                   "away": "Away Team", "home_score": 7, "away_score": 1}]
    assert runner.exact_history_scores_map(pendiente, resultados, "mlb", now=ahora,
                                           known_events=conocidos) == {}
    # Contraprueba: sin el otro evento, el unico resultado si identifica.
    assert runner.exact_history_scores_map(pendiente, resultados, "mlb",
                                           now=ahora) == {"G2": (7, 1, "Home Team")}


def test_mapa_exacto_no_gradua_mlb_fuera_de_america():
    """FABLE-R2-002: serie en Tokio, juego 2 de dia (03:05Z): la fecha ET no
    es la oficial y apuntaria al juego 1. No se gradua."""
    j2 = "2026-03-19T03:05:00Z"
    pendiente = pd.DataFrame([_fila("J2", j2)])
    resultados = [{"date": "2026-03-18", "home": "Home Team", "away": "Away Team",
                   "home_score": 4, "away_score": 2},
                  {"date": "2026-03-19", "home": "Home Team", "away": "Away Team",
                   "home_score": 1, "away_score": 0}]
    ahora = datetime(2026, 3, 25, tzinfo=timezone.utc)
    assert runner.exact_history_scores_map(pendiente, resultados, "mlb",
                                           now=ahora) == {}


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
