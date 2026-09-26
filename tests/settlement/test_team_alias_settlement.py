"""Regresion KI-067.

El fallback de liquidacion contra data/historical/ (`settlement.runner`,
`exact_history_scores_map` y `mlb_schedule_scores_map`) y el motor de ROI
(`backtesting.roi_engine`, `_pair_key`/`_match_index`/`_match_result`)
emparejaban equipos con `normalize_key` a secas, sin los alias de liga de
`configs/leagues/team_aliases.yaml`. Con un alias real -- p.ej. "Hawaii
Rainbow Warriors" en las cuotas (The Odds API) frente a "Hawai'i Rainbow
Warriors" en el historico (ESPN) --, si el feed /scores no gradua el partido
en su ventana de 3 dias, el fallback nunca encontraba el resultado y el pick
caducaba `stale_void` en vez de liquidarse con su resultado real.

Los alias se inyectan aqui via monkeypatch de
`sqp.sports.team_names._league_aliases`: los tests son deterministas frente a
cualquier contenido -- presente o futuro -- de `team_aliases.yaml` (que ademas
tiene alias reales sin commitear) y no leen `data/`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from sqp.backtesting.roi_engine import _match_index, _match_result
from sqp.config import Settings
from sqp.domain.models import Event, EventOdds, MarketLine
from sqp.settlement import runner
from sqp.sports import team_names
from sqp.sports.team_names import get_team_normalizer, normalize_key
from sqp.storage.results_store import ResultsStore
from sqp.storage.served_store import ServedStore

# "wnba" es una liga ESPN real (SPORT_KEYS) sin alias configurados hoy en
# team_aliases.yaml; se usa solo para satisfacer `_league_meta`, los alias en
# si se inyectan por monkeypatch y nunca se leen del fichero real.
LEAGUE = "wnba"
NOW = datetime.now(timezone.utc)
GAME = NOW - timedelta(days=5)      # fuera de la ventana del feed /scores (3 dias)
GEN = GAME - timedelta(days=1)
ISO = "%Y-%m-%dT%H:%M:%SZ"

VENDOR_HOME = "Hawaii Rainbow Warriors"     # grafia de The Odds API (cuotas / pick)
HISTORY_HOME = "Hawai'i Rainbow Warriors"   # grafia del historico (ESPN)
AWAY = "Away Team"


def _aliases_liga(league: str) -> dict[str, str]:
    if league != LEAGUE:
        return {}
    return {normalize_key(VENDOR_HOME): normalize_key(HISTORY_HOME)}


def _con_alias(monkeypatch):
    monkeypatch.setattr(team_names, "_league_aliases", _aliases_liga)


def _sin_alias(monkeypatch):
    monkeypatch.setattr(team_names, "_league_aliases", lambda league: {})


class _EmptyFeed:
    """Feed /scores SANO (trae al menos un resultado utilizable) que NO lista
    el partido del pick -- fuera de su ventana de 3 dias, el caso normal --
    para forzar la ruta de respaldo contra data/historical/. Un payload
    realmente vacio se trata como proveedor mudo (AUD-HIGH-002) y no dispara
    ni la anulacion ni el respaldo historico, así que no sirve para este
    escenario."""

    def fetch_scores(self, sport_key, days_from=2):   # noqa: ARG002
        return [{"id": "otro", "completed": True, "home_team": "X",
                 "away_team": "Y", "commence_time": NOW.strftime(ISO),
                 "scores": [{"name": "X", "score": "1"},
                            {"name": "Y", "score": "0"}]}]


def _cand(event_id, *, selection=VENDOR_HOME, stake=100.0):
    return {"event_id": event_id, "league": LEAGUE, "market": "h2h",
            "selection": selection, "line": float("nan"), "price_decimal": 2.0,
            "stake": stake, "data_label": "real", "flags": "",
            "home": VENDOR_HOME, "away": AWAY,
            "generated_at": GEN.strftime("%Y-%m-%dT%H:%M:%S+00:00")}


def _pred(event_id, start=GAME):
    return {"event_id": event_id, "home": VENDOR_HOME, "away": AWAY,
            "start_time": start.strftime(ISO)}


def _write(root, *, current_cands, current_preds):
    pred_dir = root / "data" / "predictions"
    (pred_dir / "archive").mkdir(parents=True)
    pd.DataFrame(list(current_cands), columns=list(_cand("x"))).to_csv(
        pred_dir / f"candidates_{LEAGUE}.csv", index=False)
    pd.DataFrame(list(current_preds), columns=list(_pred("x"))).to_csv(
        pred_dir / f"predictions_{LEAGUE}.csv", index=False)


def _resultado(root, dia, hs, as_, gid, home=HISTORY_HOME):
    ResultsStore(root).upsert(LEAGUE, [
        {"date": dia, "home": home, "away": AWAY, "game_id": gid,
         "home_score": hs, "away_score": as_, "neutral": False,
         "ingested_at": NOW.strftime(ISO)}])


def _dia_utc(ts):
    return ts.strftime("%Y-%m-%d")


def _settle(root):
    return runner.fetch_and_settle(LEAGUE, Settings(), days_from=2, client=_EmptyFeed())


def _fila(eid, home, start, away=AWAY):
    return {"event_id": eid, "home": home, "away": away, "start_time": start}


def _servida(eid="gN"):
    return {"league": LEAGUE, "event_id": eid, "home": VENDOR_HOME,
            "away": AWAY, "start_time": GAME.strftime(ISO),
            "game_date": GAME.strftime("%Y-%m-%d"), "market": "h2h",
            "selection": "Home Team", "line": "", "price_decimal": 2.0,
            "bookmaker": "test", "model_probability": 0.5,
            "estimated_probability": 0.5, "calibrated_probability": 0.5,
            "implied_probability_novig": 0.5, "estimated_edge": 0.0,
            "books_count": 3, "stake": 0.0, "data_label": "real",
            "flags": "served_stream",
            "generated_at": GEN.strftime("%Y-%m-%dT%H:%M:%S+00:00")}


# --- (a) candidato: se gradua con el alias de liga, no expira ----------------


def test_candidato_con_alias_de_liga_se_gradua_en_vez_de_expirar(tmp_path, monkeypatch):
    """Sin el alias, `exact_history_scores_map` compara "hawaii rainbow
    warriors" (pick) con "hawai i rainbow warriors" (historico) y nunca
    empareja: el candidato caduca `stale_void`. Con el normalizador de liga
    (KI-067), ambos lados resuelven a la misma clave canonica y se gradua."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _con_alias(monkeypatch)
    _write(tmp_path, current_cands=[_cand("e1")], current_preds=[_pred("e1")])
    _resultado(tmp_path, _dia_utc(GAME), 70, 80, "g1")
    settled = _settle(tmp_path)
    assert settled.iloc[0]["result"] == "loss"
    assert float(settled.iloc[0]["pnl"]) == -100.0
    assert "stale_void" not in str(settled.iloc[0]["flags"])
    assert _settle(tmp_path).empty                       # idempotente


def test_candidato_sin_alias_reproduce_el_bug_contraprueba(tmp_path, monkeypatch):
    """Contraprueba de (a): sin el alias, la desalineacion de grafia SI
    reproduce KI-067 -- el pick expira aunque el resultado real ya este en el
    historico."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _sin_alias(monkeypatch)
    _write(tmp_path, current_cands=[_cand("e1")], current_preds=[_pred("e1")])
    _resultado(tmp_path, _dia_utc(GAME), 70, 80, "g1")
    settled = _settle(tmp_path)
    assert settled.iloc[0]["result"] == "void"
    assert "stale_void" in str(settled.iloc[0]["flags"])


# --- (b) stream servido: misma graduacion con alias --------------------------


def test_stream_servido_con_alias_de_liga_se_gradua(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _con_alias(monkeypatch)
    ServedStore(tmp_path).append_served(LEAGUE, [_servida()])
    _resultado(tmp_path, _dia_utc(GAME), 3, 1, "gN")
    assert runner._grade_served_from_history(LEAGUE) == 1


def test_stream_servido_sin_alias_no_se_gradua_contraprueba(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _sin_alias(monkeypatch)
    ServedStore(tmp_path).append_served(LEAGUE, [_servida()])
    _resultado(tmp_path, _dia_utc(GAME), 3, 1, "gN")
    assert runner._grade_served_from_history(LEAGUE) == 0


# --- (c) la ambiguedad (doble jornada) sigue absteniendose con alias --------


def test_doble_jornada_con_grafias_del_alias_se_abstiene(monkeypatch):
    """Ambiguedad (AUD-20260906-04): dos eventos del mismo par el mismo dia,
    uno con la grafia de cuotas y otro con la del historico. Solo se detectan
    como EL MISMO PAR -- y por tanto ambiguos -- si la comprobacion de
    ambiguedad de `exact_history_scores_map` tambien usa el alias; con
    `normalize_key` a secas, `eventos` los contaria como parejas distintas y
    el candidato se graduaria (mal) sin abstenerse."""
    _con_alias(monkeypatch)
    g1, g2 = "2026-09-10T17:05:00Z", "2026-09-10T23:10:00Z"   # mismo dia UTC
    pendiente = pd.DataFrame([_fila("G2", VENDOR_HOME, g2)])
    conocidos = pd.DataFrame([_fila("G1", HISTORY_HOME, g1),
                              _fila("G2", VENDOR_HOME, g2)])
    resultados = [{"date": "2026-09-10", "home": HISTORY_HOME, "away": AWAY,
                   "home_score": 7, "away_score": 1}]
    ahora = datetime(2026, 9, 15, tzinfo=timezone.utc)
    assert runner.exact_history_scores_map(
        pendiente, resultados, LEAGUE, now=ahora, known_events=conocidos) == {}
    # Contraprueba: sin el otro evento del par, el unico resultado si identifica.
    assert runner.exact_history_scores_map(
        pendiente, resultados, LEAGUE, now=ahora) == {"G2": (7, 1, VENDOR_HOME)}


def test_roi_engine_doble_jornada_con_grafias_del_alias_se_abstiene(monkeypatch):
    """Misma abstencion por ambiguedad, pero en `roi_engine._match_result`:
    sin el normalizador de liga en `_pair_key`, los dos eventos de cuotas
    caerian en cubetas DISTINTAS del indice y la abstencion nunca se activaria
    (el resultado emparejaria, mal, con uno solo de los dos)."""
    _con_alias(monkeypatch)
    norm = get_team_normalizer(LEAGUE)

    def _eo(eid, home, start):
        return EventOdds(event=Event(event_id=eid, sport_key="bt", league=LEAGUE,
                                     home=home, away=AWAY, start_time=start,
                                     data_label="real"),
                         lines=[MarketLine("h2h", "dk", home, 1.9, None)])

    eo_manana = _eo("e_manana", VENDOR_HOME, "2026-09-10T17:05:00Z")
    eo_tarde = _eo("e_tarde", HISTORY_HOME, "2026-09-10T23:10:00Z")
    idx = _match_index({"a": eo_manana, "b": eo_tarde}, normalize=norm)
    r = {"home": HISTORY_HOME, "away": AWAY, "date": "2026-09-10"}  # solo el dia
    assert _match_result(r, idx, set(), normalize=norm) is None


# --- (d) roi_engine._match_result empareja a traves del alias ---------------


def test_roi_engine_match_result_empareja_por_alias(monkeypatch):
    _con_alias(monkeypatch)
    norm = get_team_normalizer(LEAGUE)
    eo = EventOdds(event=Event(event_id="e1", sport_key="bt", league=LEAGUE,
                               home=VENDOR_HOME, away=AWAY,
                               start_time=GAME.strftime(ISO), data_label="real"),
                   lines=[MarketLine("h2h", "dk", VENDOR_HOME, 1.9, None)])
    idx = _match_index({"e1": eo}, normalize=norm)
    r = {"home": HISTORY_HOME, "away": AWAY, "date": _dia_utc(GAME)}
    assert _match_result(r, idx, set(), normalize=norm) is eo


def test_roi_engine_match_result_sin_alias_no_empareja_contraprueba(monkeypatch):
    """Contraprueba de (d): con el normalizador por defecto (`normalize_key`),
    la desalineacion de grafia SI reproduce el bug -- el resultado no
    encuentra su evento de cuotas."""
    _sin_alias(monkeypatch)
    eo = EventOdds(event=Event(event_id="e1", sport_key="bt", league=LEAGUE,
                               home=VENDOR_HOME, away=AWAY,
                               start_time=GAME.strftime(ISO), data_label="real"),
                   lines=[MarketLine("h2h", "dk", VENDOR_HOME, 1.9, None)])
    idx = _match_index({"e1": eo})           # normalize por defecto: normalize_key
    r = {"home": HISTORY_HOME, "away": AWAY, "date": _dia_utc(GAME)}
    assert _match_result(r, idx, set()) is None


# --- (e) liga sin alias: comportamiento identico a antes --------------------


def test_liga_sin_alias_es_identica_a_normalize_key(monkeypatch):
    """`get_team_normalizer` sin alias configurados para la liga debe ser
    byte-identico a `normalize_key` -- lo que garantiza que el fix no cambia
    nada para las ligas que hoy no tienen entradas en team_aliases.yaml."""
    _sin_alias(monkeypatch)
    otra_liga = "una_liga_sin_alias"
    norm = get_team_normalizer(otra_liga)
    for name in (VENDOR_HOME, HISTORY_HOME, "Boston Red Sox", "", None):
        assert norm(name) == normalize_key(name)
    # Y de punta a punta: `exact_history_scores_map` no cambia de resultado.
    pendiente = pd.DataFrame([_fila("gN", VENDOR_HOME, GAME.strftime(ISO))])
    resultado = [{"date": _dia_utc(GAME), "home": VENDOR_HOME, "away": AWAY,
                  "home_score": 3, "away_score": 1}]
    assert runner.exact_history_scores_map(pendiente, resultado, otra_liga) == {
        "gN": (3, 1, VENDOR_HOME)}
