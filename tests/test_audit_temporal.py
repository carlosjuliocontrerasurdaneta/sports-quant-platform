"""AUD-001: final scores are unavailable to every prediction on their day."""
import pytest

from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.roi_engine import realized_roi_backtest
from sqp.config import RiskConfig
from sqp.domain.models import Event, EventOdds, MarketLine


@pytest.mark.parametrize("timestamps", [False, True])
def test_daily_batch_excludes_later_results(timestamps):
    early = dict(date="2026-09-01", home="A", away="B", game_id="2",
                 home_score=1, away_score=0, neutral=False)
    # AUD-001: dos resultados de la MISMA pareja el mismo dia (doble jornada) ya no se
    # emparejan, asi que el contaminante juega contra otro rival. "0" se ordena ANTES
    # de "B" (clave fecha, local, visitante): el resultado del mismo dia se recorre
    # antes de predecir `early`, que es justo lo que el lote diario debe aislar. Con
    # un rival posterior ("C") el test pasaba aunque el adaptador observara cada
    # resultado al momento (mutante de la revision Fable, 2026-10-16).
    late = dict(early, game_id="1", home_score=10, away="0")
    if timestamps:
        early["start_time"] = "2026-09-01T10:00:00Z"
        late["start_time"] = "2026-09-01T20:00:00Z"
    odds = {
        "early": EventOdds(Event("early", "bt", "mlb", "A", "B",
                                 "2026-09-01T10:00:00Z", "real"),
                           [MarketLine("h2h", "book", side, 2.0) for side in ("A", "B")])
    }
    risk = RiskConfig(min_edge=0., market_shrink=0., max_plausible_edge=1.)
    roi_probs = []
    calibration = []
    for later in (late, dict(late, home_score=0, away_score=10)):
        roi = realized_roi_backtest([early, later], odds, "mlb", "baseball",
                                    None, risk, 1000, warmup=0)["settled"]
        roi_probs.append(roi.loc[roi.event_id == "early", "estimated_probability"].tolist())
        calibration.append(walk_forward_backtest(
            [later, early], "mlb", "baseball", warmup=0, total_lines=(8.5,)))
    assert roi_probs[0] and roi_probs[0] == roi_probs[1]
    assert calibration[0]["binary_probs"] == calibration[1]["binary_probs"]
    assert calibration[0]["markets"]["totals@8.5"]["probs"] == calibration[1]["markets"]["totals@8.5"]["probs"]
    prior = dict(late, date="2026-08-31")
    control = walk_forward_backtest([prior, early], "mlb", "baseball", warmup=1)
    assert control["binary_probs"][0] != calibration[0]["binary_probs"][0]
