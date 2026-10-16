"""AUD-001: emparejamiento resultado<->cuotas 1:1, por fecha canonica, sin voracidad."""
import random

from sqp.backtesting.roi_engine import (_match_index, _match_result, match_results,
                                        realized_roi_backtest)
from sqp.config import RiskConfig
from sqp.domain.models import Event, EventOdds, MarketLine


def _eo(eid, home, away, start, league="mlb"):
    return EventOdds(
        event=Event(event_id=eid, sport_key="bt", league=league, home=home,
                    away=away, start_time=start, data_label="real"),
        lines=[MarketLine("h2h", "dk", home, 1.9, None),
               MarketLine("h2h", "dk", away, 2.1, None)])


def _res(day, home="A", away="B", hs=5, as_=3, gid="g"):
    return {"date": day, "home": home, "away": away, "home_score": hs,
            "away_score": as_, "neutral": False, "game_id": gid}


def _west_coast_series():
    # Dia local D=06-01 inicia 02:10Z de 06-02; D+1=06-02 inicia 02:10Z de 06-03.
    # Faltan las cuotas del dia 06-01.
    odds = {"e2": _eo("e2", "A", "B", "2026-06-03T02:10:00Z")}
    results = [_res("2026-06-01", gid="g1"), _res("2026-06-02", gid="g2")]
    return odds, results


def test_mlb_west_coast_missing_odds_does_not_cross_labels():
    odds, results = _west_coast_series()
    m = match_results(results, odds, "mlb")
    assert 0 not in m                       # el dia sin cuotas queda sin pareja
    assert m[1] is odds["e2"]               # el de D+1 recibe las suyas


def test_greedy_legacy_does_cross_labels():
    # Partido nocturno del 06-01 ET (02:10Z del 06-02) sin cuotas; el del 06-02 ET
    # es de tarde (20:00Z del 06-02, dia UTC 06-02): a +-1 dia del resultado 06-01.
    odds = {"e2": _eo("e2", "A", "B", "2026-06-02T20:00:00Z")}
    results = [_res("2026-06-01", gid="g1"), _res("2026-06-02", gid="g2")]
    idx = _match_index(odds)
    # La logica voraz antigua da al resultado del 06-01 las cuotas del 06-02: cruce.
    assert _match_result(results[0], idx, set()) is odds["e2"]
    m = match_results(results, odds, "mlb")
    assert 0 not in m and m[1] is odds["e2"]


def test_doubleheader_same_et_date_is_unmatched():
    odds = {"e1": _eo("e1", "A", "B", "2026-06-01T17:00:00Z"),
            "e2": _eo("e2", "A", "B", "2026-06-01T23:00:00Z")}
    results = [_res("2026-06-01", gid="g1"), _res("2026-06-01", gid="g2")]
    assert match_results(results, odds, "mlb") == {}


def test_espn_league_exact_and_fallback():
    # Inicio 00:30Z de D+1 y resultado ESPN fechado D+1: exacto.
    odds = {"e1": _eo("e1", "A", "B", "2026-06-02T00:30:00Z", "nba")}
    assert match_results([_res("2026-06-02")], odds, "nba")[0] is odds["e1"]
    # Resultado fechado D (06-01), evento en 06-02, sin otro resultado: respaldo.
    assert match_results([_res("2026-06-01")], odds, "nba")[0] is odds["e1"]
    # Otro resultado de la pareja a +-1 dia del evento: no empareja.
    extra = [_res("2026-06-01", gid="g1"), _res("2026-06-03", gid="g2")]
    assert match_results(extra, odds, "nba") == {}


def test_fallback_blocked_when_event_has_own_result():
    odds = {"e1": _eo("e1", "A", "B", "2026-06-02T00:30:00Z", "nba")}
    results = [_res("2026-06-01", gid="g1"), _res("2026-06-02", gid="g2")]
    m = match_results(results, odds, "nba")
    assert 0 not in m and m[1] is odds["e1"]


def test_shuffle_does_not_change_assignment():
    odds = {
        "e1": _eo("e1", "A", "B", "2026-06-01T23:00:00Z"),
        "e2": _eo("e2", "A", "B", "2026-06-03T02:10:00Z"),
        "e3": _eo("e3", "A", "B", "2026-06-05T23:00:00Z"),
        "e4": _eo("e4", "A", "B", "2026-06-05T17:00:00Z"),
    }
    results = [_res("2026-06-01", gid="1"), _res("2026-06-02", gid="2"),
               _res("2026-06-03", gid="3"), _res("2026-06-05", gid="4"),
               _res("2026-06-05", gid="5")]
    base = {results[i]["game_id"]: eo.event.event_id
            for i, eo in match_results(results, odds, "mlb").items()}
    assert base == {"1": "e1", "2": "e2"}
    for seed in range(10):
        shuffled = results[:]
        random.Random(seed).shuffle(shuffled)
        got = {shuffled[i]["game_id"]: eo.event.event_id
               for i, eo in match_results(shuffled, odds, "mlb").items()}
        assert got == base


def test_tennis_keeps_legacy_behavior():
    odds = {"e1": _eo("e1", "Carlos Alcaraz", "Jannik Sinner",
                      "2026-06-20T13:00:00Z", "tennis_atp_x"),
            "e2": _eo("e2", "Jannik Sinner", "Carlos Alcaraz",
                      "2026-06-21T13:00:00Z", "tennis_atp_x")}
    results = [_res("2026-06-20", "Jannik Sinner", "Carlos Alcaraz", gid="a"),
               _res("2026-06-21", "Carlos Alcaraz", "Jannik Sinner", gid="b")]
    idx = _match_index(odds, True)
    used: set[str] = set()
    expected = {}
    for i, r in enumerate(results):
        eo = _match_result(r, idx, used, True)
        if eo is not None:
            expected[i] = eo
    assert expected
    assert match_results(results, odds, "tennis_atp_x", order_insensitive=True) == expected


def test_backtest_no_longer_crosses_labels():
    # Faltan las cuotas del dia 06-01: solo el resultado del 06-02 se empareja.
    odds, results = _west_coast_series()
    out = realized_roi_backtest(results, odds, "mlb", "baseball", None, RiskConfig(),
                                1000.0, warmup=0)
    assert out["n_events_matched"] == 1


def test_tennis_backtest_ignores_rows_outside_the_bet_window():
    # Revision Fable: precalcular el voraz de tenis sobre TODAS las filas dejaba que
    # el resultado del 06-20 (fuera de ventana o de warmup) se quedara con las
    # cuotas del partido valido del 06-21.
    odds = {"e2": _eo("e2", "Jannik Sinner", "Carlos Alcaraz",
                      "2026-06-21T13:00:00Z", "tennis_atp_x")}
    results = [_res("2026-06-20", "Jannik Sinner", "Carlos Alcaraz", gid="a"),
               _res("2026-06-21", "Carlos Alcaraz", "Jannik Sinner", gid="b")]
    for kwargs in ({"warmup": 0, "bet_from_date": "2026-06-21"}, {"warmup": 1}):
        out = realized_roi_backtest(results, odds, "tennis_atp_x", "tennis", None,
                                    RiskConfig(), 1000.0, **kwargs)
        assert out["n_events_matched"] == 1, kwargs


def test_fallback_rejected_with_two_events_around_the_result():
    odds = {"e1": _eo("e1", "A", "B", "2026-06-01T19:00:00Z", "nba"),
            "e3": _eo("e3", "A", "B", "2026-06-03T19:00:00Z", "nba")}
    assert match_results([_res("2026-06-02")], odds, "nba") == {}


def test_two_results_competing_for_one_event_both_unmatched():
    odds = {"e2": _eo("e2", "A", "B", "2026-06-02T19:00:00Z", "nba")}
    results = [_res("2026-06-01", gid="g1"), _res("2026-06-03", gid="g3")]
    assert match_results(results, odds, "nba") == {}
