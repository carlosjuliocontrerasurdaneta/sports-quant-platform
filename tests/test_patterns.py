"""Performance-pattern analysis: hit-rate math, frequency leaders, breakdowns."""
import pandas as pd

from sqp.audit import patterns
from sqp.audit.patterns import (conclusions, hit_rate, load_pick_history,
                                pattern_breakdowns)


def _history() -> pd.DataFrame:
    """Synthetic graded history: handicap-away is the best & most frequent ML
    side is home; totals lean Over; one push must be excluded from rates."""
    rows = [
        # moneyline: home picked 3x (2 win), away 1x (1 win)
        ("h2h", "home", "A", "win"), ("h2h", "home", "A", "win"),
        ("h2h", "home", "B", "loss"), ("h2h", "away", "C", "win"),
        # handicap: away picked 2x (2 win) -> best situation; home 1x loss
        ("spreads", "away", "A", "win"), ("spreads", "away", "C", "win"),
        ("spreads", "home", "B", "loss"),
        # totals: Over 3x (1 win), Under 1x (1 win), plus a push (excluded)
        ("totals", "Over", "", "win"), ("totals", "Over", "", "loss"),
        ("totals", "Over", "", "loss"), ("totals", "Under", "", "win"),
        ("totals", "Over", "", "push"),
    ]
    return pd.DataFrame(
        [{"league": "x", "date": "2026-01-01", "market": m, "side": s,
          "selection": sel, "result": r, "stake": 1.0,
          "pnl": (0.9 if r == "win" else (-1.0 if r == "loss" else 0.0)),
          "estimated_edge": 0.05, "estimated_probability": 0.55}
         for m, s, sel, r in rows])


def test_hit_rate_excludes_push_and_counts_frequency():
    h = hit_rate(_history(), ["market"])
    totals = h[h["market"] == "totals"].iloc[0]
    # 4 graded totals (3 Over + 1 Under); the push is excluded from n
    assert totals["n"] == 4
    assert totals["wins"] == 2
    assert totals["hit_rate_%"] == 50.0


def test_pattern_breakdowns_keys_and_situation_threshold(monkeypatch):
    # lower the situational/team minimums so the tiny fixture surfaces rows
    monkeypatch.setattr(patterns, "MIN_N_SITUATION", 1)
    breaks = pattern_breakdowns(_history())
    assert set(breaks) >= {"by_market", "by_situation", "moneyline_side",
                           "handicap_side", "totals_side", "team_top", "team_bottom"}
    # best situation by hit rate is handicap/away (2/2 = 100%)
    top_sit = breaks["by_situation"].iloc[0]
    assert (top_sit["market_label"], top_sit["side"]) == ("handicap", "away")
    assert top_sit["hit_rate_%"] == 100.0


def test_moneyline_frequency_leans_home():
    breaks = pattern_breakdowns(_history())
    ml = breaks["moneyline_side"].set_index("side")
    # home is picked more often than away (frequency = n)
    assert ml.loc["home", "n"] == 3
    assert ml.loc["away", "n"] == 1


def test_totals_frequency_leans_over():
    breaks = pattern_breakdowns(_history())
    to = breaks["totals_side"].set_index("side")
    assert to.loc["Over", "n"] == 3   # push excluded
    assert to.loc["Under", "n"] == 1


def test_conclusions_mention_frequency_sides():
    text = " ".join(conclusions(pattern_breakdowns(_history())))
    assert "Moneyline" in text and "home" in text
    assert "Totales" in text and "Over" in text


def test_conclusions_empty_is_safe():
    assert conclusions({}) == ["Sin historial suficiente para concluir patrones todavia."]


def test_load_pick_history_missing_is_empty(tmp_path):
    df = load_pick_history(tmp_path / "nope.csv")
    assert df.empty
    assert list(df.columns) == patterns.HISTORY_COLS
