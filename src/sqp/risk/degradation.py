"""Monitor de degradacion por (liga, mercado): auto-pausa gated.

Sobre la ventana movil de apuestas liquidadas (win/loss), un mercado con
muestra suficiente se PAUSA si su probabilidad estimada esta demostrablemente
danando: Brier del modelo peor que el baseline del mercado (probabilidad
implicita sin vig) por mas de un margen, o ROI realizado a stake plano (1
unidad por pick, valido bajo shadow mode donde los stakes reales son 0) por
debajo del umbral. La REANUDACION exige histeresis (Brier de vuelta <= mercado
Y ROI de vuelta sobre el umbral de reanudacion) para no oscilar; con muestra
insuficiente el estado NO cambia (una pausa nunca se levanta por falta de
datos). Politica conservadora: este monitor solo pausa (reusa la semantica de
paused_markets: el mercado se sigue estimando y registrando con stake 0, flag
"market_paused"); nunca sube stakes ni des-pausa lo listado estaticamente en
configs/default.yaml (el consumidor fusiona por union).

Registro en data/bets/degradation_pause.json (reemplazo atomico) y rastro de
transiciones en data/bets/degradation_log.csv. Precedente que automatiza:
mlb_totals pausado a mano 2026-06-14 por ROI realizado negativo con edge
estimado positivo. Sin imports del pipeline (mismo criterio que clv_gate).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from sqp.audit.report import load_all_settled

DEGRADATION_FILENAME = "degradation_pause.json"
DEGRADATION_LOG_FILENAME = "degradation_log.csv"

DEFAULT_WINDOW_DAYS = 60
DEFAULT_MIN_N = 30
DEFAULT_BRIER_MARGIN = 0.01
DEFAULT_ROI_PAUSE = -0.15
DEFAULT_ROI_RESUME = -0.05

_METRIC_COLS = ["league", "market", "n", "brier_model", "brier_market", "roi_flat"]


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(float("nan"), index=df.index)


def _jsonable(value) -> float | None:
    """NaN -> None para que el registro sea JSON estricto."""
    return None if value is None or pd.isna(value) else round(float(value), 4)


def degradation_metrics(settled: pd.DataFrame, *,
                        window_days: int = DEFAULT_WINDOW_DAYS,
                        today: date | None = None) -> pd.DataFrame:
    """Metricas de ventana movil por (league, market) sobre picks graduados
    win/loss: n, brier_model (probabilidad estimada vs resultado), brier_market
    (probabilidad implicita sin vig vs resultado; NaN sin la columna) y
    roi_flat (ROI realizado a stake plano de 1 unidad por pick)."""
    if settled.empty or "result" not in settled.columns:
        return pd.DataFrame(columns=_METRIC_COLS)
    df = settled[settled["result"].isin(["win", "loss"])].copy()
    if df.empty:
        return pd.DataFrame(columns=_METRIC_COLS)
    # Fecha del partido, fallback generated_at; comparacion lexicografica ISO.
    gd = df["game_date"].astype(str) if "game_date" in df.columns else pd.Series("", index=df.index)
    gen = df["generated_at"].astype(str) if "generated_at" in df.columns else pd.Series("", index=df.index)
    fecha = gd.where(gd.str.len() >= 10, gen).str[:10]
    cutoff = ((today or datetime.now(timezone.utc).date())
              - timedelta(days=window_days)).isoformat()
    df = df[fecha >= cutoff]
    if df.empty:
        return pd.DataFrame(columns=_METRIC_COLS)
    y = (df["result"] == "win").astype(float)
    p_model = _num(df, "estimated_probability")
    p_market = _num(df, "implied_probability_novig")
    price = _num(df, "price_decimal")
    df = df.assign(_se_model=(p_model - y) ** 2, _se_market=(p_market - y) ** 2,
                   _pnl_flat=(price - 1.0).where(y > 0, -1.0))
    rows = []
    for (lg, mk), g in df.groupby(["league", "market"]):
        rows.append({
            "league": str(lg), "market": str(mk), "n": int(len(g)),
            "brier_model": float(g["_se_model"].mean()),
            "brier_market": float(g["_se_market"].mean()),
            "roi_flat": float(g["_pnl_flat"].mean()),
        })
    return pd.DataFrame(rows, columns=_METRIC_COLS)


def evaluate_pauses(metrics: pd.DataFrame, previous: dict[str, dict], *,
                    min_n: int = DEFAULT_MIN_N,
                    brier_margin: float = DEFAULT_BRIER_MARGIN,
                    roi_pause: float = DEFAULT_ROI_PAUSE,
                    roi_resume: float = DEFAULT_ROI_RESUME,
                    ) -> tuple[dict[str, dict], list[dict]]:
    """Aplica el gate de pausa/reanudacion con histeresis. Devuelve el mapa
    "liga|mercado" -> entrada de estado y la lista de transiciones del dia.

    - PAUSAR (n >= min_n): brier_model > brier_market + brier_margin, o
      roi_flat < roi_pause.
    - REANUDAR (n >= min_n): brier_model <= brier_market Y roi_flat >= roi_resume.
    - n < min_n o sin metricas: el estado previo se mantiene tal cual.
    """
    now = datetime.now(timezone.utc).isoformat()
    by_key = ({f"{r.league}|{r.market}": r for r in metrics.itertuples()}
              if not metrics.empty else {})
    markets: dict[str, dict] = {}
    transitions: list[dict] = []
    for key in sorted(set(by_key) | set(previous)):
        prev = previous.get(key) or {}
        was_paused = bool(prev.get("paused"))
        r = by_key.get(key)
        if r is None or int(r.n) < min_n:
            markets[key] = {
                "paused": was_paused,
                "since": prev.get("since") if was_paused else None,
                "reasons": list(prev.get("reasons") or []) if was_paused else [],
                "n": int(r.n) if r is not None else 0,
                "brier_model": _jsonable(r.brier_model) if r is not None else None,
                "brier_market": _jsonable(r.brier_market) if r is not None else None,
                "roi_flat": _jsonable(r.roi_flat) if r is not None else None,
                "updated_at": now,
            }
            continue
        reasons = []
        if (pd.notna(r.brier_model) and pd.notna(r.brier_market)
                and r.brier_model > r.brier_market + brier_margin):
            reasons.append("brier_worse_than_market")
        if pd.notna(r.roi_flat) and r.roi_flat < roi_pause:
            reasons.append("roi_flat_below_threshold")
        if was_paused:
            brier_recovered = (pd.isna(r.brier_model) or pd.isna(r.brier_market)
                               or r.brier_model <= r.brier_market)
            roi_recovered = pd.notna(r.roi_flat) and r.roi_flat >= roi_resume
            paused = not (brier_recovered and roi_recovered)
            if paused and not reasons:
                reasons = ["hysteresis_hold"]
        else:
            paused = bool(reasons)
        entry = {
            "paused": paused,
            "since": (prev.get("since") if (paused and was_paused)
                      else (now if paused else None)),
            "reasons": reasons if paused else [],
            "n": int(r.n),
            "brier_model": _jsonable(r.brier_model),
            "brier_market": _jsonable(r.brier_market),
            "roi_flat": _jsonable(r.roi_flat),
            "updated_at": now,
        }
        markets[key] = entry
        if paused != was_paused:
            lg, mk = key.split("|", 1)
            transitions.append({
                "timestamp": now, "league": lg, "market": mk,
                "action": "pause" if paused else "resume",
                "reasons": ";".join(reasons), "n": int(r.n),
                "brier_model": entry["brier_model"],
                "brier_market": entry["brier_market"],
                "roi_flat": entry["roi_flat"],
            })
    return markets, transitions


def write_degradation_registry(markets: dict[str, dict], bets_dir: Path,
                               params: dict | None = None) -> Path:
    """Persiste el registro (reemplazo atomico via archivo temporal). Escribe
    SIEMPRE, incluso vacio: un registro sin markets hace explicito que el
    monitor corrio y no pauso nada."""
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "params": params or {}, "markets": markets}
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / DEGRADATION_FILENAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def load_degradation_registry(bets_dir: Path) -> dict[str, dict]:
    """Mapa "liga|mercado" -> entrada de estado. {} si no existe o es ilegible
    (el consumidor lo trata como "sin auto-pausas", nunca como error)."""
    path = Path(bets_dir) / DEGRADATION_FILENAME
    if not path.exists():
        return {}
    try:
        markets = json.loads(path.read_text(encoding="utf-8")).get("markets")
    except (OSError, json.JSONDecodeError):
        return {}
    return markets if isinstance(markets, dict) else {}


def paused_from_registry(markets: dict[str, dict]) -> dict[str, list[str]]:
    """league -> lista ordenada de mercados auto-pausados, listo para fusionar
    por union con Settings.paused_markets."""
    out: dict[str, set[str]] = {}
    for key, entry in (markets or {}).items():
        if not (isinstance(entry, dict) and entry.get("paused")) or "|" not in key:
            continue
        lg, mk = key.split("|", 1)
        out.setdefault(lg, set()).add(mk)
    return {lg: sorted(mks) for lg, mks in out.items()}


def append_degradation_log(transitions: list[dict], bets_dir: Path) -> Path | None:
    """Rastro auditable de cada transicion pause/resume (append-only CSV)."""
    if not transitions:
        return None
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / DEGRADATION_LOG_FILENAME
    pd.DataFrame(transitions).to_csv(path, mode="a", header=not path.exists(),
                                     index=False)
    return path


def run_degradation_monitor(bets_dir: Path, *,
                            window_days: int = DEFAULT_WINDOW_DAYS,
                            min_n: int = DEFAULT_MIN_N,
                            brier_margin: float = DEFAULT_BRIER_MARGIN,
                            roi_pause: float = DEFAULT_ROI_PAUSE,
                            roi_resume: float = DEFAULT_ROI_RESUME,
                            today: date | None = None,
                            ) -> tuple[Path, list[dict], dict[str, list[str]]]:
    """Ciclo completo del monitor: liquidadas -> metricas de ventana -> gate con
    histeresis contra el registro previo -> persistir registro + log. Devuelve
    (ruta del registro, transiciones del dia, mapa de auto-pausas vigentes)."""
    bets_dir = Path(bets_dir)
    settled = load_all_settled(bets_dir)
    metrics = degradation_metrics(settled, window_days=window_days, today=today)
    previous = load_degradation_registry(bets_dir)
    markets, transitions = evaluate_pauses(
        metrics, previous, min_n=min_n, brier_margin=brier_margin,
        roi_pause=roi_pause, roi_resume=roi_resume)
    params = {"window_days": int(window_days), "min_n": int(min_n),
              "brier_margin": float(brier_margin), "roi_pause": float(roi_pause),
              "roi_resume": float(roi_resume)}
    path = write_degradation_registry(markets, bets_dir, params=params)
    append_degradation_log(transitions, bets_dir)
    return path, transitions, paused_from_registry(markets)
