"""Medicion del pre-registro del descanso/back-to-back en NHL (2026-09-27).

Ver `docs/research/2026-09-27-preregistro-descanso-nhl.md`. Solo la NHL: el
mecanismo (`RestModel` dentro de `PoissonAdapter`, clave `rest_elo_per_day`)
tambien lo heredan `BaseballAdapter`/`SoccerAdapter`, pero este pre-registro
mide unicamente hockey (seccion 4). Tres modos:

  --pre            recuentos de dias de descanso SIN marcadores (seccion 9):
                    NUNCA lee home_score/away_score, solo date/home/away/
                    game_id via RestModel. Registra SHA-256 y filas del
                    fichero de results_nhl.csv leido.
  --parity-only    construye el brazo base (c=0) y comprueba la paridad con
                    el motor canonico `sqp.backtesting.engine.
                    walk_forward_backtest` a 1e-12 (moneyline, puck line
                    +-1,5 y totales 5,5/6,5). Repite la comprobacion con un
                    `c` de prueba arbitrario (PROBE_C, seccion 5, aserciones
                    1 y 2) para el mecanismo `rest_elo_per_day`. NO estima
                    ninguna `c`, no calcula ningun Delta y no evalua ningun
                    criterio de aceptacion.
  (sin flags)      medicion completa, UNA SOLA EJECUCION (seccion 14): ajusta
                    `c` (brazo T), `a` (brazo C) y (a_conj, c_conj) por
                    particion, evalua los 7 criterios de la seccion 7, el
                    bootstrap de la seccion 8 y los informes secundarios de
                    la seccion 10, y escribe el JSON de salida.
                    `--pre-json <salida-de---pre>` es OBLIGATORIO en este
                    modo: aborta si falta, o si a `--pre-json` o al fichero
                    de resultados leido ahora le falta el SHA-256, o si
                    difieren entre si.

  python scripts/research/measure_rest_nhl.py --parity-only
  python scripts/research/measure_rest_nhl.py --pre --out <json>
  python scripts/research/measure_rest_nhl.py --out <json> --pre-json <pre.json>

Reutiliza codigo de produccion (RestModel, SportAdapter/get_adapter,
EloRatings.rating_diff, TeamScoringRates.expected_total, _league_meta) en vez
de reimplementar formulas: el "brazo base" reproduce literalmente las dos
lineas de `PoissonAdapter._rates` (rating_diff -> logistica -> tilt acotado
-> lambdas), y el diferencial de descanso Delta_r se obtiene con una segunda
instancia de `RestModel` sondeada con `points_per_day=1.0` y
`margin_adjustment` (misma tecnica que `measure_rest_basketball.py`, enmienda
E4 de la revision independiente de basket), nunca con el min/max
reimplementado a mano.

La rejilla de Poisson SI esta vectorizada (numpy + scipy.stats.poisson) en
vez de llamar a `dist.poisson_match_probs` partido a partido -- lo permite la
configuracion de produccion de la NHL (`dc_rho=0`, `dispersion_k=None`,
`score_rho=0`: independencia pura, ver `_joint_grid`/`poisson_match_probs`),
y las aserciones de paridad de la seccion 5 son justamente la red de
seguridad que la propia seccion 5 anticipa para este caso.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date as _date
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson as _poisson

from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.roi_engine import _match_index, _match_result, load_closing_odds
from sqp.backtesting.tuning import IMPROVEMENT_MARGIN
from sqp.calibration.metrics import expected_calibration_error
from sqp.config import ROOT
from sqp.models import distributions as dist
from sqp.models.rest import RestModel
from sqp.pipeline.daily import _league_meta
from sqp.pipeline.probabilities import _pick_main_lines
from sqp.sports.registry import get_adapter
from sqp.sports.team_names import get_team_normalizer
from sqp.storage.results_store import ResultsStore

LEAGUE = "nhl"
FAMILY = "hockey"
WARMUP = 60  # default de walk_forward_backtest (seccion 5 y 9)
NM_OPTS = {"xatol": 1e-7, "fatol": 1e-10, "maxiter": 2000}  # seccion 6
N_BOOT, SEED = 10_000, 42  # seccion 8
PROBE_C = 25.0  # solo para la prueba de paridad de --parity-only (seccion 5); puntos Elo/dia
SPREAD_LINES = (-1.5, 1.5)   # puck line que cotiza el mercado (seccion 5)
TOTAL_LINES = (5.5, 6.5)     # solo paridad/informes, alrededor de avg_total 6.1 (seccion 7)

FOLDS = {
    "A": {"train_end": "2014-09-30", "test_start": "2014-10-01", "test_end": "2018-09-30"},
    "B": {"train_end": "2018-09-30", "test_start": "2018-10-01", "test_end": "2022-09-30"},
    "C": {"train_end": "2022-09-30", "test_start": "2022-10-01", "test_end": "2026-06-30"},
}


# ------------------------------------------------------------------ datos --
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_league() -> tuple[list[dict], dict, dict]:
    """Resultados, `league_params` resueltos (seccion 5: `_league_meta`) y
    procedencia (hash/filas) del fichero leido. Aborta si el mecanismo ya
    NO esta apagado en la configuracion base, o si hay un `goalie_beta` != 0
    sin que una enmienda de este documento lo autorice (seccion 5)."""
    results = ResultsStore(ROOT).load(LEAGUE)
    params = dict(_league_meta(LEAGUE).get("league_params") or {})
    if params.get("rest_elo_per_day", 0.0) != 0.0:
        raise ValueError(
            "nhl: rest_elo_per_day ya no es 0.0 en configs/leagues/ratings.yaml -- "
            "el pre-registro asume el mecanismo APAGADO en la configuracion base. "
            "No decido reinterpretar la base: abortando.")
    if params.get("goalie_beta", 0.0) != 0.0:
        raise ValueError(
            "nhl: goalie_beta != 0.0 en configs/leagues/ratings.yaml y este "
            "documento no trae una enmienda que lo autorice (seccion 11). "
            "No decido reinterpretar la base: abortando.")
    path = ResultsStore(ROOT).path(LEAGUE)
    procedencia = {"fichero": str(path), "filas": len(results)}
    if path.exists():
        procedencia["sha256"] = sha256_of(path)
    return results, params, procedencia


def resolved_params(league_params: dict) -> dict:
    """Parametros de liga tal como los ve el adaptador (FAMILY_PARAMS ->
    LEAGUE_OVERRIDES -> league_params), sin reimplementar `get_adapter`."""
    return get_adapter(LEAGUE, FAMILY, league_params).params


# --------------------------------------------------------- calendario Delta_r --
def rest_calendar(results: list[dict], params: dict, warmup: int = WARMUP,
                  probe: RestModel | None = None) -> pd.DataFrame:
    """Dias de descanso por partido, en el orden y warmup del motor
    (`engine.walk_forward_backtest`), SIN tocar marcadores: solo
    date/home/away/game_id. Reutiliza `RestModel` (sondeada con
    points_per_day=1.0 y margin_adjustment, equivalente a la definicion de la
    seccion 3 -- enmienda E4 de basket) y el normalizador de equipos de
    produccion; no reimplementa la regla `min(max(D-L,0), rest_max_days)`.

    `probe` es inyectable para reutilizar este mismo recorrido temporal con
    otra instancia de `RestModel` (p.ej. sin tope, seccion 9 de `--pre`); por
    defecto construye la sonda de produccion con el tope de la liga.
    """
    normalize = get_team_normalizer(LEAGUE)
    if probe is None:
        max_rest = int(params.get("rest_max_days", 4))
        probe = RestModel(points_per_day=1.0, max_rest=max_rest, normalize=normalize)
    ordered = sorted(results, key=lambda row: str(row.get("date", "")))
    rows: list[dict] = []
    pending: list[dict] = []
    for i, r in enumerate(ordered):
        date = str(r.get("date", ""))
        if pending and date[:10] != str(pending[0].get("date", ""))[:10]:
            for done in pending:
                probe.observe(done["home"], done["away"], done.get("date"))
            pending.clear()
        if i >= warmup:
            hr = probe.rest_days(r["home"], date)
            ar = probe.rest_days(r["away"], date)
            delta_eff = probe.margin_adjustment(r["home"], r["away"], date)
            known = hr is not None and ar is not None
            rows.append({
                "idx": i, "game_id": str(r.get("game_id", "")), "date": date[:10],
                "home": r["home"], "away": r["away"],
                "hr": hr, "ar": ar, "known": known,
                "delta_r": float(hr - ar) if known else float("nan"),
                "delta_eff": float(delta_eff),
                "neutral": bool(r.get("neutral", False)),
            })
        pending.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------- diff_base (brazo base) --
def diff_base_frame(results: list[dict], params: dict,
                    warmup: int = WARMUP) -> pd.DataFrame:
    """`rating_diff` y `avg` (escala) SIN el termino de descanso, en el orden
    del motor. Reutiliza el `adapter` de produccion completo para las
    actualizaciones (`adapter.observe`), y para el punto de estimacion llama
    literalmente `adapter.elo.rating_diff` + `adapter.scoring.expected_total`:
    las mismas dos lineas que ejecuta `PoissonAdapter._rates` ANTES de sumar
    `self.rest.margin_adjustment` (seccion 5: "El ajuste no realimenta el Elo
    ni las tasas", por eso diff_base/avg se calculan una unica vez y cada
    brazo es funcion analitica de (diff_base, avg, Delta_r)).
    """
    adapter = get_adapter(LEAGUE, FAMILY, params)
    # `adapter.params` (FAMILY_PARAMS -> LEAGUE_OVERRIDES -> league_params),
    # NOT the raw `params` argument (which is just `_league_meta`'s
    # `league_params`, e.g. only `{"elo_home_adv": 15.0}` for the NHL):
    # `avg_total`/`scoring_totals` live in the resolved dict, same one
    # `PoissonAdapter._rates` reads from `self.params`.
    scoring_on = adapter.params.get("scoring_totals", True)
    ordered = sorted(results, key=lambda row: str(row.get("date", "")))
    rows: list[dict] = []
    pending: list[dict] = []
    for i, r in enumerate(ordered):
        date = str(r.get("date", ""))
        if pending and date[:10] != str(pending[0].get("date", ""))[:10]:
            for done in pending:
                adapter.observe(done)
            pending.clear()
        if i >= warmup:
            diff = adapter.elo.rating_diff(r["home"], r["away"])
            avg = adapter.params["avg_total"]
            if scoring_on:
                avg = adapter.scoring.expected_total(r["home"], r["away"], avg)
            hs, aws = float(r["home_score"]), float(r["away_score"])
            y = 1.0 if hs > aws else (0.5 if hs == aws else 0.0)
            # `margin`/`total` van alineados POR POSICION (idx), no por
            # game_id: el esquema legacy de ResultsStore permite
            # `game_id == ""` en varias filas (doubleheaders/registros
            # antiguos), y un diccionario indexado por game_id colapsaria esas
            # filas (mismo defecto que measure_rest_basketball.build_rest_frame
            # documenta para NBA).
            rows.append({"idx": i, "diff_base": float(diff), "avg": float(avg),
                        "y": y, "margin": hs - aws, "total": hs + aws})
        pending.append(r)
    return pd.DataFrame(rows)


def build_rest_frame(results: list[dict], params: dict,
                     warmup: int = WARMUP) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Une diff_base/avg y el calendario de descanso, en orden temporal.

    Devuelve DOS vistas, por la MISMA razon que `measure_rest_basketball.
    build_rest_frame` (causa raiz alli: `binary_probs` y `markets['spreads@L']`
    NO tienen la misma longitud porque el motor no excluye empates al
    alimentar mercados de spread/total, solo moneyline):

    - `df`: excluye empates (y==0.5) -- vista correcta para el moneyline
      (`binary_probs`/`binary_outcomes`, engine.py:116-119).
    - `df_all`: TODAS las filas con i>=warmup, incluidos los empates -- vista
      correcta para paridad y criterios de spreads/totales (engine.py
      alimenta esos mercados DENTRO del mismo `if i >= warmup:` sin la
      mascara binaria, solo excluye push). Los empates de la NHL (anteriores
      a 2005) salen del moneyline pero entran en la puck line (seccion 3.5).
    """
    mb = diff_base_frame(results, params, warmup)
    rc = rest_calendar(results, params, warmup)
    merged = mb.merge(rc, on="idx", how="inner", validate="one_to_one")
    merged = merged.sort_values("idx", kind="stable").reset_index(drop=True)
    merged["afectado"] = merged["known"] & (merged["delta_r"].fillna(0.0) != 0.0)
    df_all = merged
    df = merged[merged["y"].isin([0.0, 1.0])].reset_index(drop=True)
    return df, df_all


# ------------------------------------------------------ rejilla vectorizada --
def _lambda_split(diff: np.ndarray, avg: np.ndarray, tilt_scale: float,
                  bonus: float) -> tuple[np.ndarray, np.ndarray]:
    """Las mismas cuatro lineas de `PoissonAdapter._rates` (tilt acotado a
    +-0,30, suelo 0,1), vectorizadas."""
    p_home = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
    tilt = np.clip((p_home - 0.5) * tilt_scale, -0.30, 0.30)
    lam_h = np.maximum(0.1, avg * (0.5 + tilt) + bonus)
    lam_a = np.maximum(0.1, avg * (0.5 - tilt))
    return lam_h, lam_a


def _pmf_grid(lam: np.ndarray, max_goals: int) -> np.ndarray:
    ks = np.arange(max_goals + 1)
    return _poisson.pmf(ks[None, :], lam[:, None])


def home_win_vec(diff: np.ndarray, avg: np.ndarray, tilt_scale: float, bonus: float,
                 max_goals: int) -> np.ndarray:
    """P(home gana), incluido el reparto 50/50 del empate (three_way=False,
    la convencion de moneyline de la NHL -- `poisson_match_probs`, seccion
    1.1). Exacto (no aproximado) porque `dc_rho=0`/`score_rho=0` en produccion
    reducen `_joint_grid`/`poisson_match_probs` a independencia pura sobre la
    MISMA rejilla truncada a `max_goals`; la aserccion de paridad de
    --parity-only es la que lo demuestra, no esta funcion."""
    lam_h, lam_a = _lambda_split(diff, avg, tilt_scale, bonus)
    pmf_h, pmf_a = _pmf_grid(lam_h, max_goals), _pmf_grid(lam_a, max_goals)
    sum_h, sum_a = pmf_h.sum(axis=1), pmf_a.sum(axis=1)
    mass = sum_h * sum_a
    cum_a = np.cumsum(pmf_a, axis=1)
    less_a = np.zeros_like(pmf_a)
    less_a[:, 1:] = cum_a[:, :-1]           # sum_{j<i} pmf_a[j]
    win = np.sum(pmf_h * less_a, axis=1)
    draw = np.sum(pmf_h * pmf_a, axis=1)
    return (win + 0.5 * draw) / mass


def cover_vec(diff: np.ndarray, avg: np.ndarray, tilt_scale: float, bonus: float,
             max_goals: int, line: float) -> np.ndarray:
    """P(local cubre `line`), linea de medio punto (nunca hay push): reutiliza
    la misma convencion `margin > -line` de `poisson_match_probs`."""
    lam_h, lam_a = _lambda_split(diff, avg, tilt_scale, bonus)
    pmf_h, pmf_a = _pmf_grid(lam_h, max_goals), _pmf_grid(lam_a, max_goals)
    K = max_goals + 1
    mass = pmf_h.sum(axis=1) * pmf_a.sum(axis=1)
    m0 = int(round(-line + 0.5))            # margin >= m0 <=> margin > -line
    rev_cum = np.cumsum(pmf_h[:, ::-1], axis=1)[:, ::-1]  # rev_cum[:,k]=sum_{i>=k}
    cover = np.zeros(pmf_h.shape[0])
    for j in range(K):
        k = j + m0
        if k >= K:
            continue
        surv = pmf_h.sum(axis=1) if k <= 0 else rev_cum[:, k]
        cover += pmf_a[:, j] * surv
    return cover / mass


def over_vec(diff: np.ndarray, avg: np.ndarray, tilt_scale: float, bonus: float,
            max_goals: int, line: float) -> np.ndarray:
    """P(total > `line`), linea de medio punto (nunca hay push)."""
    lam_h, lam_a = _lambda_split(diff, avg, tilt_scale, bonus)
    pmf_h, pmf_a = _pmf_grid(lam_h, max_goals), _pmf_grid(lam_a, max_goals)
    K = max_goals + 1
    mass = pmf_h.sum(axis=1) * pmf_a.sum(axis=1)
    m0 = int(round(line + 0.5))              # total >= m0 <=> total > line
    sum_a = pmf_a.sum(axis=1)
    over = np.zeros(pmf_h.shape[0])
    for i in range(K):
        j0 = m0 - i
        if j0 >= K:
            continue
        tail_a = sum_a if j0 <= 0 else np.sum(pmf_a[:, j0:], axis=1)
        over += pmf_h[:, i] * tail_a
    return over / mass


def ll_per_game(p: np.ndarray, y: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Log loss binario por partido, mismo recorte que `tuning._binary_nll_series`."""
    p = np.clip(p, eps, 1.0 - eps)
    return -(y * np.log(p) + (1.0 - y) * np.log(1.0 - p))


def fit(objective: Callable[[np.ndarray], float], x0: list[float], name: str) -> np.ndarray:
    res = minimize(objective, x0=np.asarray(x0, dtype=float), method="Nelder-Mead",
                   options=NM_OPTS)
    if not res.success:
        raise SystemExit(
            f"El optimizador Nelder-Mead NO CONVERGIO ({name}): {res.message}. "
            "Seccion 6: se trata como defecto de codigo y se aborta, no se repite "
            "con otro punto de partida.")
    return res.x


def fit_c(diff_tr: np.ndarray, avg_tr: np.ndarray, de_tr: np.ndarray, y_tr: np.ndarray,
          tilt_scale: float, bonus: float, max_goals: int) -> float:
    def obj(x: np.ndarray) -> float:
        p = home_win_vec(diff_tr + x[0] * de_tr, avg_tr, tilt_scale, bonus, max_goals)
        return float(np.mean(ll_per_game(p, y_tr)))
    return float(fit(obj, [0.0], "c")[0])


def fit_a(diff_tr: np.ndarray, avg_tr: np.ndarray, y_tr: np.ndarray,
         tilt_scale: float, bonus: float, max_goals: int) -> float:
    def obj(x: np.ndarray) -> float:
        p = home_win_vec(diff_tr + x[0], avg_tr, tilt_scale, bonus, max_goals)
        return float(np.mean(ll_per_game(p, y_tr)))
    return float(fit(obj, [0.0], "a")[0])


def fit_ac(diff_tr: np.ndarray, avg_tr: np.ndarray, de_tr: np.ndarray, y_tr: np.ndarray,
          tilt_scale: float, bonus: float, max_goals: int) -> tuple[float, float]:
    def obj(x: np.ndarray) -> float:
        p = home_win_vec(diff_tr + x[0] + x[1] * de_tr, avg_tr, tilt_scale, bonus, max_goals)
        return float(np.mean(ll_per_game(p, y_tr)))
    x = fit(obj, [0.0, 0.0], "a,c conjunto")
    return float(x[0]), float(x[1])


def bootstrap_por_fecha(dates: np.ndarray, diff: np.ndarray,
                        margen: float | None = None) -> dict:
    """Seccion 8: remuestrea DIAS UTC completos del test combinado, 10.000
    replicas, semilla 42. IC95 percentil y error estandar del Delta medio.

    Cuando `margen` no es None, anade `prob_supera_margen`: la fraccion de
    replicas con Delta <= -margen -- "la probabilidad aproximada de que el
    Delta real supere el margen" (seccion 8). No hay una definicion
    equivalente en `measure_rest_basketball.py` (no calcula esta
    probabilidad), asi que se deriva directamente del propio bootstrap, tal
    como exige la seccion 8 en ese caso."""
    u, inv = np.unique(dates, return_inverse=True)
    sums = np.bincount(inv, weights=diff)
    cnts = np.bincount(inv).astype(float)
    rng = np.random.default_rng(SEED)
    pick = rng.integers(0, len(u), size=(N_BOOT, len(u)))
    reps = sums[pick].sum(axis=1) / cnts[pick].sum(axis=1)
    out = {"n_dias": int(len(u)),
          "ic95": [float(np.quantile(reps, 0.025)), float(np.quantile(reps, 0.975))],
          "se": float(np.std(reps, ddof=1))}
    if margen is not None:
        out["prob_supera_margen"] = float(np.mean(reps <= -margen))
    return out


def _safe_informe(nombre: str, fn: Callable[[], dict | None]) -> dict | None:
    """Ejecuta un informe secundario protegido: la seccion 10 los llama "no
    deciden", asi que un fallo en uno de ellos (fichero ausente/corrupto,
    columna inesperada, particion vacia...) NUNCA debe impedir escribir el
    JSON principal con los criterios y el veredicto. El error se anota en la
    propia seccion en vez de abortar toda la medicion."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 -- informe opcional, ver docstring
        print(f"aviso: informe secundario '{nombre}' fallo: {type(exc).__name__}: {exc}",
             file=sys.stderr)
        return {"error": f"{type(exc).__name__}: {exc}"}


def bias_of(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean(p) - np.mean(y))


# ------------------------------------------------------------------ paridad --
def assert_parity_base(results: list[dict], params: dict, df: pd.DataFrame,
                       df_all: pd.DataFrame, tilt_scale: float, bonus: float,
                       max_goals: int, warmup: int = WARMUP, atol: float = 1e-12) -> None:
    """Seccion 5, aserto 1: el brazo base coincide con `binary_probs` y con
    `markets['spreads@-1.5'|'spreads@1.5'|'totals@5.5'|'totals@6.5']` del
    motor ejecutado sobre la configuracion de produccion (c=0 implicito)."""
    ref = walk_forward_backtest(results, LEAGUE, FAMILY, params, warmup=warmup,
                                spread_lines=SPREAD_LINES, total_lines=TOTAL_LINES)
    mine_p = home_win_vec(df["diff_base"].to_numpy(), df["avg"].to_numpy(),
                          tilt_scale, bonus, max_goals)
    mine_y = df["y"].to_numpy()
    theirs_p = np.asarray(ref["binary_probs"], dtype=float)
    theirs_y = np.asarray(ref["binary_outcomes"], dtype=float)
    if len(mine_p) != len(theirs_p) or not np.allclose(mine_p, theirs_p, rtol=0, atol=atol):
        raise SystemExit("PARIDAD ROTA (base, moneyline): no se mide nada.")
    if not np.array_equal(mine_y, theirs_y):
        raise SystemExit("RESULTADOS DESALINEADOS (base, moneyline).")
    # Espeja tambien la formula escalar de produccion (sin duplicarla) en una
    # muestra: el vector vectorizado debe coincidir con
    # `dist.poisson_match_probs` llamado fila a fila.
    sample = df.head(200)
    for _, row in sample.iterrows():
        lam_h, lam_a = _lambda_split(np.array([row["diff_base"]]), np.array([row["avg"]]),
                                     tilt_scale, bonus)
        scalar = dist.poisson_match_probs(float(lam_h[0]), float(lam_a[0]), None, None,
                                          max_goals=max_goals)["home_win"]
        vec = home_win_vec(np.array([row["diff_base"]]), np.array([row["avg"]]),
                           tilt_scale, bonus, max_goals)[0]
        if not np.isclose(scalar, vec, rtol=0, atol=atol):
            raise SystemExit("PARIDAD ROTA (formula escalar, moneyline).")
    _assert_parity_markets(ref, df_all, params, tilt_scale, bonus, max_goals,
                           c=0.0, atol=atol)


def _delta_eff_frame(df_all: pd.DataFrame, c: float) -> tuple[np.ndarray, np.ndarray]:
    diff_eff = df_all["diff_base"].to_numpy() + c * df_all["delta_eff"].to_numpy()
    return diff_eff, df_all["avg"].to_numpy()


def _assert_parity_markets(ref: dict, df_all: pd.DataFrame, params: dict, tilt_scale: float,
                           bonus: float, max_goals: int, c: float, atol: float) -> None:
    """Puck line +-1,5 y totales 5,5/6,5 sobre TODA `df_all` (incluidos
    empates, seccion 3.5 -- el motor no los excluye en spreads/totals, solo en
    moneyline). Usada tanto por el brazo base (c=0) como por el de tratamiento
    (aserto 2)."""
    diff_eff, avg = _delta_eff_frame(df_all, c)
    margin = df_all["margin"].to_numpy()
    total = df_all["total"].to_numpy()
    for line in SPREAD_LINES:
        key = f"spreads@{line}"
        mkt = ref["markets"].get(key)
        if mkt is None:
            raise SystemExit(f"PARIDAD ROTA (spreads) c={c}: el motor no devolvio '{key}'.")
        mine_p = cover_vec(diff_eff, avg, tilt_scale, bonus, max_goals, line)
        push = margin == -line   # nunca ocurre con una linea de medio punto
        mine_p, mine_y = mine_p[~push], (margin[~push] > -line).astype(float)
        theirs_p = np.asarray(mkt["probs"], dtype=float)
        theirs_y = np.asarray(mkt["outcomes"], dtype=float)
        if len(mine_p) != len(theirs_p) or not np.allclose(mine_p, theirs_p, rtol=0, atol=atol):
            raise SystemExit(f"PARIDAD ROTA (spreads probs) c={c} linea {line}.")
        if len(mine_y) != len(theirs_y) or not np.array_equal(mine_y, theirs_y):
            raise SystemExit(f"PARIDAD ROTA (spreads outcomes) c={c} linea {line}.")
    for line in TOTAL_LINES:
        key = f"totals@{line}"
        mkt = ref["markets"].get(key)
        if mkt is None:
            raise SystemExit(f"PARIDAD ROTA (totals) c={c}: el motor no devolvio '{key}'.")
        mine_p = over_vec(diff_eff, avg, tilt_scale, bonus, max_goals, line)
        push = total == line     # nunca ocurre con una linea de medio punto
        mine_p, mine_y = mine_p[~push], (total[~push] > line).astype(float)
        theirs_p = np.asarray(mkt["probs"], dtype=float)
        theirs_y = np.asarray(mkt["outcomes"], dtype=float)
        if len(mine_p) != len(theirs_p) or not np.allclose(mine_p, theirs_p, rtol=0, atol=atol):
            raise SystemExit(f"PARIDAD ROTA (totals probs) c={c} linea {line}.")
        if len(mine_y) != len(theirs_y) or not np.array_equal(mine_y, theirs_y):
            raise SystemExit(f"PARIDAD ROTA (totals outcomes) c={c} linea {line}.")


def assert_parity_treatment(results: list[dict], params: dict, df: pd.DataFrame,
                            df_all: pd.DataFrame, tilt_scale: float, bonus: float,
                            max_goals: int, c: float, warmup: int = WARMUP,
                            atol: float = 1e-12) -> None:
    """Seccion 5, aserto 2: el brazo T con `c` coincide con el motor ejecutado
    con `params["rest_elo_per_day"] = c`, en moneyline, puck line y totales."""
    diff_eff = df["diff_base"].to_numpy() + c * df["delta_eff"].to_numpy()
    mine_p = home_win_vec(diff_eff, df["avg"].to_numpy(), tilt_scale, bonus, max_goals)
    ref = walk_forward_backtest(results, LEAGUE, FAMILY, {**params, "rest_elo_per_day": c},
                                warmup=warmup, spread_lines=SPREAD_LINES,
                                total_lines=TOTAL_LINES)
    theirs_p = np.asarray(ref["binary_probs"], dtype=float)
    if len(mine_p) != len(theirs_p) or not np.allclose(mine_p, theirs_p, rtol=0, atol=atol):
        raise SystemExit(f"PARIDAD ROTA (tratamiento c={c}): no se mide nada.")
    _assert_parity_markets(ref, df_all, params, tilt_scale, bonus, max_goals, c, atol)


# -------------------------------------------------------------------- --pre --
def _b2b_breakdown(rc_known: pd.DataFrame) -> dict:
    local = int(((rc_known["hr"] == 1) & (rc_known["ar"] != 1)).sum())
    visit = int(((rc_known["ar"] == 1) & (rc_known["hr"] != 1)).sum())
    both = int(((rc_known["hr"] == 1) & (rc_known["ar"] == 1)).sum())
    return {"solo_local": local, "solo_visitante": visit, "ambos": both}


def _potencia_fold(rc: pd.DataFrame, fold: dict, warmup_train_start: str = "") -> dict:
    train = rc[rc["date"] <= fold["train_end"]]
    test = rc[(rc["date"] >= fold["test_start"]) & (rc["date"] <= fold["test_end"])]
    test_known = test[test["known"]]
    test_af = test_known[test_known["delta_r"] != 0.0]
    return {
        "n_train": int(len(train)), "n_test": int(len(test)),
        "n_dias_test": int(test["date"].nunique()),
        "n_test_afectados": int(len(test_af)),
        "dias_con_afectados": int(test_af["date"].nunique()),
        "abs_delta_r_1_2_3": [int((test_af["delta_r"].abs() == k).sum()) for k in (1, 2, 3)],
        "local_mas_descansado": int((test_af["delta_r"] > 0).sum()),
        "media_delta_r": float(test_af["delta_r"].mean()) if len(test_af) else None,
        "rms_delta_r": float(np.sqrt((test_af["delta_r"] ** 2).mean())) if len(test_af) else None,
        "back_to_back": _b2b_breakdown(test_known),
    }


def _pares_mismo_dia_utc(results: list[dict]) -> dict:
    """Seccion 3.1: pares equipo-fecha con DOS partidos el mismo dia UTC (el
    equipo aparece dos veces como local o visitante en la misma fecha), y
    filas identicas (fecha, local, visitante) por separado -- el defecto ya
    documentado en la enmienda 1 del portero, distinto del caso de calendario
    (doble jornada real vs. fila duplicada)."""
    by_date_team: Counter = Counter()
    seen_rows: Counter = Counter()
    for r in results:
        d = str(r.get("date", ""))[:10]
        by_date_team[(d, r["home"])] += 1
        by_date_team[(d, r["away"])] += 1
        seen_rows[(d, r["home"], r["away"])] += 1
    pares_dobles = sum(1 for v in by_date_team.values() if v >= 2)
    filas_identicas = sum(v - 1 for v in seen_rows.values() if v >= 2)
    return {"pares_equipo_fecha_dobles": int(pares_dobles),
           "filas_identicas_extra": int(filas_identicas)}


def informe_pre() -> dict:
    results, params, procedencia = load_league()
    if not results:
        return {"liga": LEAGUE, **procedencia, "aviso": "sin resultados historicos"}
    rc = rest_calendar(results, params, WARMUP)
    conocidos = rc[rc["known"]]
    afectados = conocidos[conocidos["delta_r"] != 0.0]

    normalize = get_team_normalizer(LEAGUE)
    probe_sin_tope = RestModel(points_per_day=0.0, max_rest=10**9, normalize=normalize)
    rc_sin_tope = rest_calendar(results, params, WARMUP, probe=probe_sin_tope)
    conocidos_sin_tope = rc_sin_tope[rc_sin_tope["known"]]
    desconocidos = rc[~rc["known"]]

    out = {
        "liga": LEAGUE, **procedencia,
        "partidos_totales": int(len(results)),
        "evaluados_tras_warmup": int(len(rc)),
        "con_ambos_descansos_conocidos": int(len(conocidos)),
        "primer_partido_sin_historial": int(len(desconocidos)),
        "afectados": int(len(afectados)),
        "fraccion_afectada_f": float(len(afectados) / len(conocidos)) if len(conocidos) else None,
        "neutrales": int(rc["neutral"].sum()),
        "delta_r_counts": {str(int(k)): int(v)
                          for k, v in conocidos["delta_r"].value_counts().sort_index().items()},
        "dias_descanso_por_equipo_partido": {
            str(int(k)): int(v) for k, v in
            pd.concat([conocidos["hr"], conocidos["ar"]]).value_counts().sort_index().items()},
        "dias_descanso_5_o_mas_sin_tope": int(
            pd.concat([conocidos_sin_tope["hr"], conocidos_sin_tope["ar"]]).ge(5).sum()),
        "back_to_back_global": _b2b_breakdown(conocidos),
        "particiones": {name: _potencia_fold(rc, fold) for name, fold in FOLDS.items()},
        **_pares_mismo_dia_utc(results),
    }
    return out


# -------------------------------------------------------------- captura odds --
def captured_lines(results: list[dict]) -> dict:
    """Linea de puck line capturada y procedencia de las cuotas leidas (mismo
    mecanismo que `measure_rest_basketball.captured_lines`:
    `_match_index`/`_match_result`/`_pick_main_lines` de produccion)."""
    odds_dir = ROOT / "data" / "odds"
    ficheros_sha256 = {f.name: sha256_of(f)
                       for f in sorted(odds_dir.glob(f"odds_{LEAGUE}_*.csv"))}
    odds = load_closing_odds(ROOT, LEAGUE)
    if not odds:
        return {"spreads": {}, "game_ids_emparejados": set(),
               "ficheros_sha256": ficheros_sha256}
    idx, used, spreads = _match_index(odds), set(), {}
    game_ids_emparejados: set[str] = set()
    for r in sorted(results, key=lambda x: str(x.get("date", ""))):
        eo = _match_result(r, idx, used)
        if eo is None:
            continue
        used.add(eo.event.event_id)
        game_ids_emparejados.add(str(r.get("game_id")))
        spread, _total = _pick_main_lines(eo)
        if spread is not None:
            spreads[str(r.get("game_id"))] = spread
    return {"spreads": spreads, "game_ids_emparejados": game_ids_emparejados,
           "ficheros_sha256": ficheros_sha256}


# ------------------------------------------------------------- modo completo --
def run_nhl(results: list[dict], params: dict) -> dict:
    rparams = resolved_params(params)
    tilt_scale = rparams.get("tilt_scale", 0.9)
    bonus = rparams.get("home_scoring_bonus", 0.0)
    max_goals = int(rparams.get("max_score", 15))

    df, df_all = build_rest_frame(results, params, WARMUP)
    assert_parity_base(results, params, df, df_all, tilt_scale, bonus, max_goals)
    assert_parity_treatment(results, params, df, df_all, tilt_scale, bonus, max_goals, PROBE_C)

    out: dict = {"n_total": int(len(df)), "folds": {}}
    pieces, pieces_all = [], []
    c_by_fold: dict[str, float] = {}
    a_by_fold: dict[str, float] = {}
    cconj_by_fold: dict[str, float] = {}
    grid_c = np.round(np.arange(-10.0, 30.0 + 1e-9, 2.5), 2)  # informe secundario 3
    # Criterio 6 agregado (seccion 7.6): partidos crudos (ambas lineas de
    # puck line, las tres particiones), NO las 6 medias por
    # particion/linea -- ver el comentario junto a `puck_delta_mean` abajo.
    puck_diffs_all: list[np.ndarray] = []
    puck_dates_all: list[np.ndarray] = []

    for name, fold in FOLDS.items():
        train = df[df["date"] <= fold["train_end"]]
        test = df[(df["date"] >= fold["test_start"]) & (df["date"] <= fold["test_end"])].copy()
        test_all = df_all[(df_all["date"] >= fold["test_start"])
                          & (df_all["date"] <= fold["test_end"])].copy()
        diff_tr = train["diff_base"].to_numpy()
        avg_tr = train["avg"].to_numpy()
        de_tr = train["delta_eff"].to_numpy()
        y_tr = train["y"].to_numpy()

        c = fit_c(diff_tr, avg_tr, de_tr, y_tr, tilt_scale, bonus, max_goals)
        a0 = fit_a(diff_tr, avg_tr, y_tr, tilt_scale, bonus, max_goals)
        a_joint, c_joint = fit_ac(diff_tr, avg_tr, de_tr, y_tr, tilt_scale, bonus, max_goals)
        c_by_fold[name], a_by_fold[name], cconj_by_fold[name] = c, a0, c_joint

        diff_te = test["diff_base"].to_numpy()
        avg_te = test["avg"].to_numpy()
        de_te = test["delta_eff"].to_numpy()
        y_te = test["y"].to_numpy()
        p_base = home_win_vec(diff_te, avg_te, tilt_scale, bonus, max_goals)
        p_treat = home_win_vec(diff_te + c * de_te, avg_te, tilt_scale, bonus, max_goals)
        p_ctrl = home_win_vec(diff_te + a0, avg_te, tilt_scale, bonus, max_goals)
        test["ll_base"] = ll_per_game(p_base, y_te)
        test["ll_treat"] = ll_per_game(p_treat, y_te)
        test["ll_ctrl"] = ll_per_game(p_ctrl, y_te)
        test["p_base"], test["p_treat"] = p_base, p_treat
        af = test[test["afectado"]]

        perfil = [{"c": float(cc), "log_loss_train": float(np.mean(ll_per_game(
            home_win_vec(diff_tr + cc * de_tr, avg_tr, tilt_scale, bonus, max_goals), y_tr)))}
                 for cc in grid_c]

        # Puck line, criterio 6: `c` del moneyline de esta particion, sobre
        # TODA `test_all` (incluye empates, seccion 3.5).
        diff_te_all = test_all["diff_base"].to_numpy()
        avg_te_all = test_all["avg"].to_numpy()
        de_te_all = test_all["delta_eff"].to_numpy()
        margin_all = test_all["margin"].to_numpy()
        dates_te_all = test_all["date"].to_numpy()
        spreads_delta = {}
        for line in SPREAD_LINES:
            p_b = cover_vec(diff_te_all, avg_te_all, tilt_scale, bonus, max_goals, line)
            p_t = cover_vec(diff_te_all + c * de_te_all, avg_te_all, tilt_scale, bonus,
                            max_goals, line)
            covered = (margin_all > -line).astype(float)
            push = margin_all == -line
            ll_b = ll_per_game(p_b[~push], covered[~push])
            ll_t = ll_per_game(p_t[~push], covered[~push])
            diff_line = ll_t - ll_b
            spreads_delta[str(line)] = float(diff_line.mean()) if (~push).any() else None
            if (~push).any():
                puck_diffs_all.append(diff_line)
                puck_dates_all.append(dates_te_all[~push])

        out["folds"][name] = {
            "train_end": fold["train_end"], "test": [fold["test_start"], fold["test_end"]],
            "n_train": int(len(train)), "n_test": int(len(test)), "n_test_afectados": int(len(af)),
            "c": c, "control_a": a0, "c_conj": c_joint, "a_conj": a_joint,
            "bias_base_test": bias_of(p_base, y_te),
            "delta_ll_afectados": float((af["ll_treat"] - af["ll_base"]).mean()) if len(af) else None,
            "delta_ll_universo": float((test["ll_treat"] - test["ll_base"]).mean()),
            "ll_trat_menos_ctrl_universo": float((test["ll_treat"] - test["ll_ctrl"]).mean()),
            "perfil_log_loss_train_grid": perfil,
            "delta_ll_puck_line": spreads_delta,
        }
        pieces.append(test)
        pieces_all.append(test_all)

    assert_parity_treatment(results, params, df, df_all, tilt_scale, bonus, max_goals,
                            c_by_fold["C"])

    test_all_mny = pd.concat(pieces).reset_index(drop=True)
    test_all_full = pd.concat(pieces_all).reset_index(drop=True)
    af_all = test_all_mny[test_all_mny["afectado"]]
    diff_af = (af_all["ll_treat"] - af_all["ll_base"]).to_numpy()
    diff_tc = (test_all_mny["ll_treat"] - test_all_mny["ll_ctrl"]).to_numpy()
    # Seccion 9: partidos afectados donde el tilt YA estaba recortado a
    # +-0,30 a partir de `diff_base` solo (antes de sumar el termino de
    # descanso, |diff_base| aprox 280 Elo) -- el ajuste de descanso vale 0 en
    # probabilidad para esos partidos aunque delta_r != 0 los cuente como
    # "afectados" (dilucion conservadora del criterio 1, seccion 9).
    p_home_base_af = 1.0 / (1.0 + 10.0 ** (-af_all["diff_base"].to_numpy() / 400.0))
    n_afectados_tilt_recortado = int(
        (np.abs((p_home_base_af - 0.5) * tilt_scale) >= 0.30).sum())
    out["combinado"] = {
        "n_test": int(len(test_all_mny)), "n_afectados": int(len(af_all)),
        "n_afectados_tilt_recortado": n_afectados_tilt_recortado,
        "delta_ll_afectados": float(diff_af.mean()),
        "bootstrap_afectados": bootstrap_por_fecha(af_all["date"].to_numpy(), diff_af,
                                                   margen=IMPROVEMENT_MARGIN),
        "bootstrap_trat_vs_ctrl": bootstrap_por_fecha(test_all_mny["date"].to_numpy(), diff_tc),
        "delta_ll_universo": float((test_all_mny["ll_treat"] - test_all_mny["ll_base"]).mean()),
        "ece_base": float(expected_calibration_error(test_all_mny["p_base"].tolist(),
                                                      test_all_mny["y"].tolist())),
        "ece_trat": float(expected_calibration_error(test_all_mny["p_treat"].tolist(),
                                                      test_all_mny["y"].tolist())),
        "ll_trat": float(test_all_mny["ll_treat"].mean()),
        "ll_ctrl": float(test_all_mny["ll_ctrl"].mean()),
        "bias_base": bias_of(test_all_mny["p_base"].to_numpy(), test_all_mny["y"].to_numpy()),
    }
    c_comb = out["combinado"]
    # Criterio 6 agregado (correccion de esta sesion): media POR PARTIDO
    # sobre la concatenacion de todos los partidos de las dos lineas de puck
    # line en las tres particiones -- NO la media sin ponderar de las 6
    # medias por particion/linea (esa version pesaba igual una particion con
    # pocos partidos evaluados que una con miles). `delta_ll_puck_line` por
    # particion/linea (dentro de `out["folds"]`) queda como diagnostico.
    puck_diff_concat = np.concatenate(puck_diffs_all) if puck_diffs_all else np.array([])
    puck_dates_concat = np.concatenate(puck_dates_all) if puck_dates_all else np.array([])
    if len(puck_diff_concat) == 0:
        raise SystemExit("criterio 6: no hay ningun partido evaluable en la puck line.")
    puck_delta_mean = float(puck_diff_concat.mean())
    c_comb["bootstrap_puck_line"] = bootstrap_por_fecha(puck_dates_concat, puck_diff_concat,
                                                        margen=0.0)
    out["criterios"] = {
        "1_delta_afectados_combinado_le_-0.002": c_comb["delta_ll_afectados"] <= -IMPROVEMENT_MARGIN,
        "2_delta_afectados_negativo_en_cada_particion":
            all(f["delta_ll_afectados"] is not None and f["delta_ll_afectados"] < 0
                for f in out["folds"].values()),
        "3_ece_universo_no_empeora": c_comb["ece_trat"] <= c_comb["ece_base"],
        "4_c_positivo_en_las_tres_particiones": all(v > 0 for v in c_by_fold.values()),
        "5_trat_bate_control_intercepto": c_comb["ll_trat"] < c_comb["ll_ctrl"],
        "6_puck_line_no_empeora": puck_delta_mean <= 0,
        "7_c_conj_positivo_en_las_tres_particiones": all(v > 0 for v in cconj_by_fold.values()),
    }
    out["veredicto"] = "ACEPTA" if all(out["criterios"].values()) else "RECHAZA"
    out["c_por_particion"] = c_by_fold
    out["a_por_particion"] = a_by_fold
    out["c_conj_por_particion"] = cconj_by_fold
    out["delta_ll_puck_line_media"] = puck_delta_mean

    # Informes secundarios 4-11 (seccion 10: "no deciden"). Cada uno se
    # ejecuta bajo `_safe_informe`: un fallo en cualquiera de ellos (fichero
    # ausente/corrupto, columna inesperada, particion vacia...) se anota como
    # `{"error": ...}` en su propia seccion, pero NUNCA impide escribir el
    # JSON principal con los criterios y el veredicto ya calculados arriba.

    def _informe_por_delta_r() -> dict:
        return {
            "por_abs_delta_r": {
                str(k): float((af_all.loc[af_all["delta_r"].abs() == k, "ll_treat"]
                              - af_all.loc[af_all["delta_r"].abs() == k, "ll_base"]).mean())
                for k in (1, 2, 3) if (af_all["delta_r"].abs() == k).any()},
            "por_signo": {
                "positivo": float((af_all.loc[af_all["delta_r"] > 0, "ll_treat"]
                                  - af_all.loc[af_all["delta_r"] > 0, "ll_base"]).mean())
                if (af_all["delta_r"] > 0).any() else None,
                "negativo": float((af_all.loc[af_all["delta_r"] < 0, "ll_treat"]
                                  - af_all.loc[af_all["delta_r"] < 0, "ll_base"]).mean())
                if (af_all["delta_r"] < 0).any() else None},
            "residuo_medio_por_delta_r": {
                str(int(k)): float((g["y"] - g["p_base"]).mean())
                for k, g in test_all_mny[test_all_mny["known"]].groupby("delta_r")},
        }

    def _informe_por_back_to_back() -> dict:
        # Informe secundario 5: por back-to-backs (ninguno/local/visitante/ambos).
        known_all = test_all_mny[test_all_mny["known"]].copy()
        known_all["hr"] = known_all["hr"].astype(float)
        known_all["ar"] = known_all["ar"].astype(float)
        cats = {
            "ninguno": (known_all["hr"] != 1) & (known_all["ar"] != 1),
            "solo_local": (known_all["hr"] == 1) & (known_all["ar"] != 1),
            "solo_visitante": (known_all["ar"] == 1) & (known_all["hr"] != 1),
            "ambos": (known_all["hr"] == 1) & (known_all["ar"] == 1),
        }
        return {
            name: {"n": int(mask.sum()),
                  "delta_ll_universo": float((known_all.loc[mask, "ll_treat"]
                                             - known_all.loc[mask, "ll_base"]).mean())
                  if mask.any() else None}
            for name, mask in cats.items()}

    def _informe_por_temporada() -> dict:
        # Informe secundario 6: por temporada (Oct-Jun ~ "YYYY-YY"). Usa una
        # copia local (`con_temporada`) en vez de reasignar `test_all_mny`,
        # para que un fallo aqui no deje la variable compartida a medio
        # mutar para los informes que se ejecutan despues.
        season = test_all_mny["date"].apply(_nhl_season_label)
        con_temporada = test_all_mny.assign(season=season)
        return {
            s: {"n": int(len(g)),
               "delta_ll_universo": float((g["ll_treat"] - g["ll_base"]).mean()),
               "regimen_atipico": s in ("2019-20", "2020-21")}
            for s, g in con_temporada.groupby("season")}

    def _informe_sin_exhibiciones() -> dict:
        # Informe secundario 8: sin exhibiciones (equipos con <=11
        # apariciones, TODO el fichero, no solo el test).
        apariciones: Counter = Counter()
        for r in results:
            apariciones[adapter_normalize(r["home"])] += 1
            apariciones[adapter_normalize(r["away"])] += 1
        pocas = {t for t, n in apariciones.items() if n <= 11}
        home_norm = af_all["home"].map(adapter_normalize)
        away_norm = af_all["away"].map(adapter_normalize)
        sin_exh = af_all[~home_norm.isin(pocas) & ~away_norm.isin(pocas)]
        return {
            "equipos_excluidos": len(pocas), "n_afectados": int(len(sin_exh)),
            "delta_ll_afectados": float((sin_exh["ll_treat"] - sin_exh["ll_base"]).mean())
            if len(sin_exh) else None,
        }

    def _informe_sin_pares_dobles() -> dict:
        # Informe secundario 9: sin los pares equipo-fecha dobles del mismo
        # dia UTC (distinto del "9" de la seccion 9 del documento, que es
        # `n_afectados_tilt_recortado` en `out["combinado"]`).
        dobles = _pares_mismo_dia_utc(results)
        doble_dates_teams = _sameday_pairs_set(results)
        af_sin_dobles = af_all[~af_all.apply(
            lambda row: (row["date"], row["home"]) in doble_dates_teams
            or (row["date"], row["away"]) in doble_dates_teams, axis=1)]
        return {
            **dobles, "n_afectados": int(len(af_sin_dobles)),
            "delta_ll_afectados": float((af_sin_dobles["ll_treat"] - af_sin_dobles["ll_base"]).mean())
            if len(af_sin_dobles) else None,
        }

    def _informe_totales_max_abs_delta_p_over() -> dict:
        # Informe secundario 7: totales, con c_C (se espera ~1e-6/1e-7).
        c_c = c_by_fold["C"]
        diff_full = test_all_full["diff_base"].to_numpy()
        avg_full = test_all_full["avg"].to_numpy()
        de_full = test_all_full["delta_eff"].to_numpy()
        max_dp_over = {}
        for line in TOTAL_LINES:
            p_b = over_vec(diff_full, avg_full, tilt_scale, bonus, max_goals, line)
            p_t = over_vec(diff_full + c_c * de_full, avg_full, tilt_scale, bonus, max_goals, line)
            max_dp_over[str(line)] = float(np.max(np.abs(p_t - p_b))) if len(p_b) else None
        return max_dp_over

    def _informe_linea_capturada() -> dict | None:
        # Informe secundario 10: linea capturada del mercado (h2h y puck line).
        c_c = c_by_fold["C"]
        cap = captured_lines(results)
        matched_ids = cap["game_ids_emparejados"]
        if not matched_ids:
            return None
        cte = test_all_mny[(test_all_mny["date"] >= FOLDS["C"]["test_start"])
                           & (test_all_mny["date"] <= FOLDS["C"]["test_end"])
                           & (test_all_mny["game_id"].isin(matched_ids))].copy()
        cte["mkt_line"] = cte["game_id"].map(cap["spreads"])
        m = cte[cte["mkt_line"].notna()]
        informe = {
            "n_h2h": int(len(cte)),
            "delta_ll_h2h": float((cte["ll_treat"] - cte["ll_base"]).mean()) if len(cte) else None,
            "n_spread_con_linea": int(len(m)),
            "ficheros_odds_sha256": cap["ficheros_sha256"],
        }
        if len(m):
            diff_m = m["diff_base"].to_numpy()
            avg_m = m["avg"].to_numpy()
            de_m = m["delta_eff"].to_numpy()
            lines = m["mkt_line"].to_numpy(dtype=float)
            margin_m = m["margin"].to_numpy()
            push = margin_m == -lines
            p_b = np.array([dist.poisson_match_probs(
                *_lambda_split(np.array([d]), np.array([a]), tilt_scale, bonus),
                ln, None, max_goals=max_goals)["home_cover"]
                for d, a, ln in zip(diff_m, avg_m, lines)])
            p_t = np.array([dist.poisson_match_probs(
                *_lambda_split(np.array([d + c_c * de]), np.array([a]), tilt_scale, bonus),
                ln, None, max_goals=max_goals)["home_cover"]
                for d, a, de, ln in zip(diff_m, avg_m, de_m, lines)])
            covered = (margin_m > -lines).astype(float)
            ll_b = ll_per_game(p_b[~push], covered[~push])
            ll_t = ll_per_game(p_t[~push], covered[~push])
            informe["delta_ll_spread"] = float((ll_t - ll_b).mean()) if (~push).any() else None
            informe["n_spread_evaluado"] = int((~push).sum())
        return informe

    out["secundario_por_delta_r"] = _safe_informe("por_delta_r", _informe_por_delta_r)
    out["secundario_por_back_to_back"] = _safe_informe("por_back_to_back",
                                                        _informe_por_back_to_back)
    out["secundario_por_temporada"] = _safe_informe("por_temporada", _informe_por_temporada)
    out["secundario_sin_exhibiciones"] = _safe_informe("sin_exhibiciones",
                                                       _informe_sin_exhibiciones)
    out["secundario_sin_pares_dobles"] = _safe_informe("sin_pares_dobles",
                                                       _informe_sin_pares_dobles)
    out["secundario_totales_max_abs_delta_p_over"] = _safe_informe(
        "totales_max_abs_delta_p_over", _informe_totales_max_abs_delta_p_over)

    # Paridad de la puck line/totales con c_C constante sobre TODO el
    # historico: es una comprobacion de correccion, no un informe opcional
    # (seccion 10 solo cubre informes que "no deciden"), asi que se deja
    # SIN la proteccion de `_safe_informe` -- un fallo aqui debe abortar.
    c_c = c_by_fold["C"]
    ref_c = walk_forward_backtest(results, LEAGUE, FAMILY, {**params, "rest_elo_per_day": c_c},
                                  warmup=WARMUP, spread_lines=SPREAD_LINES,
                                  total_lines=TOTAL_LINES)
    _assert_parity_markets(ref_c, df_all, params, tilt_scale, bonus, max_goals, c_c, 1e-12)

    out["secundario_linea_capturada"] = _safe_informe("linea_capturada",
                                                       _informe_linea_capturada)
    # Informe secundario 11: SOLO identidades del portero (si el fichero
    # existe), sin leer resultados de porteria.
    out["secundario_porteros_identidades"] = _safe_informe(
        "porteros_identidades", lambda: _informe_goalies_solo_identidades(results))

    return out


def _sameday_pairs_set(results: list[dict]) -> set[tuple[str, str]]:
    by_date_team: dict[tuple[str, str], int] = Counter()
    for r in results:
        d = str(r.get("date", ""))[:10]
        by_date_team[(d, r["home"])] += 1
        by_date_team[(d, r["away"])] += 1
    return {k for k, v in by_date_team.items() if v >= 2}


_normalize_nhl = get_team_normalizer(LEAGUE)


def adapter_normalize(name: str) -> str:
    return _normalize_nhl(name)


def _nhl_season_label(date_str: str) -> str:
    y, m = int(date_str[:4]), int(date_str[5:7])
    start = y if m >= 8 else y - 1  # temporada regular NHL: oct-jun, con
    return f"{start}-{str((start + 1) % 100).zfill(2)}"          # pretemporada en sep


def _informe_goalies_solo_identidades(results: list[dict]) -> dict | None:
    """Seccion 10.11: fraccion de partidos con r=1 (back-to-back) en que el
    titular difiere del titular del partido anterior del equipo.

    Esquema real de `goalies_nhl.csv` (`src/sqp/storage/goalies.py:44`,
    `APPEARANCE_COLUMNS`): NO hay columna `team` (solo `team_nhl`/
    `team_espn`/`team_side`), y `starter` es booleano -- se parsea con la
    misma tolerancia que `pipeline.goalie_backfill._load_complete_game_ids`
    (pandas puede serializar el booleano como "True"/"False", "true"/"false"
    o 1/0 segun como se haya escrito el CSV). Solo lee date/team_nhl/
    goalie_player_id/starter, NUNCA shots_against/saves/goals_against/toi, y
    no cruza porteros con resultados de partido."""
    path = ROOT / "data" / "historical" / "goalies_nhl.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, usecols=["date", "team_nhl", "goalie_player_id", "starter"],
                     dtype={"date": str, "team_nhl": str, "goalie_player_id": str})
    is_starter = df["starter"].astype(str).str.strip().isin({"True", "true", "1", "1.0"})
    df = df[is_starter].sort_values("date", kind="stable")
    last_starter: dict[str, str] = {}
    last_date: dict[str, str] = {}
    cambios = {"1": [0, 0], "otros": [0, 0]}  # [cambios, total] por bucket r==1 / resto
    for _, row in df.iterrows():
        team = row["team_nhl"]
        date = row["date"][:10]
        starter = row["goalie_player_id"]
        prev_starter = last_starter.get(team)
        prev_date = last_date.get(team)
        if prev_starter is not None and prev_date is not None:
            try:
                r = (_date.fromisoformat(date) - _date.fromisoformat(prev_date)).days
            except ValueError:
                r = None
            bucket = "1" if r == 1 else "otros"
            cambios[bucket][1] += 1
            if starter != prev_starter:
                cambios[bucket][0] += 1
        last_starter[team] = starter
        last_date[team] = date
    return {bucket: {"cambios": c, "total": t, "fraccion": (c / t if t else None)}
           for bucket, (c, t) in cambios.items()}


# ------------------------------------------------------------------- main --
def _check_pre_hash(pre_data: dict, procedencia: dict) -> None:
    """`pre_data` es obligatorio en el modo completo (ver `main`): esta
    funcion aborta si a cualquiera de los dos lados le falta el SHA-256, en
    vez de dejarlo pasar en silencio -- antes de esta correccion, la ausencia
    de hash en cualquiera de los dos lados desactivaba la comprobacion sin
    avisar."""
    hash_previo = pre_data.get("sha256")
    hash_actual = procedencia.get("sha256")
    if hash_previo is None:
        raise SystemExit(
            "--pre-json no registra 'sha256' (el --pre que lo genero no llego a "
            "leer results_nhl.csv, o el fichero no existia entonces). El modo "
            "completo aborta: no hay hash de referencia con el que comparar.")
    if hash_actual is None:
        raise SystemExit(
            "El fichero de resultados leido ahora no tiene SHA-256 registrado "
            "(no existe). El modo completo aborta: no se puede comparar contra "
            "--pre-json.")
    if hash_previo != hash_actual:
        raise SystemExit(
            f"HASH DE ENTRADA CAMBIO: --pre-json registra {hash_previo} y el "
            f"fichero leido ahora es {hash_actual}. El modo completo aborta "
            "(seccion 14): los datos ya no son los que midio --pre.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pre", action="store_true")
    ap.add_argument("--parity-only", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--pre-json", type=Path, default=None,
                    help="Salida de --pre; el modo completo aborta si el SHA-256 del "
                        "fichero de resultados leido ahora difiere del alli registrado.")
    args = ap.parse_args()

    if args.pre and args.parity_only:
        ap.error("--pre y --parity-only son mutuamente excluyentes.")
    if not args.parity_only and args.out is None:
        ap.error("--out es obligatorio salvo en --parity-only.")
    if args.pre_json and (args.pre or args.parity_only):
        ap.error("--pre-json solo aplica al modo completo.")
    if not args.pre and not args.parity_only and args.pre_json is None:
        ap.error("--pre-json es obligatorio en el modo completo (seccion 14): "
                 "ejecuta antes --pre --out <pre.json> y pasa ese fichero aqui.")

    if args.parity_only:
        results, params, _ = load_league()
        if not results:
            out = {"modo": "parity-only", "resultado": "SIN RESULTADOS HISTORICOS."}
        else:
            rparams = resolved_params(params)
            tilt_scale = rparams.get("tilt_scale", 0.9)
            bonus = rparams.get("home_scoring_bonus", 0.0)
            max_goals = int(rparams.get("max_score", 15))
            df, df_all = build_rest_frame(results, params, WARMUP)
            assert_parity_base(results, params, df, df_all, tilt_scale, bonus, max_goals)
            assert_parity_treatment(results, params, df, df_all, tilt_scale, bonus,
                                    max_goals, PROBE_C)
            out = {"modo": "parity-only",
                  "resultado": (f"PARIDAD OK (n={len(df)}, n_all={len(df_all)}, "
                                f"c_prueba={PROBE_C}, lineas_spread={list(SPREAD_LINES)}, "
                                f"lineas_totals={list(TOTAL_LINES)})")}
        print(json.dumps(out, indent=2, ensure_ascii=False))
        if args.out:
            args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    if args.pre:
        out = {"modo": "pre (sin marcadores)", **informe_pre()}
        args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    # Modo completo. UNA SOLA EJECUCION (seccion 14). `--pre-json` es
    # obligatorio aqui (comprobado en el parseo de argumentos arriba).
    pre_data = json.loads(args.pre_json.read_text(encoding="utf-8"))
    results, params, procedencia = load_league()
    _check_pre_hash(pre_data, procedencia)
    out = {"procedencia": procedencia, LEAGUE: run_nhl(results, params)}
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
