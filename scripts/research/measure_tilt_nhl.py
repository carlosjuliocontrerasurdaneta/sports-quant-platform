"""Medicion del pre-registro de `tilt_scale` en la NHL (2026-09-29).

Ver `docs/research/2026-09-29-preregistro-tilt-nhl.md` (decisiones del operador
resueltas el 2026-09-30 al final del documento). Solo la NHL. Reutiliza el
adaptador y el motor de produccion (`get_adapter`, `PoissonAdapter._rates` via
las funciones ya vectorizadas y validadas por paridad de
`measure_rest_nhl.py`: `_lambda_split`, `home_win_vec`, `cover_vec`,
`over_vec`, `ll_per_game`, `fit`, `bootstrap_por_fecha`, `_safe_informe`,
`bias_of`, `sha256_of`, `FOLDS`, `NM_OPTS`) en vez de reimplementar formulas.
`tilt_scale` NO realimenta el Elo ni las tasas de anotacion (seccion 1.3 del
pre-registro): `diff_base`/`avg` de cada partido son los mismos para
CUALQUIER tilt, asi que basta un unico walk-forward de la base
(`measure_rest_nhl.diff_base_frame`) y cada brazo es una funcion analitica y
determinista de `(diff_base, avg, tilt_scale[, desplazamiento de nivel])`.

Tres modos:

  --pre            Recuentos y distribuciones de `p` SIN marcadores
                    (seccion 9), mas los escenarios KL/entropia de la seccion
                    9.2 (`escenarios_9_2`, t* en 0,7/0,6/0,5/0,4/0,3/0,2):
                    nunca lee home_score/away_score fuera de lo que el propio
                    `adapter.observe` consume para actualizar Elo/tasas.
                    Registra SHA-256 y filas de results_nhl.csv,
                    `git rev-parse HEAD` y `git status --porcelain -- src
                    configs scripts/research`.
  --parity-only    Construye el brazo base (tilt=0.9, el valor de familia
                    vigente) y comprueba la paridad con el motor canonico
                    `sqp.backtesting.engine.walk_forward_backtest` a 1e-12
                    (moneyline, puck line +-1,5 y totales 5,5/6,5). Repite la
                    comprobacion con un tilt de prueba PROBE_TILT=0,5 != 0,9
                    (seccion 5.3, aserto 3) y comprueba que `diff_base`/`avg`
                    del walk-forward son IDENTICOS con 0,9 y con 0,5
                    (seccion 1.3). NO estima ningun `tilt_scale`, no calcula
                    ninguna perdida y no evalua ningun criterio.
  (sin flags)      Medicion completa, UNA SOLA EJECUCION (seccion 15): ajusta
                    `t` (brazo T), `k` (brazo K), `(alpha, beta)` (brazo
                    Platt) y `(t2, a2)` (brazo T2, diagnostico) por
                    particion, evalua los 7 criterios de la seccion 7 (con
                    las decisiones del operador resueltas el 2026-09-30: el
                    criterio 3 es solo signo y el criterio 7 cuenta), el
                    bootstrap de la seccion 8 (incluida la fraccion de
                    replicas con T-K<0) y los doce informes secundarios de la
                    seccion 10 (sesgo completo de los cuatro brazos, AUC,
                    perfil de la rejilla, version ANALITICA de
                    `tuning.rolling_origin_improvement` con paridad puntual
                    en 2-3 valores en vez de recorrer toda la rejilla,
                    pendiente de calibracion, tabla de fiabilidad + Delta por
                    quintil de |diff|, Delta por temporada, puck line por
                    linea, totales, fraccion de la ganancia de Platt con IC
                    por bootstrap, linea capturada del mercado con calculo
                    propio y sensibilidad al redondeo de `t_C`), todos
                    protegidos con `_safe_informe`, y escribe el JSON de
                    salida. Antes de medir comprueba `git status --porcelain
                    -- src configs scripts/research` (aborta si no esta
                    vacio). `--pre-json <salida-de---pre>` es OBLIGATORIO:
                    aborta si falta, si al `--pre-json` o al fichero de
                    resultados leido ahora les falta el SHA-256 o el
                    `git rev-parse HEAD`, o si alguno de los dos difiere.

  python scripts/research/measure_tilt_nhl.py --parity-only --data-root <root>
  python scripts/research/measure_tilt_nhl.py --pre --out <json> --data-root <root>
  python scripts/research/measure_tilt_nhl.py --out <json> --pre-json <pre.json> --data-root <root>

`--data-root` (por defecto `sqp.config.ROOT`, es decir el arbol del que
proviene `src/`) es DELIBERADO: en un worktree de investigacion
`sqp.config.ROOT` apunta al propio worktree, que no tiene `data/` (nunca se
crean junctions de datos alli, ver CLAUDE.md). Pasar la raiz de datos de
produccion por parametro deja el codigo (`src/`, `configs/`) leido del
worktree que se esta revisando y los datos (`data/historical/`) leidos de
donde realmente viven, sin symlinks.

Este script NO puede reutilizar `measure_rest_nhl.load_league` tal cual
porque esa funcion tiene `sqp.config.ROOT` fijo (no parametrizable) y ademas
no conoce la invariante propia de este pre-registro (`tilt_scale == 0.9` en
la configuracion base); por eso `load_league` se redefine aqui, reutilizando
`ResultsStore`/`_league_meta`/`get_adapter`/`sha256_of` de produccion/precedente
en vez de reimplementarlos. El resto de utilidades sin dependencia de `ROOT`
(`diff_base_frame`, las vectorizadas, `fit`, `bootstrap_por_fecha`,
`_safe_informe`, `bias_of`, `FOLDS`, `NM_OPTS`) se importan directamente de
`measure_rest_nhl` (modulo hermano en `scripts/research/`).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # measure_rest_nhl.py: modulo hermano

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

import measure_rest_nhl as rmnhl  # reutiliza codigo validado, no lo copia
from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.tuning import (
    HOLDOUT_MIN_TRAIN_FRAC,
    IMPROVEMENT_MARGIN,
    rolling_origin_improvement,
)
from sqp.calibration.metrics import expected_calibration_error, reliability_table
from sqp.config import ROOT as DEFAULT_ROOT
from sqp.models import distributions as dist
from sqp.pipeline.daily import _league_meta
from sqp.sports.registry import get_adapter
from sqp.storage.results_store import ResultsStore

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]  # para git_head() y el docstring del CLI

LEAGUE = "nhl"
FAMILY = "hockey"
WARMUP = rmnhl.WARMUP                     # 60, el default del motor
NM_OPTS = rmnhl.NM_OPTS                   # xatol=1e-7, fatol=1e-10, maxiter=2000 (seccion 2)
N_BOOT, SEED = rmnhl.N_BOOT, rmnhl.SEED   # 10_000, 42 (seccion 8)
PROBE_TILT = 0.5                          # tilt de prueba != 0.9 (seccion 5.3, aserto 3)
SPREAD_LINES = rmnhl.SPREAD_LINES         # (-1.5, 1.5), la puck line que cotiza el mercado
TOTAL_LINES = rmnhl.TOTAL_LINES           # (5.5, 6.5), alrededor de avg_total 6.1
FOLDS = rmnhl.FOLDS                       # mismas particiones que descanso/portero NHL
GRID_TILT = tuple(float(x) for x in np.round(np.arange(0.0, 1.20 + 1e-9, 0.05), 2))  # secc. 6/10

# Funciones ya validadas por paridad en measure_rest_nhl.py (seccion 1.3 del
# pre-registro: "las mismas funciones vectorizadas... que ya reciben
# tilt_scale como argumento"). Se reutilizan por referencia, no se copian.
diff_base_frame = rmnhl.diff_base_frame
home_win_vec = rmnhl.home_win_vec
cover_vec = rmnhl.cover_vec
over_vec = rmnhl.over_vec
_lambda_split = rmnhl._lambda_split
ll_per_game = rmnhl.ll_per_game
fit = rmnhl.fit
bootstrap_por_fecha = rmnhl.bootstrap_por_fecha
_safe_informe = rmnhl._safe_informe
bias_of = rmnhl.bias_of
sha256_of = rmnhl.sha256_of
resolved_params = rmnhl.resolved_params


# ------------------------------------------------------------------ datos --
def load_league(data_root: Path) -> tuple[list[dict], dict, dict]:
    """Resultados, `league_params` resueltos y procedencia, con la raiz de
    datos parametrizada (ver docstring del modulo). Aborta si el mecanismo de
    descanso o el portero ya no estan apagados en la configuracion base
    (mismas dos comprobaciones que `measure_rest_nhl.load_league`, seccion 4
    del pre-registro del portero) o si `tilt_scale` resuelto ya no es 0,9
    (invariante propia de este documento, seccion 15: "aborta si tilt_scale
    != 0,9")."""
    results = ResultsStore(data_root).load(LEAGUE)
    params = dict(_league_meta(LEAGUE).get("league_params") or {})
    if params.get("rest_elo_per_day", 0.0) != 0.0:
        raise ValueError(
            "nhl: rest_elo_per_day ya no es 0.0 en configs/leagues/ratings.yaml -- "
            "el pre-registro del tilt asume el mecanismo de descanso APAGADO en la "
            "configuracion base. No decido reinterpretar la base: abortando.")
    if params.get("goalie_beta", 0.0) != 0.0:
        raise ValueError(
            "nhl: goalie_beta != 0.0 en configs/leagues/ratings.yaml y este "
            "documento no trae una enmienda que lo autorice. No decido "
            "reinterpretar la base: abortando.")
    rparams = get_adapter(LEAGUE, FAMILY, params).params
    if rparams.get("tilt_scale", 0.9) != 0.9:
        raise ValueError(
            f"nhl: tilt_scale resuelto es {rparams.get('tilt_scale')!r}, no 0.9 -- "
            "el pre-registro asume el valor de familia (0.9), nunca ajustado para "
            "la NHL, como base. No decido reinterpretar la base: abortando.")
    path = ResultsStore(data_root).path(LEAGUE)
    procedencia = {"fichero": str(path), "filas": len(results)}
    if path.exists():
        procedencia["sha256"] = sha256_of(path)
    return results, params, procedencia


def git_head(cwd: Path) -> str | None:
    """`git rev-parse HEAD` del arbol que se esta midiendo (seccion 15: el
    `--pre` lo registra y el modo completo aborta si difiere). `None` si git
    no esta disponible o el directorio no es un repositorio -- se deja
    constancia en la salida en vez de fallar en silencio."""
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(cwd),
                             capture_output=True, text=True, check=True, timeout=30)
        return res.stdout.strip()
    except Exception:  # noqa: BLE001 -- procedencia informativa, no decide nada
        return None


_GIT_STATUS_PATHS = ("src", "configs", "scripts/research")


def git_status_porcelain(cwd: Path, paths: tuple[str, ...] = _GIT_STATUS_PATHS) -> str | None:
    """`git status --porcelain -- src configs scripts/research` del arbol que
    se esta midiendo (punto 6 de la revision de Fable): el `--pre` lo
    registra como procedencia y el modo completo aborta si no esta vacio
    (`_check_git_clean`) -- ademas del HEAD, que ya comprueba
    `_check_pre_provenance`. `None` si git no esta disponible o el directorio
    no es un repositorio."""
    try:
        res = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=str(cwd),
                             capture_output=True, text=True, check=True, timeout=30)
        return res.stdout
    except Exception:  # noqa: BLE001 -- procedencia informativa, no decide nada
        return None


def _check_git_clean(status: str | None) -> None:
    """Aborta el modo completo si `git status --porcelain -- src configs
    scripts/research` no esta vacio, o si no se pudo obtener (punto 6 de la
    revision de Fable): no se mide con codigo o configuracion sin commitear
    en esas rutas."""
    if status is None:
        raise SystemExit(
            "No se pudo obtener 'git status --porcelain -- src configs "
            "scripts/research' ahora. El modo completo aborta: no se puede "
            "verificar que el arbol este limpio en esas rutas.")
    if status.strip() != "":
        raise SystemExit(
            "git status --porcelain -- src configs scripts/research NO esta "
            f"vacio:\n{status}\nEl modo completo aborta: no se mide con cambios "
            "sin commitear en esas rutas.")


# ------------------------------------------------------- escenarios (seccion 9.2) --
TSTAR_9_2 = (0.7, 0.6, 0.5, 0.4, 0.3, 0.2)  # los mismos t* de la tabla del pre-registro


def _kl_bernoulli(p: np.ndarray, q: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """KL(Bernoulli(p) || Bernoulli(q)) por partido, logaritmo natural (la
    misma base que `ll_per_game`/log loss). Seccion 9.2 del pre-registro."""
    p = np.clip(p, eps, 1.0 - eps)
    q = np.clip(q, eps, 1.0 - eps)
    return p * np.log(p / q) + (1.0 - p) * np.log((1.0 - p) / (1.0 - q))


def _entropy_bernoulli(p: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    p = np.clip(p, eps, 1.0 - eps)
    return -(p * np.log(p) + (1.0 - p) * np.log(1.0 - p))


def _var_delta_bernoulli(p_true: np.ndarray, p_base: np.ndarray,
                         eps: float = 1e-12) -> np.ndarray:
    """Varianza analitica, bajo `Y ~ Bernoulli(p_true)`, de
    `D = ll(p_base, Y) - ll(p_true, Y)` (la ganancia de log loss de ESE
    partido si la verdad fuera `p_true`). `D` es una variable de dos puntos
    (`Y in {0,1}`), asi que su varianza tiene forma cerrada:
    `p_true*(1-p_true)*(D(1)-D(0))^2`, sin necesitar simulacion. Es el
    ingrediente de la seccion 9.2: `E[D] = KL(p_true || p_base)` (identidad
    estandar de log loss esperado), y sumar estas varianzas POR PARTIDO SIN
    AGRUPAR (partidos independientes, a diferencia del bootstrap por dias de
    la seccion 8) da el error estandar de la ganancia media."""
    p_true = np.clip(p_true, eps, 1.0 - eps)
    p_base = np.clip(p_base, eps, 1.0 - eps)
    d1 = np.log(p_true) - np.log(p_base)                    # D(Y=1)
    d0 = np.log(1.0 - p_true) - np.log(1.0 - p_base)        # D(Y=0)
    return p_true * (1.0 - p_true) * (d1 - d0) ** 2


def escenarios_9_2(diff: np.ndarray, avg: np.ndarray, bonus: float, max_goals: int,
                   tstars: tuple[float, ...] = TSTAR_9_2,
                   tilt_base: float = 0.9) -> dict[str, dict[str, float | None]]:
    """Seccion 9.2: para cada t* supuesto "verdadero", la ganancia esperada de
    pasar de `tilt_base` a t* (`E[KL(p_t* || p_tilt_base)]`), su error
    estandar POR PARTIDO SIN AGRUPAR (la seccion 9.2 aclara que NO es el
    bootstrap por dias de la seccion 8: es la raiz de la varianza MEDIA de
    `D_i` -- seccion `_var_delta_bernoulli` -- entre `n`, es decir la SE
    analitica de la ganancia media si `Y` se generara con `p_t*`, NO la
    dispersion empirica de `KL_i` entre partidos) y la ventaja sobre la
    constante (`H(E p_t*) - E[H(p_t*)]`). Nunca lee `y`: son escenarios bajo
    un modelo supuesto, calculados solo sobre `(diff, avg)` del test
    combinado, exactamente como exige `--pre`."""
    n = len(diff)
    p_base = home_win_vec(diff, avg, tilt_base, bonus, max_goals)
    out: dict[str, dict[str, float | None]] = {}
    for t in tstars:
        p_t = home_win_vec(diff, avg, t, bonus, max_goals)
        kl = _kl_bernoulli(p_t, p_base)
        var_delta = _var_delta_bernoulli(p_t, p_base)
        ee = float(np.sqrt(np.mean(var_delta) / n)) if n else None
        ventaja = float(_entropy_bernoulli(np.array([np.mean(p_t)]))[0]
                        - np.mean(_entropy_bernoulli(p_t))) if n else None
        out[str(t)] = {
            "ganancia_esperada_vs_base": float(np.mean(kl)) if n else None,
            "ee_delta": ee,
            "ventaja_sobre_constante": ventaja,
        }
    return out


# ---------------------------------------------------- calendario (sin marcadores) --
def game_calendar(results: list[dict], warmup: int = WARMUP) -> pd.DataFrame:
    """`idx`/`date`/`home`/`away`/`game_id`/`neutral` en el orden y warmup del
    motor, SIN tocar marcadores (analogo a la primera mitad de
    `measure_rest_nhl.rest_calendar`, pero sin `RestModel`: el tilt no
    necesita dias de descanso, solo la fecha para particionar)."""
    ordered = sorted(results, key=lambda row: str(row.get("date", "")))
    rows: list[dict] = []
    for i, r in enumerate(ordered):
        if i >= warmup:
            rows.append({"idx": i, "game_id": str(r.get("game_id", "")),
                        "date": str(r.get("date", ""))[:10],
                        "home": r["home"], "away": r["away"],
                        "neutral": bool(r.get("neutral", False))})
    return pd.DataFrame(rows)


def build_tilt_frame(results: list[dict], params: dict,
                     warmup: int = WARMUP) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Une `diff_base_frame` (produccion, con marcadores) y el calendario
    (sin marcadores) por `idx`, igual que `measure_rest_nhl.build_rest_frame`.

    Devuelve DOS vistas, por la misma razon que el descanso NHL: `binary_probs`
    excluye empates y `markets['spreads@L'|'totals@L']` no los excluye.

    - `df`: excluye empates (y==0.5) -- vista del moneyline.
    - `df_all`: TODAS las filas con i>=warmup, incluidos los empates -- vista
      de la puck line y los totales (seccion 4: "todas las filas tras el
      warmup"; decision del operador: los empates SI entran en `spreads@L`).
    """
    mb = diff_base_frame(results, params, warmup)
    cal = game_calendar(results, warmup)
    merged = mb.merge(cal, on="idx", how="inner", validate="one_to_one")
    merged = merged.sort_values("idx", kind="stable").reset_index(drop=True)
    df_all = merged
    df = merged[merged["y"].isin([0.0, 1.0])].reset_index(drop=True)
    return df, df_all


def diff_avg_for_pre(results: list[dict], params: dict,
                     warmup: int = WARMUP) -> pd.DataFrame:
    """`diff_base`/`avg` por partido para `--pre`. Reutiliza literalmente las
    dos lineas de `PoissonAdapter._rates` anteriores al tilt
    (`adapter.elo.rating_diff` + `adapter.scoring.expected_total`, las mismas
    que `measure_rest_nhl.diff_base_frame`), pero a diferencia de esa funcion
    el frame devuelto NUNCA incluye `y`/`margin`/`total` (ni ninguna magnitud
    derivada del resultado): la unica lectura de marcadores en esta ruta es
    la que hace `adapter.observe(row)` para actualizar Elo/tasas, identica a
    produccion (seccion 15: "--pre ... nunca lee y, salvo lo que consume el
    propio observe"). No se puede llamar a `diff_base_frame` aqui porque esa
    funcion SI calcula y devuelve `y`/`margin`/`total` a partir del marcador.
    """
    adapter = get_adapter(LEAGUE, FAMILY, params)
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
            rows.append({"idx": i, "date": date[:10], "diff_base": float(diff),
                        "avg": float(avg)})
        pending.append(r)
    return pd.DataFrame(rows)


# ------------------------------------------------------------- brazos (fit) --
def _logit(p: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    p = np.clip(p, eps, 1.0 - eps)
    return np.log(p / (1.0 - p))


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def fit_t(diff_tr: np.ndarray, avg_tr: np.ndarray, y_tr: np.ndarray,
         bonus: float, max_goals: int) -> float:
    """Brazo T: un solo `tilt_scale`, Nelder-Mead desde 0,9 (seccion 2)."""
    def obj(x: np.ndarray) -> float:
        p = home_win_vec(diff_tr, avg_tr, float(x[0]), bonus, max_goals)
        return float(np.mean(ll_per_game(p, y_tr)))
    return float(fit(obj, [0.9], "t")[0])


def fit_t2(diff_tr: np.ndarray, avg_tr: np.ndarray, y_tr: np.ndarray,
          bonus: float, max_goals: int) -> tuple[float, float]:
    """Brazo T2 (diagnostico, seccion 5.1): tilt + desplazamiento de nivel
    `a` (puntos Elo, sin realimentar), partida (0,9, 0)."""
    def obj(x: np.ndarray) -> float:
        p = home_win_vec(diff_tr + x[1], avg_tr, float(x[0]), bonus, max_goals)
        return float(np.mean(ll_per_game(p, y_tr)))
    x = fit(obj, [0.9, 0.0], "t2 (tilt+nivel)")
    return float(x[0]), float(x[1])


def fit_platt(p_base_tr: np.ndarray, y_tr: np.ndarray) -> tuple[float, float]:
    """Brazo P (referencia de techo, no decide): sigma(alpha + beta*logit(p_base)),
    partida (0, 1) (seccion 5.1)."""
    logit_p = _logit(p_base_tr)
    def obj(x: np.ndarray) -> float:
        p = _sigmoid(x[0] + x[1] * logit_p)
        return float(np.mean(ll_per_game(p, y_tr)))
    x = fit(obj, [0.0, 1.0], "platt")
    return float(x[0]), float(x[1])


def _pendiente_calibracion(p: np.ndarray, y: np.ndarray) -> float | None:
    """Informe 5 (seccion 10.5): pendiente de la regresion logistica de `y`
    sobre `logit(p)` (regresion logistica de un solo predictor, sin termino
    cuadratico ni interaccion). `None` si `y` no tiene las dos clases (la
    regresion no esta definida)."""
    if len(np.unique(y)) < 2:
        return None
    x = _logit(p).reshape(-1, 1)
    clf = LogisticRegression(fit_intercept=True)
    clf.fit(x, y)
    return float(clf.coef_[0][0])


# ------------------------------------------------------------------ paridad --
def assert_parity(results: list[dict], params: dict, df: pd.DataFrame,
                  df_all: pd.DataFrame, tilt_scale: float, bonus: float,
                  max_goals: int, warmup: int = WARMUP, atol: float = 1e-12,
                  label: str = "") -> None:
    """Seccion 5.3: el brazo con `tilt_scale` coincide con el motor
    `walk_forward_backtest` ejecutado con `params["tilt_scale"] = tilt_scale`
    (moneyline y los cuatro mercados), en la cadena FAMILY_PARAMS ->
    LEAGUE_OVERRIDES -> league_params, igual que produccion. Con
    `tilt_scale` = el valor de familia vigente (0,9) esto ES el aserto 1
    (brazo base); con cualquier otro valor es el aserto 2 (brazo de
    tratamiento). Aborta con SystemExit si algo no cuadra."""
    ref = walk_forward_backtest(results, LEAGUE, FAMILY, {**params, "tilt_scale": tilt_scale},
                                warmup=warmup, spread_lines=SPREAD_LINES, total_lines=TOTAL_LINES)
    mine_p = home_win_vec(df["diff_base"].to_numpy(), df["avg"].to_numpy(),
                          tilt_scale, bonus, max_goals)
    mine_y = df["y"].to_numpy()
    theirs_p = np.asarray(ref["binary_probs"], dtype=float)
    theirs_y = np.asarray(ref["binary_outcomes"], dtype=float)
    if len(mine_p) != len(theirs_p) or not np.allclose(mine_p, theirs_p, rtol=0, atol=atol):
        raise SystemExit(f"PARIDAD ROTA (moneyline, tilt={tilt_scale} {label}): no se mide nada.")
    if not np.array_equal(mine_y, theirs_y):
        raise SystemExit(f"RESULTADOS DESALINEADOS (moneyline, tilt={tilt_scale} {label}).")

    # Cruce con la formula escalar de produccion (dist.poisson_match_probs),
    # en una muestra, para no depender solo del vector vectorizado.
    sample = df.head(200)
    for _, row in sample.iterrows():
        lam_h, lam_a = _lambda_split(np.array([row["diff_base"]]), np.array([row["avg"]]),
                                     tilt_scale, bonus)
        scalar = dist.poisson_match_probs(float(lam_h[0]), float(lam_a[0]), None, None,
                                          max_goals=max_goals)["home_win"]
        vec = home_win_vec(np.array([row["diff_base"]]), np.array([row["avg"]]),
                           tilt_scale, bonus, max_goals)[0]
        if not np.isclose(scalar, vec, rtol=0, atol=atol):
            raise SystemExit(f"PARIDAD ROTA (formula escalar, tilt={tilt_scale} {label}).")

    diff = df_all["diff_base"].to_numpy()
    avg = df_all["avg"].to_numpy()
    margin = df_all["margin"].to_numpy()
    total = df_all["total"].to_numpy()
    for line in SPREAD_LINES:
        key = f"spreads@{line}"
        mkt = ref["markets"].get(key)
        if mkt is None:
            raise SystemExit(f"PARIDAD ROTA (spreads) tilt={tilt_scale} {label}: "
                             f"el motor no devolvio '{key}'.")
        mine_p_s = cover_vec(diff, avg, tilt_scale, bonus, max_goals, line)
        push = margin == -line  # nunca ocurre con una linea de medio punto
        mine_p_s, mine_y_s = mine_p_s[~push], (margin[~push] > -line).astype(float)
        theirs_p_s = np.asarray(mkt["probs"], dtype=float)
        theirs_y_s = np.asarray(mkt["outcomes"], dtype=float)
        if (len(mine_p_s) != len(theirs_p_s)
                or not np.allclose(mine_p_s, theirs_p_s, rtol=0, atol=atol)):
            raise SystemExit(f"PARIDAD ROTA (spreads probs) tilt={tilt_scale} linea {line} {label}.")
        if len(mine_y_s) != len(theirs_y_s) or not np.array_equal(mine_y_s, theirs_y_s):
            raise SystemExit(f"PARIDAD ROTA (spreads outcomes) tilt={tilt_scale} linea {line} {label}.")
    for line in TOTAL_LINES:
        key = f"totals@{line}"
        mkt = ref["markets"].get(key)
        if mkt is None:
            raise SystemExit(f"PARIDAD ROTA (totals) tilt={tilt_scale} {label}: "
                             f"el motor no devolvio '{key}'.")
        mine_p_t = over_vec(diff, avg, tilt_scale, bonus, max_goals, line)
        push = total == line  # nunca ocurre con una linea de medio punto
        mine_p_t, mine_y_t = mine_p_t[~push], (total[~push] > line).astype(float)
        theirs_p_t = np.asarray(mkt["probs"], dtype=float)
        theirs_y_t = np.asarray(mkt["outcomes"], dtype=float)
        if (len(mine_p_t) != len(theirs_p_t)
                or not np.allclose(mine_p_t, theirs_p_t, rtol=0, atol=atol)):
            raise SystemExit(f"PARIDAD ROTA (totals probs) tilt={tilt_scale} linea {line} {label}.")
        if len(mine_y_t) != len(theirs_y_t) or not np.array_equal(mine_y_t, theirs_y_t):
            raise SystemExit(f"PARIDAD ROTA (totals outcomes) tilt={tilt_scale} linea {line} {label}.")


def assert_diff_avg_tilt_invariant(results: list[dict], params: dict,
                                   warmup: int = WARMUP) -> None:
    """Seccion 1.3 y 5.3 (aserto 3): `diff_base`/`avg` NO dependen de
    `tilt_scale` -- se construye el frame dos veces, con `params` sin tocar
    (familia, 0,9) y con `tilt_scale` sobrescrito a `PROBE_TILT`, y se exige
    IGUALDAD EXACTA (no solo proxima) de las dos columnas."""
    _, df_all_0 = build_tilt_frame(results, params, warmup)
    _, df_all_probe = build_tilt_frame(results, {**params, "tilt_scale": PROBE_TILT}, warmup)
    if not np.array_equal(df_all_0["diff_base"].to_numpy(), df_all_probe["diff_base"].to_numpy()):
        raise SystemExit(
            "PARIDAD ROTA (seccion 1.3): diff_base cambia con tilt_scale -- "
            "el tilt esta realimentando el Elo, contra la propiedad clave del "
            "pre-registro. No se mide nada.")
    if not np.array_equal(df_all_0["avg"].to_numpy(), df_all_probe["avg"].to_numpy()):
        raise SystemExit(
            "PARIDAD ROTA (seccion 1.3): avg cambia con tilt_scale -- "
            "el tilt esta realimentando las tasas de anotacion. No se mide nada.")


# -------------------------------------------------------------------- --pre --
def informe_pre(data_root: Path) -> dict:
    results, params, procedencia = load_league(data_root)
    if not results:
        return {"liga": LEAGUE, **procedencia, "aviso": "sin resultados historicos"}
    rparams = resolved_params(params)
    bonus = float(rparams.get("home_scoring_bonus", 0.0))
    max_goals = int(rparams.get("max_score", 15))

    cal = diff_avg_for_pre(results, params, WARMUP)

    particiones = {}
    for name, foldd in FOLDS.items():
        train = cal[cal["date"] <= foldd["train_end"]]
        test = cal[(cal["date"] >= foldd["test_start"]) & (cal["date"] <= foldd["test_end"])]
        particiones[name] = {
            "n_train": int(len(train)), "n_test": int(len(test)),
            "n_dias_test": int(test["date"].nunique()),
            # No distingue empates (requeriria leer el marcador): son las
            # filas TOTALES tras el warmup en la ventana, no el "n moneyline"
            # de la seccion 6 del documento (esa distincion exige y).
        }

    tilts_dispersión = [0.9, 0.7, 0.5, 0.4, 0.3, 0.0]
    dispersión: dict[str, dict[str, dict[str, float | None]]] = {}
    partes = []
    for name, foldd in FOLDS.items():
        test = cal[(cal["date"] >= foldd["test_start"]) & (cal["date"] <= foldd["test_end"])]
        partes.append(test)
        fila: dict[str, dict[str, float | None]] = {}
        for t in tilts_dispersión:
            p = home_win_vec(test["diff_base"].to_numpy(), test["avg"].to_numpy(),
                             t, bonus, max_goals)
            # Guarda contra particion de test vacia (fuera del rango de fechas
            # del historico leido): sin esta guarda, `np.quantile` de un
            # array vacio lanza IndexError en vez de reportar `None` -- el
            # mismo defecto que ya se evitaba abajo para el combinado.
            fila[str(t)] = {"media": float(np.mean(p)) if len(p) else None,
                            "dt": float(np.std(p, ddof=0)) if len(p) else None,
                            "p5": float(np.quantile(p, 0.05)) if len(p) else None,
                            "p95": float(np.quantile(p, 0.95)) if len(p) else None}
        dispersión[name] = fila
    combinado = pd.concat(partes) if partes else cal.iloc[0:0]
    fila_comb: dict[str, dict[str, float | None]] = {}
    for t in tilts_dispersión:
        p = home_win_vec(combinado["diff_base"].to_numpy(), combinado["avg"].to_numpy(),
                         t, bonus, max_goals)
        fila_comb[str(t)] = {"media": float(np.mean(p)) if len(p) else None,
                             "dt": float(np.std(p, ddof=0)) if len(p) else None,
                             "p5": float(np.quantile(p, 0.05)) if len(p) else None,
                             "p95": float(np.quantile(p, 0.95)) if len(p) else None}
    dispersión["combinado"] = fila_comb

    # Seccion 9.2: escenarios KL/entropia sobre el test combinado (`combinado`,
    # ya construido arriba para la tabla de dispersion), para los mismos t* de
    # la tabla del pre-registro. Tampoco lee `y`.
    escenarios = (escenarios_9_2(combinado["diff_base"].to_numpy(),
                                 combinado["avg"].to_numpy(), bonus, max_goals)
                 if len(combinado) else {})

    return {
        "liga": LEAGUE, **procedencia,
        "git_head": git_head(_WORKTREE_ROOT),
        "git_status_porcelain": git_status_porcelain(_WORKTREE_ROOT),
        "parametros_resueltos": {k: rparams.get(k) for k in
                                 ("avg_total", "tilt_scale", "max_score",
                                  "home_scoring_bonus", "elo_k", "elo_home_adv",
                                  "rest_elo_per_day", "goalie_beta")},
        "partidos_totales": int(len(results)),
        "evaluados_tras_warmup": int(len(cal)),
        "particiones": particiones,
        "dispersion_p_por_tilt_moneyline": dispersión,
        "aviso_dispersion": (
            "Incluye TODAS las filas tras el warmup en la ventana de cada test "
            "(tambien los empates historicos pre-2005): --pre no lee y, asi que "
            "no puede excluirlos como hace binary_probs en el modo completo. "
            "No se ha calculado ninguna perdida ni se ha comparado con ningun "
            "resultado (seccion 9)."),
        "escenarios_9_2": escenarios,
        "aviso_escenarios_9_2": (
            "Ganancia esperada E[KL(p_t* || p_0,9)], error estandar POR "
            "PARTIDO SIN AGRUPAR como sqrt(mean_i Var(D_i | p_t*) / n) -- trata "
            "cada partido como fijo; NO es std/sqrt(n) ni el bootstrap por dias "
            "de la seccion 8 -- y ventaja sobre la constante H(E p_t*) - "
            "E[H(p_t*)], sobre el test combinado. Diferencia con la tabla de la "
            "seccion 9.2 (hasta ~7-8% en el EE): la tabla sumaba la dispersion "
            "entre partidos de la ganancia, sqrt((mean Var_i + var KL_i)/n), y "
            "los datos crecieron (32.902 -> 32.907 filas). NO se debe a empates: "
            "los tests empiezan en 2014 y n coincide (16.950). Informativo, no "
            "decide."),
    }


def _bootstrap_ratio_por_fecha(dates: np.ndarray, num: np.ndarray, den: np.ndarray) -> dict:
    """Bootstrap por dias UTC (mismo remuestreo que `bootstrap_por_fecha`,
    seccion 8: 10.000 replicas, semilla 42) del cociente
    `mean(num)/mean(den)` -- informe 10 (seccion 10.10, punto 5 de la
    revision de Fable): fraccion de la ganancia de Platt que captura T, con
    su IC95 percentil y error estandar. Replicas con denominador 0 (dia sin
    variacion de `ll_base - ll_platt`) se descartan del IC, no se propagan
    como `inf`/`nan`."""
    u, inv = np.unique(dates, return_inverse=True)
    num_sums = np.bincount(inv, weights=num)
    den_sums = np.bincount(inv, weights=den)
    rng = np.random.default_rng(SEED)
    pick = rng.integers(0, len(u), size=(N_BOOT, len(u)))
    num_tot = num_sums[pick].sum(axis=1)
    den_tot = den_sums[pick].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        reps = num_tot / den_tot
    reps = reps[np.isfinite(reps)]
    if len(reps) == 0:
        return {"n_dias": int(len(u)), "ic95": [None, None], "se": None}
    return {"n_dias": int(len(u)),
           "ic95": [float(np.quantile(reps, 0.025)), float(np.quantile(reps, 0.975))],
           "se": float(np.std(reps, ddof=1))}


captured_lines = rmnhl.captured_lines  # reutilizado por referencia (informe 11), no reimplementado


def informe_linea_capturada(results: list[dict], test_all_mny: pd.DataFrame, fold_c: dict,
                            bonus: float, max_goals: int, tilt0: float, t_c: float) -> dict | None:
    """Informe secundario 11 (seccion 10.11): linea capturada del mercado
    (h2h y puck line), restringido al test de la particion C (misma ventana
    que `t_c`). CALCULO PROPIO: no reutiliza
    `measure_rest_nhl._informe_linea_capturada`, que documentadamente carece
    de `float(lam[0])` (seccion 10.11 del pre-registro); aqui cada lambda
    escalar se envuelve explicitamente en `float()` antes de pasarla a
    `dist.poisson_match_probs` (punto 5 de la revision de Fable)."""
    cap = captured_lines(results)
    matched_ids = cap["game_ids_emparejados"]
    if not matched_ids:
        return None
    cte = test_all_mny[(test_all_mny["date"] >= fold_c["test_start"])
                       & (test_all_mny["date"] <= fold_c["test_end"])
                       & (test_all_mny["game_id"].isin(matched_ids))].copy()
    informe: dict = {
        "n_h2h": int(len(cte)),
        "delta_ll_h2h": None,
        "n_spread_con_linea": 0,
        "ficheros_odds_sha256": cap["ficheros_sha256"],
    }
    if cte.empty:
        return informe
    diff_c = cte["diff_base"].to_numpy()
    avg_c = cte["avg"].to_numpy()
    y_c = cte["y"].to_numpy()
    ll_base_h2h = ll_per_game(home_win_vec(diff_c, avg_c, tilt0, bonus, max_goals), y_c)
    ll_treat_h2h = ll_per_game(home_win_vec(diff_c, avg_c, t_c, bonus, max_goals), y_c)
    informe["delta_ll_h2h"] = float(np.mean(ll_treat_h2h - ll_base_h2h))

    cte["mkt_line"] = cte["game_id"].map(cap["spreads"])
    m = cte[cte["mkt_line"].notna()]
    informe["n_spread_con_linea"] = int(len(m))
    if len(m):
        diff_m = m["diff_base"].to_numpy()
        avg_m = m["avg"].to_numpy()
        lines = m["mkt_line"].to_numpy(dtype=float)
        margin_m = m["margin"].to_numpy()
        push = margin_m == -lines
        p_b = np.empty(len(m))
        p_t = np.empty(len(m))
        for i, (d, a, ln) in enumerate(zip(diff_m, avg_m, lines)):
            lam_h_b, lam_a_b = _lambda_split(np.array([d]), np.array([a]), tilt0, bonus)
            p_b[i] = dist.poisson_match_probs(float(lam_h_b[0]), float(lam_a_b[0]), ln, None,
                                              max_goals=max_goals)["home_cover"]
            lam_h_t, lam_a_t = _lambda_split(np.array([d]), np.array([a]), t_c, bonus)
            p_t[i] = dist.poisson_match_probs(float(lam_h_t[0]), float(lam_a_t[0]), ln, None,
                                              max_goals=max_goals)["home_cover"]
        covered = (margin_m > -lines).astype(float)
        ll_b = ll_per_game(p_b[~push], covered[~push])
        ll_t = ll_per_game(p_t[~push], covered[~push])
        informe["delta_ll_spread"] = float(np.mean(ll_t - ll_b)) if (~push).any() else None
        informe["n_spread_evaluado"] = int((~push).sum())
    return informe


# ------------------------------------------------------------- modo completo --
def run_nhl(results: list[dict], params: dict) -> dict:
    rparams = resolved_params(params)
    tilt0 = float(rparams.get("tilt_scale", 0.9))
    bonus = float(rparams.get("home_scoring_bonus", 0.0))
    max_goals = int(rparams.get("max_score", 15))

    df, df_all = build_tilt_frame(results, params, WARMUP)
    assert_parity(results, params, df, df_all, tilt0, bonus, max_goals, label="base")

    out: dict = {"n_total": int(len(df)), "folds": {}}
    t_by_fold: dict[str, float] = {}
    k_by_fold: dict[str, float] = {}
    t2_by_fold: dict[str, float] = {}
    a2_by_fold: dict[str, float] = {}
    grid = GRID_TILT

    pieces_mny, pieces_all = [], []
    puck_diffs_all: list[np.ndarray] = []
    puck_dates_all: list[np.ndarray] = []
    puck_line_pieces: dict[float, list[dict]] = {line: [] for line in SPREAD_LINES}

    for name, foldd in FOLDS.items():
        train = df[df["date"] <= foldd["train_end"]]
        test = df[(df["date"] >= foldd["test_start"]) & (df["date"] <= foldd["test_end"])].copy()
        test_all = df_all[(df_all["date"] >= foldd["test_start"])
                          & (df_all["date"] <= foldd["test_end"])].copy()
        diff_tr = train["diff_base"].to_numpy()
        avg_tr = train["avg"].to_numpy()
        y_tr = train["y"].to_numpy()

        t = fit_t(diff_tr, avg_tr, y_tr, bonus, max_goals)
        k = float(np.mean(y_tr))
        p_base_tr = home_win_vec(diff_tr, avg_tr, tilt0, bonus, max_goals)
        alpha, beta = fit_platt(p_base_tr, y_tr)
        t2, a2 = fit_t2(diff_tr, avg_tr, y_tr, bonus, max_goals)
        t_by_fold[name], k_by_fold[name] = t, k
        t2_by_fold[name], a2_by_fold[name] = t2, a2

        diff_te = test["diff_base"].to_numpy()
        avg_te = test["avg"].to_numpy()
        y_te = test["y"].to_numpy()
        p_base = home_win_vec(diff_te, avg_te, tilt0, bonus, max_goals)
        p_treat = home_win_vec(diff_te, avg_te, t, bonus, max_goals)
        p_const = np.full_like(y_te, k)
        p_platt = _sigmoid(alpha + beta * _logit(p_base))
        p_t2 = home_win_vec(diff_te + a2, avg_te, t2, bonus, max_goals)

        test["ll_base"] = ll_per_game(p_base, y_te)
        test["ll_treat"] = ll_per_game(p_treat, y_te)
        test["ll_const"] = ll_per_game(p_const, y_te)
        test["ll_platt"] = ll_per_game(p_platt, y_te)
        test["ll_t2"] = ll_per_game(p_t2, y_te)
        test["p_base"], test["p_treat"] = p_base, p_treat
        test["p_platt"], test["p_t2"] = p_platt, p_t2

        auc_base = auc_treat = None
        try:
            if len(np.unique(y_te)) > 1:
                auc_base = float(roc_auc_score(y_te, p_base))
                auc_treat = float(roc_auc_score(y_te, p_treat))
        except Exception:  # noqa: BLE001 -- informe 2, no decide
            pass

        perfil = [{"t": float(tt), "log_loss_train": float(np.mean(ll_per_game(
            home_win_vec(diff_tr, avg_tr, tt, bonus, max_goals), y_tr)))}
                 for tt in grid]

        diff_te_all = test_all["diff_base"].to_numpy()
        avg_te_all = test_all["avg"].to_numpy()
        margin_all = test_all["margin"].to_numpy()
        dates_te_all = test_all["date"].to_numpy()
        spreads_delta = {}
        for line in SPREAD_LINES:
            p_b = cover_vec(diff_te_all, avg_te_all, tilt0, bonus, max_goals, line)
            p_t = cover_vec(diff_te_all, avg_te_all, t, bonus, max_goals, line)
            covered = (margin_all > -line).astype(float)
            push = margin_all == -line
            ll_b = ll_per_game(p_b[~push], covered[~push])
            ll_t = ll_per_game(p_t[~push], covered[~push])
            diff_line = ll_t - ll_b
            spreads_delta[str(line)] = float(diff_line.mean()) if (~push).any() else None
            if (~push).any():
                puck_diffs_all.append(diff_line)
                puck_dates_all.append(dates_te_all[~push])
                puck_line_pieces[line].append({
                    "p_base": p_b[~push], "p_treat": p_t[~push], "y": covered[~push]})

        out["folds"][name] = {
            "train_end": foldd["train_end"], "test": [foldd["test_start"], foldd["test_end"]],
            "n_train": int(len(train)), "n_test": int(len(test)),
            "t": t, "k": k, "platt_alpha": alpha, "platt_beta": beta,
            "t2": t2, "a2_elo": a2,
            # Informe 1 completo (seccion 10.1): sesgo de los CUATRO brazos
            # (base, T, T2, P), no solo base/T -- por particion y, mas abajo,
            # en el combinado (`c_comb`).
            "bias_base_test": bias_of(p_base, y_te),
            "bias_treat_test": bias_of(p_treat, y_te),
            "bias_t2_test": bias_of(p_t2, y_te),
            "bias_platt_test": bias_of(p_platt, y_te),
            "delta_ll_universo": float((test["ll_treat"] - test["ll_base"]).mean()),
            "ll_treat": float(test["ll_treat"].mean()),
            "ll_const": float(test["ll_const"].mean()),
            "ll_platt": float(test["ll_platt"].mean()),
            "ll_t2": float(test["ll_t2"].mean()),  # solo informativo: el criterio 7 mira t2, no esto
            "auc_base": auc_base, "auc_treat": auc_treat,
            "perfil_log_loss_train_grid": perfil,
            "delta_ll_puck_line": spreads_delta,
        }
        pieces_mny.append(test)
        pieces_all.append(test_all)

    assert_parity(results, params, df, df_all, t_by_fold["C"], bonus, max_goals, label="tratamiento C")

    test_all_mny = pd.concat(pieces_mny).reset_index(drop=True)
    test_all_full = pd.concat(pieces_all).reset_index(drop=True)

    diff_universo = (test_all_mny["ll_treat"] - test_all_mny["ll_base"]).to_numpy()
    diff_tk = (test_all_mny["ll_treat"] - test_all_mny["ll_const"]).to_numpy()
    diff_tp = (test_all_mny["ll_treat"] - test_all_mny["ll_platt"]).to_numpy()
    dates_mny = test_all_mny["date"].to_numpy()

    out["combinado"] = {
        "n_test": int(len(test_all_mny)),
        "delta_ll_universo": float(diff_universo.mean()),
        "bootstrap_delta_universo": bootstrap_por_fecha(dates_mny, diff_universo,
                                                        margen=IMPROVEMENT_MARGIN),
        # `margen=0.0`: ademas del IC95/EE, registra `prob_supera_margen` =
        # fraccion de replicas con T - K <= 0 (punto 4 de la revision de
        # Fable: "la fraccion de replicas con T - K < 0").
        "bootstrap_trat_vs_const": bootstrap_por_fecha(dates_mny, diff_tk, margen=0.0),
        "bootstrap_trat_vs_platt": bootstrap_por_fecha(dates_mny, diff_tp),
        "ece_base": float(expected_calibration_error(test_all_mny["p_base"].tolist(),
                                                      test_all_mny["y"].tolist())),
        "ece_trat": float(expected_calibration_error(test_all_mny["p_treat"].tolist(),
                                                      test_all_mny["y"].tolist())),
        "ll_base": float(test_all_mny["ll_base"].mean()),
        "ll_treat": float(test_all_mny["ll_treat"].mean()),
        "ll_const": float(test_all_mny["ll_const"].mean()),
        "ll_platt": float(test_all_mny["ll_platt"].mean()),
        "bias_base": bias_of(test_all_mny["p_base"].to_numpy(), test_all_mny["y"].to_numpy()),
        "bias_treat": bias_of(test_all_mny["p_treat"].to_numpy(), test_all_mny["y"].to_numpy()),
        "bias_t2": bias_of(test_all_mny["p_t2"].to_numpy(), test_all_mny["y"].to_numpy()),
        "bias_platt": bias_of(test_all_mny["p_platt"].to_numpy(), test_all_mny["y"].to_numpy()),
    }
    c_comb = out["combinado"]

    puck_diff_concat = np.concatenate(puck_diffs_all) if puck_diffs_all else np.array([])
    puck_dates_concat = np.concatenate(puck_dates_all) if puck_dates_all else np.array([])
    if len(puck_diff_concat) == 0:
        raise SystemExit("criterio 6: no hay ningun partido evaluable en la puck line.")
    puck_delta_mean = float(puck_diff_concat.mean())
    c_comb["bootstrap_puck_line"] = bootstrap_por_fecha(puck_dates_concat, puck_diff_concat,
                                                        margen=0.0)

    out["criterios"] = {
        "1_delta_universo_combinado_le_-0.002": c_comb["delta_ll_universo"] <= -IMPROVEMENT_MARGIN,
        "2_delta_negativo_en_cada_particion": all(
            out["folds"][f]["delta_ll_universo"] < 0 for f in FOLDS),
        "3_t_bate_constante_signo": (
            c_comb["ll_treat"] < c_comb["ll_const"]
            and all(out["folds"][f]["ll_treat"] < out["folds"][f]["ll_const"] for f in FOLDS)),
        "4_ece_no_empeora": c_comb["ece_trat"] <= c_comb["ece_base"],
        "5_t_entre_0_y_0.9_en_las_tres_particiones": all(0.0 < v < 0.9 for v in t_by_fold.values()),
        "6_puck_line_no_empeora": puck_delta_mean <= 0,
        "7_t2_menor_que_0.9_en_las_tres_particiones": all(v < 0.9 for v in t2_by_fold.values()),
    }
    out["veredicto"] = "ACEPTA" if all(out["criterios"].values()) else "RECHAZA"
    out["t_por_particion"] = t_by_fold
    out["k_por_particion"] = k_by_fold
    out["t2_por_particion"] = t2_by_fold
    out["a2_por_particion"] = a2_by_fold
    out["delta_ll_puck_line_media"] = puck_delta_mean

    # Informes secundarios (seccion 10 del pre-registro / bullets de la
    # tarea: AUC, rejilla 0-1,20 + rolling_origin_improvement, puck line por
    # linea con ECE, totales). "No deciden": nunca deben impedir escribir el
    # JSON principal (ya construido arriba con los 7 criterios y el
    # veredicto).

    def _informe_auc() -> dict:
        y_comb = test_all_mny["y"].to_numpy()
        p_base_comb = test_all_mny["p_base"].to_numpy()
        p_treat_comb = test_all_mny["p_treat"].to_numpy()
        return {
            "por_particion": {f: {"base": out["folds"][f]["auc_base"],
                                  "t": out["folds"][f]["auc_treat"]} for f in FOLDS},
            "combinado": {"base": float(roc_auc_score(y_comb, p_base_comb)),
                         "t": float(roc_auc_score(y_comb, p_treat_comb))},
        }

    def _informe_grid_canonico() -> dict:
        # Procedimiento canonico del proyecto (informe 4 del pre-registro),
        # version ANALITICA (punto 7 de la revision de Fable): en vez de
        # ~26 pasadas completas de `walk_forward_backtest` (una por valor de
        # la rejilla), se reutiliza que `diff_base`/`avg` de `df` NO dependen
        # del tilt (seccion 1.3, ya verificado por `assert_diff_avg_tilt_
        # invariant` en --parity-only): cada perdida de la rejilla es
        # `ll_per_game(home_win_vec(diff, avg, tt, ...), y)` sobre el MISMO
        # `df` de moneyline, en el mismo orden temporal que alimenta
        # `binary_probs`/`binary_outcomes`. La paridad puntual (no las 26
        # pasadas completas, solo 2-3 valores representativos) confirma que
        # esa serie analitica coincide con el motor.
        diff_all = df["diff_base"].to_numpy()
        avg_all = df["avg"].to_numpy()
        y_all = df["y"].to_numpy()
        valores = sorted(set(list(grid) + [tilt0]))
        loss_series: dict[float, list[float]] = {
            float(tt): ll_per_game(home_win_vec(diff_all, avg_all, tt, bonus, max_goals),
                                   y_all).tolist()
            for tt in valores
        }
        puntos_paridad = sorted({valores[0], valores[len(valores) // 2], tilt0})
        for tt in puntos_paridad:
            # `assert_parity` aborta con SystemExit, que `_safe_informe` (solo
            # Exception) no captura: un fallo aqui mataria el proceso tras
            # calcular los criterios y ANTES de escribir el JSON de la ejecucion
            # unica. En un informe secundario se anota y se sigue (revision de
            # Fable 2026-09-30); las paridades que deciden siguen abortando.
            try:
                assert_parity(results, params, df, df_all, tt, bonus, max_goals,
                              label=f"informe4 rejilla {tt}")
            except SystemExit as exc:
                return {"error": f"PARIDAD ROTA en la rejilla (tilt={tt}): {exc}",
                        "rolling_origin": None}
        ro = rolling_origin_improvement(loss_series, default_value=tilt0, n_splits=4,
                                        min_train_frac=HOLDOUT_MIN_TRAIN_FRAC)
        return {"grid": [float(v) for v in valores], "default": tilt0, "rolling_origin": ro,
               "paridad_verificada_en": puntos_paridad}

    def _informe_puck_line_detalle() -> dict:
        out_line: dict[str, dict[str, float] | None] = {}
        for line, piezas in puck_line_pieces.items():
            if not piezas:
                out_line[str(line)] = None
                continue
            p_b = np.concatenate([p["p_base"] for p in piezas])
            p_t = np.concatenate([p["p_treat"] for p in piezas])
            y_l = np.concatenate([p["y"] for p in piezas])
            out_line[str(line)] = {
                "n": int(len(y_l)),
                "delta_ll": float(np.mean(ll_per_game(p_t, y_l) - ll_per_game(p_b, y_l))),
                "ece_base": float(expected_calibration_error(p_b.tolist(), y_l.tolist())),
                "ece_treat": float(expected_calibration_error(p_t.tolist(), y_l.tolist())),
            }
        return out_line

    def _informe_totales_max_abs_delta_p_over() -> dict:
        t_c = t_by_fold["C"]
        diff_full = test_all_full["diff_base"].to_numpy()
        avg_full = test_all_full["avg"].to_numpy()
        out_tot = {}
        for line in TOTAL_LINES:
            p_b = over_vec(diff_full, avg_full, tilt0, bonus, max_goals, line)
            p_t = over_vec(diff_full, avg_full, t_c, bonus, max_goals, line)
            out_tot[str(line)] = float(np.max(np.abs(p_t - p_b))) if len(p_b) else None
        return out_tot

    def _informe_redondeo_tc() -> dict:
        # Informe 12 (seccion 10.12, punto 5 de la revision de Fable): Delta
        # log loss en el test de la particion C entre t_C exacto y t_C
        # redondeado a 3 decimales -- el valor que se escribiria en produccion
        # si se activara (seccion 13.2 del pre-registro).
        t_c = t_by_fold["C"]
        t_c_redondeado = round(t_c, 3)
        fold_c = FOLDS["C"]
        test_c = df[(df["date"] >= fold_c["test_start"]) & (df["date"] <= fold_c["test_end"])]
        diff_c = test_c["diff_base"].to_numpy()
        avg_c = test_c["avg"].to_numpy()
        y_c = test_c["y"].to_numpy()
        ll_exacto = ll_per_game(home_win_vec(diff_c, avg_c, t_c, bonus, max_goals), y_c)
        ll_redondeado = ll_per_game(
            home_win_vec(diff_c, avg_c, t_c_redondeado, bonus, max_goals), y_c)
        return {"t_c": t_c, "t_c_redondeado": t_c_redondeado, "n_test_c": int(len(test_c)),
               "delta_ll_redondeo": float(np.mean(ll_redondeado - ll_exacto))}

    def _informe_fraccion_platt() -> dict:
        # Informe 10 (seccion 10.10, punto 5 de la revision de Fable): que
        # fraccion de la ganancia de Platt (la mejor recalibracion monotona de
        # la base) captura T, con su IC por bootstrap de dias (seccion 5.2:
        # (ll_base - ll_T)/(ll_base - ll_P)).
        ll_base_g = test_all_mny["ll_base"].to_numpy()
        ll_treat_g = test_all_mny["ll_treat"].to_numpy()
        ll_platt_g = test_all_mny["ll_platt"].to_numpy()
        num = ll_base_g - ll_treat_g
        den = ll_base_g - ll_platt_g
        denom_media = float(np.mean(den))
        fraccion = float(np.mean(num) / denom_media) if denom_media != 0 else None
        return {"fraccion_ganancia_platt": fraccion,
               "bootstrap": _bootstrap_ratio_por_fecha(dates_mny, num, den)}

    def _informe_pendiente_calibracion() -> dict:
        # Informe 5 (seccion 10.5): pendiente de la regresion logistica de y
        # sobre logit(p) de base y T, por particion y en el combinado. En T
        # deberia acercarse a 1 (seccion 10.5 del pre-registro).
        resultado: dict[str, dict[str, float | None]] = {}
        for name, foldd in FOLDS.items():
            sub = test_all_mny[(test_all_mny["date"] >= foldd["test_start"])
                               & (test_all_mny["date"] <= foldd["test_end"])]
            resultado[name] = {
                "base": _pendiente_calibracion(sub["p_base"].to_numpy(), sub["y"].to_numpy()),
                "t": _pendiente_calibracion(sub["p_treat"].to_numpy(), sub["y"].to_numpy()),
            }
        resultado["combinado"] = {
            "base": _pendiente_calibracion(test_all_mny["p_base"].to_numpy(),
                                           test_all_mny["y"].to_numpy()),
            "t": _pendiente_calibracion(test_all_mny["p_treat"].to_numpy(),
                                        test_all_mny["y"].to_numpy()),
        }
        return resultado

    def _informe_fiabilidad_y_quintiles() -> dict:
        # Informe 6 (seccion 10.6): tabla de fiabilidad (10 bins, la misma
        # funcion de `sqp.calibration.metrics`) de base, T y P en el
        # combinado, y Delta log loss por quintil de |diff_base| (la ganancia
        # deberia concentrarse en los extremos).
        y_comb = test_all_mny["y"].to_numpy()
        tabla_base = reliability_table(test_all_mny["p_base"].to_numpy(), y_comb).to_dict("records")
        tabla_t = reliability_table(test_all_mny["p_treat"].to_numpy(), y_comb).to_dict("records")
        tabla_platt = reliability_table(test_all_mny["p_platt"].to_numpy(), y_comb).to_dict("records")
        quintiles = pd.qcut(test_all_mny["diff_base"].abs(), 5, duplicates="drop")
        delta_por_quintil = (test_all_mny["ll_treat"] - test_all_mny["ll_base"]).groupby(
            quintiles, observed=True).mean()
        return {
            "fiabilidad_base": tabla_base, "fiabilidad_t": tabla_t, "fiabilidad_platt": tabla_platt,
            "delta_ll_por_quintil_abs_diff_base": {
                str(intervalo): float(v) for intervalo, v in delta_por_quintil.items()},
        }

    def _informe_por_temporada() -> dict:
        # Informe 7 (seccion 10.7): Delta log loss por temporada NHL
        # (2014-15 a 2025-26), marcando 2019-20 (burbuja) y 2020-21.
        # `_nhl_season_label` se reutiliza de measure_rest_nhl.py (no se
        # reimplementa: misma convencion oct-jun/pretemporada sep).
        season = test_all_mny["date"].apply(rmnhl._nhl_season_label)
        con_temporada = test_all_mny.assign(season=season)
        return {
            s: {"n": int(len(g)),
               "delta_ll_universo": float((g["ll_treat"] - g["ll_base"]).mean()),
               "regimen_atipico": s in ("2019-20", "2020-21")}
            for s, g in con_temporada.groupby("season")}

    out["secundario_auc"] = _safe_informe("auc", _informe_auc)
    out["secundario_grid_rolling_origin"] = _safe_informe("grid_rolling_origin", _informe_grid_canonico)
    out["secundario_puck_line_detalle"] = _safe_informe("puck_line_detalle", _informe_puck_line_detalle)
    out["secundario_totales_max_abs_delta_p_over"] = _safe_informe(
        "totales_max_abs_delta_p_over", _informe_totales_max_abs_delta_p_over)
    out["secundario_redondeo_tc"] = _safe_informe("redondeo_tc", _informe_redondeo_tc)
    out["secundario_fraccion_platt"] = _safe_informe("fraccion_platt", _informe_fraccion_platt)
    out["secundario_pendiente_calibracion"] = _safe_informe(
        "pendiente_calibracion", _informe_pendiente_calibracion)
    out["secundario_fiabilidad_y_quintiles"] = _safe_informe(
        "fiabilidad_y_quintiles", _informe_fiabilidad_y_quintiles)
    out["secundario_por_temporada"] = _safe_informe("por_temporada", _informe_por_temporada)
    out["secundario_linea_capturada"] = _safe_informe(
        "linea_capturada",
        lambda: informe_linea_capturada(results, test_all_mny, FOLDS["C"], bonus, max_goals,
                                        tilt0, t_by_fold["C"]))

    return out


# -------------------------------------------------------------------- main --
def _check_pre_provenance(pre_data: dict, procedencia: dict, head_now: str | None) -> None:
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
            f"fichero leido ahora es {hash_actual}. El modo completo aborta: "
            "los datos ya no son los que midio --pre.")
    head_previo = pre_data.get("git_head")
    if head_previo is None:
        raise SystemExit(
            "--pre-json no registra 'git_head' (git no estaba disponible cuando "
            "se ejecuto --pre). El modo completo aborta: no hay HEAD de "
            "referencia con el que comparar.")
    if head_now is None:
        raise SystemExit(
            "No se pudo obtener 'git rev-parse HEAD' ahora. El modo completo "
            "aborta: no se puede comparar contra --pre-json.")
    if head_previo != head_now:
        raise SystemExit(
            f"HEAD DE GIT CAMBIO: --pre-json registra {head_previo} y el HEAD "
            f"actual es {head_now}. El modo completo aborta: el codigo ya no es "
            "el que midio --pre.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pre", action="store_true")
    ap.add_argument("--parity-only", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--pre-json", type=Path, default=None,
                    help="Salida de --pre; el modo completo aborta si el SHA-256 o el "
                        "git HEAD difieren de los alli registrados.")
    ap.add_argument("--data-root", type=Path, default=DEFAULT_ROOT,
                    help="Raiz de datos (data/historical/results_nhl.csv). Por defecto, "
                        "sqp.config.ROOT. En un worktree de investigacion, pasar la raiz "
                        "de produccion en vez de crear una junction (CLAUDE.md).")
    args = ap.parse_args()

    if args.pre and args.parity_only:
        ap.error("--pre y --parity-only son mutuamente excluyentes.")
    if not args.parity_only and args.out is None:
        ap.error("--out es obligatorio salvo en --parity-only.")
    if args.pre_json and (args.pre or args.parity_only):
        ap.error("--pre-json solo aplica al modo completo.")
    if not args.pre and not args.parity_only and args.pre_json is None:
        ap.error("--pre-json es obligatorio en el modo completo: ejecuta antes "
                 "--pre --out <pre.json> y pasa ese fichero aqui.")

    t0 = time.perf_counter()
    out: dict[str, object]

    if args.parity_only:
        results, params, _ = load_league(args.data_root)
        if not results:
            out = {"modo": "parity-only", "resultado": "SIN RESULTADOS HISTORICOS."}
        else:
            rparams = resolved_params(params)
            tilt0 = float(rparams.get("tilt_scale", 0.9))
            bonus = float(rparams.get("home_scoring_bonus", 0.0))
            max_goals = int(rparams.get("max_score", 15))
            df, df_all = build_tilt_frame(results, params, WARMUP)
            assert_parity(results, params, df, df_all, tilt0, bonus, max_goals, label="base (0.9)")
            assert_parity(results, params, df, df_all, PROBE_TILT, bonus, max_goals,
                         label=f"tratamiento (prueba {PROBE_TILT})")
            assert_diff_avg_tilt_invariant(results, params, WARMUP)
            out = {"modo": "parity-only",
                  "resultado": (f"PARIDAD OK (n={len(df)}, n_all={len(df_all)}, "
                                f"tilt_base={tilt0}, tilt_prueba={PROBE_TILT}, "
                                f"lineas_spread={list(SPREAD_LINES)}, "
                                f"lineas_totals={list(TOTAL_LINES)}, "
                                "diff_base/avg invariantes al tilt: OK)")}
        out["segundos"] = time.perf_counter() - t0
        print(json.dumps(out, indent=2, ensure_ascii=False))
        if args.out:
            args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    if args.pre:
        out = {"modo": "pre (sin marcadores)", **informe_pre(args.data_root)}
        out["segundos"] = time.perf_counter() - t0
        args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    # Modo completo. UNA SOLA EJECUCION. `--pre-json` es obligatorio (ya
    # comprobado en el parseo de argumentos). Punto 6 de la revision de
    # Fable: ademas del HEAD (`_check_pre_provenance`), aborta si
    # `git status --porcelain -- src configs scripts/research` no esta vacio.
    _check_git_clean(git_status_porcelain(_WORKTREE_ROOT))
    pre_data = json.loads(args.pre_json.read_text(encoding="utf-8"))
    results, params, procedencia = load_league(args.data_root)
    _check_pre_provenance(pre_data, procedencia, git_head(_WORKTREE_ROOT))
    out = {"procedencia": procedencia, LEAGUE: run_nhl(results, params)}
    out["segundos"] = time.perf_counter() - t0
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
