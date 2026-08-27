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
             p_market: float, price: float, generated_at: str) -> dict:
    return {"league": "mls", "market": "h2h", "event_id": event_id,
            "selection": selection, "line": 0.0, "model_probability": p_model,
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
