"""Gate de prediccion por (liga, mercado): la regla de salida vigente.

Criterio pre-registrado en docs/research/2026-08-16-preregistro-regla-de-salida.md:
un mercado lleva stake real solo si su modelo PURO bate al mercado en test de
signo pareado fuera de muestra (n >= 300, p < 0.05) Y su EV a stake plano es
positivo. Default-deny.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from sqp.risk.prediction_gate import (VALIDATION_START, evaluate_markets,
                                      load_prediction_gate, market_allowed,
                                      write_prediction_gate)


def _rows(n_win: int, n_loss: int, *, p_model: float, p_market: float,
          price: float, league: str = "brasileirao", market: str = "totals",
          game_date: str = "2026-09-01",
          event_prefix: str | None = None) -> pd.DataFrame:
    """Filas graduadas sinteticas: n_win ganadas y n_loss perdidas.

    Cada fila lleva su PROPIO `event_id`: estas pruebas quieren n observaciones
    independientes, y desde que el gate colapsa por evento
    (`_independent_units`) eso hay que decirlo explicitamente en el dato."""
    prefix = event_prefix or f"{league}-{market}-{game_date}"
    recs = []
    for result, count in (("win", n_win), ("loss", n_loss)):
        for _ in range(count):
            recs.append({"league": league, "market": market,
                         "event_id": f"{prefix}-{len(recs)}",
                         "model_probability": p_model,
                         "implied_probability_novig": p_market,
                         "price_decimal": price, "result": result,
                         "game_date": game_date})
    return pd.DataFrame(recs)


# --- default-deny -------------------------------------------------------------

def test_empty_registry_denies_every_market():
    assert market_allowed({}, "brasileirao", "totals") is False


def test_market_absent_from_registry_is_denied():
    gate = {"mlb|h2h": {"allowed": True}}
    assert market_allowed(gate, "brasileirao", "totals") is False


def test_market_present_and_allowed_is_permitted():
    gate = {"brasileirao|totals": {"allowed": True}}
    assert market_allowed(gate, "brasileirao", "totals") is True


def test_market_present_but_not_allowed_is_denied():
    gate = {"brasileirao|totals": {"allowed": False}}
    assert market_allowed(gate, "brasileirao", "totals") is False


# --- fuera de muestra ---------------------------------------------------------

def test_rows_on_or_before_the_preregistration_date_are_ignored():
    """El pre-registro es del 2026-08-16: solo cuenta lo ESTRICTAMENTE
    posterior. Usar lo anterior seria validar sobre la muestra donde se
    descubrio el patron (KI-019)."""
    df = _rows(240, 160, p_model=0.6, p_market=0.5, price=2.0,
               game_date=VALIDATION_START)
    out = evaluate_markets(df)
    assert out.empty or int(out.iloc[0]["n"]) == 0


def test_only_rows_after_the_preregistration_date_are_counted():
    viejo = _rows(240, 160, p_model=0.6, p_market=0.5, price=2.0,
                  game_date="2026-08-01")
    nuevo = _rows(180, 120, p_model=0.6, p_market=0.5, price=2.0,
                  game_date="2026-09-01")
    out = evaluate_markets(pd.concat([viejo, nuevo], ignore_index=True))
    assert int(out.iloc[0]["n"]) == 300


# --- condicion 1: bate al mercado ---------------------------------------------

def test_thin_sample_is_denied_however_good_it_looks():
    # n=200 < PREDICTION_GATE_MIN_N (300) → muestra insuficiente
    df = _rows(120, 80, p_model=0.6, p_market=0.5, price=2.0)
    out = evaluate_markets(df)
    row = out.iloc[0]
    assert bool(row["allowed"]) is False
    assert row["reason"] == "muestra_insuficiente"


def test_model_beating_the_market_with_positive_ev_is_allowed():
    df = _rows(240, 160, p_model=0.6, p_market=0.5, price=2.0)
    out = evaluate_markets(df)
    row = out.iloc[0]
    assert int(row["n"]) == 400
    assert int(row["wins"]) == 240
    assert row["p_value"] < 0.05
    assert row["ev_flat"] > 0
    assert bool(row["allowed"]) is True


def test_model_losing_to_the_market_is_denied():
    """El modelo yerra mas que el mercado evento a evento: 160 de 400."""
    df = _rows(160, 240, p_model=0.6, p_market=0.5, price=2.0)
    out = evaluate_markets(df)
    row = out.iloc[0]
    assert bool(row["allowed"]) is False
    assert row["reason"] == "no_bate_al_mercado"


def test_exact_ties_are_excluded_from_the_sample():
    """p_modelo == p_mercado -> d == 0. Se excluyen, no cuentan como derrota
    (misma convencion que el gate intradia, KI-020)."""
    reales = _rows(240, 160, p_model=0.6, p_market=0.5, price=2.0)
    empates = _rows(50, 50, p_model=0.5, p_market=0.5, price=2.0)
    out = evaluate_markets(pd.concat([reales, empates], ignore_index=True))
    assert int(out.iloc[0]["n"]) == 400


# --- independencia de los ensayos ---------------------------------------------

def _serving(event_id: str, selection: str, *, result: str, p_model: float,
             p_market: float, price: float, generated_at: str,
             market: str = "h2h", line: float = 0.0,
             home: str = "LA Galaxy", away: str = "Austin FC") -> dict:
    """Fila servida con la forma REAL del stream: `home`/`away` van siempre
    (`served_store.COLUMNS`), y `line` es RELATIVA AL LADO en spreads."""
    return {"league": "mls", "market": market, "event_id": event_id,
            "selection": selection, "line": line, "home": home, "away": away,
            "model_probability": p_model,
            "implied_probability_novig": p_market, "price_decimal": price,
            "result": result, "game_date": "2026-09-01",
            "generated_at": generated_at}


def test_repeated_servings_of_the_same_pick_count_once():
    """`append_served` deduplica solo dentro del mismo dia de run, asi que un
    pick dentro del horizonte de 7 dias entra una vez por dia. Medido el
    2026-08-27: `mls|h2h` tenia 348 filas de 21 eventos con el umbral en 300."""
    filas = [_serving("e1", "LA Galaxy", result="win", p_model=0.6,
                      p_market=0.5, price=2.0,
                      generated_at=f"2026-08-2{d}T12:00:00Z") for d in range(1, 8)]
    out = evaluate_markets(pd.DataFrame(filas))
    assert int(out.iloc[0]["n"]) == 1, "siete servidas del mismo pick son UN evento"


def test_both_sides_of_the_same_market_count_once():
    """Con probabilidades complementarias, `(p'-y')^2 == (p-y)^2`: el lado
    contrario da EXACTAMENTE el mismo `d` y no aporta ni un bit."""
    filas = [
        _serving("e1", "LA Galaxy", result="win", p_model=0.6, p_market=0.5,
                 price=2.0, generated_at="2026-08-21T12:00:00Z"),
        _serving("e1", "Austin FC", result="loss", p_model=0.4, p_market=0.5,
                 price=2.0, generated_at="2026-08-21T12:00:00Z"),
    ]
    out = evaluate_markets(pd.DataFrame(filas))
    assert int(out.iloc[0]["n"]) == 1


def test_both_sides_of_a_spread_count_once():
    """El caso que el test de arriba NO ejercita: en `spreads` la linea es
    RELATIVA AL LADO -- `probabilities.py` emite (home, +L) y (away, -L) --, asi
    que agrupar por la linea CRUDA separa dos caras que son el mismo ensayo.

    Medido el 2026-09-01 sobre `data/calibration/graded_*.csv`: los 855 pares
    simultaneos suman exactamente 1.000000 en `model_probability`,
    `implied_probability_novig` E `y`, luego `d` es identico y la segunda cara no
    aporta ni un bit. `mlb|spreads` declaraba n=266 sobre 136 eventos reales."""
    filas = [
        _serving("e1", "LA Galaxy", result="win", p_model=0.6, p_market=0.5,
                 price=2.0, generated_at="2026-08-21T12:00:00Z",
                 market="spreads", line=-1.5),
        _serving("e1", "Austin FC", result="loss", p_model=0.4, p_market=0.5,
                 price=2.0, generated_at="2026-08-21T12:00:00Z",
                 market="spreads", line=1.5),
    ]
    out = evaluate_markets(pd.DataFrame(filas))
    assert int(out.iloc[0]["n"]) == 1, "las dos caras de un spread son UN ensayo"


def test_the_same_side_at_opposite_lines_stays_separate():
    """Contraparte del anterior: colapsar por `abs(line)` seria un arreglo
    INCORRECTO. `home -1.5` y `home +1.5` son mercados DISTINTOS (la linea cruzo
    el pick'em entre dias), y en los datos reales del 2026-09-01 hay 20 pares
    evento/seleccion que tienen ambas. Deben seguir contando como dos."""
    filas = [
        _serving("e1", "LA Galaxy", result="win", p_model=0.6, p_market=0.5,
                 price=2.0, generated_at="2026-08-21T12:00:00Z",
                 market="spreads", line=-1.5),
        _serving("e1", "LA Galaxy", result="win", p_model=0.6, p_market=0.5,
                 price=2.0, generated_at="2026-08-22T12:00:00Z",
                 market="spreads", line=1.5),
    ]
    out = evaluate_markets(pd.DataFrame(filas))
    assert int(out.iloc[0]["n"]) == 2, "misma cara a lineas opuestas son DOS mercados"


def test_rows_without_event_id_are_denied():
    """Sin identidad de evento no se puede verificar la independencia, y un
    p-valor sobre filas correlacionadas no significa nada: default-deny."""
    df = _rows(240, 160, p_model=0.6, p_market=0.5, price=2.0).drop(
        columns=["event_id"])
    out = evaluate_markets(df)
    assert out.empty or bool(out.iloc[0]["allowed"]) is False


# --- condicion 2: EV neto de vig ----------------------------------------------

def test_beating_the_market_without_positive_ev_is_denied():
    """Acertar mas que el precio no basta si el margen no cubre el vig: es la
    leccion de pick_mode accuracy (favoritos a 1.07)."""
    df = _rows(240, 160, p_model=0.6, p_market=0.5, price=1.5)
    out = evaluate_markets(df)
    row = out.iloc[0]
    assert row["p_value"] < 0.05, "debe ganar el test de signo"
    assert row["ev_flat"] < 0
    assert bool(row["allowed"]) is False
    assert row["reason"] == "ev_no_positivo"


# --- histeresis del pre-registro: pestillo de una sola direccion ---------------
#
# "Un corte que pase el gate y luego lo pierda NO VUELVE A ENTRAR sin revision
# humana" (pre-registro 2026-08-16, criterios de descarte). No es la histeresis
# de dos umbrales de degradation.py: es un pestillo que solo abre un humano.


def _stream_pass(game_date: str = "2026-09-01") -> pd.DataFrame:
    """240/400 unidades a favor con EV>0: pasa las dos condiciones."""
    return _rows(240, 160, p_model=0.6, p_market=0.5, price=2.0,
                 game_date=game_date, event_prefix=f"pass-{game_date}")


def _stream_fail(game_date: str = "2026-09-02") -> pd.DataFrame:
    """300 derrotas puras del MODELO en el test pareado: confiado (0.6) en
    eventos que se pierden, d = (0.5-0)^2 - (0.6-0)^2 < 0. Acumuladas, hunden
    el test de signo."""
    return _rows(0, 300, p_model=0.6, p_market=0.5, price=2.0,
                 game_date=game_date, event_prefix=f"fail-{game_date}")


def _stream_recover(game_date: str = "2026-09-03") -> pd.DataFrame:
    """400 aciertos: el acumulado VUELVE a cumplir los criterios estadisticos."""
    return _rows(400, 0, p_model=0.6, p_market=0.5, price=2.0,
                 game_date=game_date, event_prefix=f"rec-{game_date}")


def test_a_cut_that_passes_then_fails_is_latched_out(tmp_path):
    """Dia 1 pasa; dia 2 el acumulado deja de cumplir. El pestillo se arma."""
    day1 = _stream_pass()
    write_prediction_gate(day1, tmp_path)
    assert market_allowed(load_prediction_gate(tmp_path),
                          "brasileirao", "totals") is True
    day2 = pd.concat([day1, _stream_fail()], ignore_index=True)
    write_prediction_gate(day2, tmp_path)
    gate = load_prediction_gate(tmp_path)
    assert market_allowed(gate, "brasileirao", "totals") is False
    assert gate["brasileirao|totals"].get("latched") is True


def test_a_latched_cut_does_not_reenter_without_human_release(tmp_path):
    """LA PRUEBA DISCRIMINANTE del pre-registro: pasa -> pierde -> volveria a
    cumplir. Sin liberacion humana debe seguir bloqueado. Con el codigo previo
    (re-evaluacion desde cero cada dia) esto FALLABA: el corte reentraba solo."""
    day1 = _stream_pass()
    write_prediction_gate(day1, tmp_path)
    day2 = pd.concat([day1, _stream_fail()], ignore_index=True)
    write_prediction_gate(day2, tmp_path)
    day3 = pd.concat([day2, _stream_recover()], ignore_index=True)
    # sanity: los criterios estadisticos SI se cumplen el dia 3...
    row = evaluate_markets(day3).iloc[0]
    assert row["p_value"] < 0.05 and row["ev_flat"] > 0
    write_prediction_gate(day3, tmp_path)
    gate = load_prediction_gate(tmp_path)
    # ...pero el pestillo manda: no hay reentrada sin humano.
    assert market_allowed(gate, "brasileirao", "totals") is False
    entry = gate["brasileirao|totals"]
    assert entry.get("latched") is True
    assert bool(entry["allowed"]) is False


def test_human_release_lets_the_cut_reenter_via_the_criteria(tmp_path):
    """La liberacion humana desarma el pestillo; la reentrada la decide el
    criterio pre-registrado en la siguiente evaluacion, no la liberacion."""
    from sqp.risk.prediction_gate import release_prediction_gate_latch
    day1 = _stream_pass()
    write_prediction_gate(day1, tmp_path)
    day2 = pd.concat([day1, _stream_fail()], ignore_index=True)
    write_prediction_gate(day2, tmp_path)
    day3 = pd.concat([day2, _stream_recover()], ignore_index=True)
    write_prediction_gate(day3, tmp_path)
    released = release_prediction_gate_latch(tmp_path, "brasileirao", "totals",
                                             released_by="Carlos",
                                             note="revision humana de prueba")
    assert released is True
    # La liberacion NO pone allowed=true por si misma (direccion segura):
    assert market_allowed(load_prediction_gate(tmp_path),
                          "brasileirao", "totals") is False
    # La siguiente evaluacion aplica el criterio y reabre porque se cumple:
    write_prediction_gate(day3, tmp_path)
    assert market_allowed(load_prediction_gate(tmp_path),
                          "brasileirao", "totals") is True


def test_release_requires_an_identity(tmp_path):
    from sqp.risk.prediction_gate import release_prediction_gate_latch
    with pytest.raises(ValueError):
        release_prediction_gate_latch(tmp_path, "mlb", "h2h", released_by="  ")


def test_release_of_an_unlatched_market_is_a_noop(tmp_path):
    from sqp.risk.prediction_gate import release_prediction_gate_latch
    write_prediction_gate(_stream_pass(), tmp_path)
    assert release_prediction_gate_latch(tmp_path, "brasileirao", "totals",
                                         released_by="Carlos") is False


def test_latch_and_release_leave_an_audit_trail(tmp_path):
    from sqp.risk.prediction_gate import (PREDICTION_GATE_LATCH_LOG,
                                          release_prediction_gate_latch)
    day1 = _stream_pass()
    write_prediction_gate(day1, tmp_path)
    day2 = pd.concat([day1, _stream_fail()], ignore_index=True)
    write_prediction_gate(day2, tmp_path)
    release_prediction_gate_latch(tmp_path, "brasileirao", "totals",
                                  released_by="Carlos", note="ok")
    log = pd.read_csv(tmp_path / PREDICTION_GATE_LATCH_LOG)
    acts = log[(log["league"] == "brasileirao") & (log["market"] == "totals")]
    assert list(acts["action"]) == ["latch", "release"]
    assert acts.iloc[1]["released_by"] == "Carlos"


def test_an_allowed_cut_that_vanishes_from_the_stream_latches(tmp_path):
    """Si un corte aprobado desaparece de la evaluacion, no se puede verificar
    que siga cumpliendo: direccion segura, se arma el pestillo."""
    write_prediction_gate(_stream_pass(), tmp_path)
    write_prediction_gate(pd.DataFrame(), tmp_path)
    gate = load_prediction_gate(tmp_path)
    entry = gate.get("brasileirao|totals")
    assert entry is not None
    assert bool(entry["allowed"]) is False
    assert entry.get("latched") is True


def test_old_format_registry_without_latch_fields_still_works(tmp_path):
    """Retrocompatibilidad del contrato persistido: un registro escrito por la
    version ANTERIOR (sin `latched`) debe cargar, negar por defecto y no armar
    pestillos espurios sobre cortes que nunca estuvieron aprobados."""
    (tmp_path / "prediction_gate.json").write_text(json.dumps({
        "generated_at": "2026-09-01T00:00:00+00:00", "min_n": 300,
        "alpha": 0.05, "validation_start": "2026-08-16",
        "markets": {"mlb|spreads": {"allowed": False, "n": 150, "wins": 70,
                                    "p_value": 0.76, "ev_flat": -0.02,
                                    "reason": "muestra_insuficiente"}},
    }), encoding="utf-8")
    gate = load_prediction_gate(tmp_path)
    assert market_allowed(gate, "mlb", "spreads") is False
    # Reescribir encima del formato viejo no arma pestillo (nunca fue allowed)
    # ni abre ninguna puerta:
    write_prediction_gate(_rows(10, 5, p_model=0.6, p_market=0.5, price=2.0,
                                league="mlb", market="spreads"), tmp_path)
    gate = load_prediction_gate(tmp_path)
    assert bool(gate["mlb|spreads"]["allowed"]) is False
    assert bool(gate["mlb|spreads"].get("latched")) is False


def test_market_allowed_denies_a_forged_allowed_with_latch():
    """Cinturon y tirantes: aunque un registro llegara con allowed=true y
    latched=true a la vez, el consumidor niega."""
    gate = {"mlb|h2h": {"allowed": True, "latched": True}}
    assert market_allowed(gate, "mlb", "h2h") is False


# --- persistencia -------------------------------------------------------------

def test_registry_is_written_even_without_markets(tmp_path):
    """Un registro con markets vacio hace EXPLICITO el default-deny."""
    path = write_prediction_gate(pd.DataFrame(), tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["markets"] == {}
    assert load_prediction_gate(tmp_path) == {}


def test_written_registry_round_trips_the_decision(tmp_path):
    df = _rows(240, 160, p_model=0.6, p_market=0.5, price=2.0)
    write_prediction_gate(df, tmp_path)
    gate = load_prediction_gate(tmp_path)
    assert market_allowed(gate, "brasileirao", "totals") is True


def test_missing_registry_loads_as_default_deny(tmp_path):
    assert load_prediction_gate(tmp_path) == {}


def test_corrupt_registry_loads_as_default_deny(tmp_path):
    (tmp_path / "prediction_gate.json").write_text("{no es json", encoding="utf-8")
    assert load_prediction_gate(tmp_path) == {}


@pytest.mark.parametrize("missing", ["model_probability",
                                     "implied_probability_novig",
                                     "price_decimal"])
def test_rows_missing_a_required_column_are_dropped(missing):
    df = _rows(240, 160, p_model=0.6, p_market=0.5, price=2.0)
    df[missing] = float("nan")
    out = evaluate_markets(df)
    assert out.empty or bool(out.iloc[0]["allowed"]) is False


# --- carga del stream graduado ------------------------------------------------

def test_load_all_graded_tags_every_row_with_its_league(tmp_path):
    """La carga vive en el store porque la consumen tres sitios (el gate diario,
    el script y el analisis de prediccion); duplicarla invita a que diverjan."""
    from sqp.storage.served_store import ServedStore
    store = ServedStore(tmp_path)
    store.dir.mkdir(parents=True, exist_ok=True)
    _rows(2, 1, p_model=0.6, p_market=0.5, price=2.0).to_csv(
        store.graded_path("brasileirao"), index=False)
    _rows(1, 1, p_model=0.6, p_market=0.5, price=2.0).to_csv(
        store.graded_path("mlb"), index=False)
    out = store.load_all_graded()
    assert len(out) == 5
    assert set(out["league"]) == {"brasileirao", "mlb"}


def test_load_all_graded_without_any_file_is_empty(tmp_path):
    from sqp.storage.served_store import ServedStore
    assert ServedStore(tmp_path).load_all_graded().empty


# --- plomeria de configuracion ------------------------------------------------

def test_settings_expose_the_prediction_gate_flag():
    from sqp.config import Settings
    assert Settings.load().prediction_gate_enabled is True


def test_production_yaml_enables_the_prediction_gate():
    """Es la regla de salida vigente: si se apaga, no queda ninguna barrera
    rectora entre un pick y el dinero."""
    from sqp.config import CONFIG_DIR, load_yaml
    cfg = load_yaml(CONFIG_DIR / "default.yaml")
    assert (cfg.get("prediction_gate") or {}).get("enabled") is True


# --- cableado en la decision de stake -----------------------------------------

def test_blocked_market_is_flagged_prediction_gate():
    from sqp.pipeline.daily import _zero_stake_flag
    assert _zero_stake_flag(False, False, False,
                            prediction_blocked=True) == "prediction_gate"


def test_allowed_market_carries_stake():
    from sqp.pipeline.daily import _zero_stake_flag
    assert _zero_stake_flag(False, False, False,
                            prediction_blocked=False) is None


def test_shadow_mode_still_outranks_the_prediction_gate():
    from sqp.pipeline.daily import _zero_stake_flag
    assert _zero_stake_flag(False, False, True,
                            prediction_blocked=True) == "shadow_mode"


def test_pause_outranks_the_prediction_gate():
    from sqp.pipeline.daily import _zero_stake_flag
    assert _zero_stake_flag(True, False, False,
                            prediction_blocked=True) == "market_paused"


def test_gate_verdicts_none_means_gate_disabled_not_blocking():
    """`None` = gate apagado. Es la distincion que el `and` inline hacia de
    forma implicita y donde se escondio el NameError del 2026-08-17."""
    from sqp.pipeline.daily import _gate_verdicts
    assert _gate_verdicts(None, None, "mlb", "h2h") == (False, False)


def test_gate_verdicts_empty_registry_blocks_default_deny():
    from sqp.pipeline.daily import _gate_verdicts
    assert _gate_verdicts({}, {}, "mlb", "h2h") == (True, True)


def test_gate_verdicts_allowed_market_is_not_blocked():
    from sqp.pipeline.daily import _gate_verdicts
    gate = {"mlb|h2h": {"allowed": True}}
    assert _gate_verdicts(gate, None, "mlb", "h2h") == (False, False)


def test_gate_verdicts_are_independent_per_gate():
    """El de prediccion permite y el de CLV no: cada uno responde por si mismo.
    Quien decide la precedencia es _zero_stake_flag, no esta funcion."""
    from sqp.pipeline.daily import _gate_verdicts
    pred = {"mlb|h2h": {"allowed": True}}
    clv = {"mlb|h2h": {"allowed": False}}
    assert _gate_verdicts(pred, clv, "mlb", "h2h") == (False, True)


def test_gate_verdicts_other_market_of_the_same_league_is_blocked():
    from sqp.pipeline.daily import _gate_verdicts
    gate = {"mlb|h2h": {"allowed": True}}
    assert _gate_verdicts(gate, None, "mlb", "totals") == (True, False)


def test_daily_module_resolves_the_prediction_gate_helpers():
    """Red de seguridad para un fallo REAL observado el 2026-08-17.

    La rama que consulta el gate vive bajo `mode != "demo"`, y en demo
    `prediction_gate` es None, asi que el `and` corto-circuita y la llamada a
    `prediction_allowed` nunca se evalua. Un NameError en esa linea paso los
    1073 tests de la suite entera y solo lo detecto ruff (F821): habria
    explotado en el primer run diario en vivo.

    Verificar que los helpers se resuelven en el namespace del modulo es barato
    y cubre exactamente ese agujero. NO sustituye a un test de integracion de la
    ruta live, que sigue sin existir."""
    from sqp.pipeline import daily
    assert callable(daily.prediction_allowed)
    assert callable(daily.load_prediction_gate)


def test_prediction_gate_live_route_end_to_end(tmp_path):
    """Integración de la ruta live: write gate -> load -> _gate_verdicts ->
    _zero_stake_flag. Cubre el agujero documentado en el comentario del test
    anterior: que los helpers sean callables NO garantiza que la cadena completa
    funcione correctamente en el camino live (mode != 'demo').

    Usa n=500 (>= min_n=300) con win-rate suficiente para que el gate apruebe,
    y verifica que el mercado resultante no bloquea el stake."""
    from sqp.pipeline.daily import _gate_verdicts, _zero_stake_flag
    from sqp.risk.prediction_gate import load_prediction_gate, write_prediction_gate

    df = _rows(300, 200, p_model=0.6, p_market=0.5, price=2.0,
               league="mlb", market="h2h", game_date="2026-09-01")
    write_prediction_gate(df, tmp_path)
    gate = load_prediction_gate(tmp_path)

    pred_blocked, clv_blocked = _gate_verdicts(gate, None, "mlb", "h2h")
    flag = _zero_stake_flag(False, False, False,
                            prediction_blocked=pred_blocked,
                            clv_blocked=clv_blocked)
    assert pred_blocked is False
    assert flag is None


def test_prediction_gate_live_route_blocks_denied_market(tmp_path):
    """Un mercado con n insuficiente escrito al gate debe bloquear el stake."""
    from sqp.pipeline.daily import _gate_verdicts, _zero_stake_flag
    from sqp.risk.prediction_gate import load_prediction_gate, write_prediction_gate

    df = _rows(120, 80, p_model=0.6, p_market=0.5, price=2.0,
               league="nfl", market="totals", game_date="2026-09-01")
    write_prediction_gate(df, tmp_path)
    gate = load_prediction_gate(tmp_path)

    pred_blocked, _ = _gate_verdicts(gate, None, "nfl", "totals")
    flag = _zero_stake_flag(False, False, False, prediction_blocked=pred_blocked)
    assert pred_blocked is True
    assert flag == "prediction_gate"


def test_prediction_gate_outranks_the_clv_gate():
    """El de prediccion es la regla RECTORA desde 2026-08-16; el de CLV queda
    como evidencia. Si ambos bloquean, el motivo que se reporta es el vigente."""
    from sqp.pipeline.daily import _zero_stake_flag
    assert _zero_stake_flag(False, False, False, clv_blocked=True,
                            prediction_blocked=True) == "prediction_gate"


# --- multiplicidad y miradas repetidas ---------------------------------------
# Pre-registro 2026-09-04, aprobado por el operador. Dos reglas: alpha repartido
# por Bonferroni sobre K=41 cortes, y UN SOLO test de entrada por corte.

def test_alpha_is_the_family_alpha_split_by_bonferroni():
    """El numero no se escribe a mano: se DERIVA, para que no pueda derivar de
    sus dos factores sin que se note en el diff."""
    from sqp.risk.prediction_gate import (PREDICTION_GATE_ALPHA,
                                          PREDICTION_GATE_FAMILY_ALPHA,
                                          PREDICTION_GATE_K)
    assert PREDICTION_GATE_FAMILY_ALPHA == 0.05
    assert PREDICTION_GATE_K == 41
    assert PREDICTION_GATE_ALPHA == pytest.approx(0.05 / 41)
    assert PREDICTION_GATE_ALPHA < 0.05, "Bonferroni solo puede ENDURECER"


def test_a_cut_that_would_pass_at_005_but_not_at_bonferroni_is_denied():
    """La discriminacion que importa: una ventaja que el alpha viejo aprobaba y
    el nuevo no. 165/300 da p just under 0,05 y muy por encima de 0,00122."""
    from scipy.stats import binomtest
    from sqp.risk.prediction_gate import PREDICTION_GATE_ALPHA
    p = binomtest(165, 300, 0.5, alternative="greater").pvalue
    assert p < 0.05, "premisa del test: al alpha antiguo esto pasaba"
    assert p > PREDICTION_GATE_ALPHA, "premisa: al alpha nuevo ya no"
    out = evaluate_markets(_rows(165, 135, p_model=0.6, p_market=0.5, price=2.0))
    assert bool(out.iloc[0]["allowed"]) is False
    assert out.iloc[0]["reason"] == "no_bate_al_mercado"


def test_the_entry_test_is_not_spent_while_the_sample_is_thin(tmp_path):
    """Un corte sin muestra no ha gastado su unica bala: si la gastara, bastaria
    con existir unos dias para quedarse fuera para siempre."""
    from sqp.risk.prediction_gate import load_prediction_gate
    write_prediction_gate(_rows(60, 40, p_model=0.6, p_market=0.5, price=2.0),
                          tmp_path)
    e = load_prediction_gate(tmp_path)["brasileirao|totals"]
    assert e["reason"] == "muestra_insuficiente"
    assert e["entry_test_at"] is None


def test_a_cut_gets_exactly_one_entry_test(tmp_path):
    """El corazon del pre-registro. Dia 1: alcanza n>=300 y NO pasa -> gasta el
    test. Dia 2: los mismos datos mas una racha que SI pasaria el criterio ->
    sigue fuera. Sin esta regla el gate reevalua a diario y el corte tira el
    dado hasta que le sale (parada opcional)."""
    from sqp.risk.prediction_gate import load_prediction_gate
    flojo = _rows(160, 140, p_model=0.6, p_market=0.5, price=2.0)
    write_prediction_gate(flojo, tmp_path)
    e1 = load_prediction_gate(tmp_path)["brasileirao|totals"]
    assert bool(e1["allowed"]) is False and e1["entry_test_at"] is not None
    gastado = e1["entry_test_at"]

    fuerte = pd.concat([flojo, _rows(300, 0, p_model=0.6, p_market=0.5,
                                     price=2.0, event_prefix="extra")],
                       ignore_index=True)
    write_prediction_gate(fuerte, tmp_path)
    e2 = load_prediction_gate(tmp_path)["brasileirao|totals"]
    assert e2["p_value"] < 0.00122, "premisa: al criterio le sobraria evidencia"
    assert bool(e2["allowed"]) is False, (
        "gasto su test unico: no reentra por acumular una racha despues")
    assert e2["reason"] == "agotado_test_unico"
    assert e2["entry_test_at"] == gastado, "el sello del test no se reescribe"


def test_human_release_returns_the_entry_test(tmp_path):
    """La liberacion autoriza la RE-EVALUACION, no la entrada: devuelve el test
    y decide despues el criterio pre-registrado."""
    from sqp.risk.prediction_gate import (load_prediction_gate,
                                          release_prediction_gate_latch)
    write_prediction_gate(_rows(160, 140, p_model=0.6, p_market=0.5, price=2.0),
                          tmp_path)
    assert release_prediction_gate_latch(tmp_path, "brasileirao", "totals",
                                         released_by="Carlos") is True
    e = load_prediction_gate(tmp_path)["brasileirao|totals"]
    assert e["entry_test_at"] is None and bool(e["allowed"]) is False
    assert e["reason"] == "liberado_pendiente_reevaluacion"


def test_vanishing_from_the_stream_does_not_return_the_entry_test(tmp_path):
    """Si desaparecer devolviera el test, un corte se quedaria sin partidos unos
    dias y volveria a tirar el dado."""
    from sqp.risk.prediction_gate import load_prediction_gate
    write_prediction_gate(_rows(160, 140, p_model=0.6, p_market=0.5, price=2.0),
                          tmp_path)
    gastado = load_prediction_gate(tmp_path)["brasileirao|totals"]["entry_test_at"]
    write_prediction_gate(_rows(10, 10, p_model=0.6, p_market=0.5, price=2.0,
                                league="otra"), tmp_path)
    e = load_prediction_gate(tmp_path)["brasileirao|totals"]
    assert e["reason"] == "sin_evaluacion" and e["entry_test_at"] == gastado


def test_the_registry_records_how_alpha_was_split(tmp_path):
    """Sin esto, leyendo el registro no se puede reconstruir de donde sale un
    alpha de 0,00122 -- y un umbral que no se puede auditar no es un candado."""
    import json
    write_prediction_gate(_rows(60, 40, p_model=0.6, p_market=0.5, price=2.0),
                          tmp_path)
    payload = json.loads((tmp_path / "prediction_gate.json").read_text(encoding="utf-8"))
    assert payload["family_alpha"] == 0.05
    assert payload["k_bonferroni"] == 41
    assert payload["alpha"] == pytest.approx(0.05 / 41)
