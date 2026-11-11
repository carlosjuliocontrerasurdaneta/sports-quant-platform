"""Revalidacion de `park_bound` de MLB con datos deportivos (log loss y Brier, SIN cuotas).

Pre-registro `docs/research/2026-11-10-preregistro-park-bound-mlb.md`, que es el
CONTRATO de este script (seccion 14). Mide si el factor de parque acotado por
`park_bound` mejora la probabilidad del modelo en los TOTALES frente al desenlace
y que cota elige un procedimiento que solo mira el pasado. NO mide ventaja sobre
el mercado ni rentabilidad. NO importa `sqp.backtesting.roi_engine` y NO lee
cuotas en ningun modo (candado P8(a) del informe 09; un test lo fija). Para no
arrastrar `roi_engine` tampoco importa `measure_adjustment_battery`: las utilidades
que necesita estan copiadas aqui (hashes, git, bootstrap por dias, Nelder-Mead).

Modos (todos exigen `--data-root`, una INSTANTANEA fuera del repo y de cualquier
checkout git; el modo completo rechaza un `--out` ya existente: una sola ejecucion):

  --pre          HEAD, `git status --porcelain` (vacio en TODO el repo), manifiesto
                 de hashes, parametros resueltos (aserto), recuentos, distribucion de
                 f_i, fraccion de partidos recortados por cota, clases de equivalencia,
                 Delta p_i(b) y escenarios KL (seccion 9). NO lee ningun desenlace:
                 los marcadores solo entran al modelo por `observe`.
  --parity-only  Asertos de paridad de la seccion 5.2 contra `walk_forward_backtest`
                 (1e-12). No mide nada. `--parity-stride N` comprueba 1 de cada N
                 (solo aplica a este modo; el modo completo corre siempre a stride 1).
  (completo)     Medicion unica (secciones 4-11) con `--pre-json`: aborta si el HEAD,
                 los hashes de datos, los SHA-256 de `configs/` o los parametros
                 resueltos difieren del `pre.json`; registra el SHA-256 del `pre.json`.

Uso:
  python scripts/research/measure_park_bound_mlb.py --pre --data-root <inst> --out pre.json
  python scripts/research/measure_park_bound_mlb.py --parity-only --data-root <inst> [--parity-stride N]
  python scripts/research/measure_park_bound_mlb.py --data-root <inst> --pre-json pre.json --out res.json [--n-boot 10000] [--seed 42]

Una sola ejecucion (seccion 15). El informe de resultado se redacta a partir del
JSON; este script no lo genera.

Lecturas del contrato que el pre-registro deja abiertas. Revisadas por Fable (APTO CON
CAMBIOS, 2026-11-11): 2, 3, 4, 7 y 10 quedan RESUELTAS por el addendum del pre-registro
del 2026-11-11; el resto (1, 5, 6, 8, 9, 11) se marca fiel, sin addendum.

  AMBIGUEDAD 1 (fiel, sin addendum): moneyline "sin empates" (seccion 4). Se
    excluyen los empates (marcador igual) del log loss del moneyline, como las
    metricas binarias de `walk_forward_backtest`. Las lineas de medio punto no tienen empujes.
  AMBIGUEDAD 2 (RESUELTA por el addendum del 2026-11-11): "Delta(b_C) - Delta(0,10)" (seccion 11).
    Se calcula con DOS brazos GLOBALES fijos, T(b_C) y T(0,10), en las filas del test
    combinado (no con el b_P de cada particion). Si b_C == 0,10 no se informa.
  AMBIGUEDAD 3 (RESUELTA por el addendum del 2026-11-11): "Delta en
    temporada regular frente a postemporada" (informe 8). El `ResultsStore` no trae
    el tipo de partido; el script NO lo infiere de la fecha. Informa Delta por
    temporada y por mes y deja `regular_vs_postemporada` como "no disponible".
  AMBIGUEDAD 4 (RESUELTA por el addendum del 2026-11-11): nombres de los dos equipos con cambio
    de estadio (informe 7). El pre-registro no da las claves. Se usan las claves
    normalizadas de "Oakland Athletics", "Athletics", "Sacramento Athletics" y
    "Tampa Bay Rays" (`get_team_normalizer("mlb")`); el `--pre` lista las claves de
    equipo local por temporada para que se revise si faltan.
  AMBIGUEDAD 5 (fiel, sin addendum): el `ParkFactors` sombra usa
    `prior_games = adapter.park.prior_games` (20,0 en la base: el aserto de
    parametros resueltos impide un override) en lugar del literal 20.0, para que el
    informe 10 (sensibilidad al prior) reutilice `walk_components`. Es 20.0 en toda la
    medicion decisoria.
  AMBIGUEDAD 6 (fiel, sin addendum): "SHA-256 de `configs/`" (seccion 14).
    Se hashean TODOS los ficheros bajo `configs/` (claves relativas), no solo los dos yaml.
  AMBIGUEDAD 7 (RESUELTA por el addendum del 2026-11-11): "Delta medio de `spreads@-1.5` y
    `spreads@+1.5`" (criterio 7) = media aritmetica de los dos Delta de log loss.
  AMBIGUEDAD 8 (fiel, sin addendum): umbrales de la fraccion de replicas
    (seccion 11): "Delta <= -0,002" (<=) y "T - C < 0" (<). El p unilateral
    Phi(Delta/EE) se informa solo para el Delta del criterio 1.
  AMBIGUEDAD 9 (fiel, sin addendum): `MIN_EVAL` (200) solo se REGISTRA por
    particion (seccion 8: "el --pre lo registra"); no es una puerta del script. El suelo
    1e-300 de P(T = k) (informe 4) es el `LEVEL_FLOOR` del precedente de recencia.
  AMBIGUEDAD 10 (RESUELTA por el addendum del 2026-11-11): coste. `dist.poisson_match_probs` tarda
    ~5 ms por llamada (medido en esta maquina con max_goals 25 y dispersion_k 3,8) y
    la seccion 4 prohibe reimplementarla. El modo completo hace del orden de 10^5
    llamadas para la rejilla, ~5.10^5 para ajustar C y ~4.10^6 para los ajustes de T2
    (informe, dentro de `_safe_informe`): del orden de horas. No se ha cambiado el
    contrato para acelerarlo.
  AMBIGUEDAD 11 (fiel, sin addendum): la paridad del modo completo (aserto 5.2) corre
    SIEMPRE a stride 1 (`--parity-stride` se rechaza fuera de `--parity-only`); duplica el
    coste del motor. El `--pre` no ejecuta la paridad.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import pandas as pd
import scipy
from scipy.optimize import minimize
from scipy.stats import norm as _norm_dist

from sqp.backtesting import tuning
from sqp.backtesting.engine import walk_forward_backtest
from sqp.calibration.metrics import brier_score, expected_calibration_error, reliability_table
from sqp.config import ROOT as DEFAULT_ROOT
from sqp.domain.models import Event
from sqp.models import distributions as dist
from sqp.models.park import ParkFactors
from sqp.pipeline.daily import _league_meta
from sqp.sports.adapters import BaseballAdapter, PoissonAdapter
from sqp.sports.registry import get_adapter
from sqp.sports.team_names import get_team_normalizer
from sqp.storage.results_store import ResultsStore
from sqp.storage.starters import StartersStore

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]

# ------------------------------------------------------------ constantes --
LEAGUE, FAMILY = "mlb", "baseball"
GRID = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50)             # seccion 2
B_VIGENTE = 0.10                                              # seccion 2 (empates)
CUTOFF = "2026-09-26"                                         # seccion 6
WARMUP = 60                                                   # seccion 6 (default del motor)
FOLDS: dict[str, dict[str, str]] = {                          # seccion 7
    "A": {"train_end": "2023-12-31", "test_start": "2024-01-01", "test_end": "2024-12-31"},
    "B": {"train_end": "2024-12-31", "test_start": "2025-01-01", "test_end": "2025-12-31"},
    "C": {"train_end": "2025-12-31", "test_start": "2026-01-01", "test_end": "2026-09-26"},
}
MARGIN = tuning.IMPROVEMENT_MARGIN                            # 0,002 (importado, no copiado)
MIN_EVAL = tuning.MIN_EVAL_MARKET                             # 200
NM_OPTS = {"xatol": 1e-7, "fatol": 1e-10, "maxiter": 2000}    # seccion 5.1
SEED = 42
N_BOOT = 10_000
TOL = 1e-12
LOSS_EPS = 1e-12                                              # recorte de tuning._binary_nll_series
LEVEL_FLOOR = 1e-300                                          # AMBIGUEDAD 9
SHADOW_BOUND = 1e9                                            # ParkFactors sombra: no recorta
RL = 1.5                                                      # run line +-1,5
CANON_LINE = 8.5                                              # linea fija canonica (seccion 4)
MAX_T = 50                                                    # P(T = k) solo para T_i <= 50
PRIORS_SENSITIVITY = (10.0, 40.0)                             # informe 10
PARITY_BOUNDS = (0.0, 0.10, 0.20)                             # seccion 5.2
STADIUM_CHANGE_NAMES = ("Oakland Athletics", "Athletics", "Sacramento Athletics",
                        "Tampa Bay Rays")                      # AMBIGUEDAD 4

# Referencias de la seccion 6 (para que `--pre` informe las diferencias).
REF_ROWS_AFTER_CUTOFF = 9704
REF_EVALUATED = 9644
REF_TEST = {"B": {"games": 2430, "days": 184}, "C": {"games": 2415, "days": 183}}
REF_DEDUPE_DROPPED = 15

# Seccion 5.2: parametros resueltos que se asertan por IGUALDAD EXACTA.
EXPECTED_LEAGUE_PARAMS: dict[str, float] = {
    "park_bound": 0.1, "pitcher_bound": 0.05, "pitcher_prior_starts": 5.0, "tilt_scale": 0.4}
EXPECTED_ADAPTER_PARAMS: dict[str, Any] = {
    "avg_total": 8.7, "dispersion_k": 3.8, "elo_home_adv": 25, "elo_k": 6,
    "home_scoring_bonus": 0.1, "max_score": 25, "park_bound": 0.1, "pitcher_bound": 0.05,
    "pitcher_prior_starts": 5.0, "tilt_scale": 0.4}


# -------------------------------------------------------------- utilidades --
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows(path: Path) -> int:
    n = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            n += chunk.count(b"\n")
    return max(0, n - 1)


def _clean(obj: object) -> object:
    """JSON limpio: NaN/inf -> None, numpy -> python."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
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


def _dump(obj: object) -> str:
    return json.dumps(_clean(obj), indent=2, ensure_ascii=False, sort_keys=True)


def _safe_informe(nombre: str, fn: Callable[[], object]) -> object:
    """Un informe secundario NUNCA impide escribir el JSON principal (seccion 14).
    El error se anota en su propia seccion. NINGUN criterio pasa por aqui."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 -- informe opcional, ver docstring
        print(f"aviso: informe secundario '{nombre}' fallo: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return {"error": f"{type(exc).__name__}: {exc}", "tipo": type(exc).__name__,
                "traceback": traceback.format_exc()}


def _log(msg: str) -> None:
    print(f"[park_bound] {msg}", file=sys.stderr, flush=True)


def git_head(cwd: Path) -> str | None:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(cwd), capture_output=True,
                             text=True, check=True, timeout=30)
        return res.stdout.strip()
    except Exception:  # noqa: BLE001 -- procedencia, no decide nada
        return None


def git_status_porcelain(cwd: Path, paths: tuple[str, ...] | None = None) -> str | None:
    """`git status --porcelain` de TODO el repositorio (paths=None, lo que exige
    `--pre`) o de unas rutas (lo que comprueba el modo completo)."""
    cmd = ["git", "status", "--porcelain"] + (["--", *paths] if paths else [])
    try:
        res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True,
                             timeout=30)
        return res.stdout
    except Exception:  # noqa: BLE001
        return None


FULL_GIT_PATHS = ("src", "configs", "scripts/research")


def check_git_clean(status: str | None, where: str) -> None:
    if status is None:
        raise SystemExit(f"No se pudo obtener 'git status --porcelain' ({where}). Se aborta: no "
                         "se puede verificar que el arbol este limpio.")
    if status.strip() != "":
        raise SystemExit(f"'git status --porcelain' ({where}) NO esta vacio:\n{status}\n"
                         "Se aborta: no se mide con cambios sin commitear.")


def config_hashes() -> dict[str, str]:
    """SHA-256 de todos los ficheros bajo `configs/` (AMBIGUEDAD 6)."""
    base = _WORKTREE_ROOT / "configs"
    return {p.relative_to(_WORKTREE_ROOT).as_posix(): sha256_of(p)
            for p in sorted(base.rglob("*")) if p.is_file()}


def manifest(data_root: Path) -> dict[str, dict]:
    """SHA-256 y filas de los ficheros que lee el script (resultados y abridores;
    NUNCA cuotas)."""
    files = [ResultsStore(data_root).path(LEAGUE), StartersStore(data_root).path(LEAGUE)]
    out: dict[str, dict] = {}
    for p in files:
        rel = p.relative_to(data_root).as_posix()
        out[rel] = ({"sha256": sha256_of(p), "filas": count_rows(p)} if p.exists()
                    else {"sha256": None, "filas": None})
    return out


# ------------------------------------------------------------- parametros --
def assert_resolved_params(league_params: dict | None, adapter_params: dict) -> None:
    """Seccion 5.2: igualdad EXACTA en los dos niveles (`league_params` y
    `get_adapter(...).params`). Cualquier clave extra (`pitcher_signal`,
    `rest_elo_per_day`, `park_prior_games`, `scoring_half_life_days` != 0...) aborta."""
    if league_params is None or dict(league_params) != EXPECTED_LEAGUE_PARAMS:
        raise SystemExit(f"{LEAGUE}: _league_meta(...)['league_params'] = {league_params!r} != "
                         f"{EXPECTED_LEAGUE_PARAMS!r} (seccion 5.2). Se aborta: hace falta una "
                         "enmienda de base.")
    got = dict(adapter_params)
    if got.get("scoring_half_life_days", None) == 0:      # 0 explicito == ausente (seccion 5.2)
        got.pop("scoring_half_life_days")
    if got != EXPECTED_ADAPTER_PARAMS:
        diff = {k: (got.get(k, "<ausente>"), EXPECTED_ADAPTER_PARAMS.get(k, "<ausente>"))
                for k in sorted(set(got) | set(EXPECTED_ADAPTER_PARAMS))
                if got.get(k, "<a>") != EXPECTED_ADAPTER_PARAMS.get(k, "<a>")}
        raise SystemExit(f"{LEAGUE}: adapter.params efectivo difiere (resuelto, esperado): {diff}. "
                         "Se aborta (seccion 5.2).")


def resolved_report() -> dict:
    meta = _league_meta(LEAGUE)
    lp = meta.get("league_params")
    fam = meta.get("family", FAMILY)
    return {"family": fam, "league_params": lp,
            "adapter_params": dict(get_adapter(LEAGUE, fam, lp).params)}


def assert_family_and_params() -> tuple[dict, dict]:
    """Devuelve (league_params, adapter_params) tras los dos asertos."""
    rep = resolved_report()
    if rep["family"] != FAMILY:
        raise SystemExit(f"{LEAGUE}: familia {rep['family']!r} != {FAMILY!r}. Se aborta.")
    assert_resolved_params(rep["league_params"], rep["adapter_params"])
    return dict(rep["league_params"]), dict(rep["adapter_params"])


def pricing_kwargs(adapter: PoissonAdapter) -> dict:
    """Argumentos de `dist.poisson_match_probs` tomados de `adapter.params` y
    `adapter.TIE_ADDS_GOAL`, no literales (seccion 14)."""
    p = adapter.params
    if adapter.three_way:
        raise SystemExit("El beisbol es de dos vias (three_way=False). Se aborta.")
    return {"three_way": adapter.three_way, "max_goals": p.get("max_score", 15),
            "dc_rho": p.get("dc_rho", 0.0), "dispersion_k": p.get("dispersion_k"),
            "score_rho": p.get("score_rho", 0.0), "tie_adds_goal": adapter.TIE_ADDS_GOAL}


# ------------------------------------------------------------------ datos --
def load_mlb(data_root: Path) -> tuple[list[dict], dict]:
    """Resultados MLB con la deduplicacion por `game_id` por DEFECTO del store,
    `date <= CUTOFF`, y abridores adjuntos (seccion 6). Devuelve (filas, procedencia)."""
    store = ResultsStore(data_root)
    raw_all = store.load(LEAGUE, dedupe_game_id=False)
    deduped = store.load(LEAGUE)
    rows = [r for r in deduped if str(r.get("date", ""))[:10] <= CUTOFF]
    raw_cut = sum(1 for r in raw_all if str(r.get("date", ""))[:10] <= CUTOFF)
    n_attached = StartersStore(data_root).attach(LEAGUE, rows)
    proc: dict[str, Any] = {
        "fichero": str(store.path(LEAGUE)), "corte": CUTOFF,
        "filas_sin_dedupe_total": len(raw_all), "filas_con_dedupe_total": len(deduped),
        "filas_sin_dedupe_hasta_corte": raw_cut, "filas_con_dedupe_hasta_corte": len(rows),
        "descartadas_por_dedupe_game_id_hasta_corte": raw_cut - len(rows),
        "abridores_adjuntos_ambos": n_attached}
    return rows, proc


# --------------------------------------------------------------- recorrido --
def walk_components(results: list[dict], league_params: dict | None, *,
                    warmup: int = WARMUP) -> dict[str, np.ndarray]:
    """UN walk-forward del adaptador de produccion (copia del bucle de
    `walk_forward_backtest`, `engine.py:78-125`): por partido evaluado, el estado
    al CIERRE DEL DIA ANTERIOR. Guarda lam^0 (la lambda ANTES del parque), `f` (el
    factor SIN recortar, de un `ParkFactors` sombra de cota 1e9 actualizado en el
    mismo `observe`), `pf_prod` y `known` (para la paridad). NUNCA lee el marcador
    del partido que estima y NO devuelve ningun desenlace: los marcadores solo
    entran por `observe`, despues de cerrar el dia (`read_outcomes` los da aparte)."""
    adapter = get_adapter(LEAGUE, FAMILY, league_params)
    if not isinstance(adapter, BaseballAdapter):
        raise SystemExit(f"{LEAGUE}: el adaptador no es BaseballAdapter. Se aborta.")
    shadow = ParkFactors(prior_games=float(adapter.park.prior_games), bound=SHADOW_BOUND,
                         normalize=adapter.normalize)               # AMBIGUEDAD 5
    elo = getattr(adapter, "elo", None)
    ordered = sorted(results, key=lambda row: str(row.get("date", "")))
    cols: dict[str, list] = {k: [] for k in
                             ("date", "home", "away", "lam_h0", "lam_a0", "f", "pf_prod", "known")}
    pending: list[dict] = []
    for i, r in enumerate(ordered):
        if pending and str(r.get("date", ""))[:10] != str(pending[0].get("date", ""))[:10]:
            for completed in pending:
                adapter.observe(completed)
                shadow.update(completed["home"], completed["away"],
                              completed["home_score"] + completed["away_score"])
            pending.clear()
        if i >= warmup:
            ev = Event(event_id=str(i), sport_key="bt", league=LEAGUE,
                       home=r["home"], away=r["away"], start_time=str(r.get("date")),
                       data_label=r.get("data_label", "real"),
                       home_pitcher=r.get("home_starter"),
                       away_pitcher=r.get("away_starter"),
                       home_goalie=r.get("home_goalie_announced"),
                       away_goalie=r.get("away_goalie_announced"))
            if elo is not None and elo.season_regression > 0.0:   # envoltorio `_advance_before`
                elo.advance_to(ev.start_time)
            lam_h, lam_a = PoissonAdapter._rates(adapter, ev)
            # Las operaciones de `adapters.py:214-216` SIN `pf`.
            cols["lam_h0"].append(lam_h * adapter.starters.factor(ev.away_pitcher))
            cols["lam_a0"].append(lam_a * adapter.starters.factor(ev.home_pitcher))
            cols["f"].append(shadow.factor(ev.home))
            cols["pf_prod"].append(adapter.park.factor(ev.home))
            cols["known"].append(adapter.park.is_known(ev.home))
            cols["date"].append(str(r.get("date", ""))[:10])
            cols["home"].append(r["home"])
            cols["away"].append(r["away"])
        pending.append(r)
    return {"date": np.asarray(cols["date"], dtype=str),
            "home": np.asarray(cols["home"], dtype=object),
            "away": np.asarray(cols["away"], dtype=object),
            "lam_h0": np.asarray(cols["lam_h0"], float), "lam_a0": np.asarray(cols["lam_a0"], float),
            "f": np.asarray(cols["f"], float), "pf_prod": np.asarray(cols["pf_prod"], float),
            "known": np.asarray(cols["known"], bool)}


def read_outcomes(results: list[dict], *, warmup: int = WARMUP) -> dict[str, np.ndarray]:
    """Marcadores de los partidos EVALUADOS (mismo orden que `walk_components`). Solo
    el modo completo y la paridad la llaman: `--pre` jamas (un test lo fija)."""
    rows = sorted(results, key=lambda row: str(row.get("date", "")))[warmup:]
    hs = np.asarray([float(r["home_score"]) for r in rows], float)
    aw = np.asarray([float(r["away_score"]) for r in rows], float)
    return {"home": hs, "away": aw, "total": hs + aw, "margin": hs - aw}


def line_of(comp: dict) -> np.ndarray:
    """L_i = floor(lam_h0 + lam_a0) + 0,5: la linea del modelo nulo, comun a todos
    los brazos y fijada sin desenlace (seccion 4)."""
    return np.floor(comp["lam_h0"] + comp["lam_a0"]) + 0.5


def pf_of(f: np.ndarray, b: float) -> np.ndarray:
    """`max(1 - b, min(1 + b, f))`, la expresion literal de `park.py:58`."""
    return np.maximum(1.0 - b, np.minimum(1.0 + b, f))


def lam_arm(comp: dict, b: float, a: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """lam_h(b) = max(0,1, lam_h0 * pf(b) * (1 + a)); a = 0 para T(b); b = 0 para C."""
    pf = pf_of(comp["f"], b)
    return (np.maximum(0.1, comp["lam_h0"] * pf * (1.0 + a)),
            np.maximum(0.1, comp["lam_a0"] * pf * (1.0 + a)))


# ----------------------------------------------------------- probabilidades --
def _pmp(lh: float, la: float, spread: float | None, total: float | None, kw: dict) -> dict:
    return dist.poisson_match_probs(float(lh), float(la), spread, total, **kw)


def over_probs(lh: np.ndarray, la: np.ndarray, line: np.ndarray | float, kw: dict) -> np.ndarray:
    ln = np.broadcast_to(np.asarray(line, float), np.shape(lh))
    return np.asarray([_pmp(h, a, None, t, kw)["over"] for h, a, t in zip(lh, la, ln)], float)


def ml_rl_probs(lh: np.ndarray, la: np.ndarray, kw: dict
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """P(local), P(local cubre -1,5), P(local cubre +1,5) de `poisson_match_probs`."""
    ml, rlm, rlp = [], [], []
    for h, a in zip(lh, la):
        r1 = _pmp(h, a, -RL, None, kw)
        ml.append(r1["home_win"])
        rlm.append(r1["home_cover"])
        rlp.append(_pmp(h, a, RL, None, kw)["home_cover"])
    return np.asarray(ml, float), np.asarray(rlm, float), np.asarray(rlp, float)


class Arms:
    """Probabilidades por brazo con cache. `over(b)` da P(Over L_i) para TODAS las
    filas; `mlrl(b, mask)` rellena solo las filas pedidas."""

    def __init__(self, comp: dict, kw: dict) -> None:
        self.comp, self.kw, self.line = comp, kw, line_of(comp)
        n = len(self.line)
        self._over: dict[float, np.ndarray] = {}
        self._mlrl: dict[float, np.ndarray] = {}
        self._done: dict[float, np.ndarray] = {}
        self._n = n

    def over(self, b: float) -> np.ndarray:
        if b not in self._over:
            lh, la = lam_arm(self.comp, b)
            self._over[b] = over_probs(lh, la, self.line, self.kw)
        return self._over[b]

    def over_level(self, b: float, a: float, mask: np.ndarray) -> np.ndarray:
        """P(Over L_i) del brazo C (b = 0) o T2 en las filas de `mask` (resto NaN)."""
        out = np.full(self._n, np.nan)
        idx = np.flatnonzero(mask)
        lh, la = lam_arm(self.comp, b, a)
        out[idx] = over_probs(lh[idx], la[idx], self.line[idx], self.kw)
        return out

    def mlrl(self, b: float, mask: np.ndarray) -> np.ndarray:
        if b not in self._mlrl:
            self._mlrl[b] = np.full((3, self._n), np.nan)
            self._done[b] = np.zeros(self._n, bool)
        need = np.flatnonzero(mask & ~self._done[b])
        if len(need):
            lh, la = lam_arm(self.comp, b)
            ml, rlm, rlp = ml_rl_probs(lh[need], la[need], self.kw)
            self._mlrl[b][0, need], self._mlrl[b][1, need], self._mlrl[b][2, need] = ml, rlm, rlp
            self._done[b][need] = True
        return self._mlrl[b]


# ------------------------------------------------------------ perdidas y NM --
def ll_vec(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Log loss binario por partido, mismo recorte que `tuning._binary_nll_series`."""
    p = np.clip(p, LOSS_EPS, 1.0 - LOSS_EPS)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def fit(objective: Callable[[np.ndarray], float], x0: list[float], name: str) -> np.ndarray:
    """Nelder-Mead (`NM_OPTS`, sin limites). Si no converge, aborta: defecto de codigo (E9)."""
    res = minimize(objective, x0=np.asarray(x0, dtype=float), method="Nelder-Mead", options=NM_OPTS)
    if not res.success:
        raise SystemExit(f"El optimizador Nelder-Mead NO CONVERGIO ({name}): {res.message}. "
                         "Seccion 5.1: se trata como defecto de codigo y se aborta.")
    return res.x


def fit_level(arms: Arms, b: float, y_over: np.ndarray, train: np.ndarray) -> tuple[float, float]:
    """a que minimiza el log loss medio de entrenamiento de `lam^0 * pf(b) * (1 + a)`
    (Nelder-Mead desde 0). b = 0 es el control de nivel C. Devuelve (a, perdida)."""
    idx = np.flatnonzero(train)
    lh0, la0, ln = arms.comp["lam_h0"][idx], arms.comp["lam_a0"][idx], arms.line[idx]
    pf = pf_of(arms.comp["f"][idx], b)
    yy = y_over[idx]

    def obj(v: np.ndarray) -> float:
        lh = np.maximum(0.1, lh0 * pf * (1.0 + v[0]))
        la = np.maximum(0.1, la0 * pf * (1.0 + v[0]))
        return float(np.mean(ll_vec(over_probs(lh, la, ln, arms.kw), yy)))

    a = float(fit(obj, [0.0], f"nivel a (b={b})")[0])
    return a, obj(np.asarray([a]))


def fit_t2_per_bound(arms: Arms, y_over: np.ndarray, train: np.ndarray
                     ) -> dict[float, tuple[float, float]]:
    """T2: (a_b, perdida) por cota. Las cotas cuyo `pf_of(f[train], b)` es identico
    (`np.array_equal`) son el MISMO modelo: se reutiliza el ajuste, bit a bit igual."""
    f_tr = arms.comp["f"][train]
    done: list[tuple[np.ndarray, tuple[float, float]]] = []
    out: dict[float, tuple[float, float]] = {}
    for b in GRID:
        pf = pf_of(f_tr, b)
        hit = next((v for k, v in done if np.array_equal(k, pf)), None)
        if hit is None:
            hit = fit_level(arms, b, y_over, train)
            done.append((pf, hit))
            _log(f"T2 b={b}: a={hit[0]:.6f}")
        out[b] = hit
    return out


def select_b(train_loss: dict[float, float], b_vig: float = B_VIGENTE) -> float:
    """Seccion 2: b_P = argmin de la perdida media de entrenamiento. Empate EXACTO:
    la cota mas cercana al vigente (0,10); si persiste, la MENOR. El test nunca interviene."""
    if not train_loss:
        raise SystemExit("select_b: rejilla vacia.")
    if any(not math.isfinite(v) for v in train_loss.values()):
        raise SystemExit("select_b: perdida de entrenamiento no finita en la rejilla.")
    best = min(train_loss.values())
    tied = [b for b, v in train_loss.items() if v == best]
    tied.sort(key=lambda b: (round(abs(b - b_vig), 12), b))
    return float(tied[0])


def min_gap(train_loss: dict[float, float]) -> float | None:
    """Diferencia minima de perdida entre dos cotas distintas (se informa; seccion 14)."""
    v = sorted(train_loss.values())
    return float(min(np.diff(v))) if len(v) > 1 else None


def fold_masks(dates: np.ndarray) -> dict[str, dict[str, np.ndarray]]:
    out: dict[str, dict[str, np.ndarray]] = {}
    for name, f in FOLDS.items():
        out[name] = {"train": dates <= f["train_end"],
                     "test": (dates >= f["test_start"]) & (dates <= f["test_end"])}
    return out


# ------------------------------------------------------ bootstrap por dias --
def bootstrap_dias(dates: np.ndarray, stats: dict[str, tuple[np.ndarray, np.ndarray]],
                   n_boot: int = N_BOOT, seed: int = SEED, chunk: int = 250,
                   thresholds: dict[str, tuple[str, float]] | None = None) -> dict[str, dict]:
    """Seccion 11: remuestrea DIAS completos del test combinado, `n_boot` replicas,
    semilla `seed`. Cada estadistico es un cociente sum(num)/sum(den). IC95 percentil,
    EE y, si hay umbral, la fraccion de replicas ('le' <=, 'lt' <). No es puerta."""
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
        est = float(sums[k].sum() / cnts[k].sum()) if cnts[k].sum() > 0 else None
        d: dict[str, Any] = {
            "estimacion": est, "n_dias": int(nd), "n_replicas": int(len(fin)),
            "ic95": ([float(np.quantile(fin, 0.025)), float(np.quantile(fin, 0.975))]
                     if len(fin) else [None, None]),
            "se": float(np.std(fin, ddof=1)) if len(fin) > 1 else None}
        if thresholds and k in thresholds and len(fin):
            kind, thr = thresholds[k]
            d["fraccion_replicas"] = float(np.mean(fin <= thr if kind == "le" else fin < thr))
            d["umbral"] = [kind, thr]
        out[k] = d
    return out


def p_value(delta: float | None, se: float | None) -> float:
    """p unilateral = Phi(delta / EE) (H0: delta >= 0). Sin delta o EE utilizable, p = 1."""
    if delta is None or se is None or not math.isfinite(delta) or not math.isfinite(se) or se <= 0:
        return 1.0
    return float(_norm_dist.cdf(delta / se))


# =========================================================== modo --pre ==
def _pct(x: np.ndarray) -> dict:
    if len(x) == 0:
        return {"n": 0}
    qs = (1, 5, 25, 50, 75, 95, 99)
    out: dict[str, Any] = {"n": int(len(x)), "min": float(np.min(x)), "max": float(np.max(x))}
    out.update({f"p{q}": float(np.percentile(x, q)) for q in qs})
    return out


def _bern_kl(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    p = np.clip(p, LOSS_EPS, 1 - LOSS_EPS)
    q = np.clip(q, LOSS_EPS, 1 - LOSS_EPS)
    return p * np.log(p / q) + (1 - p) * np.log((1 - p) / (1 - q))


def clipped_fraction(f: np.ndarray, b: float) -> float:
    return float(np.mean((f < 1.0 - b) | (f > 1.0 + b))) if len(f) else float("nan")


def build_pre(comp: dict, arms: Arms) -> dict:
    """Seccion 9. Recibe SOLO componentes del modelo (nunca desenlaces)."""
    dates, f = comp["date"], comp["f"]
    masks = fold_masks(dates)
    test_all = np.zeros(len(dates), bool)
    for m in masks.values():
        test_all |= m["test"]
    counts: dict[str, Any] = {"evaluados_total": int(len(dates)),
                              "referencia_evaluados": REF_EVALUATED,
                              "diferencia_evaluados": int(len(dates)) - REF_EVALUATED, "particiones": {}}
    for n, m in masks.items():
        tdays = int(len(np.unique(dates[m["test"]])))
        entry = {"n_entrenamiento": int(m["train"].sum()), "n_test": int(m["test"].sum()),
                 "dias_test": tdays, "min_eval_ok": bool(int(m["test"].sum()) >= MIN_EVAL)}
        if n in REF_TEST:
            entry["referencia"] = REF_TEST[n]
            entry["diferencia_n_test"] = entry["n_test"] - REF_TEST[n]["games"]
            entry["diferencia_dias_test"] = tdays - REF_TEST[n]["days"]
        counts["particiones"][n] = entry
    fdist = {n: {"entrenamiento": _pct(f[m["train"]]), "test": _pct(f[m["test"]]),
                 "fraccion_factor_1_0_test": (float(np.mean(f[m["test"]] == 1.0))
                                              if m["test"].any() else None),
                 "fraccion_sin_muestra_test": (float(np.mean(~comp["known"][m["test"]]))
                                               if m["test"].any() else None)}
             for n, m in masks.items()}
    fdist["combinado_test"] = {"test": _pct(f[test_all]),
                               "fraccion_factor_1_0": float(np.mean(f[test_all] == 1.0)) if test_all.any() else None,
                               "fraccion_sin_muestra": float(np.mean(~comp["known"][test_all])) if test_all.any() else None}
    clip = {n: {"entrenamiento": {str(b): clipped_fraction(f[m["train"]], b) for b in GRID},
                "test": {str(b): clipped_fraction(f[m["test"]], b) for b in GRID}}
            for n, m in masks.items()}
    clipped_top = int(np.sum((f < 1.0 - GRID[-1]) | (f > 1.0 + GRID[-1])))
    classes: dict[str, list] = {}
    for n, m in masks.items():
        groups: list[list[float]] = []
        for b in GRID:
            pb = pf_of(f[m["train"]], b)
            for g in groups:
                if np.array_equal(pf_of(f[m["train"]], g[0]), pb):
                    g.append(b)
                    break
            else:
                groups.append([b])
        classes[n] = [list(g) for g in groups]
    # Delta p_i(b), medias de P(Over L_i) y escenarios KL (sin desenlaces).
    p0 = arms.over(0.0)
    dp = {str(b): _pct(arms.over(b) - p0) for b in GRID}
    mean_p = {str(b): float(np.mean(arms.over(b))) for b in GRID}
    kl = {str(b): {"E_KL_test_combinado": float(np.mean(_bern_kl(arms.over(b)[test_all], p0[test_all])))
                   if test_all.any() else None} for b in GRID}
    # Claves de equipo local por temporada.
    norm = get_team_normalizer(LEAGUE)
    seasons = sorted({d[:4] for d in dates})
    keys: dict[str, dict[str, int]] = {s: {} for s in seasons}
    for d, h in zip(dates, comp["home"]):
        k = norm(h)
        keys[d[:4]][k] = keys[d[:4]].get(k, 0) + 1
    allk = sorted({k for s in keys.values() for k in s})
    partial = {k: [s for s in seasons if k in keys[s]] for k in allk if any(k not in keys[s] for s in seasons)}
    return {"recuentos": counts, "distribucion_f": fdist, "fraccion_recortada_por_cota": clip,
            "recortados_con_cota_0_50_total": clipped_top,
            "cota_050_no_vinculante": clipped_top == 0, "clases_de_equivalencia_entrenamiento": classes,
            "delta_p_por_cota": dp, "media_P_over_por_brazo": mean_p, "escenarios_KL": kl,
            "claves_equipo_local_por_temporada": keys, "claves_solo_en_algunas_temporadas": partial}


def informe_pre(data_root: Path) -> dict:
    status = git_status_porcelain(_WORKTREE_ROOT)
    check_git_clean(status, "repositorio completo (--pre)")
    league_params, adapter_params = assert_family_and_params()
    results, proc = load_mlb(data_root)
    adapter = get_adapter(LEAGUE, FAMILY, league_params)
    kw = pricing_kwargs(adapter)
    t0 = time.perf_counter()
    comp = walk_components(results, league_params)
    arms = Arms(comp, kw)
    pre = build_pre(comp, arms)
    return {"git_head": git_head(_WORKTREE_ROOT), "git_status_porcelain": status,
            "manifiesto": manifest(data_root), "config_sha256": config_hashes(),
            "parametros_resueltos": {"league_params": league_params, "adapter_params": adapter_params},
            "procedencia": proc, "pricing_kwargs": kw, "grid": list(GRID), "folds": FOLDS,
            "constantes": {"CUTOFF": CUTOFF, "WARMUP": WARMUP, "MARGIN": MARGIN, "MIN_EVAL": MIN_EVAL,
                           "SEED": SEED, "N_BOOT": N_BOOT, "TOL": TOL},
            "referencias_seccion_6": {"filas_tras_corte": REF_ROWS_AFTER_CUTOFF,
                                      "diferencia_filas": proc["filas_con_dedupe_hasta_corte"] - REF_ROWS_AFTER_CUTOFF,
                                      "descartadas_dedupe_referencia": REF_DEDUPE_DROPPED},
            **pre, "segundos_calculo": time.perf_counter() - t0}


# ===================================================== paridad (sec. 5.2) ==
def _aligned(engine_probs: list[float], keep: np.ndarray, idx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Alinea la serie del motor (sin empujes/empates) con las filas `idx` conservadas."""
    pos = np.cumsum(keep) - 1
    sel = idx[keep[idx]]
    return sel, np.asarray(engine_probs, float)[pos[sel]]


def run_parity(results: list[dict], league_params: dict, kw: dict, stride: int = 1) -> dict:
    """Asertos 1-3 de la seccion 5.2. Aborta si falla (tolerancia `TOL`)."""
    if stride < 1:
        raise SystemExit("--parity-stride debe ser >= 1.")
    out_rows = read_outcomes(results)
    margin, total = out_rows["margin"], out_rows["total"]
    base = dict(league_params)
    comps: dict[float, dict] = {}
    for b in PARITY_BOUNDS:
        comps[b] = walk_components(results, {**base, "park_bound": b})
    ref = comps[PARITY_BOUNDS[0]]
    n = len(ref["f"])
    for b, c in comps.items():
        for key in ("lam_h0", "lam_a0", "f"):
            if not np.array_equal(ref[key], c[key]):
                raise SystemExit(f"PARIDAD (aserto 3): '{key}' difiere con park_bound={b}. Se aborta.")
        if not np.array_equal(c["pf_prod"], pf_of(c["f"], b)):
            raise SystemExit(f"PARIDAD (aserto 2): pf(b={b}) != adapter.park.factor. Se aborta.")
    idx = np.arange(0, n, stride)
    report: dict[str, Any] = {"n_evaluados": int(n), "stride": stride, "cotas": {}}
    for b in PARITY_BOUNDS:
        eng = walk_forward_backtest(results, LEAGUE, FAMILY, {**base, "park_bound": b},
                                    warmup=WARMUP, spread_lines=(-RL, RL), total_lines=(CANON_LINE,))
        lh, la = lam_arm(ref, b)
        ml = np.full(n, np.nan)
        rlm = np.full(n, np.nan)
        rlp = np.full(n, np.nan)
        ov = np.full(n, np.nan)
        for i in idx:
            r1 = _pmp(lh[i], la[i], -RL, None, kw)
            ml[i], rlm[i] = r1["home_win"], r1["home_cover"]
            rlp[i] = _pmp(lh[i], la[i], RL, None, kw)["home_cover"]
            ov[i] = _pmp(lh[i], la[i], None, CANON_LINE, kw)["over"]
        checks = {
            "h2h": (ml, eng["binary_probs"], margin != 0.0),
            "spreads@-1.5": (rlm, eng["markets"]["spreads@-1.5"]["probs"], margin != -(-RL)),
            "spreads@1.5": (rlp, eng["markets"]["spreads@1.5"]["probs"], margin != -RL),
            "totals@8.5": (ov, eng["markets"]["totals@8.5"]["probs"], total != CANON_LINE)}
        dev: dict[str, float] = {}
        for name, (mine, theirs, keep) in checks.items():
            if len(theirs) != int(keep.sum()):
                raise SystemExit(f"PARIDAD (aserto 1/2): {name} con b={b}: el motor da {len(theirs)} "
                                 f"filas y se esperaban {int(keep.sum())}. Se aborta.")
            sel, eng_p = _aligned(theirs, keep, idx)
            d = float(np.max(np.abs(mine[sel] - eng_p))) if len(sel) else 0.0
            dev[name] = d
            if not d <= TOL:
                raise SystemExit(f"PARIDAD ROTA: {name} con park_bound={b}: max|dif| = {d:.3e} > {TOL}. "
                                 "Se aborta (seccion 5.2).")
        report["cotas"][str(b)] = dev
    report["lam0_f_identicos_bajo_las_tres_cotas"] = True
    return report


# ====================================================== modo completo ==
def check_provenance(pre: dict, head_now: str | None, manifest_now: dict, cfg_now: dict,
                     params_now: dict) -> None:
    """Seccion 14: aborta si HEAD, hashes de datos, hashes de configs o parametros
    resueltos difieren del `pre.json`."""
    if pre.get("git_head") is None or head_now is None:
        raise SystemExit("No se pudo comparar 'git rev-parse HEAD' con el del pre.json. Se aborta.")
    if pre["git_head"] != head_now:
        raise SystemExit(f"HEAD DE GIT CAMBIO: pre.json {pre['git_head']} vs {head_now}. Se aborta.")
    if (pre.get("git_status_porcelain") or "").strip() != "":
        raise SystemExit("pre.json registra un arbol git sucio. Se aborta.")
    prev = pre.get("manifiesto") or {}
    if not prev or set(prev) != set(manifest_now) or any(
            prev[k].get("sha256") != manifest_now[k].get("sha256")
            or prev[k].get("filas") != manifest_now[k].get("filas") for k in prev):
        raise SystemExit("HASH DE ENTRADA CAMBIO respecto del pre.json (resultados/abridores). Se aborta.")
    if pre.get("config_sha256") != cfg_now:
        raise SystemExit("SHA-256 de configs/ distinto del del pre.json. Se aborta.")
    if _clean(pre.get("parametros_resueltos")) != _clean(params_now):
        raise SystemExit("Parametros resueltos distintos de los del pre.json. Se aborta.")
    if pre.get("cota_050_no_vinculante") is not True:
        raise SystemExit("pre.json no certifica 0 partidos recortados con b = 0,50 (seccion 2): "
                         "hace falta una enmienda antes del modo completo. Se aborta.")


def _mean(x: np.ndarray, mask: np.ndarray | None = None) -> float:
    v = x if mask is None else x[mask]
    return float(np.mean(v)) if len(v) else float("nan")


def _require_finite(name: str, x: np.ndarray, idx: np.ndarray) -> None:
    if not np.all(np.isfinite(x[idx])):
        raise SystemExit(f"Probabilidad no finita en {name}. Se aborta (defecto de codigo).")


def run_full(results: list[dict], league_params: dict, kw: dict, n_boot: int, seed: int,
             on_partial: Callable[[dict], None] | None = None) -> dict:
    t_start = time.perf_counter()
    parity = run_parity(results, league_params, kw, 1)
    _log("paridad OK")
    comp = walk_components(results, league_params)
    oc = read_outcomes(results)
    n = len(comp["f"])
    if len(oc["total"]) != n:
        raise SystemExit("Desajuste entre componentes y desenlaces. Se aborta.")
    arms = Arms(comp, kw)
    dates, line = comp["date"], arms.line
    masks = fold_masks(dates)
    y_over = (oc["total"] > line).astype(float)
    y_ml = (oc["margin"] > 0).astype(float)
    nontie = oc["margin"] != 0.0
    y_rlm = (oc["margin"] > RL).astype(float)
    y_rlp = (oc["margin"] > -RL).astype(float)

    # --- brazos de la rejilla (P(Over L_i) para todas las filas) ---
    for b in GRID:
        arms.over(b)
        _log(f"rejilla b={b} lista")
    # --- seleccion por particion (solo entrenamiento) ---
    sel: dict[str, dict] = {}
    for fn, m in masks.items():
        tl = {b: _mean(ll_vec(arms.over(b), y_over), m["train"]) for b in GRID}
        bp = select_b(tl)
        sel[fn] = {"train_loss": tl, "b_P": bp, "min_gap": min_gap(tl),
                   "n_train": int(m["train"].sum()), "n_test": int(m["test"].sum())}
    b_p = {fn: sel[fn]["b_P"] for fn in FOLDS}
    b_c = b_p[list(FOLDS)[-1]]
    # --- control de nivel C por particion ---
    level: dict[str, dict] = {}
    p_c = np.full(n, np.nan)
    for fn, m in masks.items():
        a, tr_loss = fit_level(arms, 0.0, y_over, m["train"])
        level[fn] = {"a": a, "perdida_entrenamiento": tr_loss}
        p_c[m["test"]] = arms.over_level(0.0, a, m["test"])[m["test"]]
        _log(f"C particion {fn}: a={a:.6f}")
    test_any = np.zeros(n, bool)
    for m in masks.values():
        test_any |= m["test"]
    idx = np.flatnonzero(test_any)
    fold_of = np.full(n, "", dtype=object)
    for fn, m in masks.items():
        fold_of[m["test"]] = fn
    p_n = arms.over(0.0)
    p_t = np.full(n, np.nan)
    for fn, m in masks.items():
        p_t[m["test"]] = arms.over(b_p[fn])[m["test"]]
    for nm, arr in (("N", p_n), ("T", p_t), ("C", p_c)):
        _require_finite(nm, arr, idx)
    # moneyline y run line: N y T(b_P) solo en las filas de test
    n_ml = arms.mlrl(0.0, test_any)
    t_ml = np.full((3, n), np.nan)
    for fn, m in masks.items():
        t_ml[:, m["test"]] = arms.mlrl(b_p[fn], m["test"])[:, m["test"]]

    ll_n, ll_t, ll_c = ll_vec(p_n, y_over), ll_vec(p_t, y_over), ll_vec(p_c, y_over)
    d_by_fold = {fn: _mean(ll_t - ll_n, m["test"]) for fn, m in masks.items()}
    d_comb = _mean(ll_t - ll_n, test_any)
    tc_comb = _mean(ll_t - ll_c, test_any)
    brier_n = float(brier_score(p_n[idx], y_over[idx]))
    brier_t = float(brier_score(p_t[idx], y_over[idx]))
    ece_n = float(expected_calibration_error(p_n[idx], y_over[idx]))
    ece_t = float(expected_calibration_error(p_t[idx], y_over[idx]))
    nt_idx = idx[nontie[idx]]
    d_ml = float(np.mean(ll_vec(t_ml[0], y_ml)[nt_idx] - ll_vec(n_ml[0], y_ml)[nt_idx]))
    d_rlm = float(np.mean(ll_vec(t_ml[1], y_rlm)[idx] - ll_vec(n_ml[1], y_rlm)[idx]))
    d_rlp = float(np.mean(ll_vec(t_ml[2], y_rlp)[idx] - ll_vec(n_ml[2], y_rlp)[idx]))
    d_rl = (d_rlm + d_rlp) / 2.0                                         # AMBIGUEDAD 7
    criteria = {
        "1_delta_logloss_combinado": {"valor": d_comb, "umbral": -MARGIN, "pasa": bool(d_comb <= -MARGIN)},
        "2_delta_negativo_en_cada_particion": {"valor": d_by_fold, "pasa": bool(all(v < 0 for v in d_by_fold.values()))},
        "3_bP_positivo_en_las_tres": {"valor": b_p, "pasa": bool(all(v > 0 for v in b_p.values()))},
        "4_brier_T_le_N": {"T": brier_t, "N": brier_n, "pasa": bool(brier_t <= brier_n)},
        "5_ece_T_le_N": {"T": ece_t, "N": ece_n, "pasa": bool(ece_t <= ece_n)},
        "6_logloss_T_lt_C": {"T_menos_C": tc_comb, "pasa": bool(tc_comb < 0)},
        "7_moneyline_y_runline_no_empeoran": {
            "delta_moneyline": d_ml, "delta_runline_menos_1_5": d_rlm, "delta_runline_mas_1_5": d_rlp,
            "delta_runline_medio": d_rl, "pasa": bool(d_ml <= 0 and d_rl <= 0)}}
    accept = all(c["pasa"] for c in criteria.values())
    verdict = {"veredicto": "ACEPTA" if accept else "RECHAZA", "b_C": b_c,
               "valor_validado": b_c if accept else None,
               "criterios_fallidos": [k for k, c in criteria.items() if not c["pasa"]]}

    # --- bootstrap por bloques de fecha (no es puerta) ---
    one = np.ones(len(idx))
    nt = nontie[idx].astype(float)
    stats: dict[str, tuple[np.ndarray, np.ndarray]] = {
        "delta_logloss": ((ll_t - ll_n)[idx], one),
        "T_menos_C": ((ll_t - ll_c)[idx], one),
        "delta_brier": (((p_t - y_over) ** 2 - (p_n - y_over) ** 2)[idx], one),
        "delta_moneyline": (((ll_vec(t_ml[0], y_ml) - ll_vec(n_ml[0], y_ml))[idx] * nt), nt),
        "delta_runline_medio": ((((ll_vec(t_ml[1], y_rlm) - ll_vec(n_ml[1], y_rlm))
                                 + (ll_vec(t_ml[2], y_rlp) - ll_vec(n_ml[2], y_rlp))) / 2.0)[idx], one)}
    if b_c != B_VIGENTE:
        stats["delta_bC_menos_delta_0_10"] = ((ll_vec(arms.over(b_c), y_over) - ll_vec(arms.over(B_VIGENTE), y_over))[idx], one)
    boot = bootstrap_dias(dates[idx], stats, n_boot, seed,
                          thresholds={"delta_logloss": ("le", -MARGIN), "T_menos_C": ("lt", 0.0)})
    boot["p_unilateral_delta_logloss"] = p_value(d_comb, boot["delta_logloss"]["se"])
    _log("criterios y bootstrap listos")

    # --- tabla de perdidas por brazo y particion ---
    tabla: dict[str, Any] = {"entrenamiento_por_cota": {fn: sel[fn]["train_loss"] for fn in FOLDS},
                             "test_por_brazo": {}}
    for fn, m in masks.items():
        tabla["test_por_brazo"][fn] = {"N": _mean(ll_n, m["test"]), "T": _mean(ll_t, m["test"]),
                                       "C": _mean(ll_c, m["test"]),
                                       "por_cota": {str(b): _mean(ll_vec(arms.over(b), y_over), m["test"]) for b in GRID}}
    tabla["test_por_brazo"]["combinado"] = {
        "N": _mean(ll_n, test_any), "T": _mean(ll_t, test_any), "C": _mean(ll_c, test_any),
        "por_cota": {str(b): _mean(ll_vec(arms.over(b), y_over), test_any) for b in GRID}}

    particiones = {fn: {"b_P": sel[fn]["b_P"], "diferencia_minima_entre_cotas": sel[fn]["min_gap"],
                        "n_entrenamiento": sel[fn]["n_train"], "n_test": sel[fn]["n_test"],
                        "n_test_sin_muestra": int(np.sum(~comp["known"][masks[fn]["test"]])),
                        "min_eval_ok": bool(sel[fn]["n_test"] >= MIN_EVAL),
                        "a_nivel_C": level[fn]["a"]} for fn in FOLDS}
    res = {"paridad": parity, "particiones": particiones, "perdidas": tabla, "criterios": criteria,
           "veredicto": verdict, "bootstrap": boot, "n_boot": n_boot, "seed": seed}
    if on_partial is not None:     # el JSON con los criterios existe ANTES de los informes lentos
        on_partial({**res, "informes": {"estado": "en curso"}})
    informes = _informes(results, league_params, kw, comp, arms, masks, test_any, idx, y_over,
                         y_ml, y_rlm, y_rlp, nontie, oc, p_n, p_t, p_c, n_ml, t_ml, ll_n, ll_t,
                         b_p, level, sel, n_boot, seed)
    return {**res, "informes": informes, "segundos_medicion": time.perf_counter() - t_start}


# ------------------------------------------------------------- informes --
def _informes(results, league_params, kw, comp, arms, masks, test_any, idx, y_over, y_ml, y_rlm,
              y_rlp, nontie, oc, p_n, p_t, p_c, n_ml, t_ml, ll_n, ll_t, b_p, level, sel,
              n_boot, seed) -> dict:
    """Secciones 10.1-10.10. Ninguno decide; cada uno va envuelto en `_safe_informe`."""
    n = len(comp["f"])
    dates = comp["date"]
    t2_cache: dict[str, Any] = {}

    def t2_fits() -> dict:
        if "v" not in t2_cache:
            out: dict[str, Any] = {}
            for fn, m in masks.items():
                per_b = fit_t2_per_bound(arms, y_over, m["train"])
                b_t2 = select_b({b: v[1] for b, v in per_b.items()})
                out[fn] = {"b_T2": b_t2, "a": per_b[b_t2][0],
                           "por_cota": {str(b): {"a": v[0], "perdida": v[1]} for b, v in per_b.items()}}
            t2_cache["v"] = out
        return t2_cache["v"]

    def p_t2() -> np.ndarray:
        fits = t2_fits()
        out = np.full(n, np.nan)
        for fn, m in masks.items():
            out[m["test"]] = arms.over_level(fits[fn]["b_T2"], fits[fn]["a"], m["test"])[m["test"]]
        return out

    def i1() -> dict:
        res: dict = {}
        for b in GRID:
            d = ll_vec(arms.over(b), y_over) - ll_n
            res[str(b)] = {**{fn: _mean(d, m["test"]) for fn, m in masks.items()}, "combinado": _mean(d, test_any)}
        return res

    def i2() -> dict:
        res = {}
        for fn in FOLDS:
            tl = sel[fn]["train_loss"]
            bp = sel[fn]["b_P"]
            res[fn] = {"perdida_entrenamiento": {str(b): v for b, v in tl.items()}, "b_P": bp,
                       "tipo_de_minimo": ("cero" if bp == 0.0 else
                                          "borde_superior_no_vinculante" if bp == GRID[-1] else "interior")}
        return res

    def i3() -> dict:
        base = {k: v for k, v in league_params.items() if k != "park_bound"}
        r = tuning.tune_market_param(results, LEAGUE, FAMILY, param="park_bound", grid=GRID,
                                     market="totals", line=CANON_LINE, default_value=0.0,
                                     league_params=base, n_splits=4)
        r = dict(r)
        tbl = r.pop("table")
        r["table"] = tbl.to_dict("records")
        return r

    def nll_total(lh: np.ndarray, la: np.ndarray, t: np.ndarray) -> np.ndarray:
        out = np.full(len(t), np.nan)
        for i, (h, a, k) in enumerate(zip(lh, la, t)):
            if k <= MAX_T:
                pk = _pmp(h, a, None, k - 0.5, kw)["over"] - _pmp(h, a, None, k + 0.5, kw)["over"]
                out[i] = -math.log(max(LEVEL_FLOOR, pk))
        return out

    def i4() -> dict:
        fits = t2_fits()
        res: dict = {}
        acc: dict[str, list] = {k: [] for k in ("N", "T", "C", "T2")}
        excl = 0
        for fn, m in masks.items():
            ii = np.flatnonzero(m["test"])
            t = oc["total"][ii]
            excl += int(np.sum(t > MAX_T))
            lam = {"N": lam_arm(comp, 0.0), "T": lam_arm(comp, b_p[fn]),
                   "C": lam_arm(comp, 0.0, level[fn]["a"]),
                   "T2": lam_arm(comp, fits[fn]["b_T2"], fits[fn]["a"])}
            res[fn] = {}
            for k, (lh, la) in lam.items():
                v = nll_total(lh[ii], la[ii], t)
                acc[k].append(v)
                res[fn][k] = float(np.nanmean(v))
        res["combinado"] = {k: float(np.nanmean(np.concatenate(v))) for k, v in acc.items()}
        res["T_i_mayor_que_50_excluidos"] = excl
        return res

    def i5() -> dict:
        fits = t2_fits()
        pt2 = p_t2()
        ll_t2 = ll_vec(pt2, y_over)
        obs = {fn: _mean(y_over, m["test"]) for fn, m in masks.items()}
        sesgo = {fn: {"N": _mean(p_n, m["test"]) - obs[fn], "T": _mean(p_t, m["test"]) - obs[fn]}
                 for fn, m in masks.items()}
        gain_t = _mean(ll_n - ll_t, test_any)
        gain_t2 = _mean(ll_n - ll_t2, test_any)
        return {"sesgo_P_over_menos_tasa_over": sesgo, "a_nivel_C": {fn: level[fn]["a"] for fn in FOLDS},
                "T2": {fn: {"b_T2": fits[fn]["b_T2"], "a": fits[fn]["a"]} for fn in FOLDS},
                "ganancia_T": gain_t, "ganancia_T2": gain_t2,
                "fraccion_de_la_ganancia_de_T2_que_captura_T": (gain_t / gain_t2 if gain_t2 else None)}

    def i6() -> dict:
        rel = {"N": reliability_table(p_n[idx], y_over[idx]).to_dict("records"),
               "T": reliability_table(p_t[idx], y_over[idx]).to_dict("records")}
        dev = np.abs(comp["f"][idx] - 1.0)
        edges = np.quantile(dev, [0.2, 0.4, 0.6, 0.8])
        q = np.digitize(dev, edges)
        d = (ll_t - ll_n)[idx]
        quint = {str(k): {"n": int(np.sum(q == k)), "delta": float(np.mean(d[q == k])) if np.any(q == k) else None}
                 for k in range(5)}
        return {"fiabilidad_10_bins": rel, "cortes_quintiles_abs_f_menos_1": edges.tolist(),
                "delta_por_quintil_de_abs_f_menos_1": quint}

    def i7() -> dict:
        norm = get_team_normalizer(LEAGUE)
        names = {norm(x) for x in STADIUM_CHANGE_NAMES}
        keep = np.asarray([norm(h) not in names for h in comp["home"]], bool)
        sub = test_any & keep
        return {"claves_excluidas": sorted(names), "n_excluidos": int(np.sum(test_any & ~keep)),
                "delta_sin_esos_partidos": _mean(ll_t - ll_n, sub), "delta_con_todos": _mean(ll_t - ll_n, test_any)}

    def i8() -> dict:
        d = ll_t - ll_n
        res: dict = {"por_temporada": {}, "por_mes": {}}
        for key, cut in (("por_temporada", 4), ("por_mes", 7)):
            for g in sorted({x[:cut] for x in dates[idx]}):
                mk = test_any & np.asarray([x[:cut] == g for x in dates], bool)
                res[key][g] = {"n": int(mk.sum()), "delta": _mean(d, mk)}
        res["regular_vs_postemporada"] = "no aplicable: el proveedor MLB solo ingiere gameType=R"
        return res

    def i9() -> dict:
        res: dict = {}
        for name, k, y in (("moneyline", 0, y_ml), ("runline_menos_1_5", 1, y_rlm), ("runline_mas_1_5", 2, y_rlp)):
            sub = idx[nontie[idx]] if k == 0 else idx
            res[name] = {
                "delta": float(np.mean(ll_vec(t_ml[k], y)[sub] - ll_vec(n_ml[k], y)[sub])),
                "ece_N": float(expected_calibration_error(n_ml[k][sub], y[sub])),
                "ece_T": float(expected_calibration_error(t_ml[k][sub], y[sub]))}
        return res

    def i10() -> dict:
        res: dict = {}
        for prior in PRIORS_SENSITIVITY:
            c = walk_components(results, {**league_params, "park_prior_games": prior})
            a = Arms(c, kw)
            mk = fold_masks(c["date"])
            res[str(prior)] = {fn: {str(b): _mean(ll_vec(a.over(b), y_over), m["train"]) for b in GRID}
                               for fn, m in mk.items()}
        return {"perfil_de_entrenamiento_con_park_prior_games": res,
                "nota": "descriptivo; no se usa para elegir nada"}

    out: dict = {}
    for name, fn in (("1_delta_de_toda_la_rejilla", i1), ("2_perfil_de_entrenamiento", i2),
                     ("3_procedimiento_canonico_tune_market_param", i3), ("4_perdida_sin_linea", i4),
                     ("5_sesgo_y_T2", i5), ("6_fiabilidad_y_quintiles", i6),
                     ("7_sin_cambio_de_estadio", i7), ("8_por_temporada_y_mes", i8),
                     ("9_moneyline_y_runline", i9), ("10_sensibilidad_al_prior", i10)):
        out[name] = _safe_informe(name, fn)
    return out


# ====================================================================== main ==
def _data_root_error(args: argparse.Namespace) -> str | None:
    """Reglas de `--data-root` (instantanea congelada): obligatorio en TODOS los
    modos; no puede ser la raiz viva del repositorio (sqp.config.ROOT) ni ningun
    checkout git (existe `<root>/.git`); el modo completo rechaza un `--out` ya
    existente (una sola ejecucion)."""
    if args.data_root is None:
        return "--data-root es obligatorio (instantanea congelada)."
    if Path(args.data_root).resolve() == Path(DEFAULT_ROOT).resolve():
        return ("--data-root no puede ser la raiz viva del repositorio (sqp.config.ROOT): "
                "usa la instantanea congelada.")
    if (Path(args.data_root) / ".git").exists():
        return ("--data-root es un checkout git (existe .git): puede ser la raiz viva de "
                "produccion u otro arbol; usa una instantanea de datos.")
    if not args.pre and not args.parity_only and args.out is not None and Path(args.out).exists():
        return f"--out ya existe ({args.out}): el modo completo es UNA SOLA EJECUCION; no se sobrescribe."
    return None


def _versions() -> dict:
    return {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__,
            "pandas": pd.__version__, "scipy": scipy.__version__}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pre", action="store_true")
    ap.add_argument("--parity-only", action="store_true")
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--pre-json", type=Path, default=None)
    ap.add_argument("--parity-stride", type=int, default=1)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)
    if args.pre and args.parity_only:
        ap.error("--pre y --parity-only son mutuamente excluyentes.")
    if not args.parity_only and args.out is None:
        ap.error("--out es obligatorio salvo en --parity-only.")
    if args.pre_json and (args.pre or args.parity_only):
        ap.error("--pre-json solo aplica al modo completo.")
    if not args.pre and not args.parity_only and args.pre_json is None:
        ap.error("--pre-json es obligatorio en el modo completo.")
    if args.parity_stride != 1 and not args.parity_only:
        ap.error("--parity-stride solo aplica a --parity-only (el modo completo corre a stride 1).")
    err = _data_root_error(args)
    if err:
        ap.error(err)

    t0 = time.perf_counter()
    exit_code = 0
    out: dict[str, Any]
    if args.pre:
        out = {"modo": "pre (sin desenlaces ni cuotas)", **informe_pre(args.data_root)}
        if not out["cota_050_no_vinculante"]:
            print("ATENCION: hay partidos recortados con b = 0,50; la seccion 2 exige una enmienda "
                  "(valor superior de la rejilla) antes del modo completo.", file=sys.stderr)
            exit_code = 2
    elif args.parity_only:
        league_params, _ = assert_family_and_params()
        results, _ = load_mlb(args.data_root)
        kw = pricing_kwargs(get_adapter(LEAGUE, FAMILY, league_params))
        rep = run_parity(results, league_params, kw, args.parity_stride)
        out = {"modo": "parity-only", "resultado": f"PARIDAD OK (n={rep['n_evaluados']}, "
               f"stride={rep['stride']}; T(0), T(0,10), T(0,20) frente al motor a {TOL})", "paridad": rep}
    else:
        check_git_clean(git_status_porcelain(_WORKTREE_ROOT, FULL_GIT_PATHS), "src, configs, scripts/research")
        pre_text = args.pre_json.read_bytes()
        pre = json.loads(pre_text.decode("utf-8"))
        league_params, adapter_params = assert_family_and_params()
        results, proc = load_mlb(args.data_root)
        check_provenance(pre, git_head(_WORKTREE_ROOT), manifest(args.data_root), config_hashes(),
                         {"league_params": league_params, "adapter_params": adapter_params})
        kw = pricing_kwargs(get_adapter(LEAGUE, FAMILY, league_params))
        head = {"modo": "completo", "git_head": git_head(_WORKTREE_ROOT),
                "pre_json_sha256": hashlib.sha256(pre_text).hexdigest(),
                "manifiesto": manifest(args.data_root), "config_sha256": config_hashes(),
                "parametros_resueltos": {"league_params": league_params, "adapter_params": adapter_params},
                "procedencia": proc, "pricing_kwargs": kw, "grid": list(GRID), "folds": FOLDS,
                "versiones": _versions()}

        def write_partial(partial: dict) -> None:
            args.out.write_text(_dump({**head, **partial, "parcial": True,
                                       "segundos": time.perf_counter() - t0}), encoding="utf-8")

        res = run_full(results, league_params, kw, args.n_boot, args.seed, write_partial)
        out = {**head, **res}
    out["segundos"] = time.perf_counter() - t0
    text = _dump(out)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text if args.parity_only else f"escrito {args.out}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
