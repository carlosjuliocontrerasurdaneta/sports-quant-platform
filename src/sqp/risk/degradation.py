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
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from sqp.audit.report import graded_in_window, load_all_settled
from sqp.exceptions import RegistroEstadoIlegibleError
from sqp.logging_config import get_logger
from sqp.storage.atomic import (atomic_write_csv, atomic_write_json,
                                read_json_retrying)

log = get_logger("sqp.risk.degradation")

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
    df = graded_in_window(settled, window_days=window_days, today=today)
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
    atomic_write_json(payload, path)   # temporal UNICO + fsync (AUD-002 en JSON)
    return path


def load_degradation_registry(bets_dir: Path) -> dict[str, dict]:
    """Mapa "liga|mercado" -> entrada de estado. {} si no existe o es ilegible
    (el consumidor lo trata como "sin auto-pausas", nunca como error)."""
    path = Path(bets_dir) / DEGRADATION_FILENAME
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        # Raiz comprobada antes de `.get` (AUD-002, audit-2026-09-18): una raiz
        # no objeto lanzaba AttributeError fuera del `except`. Aqui pesaba mas
        # que en el gate: el fallback de `run_all.py` volvia a llamar a este
        # lector FUERA de su `try` y abortaba el run entero antes de la primera
        # liga. Mismo patron que `risk.clv_gate.load_clv_gate`.
        markets = payload.get("markets") if isinstance(payload, dict) else None
    except (OSError, ValueError):  # ValueError cubre JSON y UnicodeDecodeError
        return {}
    return markets if isinstance(markets, dict) else {}


def auto_pauses_from_persisted_registry(bets_dir: Path, *,
                                        window_days: int = DEFAULT_WINDOW_DAYS,
                                        min_n: int = DEFAULT_MIN_N,
                                        brier_margin: float = DEFAULT_BRIER_MARGIN,
                                        roi_pause: float = DEFAULT_ROI_PAUSE,
                                        roi_resume: float = DEFAULT_ROI_RESUME,
                                        today: date | None = None,
                                        ) -> dict[str, list[str]]:
    """Auto-pausas vigentes segun el ULTIMO registro persistido, sin recalcular.

    Es el camino de degradacion de `run_all.py` cuando el monitor falla: se
    aplican las pausas ya conocidas (conservador) y el run sigue. Nunca lanza:
    un registro ilegible o con forma inesperada equivale a "sin auto-pausas",
    y se deja constancia en el log, porque abortar el run del dinero por un
    fichero de observabilidad es el modo de fallo que AUD-002 documento.
    """
    try:
        return paused_from_registry(_load_previous_state(bets_dir))
    except RegistroEstadoIlegibleError as exc:
        # El registro existe y no se lee (AUD-002, ronda audit-2026-09-22-r2).
        # Devolver {} aqui soltaba TODAS las pausas justo cuando el monitor, por
        # la misma causa, tampoco puede calcularlas. El log append-only guarda
        # cada pause/resume: su ultima accion por corte ES la pausa vigente.
        log.error("registro de degradacion ilegible (%s); auto-pausas "
                  "reconstruidas desde %s.", exc, DEGRADATION_LOG_FILENAME)
        try:
            previous = _previous_from_log(bets_dir)
        except Exception as exc2:  # defensa final: el consumidor no debe caer
            log.warning("log de degradacion tambien ilegible (%s); se continua "
                        "sin auto-pausas.", exc2)
            return {}
        # KI-061 (REG-001 de la verificacion de r2): devolver SOLO las pausas del
        # log dejaba sin pausar a un mercado que se degrada por primera vez
        # mientras el registro siga ilegible -- y ya no se reescribe, asi que
        # indefinidamente. Se evalua el gate de HOY con los mismos umbrales que
        # el monitor, sobre el estado reconstruido del log, y NO se escribe nada:
        # el registro ilegible sigue intacto para revisarlo a mano.
        try:
            metrics = degradation_metrics(load_all_settled(Path(bets_dir)),
                                          window_days=window_days, today=today)
            markets, _ = evaluate_pauses(metrics, previous, min_n=min_n,
                                         brier_margin=brier_margin,
                                         roi_pause=roi_pause, roi_resume=roi_resume)
            return paused_from_registry(markets)
        except Exception as exc3:  # sin metricas: al menos las pausas conocidas
            log.warning("no se pudo evaluar la degradacion de hoy (%s); se aplican "
                        "solo las pausas del log.", exc3)
            return paused_from_registry(previous)
    except Exception as exc:  # defensa final: el consumidor no debe caer
        log.warning("registro de degradacion ilegible (%s); se continua sin "
                    "auto-pausas.", exc)
        return {}


def _load_previous_state(bets_dir: Path) -> dict[str, dict]:
    """Estado previo para el ESCRITOR (y el fallback). Ausente -> ``{}``;
    existente pero ilegible -> ``RegistroEstadoIlegibleError``.

    `load_degradation_registry` devuelve ``{}`` en ambos casos, y el monitor
    tomaba "no se lee" por "nada estaba pausado": perdia la histeresis y lo
    persistia encima (AUD-002, ronda audit-2026-09-22-r2)."""
    path = Path(bets_dir) / DEGRADATION_FILENAME
    if not path.exists():
        return {}
    try:
        # Reintenta OSError (transitorio en Windows); corrupto no se reintenta.
        payload = read_json_retrying(path)
    except (OSError, ValueError) as exc:  # ValueError: JSON y UnicodeDecodeError
        raise RegistroEstadoIlegibleError(
            f"{path} existe pero no se puede leer ({exc}); no se reescribe para "
            "no perder la histeresis de las pausas. Revisar a mano.") from exc
    markets = payload.get("markets") if isinstance(payload, dict) else None
    if not isinstance(markets, dict):
        raise RegistroEstadoIlegibleError(
            f"{path} no tiene la forma esperada (raiz objeto con 'markets' "
            "objeto); no se reescribe. Revisar a mano.")
    return markets


def _previous_from_log(bets_dir: Path) -> dict[str, dict]:
    """Estado pausado/no pausado de cada corte segun la ULTIMA accion en el log
    append-only (orden de fichero = orden cronologico de escritura). Sirve de
    ``previous`` para `evaluate_pauses` cuando el registro no se lee."""
    path = Path(bets_dir) / DEGRADATION_LOG_FILENAME
    if not path.exists():
        return {}
    df = pd.read_csv(path, usecols=["league", "market", "action"], dtype=str)
    last = df.dropna().drop_duplicates(["league", "market"], keep="last")
    return {f"{r.league}|{r.market}": {"paused": r.action == "pause"}
            for r in last.itertuples()}


def _pauses_from_log(bets_dir: Path) -> dict[str, list[str]]:
    """Pausas vigentes segun el log (ver `_previous_from_log`)."""
    return paused_from_registry(_previous_from_log(bets_dir))


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
    """Rastro auditable de cada transicion pause/resume (append-only CSV, escritura atomica)."""
    if not transitions:
        return None
    bets_dir.mkdir(parents=True, exist_ok=True)
    path = bets_dir / DEGRADATION_LOG_FILENAME
    new = pd.DataFrame(transitions)
    if path.exists():
        try:
            prior = pd.read_csv(path)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            prior = pd.DataFrame()
        if not prior.empty:
            cols = list(prior.columns) + [c for c in new.columns if c not in prior.columns]
            new = pd.concat([prior.reindex(columns=cols), new.reindex(columns=cols)],
                            ignore_index=True)
    # `atomic_write_csv` y no un temporal a mano (AUD-MED-003, auditoria
    # integral 2026-09-08): temporal UNICO por proceso y fsync.
    atomic_write_csv(new, path)
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
    # Estricto (AUD-002, ronda r2): ilegible lanza ANTES de escribir; el llamador
    # (`run_all.py`) cae a `auto_pauses_from_persisted_registry`, que reconstruye
    # las pausas desde el log.
    previous = _load_previous_state(bets_dir)
    markets, transitions = evaluate_pauses(
        metrics, previous, min_n=min_n, brier_margin=brier_margin,
        roi_pause=roi_pause, roi_resume=roi_resume)
    params = {"window_days": int(window_days), "min_n": int(min_n),
              "brier_margin": float(brier_margin), "roi_pause": float(roi_pause),
              "roi_resume": float(roi_resume)}
    path = write_degradation_registry(markets, bets_dir, params=params)
    append_degradation_log(transitions, bets_dir)
    return path, transitions, paused_from_registry(markets)
