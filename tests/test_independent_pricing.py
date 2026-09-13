from __future__ import annotations

import copy
import importlib.util
import json
from dataclasses import FrozenInstanceError
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from sqp.markets.independent import compare_quotes
from sqp.models.distributions import normal_margin_probs, normal_total_probs, poisson_match_probs
from sqp.models.independent import freeze_model, timestamp

ROOT = Path(__file__).resolve().parents[1]
NOW = timestamp("2026-09-10T12:00:00Z")


@pytest.fixture
def spec():
    return json.loads((ROOT / "examples/independent_model.json").read_text())


@pytest.fixture
def quotes():
    return json.loads((ROOT / "examples/independent_quotes.json").read_text())


def test_freeze_is_immutable_and_does_not_alias_caller(spec):
    frozen = freeze_model(spec, now=NOW)
    report = frozen.report()
    spec["distribution"]["expected_home"] = 20
    exposed = frozen.spec
    exposed["distribution"]["expected_away"] = 30
    assert frozen.report() == report
    with pytest.raises(FrozenInstanceError): frozen.model_id = "changed"
    with pytest.raises(ValueError): frozen._grid()[0, 0] = 2


def test_fingerprint_deterministic_and_versions_change_it(spec):
    one = freeze_model(spec, now=NOW)
    assert one.model_id == freeze_model(copy.deepcopy(spec), now=NOW).model_id
    spec["model_version"] += 1
    assert one.model_id != freeze_model(spec, now=NOW).model_id


@pytest.mark.parametrize("field,value", [("moneyline", 1.9), ("spread", -3), ("market", {}),
                                        ("implied_probability", 0.55)])
def test_market_fields_forbidden_in_sporting_model(spec, field, value):
    spec[field] = value
    with pytest.raises(ValueError, match="unexpected"):
        freeze_model(spec, now=NOW)


@pytest.mark.parametrize("mutate", [
    lambda s: s.update(sporting_as_of="2026-09-10T13:00:00Z"),
    lambda s: s["sources"][0].update(as_of="2026-09-10T11:01:00Z"),
    lambda s: s["event"].update(starts_at="2026-09-10T12:00:00Z"),
    lambda s: s["event"].update(starts_at="2026-09-10T20:00:00"),
    lambda s: s["event"].update(period="full_game"),
    lambda s: s["distribution"].update(dc_rho=-2),
    lambda s: s["distribution"].update(max_score=1),
    lambda s: s["distribution"].update(expected_home=float("nan")),
    lambda s: s["distribution"].update(expected_home=True),
    lambda s: s["distribution"].update(dispersion_k=-1),
    lambda s: s["distribution"].update(max_score=1000000),
    lambda s: s.update(sources=[]),
])
def test_invalid_or_future_model_rejected(spec, mutate):
    mutate(spec)
    with pytest.raises(ValueError): freeze_model(spec, now=NOW)


@pytest.mark.parametrize("kind", ["count", "normal"])
@pytest.mark.parametrize("line", [-1.75, -1, -0.75, -0.25, 0, 0.25, 0.75, 1, 1.75, 3.25])
def test_all_settlement_states_conserve_mass_and_opposites_balance(spec, kind, line):
    if kind == "normal":
        spec["distribution"] = dict(kind="normal", expected_home=110, expected_away=106,
                                    margin_sigma=13, total_sigma=22)
        spec["event"]["period"] = "full_game"
    model = freeze_model(spec, now=NOW)
    for market, side_a, side_b, line_b in [("spread", "home", "away", -line), ("total", "over", "under", line)]:
        a = model.price(market, side_a, line)
        b = model.price(market, side_b, line_b)
        assert a.expected_value(2) + b.expected_value(2) == pytest.approx(0, abs=1e-12)
        if a.fair_decimal is not None and a.fair_decimal > 1:
            assert a.expected_value(a.fair_decimal) == pytest.approx(0, abs=1e-12)


def test_count_probabilities_match_legacy_but_keep_push(spec):
    model = freeze_model(spec, now=NOW)
    old = poisson_match_probs(1.6, 1.1, 0, 3, three_way=True, max_goals=30)
    assert model.price("moneyline_3way", "draw").full_win == pytest.approx(old["draw"])
    assert model.price("spread", "home", 0).decision_probability == pytest.approx(old["home_cover"])
    p = model.price("total", "over", 3)
    assert p.push > 0
    assert p.decision_probability == pytest.approx(old["over"])
    assert p.expected_value(2) != pytest.approx(old["over"] * 2 - 1)
    with pytest.raises(ValueError): model.price("moneyline_2way", "home")


def test_normal_matches_legacy_and_declares_no_draw_convention(spec):
    spec["distribution"] = dict(kind="normal", expected_home=112, expected_away=108,
                                margin_sigma=13, total_sigma=22)
    spec["event"]["period"] = "full_game"
    model = freeze_model(spec, now=NOW)
    old = normal_margin_probs(4, 13, -3)
    assert model.price("moneyline_2way", "home").full_win == pytest.approx(old["home_win"])
    assert model.price("spread", "home", -3).decision_probability == pytest.approx(old["home_cover"])
    assert model.price("total", "under", 220).decision_probability == pytest.approx(normal_total_probs(220, 22, 220)["under"])
    with pytest.raises(ValueError): model.price("moneyline_3way", "draw")


def test_quarter_ev_equals_direct_net_returns_over_same_score_grid(spec):
    model = freeze_model(spec, now=NOW)
    grid = model._grid()
    h, a = np.indices(grid.shape)
    for line in [-1.75, -0.75, -0.25, 0.25, 0.75, 1.75]:
        lo, hi = np.floor(line * 2) / 2, np.ceil(line * 2) / 2
        returns = sum(np.where(h - a + part > 0, 0.95, np.where(h - a + part == 0, 0, -1)) / 2 for part in (lo, hi))
        assert model.price("spread", "home", line).expected_value(1.95) == pytest.approx(float((grid * returns).sum()))


def test_market_comparison_cannot_change_frozen_model(spec, quotes):
    model = freeze_model(spec, now=NOW)
    before = model.report()
    result = compare_quotes(model, quotes, now=NOW, max_age_minutes=90)
    for row in result["quotes"]:
        assert row["no_vig_status"] == "COMPLETE_MATCHED"
        assert row["probability_edge_pp"] == pytest.approx(100 * (row["settlement"]["decision_probability"] - row["market_no_vig_probability"]))
        assert row["stake"] == 0
    quotes["quotes"][0]["price_decimal"] = 10
    compare_quotes(model, quotes, now=NOW, max_age_minutes=90)
    assert model.report() == before


@pytest.mark.parametrize("field,value", [("bookmaker", "OTHER"), ("source", "OTHER"),
                                        ("timestamp", "2026-09-10T11:58:00Z"), ("line", 0.75)])
def test_no_vig_never_mixes_counterparts(spec, quotes, field, value):
    quotes["quotes"] = quotes["quotes"][:2]
    quotes["quotes"][1][field] = value
    rows = compare_quotes(freeze_model(spec, now=NOW), quotes, now=NOW, max_age_minutes=90)["quotes"]
    assert all(r["market_no_vig_probability"] is None for r in rows)
    assert all(r["settlement"]["ev_per_unit"] is not None for r in rows)


@pytest.mark.parametrize("changes", [{"event_id": "wrong"}, {"period": "full_game"},
                                      {"timestamp": "2026-09-10T12:01:00Z"},
                                      {"timestamp": "2026-09-10T09:00:00Z"},
                                      {"price_decimal": float("nan")}, {"price_decimal": 1}, {"line": 0.1}])
def test_bad_quote_rejected_without_dropping_valid_quotes(spec, quotes, changes):
    quotes["quotes"][0].update(changes)
    result = compare_quotes(freeze_model(spec, now=NOW), quotes, now=NOW, max_age_minutes=90)
    assert len(result["rejected_quotes"]) == 1
    assert len(result["quotes"]) == 3


def test_duplicates_are_ambiguous_not_silently_selected(spec, quotes):
    quotes["quotes"].append(copy.deepcopy(quotes["quotes"][0]))
    result = compare_quotes(freeze_model(spec, now=NOW), quotes, now=NOW, max_age_minutes=90)
    assert result["quotes"][0]["no_vig_status"] == "AMBIGUOUS_DUPLICATE"
    assert result["quotes"][0]["market_no_vig_probability"] is None


def test_no_market_and_no_decision_are_not_fabricated(spec):
    spec["distribution"].update(expected_home=0, expected_away=0)
    p = freeze_model(spec, now=NOW).price("total", "over", 0)
    assert p.push == 1 and p.decision_probability is None


def _cli():
    spec = importlib.util.spec_from_file_location("independent_cli_test", ROOT / "scripts/price_independent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_persists_freeze_before_opening_market_and_never_overwrites(tmp_path, monkeypatch):
    cli = _cli()
    out = tmp_path / "audit"
    args = ["--model", str(ROOT / "examples/independent_model.json"), "--quotes",
            str(ROOT / "examples/independent_quotes.json"), "--output-dir", str(out),
            "--as-of", NOW.isoformat(), "--max-quote-age-min", "90"]
    original = cli._load
    reads = []
    def spy(path):
        reads.append(path)
        if "quotes" in path.name:
            assert (out / "model_freeze.json").is_file()
        return original(path)
    monkeypatch.setattr(cli, "_load", spy)
    assert cli.main(args) == 0
    content = (out / "report.json").read_bytes()
    assert len(reads) == 2
    assert cli.main(args) == 2
    assert (out / "report.json").read_bytes() == content


def test_cli_no_market_is_valid_and_missing_market_keeps_freeze(tmp_path):
    cli = _cli()
    args = ["--model", str(ROOT / "examples/independent_model.json"), "--as-of", NOW.isoformat()]
    out = tmp_path / "alone"
    assert cli.main(args + ["--output-dir", str(out)]) == 0
    assert json.loads((out / "report.json").read_text())["market"] is None
    failed = tmp_path / "missing"
    assert cli.main(args + ["--output-dir", str(failed), "--quotes", str(tmp_path / "absent.json"), "--max-quote-age-min", "90"]) == 2
    assert (failed / "model_freeze.json").is_file()


def test_no_postgame_or_prefreeze_comparison(spec, quotes):
    model = freeze_model(spec, now=NOW)
    for now in (NOW - timedelta(seconds=1), timestamp(spec["event"]["starts_at"])):
        with pytest.raises(ValueError): compare_quotes(model, quotes, now=now, max_age_minutes=90)
