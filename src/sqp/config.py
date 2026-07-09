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
    # Global (cross-league) daily exposure cap. `max_daily_exposure_pct` is applied
    # PER LEAGUE inside run_league, so a multi-league day could commit up to
    # N x that fraction. This caps the whole day's staked exposure across every
    # league at `bankroll * max_total_exposure_pct`, enforced once after all
    # leagues run (see daily.apply_global_exposure_cap / run_all). 0 disables it.
    max_total_exposure_pct: float = 0.10
    # Edges above this are almost certainly model miscalibration, not market
    # value: such selections are flagged and not staked (see audit 2026-06).
    max_plausible_edge: float = 0.15
    # Shrink model probabilities toward the no-vig market before computing edge:
    # p = (1-s)*p_model + s*p_market. The model is overconfident on tails (runline
    # +1.5 overestimated ~5pts) and has no proven edge, so 0 < s anchors it to the
    # market. 0 = pure model, 1 = pure market. See audit 2026-06.
    market_shrink: float = 0.5
    # Edge-realism penalty (ported from project 2). Deflate the EV by how far the
    # model strays from the no-vig market: penalty = gap*uncertainty_penalty
    # (+anomaly_extra_penalty if gap>anomaly_edge_gap) (+low_book_penalty if a line
    # has < min_books_for_consensus books). The penalty is folded into the staked
    # probability, so it shrinks the Kelly stake too. Defaults 0 = no-op; the
    # shipped configs/default.yaml activates the recommended values. See
    # sqp.markets.edge and the 2026-06-21 realized-ROI audit (edges overconfident).
    uncertainty_penalty: float = 0.0
    anomaly_edge_gap: float = 0.0
    anomaly_extra_penalty: float = 0.0
    low_book_penalty: float = 0.0
    min_books_for_consensus: int = 0


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
    # When true, the live daily run sizes stakes on the running balance from the
    # bankroll ledger (initial + realized PnL + manual adjustments) instead of the
    # fixed `bankroll` above. OFF by default -> staking is byte-identical to the
    # static behavior. Only the live entrypoint (scripts/run_all.py) applies it;
    # demo and direct run_league calls keep the static initial. See
    # sqp.risk.bankroll.
    bankroll_dynamic: bool = field(
        default_factory=lambda: os.getenv("BANKROLL_DYNAMIC", "").lower()
        in ("1", "true", "yes"))
    # Only estimate events commencing within this many days. The Odds API posts
    # next-season opener lines months early (e.g. NFL Week 1 in June); without a
    # horizon those flood the picks with games that won't play for weeks.
    event_horizon_days: int = field(default_factory=lambda: int(os.getenv("MAX_EVENT_HORIZON_DAYS", "7")))
    risk: RiskConfig = field(default_factory=RiskConfig)
    # Shadow mode: the pipeline selects picks exactly as in real mode (selection
    # still requires a would-be-staked candidate) but records every pick with
    # stake 0, flagged "shadow_mode". Evidence (settlement, CLV vs closing,
    # calibration training) keeps accruing without risking capital. Unlike
    # paused_markets this is global, so it also covers leagues discovered
    # dynamically. Env var SHADOW_MODE (when set) wins over the yaml key.
    shadow_mode: bool = field(
        default_factory=lambda: os.getenv("SHADOW_MODE", "").lower()
        in ("1", "true", "yes"))
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
    # Auto-correction (2026-07-08): after the daily staging retrain, promote
    # into the LIVE registry the candidates that passed the OOS gates (ECE +
    # Brier + monotonicity) with enough validation sample, and demote what the
    # retrain no longer recommends. OFF by default: with the flag unset the
    # promotion stays a deliberate human step (scripts/promote_calibration.py).
    calibration_auto_promote: bool = field(
        default_factory=lambda: os.getenv("CALIBRATION_AUTO_PROMOTE", "").lower()
        in ("1", "true", "yes"))
    # CLV gate (2026-07-08): per-(league, market) ALLOW-LIST for real staking.
    # A market may carry stake only if its median CLV over >= clv_gate_min_n
    # settled bets matched to a captured close is positive, per the registry
    # data/bets/clv_gate.json rewritten by the daily CLV audit. Default-deny
    # (no registry / no entry / thin sample -> stake 0, flag "clv_gate");
    # layered UNDER shadow_mode, so it becomes the binding per-market exit
    # rule when shadow mode is lifted. OFF by default so direct Settings()
    # (tests/demo) is unaffected; production enables it via yaml.
    clv_gate_enabled: bool = field(
        default_factory=lambda: os.getenv("CLV_GATE_ENABLED", "").lower()
        in ("1", "true", "yes"))
    clv_gate_min_n: int = field(
        default_factory=lambda: int(os.getenv("CLV_GATE_MIN_N", "30")))

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
                max_daily_exposure_pct=float(os.getenv("MAX_DAILY_EXPOSURE_PCT",
                                             r.get("max_daily_exposure_pct", 0.10))),
                max_total_exposure_pct=float(os.getenv("MAX_TOTAL_EXPOSURE_PCT",
                                             r.get("max_total_exposure_pct", 0.10))),
                max_plausible_edge=float(os.getenv("MAX_PLAUSIBLE_EDGE",
                                                   r.get("max_plausible_edge", 0.15))),
                market_shrink=float(os.getenv("MARKET_SHRINK",
                                              r.get("market_shrink", 0.5))),
                uncertainty_penalty=float(os.getenv("UNCERTAINTY_PENALTY",
                                          r.get("uncertainty_penalty", 0.0))),
                anomaly_edge_gap=float(r.get("anomaly_edge_gap", 0.0)),
                anomaly_extra_penalty=float(r.get("anomaly_extra_penalty", 0.0)),
                low_book_penalty=float(r.get("low_book_penalty", 0.0)),
                min_books_for_consensus=int(r.get("min_books_for_consensus", 0)),
            )
            s.paused_markets = {str(lg): [str(m) for m in (mk or [])]
                                for lg, mk in (cfg.get("paused_markets") or {}).items()}
            if "SHADOW_MODE" not in os.environ and "shadow_mode" in cfg:
                s.shadow_mode = bool(cfg["shadow_mode"])
            cal = cfg.get("calibration") or {}
            # env var (if set) wins over yaml; otherwise yaml, else the dataclass default
            if "CALIBRATION_ENABLED" not in os.environ and "enabled" in cal:
                s.calibration_enabled = bool(cal["enabled"])
            if "CALIBRATION_METHOD" not in os.environ and cal.get("method"):
                s.calibration_method = str(cal["method"])
            if "CALIBRATION_AUTO_PROMOTE" not in os.environ and "auto_promote" in cal:
                s.calibration_auto_promote = bool(cal["auto_promote"])
            cg = cfg.get("clv_gate") or {}
            if "CLV_GATE_ENABLED" not in os.environ and "enabled" in cg:
                s.clv_gate_enabled = bool(cg["enabled"])
            if "CLV_GATE_MIN_N" not in os.environ and "min_n" in cg:
                s.clv_gate_min_n = int(cg["min_n"])
            bk = cfg.get("bankroll") or {}
            if not os.getenv("BANKROLL") and "initial" in bk:
                s.bankroll = float(bk["initial"])
            if "BANKROLL_DYNAMIC" not in os.environ and "dynamic" in bk:
                s.bankroll_dynamic = bool(bk["dynamic"])
        return s
