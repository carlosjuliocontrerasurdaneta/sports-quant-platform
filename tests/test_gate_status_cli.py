"""AUD-001 (ronda audit-2026-09-18): `scripts/gate_status.py` no puede
evaluar una regla paralela ni anunciar habilitaciones que el registro
persistido no concede.

Escenario reproducido por el auditor OpenAI: 300 filas graduadas del MISMO
evento, todas `win`, p_modelo 0,7, p_mercado 0,8, cuota 1,5. La version antigua
(pick_history, aciertos contra 0,5, EV = p − 1/cuota) imprimia "PASAN EL GATE,
n=300"; el gate canonico devuelve n=1, muestra_insuficiente, allowed=False.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "gate_status_cli", ROOT / "scripts" / "gate_status.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _same_event_rows(n: int = 300) -> pd.DataFrame:
    return pd.DataFrame([{
        "league": "mlb", "market": "h2h", "event_id": "unico",
        "model_probability": 0.7, "implied_probability_novig": 0.8,
        "price_decimal": 1.5, "result": "win", "game_date": "2026-09-01",
    } for _ in range(n)])


def test_repeated_event_is_one_unit_and_never_announced_as_passing():
    cli = _load_cli()
    texto = cli.render({}, _same_event_rows())
    assert "PASAN EL GATE" not in texto
    assert "Habilitados para stake real" not in texto  # registro vacio -> default-deny
    assert "default-deny" in texto
    prog = cli.progress_table(_same_event_rows())
    assert len(prog) == 1
    assert int(prog["n"].iloc[0]) == 1
    assert bool(prog["allowed"].iloc[0]) is False
    assert prog["reason"].iloc[0] == "muestra_insuficiente"


def test_verdict_comes_from_registry_and_respects_latch():
    cli = _load_cli()
    gate = {
        "mlb|h2h": {"allowed": True, "latched": False, "n": 320, "reason": ""},
        "mlb|totals": {"allowed": True, "latched": True, "n": 310,
                       "reason": "agotado_test_unico"},
        "nfl|h2h": {"allowed": False, "latched": False, "n": 12,
                    "reason": "muestra_insuficiente"},
    }
    tabla = cli.verdict_table(gate).set_index("mercado")
    assert bool(tabla.loc["mlb|h2h", "habilitado"]) is True
    assert bool(tabla.loc["mlb|totals", "habilitado"]) is False  # pestillo manda
    assert bool(tabla.loc["nfl|h2h", "habilitado"]) is False
    texto = cli.render(gate, pd.DataFrame())
    linea = next(ln for ln in texto.splitlines() if "Habilitados para stake real" in ln)
    assert "mlb|h2h" in linea and "mlb|totals" not in linea
    assert "Pestillos armados" in texto and "mlb|totals" in texto


def test_rows_before_validation_start_do_not_count():
    cli = _load_cli()
    rows = _same_event_rows(5).assign(
        event_id=[f"e{i}" for i in range(5)], game_date="2026-08-01")
    assert cli.progress_table(rows).empty


def test_min_n_only_filters_the_view():
    cli = _load_cli()
    rows = pd.concat([_same_event_rows(1).assign(event_id=f"e{i}") for i in range(4)],
                     ignore_index=True)
    assert len(cli.progress_table(rows)) == 1
    assert cli.progress_table(rows, min_n_display=50).empty


def test_no_parallel_rule_left_in_script():
    src = (ROOT / "scripts" / "gate_status.py").read_text(encoding="utf-8")
    assert "binomtest" not in src.replace('"""', "")  # solo via evaluate_markets
    assert "pick_history" not in src.split('"""')[2]  # fuera del docstring
    assert "evaluate_markets" in src and "load_prediction_gate" in src


def test_gate_allowed_markets_reads_persisted_verdict_not_pre_latch_table(tmp_path):
    """AUD-005: el run diario anuncia habilitados desde el registro escrito, no
    desde `decided`. Un corte que cumple los criterios hoy pero cuyo test unico
    de entrada ya se consumio (o tiene pestillo) NO puede anunciarse."""
    import json

    from sqp.risk.prediction_gate import (PREDICTION_GATE_FILENAME,
                                          evaluate_markets, gate_allowed_markets,
                                          write_prediction_gate)
    rows = pd.DataFrame([{
        "league": "mlb", "market": "h2h", "event_id": f"e{i}",
        "model_probability": 0.62, "implied_probability_novig": 0.5,
        "price_decimal": 2.0, "result": "win", "game_date": "2026-09-01",
    } for i in range(320)])
    decided = evaluate_markets(rows)
    assert bool(decided["allowed"].iloc[0]) is True  # elegible hoy
    previo = {"markets": {"mlb|h2h": {"allowed": False, "latched": False,
                                      "entry_test_at": "2026-09-10T00:00:00+00:00",
                                      "n": 300, "reason": "test_agotado"}}}
    (tmp_path / PREDICTION_GATE_FILENAME).write_text(json.dumps(previo), encoding="utf-8")
    write_prediction_gate(rows, tmp_path)
    assert gate_allowed_markets(tmp_path) == []
    anunciado_antes = [f"{r.league}|{r.market}" for r in decided.itertuples() if r.allowed]
    assert anunciado_antes == ["mlb|h2h"]  # lo que el log decia hasta AUD-005
