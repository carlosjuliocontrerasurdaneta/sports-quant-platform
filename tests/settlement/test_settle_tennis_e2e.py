"""End-to-end tennis settlement (KI-017): candidates + predictions on disk,
ESPN provider mocked, through _settle_tennis to the persisted settled CSV.

The unit pieces (tennis_scores_map, _grade, _persist_settled) have their own
tests; this guards the FLOW they form: recover players/date from
predictions_<league>.csv, match ESPN results by normalized name + date window,
grade home/away sides, attach event meta, persist idempotently.
"""
import pandas as pd

from sqp.settlement import runner
from sqp.settlement.runner import _settle_tennis

LEAGUE = "atp_wimbledon"


class FakeESPN:
    """Stands in for ESPNTennisResultsProvider; returns canned results with
    accented spellings that diverge from The Odds API names on purpose."""
    def __init__(self, results):
        self.results = results
        self.calls = 0

    def fetch_results(self, league, days_back=5):
        self.calls += 1
        return self.results


def _write_inputs(root):
    pred_dir = root / "data" / "predictions"
    pred_dir.mkdir(parents=True)
    pd.DataFrame([
        # e1: bet on home (Alcaraz), who won -> win.
        {"event_id": "e1", "league": LEAGUE, "market": "h2h",
         "selection": "Carlos Alcaraz", "line": float("nan"),
         "price_decimal": 1.80, "stake": 10.0, "data_label": "real",
         "generated_at": "2026-07-06T10:00:00+00:00"},
        # e2: bet on away (Musetti); home (Djokovic) won -> loss.
        {"event_id": "e2", "league": LEAGUE, "market": "h2h",
         "selection": "Lorenzo Musetti", "line": float("nan"),
         "price_decimal": 3.10, "stake": 5.0, "data_label": "real",
         "generated_at": "2026-07-06T10:00:00+00:00"},
        # e3: no ESPN result within the +/-1 day window -> stays pending.
        {"event_id": "e3", "league": LEAGUE, "market": "h2h",
         "selection": "Jannik Sinner", "line": float("nan"),
         "price_decimal": 1.50, "stake": 8.0, "data_label": "real",
         "generated_at": "2026-07-06T10:00:00+00:00"},
    ]).to_csv(pred_dir / f"candidates_{LEAGUE}.csv", index=False)
    pd.DataFrame([
        {"event_id": "e1", "home": "Carlos Alcaraz", "away": "Novak Djokovic",
         "start_time": "2026-07-06T13:00:00Z"},
        {"event_id": "e2", "home": "Novak Djokovic", "away": "Lorenzo Musetti",
         "start_time": "2026-07-07T15:00:00Z"},
        {"event_id": "e3", "home": "Jannik Sinner", "away": "Taylor Fritz",
         "start_time": "2026-07-07T17:00:00Z"},
    ]).to_csv(pred_dir / f"predictions_{LEAGUE}.csv", index=False)


def _results():
    return [
        # Accent/order divergences vs the Odds API spellings above.
        {"home": "Novak Djokovic", "away": "Carlos Alcaraz",
         "winner": "Carlos Alcaraz", "date": "2026-07-06"},
        {"home": "Novak Djokovic", "away": "Lorenzo Musetti",
         "winner": "Novak Djokovic", "date": "2026-07-07"},
        # Sinner result exists but 5 days off -> outside the date window.
        {"home": "Jannik Sinner", "away": "Taylor Fritz",
         "winner": "Jannik Sinner", "date": "2026-07-02"},
    ]


def test_settle_tennis_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write_inputs(tmp_path)
    settled = _settle_tennis(LEAGUE, days_from=2, provider=FakeESPN(_results()))

    # e1 win / e2 loss graded with correct PnL; e3 pending (date window).
    assert set(settled["event_id"]) == {"e1", "e2"}
    by_id = settled.set_index("event_id")
    assert by_id.loc["e1", "result"] == "win"
    assert by_id.loc["e1", "pnl"] == 8.0        # 10 * (1.80 - 1)
    assert by_id.loc["e2", "result"] == "loss"
    assert by_id.loc["e2", "pnl"] == -5.0
    # Event meta recovered from predictions_<league>.csv.
    assert by_id.loc["e1", "home"] == "Carlos Alcaraz"
    assert by_id.loc["e1", "away"] == "Novak Djokovic"
    assert by_id.loc["e2", "game_date"] == "2026-07-07"

    # Persisted to the settled CSV feeding audit/bankroll/calibration.
    out = tmp_path / "data" / "bets" / f"settled_{LEAGUE}.csv"
    assert out.exists()
    assert len(pd.read_csv(out)) == 2


def test_settle_tennis_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write_inputs(tmp_path)
    first = _settle_tennis(LEAGUE, days_from=2, provider=FakeESPN(_results()))
    again = _settle_tennis(LEAGUE, days_from=2, provider=FakeESPN(_results()))
    assert len(first) == 2
    assert again.empty  # dedup: nothing newly settled
    out = tmp_path / "data" / "bets" / f"settled_{LEAGUE}.csv"
    assert len(pd.read_csv(out)) == 2  # no duplicate rows appended


def test_settle_tennis_missing_predictions_skips_safely(tmp_path, monkeypatch):
    # Candidates without their predictions file (players/date unrecoverable)
    # must skip with a warning, not crash or grade blindly.
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write_inputs(tmp_path)
    (tmp_path / "data" / "predictions" / f"predictions_{LEAGUE}.csv").unlink()
    settled = _settle_tennis(LEAGUE, days_from=2, provider=FakeESPN(_results()))
    assert settled.empty
    assert not (tmp_path / "data" / "bets" / f"settled_{LEAGUE}.csv").exists()


def test_settle_tennis_provider_failure_is_nonfatal(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    _write_inputs(tmp_path)

    class Exploding:
        def fetch_results(self, league, days_back=5):
            raise ConnectionError("ESPN down")

    settled = _settle_tennis(LEAGUE, days_from=2, provider=Exploding())
    assert settled.empty
    assert not (tmp_path / "data" / "bets" / f"settled_{LEAGUE}.csv").exists()
