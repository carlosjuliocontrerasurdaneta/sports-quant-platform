"""Recencia de la anotacion en el adaptador de totales (`scoring_half_life_days`,
NBA, NFL y NHL). Pre-registro `docs/research/2026-10-09-preregistro-recencia-totales.md`
(commit 027c019), que es el CONTRATO de este script.

NO mide ventaja sobre el mercado ni rentabilidad: solo la probabilidad estimada
frente al desenlace. La linea y el no-vig del mercado son referencia de semantica.

Modos (seccion 14):

  --pre --data-root <inst. H> --out pre_H.json
        HEAD, `git status --porcelain` (vacio en todo el repo), manifiesto de
        hashes, parametros resueltos (aserto), recuentos por particion, descartes
        por game_id, ingesta tardia, y la tabla 9.1 (mu_h - mu_base). NO empareja
        ninguna mu con su total ni calcula ninguna perdida; no lee cuotas.
  --parity-only --data-root <inst. H> [--leagues nba,nhl] [--h-subset 0,90]
        Asertos de paridad 1-3 (seccion 11). No estima nada.
  --fase H --data-root <inst. H> --pre-json pre_H.json --out H.json
        Walk-forward historico (seccion 7), bootstrap (10), Holm K = 3.
  --fase M --pre --data-root <inst. M> --h-json H.json --h-sha256 <hex> --out pre_M.json
        Conteo de emparejados con linea y no-vig, sin desenlaces (seccion 8.2).
  --fase M --data-root <inst. M> --h-json H.json --pre-json pre_M.json --out M.json
        Fase de mercado (seccion 8): solo puede VETAR, no aceptar.

Una sola ejecucion por fase (seccion 15). Los informes se redactan a partir de los
JSON; este script no los genera. Las lecturas del contrato citan la Enmienda 1 del pre-registro (a)-(p).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import sys
import time
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
from scipy.stats import norm as _norm
from scipy.stats import poisson as _poisson

import measure_adjustment_battery as bat
from sqp.audit.clv import CLOSE_MAX_AGE_MIN
from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.roi_engine import _match_index, _match_result, load_closing_odds
from sqp.domain.models import Event
from sqp.models import distributions as dist
from sqp.pipeline.daily import _league_meta
from sqp.pipeline.probabilities import (
    _consensus_lines,
    _novig_probs,
    _pick_main_lines,
    build_model_map,
)
from sqp.sports.adapters import NormalMarginAdapter, PoissonAdapter
from sqp.sports.registry import get_adapter
from sqp.sports.team_names import get_team_normalizer
from sqp.storage.results_store import ResultsStore

# --------------------------------------------------- reutilizado de la bateria --
# Alias de modulo: los tests los sustituyen (git, bootstrap) en ESTE modulo.
git_head = bat.git_head
git_status_porcelain = bat.git_status_porcelain
check_git_clean = bat.check_git_clean
sha256_of = bat.sha256_of
bootstrap_dias = bat.bootstrap_dias
holm = bat.holm
p_value = bat.p_value
ll_vec = bat.ll_vec
fit = bat.fit
_clean = bat._clean
_safe_informe = bat._safe_informe
_WORKTREE_ROOT = bat._WORKTREE_ROOT
DEFAULT_ROOT = bat.DEFAULT_ROOT

# ------------------------------------------------------------ constantes --
CUTOFF = bat.CUTOFF                         # 2026-09-26 (seccion 6)
WARMUP = bat.WARMUP                         # 60
TOL = bat.TOL                               # 1e-12 (seccion 11)
N_BOOT, SEED = bat.N_BOOT, bat.SEED         # 10.000, 42 (seccion 10)
ALPHA = bat.ALPHA                           # 0,05
H1_MARGIN = bat.IMPROVEMENT_MARGIN          # 0,002 (`tuning.py:38`; decision 4 del operador)
K_HOLM = 3                                  # una celda por liga (seccion 7.4)

LEAGUES = ("nba", "nfl", "nhl")
FAMILY = {lg: bat.FAMILY[lg] for lg in LEAGUES}
FOLDS = {lg: bat.FOLDS[lg] for lg in LEAGUES}
HALF_LIFE_KEY = "scoring_half_life_days"
GRID = (0.0, 30.0, 45.0, 60.0, 90.0, 120.0, 180.0, 270.0, 365.0, 540.0, 730.0)     # seccion 4
H_VIGENTE = {"nba": 180.0, "nfl": 0.0, "nhl": 0.0}                                # seccion 3
H_PROBE = 90.0                                                                     # seccion 11.2
MAX_GOALS = 15                              # `max_score` del adaptador NHL (aserto de parametros)
LEVEL_FLOOR = 1e-300                        # suelo de P(T = k) antes del log

PARITY_TOTAL_LINE = {"nba": 220.5, "nfl": 44.5, "nhl": 5.5}                        # seccion 11.1
PARITY_SPREADS = {"nba": (), "nfl": (), "nhl": (-1.5, 1.5)}
PARITY_NHL_OVER_LINES = (4.5, 5.5, 6.5, 7.5)                                       # seccion 11.3

BATTERY_PRE_NAME = "pre_ee0ab19.json"
BATTERY_PRE_SHA256 = "173a5c1ce3c58963e610e1bef9f03a83d7535299e0d21f77d5bab1da866c14be"

# Fase M (seccion 8)
MARKET_START = "2026-03-01"
M_CUTOFF = "2027-01-31"
M_CUTOFF_EXT = "2027-04-20"
M_MIN_N = {"nba": 800, "nhl": 800, "nfl": 250}

# Tabla 9.1 del pre-registro: {liga: {h: (media, RMS)}} en el test C, a 2 decimales.
DOC_TABLE_9_1: dict[str, dict[float, tuple[float, float]]] = {
    "nba": {0.0: (-20.90, 21.40), 30.0: (1.08, 3.33), 60.0: (0.96, 2.30), 90.0: (0.72, 1.52),
            120.0: (0.46, 0.90), 365.0: (-1.26, 1.72), 730.0: (-4.31, 4.82)},
    "nfl": {30.0: (-0.53, 3.70), 60.0: (-0.35, 2.99), 90.0: (-0.11, 2.63), 120.0: (0.06, 2.44),
            180.0: (0.28, 2.24), 365.0: (0.67, 1.99), 730.0: (0.91, 1.72)},
    "nhl": {30.0: (0.43, 0.53), 60.0: (0.44, 0.51), 90.0: (0.45, 0.51), 120.0: (0.45, 0.51),
            180.0: (0.45, 0.50), 365.0: (0.43, 0.46), 730.0: (0.34, 0.37)},
}
# Enmienda 1(a): tolerancia de la tabla 9.1 = una unidad del ultimo decimal impreso (0,01), no media unidad:
# con datos reales NBA h = 90 da media 0,7145 y el documento imprime 0,72 (doble redondeo), asi que 0,0051 abortaria.
DOC_TABLE_TOL = 0.0101
FULL_GIT_PATHS = ("src", "configs", "scripts/research")
SIGMA_KEY = "total_sigma"


# -------------------------------------------------------------- utilidades --
def code_hashes() -> dict:
    """SHA-256 de este script y del de la bateria (Enmienda 1(e), F4), con los finales de
    linea normalizados a LF (Enmienda 1(q)): una copia CRLF reescrita por git no es un cambio."""
    here = Path(__file__).resolve().parent
    return {n: hashlib.sha256((here / n).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            for n in ("measure_totals_recency.py", "measure_adjustment_battery.py")}


def candidate_params(league_params: dict | None, h: float) -> dict:
    """Seccion 5: el candidato es SIEMPRE `league_params U {scoring_half_life_days: h}`."""
    out = dict(league_params or {})
    out[HALF_LIFE_KEY] = float(h)
    return out


def hkey(h: float) -> str:
    return str(float(h))


def select_h(train_loss: dict[float, float], h_vig: float) -> float:
    """Seccion 4: h_P = argmin de la perdida media de entrenamiento. Empate exacto:
    el h mas cercano al vigente; si persiste, el mayor. El test nunca interviene."""
    if not train_loss:
        raise SystemExit("select_h: rejilla vacia.")
    if any(not math.isfinite(v) for v in train_loss.values()):
        raise SystemExit("select_h: perdida de entrenamiento no finita en la rejilla.")
    best = min(train_loss.values())
    tied = [h for h, v in train_loss.items() if v == best]
    tied.sort(key=lambda h: (abs(h - h_vig), -h))
    return float(tied[0])


def resolved_report(leagues: tuple[str, ...] | list[str]) -> dict:
    out: dict = {}
    for lg in leagues:
        lp = _league_meta(lg).get("league_params")
        fam = FAMILY.get(lg) or _league_meta(lg)["family"]
        out[lg] = {"league_params": lp, "adapter_params": dict(get_adapter(lg, fam, lp).params)}
    return out


def assert_vigente_matches_params() -> None:
    for lg in LEAGUES:
        exp = float(bat.EXPECTED_ADAPTER_PARAMS[lg].get(HALF_LIFE_KEY, 0.0))
        if exp != H_VIGENTE[lg]:
            raise SystemExit(f"{lg}: h vigente {exp} != {H_VIGENTE[lg]} (seccion 3). Se aborta.")
    if float(H_PROBE) not in GRID or any(h not in GRID for h in H_VIGENTE.values()):
        raise SystemExit("La rejilla debe contener el h vigente de cada liga y el h de prueba.")


def load_league_cut(league: str, data_root: Path, cutoff: str) -> tuple[list[dict], dict | None, dict]:
    """Resultados con `date <= cutoff`, filtro de game_id de la Enmienda 3(c) de la
    bateria (0 descartes esperados), aserciones de parametros en dos niveles y
    procedencia. Misma logica que `bat.load_league` con el corte parametrizado
    (la fase M corta en D, la fase H en 2026-09-26)."""
    store = ResultsStore(data_root)
    rows = [r for r in store.load(league) if str(r.get("date", ""))[:10] <= cutoff]
    n_before = len(rows)
    rows, dropped = bat.dedupe_by_game_id(rows)
    bat.assert_dedupe_drops(league, dropped)
    meta_params = _league_meta(league).get("league_params")
    adapter_params = dict(get_adapter(league, FAMILY[league], meta_params).params)
    bat.assert_resolved_params(league, meta_params, adapter_params)
    proc: dict = {"fichero": str(store.path(league)), "corte": cutoff,
                  "filas_antes_dedupe_game_id": n_before, "filas_leidas": len(rows),
                  "descartadas_dedupe_game_id": [list(d) for d in dropped]}
    if store.path(league).exists():
        proc["sha256"] = sha256_of(store.path(league))
    return rows, meta_params, proc


def manifest(data_root: Path, *, odds: bool) -> dict:
    """SHA-256 y filas de los ficheros que lee cada fase. Fase H: solo resultados
    (no lee cuotas). Fase M: resultados y todos los `odds_{liga}_*.csv`."""
    files: list[Path] = [ResultsStore(data_root).path(lg) for lg in LEAGUES]
    if odds:
        for lg in LEAGUES:
            files.extend(sorted((data_root / "data" / "odds").glob(f"odds_{lg}_*.csv")))
    out: dict[str, dict] = {}
    for p in files:
        rel = p.relative_to(data_root).as_posix()
        out[rel] = ({"sha256": sha256_of(p), "filas": bat._count_rows(p)} if p.exists()
                    else {"sha256": None, "filas": None})
    return out


def check_manifest_equal(prev: dict, now: dict, what: str) -> None:
    if not prev:
        raise SystemExit(f"{what}: el JSON previo no registra 'manifiesto'. Se aborta.")
    if set(prev) != set(now):
        raise SystemExit(f"HASH DE ENTRADA: el conjunto de ficheros leidos difiere del de {what}: "
                         f"{sorted(set(prev) ^ set(now))}. Se aborta.")
    changed = [k for k in prev if prev[k].get("sha256") != now[k].get("sha256")
               or prev[k].get("filas") != now[k].get("filas")]
    if changed:
        raise SystemExit(f"HASH DE ENTRADA CAMBIO en {changed} respecto de {what}. Se aborta.")


def check_provenance(pre: dict, head_now: str | None, manifest_now: dict, cfg_now: dict,
                     params_now: dict, what: str) -> None:
    """Seccion 14: aborta si el HEAD, los hashes o los parametros difieren del JSON previo."""
    if pre.get("git_head") is None:
        raise SystemExit(f"{what} no registra 'git_head'. Se aborta.")
    if head_now is None:
        raise SystemExit("No se pudo obtener 'git rev-parse HEAD'. Se aborta.")
    if pre["git_head"] != head_now:
        raise SystemExit(f"HEAD DE GIT CAMBIO: {what} registra {pre['git_head']} y el HEAD actual es "
                         f"{head_now}. Se aborta.")
    check_manifest_equal(pre.get("manifiesto") or {}, manifest_now, what)
    if pre.get("config_sha256") != cfg_now:
        raise SystemExit(f"SHA-256 de ratings.yaml/default.yaml distinto del de {what}. Se aborta.")
    if _clean(pre.get("parametros_resueltos")) != _clean(params_now):
        raise SystemExit(f"Parametros resueltos distintos de los de {what}. Se aborta.")
    if "codigo_sha256" not in pre:
        raise SystemExit(f"{what} no registra codigo_sha256. Se aborta.")
    if pre["codigo_sha256"] != code_hashes():
        raise SystemExit(f"El codigo difiere del de {what} (SHA-256). Se aborta.")


# ---------------------------------------------------------------- recorrido --
def walk_mu(results: list[dict], league: str, family: str, league_params: dict | None, *,
            warmup: int = WARMUP) -> dict[str, np.ndarray]:
    """Un walk-forward del adaptador de produccion: por partido evaluado, la mu del
    total con el estado al CIERRE DEL DIA ANTERIOR (bucle de `walk_forward_backtest`).
    NUNCA lee el marcador del partido que estima: los marcadores solo entran al
    modelo por `observe`, despues de cerrar el dia. No devuelve ningun desenlace.

    NBA/NFL: mu = `scoring.expected_total`. NHL: lam_h, lam_a de `_rates` (mu = suma,
    como la bateria) mas avg y tilt, para el control de nivel C (seccion 7.2)."""
    ordered = sorted(results, key=lambda row: str(row.get("date", "")))
    adapter = get_adapter(league, family, league_params)
    hockey = isinstance(adapter, PoissonAdapter)
    if not hockey and not isinstance(adapter, NormalMarginAdapter):
        raise SystemExit(f"{league}: familia {family} fuera del alcance de este script.")
    tilt_scale = adapter.params.get("tilt_scale", 0.9)
    scoring_on = adapter.params.get("scoring_totals", True)
    dates: list[str] = []
    mu_l: list[float] = []
    avg_l: list[float] = []
    tilt_l: list[float] = []
    lh_l: list[float] = []
    la_l: list[float] = []
    pending: list[dict] = []
    for i, r in enumerate(ordered):
        rd = str(r.get("date", ""))[:10]
        if pending and rd != str(pending[0].get("date", ""))[:10]:
            for completed in pending:
                adapter.observe(completed)
            pending.clear()
        if i >= warmup:
            if hockey:
                ev = Event(event_id=str(i), sport_key="bt", league=league, home=r["home"],
                           away=r["away"], start_time=str(r.get("date")),
                           data_label=r.get("data_label", "real"))
                lam_h, lam_a = adapter._rates(ev)
                avg = adapter.params["avg_total"]
                if scoring_on:
                    avg = adapter.scoring.expected_total(ev.home, ev.away, avg)
                diff = adapter.elo.rating_diff(ev.home, ev.away) + adapter.rest.margin_adjustment(
                    ev.home, ev.away, str(ev.start_time)[:10])
                p_home = 1.0 / (1.0 + 10 ** (-diff / 400.0))
                tilt = max(-0.30, min(0.30, (p_home - 0.5) * tilt_scale))
                mu_l.append(lam_h + lam_a)
                avg_l.append(avg)
                tilt_l.append(tilt)
                lh_l.append(lam_h)
                la_l.append(lam_a)
            else:
                mu = adapter.params["avg_total"]
                if scoring_on:
                    mu = adapter.scoring.expected_total(r["home"], r["away"], mu)
                mu_l.append(mu)
            dates.append(rd)
        pending.append(r)
    out: dict[str, np.ndarray] = {"date": np.asarray(dates, dtype=str), "mu": np.asarray(mu_l, float)}
    if hockey:
        out.update(avg=np.asarray(avg_l, float), tilt=np.asarray(tilt_l, float),
                   lam_h=np.asarray(lh_l, float), lam_a=np.asarray(la_l, float))
    return out


def read_outcomes(results: list[dict], *, warmup: int = WARMUP) -> dict[str, np.ndarray]:
    """Marcadores de los partidos EVALUADOS (mismo orden que `walk_mu`). Solo la
    fase H y la paridad la llaman: `--pre` jamas (hay un test que lo fija)."""
    rows = sorted(results, key=lambda row: str(row.get("date", "")))[warmup:]
    hs = np.asarray([float(r["home_score"]) for r in rows], float)
    aw = np.asarray([float(r["away_score"]) for r in rows], float)
    return {"home": hs, "away": aw, "total": hs + aw, "margin": hs - aw}


def l_base(mu_base: np.ndarray) -> np.ndarray:
    """L_i^base = floor(mu_base) + 0,5 (la linea de la bateria)."""
    return np.floor(mu_base) + 0.5


def l_hash(line: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(line, float)).tobytes()).hexdigest()


# ----------------------------------------------------------- distribuciones --
def normal_nll(mu: np.ndarray, total: np.ndarray, sigma: float) -> np.ndarray:
    """-log[phi((T - mu)/sigma)/sigma] (seccion 7.3), igual a `-norm.logpdf`."""
    z = (np.asarray(total, float) - np.asarray(mu, float)) / sigma
    return 0.5 * z * z + math.log(sigma) + 0.5 * math.log(2.0 * math.pi)


def normal_over(mu: np.ndarray, sigma: float, line: np.ndarray | float) -> np.ndarray:
    """P(Over line) = `dist.normal_total_probs(...)["over"]` vectorizada, con la
    probabilidad condicionada a no empuje en las lineas enteras."""
    mu = np.asarray(mu, float)
    ln = np.broadcast_to(np.asarray(line, float), mu.shape)
    half = 1.0 - _norm.cdf(ln, mu, sigma)
    up, dn = _norm.cdf(ln + 0.5, mu, sigma), _norm.cdf(ln - 0.5, mu, sigma)
    integer = ln == np.floor(ln)
    whole = (1.0 - up) / np.maximum(1e-12, 1.0 - (up - dn))
    return np.where(integer, whole, half)


def hockey_pt(lam_h: np.ndarray, lam_a: np.ndarray, max_goals: int = MAX_GOALS) -> np.ndarray:
    """P(T = k), k = 0..2*max_goals, de la rejilla conjunta de Poisson truncada en
    `max_goals` por equipo y renormalizada, como `poisson_match_probs`."""
    scores = np.arange(max_goals + 1)
    ph = _poisson.pmf(scores[None, :], np.asarray(lam_h, float)[:, None])
    pa = _poisson.pmf(scores[None, :], np.asarray(lam_a, float)[:, None])
    pt = np.zeros((len(ph), 2 * max_goals + 1))
    for i in range(max_goals + 1):
        pt[:, i:i + max_goals + 1] += ph[:, i:i + 1] * pa
    return pt / pt.sum(axis=1)[:, None]


def hockey_over(pt: np.ndarray, line: np.ndarray | float) -> np.ndarray:
    """P(Over line | no empuje) desde P(T = k): lineas de medio punto y enteras."""
    ln = np.broadcast_to(np.asarray(line, float), (len(pt),))
    k = pt.shape[1]
    tail = np.cumsum(pt[:, ::-1], axis=1)[:, ::-1]
    rows = np.arange(len(pt))
    fl = np.floor(ln).astype(int)
    over = np.where(fl + 1 <= k - 1, tail[rows, np.clip(fl + 1, 0, k - 1)], 0.0)
    integer = ln == np.floor(ln)
    push = np.where(integer & (fl >= 0) & (fl <= k - 1), pt[rows, np.clip(fl, 0, k - 1)], 0.0)
    return over / np.maximum(1e-12, 1.0 - push)


def hockey_margin(lam_h: np.ndarray, lam_a: np.ndarray, spreads: tuple[float, ...],
                  max_goals: int = MAX_GOALS, chunk: int = 2048) -> dict[str, np.ndarray]:
    """P(local gana) (sin empates: el empate se reparte 50/50, como `poisson_match_probs`
    con dos resultados) y P(local cubre s) para lineas de medio punto."""
    if any(float(s).is_integer() for s in spreads):
        raise ValueError("hockey_margin solo admite lineas de medio punto.")
    mg1 = max_goals + 1
    m = (np.arange(mg1)[:, None] - np.arange(mg1)[None, :]).ravel()
    win_m, draw_m = (m > 0).astype(float), (m == 0).astype(float)
    cover_m = {s: (m > -s).astype(float) for s in spreads}
    scores = np.arange(mg1)
    n = len(lam_h)
    out: dict[str, np.ndarray] = {"home_win": np.empty(n), **{f"cover@{s}": np.empty(n) for s in spreads}}
    for a in range(0, n, chunk):
        sl = slice(a, min(n, a + chunk))
        ph = _poisson.pmf(scores[None, :], np.asarray(lam_h, float)[sl, None])
        pa = _poisson.pmf(scores[None, :], np.asarray(lam_a, float)[sl, None])
        joint = (ph[:, :, None] * pa[:, None, :]).reshape(len(ph), -1)
        mass = joint.sum(axis=1)
        out["home_win"][sl] = (joint @ win_m + 0.5 * (joint @ draw_m)) / mass
        for s, cm in cover_m.items():
            out[f"cover@{s}"][sl] = (joint @ cm) / mass
    return out


def hockey_lambdas(avg: np.ndarray, tilt: np.ndarray, bonus: float, shift: float = 0.0
                   ) -> tuple[np.ndarray, np.ndarray]:
    """Mismas formulas de `PoissonAdapter._rates` con `avg + shift` (control C)."""
    a = np.asarray(avg, float) + shift
    return (np.maximum(0.1, a * (0.5 + tilt) + bonus), np.maximum(0.1, a * (0.5 - tilt)))


def hockey_nll(lam_h: np.ndarray, lam_a: np.ndarray, total: np.ndarray, max_goals: int = MAX_GOALS
               ) -> tuple[np.ndarray, np.ndarray]:
    """(-log P(T = T_i), valido). Fuera de la rejilla o no entero: invalido (NaN)."""
    pt = hockey_pt(lam_h, lam_a, max_goals)
    t = np.asarray(total, float)
    valid = np.isfinite(t) & (t == np.floor(t)) & (t >= 0) & (t <= 2 * max_goals)
    ki = np.where(valid, t, 0).astype(int)
    p = pt[np.arange(len(pt)), ki]
    return np.where(valid, -np.log(np.maximum(p, LEVEL_FLOOR)), np.nan), valid


class LeagueSpec:
    """Parametros efectivos de una liga (los asertados en la seccion 5)."""

    def __init__(self, league: str, params: dict) -> None:
        self.league = league
        self.hockey = FAMILY[league] == "hockey"
        self.sigma = float(params.get(SIGMA_KEY, 0.0))
        self.bonus = float(params.get("home_scoring_bonus", 0.0))
        self.max_goals = int(params.get("max_score", MAX_GOALS))


def total_loss(spec: LeagueSpec, walk: dict, total: np.ndarray, shift: float = 0.0
               ) -> tuple[np.ndarray, np.ndarray]:
    """Perdida por partido (seccion 7.3) y mascara de validez. `shift` = a_P del
    control C (en NHL entra como `avg_i + a_P` en las formulas de lambda)."""
    if spec.hockey:
        if shift == 0.0:
            lh, la = walk["lam_h"], walk["lam_a"]
        else:
            lh, la = hockey_lambdas(walk["avg"], walk["tilt"], spec.bonus, shift)
        return hockey_nll(lh, la, total, spec.max_goals)
    valid = np.isfinite(total)
    return np.where(valid, normal_nll(walk["mu"] + shift, total, spec.sigma), np.nan), valid


def over_prob(spec: LeagueSpec, walk: dict, line: np.ndarray | float) -> np.ndarray:
    if spec.hockey:
        return hockey_over(hockey_pt(walk["lam_h"], walk["lam_a"], spec.max_goals), line)
    return normal_over(walk["mu"], spec.sigma, line)


def fit_level_shift(spec: LeagueSpec, walk: dict, total: np.ndarray, train: np.ndarray) -> float:
    """a_P del control C: minimiza la MISMA perdida en el entrenamiento de P.
    NHL: Nelder-Mead de la bateria."""
    # Enmienda 1(d): NBA/NFL usan la media del residuo (minimo EXACTO de la perdida normal con sigma fija)
    # en vez de un optimizador; el contrato dice "minimizando la misma perdida" sin nombrar metodo.
    if not train.any():
        raise SystemExit("fit_level_shift: entrenamiento vacio.")
    _, valid = total_loss(spec, walk, total)
    tr = train & valid
    if not tr.any():
        raise SystemExit("fit_level_shift: entrenamiento sin partidos validos.")
    if not spec.hockey:
        return float(np.mean(total[tr] - walk["mu"][tr]))
    avg, tilt, tt = walk["avg"][tr], walk["tilt"][tr], total[tr]

    def objective(v: np.ndarray) -> float:
        lh, la = hockey_lambdas(avg, tilt, spec.bonus, float(v[0]))
        return float(np.mean(hockey_nll(lh, la, tt, spec.max_goals)[0]))

    return float(fit(objective, [0.0], "a (control C, NHL)")[0])


# --------------------------------------------------------- tabla 9.1 y --pre --
def partition_masks(dates: np.ndarray, folds: dict[str, dict[str, str]]) -> dict[str, dict[str, np.ndarray]]:
    return {name: {"train": dates <= f["train_end"],
                   "test": (dates >= f["test_start"]) & (dates <= f["test_end"])}
            for name, f in folds.items()}


def table_9_1(base: dict, grid: dict[float, dict], test_c: np.ndarray) -> dict[str, dict]:
    """Seccion 9.1: media y RMS de (mu_h - mu_base) en el test C. No usa desenlaces."""
    out: dict[str, dict] = {}
    for h in sorted(grid):
        d = (grid[h]["mu"] - base["mu"])[test_c]
        out[hkey(h)] = {"media": float(np.mean(d)), "rms": float(np.sqrt(np.mean(d * d))), "n": int(len(d))}
    return out


def compare_doc_table(league: str, table: dict[str, dict]) -> dict:
    """Compara la tabla recalculada con la impresa en el pre-registro (2 decimales)."""
    diffs: dict[str, dict] = {}
    bad: list[str] = []
    for h, (mean_ref, rms_ref) in DOC_TABLE_9_1[league].items():
        got = table[hkey(h)]
        dm, dr = abs(got["media"] - mean_ref), abs(got["rms"] - rms_ref)
        diffs[hkey(h)] = {"dif_media": dm, "dif_rms": dr}
        if dm > DOC_TABLE_TOL or dr > DOC_TABLE_TOL:
            bad.append(hkey(h))
    return {"diferencias": diffs, "no_coinciden": bad, "coincide": not bad, "tolerancia": DOC_TABLE_TOL}


def load_battery_pre(data_root: Path) -> dict:
    """`pre_ee0ab19.json` de la bateria (sin desenlaces), verificado por SHA-256."""
    p = data_root / BATTERY_PRE_NAME
    if not p.exists():
        raise SystemExit(f"Falta {p}: el aserto 5 de la seccion 11 compara con el --pre de la bateria.")
    got = sha256_of(p)
    if got != BATTERY_PRE_SHA256:
        raise SystemExit(f"{p} tiene SHA-256 {got} != {BATTERY_PRE_SHA256}. Se aborta.")
    return json.loads(p.read_text(encoding="utf-8"))


def check_against_battery(league: str, counts: dict, line_hash: str, n_eval: int, battery: dict) -> dict:
    """Aserto 5 (seccion 11): lineas L_i^base, recuentos por particion y evaluados
    iguales a los de la bateria. Aborta si difieren."""
    ref = battery["ligas"][league]
    rep: dict = {"evaluados": (n_eval, ref["evaluados"]),
                 "sha256_lineas_L": (line_hash, ref["lineas_L"]["sha256_vector"])}
    ok = n_eval == ref["evaluados"] and line_hash == ref["lineas_L"]["sha256_vector"]
    for name, c in counts.items():
        r = ref["particiones"][name]
        rep[f"particion_{name}"] = {"partidos": (c["partidos"], r["partidos"]), "dias": (c["dias"], r["dias"])}
        ok = ok and c["partidos"] == r["partidos"] and c["dias"] == r["dias"]
    if not ok:
        raise SystemExit(f"{league}: la base NO coincide con el --pre de la bateria (aserto 5): {rep}. "
                         "Se aborta: la base no es la que midio la bateria.")
    return {"coincide": True, "detalle": rep}


def month_counts(results: list[dict]) -> dict[str, int]:
    cnt: dict[str, int] = defaultdict(int)
    for r in results:
        cnt[str(r.get("date", ""))[5:7]] += 1
    return dict(sorted(cnt.items()))


class LeagueRun:
    """Datos de una liga para la fase H: filas, walks (base y rejilla) y especificacion."""

    def __init__(self, league: str, data_root: Path, *, grid: tuple[float, ...] = GRID,
                 cutoff: str = CUTOFF) -> None:
        self.league = league
        self.results, self.league_params, self.proc = load_league_cut(league, data_root, cutoff)
        self.params = dict(get_adapter(league, FAMILY[league], self.league_params).params)
        self.spec = LeagueSpec(league, self.params)
        self.h_vig = H_VIGENTE[league]
        self.grid_hs = tuple(sorted(set(float(h) for h in grid) | {self.h_vig}))
        self.base = walk_mu(self.results, league, FAMILY[league], self.league_params)
        self.grid = {h: walk_mu(self.results, league, FAMILY[league],
                                candidate_params(self.league_params, h)) for h in self.grid_hs}
        for k in self.base:     # la base ES el recorrido de la rejilla en el h vigente (aserto interno)
            if not np.array_equal(self.base[k], self.grid[self.h_vig][k]):
                raise SystemExit(f"{league}: el recorrido base difiere del de la rejilla en h = "
                                 f"{self.h_vig} ({k}). Se aborta.")
        self.dates = self.base["date"]
        self.masks = partition_masks(self.dates, FOLDS[league])
        self.in_test = np.zeros(len(self.dates), dtype=bool)
        for m in self.masks.values():
            self.in_test |= m["test"]


def pre_league(run: LeagueRun, battery: dict, data_root: Path) -> dict:
    """Informe `--pre` de una liga: sin desenlaces, sin perdidas."""
    lg = run.league
    counts = {name: {"partidos": int(m["test"].sum()), "dias": int(len(np.unique(run.dates[m["test"]]))),
                     "ref_partidos": bat.REF_FOLD_GAMES[lg][name], "ref_dias": bat.REF_FOLD_DAYS[lg][name]}
              for name, m in run.masks.items()}
    line_hash = l_hash(l_base(run.base["mu"]))
    table = table_9_1(run.base, run.grid, run.masks["C"]["test"])
    cmp_doc = compare_doc_table(lg, table)
    if not cmp_doc["coincide"]:
        raise SystemExit(f"{lg}: la tabla 9.1 recalculada no reproduce la del pre-registro en h = "
                         f"{cmp_doc['no_coinciden']}: {cmp_doc['diferencias']}. Se aborta (Enmienda 1(a)).")
    return {"procedencia": run.proc, "evaluados": int(len(run.dates)),
            "filas_hasta_corte": len(run.results), "particiones": counts,
            "sha256_lineas_L": line_hash,
            "aserto5_bateria": check_against_battery(lg, counts, line_hash, int(len(run.dates)), battery),
            "tabla_9_1": table, "tabla_9_1_vs_pre_registro": cmp_doc,
            "ingesta": bat.ingestion_report(lg, data_root, FOLDS[lg]),
            "filas_por_mes": month_counts(run.results)}


def informe_pre_H(data_root: Path) -> dict:
    head = git_head(_WORKTREE_ROOT)
    status = git_status_porcelain(_WORKTREE_ROOT)
    check_git_clean(status, "todo el repositorio")
    assert_vigente_matches_params()
    battery = load_battery_pre(data_root)
    out: dict = {"git_head": head, "git_status_porcelain": status, "snapshot_root": str(data_root),
                 "corte_datos": CUTOFF, "manifiesto": manifest(data_root, odds=False),
                 "codigo_sha256": code_hashes(), "config_sha256": bat.config_hashes(), "parametros_resueltos": resolved_report(LEAGUES),
                 "rejilla": list(GRID), "ligas": {}}
    for k, v in out["manifiesto"].items():     # misma instantanea que la bateria (seccion 6)
        ref = battery["manifiesto"].get(k)
        if ref is None or ref.get("sha256") != v["sha256"] or ref.get("filas") != v["filas"]:
            raise SystemExit(f"{k}: el manifiesto NO coincide con el de la bateria (seccion 6). Se aborta.")
    if battery["config_sha256"] != out["config_sha256"]:
        raise SystemExit("SHA-256 de configuracion distinto del de la bateria (seccion 5). Se aborta.")
    for lg in LEAGUES:
        out["ligas"][lg] = pre_league(LeagueRun(lg, data_root), battery, data_root)
    out["tabla_9_1"] = {lg: out["ligas"][lg]["tabla_9_1"] for lg in LEAGUES}
    out["recuentos"] = {lg: {n: (c["partidos"], c["dias"]) for n, c in out["ligas"][lg]["particiones"].items()}
                        for lg in LEAGUES}
    return out


# ------------------------------------------------------------------ fase H --
def evaluate_league_H(run: LeagueRun, outcomes: dict[str, np.ndarray], *, n_boot: int | None = None) -> dict:
    """Secciones 7.2-7.4 y 10 para una liga. Devuelve ademas `_w` (trabajo)."""
    lg, spec, folds = run.league, run.spec, FOLDS[run.league]
    total, margin = outcomes["total"], outcomes["margin"]
    n = len(total)
    if n != len(run.dates):
        raise SystemExit(f"{lg}: desenlaces ({n}) y recorrido ({len(run.dates)}) desalineados.")
    names = list(folds)
    loss_h: dict[float, np.ndarray] = {}
    valid = np.ones(n, dtype=bool)
    for h in run.grid_hs:
        loss_h[h], valid = total_loss(spec, run.grid[h], total)
    loss_b, _ = total_loss(spec, run.base, total)
    # --- seleccion en entrenamiento (seccion 4) -----------------------------
    h_p: dict[str, float] = {}
    train_profile: dict[str, dict[str, float]] = {}
    a_p: dict[str, float] = {}
    for name in names:
        tr = run.masks[name]["train"] & valid
        if not tr.any():
            raise SystemExit(f"{lg}: entrenamiento vacio en la particion {name}.")
        prof = {h: float(np.mean(loss_h[h][tr])) for h in run.grid_hs}
        train_profile[name] = {hkey(h): v for h, v in prof.items()}
        h_p[name] = select_h(prof, run.h_vig)
        a_p[name] = fit_level_shift(spec, run.base, total, run.masks[name]["train"])
    # --- brazos T y C compuestos por particion ------------------------------
    loss_t = np.full(n, np.nan)
    loss_c = np.full(n, np.nan)
    line = l_base(run.base["mu"])
    y4 = (total > line).astype(float)
    p4_base = over_prob(spec, run.base, line)
    p4_t = np.full(n, np.nan)
    for name in names:
        te = run.masks[name]["test"]
        loss_t[te] = loss_h[h_p[name]][te]
        loss_c[te] = total_loss(spec, run.base, total, a_p[name])[0][te]
        p4_t[te] = over_prob(spec, run.grid[h_p[name]], line)[te]
    # Enmienda 1(b): la exclusion de T_i fuera de la rejilla NHL (seccion 7.3, "de todos los brazos") se aplica a
    # TODAS las metricas basadas en el total (H1, T-C, H4); h2h y puck line (H5) conservan su propia muestra.
    tv = run.in_test & valid
    d1 = np.where(tv, loss_t - loss_b, 0.0)
    dtc = np.where(tv, loss_t - loss_c, 0.0)
    d4 = np.where(tv, ll_vec(np.where(tv, p4_t, 0.5), y4) - ll_vec(np.where(tv, p4_base, 0.5), y4), 0.0)
    stats: dict[str, tuple[np.ndarray, np.ndarray]] = {
        "delta_H1": (d1, tv.astype(float)), "T_menos_C": (dtc, tv.astype(float)),
        "delta_H4": (d4, tv.astype(float))}
    per_part: dict[str, float | None] = {}
    losses: dict[str, dict] = {}
    for name in names:
        te = run.masks[name]["test"] & valid
        stats[f"particion_{name}"] = (np.where(te, d1, 0.0), te.astype(float))
        per_part[name] = float(np.mean(d1[te])) if te.any() else None
        losses[name] = {arm: (float(np.mean(arr[te])) if te.any() else None)
                        for arm, arr in (("base", loss_b), ("T", loss_t), ("C", loss_c))}
    losses["combinado"] = {arm: float(np.mean(arr[tv])) for arm, arr in (("base", loss_b), ("T", loss_t), ("C", loss_c))}
    delta_h1 = float(np.mean(d1[tv]))
    t_menos_c = float(np.mean(dtc[tv]))
    delta_h4 = float(np.mean(d4[tv]))
    # --- H5 (solo NHL): h2h y puck line con el h_P de cada particion ---------
    h5: dict | None = None
    if spec.hockey:
        sp = PARITY_SPREADS["nhl"]
        mb = hockey_margin(run.base["lam_h"], run.base["lam_a"], sp, spec.max_goals)
        mt: dict[str, np.ndarray] = {k: np.full(n, np.nan) for k in mb}
        for name in names:
            te = run.masks[name]["test"]
            w = run.grid[h_p[name]]
            mm = hockey_margin(w["lam_h"], w["lam_a"], sp, spec.max_goals)
            for k in mt:
                mt[k][te] = mm[k][te]
        # Enmienda 1(c): "Delta medio de spreads@-1,5 y spreads@+1,5 <= 0" se lee como la media por partido de las
        # dos lineas (peso igual, como la bateria); H5 exige ademas h2h <= 0 por separado.
        y_h2h = np.where(margin == 0, np.nan, (margin > 0).astype(float))
        v_h2h = run.in_test & np.isfinite(y_h2h)
        yh = np.where(v_h2h, y_h2h, 0.0)
        d_h2h = np.where(v_h2h, ll_vec(np.where(v_h2h, mt["home_win"], 0.5), yh)
                         - ll_vec(np.where(v_h2h, mb["home_win"], 0.5), yh), 0.0)
        d_sp = np.zeros(n)
        for s in sp:
            ys = (margin > -s).astype(float)
            d_sp += ll_vec(np.where(run.in_test, mt[f"cover@{s}"], 0.5), ys) \
                - ll_vec(np.where(run.in_test, mb[f"cover@{s}"], 0.5), ys)
        d_sp = np.where(run.in_test, d_sp / len(sp), 0.0)
        stats["delta_H5_h2h"] = (d_h2h, v_h2h.astype(float))
        stats["delta_H5_spreads"] = (d_sp, run.in_test.astype(float))
        h5 = {"h2h": float(np.mean(d_h2h[v_h2h])), "spreads": float(np.mean(d_sp[run.in_test])),
              "n_h2h": int(v_h2h.sum()), "n_spreads": int(run.in_test.sum())}
    # --- bootstrap por dias UTC (seccion 10) ---------------------------------
    boot = bootstrap_dias(run.dates[run.in_test], {k: (a[run.in_test], b[run.in_test]) for k, (a, b) in stats.items()},
                          **({} if n_boot is None else {"n_boot": n_boot}))
    boot_out = {k: {"IC95": v["ic95"], "EE": v["se"], "n_replicas": v["n_replicas"], "n_dias": v["n_dias"]}
                for k, v in boot.items()}
    ee = boot["delta_H1"]["se"]
    p = p_value(delta_h1, ee)
    crit = {"H1": delta_h1 <= -H1_MARGIN,
            "H2": all(v is not None and v < 0 for v in per_part.values()),
            "H3": t_menos_c < 0,
            "H4": delta_h4 <= 0,
            "H5": True if h5 is None else bool(h5["h2h"] <= 0 and h5["spreads"] <= 0)}
    res = {"h_por_particion": {k: v for k, v in h_p.items()}, "a_por_particion": a_p,
           "h_vigente": run.h_vig, "perdidas": losses, "delta_H1": delta_h1, "delta_por_particion": per_part,
           "T_menos_C": t_menos_c, "delta_H4": delta_h4, "delta_H5": h5, "n_test": int(tv.sum()),
           "n_fuera_de_rejilla": int((run.in_test & ~valid).sum()),
           "bootstrap": boot_out, "p": p, "criterios": crit,
           "_w": {"loss_h": loss_h, "loss_b": loss_b, "loss_t": loss_t, "loss_c": loss_c, "tv": tv,
                  "valid": valid, "d1": d1, "train_profile": train_profile, "total": total}}
    return res


def apply_holm(per_league: dict[str, dict]) -> dict:
    """Seccion 7.4 criterio H6: Holm sobre K = 3, alfa de familia 0,05."""
    pvals = {lg: per_league[lg]["p"] for lg in per_league}
    if len(pvals) != K_HOLM:
        raise SystemExit(f"La familia de Holm tiene {len(pvals)} celdas y debe tener {K_HOLM}.")
    det = holm(pvals, ALPHA)
    order = sorted(det, key=lambda k: det[k]["rango"])
    return {"orden": order, "umbrales": {k: det[k]["umbral"] for k in order},
            "p_ajustados": {k: det[k]["p_ajustado"] for k in order},
            "rechazadas": [k for k in order if det[k]["rechaza"]], "detalle": det, "alfa": ALPHA, "K": K_HOLM}


def informes_H(run: LeagueRun, res: dict) -> dict[str, object]:
    """Informes secundarios 1-4 (seccion 13); no deciden."""
    w = res["_w"]
    tv, loss_b = w["tv"], w["loss_b"]
    names = list(FOLDS[run.league])
    out: dict[str, object] = {}

    def inf1() -> dict:
        hp = res["h_por_particion"]
        ext = {n: (hp[n] in (min(run.grid_hs), max(run.grid_hs))) for n in names}
        return {"perdida_entrenamiento": w["train_profile"], "h_por_particion": hp,
                "h_C_en_extremo_de_la_rejilla": ext["C"], "en_extremo": ext}

    def inf2() -> dict:
        tot, spec = w["total"], run.spec
        rep: dict = {}
        for name in names + ["combinado"]:
            m = tv if name == "combinado" else (run.masks[name]["test"] & w["valid"])
            arms: dict = {}
            for arm, mu in (("base", run.base["mu"]),
                            ("T", _composite_mu(run, res["h_por_particion"])),
                            ("C", _composite_mu(run, res["h_por_particion"], base_shift=res["a_por_particion"]))):
                resid = (tot - mu)[m]
                arms[arm] = {"sesgo_mu_menos_T": float(-np.mean(resid)), "de_residuo": float(np.std(resid, ddof=1))}
            rep[name] = arms
        rep["sigma_vigente"] = spec.sigma if not spec.hockey else None
        return rep

    def inf3() -> dict:
        d = res["_w"]["d1"]
        seasons = np.array([bat.season_label(s, run.league) for s in run.dates])
        out3: dict = {}
        for s in sorted(set(seasons[tv])):
            m = tv & (seasons == s)
            mark = {"2019": "burbuja 2019-20", "2020": "calendario 2020-21"}.get(s) if run.league in ("nba", "nhl") else None
            out3[s] = {"n": int(m.sum()), "delta": float(np.mean(d[m])), "marca": mark}
        return out3

    def inf4() -> dict:
        return {hkey(h): float(np.mean((w["loss_h"][h] - loss_b)[tv])) for h in run.grid_hs}

    for key, fn in (("1", inf1), ("2", inf2), ("3", inf3), ("4", inf4)):
        out[key] = _safe_informe(f"{key}_{run.league}", fn)
    return out


def _composite_mu(run: LeagueRun, h_p: dict[str, float], base_shift: dict[str, float] | None = None
                  ) -> np.ndarray:
    """mu del brazo T (h_P por particion) o C (mu_base + a_P) en el test; base fuera."""
    mu = run.base["mu"].copy()
    for name, m in run.masks.items():
        te = m["test"]
        if base_shift is not None:
            mu[te] = run.base["mu"][te] + base_shift[name]
        else:
            mu[te] = run.grid[h_p[name]]["mu"][te]
    return mu


# ----------------------------------------------------------------- paridad --
def _engine_compare(label: str, mine: np.ndarray, eng: list[float], devs: dict[str, float]) -> None:
    eng_a = np.asarray(eng, float)
    if len(mine) != len(eng_a):
        raise SystemExit(f"Paridad 1 rota en {label}: {len(mine)} partidos frente a {len(eng_a)} del motor.")
    devs[label] = float(np.max(np.abs(mine - eng_a))) if len(eng_a) else 0.0


def script_fixed_line_probs(spec: LeagueSpec, walk: dict, outcomes: dict) -> dict[str, np.ndarray]:
    """Las P del script en las lineas fijas de la seccion 11.1, ya sin los empujes
    ni (h2h) los empates, en el orden en que las devuelve el motor."""
    lg = spec.league
    tl = PARITY_TOTAL_LINE[lg]
    total = outcomes["total"]
    out: dict[str, np.ndarray] = {}
    if spec.hockey:
        sp = PARITY_SPREADS[lg]
        mm = hockey_margin(walk["lam_h"], walk["lam_a"], sp, spec.max_goals)
        margin = outcomes["margin"]
        out["h2h"] = mm["home_win"][margin != 0]
        for s in sp:
            out[f"spreads@{float(s)}"] = mm[f"cover@{s}"][margin != -s]
    out[f"totals@{float(tl)}"] = over_prob(spec, walk, tl)[total != tl]
    return out


def parity_engine(run: LeagueRun, outcomes: dict, hs: tuple[float, ...]) -> dict:
    """Aserto 1 (seccion 11): para la base y para cada h, `walk_forward_backtest` con los
    parametros resueltos de la seccion 5 (con h) coincide con la P del script."""
    lg = run.league
    devs: dict[str, dict[str, float]] = {}
    arms: list[tuple[str, dict, dict]] = [("base", run.base, dict(bat.EXPECTED_ADAPTER_PARAMS[lg]))]
    for h in hs:
        pr = dict(bat.EXPECTED_ADAPTER_PARAMS[lg])
        pr[HALF_LIFE_KEY] = float(h)
        arms.append((hkey(h), run.grid[h], pr))
    # Enmienda 1(l): `params_h` del aserto 1 se pasa como los parametros RESUELTOS completos (seccion 5) con h;
    # se comprueba aparte que resuelven al mismo adaptador que `league_params U {h}` del candidato.
    for label, walk, params in arms:
        cand = run.league_params if label == "base" else candidate_params(run.league_params, float(label))
        if dict(get_adapter(lg, FAMILY[lg], params).params) != dict(get_adapter(lg, FAMILY[lg], cand).params):
            raise SystemExit(f"{lg}/{label}: los parametros resueltos de la seccion 5 no reproducen el candidato.")
        tl = PARITY_TOTAL_LINE[lg]
        ref = walk_forward_backtest(run.results, lg, FAMILY[lg], params, warmup=WARMUP,
                                    spread_lines=PARITY_SPREADS[lg], total_lines=(tl,))
        mine = script_fixed_line_probs(run.spec, walk, outcomes)
        d: dict[str, float] = {}
        if run.spec.hockey:
            _engine_compare("h2h", mine["h2h"], ref["binary_probs"], d)
        for key, arr in mine.items():
            if key != "h2h":
                _engine_compare(key, arr, ref["markets"][key]["probs"], d)
        bad = {k: v for k, v in d.items() if v > TOL}
        if bad:
            raise SystemExit(f"PARIDAD 1 ROTA ({lg}/{label}, > {TOL}): {bad}")
        devs[label] = d
    flat = [v for d in devs.values() for v in d.values()]
    return {"desviacion_max": max(flat) if flat else 0.0, "por_brazo": devs, "n": int(len(outcomes["total"])),
            "tolerancia": TOL}


def parity_mu(run: LeagueRun, outcomes: dict | None = None) -> dict:
    """Aserto 2 (seccion 11): la mu del script coincide con `adapter.estimate` de un
    adaptador de produccion construido con `get_adapter(..., league_params U {h})`,
    para la base y para h = 90. NHL: |lam_h + lam_a - (mu_scoring + bonus)| <= 1e-12."""
    lg, spec = run.league, run.spec
    line = l_base(run.base["mu"])
    devs: dict[str, dict[str, float]] = {}
    for label, lp, walk in (("base", run.league_params, run.base),
                            (hkey(H_PROBE), candidate_params(run.league_params, H_PROBE), run.grid[H_PROBE])):
        adapter = get_adapter(lg, FAMILY[lg], lp)
        ordered = sorted(run.results, key=lambda row: str(row.get("date", "")))
        d = {"over": 0.0, "mu": 0.0, "h2h": 0.0, "cover": 0.0, "identidad_nhl": 0.0, "lambda_avg_tilt": 0.0}
        if spec.hockey:
            mm = hockey_margin(walk["lam_h"], walk["lam_a"], (-1.5,), spec.max_goals)
            pt = hockey_pt(walk["lam_h"], walk["lam_a"], spec.max_goals)
            ov = hockey_over(pt, line)
            re_h, re_a = hockey_lambdas(walk["avg"], walk["tilt"], spec.bonus)
            d["lambda_avg_tilt"] = float(max(np.max(np.abs(re_h - walk["lam_h"])), np.max(np.abs(re_a - walk["lam_a"]))))
        else:
            ov = normal_over(walk["mu"], spec.sigma, line)
        pending: list[dict] = []
        k = 0
        for i, r in enumerate(ordered):
            rd = str(r.get("date", ""))[:10]
            if pending and rd != str(pending[0].get("date", ""))[:10]:
                for c in pending:
                    adapter.observe(c)
                pending.clear()
            if i >= WARMUP:
                ev = Event(event_id=str(i), sport_key="bt", league=lg, home=r["home"], away=r["away"],
                           start_time=str(r.get("date")), data_label=r.get("data_label", "real"))
                est = adapter.estimate(ev, -1.5 if spec.hockey else None, float(line[k]))
                d["over"] = max(d["over"], abs(est.over_estimated_probability - float(ov[k])))
                if spec.hockey:
                    d["h2h"] = max(d["h2h"], abs(est.home_win_estimated_probability - float(mm["home_win"][k])))
                    d["cover"] = max(d["cover"], abs(est.home_cover_estimated_probability - float(mm["cover@-1.5"][k])))
                    mu_sc = adapter.scoring.expected_total(ev.home, ev.away, adapter.params["avg_total"])
                    lam_h, lam_a = adapter._rates(ev)
                    d["identidad_nhl"] = max(d["identidad_nhl"], abs(lam_h + lam_a - (mu_sc + spec.bonus)))
                    d["mu"] = max(d["mu"], abs(lam_h + lam_a - float(walk["mu"][k])))
                else:
                    mu_prod = adapter.scoring.expected_total(ev.home, ev.away, adapter.params["avg_total"])
                    d["mu"] = max(d["mu"], abs(mu_prod - float(walk["mu"][k])))
                k += 1
            pending.append(r)
        bad = {key: v for key, v in d.items() if v > TOL}
        if bad:
            raise SystemExit(f"PARIDAD 2 ROTA ({lg}/{label}, > {TOL}): {bad}")
        devs[label] = d
    flat = [v for d in devs.values() for v in d.values()]
    return {"desviacion_max": max(flat), "por_brazo": devs, "n": int(len(line)), "tolerancia": TOL}


def parity_distribution(run: LeagueRun) -> dict:
    """Aserto 3 (solo NHL): suma de P(T = k) = 1 y P(Over L) de la rejilla del script
    igual a `poisson_match_probs(...)["over"]` en L en {4,5; 5,5; 6,5; 7,5}."""
    if not run.spec.hockey:
        return {"aplica": False}
    devs: dict[str, dict[str, float]] = {}
    for label, walk in (("base", run.base), (hkey(H_PROBE), run.grid[H_PROBE])):
        pt = hockey_pt(walk["lam_h"], walk["lam_a"], run.spec.max_goals)
        d = {"suma_pt": float(np.max(np.abs(pt.sum(axis=1) - 1.0)))}
        for ln in PARITY_NHL_OVER_LINES:
            mine = hockey_over(pt, ln)
            prod = np.asarray([dist.poisson_match_probs(float(a), float(b), None, ln, three_way=False,
                                                         max_goals=run.spec.max_goals)["over"]
                               for a, b in zip(walk["lam_h"], walk["lam_a"])])
            d[f"over@{ln}"] = float(np.max(np.abs(mine - prod)))
        bad = {k: v for k, v in d.items() if v > TOL}
        if bad:
            raise SystemExit(f"PARIDAD 3 ROTA ({run.league}/{label}, > {TOL}): {bad}")
        devs[label] = d
    flat = [v for d in devs.values() for v in d.values()]
    return {"aplica": True, "desviacion_max": max(flat), "por_brazo": devs, "n": int(len(run.base["mu"])),
            "tolerancia": TOL}


def run_parity(run: LeagueRun, outcomes: dict, hs: tuple[float, ...]) -> dict:
    return {"aserto1_motor": parity_engine(run, outcomes, hs), "aserto2_mu": parity_mu(run),
            "aserto3_distribucion": parity_distribution(run)}


def parity_only(data_root: Path, leagues: tuple[str, ...], hs: tuple[float, ...] = GRID) -> dict:
    """`--parity-only`: no estima nada. Lee los marcadores solo para excluir empujes y
    empates, como el motor; no calcula ninguna perdida."""
    assert_vigente_matches_params()
    out: dict = {"modo": "parity-only", "rejilla_comprobada": list(hs), "ligas": {}}
    for lg in leagues:
        t0 = time.perf_counter()
        run = LeagueRun(lg, data_root, grid=tuple(sorted(set(hs) | {H_PROBE})))
        out["ligas"][lg] = {"resultado": "PARIDAD OK",
                            **run_parity(run, read_outcomes(run.results), tuple(sorted(set(hs) & set(run.grid_hs)))),
                            "segundos": time.perf_counter() - t0}
    return out


# -------------------------------------------------------------- fase H (modo) --
def check_pre_tables(pre: dict, tables: dict, counts: dict) -> None:
    """La tabla 9.1 y los recuentos de `--fase H` deben ser los del `--pre`."""
    for lg in LEAGUES:
        a, b = pre.get("tabla_9_1", {}).get(lg), tables[lg]
        if not a or set(a) != set(b):
            raise SystemExit(f"{lg}: la tabla 9.1 del --pre no tiene las mismas filas. Se aborta.")
        for h in a:
            for k in ("media", "rms"):
                if abs(a[h][k] - b[h][k]) > TOL:
                    raise SystemExit(f"{lg}: la tabla 9.1 difiere del --pre en h = {h}, {k}. Se aborta.")
        if _clean(pre.get("recuentos", {}).get(lg)) != _clean({n: list(v) for n, v in counts[lg].items()}):
            raise SystemExit(f"{lg}: los recuentos por particion difieren del --pre. Se aborta.")


def run_H(data_root: Path, pre: dict | None, *, n_boot: int | None = None, leagues: tuple[str, ...] = LEAGUES,
          do_parity: bool = True) -> dict:
    assert_vigente_matches_params()
    battery = load_battery_pre(data_root)
    out: dict = {"procedencia": {"corte_datos": CUTOFF, "snapshot_root": str(data_root)},
                 "parametros_resueltos": resolved_report(LEAGUES), "rejilla": list(GRID),
                 "por_liga": {}, "paridad": {}, "informes": {"1": {}, "2": {}, "3": {}, "4": {}}}
    tables: dict = {}
    counts: dict = {}
    runs: dict[str, LeagueRun] = {}
    results: dict[str, dict] = {}
    for lg in leagues:
        run = LeagueRun(lg, data_root)
        runs[lg] = run
        out["procedencia"][lg] = run.proc
        tables[lg] = table_9_1(run.base, run.grid, run.masks["C"]["test"])
        counts[lg] = {n: (int(m["test"].sum()), int(len(np.unique(run.dates[m["test"]]))))
                      for n, m in run.masks.items()}
        check_against_battery(lg, {n: {"partidos": c[0], "dias": c[1]} for n, c in counts[lg].items()},
                              l_hash(l_base(run.base["mu"])), int(len(run.dates)), battery)
    if pre is not None:
        check_pre_tables(pre, {lg: tables[lg] for lg in leagues}, counts)
    out["tabla_9_1"] = tables
    outs = {lg: read_outcomes(runs[lg].results) for lg in leagues}
    if do_parity:      # Enmienda 1(k), F5: paridad de las tres ligas ANTES de calcular ninguna perdida
        for lg in leagues:
            out["paridad"][lg] = run_parity(runs[lg], outs[lg], runs[lg].grid_hs)
    for lg in leagues:
        run = runs[lg]
        outcomes = outs[lg]
        # Enmienda 1(k): el JSON de la fase H lleva `paridad`, asi que la fase H ejecuta las paridades 1-3 completas
        # (todos los h) antes de medir y aborta si fallan; es el tramo mas lento (motor de produccion por h).
        results[lg] = evaluate_league_H(run, outcomes, n_boot=n_boot)
        for key, val in informes_H(run, results[lg]).items():
            out["informes"][key][lg] = val
    hol = apply_holm({lg: results[lg] for lg in leagues}) if len(leagues) == K_HOLM else None
    for lg in leagues:
        r = results[lg]
        r["criterios"]["H6"] = bool(hol and lg in hol["rechazadas"])
        r["veredicto_H"] = "ACEPTA" if all(r["criterios"].values()) else "RECHAZA"
        out["por_liga"][lg] = r
    out["holm"] = hol
    return out


# ------------------------------------------------------------------ fase M --
def roi_key(r: dict) -> tuple:
    """Orden de `roi_engine.realized_roi_backtest` (reproducibilidad del emparejamiento)."""
    return (str(r.get("date", "")), str(r.get("home", "")), str(r.get("away", "")),
            str(r.get("game_id", "")), str(r.get("home_score", "")), str(r.get("away_score", "")))


class _AmbiguityCounter(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.n = 0

    def emit(self, record: logging.LogRecord) -> None:
        if "AMBIGUO" in record.getMessage():
            self.n += 1


@contextmanager
def count_ambiguous() -> Iterator[_AmbiguityCounter]:
    """Cuenta los emparejamientos omitidos por ambiguedad que `_match_result` anota en el log."""
    # Enmienda 1(h): `_match_result` devuelve None tanto sin candidato como ante ambiguedad; para informar
    # `n_ambiguos_omitidos` (seccion 14) se cuenta su aviso de log en vez de duplicar su logica interna.
    lg = logging.getLogger("sqp.roi_engine")
    h = _AmbiguityCounter()
    lg.addHandler(h)
    try:
        yield h
    finally:
        lg.removeHandler(h)


def load_h_json(path: Path, sha: str | None) -> dict:
    if sha is not None and sha256_of(path) != sha:
        raise SystemExit(f"{path} tiene SHA-256 {sha256_of(path)} != {sha} (el commiteado). Se aborta.")
    return json.loads(path.read_text(encoding="utf-8"))


def h_c_of(h_json: dict, league: str) -> float:
    try:
        h = float(h_json["por_liga"][league]["h_por_particion"]["C"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(f"H.json no trae h_por_particion.C de {league}: {exc}") from exc
    if h not in GRID:
        raise SystemExit(f"{league}: h_C = {h} no esta en la rejilla {GRID}. Se aborta.")
    return h


def script_total_probability(adapter, ev: Event, line: float, spec: LeagueSpec) -> float | None:
    """P(Over line) del script (formulas vectorizadas de arriba) para el estado actual
    del adaptador. None en lineas de cuarto: ahi solo vale la de produccion."""
    # Enmienda 1(i): las lineas de cuarto (x,25 / x,75) no tienen formula vectorizada propia (el contrato solo
    # cubre medio punto y enteras); en ellas se usa la P de produccion y no hay comparacion de paridad 4.
    if float(line * 4).is_integer() and not float(line * 2).is_integer():
        return None
    if spec.hockey:
        lh, la = adapter._rates(ev)
        return float(hockey_over(hockey_pt(np.array([lh]), np.array([la]), spec.max_goals), line)[0])
    mu = adapter.params["avg_total"]
    if adapter.params.get("scoring_totals", True):
        mu = adapter.scoring.expected_total(ev.home, ev.away, mu)
    return float(normal_over(np.array([mu]), spec.sigma, line)[0])


def m_matches(league: str, results: list[dict], odds: dict, lp: dict | None, *, start: str, h_c: float | None,
              estimate: bool) -> dict:
    """Bucle de `roi_engine.realized_roi_backtest` restringido a los totales. Con
    `estimate=False` (conteo previo) NO lee marcadores ni estima nada: solo empareja."""
    fam = FAMILY[league]
    spec = LeagueSpec(league, dict(get_adapter(league, fam, lp).params)) if estimate else None
    norm = get_team_normalizer(league)
    idx = _match_index(odds, False, norm)
    used: set[str] = set()
    ordered = sorted(results, key=roi_key)
    ad_b = get_adapter(league, fam, lp) if estimate else None
    ad_t = get_adapter(league, fam, candidate_params(lp, h_c)) if estimate and h_c is not None else None
    pending: list[dict] = []
    recs: list[dict] = []
    cnt = {"sin_emparejar": 0, "sin_linea_totales": 0, "sin_novig": 0}
    with count_ambiguous() as amb:
        for i, r in enumerate(ordered):
            rd = str(r.get("date", ""))[:10]
            if estimate and pending and rd != str(pending[0].get("date", ""))[:10]:
                for c in pending:
                    ad_b.observe(c)
                    ad_t.observe(c)
                pending.clear()
            if i >= WARMUP and rd >= start:
                eo = _match_result(r, idx, used, False, norm)
                if eo is None:
                    cnt["sin_emparejar"] += 1
                else:
                    spread, total = _pick_main_lines(eo)
                    fair = _novig_probs(_consensus_lines(eo), "totals", total).get("Over") if total is not None else None
                    if total is None:
                        cnt["sin_linea_totales"] += 1
                    elif fair is None:
                        cnt["sin_novig"] += 1
                    else:
                        rec: dict = {"date": rd, "mes": rd[:7], "event_id": eo.event.event_id, "L": float(total),
                                     "spread": spread, "p_fair": float(fair)}
                        if estimate:
                            rec.update(_m_estimate(r, eo, spread, total, ad_b, ad_t, spec, norm))
                        recs.append(rec)
            if estimate:
                pending.append(r)
        n_amb = amb.n
    cnt["n_ambiguos_omitidos"] = n_amb
    return {"recs": recs, "conteo": cnt}


def _m_estimate(r: dict, eo, spread, total, ad_b, ad_t, spec: LeagueSpec, norm: Callable) -> dict:
    """Probabilidades y desenlace de un emparejado (solo `estimate=True`)."""
    ev = Event(event_id=eo.event.event_id, sport_key="bt", league=spec.league, home=eo.event.home,
               away=eo.event.away, start_time=eo.event.start_time, data_label="real")
    same = norm(r["home"]) == norm(eo.event.home)
    hs, as_ = ((float(r["home_score"]), float(r["away_score"])) if same
               else (float(r["away_score"]), float(r["home_score"])))
    rec: dict = {"total_real": hs + as_, "hs": hs, "as": as_}
    for arm, ad in (("b", ad_b), ("t", ad_t)):
        est = ad.estimate(ev, spread, total)
        prod = build_model_map(est, ev, spread, total).get(("totals", "Over", total))
        mine = script_total_probability(ad, ev, total, spec)
        rec[f"p_{arm}"] = prod
        rec[f"dev_{arm}"] = 0.0 if mine is None else abs(prod - mine)
        rec["cuarto"] = mine is None
        rec[f"h2h_{arm}"] = est.home_win_estimated_probability
        rec[f"cov_{arm}"] = est.home_cover_estimated_probability
    return rec


def month_table(recs: list[dict]) -> dict[str, int]:
    cnt: dict[str, int] = defaultdict(int)
    for rec in recs:
        cnt[rec["mes"]] += 1
    return dict(sorted(cnt.items()))


def decide_m_league(n: int, cutoff: str, league: str, veredicto_h: str | None = "ACEPTA") -> str:
    # Enmienda 1(f): la unica prorroga (seccion 8.2) se modela con --m-cutoff en {D, D'}; el script no puede
    # comprobar que D' no se haya usado ya ni la ventana de "7 dias siguientes": es disciplina operativa.
    """Seccion 8.2: medir si n >= minimo; si no, unica prorroga a D'; si ya es D', NO CONCLUYENTE."""
    if n >= M_MIN_N[league]:
        return "medir"
    if veredicto_h != "ACEPTA":      # Enmienda 1(f).3: H RECHAZA no tiene prorroga
        return "no_medida_descriptivo"
    return "prorroga" if cutoff == M_CUTOFF else "no_concluyente"


def load_prev_pre_m(path: Path | None, cutoff: str, h_sha: str) -> dict | None:
    """Enmienda 1(f).2 (F1): en D' se exige el `pre_M` de D, de la misma H.json."""
    if cutoff != M_CUTOFF_EXT:
        if path is not None:
            raise SystemExit("--prev-pre-m solo aplica con --m-cutoff 2027-04-20.")
        return None
    if path is None:
        raise SystemExit("--prev-pre-m (el pre_M de D) es obligatorio con --m-cutoff 2027-04-20.")
    prev = json.loads(Path(path).read_text(encoding="utf-8"))
    if prev.get("corte_fase_M") != M_CUTOFF or prev.get("h_json_sha256") != h_sha:
        raise SystemExit("--prev-pre-m no es el pre_M de D (2027-01-31) de este mismo H.json. Se aborta.")
    return prev


def informe_pre_M(data_root: Path, h_json_path: Path, h_sha: str, cutoff: str,
                  prev_pre_m: dict | None = None, prev_pre_m_path: Path | None = None) -> dict:
    """`--fase M --pre`: cuenta emparejados con linea y no-vig por liga y mes. No lee
    marcadores (salvo el emparejamiento por fecha y equipos) y no estima nada."""
    status = git_status_porcelain(_WORKTREE_ROOT)
    check_git_clean(status, "todo el repositorio")
    # Enmienda 1(e): "verifica el SHA-256 de H.json (commiteado)": el script no sabe donde esta la copia
    # commiteada, asi que el operador pasa su hash con --h-sha256 y el script lo contrasta con el fichero.
    h_json = load_h_json(h_json_path, h_sha)
    assert_vigente_matches_params()
    params = resolved_report(LEAGUES)
    if _clean(h_json.get("parametros_resueltos")) != _clean(params):
        raise SystemExit("Los parametros resueltos de H.json difieren de los actuales (base cambiada). Se aborta.")
    if h_json.get("codigo_sha256") != code_hashes():       # Enmienda 1(e), F4
        raise SystemExit("El codigo (measure_totals_recency.py / measure_adjustment_battery.py) difiere del de "
                         "H.json. Solo una enmienda previa a mirar la fase M puede justificarlo. Se aborta.")
    if cutoff == M_CUTOFF_EXT and prev_pre_m is None:
        raise SystemExit("En D' hace falta el pre_M de D (prev_pre_m).")
    out: dict = {"git_head": git_head(_WORKTREE_ROOT), "git_status_porcelain": status,
                 "snapshot_root": str(data_root), "corte_fase_M": cutoff, "mercado_desde": MARKET_START,
                 "h_json_sha256": sha256_of(h_json_path), "manifiesto": manifest(data_root, odds=True),
                 "config_sha256": bat.config_hashes(), "parametros_resueltos": params,
                 "codigo_sha256": code_hashes(),
                 "prev_pre_m_sha256": None if prev_pre_m_path is None else sha256_of(Path(prev_pre_m_path)),
                 "h_C": {lg: h_c_of(h_json, lg) for lg in LEAGUES}, "minimos": M_MIN_N, "ligas": {}}
    for lg in LEAGUES:
        if prev_pre_m is not None and prev_pre_m["ligas"][lg]["decision"] != "prorroga":
            out["ligas"][lg] = {"decision": "ya_medida_en_D", "decision_en_D": prev_pre_m["ligas"][lg]["decision"]}
            continue
        rows, lp, proc = load_league_cut(lg, data_root, cutoff)
        odds = {k: v for k, v in load_closing_odds(data_root, lg).items()
                if str(v.event.start_time)[:10] <= cutoff}
        m = m_matches(lg, rows, odds, lp, start=MARKET_START, h_c=None, estimate=False)
        n = len(m["recs"])
        out["ligas"][lg] = {"procedencia": proc, "n_emparejados_con_linea_y_novig": n, "minimo": M_MIN_N[lg],
                            "por_mes": month_table(m["recs"]), "conteo": m["conteo"],
                            "decision": decide_m_league(n, cutoff, lg, h_json["por_liga"][lg].get("veredicto_H"))}
    return out


def _delta_boot(dates: np.ndarray, series: dict[str, tuple[np.ndarray, np.ndarray]], n_boot: int | None) -> dict:
    b = bootstrap_dias(dates, series, **({} if n_boot is None else {"n_boot": n_boot}))
    return {k: {"IC95": v["ic95"], "EE": v["se"], "n_replicas": v["n_replicas"], "n_dias": v["n_dias"]}
            for k, v in b.items()}


def measure_m_league(league: str, rows: list[dict], odds: dict, lp: dict | None, h_c: float, ids90: set[str],
                     *, n_boot: int | None = None, expect: dict | None = None) -> dict:
    """Seccion 8 para una liga: Delta_M, M3 (NHL), paridad 4 e informes 5 y 6.
    `expect` = entrada de la liga en el `--fase M --pre`: n y conteo por mes deben ser identicos."""
    m = m_matches(league, rows, odds, lp, start=MARKET_START, h_c=h_c, estimate=True)
    recs = m["recs"]
    n = len(recs)
    if expect is not None:     # Enmienda 1(g), correccion F3
        if n != expect["n_emparejados_con_linea_y_novig"] or month_table(recs) != expect["por_mes"]:
            raise SystemExit(f"{league}: n/conteo por mes de la fase M ({n}, {month_table(recs)}) difieren del "
                             f"--pre de la fase M ({expect['n_emparejados_con_linea_y_novig']}, {expect['por_mes']}). "
                             "Se aborta.")
    # Enmienda 1(g): `n` (M1) = emparejados con linea y no-vig ANTES de excluir empujes (seccion 8.2); el
    # bootstrap remuestrea los dias de esa muestra completa y los empujes entran con peso 0.
    if n == 0:
        raise SystemExit(f"{league}: ningun emparejado con linea y no-vig.")
    # aserto 4: P del script = P de build_model_map; linea = punto mas cotizado; no-vig sano
    dev = max(max(r["dev_b"], r["dev_t"]) for r in recs)
    if dev > TOL:
        raise SystemExit(f"PARIDAD 4 ROTA ({league}): P(Over L_m) del script difiere de build_model_map en {dev:.3e}.")
    dates = np.asarray([r["date"] for r in recs], dtype=str)
    total = np.asarray([r["total_real"] for r in recs])
    L = np.asarray([r["L"] for r in recs])
    push = total == L
    ok = ~push
    y = (total > L).astype(float)
    pb, pt_, pf = (np.asarray([r[k] for r in recs]) for k in ("p_b", "p_t", "p_fair"))
    d = np.where(ok, ll_vec(pt_, y) - ll_vec(pb, y), 0.0)
    delta_m = float(np.mean(d[ok]))
    series: dict[str, tuple[np.ndarray, np.ndarray]] = {"delta_M": (d, ok.astype(float))}
    res: dict = {"n": n, "n_empujes": int(push.sum()), "n_evaluados": int(ok.sum()),
                 "n_ambiguos_omitidos": m["conteo"]["n_ambiguos_omitidos"], "conteo": m["conteo"],
                 "h_C": h_c, "delta_M": delta_m, "por_mes": month_table(recs),
                 "n_lineas_cuarto_sin_paridad4": int(sum(1 for r in recs if r.get("cuarto"))), "paridad_M": {"desviacion_max": dev, "n": n, "tolerancia": TOL}}
    delta_m3 = None
    if FAMILY[league] == "hockey":
        hs, as_ = np.asarray([r["hs"] for r in recs]), np.asarray([r["as"] for r in recs])
        v3 = hs != as_
        y3 = (hs > as_).astype(float)
        hb, ht = np.asarray([r["h2h_b"] for r in recs]), np.asarray([r["h2h_t"] for r in recs])
        d3 = np.where(v3, ll_vec(ht, y3) - ll_vec(hb, y3), 0.0)
        series["delta_M3"] = (d3, v3.astype(float))
        delta_m3 = float(np.mean(d3[v3]))
    boot = _delta_boot(dates, series, n_boot)
    res.update(IC95=boot["delta_M"]["IC95"], EE=boot["delta_M"]["EE"], delta_M3=delta_m3, bootstrap=boot)
    crit = {"M1": n >= M_MIN_N[league], "M2": delta_m <= 0, "M3": True if delta_m3 is None else delta_m3 <= 0}
    res["criterios"] = crit
    res["veredicto_M"] = "NO CONCLUYENTE" if not crit["M1"] else ("NO VETA" if crit["M2"] and crit["M3"] else "VETA")
    res["informes"] = {"5": _safe_informe(f"5_{league}", lambda: _informe5(recs, y, ok, pb, pt_, pf)),
                       "6": _safe_informe(f"6_{league}", lambda: _informe6(league, recs, y, ok, ids90, d))}
    return res


def _informe5(recs: list[dict], y: np.ndarray, ok: np.ndarray, pb: np.ndarray, pt_: np.ndarray, pf: np.ndarray) -> dict:
    """Seccion 13.5: referencia de mercado (no-vig) en la misma muestra."""
    ll_f, ll_b, ll_t = (float(np.mean(ll_vec(p, y)[ok])) for p in (pf, pb, pt_))
    blend_b, blend_t = 0.5 * pb + 0.5 * pf, 0.5 * pt_ + 0.5 * pf
    return {"log_loss_novig": ll_f, "log_loss_base": ll_b, "log_loss_T": ll_t,
            "brecha_base_menos_novig": ll_b - ll_f, "brecha_T_menos_novig": ll_t - ll_f,
            "rms_p_menos_pfair_base": float(np.sqrt(np.mean(((pb - pf) ** 2)[ok]))),
            "rms_p_menos_pfair_T": float(np.sqrt(np.mean(((pt_ - pf) ** 2)[ok]))),
            "delta_mezcla_0_5": float(np.mean((ll_vec(blend_t, y) - ll_vec(blend_b, y))[ok])),
            "nota": "referencia de semantica; NO es ventaja sobre el mercado."}


def _informe6(league: str, recs: list[dict], y: np.ndarray, ok: np.ndarray, ids90: set[str], d: np.ndarray) -> dict:
    """Seccion 13.6: submuestra CLOSE_MAX_AGE_MIN, por mes, regular/playoffs, spreads NHL."""
    in90 = np.asarray([r["event_id"] in ids90 for r in recs])
    months = np.asarray([r["mes"] for r in recs])
    out: dict = {"close_max_age_min": CLOSE_MAX_AGE_MIN,
                 "submuestra_cierre": {"n": int((ok & in90).sum()),
                                       "delta_M": float(np.mean(d[ok & in90])) if (ok & in90).any() else None},
                 "por_mes": {mm: {"n": int((ok & (months == mm)).sum()), "delta_M": float(np.mean(d[ok & (months == mm)]))}
                             for mm in sorted(set(months)) if (ok & (months == mm)).any()},
                 }
    if FAMILY[league] == "hockey":
        sp = np.asarray([np.nan if r["spread"] is None else r["spread"] for r in recs], float)
        hs, as_ = np.asarray([r["hs"] for r in recs]), np.asarray([r["as"] for r in recs])
        v = np.isfinite(sp) & ((hs - as_) != -sp)
        ys = ((hs - as_) > -sp).astype(float)
        cb, ct = np.asarray([r["cov_b"] for r in recs], float), np.asarray([r["cov_t"] for r in recs], float)
        v &= np.isfinite(cb) & np.isfinite(ct)
        out["spreads_linea_capturada"] = {
            "n": int(v.sum()),
            "delta": float(np.mean((ll_vec(ct, ys) - ll_vec(cb, ys))[v])) if v.any() else None}
    return out


def run_M(data_root: Path, h_json: dict, pre_m: dict, *, n_boot: int | None = None) -> dict:
    # Enmienda 1(f).3: segun 16.1 la fase M tambien se ejecuta en las ligas cuya fase H RECHAZA; se marca
    # `valor: descriptivo` (y `decisorio` solo si H ACEPTA). Las ligas "prorroga"/"no_concluyente" no se miden.
    cutoff = pre_m["corte_fase_M"]
    out: dict = {"procedencia": {"corte_fase_M": cutoff, "snapshot_root": str(data_root),
                                 "h_json_sha256": pre_m["h_json_sha256"], "mercado_desde": MARKET_START},
                 "h_C": {lg: h_c_of(h_json, lg) for lg in LEAGUES}, "por_liga": {}, "paridad_M": {}, "informes": {"5": {}, "6": {}}}
    for lg in LEAGUES:
        dec = pre_m["ligas"][lg]["decision"]
        if dec != "medir":
            names = {"no_concluyente": "NO CONCLUYENTE", "prorroga": "PRORROGA", "ya_medida_en_D": "YA MEDIDA EN D",
                     "no_medida_descriptivo": "NO MEDIDA (DESCRIPTIVO)"}
            out["por_liga"][lg] = {"veredicto_M": names.get(dec, dec.upper()),
                                   "motivo": f"decision del --pre de la fase M: {dec}",
                                   "n": pre_m["ligas"][lg].get("n_emparejados_con_linea_y_novig")}
            continue
        rows, lp, proc = load_league_cut(lg, data_root, cutoff)
        out["procedencia"][lg] = proc
        odds = {k: v for k, v in load_closing_odds(data_root, lg).items() if str(v.event.start_time)[:10] <= cutoff}
        # Enmienda 1(j): la submuestra CLOSE_MAX_AGE_MIN (informe 6) se define por pertenencia del evento ya
        # emparejado al conjunto que devuelve `load_closing_odds(max_age_min=90)`, sin reemparejar.
        ids90 = set(load_closing_odds(data_root, lg, max_age_min=CLOSE_MAX_AGE_MIN))
        res = measure_m_league(lg, rows, odds, lp, out["h_C"][lg], ids90, n_boot=n_boot, expect=pre_m["ligas"][lg])
        res["h_veredicto"] = h_json["por_liga"][lg].get("veredicto_H")
        res["valor"] = "decisorio" if res["h_veredicto"] == "ACEPTA" else "descriptivo"
        out["paridad_M"][lg] = res.pop("paridad_M")
        for k, v in res.pop("informes").items():
            out["informes"][k][lg] = v
        out["por_liga"][lg] = res
    return out


# -------------------------------------------------------------------- main --
def _parse_leagues(text: str | None, ap: argparse.ArgumentParser) -> tuple[str, ...]:
    if not text:
        return LEAGUES
    lgs = tuple(s.strip() for s in text.split(",") if s.strip())
    bad = [lg for lg in lgs if lg not in LEAGUES]
    if bad:
        ap.error(f"--leagues: {bad} no son ligas del alcance {LEAGUES}.")
    return lgs


def _check_data_root(ap: argparse.ArgumentParser, data_root: Path | None, parity: bool) -> Path:
    # Enmienda 1(m): --data-root es obligatorio tambien en --parity-only (la bateria permitia el arbol vivo ahi);
    # solo los modos que miden rechazan el arbol vivo y data/.
    if data_root is None:
        ap.error("--data-root es obligatorio y explicito en todos los modos (instantanea).")
    dr = Path(data_root).resolve()
    if not parity:
        if dr == DEFAULT_ROOT.resolve():
            raise SystemExit("--data-root apunta al arbol vivo (sqp.config.ROOT): se mide SOLO sobre la "
                             "instantanea. Se aborta.")
        if dr.is_relative_to((DEFAULT_ROOT / "data").resolve()):
            raise SystemExit("--data-root esta dentro de data/ (ignorado por git): la instantanea debe quedar "
                             "fuera de data/. Se aborta.")
    return Path(data_root)


def _write(out: dict, path: Path | None) -> None:
    if path is not None:
        path.write_text(json.dumps(_clean(out), indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pre", action="store_true")
    ap.add_argument("--parity-only", action="store_true")
    ap.add_argument("--fase", choices=("H", "M"))
    ap.add_argument("--data-root", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--pre-json", type=Path)
    ap.add_argument("--h-json", type=Path)
    ap.add_argument("--h-sha256", help="SHA-256 de H.json commiteado (solo --fase M --pre).")
    ap.add_argument("--prev-pre-m", type=Path, help="pre_M de D (obligatorio con --m-cutoff 2027-04-20).")
    ap.add_argument("--m-cutoff", choices=(M_CUTOFF, M_CUTOFF_EXT), default=M_CUTOFF)
    ap.add_argument("--leagues", help="Solo --parity-only.")
    ap.add_argument("--h-subset", help="Solo --parity-only: valores de la rejilla a comprobar (p. ej. 0,90).")
    args = ap.parse_args(argv)

    if args.parity_only:
        if args.pre or args.fase:
            ap.error("--parity-only es excluyente con --pre y --fase.")
    elif args.leagues or args.h_subset:
        ap.error("--leagues/--h-subset solo aplican a --parity-only.")
    if not args.parity_only and not args.pre and not args.fase:
        ap.error("indica un modo: --pre, --parity-only, --fase H o --fase M.")
    if args.fase == "H" and args.h_json:
        ap.error("--h-json solo aplica a la fase M.")
    mode = ("parity" if args.parity_only else
            "pre_M" if args.pre and args.fase == "M" else
            "pre_H" if args.pre else "M" if args.fase == "M" else "H")
    data_root = _check_data_root(ap, args.data_root, mode == "parity")
    if mode != "parity" and args.out is None:
        ap.error("--out es obligatorio salvo en --parity-only.")
    if mode in ("H", "M") and args.pre_json is None:
        ap.error("--pre-json es obligatorio en la fase completa: ejecuta antes --pre.")
    if mode in ("pre_M", "M") and args.h_json is None:
        ap.error("--h-json es obligatorio en la fase M.")
    if mode == "pre_M" and not args.h_sha256:
        ap.error("--h-sha256 (hash del H.json commiteado) es obligatorio en --fase M --pre.")
    if args.pre_json and mode in ("pre_H", "pre_M", "parity"):
        ap.error("--pre-json solo aplica a las fases completas.")

    if mode != "parity" and args.out.exists():      # Enmienda 1(n), F2
        raise SystemExit(f"{args.out} ya existe: las salidas no se sobrescriben (una repeticion E10 usa un fichero nuevo).")
    if args.prev_pre_m and mode != "pre_M":
        ap.error("--prev-pre-m solo aplica a --fase M --pre.")
    t0 = time.perf_counter()
    if mode == "parity":
        hs = tuple(float(s) for s in args.h_subset.split(",")) if args.h_subset else GRID
        bad = [h for h in hs if h not in GRID]
        if bad:
            ap.error(f"--h-subset: {bad} no estan en la rejilla {GRID}.")
        out = parity_only(data_root, _parse_leagues(args.leagues, ap), hs)
        out["segundos"] = time.perf_counter() - t0
        print(json.dumps(_clean(out), indent=2, ensure_ascii=False))
        _write(out, args.out)
        return 0
    if mode == "pre_H":
        out = {"modo": "pre H (sin desenlaces)", **informe_pre_H(data_root)}
    elif mode == "pre_M":
        prev = load_prev_pre_m(args.prev_pre_m, args.m_cutoff, args.h_sha256)
        out = {"modo": "pre M (sin desenlaces)",
               **informe_pre_M(data_root, args.h_json, args.h_sha256, args.m_cutoff, prev, args.prev_pre_m)}
    else:
        porcelain = git_status_porcelain(_WORKTREE_ROOT, FULL_GIT_PATHS)
        check_git_clean(porcelain, "src configs scripts/research")
        pre = json.loads(args.pre_json.read_text(encoding="utf-8"))
        man = manifest(data_root, odds=(mode == "M"))
        cfg, params = bat.config_hashes(), resolved_report(LEAGUES)
        check_provenance(pre, git_head(_WORKTREE_ROOT), man, cfg, params, "--pre-json")
        head = {"git_head": git_head(_WORKTREE_ROOT), "git_status_porcelain_src_configs_scripts_research": porcelain,
                "pre_json_sha256": sha256_of(args.pre_json), "parametros_resueltos": params, "manifiesto": man,
                "codigo_sha256": code_hashes(), "config_sha256": cfg}
        if mode == "H":
            out = {"modo": "fase H", **head, **run_H(data_root, pre)}
        else:
            h_json = load_h_json(args.h_json, pre.get("h_json_sha256"))
            out = {"modo": "fase M", **head, **run_M(data_root, h_json, pre)}
    out["segundos"] = time.perf_counter() - t0
    _write(out, args.out)
    print(json.dumps({"escrito": str(args.out), "modo": out["modo"], "git_head": out.get("git_head")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
