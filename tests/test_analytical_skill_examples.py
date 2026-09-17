"""Execute the documented calculations against independent numerical expectations."""
from pathlib import Path
import re
import textwrap
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude/skills/sports-analytical-system/SKILL.md"


def _example(section: str) -> str:
    text = SKILL.read_text(encoding="utf-8").split(section, 1)[1]
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    assert match is not None, "Missing executable documentation example"
    return textwrap.dedent(match[1])


@pytest.mark.parametrize("probability,price,expected", [
    (0.97, 1.10, 20.0),  # Without the cap the example recommends 53.60.
    (0.625, 2.0, 20.0),  # Exactly at the cap.
    (0.55, 2.0, 8.0),
    (0.505, 2.0, 0.0),  # Positive EV but below min_edge.
    (0.54, 1.8, 0.0),
    (float("nan"), 2.0, 0.0),
])
def test_documented_stake_respects_effective_risk(probability, price, expected):
    cfg = yaml.safe_load((ROOT / "configs/default.yaml").read_text(encoding="utf-8"))
    namespace = dict(p_estimada=probability, cuota_decimal=price, bankroll=1000,
                     risk=SimpleNamespace(**cfg["risk"]))
    exec(_example("### Fase 5"), namespace)
    assert namespace["stake_recomendado"] == pytest.approx(expected)


def test_documented_stake_passes_overridden_limits():
    namespace = dict(p_estimada=0.97, cuota_decimal=1.10, bankroll=1000,
                     risk=SimpleNamespace(kelly_fraction=0.04,
                                          max_stake_pct=0.01, min_edge=0.02))
    exec(_example("### Fase 5"), namespace)
    assert namespace["stake_recomendado"] == 10.0


@pytest.mark.parametrize("odd_a,odd_b", [(2.1, 2.1), (1.8, 2.5), (2.0, 2.0)])
def test_documented_arbitrage_percentage_matches_both_payouts(odd_a, odd_b):
    namespace = dict(odd_A=odd_a, odd_B=odd_b, bankroll=100)
    exec(_example("## Reglas de Arbitraje"), namespace)
    a, b = namespace["stake_A"], namespace["stake_B"]
    assert a + b == pytest.approx(100)
    assert a * odd_a == pytest.approx(b * odd_b)
    for payout in (a * odd_a, b * odd_b):
        assert namespace["arb_pct"] == pytest.approx((payout - 100) / 100 * 100)
