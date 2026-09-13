"""Domain entities. All probabilities are *estimated probabilities*."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Event:
    event_id: str
    sport_key: str            # The Odds API sport key (e.g. basketball_nba)
    league: str               # internal league id (e.g. nba, epl)
    home: str
    away: str
    start_time: str           # ISO-8601 UTC
    data_label: str = "real"  # "real" | "demo_synthetic"
    home_pitcher: str | None = None  # baseball: probable/confirmed starter
    away_pitcher: str | None = None


@dataclass
class MarketLine:
    market: str               # h2h | spreads | totals
    bookmaker: str
    outcome: str              # team name | Draw | Over | Under
    price_decimal: float
    point: float | None = None  # spread or total line


@dataclass
class EventOdds:
    event: Event
    lines: list[MarketLine] = field(default_factory=list)


@dataclass
class EstimatedProbabilities:
    """Model output. Keys follow the simulation contract."""
    home_win_estimated_probability: float
    away_win_estimated_probability: float
    draw_estimated_probability: float | None = None  # soccer 3-way
    home_cover_estimated_probability: float | None = None
    away_cover_estimated_probability: float | None = None
    over_estimated_probability: float | None = None
    under_estimated_probability: float | None = None
    spread_line: float | None = None  # home handicap (negative = home favorite)
    total_line: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class BetCandidate:
    event_id: str
    league: str
    market: str
    selection: str
    line: float | None
    price_decimal: float
    bookmaker: str
    estimated_probability: float  # probability actually used (after market shrink)
    implied_probability_novig: float
    estimated_edge: float
    kelly_stake_pct: float
    stake: float
    data_label: str
    # Identidad de los dos equipos del evento. Existe por una razon de
    # LIQUIDACION, no de informe (AUD-MED-001, auditoria integral 2026-09-10):
    # `settle._grade` tiene una guarda que devuelve "void" cuando la seleccion no
    # casa con NINGUNO de los dos equipos -- la defensa contra FABRICAR un
    # resultado --, pero esa guarda solo actua `if row.get("away")`. Los picks se
    # escribian desde `BetCandidate.__dict__`, que no traia `away`, asi que la
    # guarda estaba INERTE justo en la ruta del dinero, mientras SI actuaba en el
    # stream servido (stake 0) y en el backtest de ROI. Reproducido: con el local
    # ganando 1-0 y la seleccion escrita de otra forma, el grading daba
    # `loss / pnl -20`; con la columna presente, `void / 0`.
    #
    # Default "" para compatibilidad hacia atras: un `candidates_*.csv` antiguo
    # sin estas columnas se sigue leyendo, y la guarda se comporta como antes
    # (se salta) en vez de romper la liquidacion del historico.
    home: str = ""
    away: str = ""
    model_probability: float = float("nan")  # raw model prob before market shrink
    # Probability actually used for edge/stake when calibration is enabled. Equals
    # estimated_probability when calibration is off or no model exists. The
    # uncalibrated estimated_probability remains the calibrator's training target.
    calibrated_probability: float = float("nan")
    # Edge after the uncertainty/thin-market penalty (sqp.markets.edge). The stake
    # is sized on this; estimated_edge stays the RAW edge for audit. Equals
    # estimated_edge when the penalty is off. edge_penalty is the EV deducted;
    # books_count is how many bookmakers quoted the staked line.
    adjusted_edge: float = float("nan")
    edge_penalty: float = 0.0
    books_count: int = 0
    flags: str = ""  # e.g. "edge_exceeds_max_plausible": flagged, not staked
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
