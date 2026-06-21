"""Configuration: environment + YAML. No secrets are ever hardcoded."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # pragma: no cover - dotenv optional at runtime
    pass

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass
class RiskConfig:
    kelly_fraction: float = 0.25
    min_edge: float = 0.02
    max_stake_pct: float = 0.02
    max_daily_exposure_pct: float = 0.10
    # Edges above this are almost certainly model miscalibration, not market
    # value: such selections are flagged and not staked (see audit 2026-06).
    max_plausible_edge: float = 0.15
    # Shrink model probabilities toward the no-vig market before computing edge:
    # p = (1-s)*p_model + s*p_market. The model is overconfident on tails (runline
    # +1.5 overestimated ~5pts) and has no proven edge, so 0 < s anchors it to the
    # market. 0 = pure model, 1 = pure market. See audit 2026-06.
    market_shrink: float = 0.5


@dataclass
class Settings:
    mode: str = field(default_factory=lambda: os.getenv("SQP_MODE", "demo"))
    # Accept THE_ODDS_API_KEY too: that is The Odds API's own env-var name and
    # the one used in this project's .env. ODDS_API_KEY (e.g. a stale OS-level
    # var) still wins when set, for backward compatibility.
    odds_api_key: str | None = field(
        default_factory=lambda: os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY"))
    regions: str = field(default_factory=lambda: os.getenv("ODDS_API_REGIONS", "us,eu"))
    odds_format: str = field(default_factory=lambda: os.getenv("ODDS_API_ODDS_FORMAT", "decimal"))
    bankroll: float = field(default_factory=lambda: float(os.getenv("BANKROLL", "1000")))
    # Only estimate events commencing within this many days. The Odds API posts
    # next-season opener lines months early (e.g. NFL Week 1 in June); without a
    # horizon those flood the picks with games that won't play for weeks.
    event_horizon_days: int = field(default_factory=lambda: int(os.getenv("MAX_EVENT_HORIZON_DAYS", "7")))
    risk: RiskConfig = field(default_factory=RiskConfig)
    # league_id -> markets paused from staking (e.g. {"mlb": ["totals"]}). A paused
    # market is still estimated, but candidates are recorded flagged "market_paused"
    # with stake 0 instead of being bet. Used to suspend a market whose realized ROI
    # contradicts its estimated edge until more settled sample accrues (audit 2026-06).
    paused_markets: dict[str, list[str]] = field(default_factory=dict)
    # Apply a trained per-(league, market) calibrator to the (shrunk) estimated
    # probability before computing edge and stake. OFF by default: with no flag
    # and no persisted model the pipeline is byte-identical to the uncalibrated
    # run. Train models with scripts/train_calibration.py. The estimated
    # probability stored for retraining stays UNCALIBRATED, so enabling this can
    # never create a calibrate-on-already-calibrated feedback loop.
    calibration_enabled: bool = field(
        default_factory=lambda: os.getenv("CALIBRATION_ENABLED", "").lower()
        in ("1", "true", "yes"))
    calibration_method: str = field(
        default_factory=lambda: os.getenv("CALIBRATION_METHOD", "isotonic"))

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        cfg_path = CONFIG_DIR / "default.yaml"
        if cfg_path.exists():
            cfg = load_yaml(cfg_path)
            r = cfg.get("risk", {})
            s.risk = RiskConfig(
                kelly_fraction=float(os.getenv("KELLY_FRACTION", r.get("kelly_fraction", 0.25))),
                min_edge=float(os.getenv("MIN_EDGE", r.get("min_edge", 0.02))),
                max_stake_pct=float(os.getenv("MAX_STAKE_PCT", r.get("max_stake_pct", 0.02))),
                max_daily_exposure_pct=float(r.get("max_daily_exposure_pct", 0.10)),
                max_plausible_edge=float(os.getenv("MAX_PLAUSIBLE_EDGE",
                                                   r.get("max_plausible_edge", 0.15))),
                market_shrink=float(os.getenv("MARKET_SHRINK",
                                              r.get("market_shrink", 0.5))),
            )
            s.paused_markets = {str(lg): [str(m) for m in (mk or [])]
                                for lg, mk in (cfg.get("paused_markets") or {}).items()}
            cal = cfg.get("calibration") or {}
            # env var (if set) wins over yaml; otherwise yaml, else the dataclass default
            if "CALIBRATION_ENABLED" not in os.environ and "enabled" in cal:
                s.calibration_enabled = bool(cal["enabled"])
            if "CALIBRATION_METHOD" not in os.environ and cal.get("method"):
                s.calibration_method = str(cal["method"])
        return s
