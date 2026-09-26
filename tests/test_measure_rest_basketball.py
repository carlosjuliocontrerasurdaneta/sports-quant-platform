"""Pruebas de las correcciones pedidas por la revision independiente de Fable
(APTO CON CAMBIOS) al pre-registro `docs/research/2026-09-26-preregistro-descanso-basket.md`,
sobre `scripts/research/measure_rest_basketball.py`.

No ejecuta `--pre` ni el modo completo (serian mediciones sobre el historico
real, fuera del alcance de esta correccion): solo ejercita, con datos
sinteticos, las funciones puras que cambiaron.
"""
from __future__ import annotations

import importlib.util
import json

import pytest

from sqp.config import ROOT

SCRIPT = ROOT / "scripts" / "research" / "measure_rest_basketball.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("measure_rest_basketball", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


# --------------------------------------------------- E1: renombrado --------
def test_script_lives_at_the_preregistered_path():
    assert SCRIPT.exists()
    assert not (ROOT / "scripts" / "research" / "measure_rest_nba.py").exists()


# --------------------------------------- cambio 2: lineas al medio punto ---
def test_fixed_spread_lines_never_land_on_an_integer(mod):
    import math
    for v in (-3.2, 0.0, 0.4, 1.9, 5.5, -0.5):
        line = math.floor(-v) + 0.5
        assert line != int(line), f"linea={line} para v={v} cae en un entero"


# ---------------------------------- cambio 3: distribucion sin tope --------
def test_uncapped_rest_distribution_separates_four_from_five_or_more(mod):
    import pandas as pd
    series = pd.Series([1, 1, 2, 3, 4, 4, 5, 6, 7, 9])
    out = mod._bucket_5_o_mas(series)
    assert out == {"1": 2, "2": 1, "3": 1, "4": 2, "5+": 4}


def test_rest_calendar_with_injected_uncapped_probe_reports_true_gap(mod):
    from sqp.models.rest import RestModel
    from sqp.sports.team_names import get_team_normalizer

    # T0 juega el dia 0 y no vuelve a jugar hasta el dia 10 (hueco de 10 dias,
    # muy por encima del tope de liga de 4). T1 juega todos los dias frente a
    # rivales de relleno para que el calendario avance.
    results = []
    fillers = ["F0", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"]
    for day in range(11):
        date = f"2024-01-{day + 1:02d}"
        if day == 0:
            results.append({"game_id": f"g{day}", "date": date, "home": "T0", "away": "T1"})
        elif day == 10:
            results.append({"game_id": f"g{day}", "date": date, "home": "T0", "away": "T1"})
        else:
            results.append({"game_id": f"g{day}", "date": date,
                            "home": fillers[day % len(fillers)], "away": "T1"})

    params = {"rest_max_days": 4}
    capped = mod.rest_calendar(results, "nba", params, warmup=0)
    last_row_capped = capped.iloc[-1]
    assert last_row_capped["home"] == "T0"
    assert last_row_capped["hr"] == 4  # topado por rest_max_days

    normalize = get_team_normalizer("nba")
    probe_sin_tope = RestModel(points_per_day=0.0, max_rest=10**9, normalize=normalize)
    uncapped = mod.rest_calendar(results, "nba", params, warmup=0, probe=probe_sin_tope)
    last_row_uncapped = uncapped.iloc[-1]
    assert last_row_uncapped["home"] == "T0"
    assert last_row_uncapped["hr"] == 10  # el hueco real, sin topar


# --------------------------------------------- cambio 6: etiqueta de temp --
def test_bubble_games_in_october_2020_belong_to_2019_20(mod):
    assert mod._nba_season_label("2020-10-11") == "2019-20"
    assert mod._nba_season_label("2020-10-01") == "2019-20"


def test_season_label_is_unchanged_outside_the_bubble(mod):
    assert mod._nba_season_label("2020-09-30") == "2019-20"  # ya era 2019-20 (m<10 en 2020)
    assert mod._nba_season_label("2020-11-01") == "2020-21"  # temporada normal 2020-21
    assert mod._nba_season_label("2021-10-19") == "2021-22"


# ------------------------------------------------- cambio 9: --pre-json ----
def test_check_pre_hash_aborts_on_mismatch(mod):
    pre_data = {"ligas": {"nba": {"sha256": "aaa"}}}
    with pytest.raises(SystemExit):
        mod._check_pre_hash(pre_data, "nba", {"sha256": "bbb"})


def test_check_pre_hash_passes_on_match(mod):
    pre_data = {"ligas": {"nba": {"sha256": "aaa"}}}
    mod._check_pre_hash(pre_data, "nba", {"sha256": "aaa"})  # no debe lanzar


def test_check_pre_hash_is_noop_without_pre_json(mod):
    mod._check_pre_hash(None, "nba", {"sha256": "aaa"})  # no debe lanzar


def test_check_pre_hash_skips_when_either_side_lacks_a_hash(mod):
    mod._check_pre_hash({"ligas": {"nba": {}}}, "nba", {"sha256": "aaa"})
    mod._check_pre_hash({"ligas": {"nba": {"sha256": "aaa"}}}, "nba", {})


# ------------------------------------------- paridad de spreads / empates --
def _synthetic_results_with_one_tie() -> list[dict]:
    """Historico sintetico minimo (6 partidos, sin warmup) con UN empate en
    medio (fila con indice 1, marcador 5-5): lo unico que hace falta para
    ejercitar la asimetria real del motor entre moneyline y spreads.
    `home`/`away` alternan entre dos equipos para que Elo tenga con que
    trabajar; las fechas son estrictamente crecientes."""
    scores = [(10, 0), (5, 5), (8, 2), (3, 7), (6, 4), (9, 1)]
    results = []
    for i, (hs, aws) in enumerate(scores):
        home, away = ("A", "B") if i % 2 == 0 else ("B", "A")
        results.append({
            "game_id": f"g{i}", "date": f"2024-01-{i + 1:02d}",
            "home": home, "away": away,
            "home_score": hs, "away_score": aws,
        })
    return results


def test_build_rest_frame_all_view_keeps_the_tie_the_binary_view_drops(mod):
    """Defecto real corregido en `build_rest_frame`: `engine.walk_forward_backtest`
    excluye empates SOLO de `binary_probs`/`binary_outcomes` (moneyline), no de
    `market_probs`/`market_outcomes` (spreads/totals) -- ver engine.py:105-119.
    `df` (vista tie-excluded) debe seguir sirviendo al moneyline; `df_all` (3er
    valor de retorno) debe conservar el empate para poder reconstruir spreads."""
    results = _synthetic_results_with_one_tie()
    df, _sigma, df_all = mod.build_rest_frame(results, "nba", {}, warmup=0)
    assert (df["y"] == 0.5).sum() == 0
    assert (df_all["y"] == 0.5).sum() == 1
    assert len(df_all) == len(df) + 1
    assert len(df_all) == len(results)


def test_assert_parity_spreads_needs_the_tie_inclusive_view(mod):
    """Reproduce, con datos sinteticos, el fallo real de la ejecucion completa
    (`PARIDAD ROTA (spreads probs) en nba linea 1.5: no se mide nada.`):
    `assert_parity_spreads` llamado con la vista tie-excluded (`df`, la unica
    que existia antes de esta correccion) SIEMPRE rompe la paridad de spreads
    en cuanto hay un empate en el historico, porque el motor no lo excluye de
    `markets['spreads@L']` y las longitudes dejan de coincidir. Llamado con
    `df_all` (incluye el empate), la paridad se mantiene."""
    results = _synthetic_results_with_one_tie()
    params: dict = {}
    df, sigma, df_all = mod.build_rest_frame(results, "nba", params, warmup=0)
    c, lineas = 0.5, [-2.5, 1.5]

    mod.assert_parity_spreads(results, "nba", params, df_all, sigma, c, lineas,
                              warmup=0)  # no debe lanzar

    with pytest.raises(SystemExit):
        mod.assert_parity_spreads(results, "nba", params, df, sigma, c, lineas,
                                  warmup=0)


def test_full_mode_wires_pre_json_into_the_hash_check(mod, tmp_path, monkeypatch):
    """El modo completo debe leer --pre-json y abortar antes de correr nada
    caro si el hash de nba ya no coincide (sin ejecutar el modo completo real:
    se stubean `load_league`/`run_nba` para no tocar el historico ni --pre)."""
    pre_json = tmp_path / "pre.json"
    pre_json.write_text(json.dumps({"ligas": {"nba": {"sha256": "hash-viejo"}}}),
                        encoding="utf-8")

    def _fake_load_league(league):
        assert league == "nba"
        return [{"game_id": "g0"}], {}, {"sha256": "hash-nuevo"}

    monkeypatch.setattr(mod, "load_league", _fake_load_league)
    monkeypatch.setattr("sys.argv",
                        ["measure_rest_basketball.py", "--out", str(tmp_path / "out.json"),
                         "--pre-json", str(pre_json)])
    with pytest.raises(SystemExit):
        mod.main()
