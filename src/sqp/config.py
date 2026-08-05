"""Configuration: environment + YAML. No secrets are ever hardcoded."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"

# Ruta explicita: load_dotenv() sin argumento busca desde el CWD, asi que una
# invocacion fuera de la raiz del repo podia cargar otro .env o ninguno
# (auditoria 2026-07-24, M-4).
load_dotenv(ROOT / ".env")


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_TRUE = ("1", "true", "yes", "on")
_FALSE = ("0", "false", "no", "off")


def _env_flag(name: str) -> bool | None:
    """Tri-state boolean environment flag: True / False / None (not configured).

    The previous idiom was ``os.getenv(NAME, "").lower() in ("1","true","yes")``
    paired with ``if NAME not in os.environ`` to decide whether the yaml wins.
    That combination FAILS OPEN: a variable that exists but is not recognized
    (``SHADOW_MODE=``, ``SHADOW_MODE=on``, a trailing space) suppressed the yaml
    branch AND evaluated to False, so ``shadow_mode: true`` in default.yaml was
    silently ignored and stakes would have gone live (audit 2026-07-29, B-08).

    An unrecognized value now returns None -- indistinguishable from unset -- so
    the yaml keeps control, and the anomaly is logged instead of swallowed.
    """
    raw = os.environ.get(name)
    if raw is None:
        return None
    v = raw.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    from sqp.logging_config import get_logger
    get_logger("sqp.config").warning(
        "Valor no reconocido para %s (se ignora y manda la configuracion yaml).", name)
    return None


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
    # repr=False: sin esto un futuro log.info(f"{settings}") volcaria la clave a
    # logs/sqp.log (auditoria 2026-07-29, S-13). Hoy nadie loguea el objeto
    # completo; el campo queda excluido del repr por defensa en profundidad.
    odds_api_key: str | None = field(
        default_factory=lambda: os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY"),
        repr=False)
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
        default_factory=lambda: _env_flag("BANKROLL_DYNAMIC") is True)
    # Only estimate events commencing within this many days. The Odds API posts
    # next-season opener lines months early (e.g. NFL Week 1 in June); without a
    # horizon those flood the picks with games that won't play for weeks.
    event_horizon_days: int = field(default_factory=lambda: int(os.getenv("MAX_EVENT_HORIZON_DAYS", "7")))
    risk: RiskConfig = field(default_factory=RiskConfig)
    # Modo de seleccion de picks (decision 2026-07-27: el objetivo del proyecto
    # es maximizar el porcentaje de aciertos). "edge": seleccion clasica por
    # valor esperado (Kelly sobre min_edge). "accuracy": seleccion por
    # probabilidad de decision calibrada (blend modelo + no-vig) >= umbral,
    # SOLO moneyline, stake plano. Default "edge": Settings() directo
    # (tests/demo) queda byte-identico; produccion activa accuracy via yaml.
    pick_mode: str = field(default_factory=lambda: os.getenv("PICK_MODE", "edge"))
    accuracy_threshold: float = field(
        default_factory=lambda: float(os.getenv("ACCURACY_THRESHOLD", "0.70")))
    # Shadow mode: the pipeline selects picks exactly as in real mode (selection
    # still requires a would-be-staked candidate) but records every pick with
    # stake 0, flagged "shadow_mode". Evidence (settlement, CLV vs closing,
    # calibration training) keeps accruing without risking capital. Unlike
    # paused_markets this is global, so it also covers leagues discovered
    # dynamically. Env var SHADOW_MODE (when set) wins over the yaml key.
    shadow_mode: bool = field(
        default_factory=lambda: _env_flag("SHADOW_MODE") is True)
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
        default_factory=lambda: _env_flag("CALIBRATION_ENABLED") is True)
    calibration_method: str = field(
        default_factory=lambda: os.getenv("CALIBRATION_METHOD", "isotonic"))
    # Auto-correction (2026-07-08): after the daily staging retrain, promote
    # into the LIVE registry the candidates that passed the OOS gates (ECE +
    # Brier + monotonicity) with enough independent validation events, and
    # demote what the retrain no longer recommends. OFF by default: with the flag unset the
    # promotion stays a deliberate human step (scripts/promote_calibration.py).
    calibration_auto_promote: bool = field(
        default_factory=lambda: _env_flag("CALIBRATION_AUTO_PROMOTE") is True)
    # CLV gate (2026-07-08): per-(league, market) ALLOW-LIST for real staking.
    # A market may carry stake only if its median CLV over >= clv_gate_min_n
    # settled bets matched to a captured close is positive, per the registry
    # data/bets/clv_gate.json rewritten by the daily CLV audit. Default-deny
    # (no registry / no entry / thin sample -> stake 0, flag "clv_gate");
    # layered UNDER shadow_mode, so it becomes the binding per-market exit
    # rule when shadow mode is lifted. OFF by default so direct Settings()
    # (tests/demo) is unaffected; production enables it via yaml.
    clv_gate_enabled: bool = field(
        default_factory=lambda: _env_flag("CLV_GATE_ENABLED") is True)
    clv_gate_min_n: int = field(
        default_factory=lambda: int(os.getenv("CLV_GATE_MIN_N", "30")))
    # Monitor de degradacion por (liga, mercado) (2026-07-13): auto-pausa gated.
    # Sobre la ventana movil de liquidadas, pausa un mercado cuyo Brier estimado
    # es peor que el baseline del mercado (prob. implicita sin vig) por mas de
    # brier_margin, o cuyo ROI a stake plano cae bajo roi_pause; reanuda solo
    # con histeresis (Brier <= mercado Y roi >= roi_resume). Solo pausa (flag
    # "market_paused" via paused_markets); nunca sube stakes. OFF por defecto
    # para Settings() directo (tests/demo); produccion lo activa via yaml.
    degradation_enabled: bool = field(
        default_factory=lambda: _env_flag("DEGRADATION_ENABLED") is True)
    degradation_window_days: int = field(
        default_factory=lambda: int(os.getenv("DEGRADATION_WINDOW_DAYS", "60")))
    degradation_min_n: int = field(
        default_factory=lambda: int(os.getenv("DEGRADATION_MIN_N", "30")))
    degradation_brier_margin: float = field(
        default_factory=lambda: float(os.getenv("DEGRADATION_BRIER_MARGIN", "0.01")))
    degradation_roi_pause: float = field(
        default_factory=lambda: float(os.getenv("DEGRADATION_ROI_PAUSE", "-0.15")))
    degradation_roi_resume: float = field(
        default_factory=lambda: float(os.getenv("DEGRADATION_ROI_RESUME", "-0.05")))
    # Segundo pase pre-partido (2026-07-14): tras cada captura de cierre
    # horaria, re-valida el edge de los picks del dia con evento inminente
    # contra el consenso vigente y revoca (stake 0, flag stale_edge_revoked)
    # los que ya no se generarian (edge < min_edge al precio actual). Solo
    # baja stakes; sin snapshot fresco no actua. OFF por defecto para
    # Settings() directo (tests/demo); produccion lo activa via yaml.
    revalidation_enabled: bool = field(
        default_factory=lambda: _env_flag("REVALIDATION_ENABLED") is True)
    revalidation_window_min: int = field(
        default_factory=lambda: int(os.getenv("REVALIDATION_WINDOW_MIN", "120")))
    revalidation_price_max_age_min: float = field(
        default_factory=lambda: float(
            os.getenv("REVALIDATION_PRICE_MAX_AGE_MIN", "90")))
    # Observatorio de edge intradia (2026-07-14): tras cada captura loguea el
    # edge h2h de las probabilidades servidas a las 11:00 contra el consenso
    # vigente (medicion pura: nunca crea picks ni toca stakes). El dataset
    # decide la fase ofensiva de generacion intradia. OFF por defecto para
    # Settings() directo (tests/demo); produccion lo activa via yaml.
    intraday_scan_enabled: bool = field(
        default_factory=lambda: _env_flag("INTRADAY_SCAN_ENABLED") is True)

    def validate(self) -> "Settings":
        """Fail fast on unsafe or internally inconsistent operator settings."""
        if self.mode not in ("demo", "live"):
            raise ValueError(f"SQP_MODE must be 'demo' or 'live', got {self.mode!r}")
        if self.bankroll <= 0:
            raise ValueError("BANKROLL must be > 0")
        bounded = {
            "KELLY_FRACTION": self.risk.kelly_fraction,
            "MAX_STAKE_PCT": self.risk.max_stake_pct,
            "MAX_DAILY_EXPOSURE_PCT": self.risk.max_daily_exposure_pct,
            "MAX_TOTAL_EXPOSURE_PCT": self.risk.max_total_exposure_pct,
            "MARKET_SHRINK": self.risk.market_shrink,
        }
        for name, value in bounded.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1, got {value}")
        nonnegative = {
            "MIN_EDGE": self.risk.min_edge,
            "MAX_PLAUSIBLE_EDGE": self.risk.max_plausible_edge,
            "UNCERTAINTY_PENALTY": self.risk.uncertainty_penalty,
            "ANOMALY_EDGE_GAP": self.risk.anomaly_edge_gap,
            "ANOMALY_EXTRA_PENALTY": self.risk.anomaly_extra_penalty,
            "LOW_BOOK_PENALTY": self.risk.low_book_penalty,
        }
        for name, value in nonnegative.items():
            if value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")
        if self.risk.max_plausible_edge < self.risk.min_edge:
            raise ValueError("MAX_PLAUSIBLE_EDGE must be >= MIN_EDGE")
        if self.risk.min_books_for_consensus < 0:
            raise ValueError("MIN_BOOKS_FOR_CONSENSUS must be >= 0")
        if self.event_horizon_days < 0:
            raise ValueError("MAX_EVENT_HORIZON_DAYS must be >= 0")
        if self.clv_gate_min_n < 1:
            raise ValueError("CLV_GATE_MIN_N must be >= 1")
        if self.degradation_window_days < 1:
            raise ValueError("DEGRADATION_WINDOW_DAYS must be >= 1")
        if self.degradation_min_n < 1:
            raise ValueError("DEGRADATION_MIN_N must be >= 1")
        if self.degradation_brier_margin < 0:
            raise ValueError("DEGRADATION_BRIER_MARGIN must be >= 0")
        if self.degradation_roi_resume < self.degradation_roi_pause:
            raise ValueError("DEGRADATION_ROI_RESUME must be >= "
                             "DEGRADATION_ROI_PAUSE (hysteresis)")
        if self.revalidation_window_min < 1:
            raise ValueError("REVALIDATION_WINDOW_MIN must be >= 1")
        if self.revalidation_price_max_age_min <= 0:
            raise ValueError("REVALIDATION_PRICE_MAX_AGE_MIN must be > 0")
        if self.calibration_method not in ("isotonic", "beta", "auto"):
            raise ValueError(
                "CALIBRATION_METHOD must be isotonic, beta or auto")
        if self.pick_mode not in ("edge", "accuracy"):
            raise ValueError(
                f"PICK_MODE must be 'edge' or 'accuracy', got {self.pick_mode!r}")
        if not 0.5 <= self.accuracy_threshold < 1.0:
            # < 0.5 seleccionaria perdedores esperados; 1.0 afirmaria certeza,
            # prohibido por las reglas de lenguaje del proyecto.
            raise ValueError("ACCURACY_THRESHOLD must be in [0.5, 1.0), got "
                             f"{self.accuracy_threshold}")
        return self

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        cfg_path = CONFIG_DIR / "default.yaml"
        if not cfg_path.exists():
            # Fail fast, never fail open. The whole risk stack lives ONLY in this
            # file: shadow_mode, the CLV gate and the degradation monitor all
            # default to False on the dataclass and max_plausible_edge defaults to
            # 0.15 (twice the shipped 0.075). Skipping a missing file silently
            # turned `shadow_mode: true` into real stakes with no control layer and
            # no warning -- the same fail-open class as B-08 (audit 2026-07-29),
            # here on the file path instead of the env flags.
            raise FileNotFoundError(
                f"Config no encontrado: {cfg_path}. Sin el, todo el stack de riesgo "
                "(shadow_mode, gate de CLV, pausas, max_plausible_edge) caeria a "
                "defaults inseguros en silencio.")
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
        if _env_flag("SHADOW_MODE") is None and "shadow_mode" in cfg:
            s.shadow_mode = bool(cfg["shadow_mode"])
        cal = cfg.get("calibration") or {}
        # env var (if set) wins over yaml; otherwise yaml, else the dataclass default
        if _env_flag("CALIBRATION_ENABLED") is None and "enabled" in cal:
            s.calibration_enabled = bool(cal["enabled"])
        if "CALIBRATION_METHOD" not in os.environ and cal.get("method"):
            s.calibration_method = str(cal["method"])
        if _env_flag("CALIBRATION_AUTO_PROMOTE") is None and "auto_promote" in cal:
            s.calibration_auto_promote = bool(cal["auto_promote"])
        cg = cfg.get("clv_gate") or {}
        if _env_flag("CLV_GATE_ENABLED") is None and "enabled" in cg:
            s.clv_gate_enabled = bool(cg["enabled"])
        if "CLV_GATE_MIN_N" not in os.environ and "min_n" in cg:
            s.clv_gate_min_n = int(cg["min_n"])
        dm = cfg.get("degradation_monitor") or {}
        if _env_flag("DEGRADATION_ENABLED") is None and "enabled" in dm:
            s.degradation_enabled = bool(dm["enabled"])
        if "DEGRADATION_WINDOW_DAYS" not in os.environ and "window_days" in dm:
            s.degradation_window_days = int(dm["window_days"])
        if "DEGRADATION_MIN_N" not in os.environ and "min_n" in dm:
            s.degradation_min_n = int(dm["min_n"])
        if "DEGRADATION_BRIER_MARGIN" not in os.environ and "brier_margin" in dm:
            s.degradation_brier_margin = float(dm["brier_margin"])
        if "DEGRADATION_ROI_PAUSE" not in os.environ and "roi_pause" in dm:
            s.degradation_roi_pause = float(dm["roi_pause"])
        if "DEGRADATION_ROI_RESUME" not in os.environ and "roi_resume" in dm:
            s.degradation_roi_resume = float(dm["roi_resume"])
        rv = cfg.get("revalidation") or {}
        if _env_flag("REVALIDATION_ENABLED") is None and "enabled" in rv:
            s.revalidation_enabled = bool(rv["enabled"])
        if "REVALIDATION_WINDOW_MIN" not in os.environ and "window_min" in rv:
            s.revalidation_window_min = int(rv["window_min"])
        if ("REVALIDATION_PRICE_MAX_AGE_MIN" not in os.environ
                and "price_max_age_min" in rv):
            s.revalidation_price_max_age_min = float(rv["price_max_age_min"])
        pk = cfg.get("picks") or {}
        if "PICK_MODE" not in os.environ and "mode" in pk:
            s.pick_mode = str(pk["mode"])
        if "ACCURACY_THRESHOLD" not in os.environ and "accuracy_threshold" in pk:
            s.accuracy_threshold = float(pk["accuracy_threshold"])
        isc = cfg.get("intraday_scan") or {}
        if _env_flag("INTRADAY_SCAN_ENABLED") is None and "enabled" in isc:
            s.intraday_scan_enabled = bool(isc["enabled"])
        bk = cfg.get("bankroll") or {}
        if not os.getenv("BANKROLL") and "initial" in bk:
            s.bankroll = float(bk["initial"])
        if _env_flag("BANKROLL_DYNAMIC") is None and "dynamic" in bk:
            s.bankroll_dynamic = bool(bk["dynamic"])
        return s.validate()
