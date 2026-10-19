"""Bateria de los ajustes aditivos de la capa de features (pre-registro
`docs/research/2026-09-27-preregistro-bateria-ajustes.md` y su Enmienda 1,
2026-10-08, que manda sobre el texto anterior).

Mide, para seis ajustes {2, 3, 4, 8, 9, 10} y cuatro ligas (NBA, NHL, NFL,
MLB), si sumar el termino aditivo de `adjust_model_probability` mejora el log
loss de la probabilidad del modelo por encima de un simple desplazamiento
constante: 24 celdas, Holm con alfa de familia 0,05 mas el margen 0,002.
NO mide ventaja sobre el mercado ni rentabilidad: solo probabilidad estimada
frente a desenlace.

Tres modos (seccion 16):

  --pre            recuentos, distribucion de x, correlaciones entre features,
                   identidades 6~9/2 y 7~4, lineas L_i, hashes, HEAD,
                   `git status --porcelain` y parametros resueltos. NO empareja
                   ninguna feature con su desenlace ni calcula ninguna perdida.
  --parity-only    aserciones de paridad 1-3 (seccion 7.2) con c = 0 y con un c
                   arbitrario fijado en el script. No estima nada.
  (completo)       el JSON (`--out`), con `--pre-json` para abortar si algun
                   hash, el HEAD o los parametros resueltos cambiaron. El
                   informe `docs/research/...resultado-bateria-ajustes.md` se
                   redacta a partir del JSON; este script no lo genera.

Uso:
  python scripts/research/measure_adjustment_battery.py --pre --data-root <snap> --out pre.json
  python scripts/research/measure_adjustment_battery.py --parity-only --data-root <snap> [--leagues nba]
  python scripts/research/measure_adjustment_battery.py --data-root <snap> --pre-json pre.json --out res.json

Lo que NO hace (Enmienda 1(b)): no calcula la bateria con `tilt_scale` 0,9 en
ningun modo, ni reutiliza `measure_tilt_nhl.load_league`; el valor de tilt (y
todo otro parametro) se lee SIEMPRE de `_league_meta(liga)["league_params"]` y se
asierta por igualdad exacta en dos niveles. Las features no se reimplementan:
`build_adjustment_context` y `adjust_model_probability` son las de produccion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm as _norm_dist

from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.roi_engine import (
    _match_index,
    _match_result,
    _prior_games,
    load_closing_odds,
)
from sqp.backtesting.tuning import IMPROVEMENT_MARGIN
from sqp.calibration.metrics import expected_calibration_error
from sqp.config import CONFIG_DIR, ROOT as DEFAULT_ROOT, RiskConfig, load_yaml
from sqp.domain.models import Event
from sqp.features.rest_form import off_def_p_adjustment, over_rate_from_index
from sqp.models import distributions as dist
from sqp.pipeline.daily import _league_meta
from sqp.pipeline.probabilities import (
    _pick_main_lines,
    adjust_model_probability,
    build_adjustment_context,
)
from sqp.sports.adapters import NormalMarginAdapter
from sqp.sports.registry import get_adapter
from sqp.sports.team_names import get_team_normalizer
from sqp.storage.results_store import ResultsStore
from sqp.storage.starter_fip import StarterFIPStore
from sqp.storage.starters import StartersStore

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]

# ------------------------------------------------------------ constantes --
CUTOFF = "2026-09-26"                       # seccion 6 y Enmienda 1(f)
WARMUP = 60                                  # default de walk_forward_backtest
NM_OPTS = {"xatol": 1e-7, "fatol": 1e-10, "maxiter": 2000}      # seccion 9
N_BOOT, SEED = 10_000, 42                    # seccion 12
ALPHA = 0.05                                 # seccion 11
K_FAMILY = 24                                # seccion 11
P_LO, P_HI = 0.01, 0.99                      # recorte de adjust_model_probability
TOL = 1e-12                                  # tolerancia de paridad
LOSS_EPS = 1e-12                             # recorte de tuning._binary_nll_series
C_STAR_TARGET = 0.032                        # seccion 13: delta_RMS para 0,002
DEFAULT_ADJ_MARGIN = IMPROVEMENT_MARGIN      # 0,002

LEAGUES = ("nba", "nhl", "nfl", "mlb")
FAMILY = {"nba": "basketball", "nhl": "hockey", "nfl": "football", "mlb": "baseball"}
ADJ_IDS = (2, 3, 4, 8, 9, 10)
COEF_NAME = {2: "recent_form_coef", 3: "h2h_coef", 4: "totals_tendency_coef",
             8: "home_away_form_coef", 9: "margin_coef", 10: "over_under_rate_coef"}
DECISION = {2: "h2h", 3: "h2h", 8: "h2h", 9: "h2h", 4: "totals", 10: "totals"}
SPREAD_RESTRICTED = (2, 8, 9)                # criterio 6
CHANNEL = {2: "calidad", 8: "calidad", 9: "calidad", 3: "cara_a_cara", 4: "anotacion", 10: "anotacion"}
WINDOW_DEFAULTS = {"recent_form_n": 5, "h2h_n": 10, "totals_tendency_n": 10, "off_def_n": 10,
                   "home_away_form_n": 5, "margin_n": 10, "over_under_rate_n": 10}

# Lineas fijas de paridad con walk_forward_backtest (seccion 7.2, aserto 1).
PARITY_LINES = {"nba": ((-4.5,), (220.5,)), "nfl": ((-3.5,), (44.5,)),
                "nhl": ((-1.5, 1.5), (5.5,)), "mlb": ((-1.5, 1.5), (8.5,))}
# c arbitrario del modo --parity-only (por unidad de x; ver el docstring de cada termino).
PROBE_C = {2: 0.08, 3: 0.14, 4: 0.01, 8: 0.08, 9: 0.01, 10: 0.2}

FOLDS: dict[str, dict[str, dict[str, str]]] = {
    "nba": {"A": {"train_end": "2012-09-30", "test_start": "2012-10-01", "test_end": "2017-09-30"},
            "B": {"train_end": "2017-09-30", "test_start": "2017-10-01", "test_end": "2022-09-30"},
            "C": {"train_end": "2022-09-30", "test_start": "2022-10-01", "test_end": "2026-06-30"}},
    "nhl": {"A": {"train_end": "2014-09-30", "test_start": "2014-10-01", "test_end": "2018-09-30"},
            "B": {"train_end": "2018-09-30", "test_start": "2018-10-01", "test_end": "2022-09-30"},
            "C": {"train_end": "2022-09-30", "test_start": "2022-10-01", "test_end": "2026-06-30"}},
    "nfl": {"A": {"train_end": "2012-06-30", "test_start": "2012-07-01", "test_end": "2017-06-30"},
            "B": {"train_end": "2017-06-30", "test_start": "2017-07-01", "test_end": "2022-06-30"},
            "C": {"train_end": "2022-06-30", "test_start": "2022-07-01", "test_end": "2026-06-30"}},
    "mlb": {"A": {"train_end": "2024-12-31", "test_start": "2025-01-01", "test_end": "2025-12-31"},
            "B": {"train_end": "2025-12-31", "test_start": "2026-01-01", "test_end": "2026-09-26"}},
}

# Enmienda 1(b): parametros resueltos que se asertan por IGUALDAD EXACTA.
EXPECTED_LEAGUE_PARAMS: dict[str, dict | None] = {
    "nba": {"rest_points_per_day": 0.795},
    "nhl": {"elo_home_adv": 15.0, "tilt_scale": 0.439},
    "nfl": None,
    "mlb": {"park_bound": 0.1, "pitcher_bound": 0.05, "pitcher_prior_starts": 5.0, "tilt_scale": 0.4},
}
EXPECTED_ADAPTER_PARAMS: dict[str, dict] = {
    "nba": {"avg_total": 224.0, "elo_home_adv": 70, "elo_k": 20, "elo_mov": True,
            "margin_sigma": 13.0, "points_per_elo": 0.028, "rest_points_per_day": 0.795,
            "scoring_half_life_days": 180.0, "total_sigma": 22.0},
    "nhl": {"avg_total": 6.1, "elo_home_adv": 15.0, "elo_k": 10, "home_scoring_bonus": 0.1,
            "max_score": 15, "tilt_scale": 0.439},
    "nfl": {"avg_total": 44.0, "elo_home_adv": 55, "elo_k": 24, "elo_mov": True,
            "margin_sigma": 13.5, "points_per_elo": 0.025, "total_sigma": 13.5},
    "mlb": {"avg_total": 8.7, "dispersion_k": 3.8, "elo_home_adv": 25, "elo_k": 6,
            "home_scoring_bonus": 0.1, "max_score": 25, "park_bound": 0.1, "pitcher_bound": 0.05,
            "pitcher_prior_starts": 5.0, "tilt_scale": 0.4},
}

# Referencias de la seccion 5/13 (para que `--pre` informe las diferencias).
REF_ROWS = {"nba": 34065, "nhl": 32888, "nfl": 8046, "mlb": 9706}
REF_FOLD_GAMES = {"nba": {"A": 7134, "B": 6621, "C": 5577}, "nhl": {"A": 5780, "B": 5192, "C": 5978},
                  "nfl": {"A": 1664, "B": 1601, "C": 1339}, "mlb": {"A": 2434, "B": 2403}}
REF_FOLD_DAYS = {"nba": {"A": 1162, "B": 1112, "C": 931}, "nhl": {"A": 957, "B": 872, "C": 952},
                 "nfl": {"A": 454, "B": 447, "C": 389}, "mlb": {"A": 184, "B": 182}}
REF_AFFECTED = {
    "nba": {2: 15201, 3: 15914, 8: 15407, 9: 19185, 4: 19205, 10: 16470},
    "nhl": {2: 13049, 3: 13277, 8: 12981, 9: 16375, 4: 16518, 10: 14611},
    "nfl": {2: 3636, 3: 3588, 8: 3727, 9: 4566, 4: 4564, 10: 3943},
    "mlb": {2: 3896, 3: 3722, 8: 3878, 9: 4739, 4: 4767, 10: 4151},
}
REF_CORR = {  # x2~x9, x2~x8, x8~x9, x3~x9, x4~x10
    "nba": (0.704, 0.613, 0.645, 0.287, 0.833), "nhl": (0.658, 0.516, 0.580, 0.216, 0.855),
    "nfl": (0.652, 0.570, 0.632, 0.184, 0.850), "mlb": (0.629, 0.669, 0.535, 0.233, 0.823)}
CORR_NAMES = ("x2~x9", "x2~x8", "x8~x9", "x3~x9", "x4~x10")
MLB_CHANGING = (4, 10)   # seccion 13: en MLB cambian porque la linea incluye abridor y parque

SECONDARY_BASKET = ("wnba", "ncaab", "wncaab")
SECONDARY_FOOTBALL = ("ncaaf",)
CONFIG_FILES = ("configs/leagues/ratings.yaml", "configs/default.yaml")


# ----------------------------------------------------------- utilidades --
def _is_true(v: object) -> bool:
    return str(v).strip().lower() in ("true", "1", "1.0")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_rows(path: Path) -> int:
    n = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            n += chunk.count(b"\n")
    return max(0, n - 1)


def _clean(obj: object) -> object:
    """JSON limpio: NaN/inf -> None, numpy -> python, claves `_x` (trabajo) fuera."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_clean(v) for v in obj.tolist()]
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def _safe_informe(nombre: str, fn: Callable[[], object]) -> object:
    """Un informe secundario NUNCA impide escribir el JSON principal (seccion
    14: no deciden nada). El error se anota en su propia seccion."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 -- informe opcional, ver docstring
        print(f"aviso: informe secundario '{nombre}' fallo: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return {"error": f"{type(exc).__name__}: {exc}", "tipo": type(exc).__name__,
                "traceback": traceback.format_exc()}


def _is_error(val: object) -> bool:
    return isinstance(val, dict) and "error" in val


# ------------------------------------------------------------------ git --
def git_head(cwd: Path) -> str | None:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(cwd), capture_output=True,
                             text=True, check=True, timeout=30)
        return res.stdout.strip()
    except Exception:  # noqa: BLE001 -- procedencia, no decide nada
        return None


def git_status_porcelain(cwd: Path, paths: tuple[str, ...] | None = None) -> str | None:
    """`git status --porcelain` de TODO el repositorio (paths=None, lo que
    registra `--pre`) o de unas rutas (lo que comprueba el modo completo)."""
    cmd = ["git", "status", "--porcelain"] + (["--", *paths] if paths else [])
    try:
        res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True,
                             timeout=30)
        return res.stdout
    except Exception:  # noqa: BLE001
        return None


_FULL_GIT_PATHS = ("src", "configs", "scripts/research")


def check_git_clean(status: str | None, where: str) -> None:
    if status is None:
        raise SystemExit(f"No se pudo obtener 'git status --porcelain' ({where}). Se aborta: no "
                         "se puede verificar que el arbol este limpio.")
    if status.strip() != "":
        raise SystemExit(f"'git status --porcelain' ({where}) NO esta vacio:\n{status}\n"
                         "Se aborta: no se mide con cambios sin commitear.")


# ------------------------------------------------------------- parametros --
_WINDOWS_CACHE: dict[str, int] | None = None


def risk_windows() -> dict[str, int]:
    """Ventanas `n` de la configuracion (`configs/default.yaml`, seccion 6).
    Aborta si difieren de las pre-registradas: no se estima ninguna ventana."""
    global _WINDOWS_CACHE
    if _WINDOWS_CACHE is None:
        r = (load_yaml(CONFIG_DIR / "default.yaml") or {}).get("risk", {}) or {}
        w = {k: int(r.get(k, d)) for k, d in WINDOW_DEFAULTS.items()}
        if w != WINDOW_DEFAULTS:
            raise SystemExit(f"Ventanas de configs/default.yaml {w} != pre-registradas "
                             f"{WINDOW_DEFAULTS}. Se aborta: las ventanas no se estiman ni se cambian.")
        _WINDOWS_CACHE = w
    return dict(_WINDOWS_CACHE)


def risk_with(**coefs: float) -> RiskConfig:
    """`RiskConfig` con las ventanas de la configuracion y SOLO los coeficientes
    indicados distintos de 0 (aserto 2 de paridad)."""
    return RiskConfig(**risk_windows(), **coefs)


def resolved_adapter_params(league: str, league_params: dict | None) -> dict:
    family = FAMILY.get(league) or _league_meta(league)["family"]
    return dict(get_adapter(league, family, league_params).params)


def assert_resolved_params(league: str, league_params: dict | None, adapter_params: dict) -> None:
    """Enmienda 1(b): igualdad EXACTA en los dos niveles; si no, aborta."""
    exp_lp = EXPECTED_LEAGUE_PARAMS[league]
    if league_params != exp_lp or (exp_lp is None) != (league_params is None):
        raise SystemExit(f"{league}: _league_meta(...)['league_params'] = {league_params!r} != "
                         f"{exp_lp!r} (Enmienda 1(b)). Se aborta: no se reinterpreta la base.")
    exp_ap = EXPECTED_ADAPTER_PARAMS[league]
    if dict(adapter_params) != exp_ap:
        diff = {k: (adapter_params.get(k, "<ausente>"), exp_ap.get(k, "<ausente>"))
                for k in sorted(set(adapter_params) | set(exp_ap))
                if adapter_params.get(k, "<a>") != exp_ap.get(k, "<a>")}
        raise SystemExit(f"{league}: adapter.params efectivo difiere (resuelto, esperado): {diff}. "
                         "Se aborta (Enmienda 1(b)).")


# ------------------------------------------------------------------ datos --
# Enmienda 3(c): copias anteriores de un gamePk MLB repetido (game_id, fecha descartada).
EXPECTED_DEDUPE_DROPS: dict[str, list[tuple[str, str]]] = {
    "nba": [], "nhl": [], "nfl": [],
    "mlb": [("718203", "2023-05-13"), ("717407", "2023-07-14"), ("717375", "2023-07-17"),
            ("717324", "2023-07-21"), ("716875", "2023-08-23"), ("716414", "2023-09-27"),
            ("716404", "2023-09-28"), ("745180", "2024-05-21"), ("746942", "2024-06-26"),
            ("746755", "2024-08-27"), ("777861", "2025-05-19"), ("777623", "2025-06-06"),
            ("777294", "2025-07-01"), ("776907", "2025-08-02"), ("824912", "2026-06-16")],
}


def _game_id_text(value: object) -> str:
    """`game_id` como texto celda a celda; None/NaN/vacio -> ''. (pandas 3: `astype(str)` deja NaN.)"""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = str(value).strip()
    return "" if s.lower() in ("nan", "none") else s


def dedupe_by_game_id(results: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    """Enmienda 3(c): por cada `game_id` no vacio repetido, conserva SOLO la fila de `date` mas tardia
    (empate de fecha: la primera en el orden del store). Las filas sin `game_id` no se tocan.
    Devuelve (lista filtrada en el orden original, [(game_id, date) descartados])."""
    keep: dict[str, int] = {}
    for i, r in enumerate(results):
        gid = _game_id_text(r.get("game_id"))
        if not gid:
            continue
        j = keep.get(gid)
        if j is None or str(r.get("date", ""))[:10] > str(results[j].get("date", ""))[:10]:
            keep[gid] = i
    kept = set(keep.values())
    out: list[dict] = []
    dropped: list[tuple[str, str]] = []
    for i, r in enumerate(results):
        gid = _game_id_text(r.get("game_id"))
        if gid and i not in kept:
            dropped.append((gid, str(r.get("date", ""))[:10]))
        else:
            out.append(r)
    return out, dropped


def assert_dedupe_drops(league: str, dropped: list[tuple[str, str]]) -> None:
    """Enmienda 3(c): 0 descartes en NBA/NHL/NFL y exactamente los 15 en MLB; si no, aborta."""
    exp = EXPECTED_DEDUPE_DROPS[league]
    if sorted(dropped) != sorted(exp):
        raise SystemExit(f"{league}: descartes por game_id duplicado {sorted(dropped)} != esperados "
                         f"{sorted(exp)} (Enmienda 3(c)). Se aborta: no se mide con otro universo de filas.")


def load_league(league: str, data_root: Path, *, assert_params: bool = True
                ) -> tuple[list[dict], dict | None, dict]:
    """Resultados con `date <= CUTOFF`, `league_params` resueltos y procedencia.
    En MLB se enriquecen con abridores y FIP (seccion 6). Sin reutilizar
    `measure_tilt_nhl.load_league` (su invariante es tilt 0,9)."""
    store = ResultsStore(data_root)
    results = [r for r in store.load(league, dedupe_game_id=False) if str(r.get("date", ""))[:10] <= CUTOFF]
    n_before = len(results)
    results, dropped = dedupe_by_game_id(results)     # Enmienda 3(c): antes de adjuntar abridores/FIP
    if assert_params and league in EXPECTED_DEDUPE_DROPS:
        assert_dedupe_drops(league, dropped)
    meta_params = _league_meta(league).get("league_params")
    adapter_params = resolved_adapter_params(league, meta_params)
    if assert_params:
        assert_resolved_params(league, meta_params, adapter_params)
    proc: dict = {"fichero": str(store.path(league)), "filas_antes_dedupe_game_id": n_before,
                  "filas_leidas": len(results), "descartadas_dedupe_game_id": [list(d) for d in dropped]}
    if store.path(league).exists():
        proc["sha256"] = sha256_of(store.path(league))
    if league == "mlb":
        proc["abridores_adjuntos"] = StartersStore(data_root).attach(league, results)
        proc["fip_adjuntos"] = StarterFIPStore(data_root).attach(league, results)
    return results, meta_params, proc


def secondary_soccer_leagues() -> list[str]:
    cfg = (load_yaml(CONFIG_DIR / "leagues" / "soccer.yaml") or {}).get("leagues", {}) or {}
    return sorted(cfg.keys())


def input_manifest(data_root: Path) -> dict:
    """SHA-256 y filas de cada fichero que lee el script (Enmienda 1(g)),
    mas los de configuracion. Claves relativas: comparables entre instantaneas."""
    files: list[Path] = []
    store = ResultsStore(data_root)
    for lg in (*LEAGUES, *SECONDARY_FOOTBALL, *SECONDARY_BASKET, *secondary_soccer_leagues()):
        files.append(store.path(lg))
    files.append(StartersStore(data_root).path("mlb"))
    files.append(StarterFIPStore(data_root).path("mlb"))
    odds_dir = data_root / "data" / "odds"
    for lg in LEAGUES:
        files.extend(sorted(odds_dir.glob(f"odds_{lg}_*.csv")))
    out: dict[str, dict] = {}
    for p in files:
        rel = p.relative_to(data_root).as_posix()
        out[rel] = ({"sha256": sha256_of(p), "filas": _count_rows(p)} if p.exists()
                    else {"sha256": None, "filas": None})
    return out


def config_hashes() -> dict:
    return {rel: (sha256_of(_WORKTREE_ROOT / rel) if (_WORKTREE_ROOT / rel).exists() else None)
            for rel in CONFIG_FILES}


def resolved_params_report(leagues: tuple[str, ...] | list[str]) -> dict:
    out: dict = {}
    for lg in leagues:
        lp = _league_meta(lg).get("league_params")
        out[lg] = {"league_params": lp, "adapter_params": resolved_adapter_params(lg, lp)}
    return out


# ----------------------------------------------------- perdida y optimizador --
def clip_p(p: np.ndarray | float) -> np.ndarray:
    return np.clip(p, P_LO, P_HI)


def ll_vec(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Log loss binario por partido, mismo recorte que `tuning._binary_nll_series`."""
    p = np.clip(p, LOSS_EPS, 1.0 - LOSS_EPS)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def fit(objective: Callable[[np.ndarray], float], x0: list[float], name: str,
        abort: bool = True) -> np.ndarray:
    """Nelder-Mead, xatol 1e-7, fatol 1e-10, maxiter 2000, sin limites (seccion
    9). Si no converge, aborta: se trata como defecto de codigo."""
    res = minimize(objective, x0=np.asarray(x0, dtype=float), method="Nelder-Mead", options=NM_OPTS)
    if not res.success:
        msg = (f"El optimizador Nelder-Mead NO CONVERGIO ({name}): {res.message}. Seccion 9: se "
               "trata como defecto de codigo y se aborta, no se repite con otro punto de partida.")
        if abort:
            raise SystemExit(msg)
        raise RuntimeError(msg)
    return res.x


def fit_c(p: np.ndarray, x: np.ndarray, y: np.ndarray) -> float:
    return float(fit(lambda v: float(np.mean(ll_vec(clip_p(p + v[0] * x), y))), [0.0], "c")[0])


def fit_a(p: np.ndarray, y: np.ndarray) -> float:
    return float(fit(lambda v: float(np.mean(ll_vec(clip_p(p + v[0]), y))), [0.0], "a")[0])


def fit_ac(p: np.ndarray, x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    v = fit(lambda w: float(np.mean(ll_vec(clip_p(p + w[0] + w[1] * x), y))), [0.0, 0.0],
            "a,c conjunto", abort=False)
    return float(v[0]), float(v[1])


# ------------------------------------------------------- bootstrap por dias --
def bootstrap_dias(dates: np.ndarray, stats: dict[str, tuple[np.ndarray, np.ndarray]],
                   n_boot: int = N_BOOT, seed: int = SEED, chunk: int = 250) -> dict[str, dict]:
    """Seccion 12: remuestrea DIAS UTC completos del test combinado (con todos
    sus partidos), `n_boot` replicas, semilla `seed`. Cada estadistico es un
    cociente sum(num)/sum(den) por replica (el Delta de los afectados tiene
    den = 1 solo en los afectados). IC95 percentil y error estandar."""
    u, inv = np.unique(dates, return_inverse=True)
    nd = len(u)
    sums = {k: np.bincount(inv, weights=np.asarray(v[0], float), minlength=nd) for k, v in stats.items()}
    cnts = {k: np.bincount(inv, weights=np.asarray(v[1], float), minlength=nd) for k, v in stats.items()}
    reps = {k: np.empty(n_boot) for k in stats}
    rng = np.random.default_rng(seed)
    done = 0
    while done < n_boot:
        m = min(chunk, n_boot - done)
        pick = rng.integers(0, nd, size=(m, nd))
        for k in stats:
            with np.errstate(divide="ignore", invalid="ignore"):
                reps[k][done:done + m] = sums[k][pick].sum(axis=1) / cnts[k][pick].sum(axis=1)
        done += m
    out: dict[str, dict] = {}
    for k, r in reps.items():
        fin = r[np.isfinite(r)]
        out[k] = {"n_dias": int(nd), "n_replicas": int(len(fin)),
                  "ic95": ([float(np.quantile(fin, 0.025)), float(np.quantile(fin, 0.975))]
                           if len(fin) else [None, None]),
                  "se": float(np.std(fin, ddof=1)) if len(fin) > 1 else None}
    return out


# ------------------------------------------------------------------- Holm --
def p_value(delta: float | None, se: float | None) -> float:
    """Seccion 11: p = Phi(delta/EE), unilateral (H0: delta >= 0). Sin delta o
    sin EE utilizable, p = 1 (no se rechaza)."""
    if delta is None or se is None or not math.isfinite(delta) or not math.isfinite(se) or se <= 0:
        return 1.0
    return float(_norm_dist.cdf(delta / se))


def holm(pvals: dict[str, float], alpha: float = ALPHA) -> dict[str, dict]:
    """Holm: p ordenados de menor a mayor; se rechaza H(k) mientras
    p(k) <= alpha/(K-k+1); al primer fallo se para. Informa p y p ajustados
    (monotonos, tope 1). Empates de p: orden por clave, determinista."""
    items = sorted(pvals.items(), key=lambda kv: (kv[1], kv[0]))
    K = len(items)
    out: dict[str, dict] = {}
    stopped = False
    running = 0.0
    for rank, (key, p) in enumerate(items, start=1):
        thr = alpha / (K - rank + 1)
        reject = (not stopped) and p <= thr
        if not reject:
            stopped = True
        running = max(running, min(1.0, (K - rank + 1) * p))
        out[key] = {"p": p, "rango": rank, "umbral": thr, "rechaza": bool(reject),
                    "p_ajustado": running}
    return out


# ------------------------------------------------------------ frame (motor) --
class Frame:
    """Salida de `build_frame`: tabla por partido + lo necesario para
    reconstruir contextos (paridad 2) sin guardar un contexto por partido."""

    def __init__(self, df: pd.DataFrame, ordered: list[dict], team_hist: dict,
                 norm: Callable[[str], str], league: str, max_identity_dev: float | None) -> None:
        self.df = df
        self.ordered = ordered
        self.team_hist = team_hist
        self.norm = norm
        self.league = league
        self.max_identity_dev = max_identity_dev


def _x_values(ctx, line: float, over_n: int) -> dict[str, float]:
    """x de cada ajuste (seccion 6); NaN si la feature no esta disponible."""
    nan = float("nan")
    fh, fa = ctx.form_home, ctx.form_away
    x2 = fh - fa if fh is not None and fa is not None else nan
    x3 = ctx.h2h_home - 0.5 if ctx.h2h_home is not None else nan
    ah, aa = ctx.avg_total_home, ctx.avg_total_away
    x4 = (ah + aa) / 2.0 - line if ah is not None and aa is not None else nan
    fhh, faa = ctx.form_home_at_home, ctx.form_away_at_away
    x8 = fhh - faa if fhh is not None and faa is not None else nan
    mh, ma = ctx.margin_home, ctx.margin_away
    x9 = mh - ma if mh is not None and ma is not None else nan
    return {"x2": x2, "x3": x3, "x4": x4, "x8": x8, "x9": x9}


def _x_over_rate(ctx, home: str, away: str, line: float, over_n: int) -> float:
    idx = ctx.team_index
    oh = over_rate_from_index(idx, home, line, over_n, ctx.normalize, ctx.ref_date)
    oa = over_rate_from_index(idx, away, line, over_n, ctx.normalize, ctx.ref_date)
    return (oh + oa) / 2.0 - 0.5 if oh is not None and oa is not None else float("nan")


def _x_offdef(ctx, home: str, away: str, line: float) -> tuple[float, float]:
    """x6 y x7 (solo para las identidades de la seccion 2; usan la funcion de produccion con coef 1)."""
    args = (ctx.avg_scored_home, ctx.avg_conceded_home, ctx.avg_scored_away, ctx.avg_conceded_away)
    if any(a is None for a in args):
        return float("nan"), float("nan")
    x6 = off_def_p_adjustment("h2h", home, home, away, *args, None, 1.0, 0.0)
    x7 = off_def_p_adjustment("totals", "Over", home, away, *args, line, 0.0, 1.0)
    return x6, x7


def build_frame(results: list[dict], league: str, family: str, league_params: dict | None, *,
                with_outcomes: bool, parity: bool = False, feature_from: str | None = None,
                feature_stride: int = 1, captured: dict | None = None,
                warmup: int = WARMUP) -> Frame:
    """Reproduce el bucle de `walk_forward_backtest` (dias completos estimados
    con el estado al cierre del dia anterior; `warmup`) y, en el mismo recorrido,
    el historial por equipo de `roi_engine` para llamar a
    `build_adjustment_context`. Seccion 7.2.

    `with_outcomes=False` (modo `--pre`): NO lee el marcador del partido que se
    esta procesando ni llama a `estimate`: solo el estado del modelo (con dias
    anteriores) para fijar L_i. `feature_from`: no calcula features antes de esa
    fecha y `feature_stride > 1` solo en uno de cada `feature_stride` partidos
    (solo para `--parity-only`, que asi cuesta menos; la columna `feat` marca
    las filas con features). El modo completo usa siempre stride 1."""
    risk = risk_with()
    over_n = risk.over_under_rate_n
    ordered = sorted(results, key=lambda row: str(row.get("date", "")))
    adapter = get_adapter(league, family, league_params)
    normal_family = isinstance(adapter, NormalMarginAdapter)
    norm_cache: dict[str, str] = {}

    def _norm(name: str) -> str:
        v = norm_cache.get(name)
        if v is None:
            v = adapter.normalize(name)
            norm_cache[name] = v
        return v

    pl_spreads, pl_totals = PARITY_LINES.get(league, ((), ()))
    team_hist: dict[str, list[tuple[int, str, dict]]] = defaultdict(list)
    pending: list[dict] = []
    rows: list[dict] = []
    max_dev: float | None = 0.0 if league == "nhl" else None
    bonus = float(adapter.params.get("home_scoring_bonus", 0.0))
    nan = float("nan")
    for i, r in enumerate(ordered):
        rd = str(r.get("date", ""))[:10]
        if pending and rd != str(pending[0].get("date", ""))[:10]:
            for completed in pending:
                adapter.observe(completed)
            pending.clear()
        if i >= warmup:
            ev = Event(event_id=str(i), sport_key="bt", league=league, home=r["home"],
                       away=r["away"], start_time=str(r.get("date")),
                       data_label=r.get("data_label", "real"),
                       home_pitcher=r.get("home_starter"), away_pitcher=r.get("away_starter"))
            # --- mu de la base y lineas por partido (seccion 7.3) -----------
            mu_margin = nan
            if normal_family:
                diff = adapter.elo.rating_diff(ev.home, ev.away)
                mu_margin = dist.elo_diff_to_margin(diff, adapter.params["points_per_elo"]) \
                    + adapter.rest.margin_adjustment(ev.home, ev.away, str(ev.start_time)[:10])
                mu = adapter.params["avg_total"]
                if adapter.params.get("scoring_totals", True):
                    mu = adapter.scoring.expected_total(ev.home, ev.away, mu)
                s1, s2 = -(math.floor(mu_margin) + 0.5), nan
            else:
                lam_h, lam_a = adapter._rates(ev)
                mu = lam_h + lam_a
                s1, s2 = -1.5, 1.5
                if league == "nhl":
                    mu_sc = adapter.scoring.expected_total(ev.home, ev.away, adapter.params["avg_total"])
                    max_dev = max(max_dev or 0.0, abs(mu - (mu_sc + bonus)))
            line = math.floor(mu) + 0.5
            row: dict = {"idx": i, "date": rd, "home": r["home"], "away": r["away"],
                         "neutral": _is_true(r.get("neutral", False)),
                         "mu": mu, "L": line, "s1": s1, "s2": s2}
            # --- features (no dependen del marcador del partido) ------------
            row["feat"] = False
            if (feature_from is None or rd >= feature_from) and (feature_stride <= 1 or i % feature_stride == 0):
                row["feat"] = True
                hn, an = _norm(ev.home), _norm(ev.away)
                prior = _prior_games(team_hist, hn, an, rd)
                ctx = build_adjustment_context(ev.home, ev.away, rd, prior, risk, _norm)
                xs = _x_values(ctx, line, over_n)
                xs["x10"] = _x_over_rate(ctx, ev.home, ev.away, line, over_n)
                xs["x6"], xs["x7"] = _x_offdef(ctx, ev.home, ev.away, line)
                row.update(xs)
                if captured:
                    cap = captured.get((rd, str(r["home"]), str(r["away"]), str(r.get("game_id", ""))))
                    if cap is not None:
                        row["cap_s"], row["cap_t"] = cap
                        if cap[1] is not None:
                            row["x4_cap"] = _x_values(ctx, cap[1], over_n)["x4"]
                            row["x10_cap"] = _x_over_rate(ctx, ev.home, ev.away, cap[1], over_n)
            else:
                row.update({k: nan for k in ("x2", "x3", "x4", "x8", "x9", "x10", "x6", "x7")})
            # --- desenlace y probabilidades de la base ---------------------
            if with_outcomes:
                hs, aws = float(r["home_score"]), float(r["away_score"])
                margin, total = hs - aws, hs + aws
                est = adapter.estimate(ev, s1, line)
                ph = est.home_win_estimated_probability
                if est.draw_estimated_probability is not None:
                    den = ph + est.away_win_estimated_probability
                    ph = ph / den if den > 0 else 0.5
                if normal_family:
                    chk = dist.normal_margin_probs(mu_margin, adapter.params["margin_sigma"], None)["home_win"]
                    chk_o = dist.normal_total_probs(mu, adapter.params["total_sigma"], line)["over"]
                    if abs(chk - est.home_win_estimated_probability) > TOL or \
                            abs(chk_o - est.over_estimated_probability) > TOL:
                        raise SystemExit("Inconsistencia: mu_margin/mu_total del script no reproducen "
                                         "adapter.estimate (NormalMarginAdapter). Se aborta.")
                    p_s2 = nan
                else:
                    est2 = adapter.estimate(ev, s2, None)
                    p_s2 = est2.home_cover_estimated_probability
                row.update({"home_score": hs, "away_score": aws, "margin": margin, "total": total,
                            "y_h2h": (nan if margin == 0 else (1.0 if margin > 0 else 0.0)),
                            "p_h2h": ph, "p_s1": est.home_cover_estimated_probability, "p_s2": p_s2,
                            "p_over": est.over_estimated_probability})
                if parity:
                    for k, s in enumerate(pl_spreads):
                        e = adapter.estimate(ev, s, pl_totals[0] if k == 0 else None)
                        row[f"pp_s{k}"] = e.home_cover_estimated_probability
                        if k == 0:
                            row["pp_t"] = e.over_estimated_probability
                cap_row = captured.get((rd, str(r["home"]), str(r["away"]), str(r.get("game_id", "")))) \
                    if captured else None
                if cap_row is not None:
                    ec = adapter.estimate(ev, cap_row[0], cap_row[1])
                    row["p_cap_cov"] = ec.home_cover_estimated_probability
                    row["p_cap_over"] = ec.over_estimated_probability
            rows.append(row)
        pending.append(r)
        hn2, an2 = _norm(str(r.get("home", ""))), _norm(str(r.get("away", "")))
        rec = (i, rd, r)
        team_hist[hn2].append(rec)
        if an2 != hn2:
            team_hist[an2].append(rec)
    df = pd.DataFrame(rows)
    for col in ("x2", "x3", "x4", "x8", "x9", "x10", "x6", "x7"):
        if col not in df.columns:
            df[col] = np.nan
    if max_dev is not None and max_dev > TOL:
        raise SystemExit(f"NHL: |lambda_h + lambda_a - (mu_scoring + bonus)| = {max_dev:.3e} > 1e-12 "
                         "(Enmienda 1(c).1). Se aborta.")
    return Frame(df, ordered, team_hist, _norm, league, max_dev)


# ----------------------------------------------------------- paridad (7.2) --
def assert_parity_engine(fr: Frame, results: list[dict], league: str, family: str,
                         league_params: dict | None, warmup: int = WARMUP) -> dict:
    """Aserto 1: `p_base` coincide con `walk_forward_backtest` (1e-12), en
    h2h y en las lineas fijas de paridad (spreads con la vista CON empates)."""
    sp, tp = PARITY_LINES[league]
    ref = walk_forward_backtest(results, league, family, league_params, warmup=warmup,
                                spread_lines=sp, total_lines=tp)
    df = fr.df
    p = df["p_h2h"].to_numpy(float)
    ok = np.isfinite(df["y_h2h"].to_numpy(float))
    a, b = np.asarray(ref["binary_probs"], float), p[ok]
    devs: dict[str, float] = {}
    if len(a) != len(b):
        raise SystemExit(f"Paridad 1 rota: h2h tiene {len(b)} partidos y el motor {len(a)}.")
    devs["h2h"] = float(np.max(np.abs(a - b))) if len(a) else 0.0
    margin = df["margin"].to_numpy(float)
    total = df["total"].to_numpy(float)
    for k, s in enumerate(sp):
        key = f"spreads@{float(s)}"
        keep = margin != -s
        mine = df[f"pp_s{k}"].to_numpy(float)[keep]
        eng = np.asarray(ref["markets"][key]["probs"], float)
        if len(mine) != len(eng):
            raise SystemExit(f"Paridad 1 rota en {key}: {len(mine)} frente a {len(eng)}.")
        devs[key] = float(np.max(np.abs(mine - eng))) if len(eng) else 0.0
    for t in tp:
        key = f"totals@{float(t)}"
        keep = total != t
        mine = df["pp_t"].to_numpy(float)[keep]
        eng = np.asarray(ref["markets"][key]["probs"], float)
        if len(mine) != len(eng):
            raise SystemExit(f"Paridad 1 rota en {key}: {len(mine)} frente a {len(eng)}.")
        devs[key] = float(np.max(np.abs(mine - eng))) if len(eng) else 0.0
    bad = {k: v for k, v in devs.items() if v > TOL}
    if bad:
        raise SystemExit(f"PARIDAD 1 ROTA (> {TOL}): {bad}")
    return {"max_desviacion": devs, "n_h2h": int(len(a)), "tolerancia": TOL}


def _layer_p(p: float, market: str, selection: str, point: float | None, home: str, away: str,
             ctx, risk: RiskConfig) -> float:
    return adjust_model_probability(p, market, selection, point, home, away, ctx, risk)


def assert_parity_layer(fr: Frame, positions: np.ndarray, coefs: dict[int, float],
                        atol: float = TOL) -> dict:
    """Aserciones 2 y 3: en cada partido indicado, `adjust_model_probability`
    con un `RiskConfig` que tiene SOLO ese coeficiente distinto de 0 coincide
    con `clip(p_base + c*x)`, y con todos a 0 devuelve `clip(p_base)`. El
    contexto se reconstruye con el historial final recortado a `d < rd`, que es
    exactamente el `prior` del recorrido incremental."""
    df = fr.df
    idxs = df["idx"].to_numpy()
    dates = df["date"].to_numpy(dtype=str)
    p_h, p_o = df["p_h2h"].to_numpy(float), df["p_over"].to_numpy(float)
    p_s1, p_s2 = df["p_s1"].to_numpy(float), df["p_s2"].to_numpy(float)
    s1, s2, L = df["s1"].to_numpy(float), df["s2"].to_numpy(float), df["L"].to_numpy(float)
    xs = {k: np.nan_to_num(df[f"x{k}"].to_numpy(float), nan=0.0) for k in ADJ_IDS}
    risk0 = risk_with()
    risks = {k: risk_with(**{COEF_NAME[k]: c}) for k, c in coefs.items()}
    max_dev, n = 0.0, 0

    def chk(got: float, want: float, what: str, pos: int) -> None:
        nonlocal max_dev
        d = abs(got - want)
        max_dev = max(max_dev, d)
        if d > atol:
            raise SystemExit(f"PARIDAD 2/3 ROTA ({what}, fila {pos}): {got!r} != {want!r} (dif {d:.3e}).")

    for pos in positions:
        pos = int(pos)
        r = fr.ordered[int(idxs[pos])]
        home, away, rd = r["home"], r["away"], str(dates[pos])
        prior = _prior_games(fr.team_hist, fr.norm(home), fr.norm(away), rd)
        ctx = build_adjustment_context(home, away, rd, prior, risk0, fr.norm)
        # aserto 3: todo a 0 -> clip(p_base)
        chk(_layer_p(p_h[pos], "h2h", home, None, home, away, ctx, risk0), float(clip_p(p_h[pos])), "cero h2h", pos)
        chk(_layer_p(p_o[pos], "totals", "Over", L[pos], home, away, ctx, risk0), float(clip_p(p_o[pos])), "cero over", pos)
        chk(_layer_p(p_s1[pos], "spreads", home, s1[pos], home, away, ctx, risk0), float(clip_p(p_s1[pos])), "cero s1", pos)
        for k, c in coefs.items():
            rk = risks[k]
            x = xs[k][pos]
            if DECISION[k] == "h2h":
                chk(_layer_p(p_h[pos], "h2h", home, None, home, away, ctx, rk),
                    float(clip_p(p_h[pos] + c * x)), f"adj{k} h2h", pos)
                if k in SPREAD_RESTRICTED:
                    chk(_layer_p(p_s1[pos], "spreads", home, s1[pos], home, away, ctx, rk),
                        float(clip_p(p_s1[pos] + c * x)), f"adj{k} spread1", pos)
                    if math.isfinite(s2[pos]):
                        chk(_layer_p(p_s2[pos], "spreads", home, s2[pos], home, away, ctx, rk),
                            float(clip_p(p_s2[pos] + c * x)), f"adj{k} spread2", pos)
                else:  # adj 3: el codigo no lo aplica a spreads
                    chk(_layer_p(p_s1[pos], "spreads", home, s1[pos], home, away, ctx, rk),
                        float(clip_p(p_s1[pos])), f"adj{k} spread (inerte)", pos)
            else:
                chk(_layer_p(p_o[pos], "totals", "Over", L[pos], home, away, ctx, rk),
                    float(clip_p(p_o[pos] + c * x)), f"adj{k} over", pos)
            n += 1
    return {"partidos": int(len(positions)), "comprobaciones": n, "comprobaciones_c0": 3 * int(len(positions)), "max_desviacion": max_dev,
            "coeficientes": {str(k): v for k, v in coefs.items()}, "tolerancia": atol}


# ------------------------------------------------------- datos por liga (arrays) --
def fold_index(dates: np.ndarray, folds: dict[str, dict[str, str]]) -> np.ndarray:
    out = np.full(len(dates), -1, dtype=int)
    for k, f in enumerate(folds.values()):
        out[(dates >= f["test_start"]) & (dates <= f["test_end"])] = k
    return out


class LeagueData:
    """Arrays de un `Frame` y las particiones de la liga."""

    def __init__(self, df: pd.DataFrame, league: str, folds: dict[str, dict[str, str]]) -> None:
        self.df, self.league, self.folds = df, league, folds
        self.dates = df["date"].to_numpy(dtype=str)
        self.fold_of = fold_index(self.dates, folds)
        self.in_test = self.fold_of >= 0
        self.x = {k: df[f"x{k}"].to_numpy(float) for k in ADJ_IDS}
        self.has_outcomes = "y_h2h" in df.columns

    def decision(self, adj: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(p_base sin recortar, y, valido) del mercado de decision."""
        df = self.df
        if DECISION[adj] == "h2h":
            p, y = df["p_h2h"].to_numpy(float), df["y_h2h"].to_numpy(float)
            valid = np.isfinite(y) & np.isfinite(p)
        else:
            p, tot, line = df["p_over"].to_numpy(float), df["total"].to_numpy(float), df["L"].to_numpy(float)
            y = (tot > line).astype(float)
            valid = np.isfinite(p) & (tot != line)
        return p, np.where(valid, y, 0.0), valid

    def spread_lines(self) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """[(p, y, valido)] por linea de spread de la liga (1 en NBA/NFL, 2 en NHL/MLB)."""
        df = self.df
        out = []
        margin = df["margin"].to_numpy(float)
        for pcol, scol in (("p_s1", "s1"), ("p_s2", "s2")):
            s = df[scol].to_numpy(float)
            if not np.isfinite(s).any():
                continue
            p = df[pcol].to_numpy(float)
            valid = np.isfinite(p) & np.isfinite(s) & (margin != -s)
            out.append((p, np.where(valid, (margin > -s).astype(float), 0.0), valid))
        return out


def fold_coefficients(L: LeagueData, adj: int) -> tuple[list[float], list[float]]:
    """(c por particion, a por particion) estimados SOLO con el entrenamiento
    de la particion (tras el warmup, hasta el dia anterior al test)."""
    p, y, valid = L.decision(adj)
    x = np.nan_to_num(L.x[adj], nan=0.0)
    cs, as_ = [], []
    for f in L.folds.values():
        tr = valid & (L.dates <= f["train_end"])
        if not tr.any():
            raise SystemExit(f"adj{adj} {L.league}: entrenamiento vacio en la particion {f}.")
        cs.append(fit_c(p[tr], x[tr], y[tr]))
        as_.append(fit_a(p[tr], y[tr]))
    return cs, as_


def evaluate_cell(L: LeagueData, adj: int) -> dict:
    """Una celda (ajuste x liga): c y a por particion, Delta de los afectados
    (criterio 1 y 2), ECE (3), T frente a C (5) y Delta de spreads (6).
    Devuelve ademas `_w` (arrays de trabajo) y `_series` (para el bootstrap)."""
    p, y, valid = L.decision(adj)
    x_raw = L.x[adj]
    x = np.nan_to_num(x_raw, nan=0.0)
    cs, as_ = fold_coefficients(L, adj)
    fo = L.fold_of
    c_row = np.where(fo >= 0, np.asarray(cs)[np.maximum(fo, 0)], 0.0)
    a_row = np.where(fo >= 0, np.asarray(as_)[np.maximum(fo, 0)], 0.0)
    pB, pT, pC = clip_p(p), clip_p(p + c_row * x), clip_p(p + a_row)
    llB, llT, llC = ll_vec(pB, y), ll_vec(pT, y), ll_vec(pC, y)
    tv = L.in_test & valid
    aff = tv & np.isfinite(x_raw) & (x_raw != 0.0)
    res: dict = {"ajuste": adj, "liga": L.league, "mercado": DECISION[adj], "canal": CHANNEL[adj],
                 "c": cs, "a": as_, "n_test": int(tv.sum()), "n_afectados": int(aff.sum()),
                 "particiones": {}}
    d_all = llT - llB
    res["delta_afectados"] = float(d_all[aff].mean()) if aff.any() else None
    fold_deltas: list[float | None] = []
    for k, name in enumerate(L.folds):
        fa = aff & (fo == k)
        fd = float(d_all[fa].mean()) if fa.any() else None
        fold_deltas.append(fd)
        ft = tv & (fo == k)
        res["particiones"][name] = {"c": cs[k], "a": as_[k], "n_test": int(ft.sum()),
                                    "n_afectados": int(fa.sum()), "delta_afectados": fd,
                                    "log_loss_base": float(llB[ft].mean()) if ft.any() else None,
                                    "log_loss_T": float(llT[ft].mean()) if ft.any() else None,
                                    "log_loss_C": float(llC[ft].mean()) if ft.any() else None}
    res["delta_por_particion"] = fold_deltas
    res["ece_base"] = float(expected_calibration_error(pB[tv], y[tv])) if tv.any() else None
    res["ece_T"] = float(expected_calibration_error(pT[tv], y[tv])) if tv.any() else None
    res["log_loss_base"] = float(llB[tv].mean()) if tv.any() else None
    res["log_loss_T"] = float(llT[tv].mean()) if tv.any() else None
    res["log_loss_C"] = float(llC[tv].mean()) if tv.any() else None
    res["delta_T_menos_C"] = float((llT - llC)[tv].mean()) if tv.any() else None
    series: dict[str, tuple[np.ndarray, np.ndarray]] = {
        "delta_afectados": (np.where(aff, d_all, 0.0), aff.astype(float)),
        "T_menos_C": (np.where(tv, llT - llC, 0.0), tv.astype(float)),
    }
    # criterio 6: spreads (media de las lineas con el mismo peso por partido)
    res["delta_spread"] = None
    if adj in SPREAD_RESTRICTED:
        lines = L.spread_lines()
        valid_all = np.ones(len(p), dtype=bool)
        d_sum = np.zeros(len(p))
        per_line = []
        for lp, ly, lv in lines:
            d_line = np.where(lv, ll_vec(clip_p(lp + c_row * x), ly) - ll_vec(clip_p(lp), ly), 0.0)
            d_sum += d_line
            valid_all &= lv
            per_line.append(float(d_line[L.in_test & lv].mean()) if (L.in_test & lv).any() else None)
        d_sp = d_sum / max(1, len(lines))
        sv = L.in_test & valid_all
        res["delta_spread"] = float(d_sp[sv].mean()) if sv.any() else None
        res["delta_spread_por_linea"] = per_line
        res["n_spread"] = int(sv.sum())
        series["delta_spread"] = (np.where(sv, d_sp, 0.0), sv.astype(float))
    res["_series"] = series
    res["_w"] = {"p": p, "y": y, "valid": valid, "x": x, "x_raw": x_raw, "pB": pB, "pT": pT, "pC": pC,
                 "llB": llB, "llT": llT, "llC": llC, "tv": tv, "aff": aff, "c_row": c_row}
    return res


def decide(res: dict, holm_rejects: bool) -> dict:
    """Criterios 1-7 (seccion 10). Todos a la vez; si falla uno, RECHAZA."""
    d = res.get("delta_afectados")
    fd = res.get("delta_por_particion") or []
    crit = {
        "1_delta_afectados_menor_igual_margen": d is not None and d <= -DEFAULT_ADJ_MARGIN,
        "2_delta_negativo_en_cada_particion": bool(fd) and all(v is not None and v < 0 for v in fd),
        "3_ece_T_no_peor_que_base": (res.get("ece_T") is not None and res.get("ece_base") is not None
                                      and res["ece_T"] <= res["ece_base"]),
        "4_c_positivo_en_todas": bool(res["c"]) and all(c > 0 for c in res["c"]),
        "5_T_mejor_que_C": res.get("delta_T_menos_C") is not None and res["delta_T_menos_C"] < 0,
        "6_spreads_no_empeoran": (True if res["ajuste"] not in SPREAD_RESTRICTED else
                                  (res.get("delta_spread") is not None and res["delta_spread"] <= 0)),
        "7_holm_rechaza": bool(holm_rejects),
    }
    return {"criterios": crit, "veredicto": "ACEPTA" if all(crit.values()) else "RECHAZA"}


def cell_name(adj: int, league: str) -> str:
    return f"adj{adj}_{league}"


def run_league_cells(L: LeagueData) -> dict[int, dict]:
    cells = {adj: evaluate_cell(L, adj) for adj in ADJ_IDS}
    dates_t = L.dates[L.in_test]
    stats: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for adj, c in cells.items():
        for name, (num, den) in c["_series"].items():
            stats[f"{adj}|{name}"] = (num[L.in_test], den[L.in_test])
    boot = bootstrap_dias(dates_t, stats)
    for adj, c in cells.items():
        c["bootstrap"] = {name: boot[f"{adj}|{name}"] for name in c["_series"]}
        c["se_delta"] = c["bootstrap"]["delta_afectados"]["se"]
        c["p"] = p_value(c["delta_afectados"], c["se_delta"])
    return cells


# ------------------------------------------------------ informes secundarios --
def _tercile_report(w: dict, x: np.ndarray) -> dict:
    aff = w["aff"]
    if not aff.any():
        return {}
    d = (w["llT"] - w["llB"])
    ax = np.abs(x)
    q1, q2 = np.quantile(ax[aff], [1 / 3, 2 / 3])
    out: dict = {"cortes_abs_x": [float(q1), float(q2)]}
    for name, m in (("T1_bajo", aff & (ax <= q1)), ("T2_medio", aff & (ax > q1) & (ax <= q2)),
                    ("T3_alto", aff & (ax > q2)), ("x_positivo", aff & (x > 0)), ("x_negativo", aff & (x < 0))):
        out[name] = {"n": int(m.sum()), "delta": float(d[m].mean()) if m.any() else None}
    return out


def season_label(date: str, league: str) -> str:
    y, m = int(date[:4]), int(date[5:7])
    return str(y) if league == "mlb" else str(y if m >= 8 else y - 1)


def _by_season(L: LeagueData, w: dict) -> dict:
    d = w["llT"] - w["llB"]
    out: dict = {}
    seasons = np.array([season_label(s, L.league) for s in L.dates])
    for s in sorted(set(seasons[w["aff"]])):
        m = w["aff"] & (seasons == s)
        mark = None
        if L.league in ("nba", "nhl"):
            mark = {"2019": "burbuja 2019-20", "2020": "calendario 2020-21"}.get(s)
        out[s] = {"n": int(m.sum()), "delta": float(d[m].mean()), "marca": mark}
    return out


def _profile_grid(L: LeagueData, adj: int, c_star: float) -> dict:
    p, y, valid = L.decision(adj)
    x = np.nan_to_num(L.x[adj], nan=0.0)
    grid = np.linspace(-2 * c_star, 4 * c_star, 25)
    out: dict = {"c_star": c_star, "rejilla": grid.tolist(), "particiones": {}}
    for name, f in L.folds.items():
        tr = valid & (L.dates <= f["train_end"])
        loss = np.array([float(np.mean(ll_vec(clip_p(p[tr] + c * x[tr]), y[tr]))) for c in grid])
        j = int(np.argmin(loss))
        mono = bool(np.all(np.diff(loss[:j + 1]) <= 1e-15) and np.all(np.diff(loss[j:]) >= -1e-15))
        out["particiones"][name] = {"log_loss_entrenamiento": loss.tolist(), "argmin_c": float(grid[j]),
                                    "monotono_a_ambos_lados": mono}
    return out


def _c_star(L: LeagueData, adj: int) -> float:
    """c* de la seccion 13: mediana entre particiones de 0,032/RMS(x afectados del test)."""
    vals = []
    for k in range(len(L.folds)):
        x = L.x[adj][(L.fold_of == k)]
        x = x[np.isfinite(x) & (x != 0)]
        if len(x):
            vals.append(C_STAR_TARGET / float(np.sqrt(np.mean(x ** 2))))
    return float(np.median(vals)) if vals else float("nan")


def _joint_report(L: LeagueData, adj: int) -> dict:
    p, y, valid = L.decision(adj)
    x = np.nan_to_num(L.x[adj], nan=0.0)
    out: dict = {}
    for name, f in L.folds.items():
        tr = valid & (L.dates <= f["train_end"])
        try:
            a, c = fit_ac(p[tr], x[tr], y[tr])
            out[name] = {"a": a, "c_con_intercepto_controlado": c}
        except RuntimeError as exc:      # no convergencia: se anota, no anula el informe
            out[name] = {"no_converge": str(exc)}
    return out


def _bias_report(L: LeagueData) -> dict:
    out: dict = {}
    mk: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {"h2h": L.decision(2), "totals": L.decision(4)}
    for k, trip in enumerate(L.spread_lines()):
        mk[f"spread_linea{k + 1}"] = trip
    for mname, (p, y, v) in mk.items():
        out[mname] = {}
        for k, name in enumerate(L.folds):
            m = v & (L.fold_of == k)
            out[mname][name] = ({"n": int(m.sum()), "bias": float(clip_p(p[m]).mean() - y[m].mean())}
                                if m.any() else {"n": 0, "bias": None})
    return out


def _coverage_report(L: LeagueData) -> dict:
    t = L.in_test
    out: dict = {"partidos_test": int(t.sum()), "neutrales_test": int(L.df["neutral"].to_numpy(bool)[t].sum()),
                 "exhibicion": "no disponible en ResultsStore"}
    for adj in ADJ_IDS:
        x = L.x[adj][t]
        out[f"adj{adj}"] = {"afectados": int((np.isfinite(x) & (x != 0)).sum()),
                            "x_cero": int((np.isfinite(x) & (x == 0)).sum()),
                            "none_por_falta_de_historia": int((~np.isfinite(x)).sum())}
    return out


def _collinearity_report(L: LeagueData, cells: dict[int, dict], verdicts: dict[int, str]) -> dict:
    out: dict = {}
    for market, members in (("h2h", (2, 3, 8, 9)), ("totals", (4, 10))):
        acc = [k for k in members if verdicts.get(k) == "ACEPTA"]
        if len(acc) < 2:
            continue
        p, y, valid = L.decision(acc[0])
        tv = L.in_test & valid
        pj = p.copy()
        union = np.zeros(len(p), dtype=bool)
        for k in acc:
            c_final = cells[k]["c"][-1]
            pj = pj + c_final * np.nan_to_num(L.x[k], nan=0.0)
            union |= np.isfinite(L.x[k]) & (L.x[k] != 0)
        d = ll_vec(clip_p(pj), y) - ll_vec(clip_p(p), y)
        indiv = {str(k): float(((cells[k]["_w"]["llT"] - cells[k]["_w"]["llB"])[tv]).mean()) for k in acc}
        out[market] = {"celdas": acc, "delta_conjunto_test": float(d[tv].mean()),
                       "delta_conjunto_union_afectados": float(d[tv & union].mean()) if (tv & union).any() else None,
                       "delta_individual_test": indiv}
    return out


def captured_lines(results: list[dict], league: str, data_root: Path) -> dict:
    """{(fecha, home, away, game_id): (spread_del_local, total)} con la linea
    principal del consenso (`_pick_main_lines`) de las cuotas capturadas
    (`load_closing_odds`), emparejadas como `roi_engine`. Informe 7."""
    odds = load_closing_odds(data_root, league)
    if not odds:
        return {}
    match_norm = get_team_normalizer(league)
    idx = _match_index(odds, False, match_norm)
    used: set[str] = set()
    out: dict = {}
    for r in sorted(results, key=lambda r: (str(r.get("date", "")), str(r.get("home", "")),
                                            str(r.get("away", "")), str(r.get("game_id", "")),
                                            str(r.get("home_score", "")), str(r.get("away_score", "")))):  # = roi_engine.backtest_league l. 289-294
        eo = _match_result(r, idx, used, False, match_norm)
        if eo is None:
            continue
        spread, total = _pick_main_lines(eo)
        if spread is not None and match_norm(r["home"]) != match_norm(eo.event.home):
            spread = -spread
        out[(str(r.get("date", ""))[:10], str(r["home"]), str(r["away"]), str(r.get("game_id", "")))] = (spread, total)
    return out


def _captured_report(L: LeagueData, cells: dict[int, dict]) -> dict:
    df = L.df
    if "cap_t" not in df.columns and "cap_s" not in df.columns:
        return {"n_emparejados": 0}
    margin = df["margin"].to_numpy(float)
    total = df["total"].to_numpy(float)
    out: dict = {}
    cap_t = df["cap_t"].to_numpy(float) if "cap_t" in df.columns else np.full(len(df), np.nan)
    cap_s = df["cap_s"].to_numpy(float) if "cap_s" in df.columns else np.full(len(df), np.nan)
    out["n_emparejados"] = int((np.isfinite(cap_t) | np.isfinite(cap_s)).sum())
    for adj in ADJ_IDS:
        c = cells[adj]["c"][-1]          # c de la ultima particion
        if DECISION[adj] == "totals":
            xc = df[f"x{adj}_cap"].to_numpy(float) if f"x{adj}_cap" in df.columns else np.full(len(df), np.nan)
            p = df["p_cap_over"].to_numpy(float) if "p_cap_over" in df.columns else np.full(len(df), np.nan)
            ok = np.isfinite(cap_t) & np.isfinite(p) & (total != cap_t)
            y = (total > cap_t).astype(float)
            x = np.nan_to_num(xc, nan=0.0)
        else:
            p, y, ok = cells[adj]["_w"]["p"], cells[adj]["_w"]["y"], cells[adj]["_w"]["valid"]
            x = np.nan_to_num(L.x[adj], nan=0.0)
            ok = ok & (np.isfinite(cap_s) | np.isfinite(cap_t))
        if not ok.any():
            out[f"adj{adj}"] = {"n": 0}
            continue
        d = ll_vec(clip_p(p + c * x), y) - ll_vec(clip_p(p), y)
        entry = {"c_ultima_particion": c, "n": int(ok.sum()), "delta_log_loss": float(d[ok].mean())}
        if adj in SPREAD_RESTRICTED and "p_cap_cov" in df.columns:
            pc = df["p_cap_cov"].to_numpy(float)
            okc = np.isfinite(cap_s) & np.isfinite(pc) & (margin != -cap_s)
            if okc.any():
                yc = (margin > -cap_s).astype(float)
                dc = ll_vec(clip_p(pc + c * np.nan_to_num(L.x[adj], nan=0.0)), yc) - ll_vec(clip_p(pc), yc)
                entry["spread_capturado"] = {"n": int(okc.sum()), "delta_log_loss": float(dc[okc].mean())}
        out[f"adj{adj}"] = entry
    out["nota"] = "log loss frente al resultado en la submuestra con cuotas; NO es ventaja sobre el mercado."
    return out


def _halflife_report(results: list[dict], league: str, family: str, league_params: dict | None,
                     cells: dict[int, dict], L: LeagueData) -> dict:
    """Informe 8: Delta de la base con `scoring_half_life_days` de produccion
    frente a la base con `scoring_half_life_days = 0`, sobre el test combinado y
    en la L_i de la BASE (un segundo frame con half-life 0 aporta mu_alt;
    `p_over_alt = normal_total_probs(mu_alt, total_sigma, L_base)`). Se informa
    en todo el test y en los afectados del ajuste 4, junto al Delta del
    termino 4. Solo describe. Solo ligas con half-life > 0 (NBA)."""
    params = resolved_adapter_params(league, league_params)
    hl = params.get("scoring_half_life_days", 0.0)
    if not hl:
        return {"aplica": False, "motivo": "scoring_half_life_days = 0 en esta liga"}
    alt = dict(league_params or {})
    alt["scoring_half_life_days"] = 0.0
    fr_alt = build_frame(results, league, family, alt, with_outcomes=False, feature_from="9999")
    mu_alt = fr_alt.df.set_index("idx")["mu"]
    df = L.df
    if not np.array_equal(df["idx"].to_numpy(), fr_alt.df["idx"].to_numpy()):
        raise RuntimeError("informe 8: los frames base y alternativo no estan alineados.")
    sigma = float(params["total_sigma"])
    line = df["L"].to_numpy(float)
    p_alt = np.array([dist.normal_total_probs(float(m), sigma, float(ln))["over"]
                      for m, ln in zip(mu_alt.loc[df["idx"]].to_numpy(float), line)])
    p, y, valid = L.decision(4)
    tv = L.in_test & valid
    d = ll_vec(clip_p(p), y) - ll_vec(clip_p(p_alt), y)       # con half-life - sin half-life
    aff = cells[4]["_w"]["aff"]
    return {"aplica": True, "scoring_half_life_days": hl,
            "delta_con_menos_sin_half_life_test": float(d[tv].mean()), "n_test": int(tv.sum()),
            "delta_con_menos_sin_half_life_afectados_adj4": float(d[aff].mean()) if aff.any() else None,
            "n_afectados_adj4": int(aff.sum()),
            "delta_termino_4_afectados": cells[4]["delta_afectados"],
            "nota": "L_i de la base; p_over_alt con mu del frame sin half-life. Solo describe."}


TRANSFER_EVAL_FROM = {"wnba": "2025-01-01"}    # informe 9: WNBA 2025-26 (estado y features con todo el historico)


def _transfer_report(source_cells: dict[int, dict], target: str, data_root: Path) -> dict:
    """Informe 9: c de la ultima particion de la liga fuente aplicado SIN
    reajustar a una liga secundaria (todo su historico tras el warmup)."""
    results, lp, proc = load_league(target, data_root, assert_params=False)
    fam = _league_meta(target)["family"]
    fr = build_frame(results, target, fam, lp, with_outcomes=True)
    eval_from = TRANSFER_EVAL_FROM.get(target, "0000-00-00")
    folds = {"todo": {"train_end": "0000-00-00", "test_start": eval_from, "test_end": "9999-99-99"}}
    Lt = LeagueData(fr.df, target, folds)
    out: dict = {"filas": proc["filas_leidas"], "evaluados": int(Lt.in_test.sum()), "evaluar_desde": eval_from,
                 "filas_antes_dedupe_game_id": proc["filas_antes_dedupe_game_id"],
                 "descartadas_dedupe_game_id": proc["descartadas_dedupe_game_id"]}
    for adj in ADJ_IDS:
        c = source_cells[adj]["c"][-1]
        p, y, valid = Lt.decision(adj)
        x_raw = Lt.x[adj]
        valid = valid & Lt.in_test
        aff = valid & np.isfinite(x_raw) & (x_raw != 0)
        if not aff.any():
            out[f"adj{adj}"] = {"n_afectados": 0, "c": c}
            continue
        x = np.nan_to_num(x_raw, nan=0.0)
        d = ll_vec(clip_p(p + c * x), y) - ll_vec(clip_p(p), y)
        out[f"adj{adj}"] = {"c": c, "n_afectados": int(aff.sum()), "delta_afectados": float(d[aff].mean())}
    return out


# ------------------------------------------------------------- modo --pre --
INGEST_AFTER = "2026-09-27"


def ingestion_report(league: str, data_root: Path, folds: dict[str, dict[str, str]]) -> dict:
    """Enmienda 1(f), solo RECUENTOS (nunca marcadores): por particion de test,
    filas con `ingested_at` posterior al 2026-09-27 y duplicados por
    (date, home, away) y por game_id. `ResultsStore.load` descarta
    `ingested_at`, asi que se lee aparte; si el fichero no la tiene, se informa."""
    path = ResultsStore(data_root).path(league)
    if not path.exists():
        return {"error": "fichero ausente"}
    keep = {"date", "home", "away", "game_id", "ingested_at"}
    df = pd.read_csv(path, usecols=lambda c: c in keep, dtype=str)
    df = df[df["date"].str[:10] <= CUTOFF]
    has_ing = "ingested_at" in df.columns
    gid = df["game_id"].fillna("") if "game_id" in df.columns else pd.Series([""] * len(df), index=df.index)
    out: dict = {"ingested_at": "disponible" if has_ing else "no disponible"}
    for name, f in folds.items():
        m = ((df["date"].str[:10] >= f["test_start"]) & (df["date"].str[:10] <= f["test_end"])).to_numpy()
        sub = df[m]
        g = gid[m]
        entry: dict = {"filas": int(m.sum()),
                       "duplicados_date_home_away": int(sub.duplicated(subset=["date", "home", "away"]).sum()),
                       "duplicados_game_id": int(g[g != ""].duplicated().sum())}
        if has_ing:
            ing = sub["ingested_at"].fillna("").str[:10]
            entry["ingestadas_despues_2026_09_27"] = int((ing > INGEST_AFTER).sum())
            entry["ingestadas_el_2026_09_27"] = int((ing == INGEST_AFTER).sum())
        else:
            entry["ingestadas_despues_2026_09_27"] = "no disponible"
            entry["ingestadas_el_2026_09_27"] = "no disponible"
        out[name] = entry
    return out


def pre_league(league: str, data_root: Path) -> dict:
    results, lp, proc = load_league(league, data_root)
    family = FAMILY[league]
    folds = FOLDS[league]
    fr = build_frame(results, league, family, lp, with_outcomes=False)
    df = fr.df
    L = LeagueData(df, league, folds)
    out: dict = {"procedencia": proc,
                 "filas_hasta_corte": len(results), "filas_referencia_seccion5": REF_ROWS[league],
                 "diferencia_filas": len(results) - REF_ROWS[league],
                 "evaluados": int(len(df)), "particiones": {}}
    if fr.max_identity_dev is not None:
        out["nhl_identidad_lambda_max_desviacion"] = fr.max_identity_dev
    for k, (name, f) in enumerate(folds.items()):
        m = L.fold_of == k
        days = int(len(np.unique(L.dates[m])))
        ref_g, ref_d = REF_FOLD_GAMES[league][name], REF_FOLD_DAYS[league][name]
        entry: dict = {"partidos": int(m.sum()), "dias": days, "ref_partidos": ref_g, "ref_dias": ref_d,
                       "coincide_partidos": int(m.sum()) == ref_g, "coincide_dias": days == ref_d}
        for adj in ADJ_IDS:
            x = L.x[adj][m]
            f_ = np.isfinite(x) & (x != 0)
            entry[f"adj{adj}"] = {"afectados": int(f_.sum()), "media_x": float(np.mean(x[f_])) if f_.any() else None,
                                  "rms_x": float(np.sqrt(np.mean(x[f_] ** 2))) if f_.any() else None}
        out["particiones"][name] = entry
    t = L.in_test
    comb: dict = {}
    for adj in ADJ_IDS:
        x = L.x[adj][t]
        f_ = np.isfinite(x) & (x != 0)
        n_aff = int(f_.sum())
        rms_by_fold = [e[f"adj{adj}"]["rms_x"] for e in out["particiones"].values()]
        c_star = [C_STAR_TARGET / r for r in rms_by_fold if r]
        ref = REF_AFFECTED[league][adj]
        expected_different = league == "mlb" and adj in MLB_CHANGING
        comb[f"adj{adj}"] = {
            "afectados": n_aff, "ref_seccion13": ref, "diferencia": n_aff - ref,
            "coincide": n_aff == ref, "esperado_distinto_por_abridor_y_parque": expected_different,
            "c_star_mediana": float(np.median(c_star)) if c_star else None,
            "media_x": float(np.mean(x[f_])) if f_.any() else None,
            "desv_x": float(np.std(x[f_])) if f_.any() else None,
            "rms_x": float(np.sqrt(np.mean(x[f_] ** 2))) if f_.any() else None,
            "no_disponibles": int((~np.isfinite(x)).sum()),
        }
    out["test_combinado"] = comb
    out["ingesta"] = ingestion_report(league, data_root, folds)

    def corr(a: str, b: str) -> float | None:
        xa, xb = L.df[a].to_numpy(float)[t], L.df[b].to_numpy(float)[t]
        ok = np.isfinite(xa) & np.isfinite(xb)
        return float(np.corrcoef(xa[ok], xb[ok])[0, 1]) if ok.sum() > 2 else None

    got = (corr("x2", "x9"), corr("x2", "x8"), corr("x8", "x9"), corr("x3", "x9"), corr("x4", "x10"))
    out["correlaciones"] = {n: {"valor": g, "ref_seccion13": r,
                                "coincide_3_decimales": g is not None and abs(round(g, 3) - r) < 1e-9,
                                "esperado_distinto_por_abridor_y_parque": league == "mlb" and n == "x4~x10"}
                            for n, g, r in zip(CORR_NAMES, got, REF_CORR[league])}
    x4, x7 = L.df["x4"].to_numpy(float)[t], L.df["x7"].to_numpy(float)[t]
    x9, x6 = L.df["x9"].to_numpy(float)[t], L.df["x6"].to_numpy(float)[t]
    ok7, ok6 = np.isfinite(x4) & np.isfinite(x7), np.isfinite(x9) & np.isfinite(x6)
    out["identidades"] = {
        "max_abs_x4_menos_x7": float(np.max(np.abs(x4[ok7] - x7[ok7]))) if ok7.any() else None,
        "max_abs_x9_medio_menos_x6": float(np.max(np.abs(x9[ok6] / 2.0 - x6[ok6]))) if ok6.any() else None,
        "nota": "seccion 2.3 y 2.4: ambas ~1e-14 con las ventanas vigentes"}
    Lc = df["L"].to_numpy(float)
    out["lineas_L"] = {"media": float(np.mean(Lc)), "minimo": float(np.min(Lc)), "maximo": float(np.max(Lc)),
                       "sha256_vector": hashlib.sha256(np.ascontiguousarray(Lc).tobytes()).hexdigest()}
    return out


def informe_pre(data_root: Path) -> dict:
    """Seccion 16 + Enmienda 1(g). No calcula ninguna perdida ni empareja
    features con desenlaces (`build_frame(with_outcomes=False)`)."""
    head = git_head(_WORKTREE_ROOT)
    status = git_status_porcelain(_WORKTREE_ROOT)
    check_git_clean(status, "todo el repositorio (Enmienda 1(b))")
    out: dict = {"git_head": head, "git_status_porcelain": status, "snapshot_root": str(data_root),
                 "corte_datos": CUTOFF, "manifiesto": input_manifest(data_root),
                 "config_sha256": config_hashes(), "ventanas": risk_windows(),
                 "parametros_resueltos": resolved_params_report(LEAGUES),
                 "parametros_secundarias_sin_asercion": resolved_params_report(
                     [*SECONDARY_BASKET, *SECONDARY_FOOTBALL, *secondary_soccer_leagues()]),
                 "ligas": {}}
    out["sha256"] = {lg: None for lg in LEAGUES}
    for lg in LEAGUES:
        out["ligas"][lg] = pre_league(lg, data_root)
        out["sha256"][lg] = out["ligas"][lg]["procedencia"].get("sha256")
    return out


# ----------------------------------------------------------- modo --parity-only --
def parity_only(data_root: Path, leagues: tuple[str, ...], stride: int = 1) -> dict:
    out: dict = {"modo": "parity-only", "stride_features": stride, "ligas": {}}
    for lg in leagues:
        t0 = time.perf_counter()
        results, lp, proc = load_league(lg, data_root)
        if not results:
            out["ligas"][lg] = {"resultado": "SIN RESULTADOS HISTORICOS"}
            continue
        folds = FOLDS[lg]
        start = min(f["test_start"] for f in folds.values())
        fr = build_frame(results, lg, FAMILY[lg], lp, with_outcomes=True, parity=True, feature_from=start,
                         feature_stride=stride)
        L = LeagueData(fr.df, lg, folds)
        p1 = assert_parity_engine(fr, results, lg, FAMILY[lg], lp)
        pos = np.flatnonzero(L.in_test & fr.df["feat"].to_numpy(bool))
        # Una sola pasada: el aserto 3 (todos los coeficientes a 0 -> clip(p_base))
        # se comprueba SIEMPRE en cada partido, ademas del aserto 2 (c arbitrario).
        p2 = assert_parity_layer(fr, pos, dict(PROBE_C))
        out["ligas"][lg] = {"resultado": "PARIDAD OK", "paridad1": p1,
                            "paridad2_y_3_c_arbitrario_y_c0": p2, "partidos_test": int(len(pos)),
                            "segundos": time.perf_counter() - t0}
    return out


# ------------------------------------------------------------- modo completo --
def _check_pre_provenance(pre: dict, head_now: str | None, manifest_now: dict, cfg_now: dict,
                          params_now: dict) -> None:
    if pre.get("git_head") is None:
        raise SystemExit("--pre-json no registra 'git_head'. El modo completo aborta.")
    if head_now is None:
        raise SystemExit("No se pudo obtener 'git rev-parse HEAD'. El modo completo aborta.")
    if pre["git_head"] != head_now:
        raise SystemExit(f"HEAD DE GIT CAMBIO: --pre-json registra {pre['git_head']} y el HEAD actual es "
                         f"{head_now}. El modo completo aborta.")
    prev = pre.get("manifiesto")
    if not prev:
        raise SystemExit("--pre-json no registra 'manifiesto' de hashes. El modo completo aborta.")
    if set(prev) != set(manifest_now):
        raise SystemExit("HASH DE ENTRADA: el conjunto de ficheros leidos difiere del de --pre: "
                         f"{sorted(set(prev) ^ set(manifest_now))}. El modo completo aborta.")
    changed = [k for k in prev if prev[k].get("sha256") != manifest_now[k].get("sha256")
               or prev[k].get("filas") != manifest_now[k].get("filas")]
    if changed:
        raise SystemExit(f"HASH DE ENTRADA CAMBIO en {changed}. El modo completo aborta: los datos ya no "
                         "son los que midio --pre.")
    if pre.get("config_sha256") != cfg_now:
        raise SystemExit("SHA-256 de ratings.yaml/default.yaml distinto del de --pre. El modo completo aborta.")
    if _clean(pre.get("parametros_resueltos")) != _clean(params_now):
        raise SystemExit("Parametros resueltos distintos de los de --pre. El modo completo aborta.")


def run_full(data_root: Path) -> dict:
    out: dict = {"procedencia": {"corte_datos": CUTOFF, "snapshot_root": str(data_root)}, "ligas": {},
                 "paridad": {}, "secundarios": {}}
    frames: dict[str, tuple[Frame, LeagueData, list[dict], dict | None]] = {}
    cells_by_league: dict[str, dict[int, dict]] = {}
    cap_errors: dict[str, dict | None] = {}
    for lg in LEAGUES:
        results, lp, proc = load_league(lg, data_root)
        out["procedencia"][lg] = proc
        cap = _safe_informe(f"cuotas_capturadas_{lg}", lambda lg=lg, results=results: captured_lines(results, lg, data_root))
        cap_errors[lg] = cap if _is_error(cap) else None      # se conserva el error (tipo + traceback)
        cap = {} if cap_errors[lg] else cap
        fr = build_frame(results, lg, FAMILY[lg], lp, with_outcomes=True, parity=True, captured=cap)
        L = LeagueData(fr.df, lg, FOLDS[lg])
        p1 = assert_parity_engine(fr, results, lg, FAMILY[lg], lp)
        cells = run_league_cells(L)
        pos = np.flatnonzero(L.in_test)
        coefs = {adj: cells[adj]["c"][-1] for adj in ADJ_IDS}
        p2 = assert_parity_layer(fr, pos, coefs)     # incluye el aserto 3 (c = 0) en cada partido
        out["paridad"][lg] = {"motor": p1, "capa_c_ultima_particion_y_c0": p2}
        frames[lg] = (fr, L, results, lp)
        cells_by_league[lg] = cells
    # Holm sobre las 24 celdas (seccion 11)
    pvals = {cell_name(adj, lg): cells_by_league[lg][adj]["p"] for lg in LEAGUES for adj in ADJ_IDS}
    if len(pvals) != K_FAMILY:
        raise SystemExit(f"La familia de Holm tiene {len(pvals)} celdas y debe tener {K_FAMILY}.")
    hol = holm(pvals)
    out["holm"] = hol
    verdicts: dict[str, dict[int, str]] = {lg: {} for lg in LEAGUES}
    for lg in LEAGUES:
        cells_json: dict = {}
        for adj in ADJ_IDS:
            c = cells_by_league[lg][adj]
            dec = decide(c, hol[cell_name(adj, lg)]["rechaza"])
            c["decision"] = dec
            c["p_holm"] = hol[cell_name(adj, lg)]
            verdicts[lg][adj] = dec["veredicto"]
            cells_json[str(adj)] = c
        out["ligas"][lg] = cells_json
    out["veredictos"] = {cell_name(a, lg): verdicts[lg][a] for lg in LEAGUES for a in ADJ_IDS}
    out["n_acepta"] = sum(1 for v in out["veredictos"].values() if v == "ACEPTA")
    # --- informes secundarios (seccion 14) ---------------------------------
    sec: dict = {}
    for lg in LEAGUES:
        fr, L, results, lp = frames[lg]
        cells = cells_by_league[lg]
        s: dict = {}
        s["1_bias_base"] = _safe_informe(f"1_{lg}", lambda: _bias_report(L))
        s["2_estimacion_conjunta"] = _safe_informe(f"2_{lg}", lambda: {str(a): _joint_report(L, a) for a in ADJ_IDS})
        s["3_perfil_rejilla_c"] = _safe_informe(f"3_{lg}", lambda: {
            str(a): _profile_grid(L, a, _c_star(L, a)) for a in ADJ_IDS})
        s["4_terciles_y_signo"] = _safe_informe(f"4_{lg}", lambda: {
            str(a): _tercile_report(cells[a]["_w"], cells[a]["_w"]["x_raw"]) for a in ADJ_IDS})
        s["5_por_temporada"] = _safe_informe(f"5_{lg}", lambda: {
            str(a): _by_season(L, cells[a]["_w"]) for a in ADJ_IDS})
        s["6_colinealidad"] = _safe_informe(f"6_{lg}", lambda: _collinearity_report(L, cells, verdicts[lg]))
        s["7_linea_capturada"] = cap_errors[lg] if cap_errors[lg] else _safe_informe(
            f"7_{lg}", lambda: _captured_report(L, cells))
        s["8_ajuste4_vs_adaptador"] = _safe_informe(f"8_{lg}", lambda: _halflife_report(
            results, lg, FAMILY[lg], lp, cells, L))
        s["10_cobertura"] = _safe_informe(f"10_{lg}", lambda: _coverage_report(L))
        sec[lg] = s
    sec["9_transferencia"] = {
        tgt: _safe_informe(f"9_{tgt}", lambda tgt=tgt, src=src: _transfer_report(cells_by_league[src], tgt, data_root))
        for src, tgts in (("nba", SECONDARY_BASKET), ("nfl", SECONDARY_FOOTBALL)) for tgt in tgts}
    sec["9_futbol_agrupado"] = {"retirado": "Enmienda 2 (2026-10-08)"}
    out["secundarios"] = sec
    return out


# ------------------------------------------------------------------- main --
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pre", action="store_true")
    ap.add_argument("--parity-only", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--pre-json", type=Path, default=None,
                    help="Salida de --pre; el modo completo aborta si HEAD, hashes o parametros difieren.")
    ap.add_argument("--data-root", type=Path, default=None,
                    help="Raiz de datos (<raiz>/data/historical, <raiz>/data/odds): la instantanea de la "
                         "Enmienda 1(g). OBLIGATORIA en --pre y en el modo completo, que abortan si es el "
                         "arbol vivo (sqp.config.ROOT). --parity-only puede usar el arbol vivo por defecto.")
    ap.add_argument("--leagues", default=None, help="Solo con --parity-only: p. ej. nba,nhl.")
    ap.add_argument("--parity-stride", type=int, default=1,
                    help="Solo con --parity-only: calcula features y comprueba la capa en uno de cada N "
                         "partidos de test (por defecto 1 = todos). El modo completo comprueba todos.")
    args = ap.parse_args(argv)

    if args.pre and args.parity_only:
        ap.error("--pre y --parity-only son mutuamente excluyentes.")
    if (args.leagues or args.parity_stride != 1) and not args.parity_only:
        ap.error("--leagues/--parity-stride solo aplican a --parity-only: el modo completo mide las "
                 "cuatro ligas y comprueba todos los partidos.")
    if args.parity_stride < 1:
        ap.error("--parity-stride debe ser >= 1.")
    if args.data_root is None:
        if not args.parity_only:
            ap.error("--data-root es obligatorio y explicito en --pre y en el modo completo (instantanea).")
        args.data_root = DEFAULT_ROOT
    elif not args.parity_only and Path(args.data_root).resolve() == DEFAULT_ROOT.resolve():
        raise SystemExit("--data-root apunta al arbol vivo (sqp.config.ROOT): --pre y el modo completo "
                         "miden SOLO sobre la instantanea de la Enmienda 1(g). Se aborta.")
    elif not args.parity_only and Path(args.data_root).resolve().is_relative_to(
            (DEFAULT_ROOT / "data").resolve()):
        raise SystemExit("--data-root esta dentro de data/ (ignorado por git): la instantanea de la "
                         "Enmienda 1(g) debe quedar fuera de data/. Se aborta.")
    if not args.parity_only and args.out is None:
        ap.error("--out es obligatorio salvo en --parity-only.")
    if args.pre_json and (args.pre or args.parity_only):
        ap.error("--pre-json solo aplica al modo completo.")
    if not args.pre and not args.parity_only and args.pre_json is None:
        ap.error("--pre-json es obligatorio en el modo completo: ejecuta antes --pre --out <pre.json>.")

    t0 = time.perf_counter()
    if args.parity_only:
        leagues = tuple(s.strip() for s in args.leagues.split(",")) if args.leagues else LEAGUES
        bad = [lg for lg in leagues if lg not in LEAGUES]
        if bad:
            ap.error(f"--leagues: {bad} no son ligas que deciden {LEAGUES}.")
        out = parity_only(args.data_root, leagues, args.parity_stride)
        out["segundos"] = time.perf_counter() - t0
        print(json.dumps(_clean(out), indent=2, ensure_ascii=False))
        if args.out:
            args.out.write_text(json.dumps(_clean(out), indent=2, ensure_ascii=False), encoding="utf-8")
        return 0
    if args.pre:
        out = {"modo": "pre (sin desenlaces)", **informe_pre(args.data_root)}
        out["segundos"] = time.perf_counter() - t0
        args.out.write_text(json.dumps(_clean(out), indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"escrito": str(args.out), "git_head": out["git_head"]}, ensure_ascii=False))
        return 0
    # Modo completo: UNA SOLA EJECUCION (seccion 16). Aborta por HEAD, porcelain, hashes o parametros.
    porcelain = git_status_porcelain(_WORKTREE_ROOT, _FULL_GIT_PATHS)
    check_git_clean(porcelain, "src configs scripts/research")
    pre = json.loads(args.pre_json.read_text(encoding="utf-8"))
    manifest, cfg, params = input_manifest(args.data_root), config_hashes(), resolved_params_report(LEAGUES)
    _check_pre_provenance(pre, git_head(_WORKTREE_ROOT), manifest, cfg, params)
    out = {"modo": "completo", "git_head": git_head(_WORKTREE_ROOT),
           "git_status_porcelain_src_configs_scripts_research": porcelain,
           "pre_json_sha256": sha256_of(args.pre_json), "parametros_resueltos": params,
           "manifiesto": manifest, "config_sha256": cfg, **run_full(args.data_root)}
    out["segundos"] = time.perf_counter() - t0
    args.out.write_text(json.dumps(_clean(out), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"escrito": str(args.out), "n_acepta": out["n_acepta"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
