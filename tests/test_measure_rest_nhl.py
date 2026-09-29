"""Pruebas de las correcciones pedidas por la revision independiente de Fable
sobre `scripts/research/measure_rest_nhl.py` (pre-registro del descanso/
back-to-back en NHL, `docs/research/2026-09-27-preregistro-descanso-nhl.md`).

No ejecuta `--pre` ni el modo completo (serian mediciones sobre el historico
real de produccion, fuera del alcance de esta correccion): solo ejercita, con
datos sinteticos, las funciones puras que cambiaron.
"""
from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pandas as pd
import pytest

from sqp.config import ROOT

SCRIPT = ROOT / "scripts" / "research" / "measure_rest_nhl.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("measure_rest_nhl", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


def test_script_exists():
    assert SCRIPT.exists()


# --------------------------- informe 11: esquema real de goalies_nhl.csv ---
APPEARANCE_COLUMNS = [
    "nhl_game_id", "espn_game_id", "date", "game_type", "start_time_utc",
    "team_side", "team_nhl", "team_espn", "matched",
    "goalie_player_id", "goalie_name", "starter",
    "shots_against", "saves", "goals_against", "toi", "fetched_at",
]


def _appearance_row(**overrides) -> dict:
    row = {c: None for c in APPEARANCE_COLUMNS}
    row.update({
        "nhl_game_id": "1", "espn_game_id": "1", "game_type": "R",
        "start_time_utc": "2026-01-01T00:00:00Z", "team_side": "home",
        "team_espn": "Toronto Maple Leafs", "matched": True,
        "goalie_name": "Goalie", "shots_against": 30, "saves": 28,
        "goals_against": 2, "toi": "60:00", "fetched_at": "2026-01-01T12:00:00Z",
    })
    row.update(overrides)
    return row


def _write_goalies_csv(root, rows: list[dict]) -> None:
    d = root / "data" / "historical"
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=APPEARANCE_COLUMNS).to_csv(d / "goalies_nhl.csv", index=False)


def test_informe_goalies_uses_team_nhl_and_goalie_player_id_not_team(mod, tmp_path, monkeypatch):
    """Esquema real (`src/sqp/storage/goalies.py:44`): no hay columna `team`,
    sino `team_nhl`/`team_side`, y `starter` es booleano. El informe debe
    leerlas correctamente y filtrar solo starter==True."""
    rows = [
        _appearance_row(nhl_game_id="1", date="2026-01-01", team_nhl="TOR",
                        goalie_player_id="G1", starter=True),
        # Backup del mismo partido: debe filtrarse (starter=False).
        _appearance_row(nhl_game_id="1", date="2026-01-01", team_nhl="TOR",
                        goalie_player_id="G9", starter=False),
        # Al dia siguiente (r=1, back-to-back): cambia el titular.
        _appearance_row(nhl_game_id="2", date="2026-01-02", team_nhl="TOR",
                        goalie_player_id="G2", starter=True),
        # Tres dias despues (r=3, no back-to-back): mismo titular.
        _appearance_row(nhl_game_id="3", date="2026-01-05", team_nhl="TOR",
                        goalie_player_id="G2", starter=True),
    ]
    _write_goalies_csv(tmp_path, rows)
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    out = mod._informe_goalies_solo_identidades([])
    assert out == {
        "1": {"cambios": 1, "total": 1, "fraccion": 1.0},
        "otros": {"cambios": 0, "total": 1, "fraccion": 0.0},
    }


def test_informe_goalies_tolerates_string_and_numeric_boolean_serializations(mod, tmp_path,
                                                                             monkeypatch):
    """`starter` puede llegar como "True"/"False" (str por defecto de pandas
    al leer un CSV) o como 1/0 -- misma tolerancia que
    `pipeline.goalie_backfill._load_complete_game_ids`."""
    d = tmp_path / "data" / "historical"
    d.mkdir(parents=True, exist_ok=True)
    raw = (
        "date,team_nhl,goalie_player_id,starter\n"
        "2026-01-01,TOR,G1,True\n"
        "2026-01-02,TOR,G1,1\n"
        "2026-01-02,TOR,G9,False\n"
    )
    (d / "goalies_nhl.csv").write_text(raw, encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    out = mod._informe_goalies_solo_identidades([])
    assert out == {
        "1": {"cambios": 0, "total": 1, "fraccion": 0.0},
        "otros": {"cambios": 0, "total": 0, "fraccion": None},
    }


def test_informe_goalies_returns_none_when_file_absent(mod, tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod._informe_goalies_solo_identidades([]) is None


# ---------------------- proteccion de informes secundarios (nunca aborta) --
def test_safe_informe_returns_the_result_on_success(mod):
    assert mod._safe_informe("x", lambda: {"a": 1}) == {"a": 1}


def test_safe_informe_captures_an_exception_instead_of_raising(mod):
    def boom():
        raise ValueError("fallo sintetico")
    out = mod._safe_informe("x", boom)
    assert out == {"error": "ValueError: fallo sintetico"}


def test_informe_goalies_schema_error_is_caught_by_safe_informe(mod, tmp_path, monkeypatch):
    """Un fichero con el esquema INCORRECTO (p.ej. sin `team_nhl`) no debe
    tirar todo el modo completo: `_safe_informe` debe envolverlo."""
    d = tmp_path / "data" / "historical"
    d.mkdir(parents=True, exist_ok=True)
    (d / "goalies_nhl.csv").write_text("date,team,starter\n2026-01-01,TOR,True\n",
                                       encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    out = mod._safe_informe("porteros_identidades",
                            lambda: mod._informe_goalies_solo_identidades([]))
    assert "error" in out


# ------------------------------------------ bootstrap: probabilidad extra --
def test_bootstrap_adds_prob_supera_margen_when_margen_is_given(mod):
    dates = np.array(["2026-01-01"] * 20)
    diff = np.full(20, -0.05)  # muy por debajo de cualquier margen razonable
    out = mod.bootstrap_por_fecha(dates, diff, margen=0.002)
    assert out["prob_supera_margen"] == pytest.approx(1.0)


def test_bootstrap_omits_prob_supera_margen_by_default(mod):
    dates = np.array(["2026-01-01"] * 20)
    diff = np.full(20, -0.05)
    out = mod.bootstrap_por_fecha(dates, diff)
    assert "prob_supera_margen" not in out


def test_bootstrap_prob_supera_margen_is_zero_when_delta_never_reaches_it(mod):
    dates = np.array(["2026-01-01"] * 20)
    diff = np.full(20, 0.05)  # Delta positivo: nunca <= -margen
    out = mod.bootstrap_por_fecha(dates, diff, margen=0.002)
    assert out["prob_supera_margen"] == pytest.approx(0.0)


# --------------------------------------------------- --pre-json obligatorio --
def test_check_pre_hash_raises_when_pre_json_lacks_hash(mod):
    with pytest.raises(SystemExit):
        mod._check_pre_hash({}, {"sha256": "aaa"})


def test_check_pre_hash_raises_when_current_file_lacks_hash(mod):
    with pytest.raises(SystemExit):
        mod._check_pre_hash({"sha256": "aaa"}, {})


def test_check_pre_hash_raises_on_mismatch(mod):
    with pytest.raises(SystemExit):
        mod._check_pre_hash({"sha256": "aaa"}, {"sha256": "bbb"})


def test_check_pre_hash_passes_on_match(mod):
    mod._check_pre_hash({"sha256": "aaa"}, {"sha256": "aaa"})  # no debe lanzar


def test_full_mode_requires_pre_json_argument(mod, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["measure_rest_nhl.py", "--out", "ignored.json"])
    with pytest.raises(SystemExit):
        mod.main()


def test_pre_json_rejected_outside_full_mode(mod, monkeypatch, tmp_path):
    pre_json = tmp_path / "pre.json"
    pre_json.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv",
                        ["measure_rest_nhl.py", "--parity-only", "--pre-json", str(pre_json)])
    with pytest.raises(SystemExit):
        mod.main()
