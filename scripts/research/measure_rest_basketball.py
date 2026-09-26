"""Medicion del pre-registro del descanso/back-to-back en basket (2026-09-26).

Ver `docs/research/2026-09-26-preregistro-descanso-basket.md`. Solo la NBA
puede producir un ACEPTA (seccion 3); WNBA/NCAAB/WNCAAB son secundarias y no
deciden nada. Tres modos:

  --pre            recuentos de dias de descanso SIN marcadores (seccion 9):
                    NUNCA lee home_score/away_score, solo date/home/away/
                    game_id via RestModel. Registra SHA-256 y filas de cada
                    fichero de results_<liga>.csv leido.
  --parity-only    construye el brazo base (c=0) para cada liga y comprueba
                    la paridad con el motor canonico
                    `sqp.backtesting.engine.walk_forward_backtest` a 1e-12
                    (probabilidades y resultados). Repite la comprobacion con
                    c=0,5 SOLO como prueba de paridad del mecanismo
                    rest_points_per_day (seccion 5, aserciones 1 y 2), y
                    ADEMAS comprueba la paridad de spreads (informe 6) con ese
                    mismo c=0,5 y tres lineas FIJAS y arbitrarias
                    (PARITY_SPREAD_LINES = -4.5, 1.5, 6.5, sin relacion con
                    los cuantiles del modo completo), para poder detectar sin
                    lanzar el modo completo cualquier desalineacion entre la
                    reconstruccion del script y `markets['spreads@L']` del
                    motor (p.ej. el motor no excluye empates en spreads como
                    si lo hace en moneyline -- ver build_rest_frame). NO
                    estima ninguna `c`, no calcula ningun Delta y no evalua
                    ningun criterio de aceptacion.
  (sin flags)      medicion completa, UNA SOLA EJECUCION (seccion 12): ajusta
                    `c` (brazo T) y `a` (brazo C) por particion sobre NBA,
                    evalua los 5 criterios de la seccion 7, el bootstrap de la
                    seccion 8 y los informes secundarios de la seccion 10, y
                    escribe el JSON de salida. Con `--pre-json <salida-de---pre>`
                    aborta si el SHA-256 de algun fichero de resultados leido
                    ahora difiere del alli registrado.

  python scripts/research/measure_rest_basketball.py --parity-only
  python scripts/research/measure_rest_basketball.py --pre --out <json>
  python scripts/research/measure_rest_basketball.py --out <json>
  python scripts/research/measure_rest_basketball.py --out <json> --pre-json <pre.json>

Reutiliza codigo de produccion (RestModel, SportAdapter/get_adapter,
distributions.elo_diff_to_margin, EloRatings.rating_diff, _league_meta) en
lugar de reimplementar formulas: el "brazo base" se obtiene llamando
literalmente `adapter.elo.rating_diff` + `dist.elo_diff_to_margin`, las MISMAS
dos lineas que ejecuta `NormalMarginAdapter.estimate` antes de sumar el
ajuste de descanso (que con `rest_points_per_day=0.0` vale siempre 0 -- ver
`src/sqp/sports/adapters.py:50-55`). El diferencial de descanso Delta_r se
obtiene con una segunda instancia de `RestModel` sondeada con
`points_per_day=1.0` y `margin_adjustment`, equivalente a la definicion de la
seccion 4 (vale hr - ar si los dos descansos se conocen y 0 si no -- enmienda
E4 de la revision independiente), nunca con el min/max reimplementado a mano.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm as _norm

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

FAMILY = "basketball"
WARMUP = 60  # default de walk_forward_backtest (seccion 5 y 9)
NM_OPTS = {"xatol": 1e-7, "fatol": 1e-10, "maxiter": 2000}  # seccion 6
N_BOOT, SEED = 10_000, 42  # seccion 8
PROBE_C = 0.5  # solo para la prueba de paridad de --parity-only (seccion 5)
# Lineas fijas SOLO para la prueba de paridad de spreads de --parity-only: no
# tienen relacion con `lineas_fijas` (derivadas de cuantiles de mu_base) que
# usa el modo completo -- son arbitrarias (negativa, positiva y de magnitud
# distinta) y sirven unicamente para ejercitar `assert_parity_spreads` sin
# depender de datos ni de ninguna estimacion.
PARITY_SPREAD_LINES = (-4.5, 1.5, 6.5)
LEAGUES = ("nba", "wnba", "ncaab", "wncaab")

# Cortes de particion (seccion 6). NBA decide; WNBA es secundaria, con sus
# propias particiones. NCAAB/WNCAAB no tienen particiones: una sola temporada,
# solo se les transfiere la `c` de la particion C de la NBA (seccion 10.10).
FOLDS_NBA = {
    "A": {"train_end": "2012-09-30", "test_start": "2012-10-01", "test_end": "2017-09-30"},
    "B": {"train_end": "2017-09-30", "test_start": "2017-10-01", "test_end": "2022-09-30"},
    "C": {"train_end": "2022-09-30", "test_start": "2022-10-01", "test_end": "2026-06-30"},
}
FOLDS_WNBA = {
    "A": {"train_end": "2024-12-31", "test_start": "2025-01-01", "test_end": "2025-12-31"},
    "B": {"train_end": "2025-12-31", "test_start": "2026-01-01", "test_end": "2026-09-25"},
}


# ------------------------------------------------------------------ datos --
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_league(league: str) -> tuple[list[dict], dict, dict]:
    """Resultados, `league_params` resueltos (seccion 5: `_league_meta` +
    `ac36d91`) y procedencia (hash/filas) del fichero leido."""
    results = ResultsStore(ROOT).load(league)
    params = dict(_league_meta(league).get("league_params") or {})
    if params.get("rest_points_per_day", 0.0) != 0.0:
        raise ValueError(
            f"{league}: rest_points_per_day ya no es 0.0 en configs/leagues/"
            "ratings.yaml -- el pre-registro asume el mecanismo APAGADO en la "
            "configuracion base (ac36d91). No decido reinterpretar la base: "
            "abortando.")
    path = ResultsStore(ROOT).path(league)
    procedencia = {"fichero": str(path), "filas": len(results)}
    if path.exists():
        procedencia["sha256"] = sha256_of(path)
    return results, params, procedencia


def resolved_params(league: str, league_params: dict) -> dict:
    """Parametros de liga tal como los ve el adaptador (FAMILY_PARAMS ->
    LEAGUE_OVERRIDES -> league_params), sin reimplementar `get_adapter`."""
    return get_adapter(league, FAMILY, league_params).params


# --------------------------------------------------------- calendario Delta_r --
def rest_calendar(results: list[dict], league: str, params: dict,
                   warmup: int = WARMUP, probe: RestModel | None = None) -> pd.DataFrame:
    """Dias de descanso por partido, en el orden y warmup del motor
    (`engine.walk_forward_backtest`), SIN tocar marcadores: solo
    date/home/away/game_id. Reutiliza `RestModel` (sondeada con
    points_per_day=1.0 y margin_adjustment, equivalente a la definicion de la
    seccion 4 -- enmienda E4) y el normalizador de equipos de produccion; no
    reimplementa la regla `min(max(D-L,0), rest_max_days)`.

    `probe` es inyectable para reutilizar este mismo recorrido temporal con
    otra instancia de `RestModel` (p.ej. sin tope, seccion 9 de `--pre`); por
    defecto construye la sonda de produccion con el tope de la liga.
    """
    normalize = get_team_normalizer(league)
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
            })
        pending.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------- mu_base (brazo base) --
def mu_base_frame(results: list[dict], league: str, params: dict,
                   warmup: int = WARMUP) -> tuple[pd.DataFrame, float]:
    """mu_margin SIN el termino de descanso, en el orden del motor.

    Reutiliza el `adapter` de produccion completo para las actualizaciones
    (`adapter.observe`, que alimenta Elo/anotacion igual que el motor), y para
    el punto de estimacion llama literalmente `adapter.elo.rating_diff` +
    `dist.elo_diff_to_margin`: las mismas dos lineas que ejecuta
    `NormalMarginAdapter.estimate` ANTES de sumar `self.rest.margin_adjustment`
    (seccion 5: "El ajuste de descanso no realimenta el Elo", por eso mu_base
    se calcula una unica vez y cada brazo es funcion analitica de mu_base).
    """
    adapter = get_adapter(league, FAMILY, params)
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
            mu = dist.elo_diff_to_margin(diff, adapter.params["points_per_elo"])
            hs, aws = r["home_score"], r["away_score"]
            y = 1.0 if hs > aws else (0.5 if hs == aws else 0.0)
            # `margin` se lleva alineado POR POSICION (idx), no por game_id: el
            # esquema legacy de ResultsStore permite `game_id == ""` en varias
            # filas (results_store.py:39-41, "fila legacy... doubleheaders"), y
            # un diccionario `{game_id: margin}` construido desde `results`
            # colapsaria todas esas filas en una sola entrada, corrompiendo el
            # marcador de cualquier partido legacy. Defecto real y separado del
            # desalineamiento por empates corregido en build_rest_frame.
            rows.append({"idx": i, "mu_base": float(mu), "y": y,
                        "margin": float(hs - aws)})
        pending.append(r)
    return pd.DataFrame(rows), adapter.params["margin_sigma"]


def build_rest_frame(results: list[dict], league: str, params: dict,
                      warmup: int = WARMUP) -> tuple[pd.DataFrame, float, pd.DataFrame]:
    """Une mu_base y el calendario de descanso, en orden temporal.

    Devuelve DOS vistas porque `engine.walk_forward_backtest` NO las filtra
    igual (causa raiz de `PARIDAD ROTA (spreads probs)`, hallada comparando
    longitudes: `binary_probs` tenia 34004 filas y `markets['spreads@L']`
    34005 para NBA):

    - `df` (2o valor... vease abajo): excluye empates (y==0.5), como la
      mascara binaria que arma `binary_probs`/`binary_outcomes` (moneyline,
      engine.py:116-119). Es la vista correcta para paridad de moneyline.
    - `df_all` (3er valor): TODAS las filas con i>=warmup, incluidos los
      empates. Es la vista correcta para paridad de spreads/totals: el motor
      alimenta `market_probs`/`market_outcomes` (engine.py:105-114) DENTRO del
      mismo `if i >= warmup:` que el moneyline, sin aplicarles esa mascara --
      solo excluye los empujes (`push`), nunca los empates. Basket no suele
      empatar, pero un unico marcador empatado en el historico (dato real, no
      hipotetico) basta para desalinear todo lo posterior si se reconstruye
      sobre la vista tie-excluded.
    """
    mb, sigma = mu_base_frame(results, league, params, warmup)
    rc = rest_calendar(results, league, params, warmup)
    merged = mb.merge(rc, on="idx", how="inner", validate="one_to_one")
    merged = merged.sort_values("idx", kind="stable").reset_index(drop=True)
    merged["afectado"] = merged["known"] & (merged["delta_r"].fillna(0.0) != 0.0)
    df_all = merged
    df = merged[merged["y"].isin([0.0, 1.0])].reset_index(drop=True)  # mascara binaria del motor
    return df, sigma, df_all


# ------------------------------------------------------------------ brazos --
def home_win_prob(mu: np.ndarray, sigma: float) -> np.ndarray:
    """P(home wins) bajo margen ~ N(mu, sigma): EXACTAMENTE
    `dist.normal_margin_probs(mu, sigma, None)["home_win"]`
    (`1 - norm.cdf(0, mu, sigma)`), vectorizado sobre un array de mu. La
    aserccion de paridad de --parity-only compara este vector contra el motor
    canonico, que a su vez llama a `dist.normal_margin_probs` fila a fila."""
    return 1.0 - _norm.cdf(0.0, loc=mu, scale=sigma)


def home_cover_prob(mu: np.ndarray, sigma: float, line: float) -> np.ndarray:
    """P(home cubre `line`), reusando `dist.normal_margin_probs` fila a fila
    (informes secundarios 6 y 7, muestras pequenas: no hace falta vectorizar
    la formula de push)."""
    return np.array([dist.normal_margin_probs(float(m), sigma, line)["home_cover"]
                     for m in mu])


def ll_per_game(p: np.ndarray, y: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Log loss binario por partido, mismo recorte que
    `tuning._binary_nll_series`."""
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


def fit_c(mu_base: np.ndarray, delta_eff: np.ndarray, y: np.ndarray, sigma: float) -> float:
    def obj(x: np.ndarray) -> float:
        p = home_win_prob(mu_base + x[0] * delta_eff, sigma)
        return float(np.mean(ll_per_game(p, y)))
    return float(fit(obj, [0.0], "c")[0])


def fit_a(mu_base: np.ndarray, y: np.ndarray, sigma: float) -> float:
    def obj(x: np.ndarray) -> float:
        p = home_win_prob(mu_base + x[0], sigma)
        return float(np.mean(ll_per_game(p, y)))
    return float(fit(obj, [0.0], "a")[0])


def fit_ac(mu_base: np.ndarray, delta_eff: np.ndarray, y: np.ndarray,
           sigma: float) -> tuple[float, float]:
    def obj(x: np.ndarray) -> float:
        p = home_win_prob(mu_base + x[0] + x[1] * delta_eff, sigma)
        return float(np.mean(ll_per_game(p, y)))
    x = fit(obj, [0.0, 0.0], "a,c conjunto")
    return float(x[0]), float(x[1])


def bootstrap_por_fecha(dates: np.ndarray, diff: np.ndarray) -> dict:
    """Seccion 8: remuestrea DIAS UTC completos del test combinado, 10.000
    replicas, semilla 42. IC95 percentil y error estandar del Delta medio."""
    u, inv = np.unique(dates, return_inverse=True)
    sums = np.bincount(inv, weights=diff)
    cnts = np.bincount(inv).astype(float)
    rng = np.random.default_rng(SEED)
    pick = rng.integers(0, len(u), size=(N_BOOT, len(u)))
    reps = sums[pick].sum(axis=1) / cnts[pick].sum(axis=1)
    return {"n_dias": int(len(u)),
            "ic95": [float(np.quantile(reps, 0.025)), float(np.quantile(reps, 0.975))],
            "se": float(np.std(reps, ddof=1))}


def bias_of(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean(p) - np.mean(y))


# ------------------------------------------------------------------ paridad --
def assert_parity_base(results: list[dict], league: str, params: dict,
                        df: pd.DataFrame, sigma: float, warmup: int = WARMUP,
                        atol: float = 1e-12) -> None:
    """Seccion 5, aserto 1: el brazo base coincide con `binary_probs` de
    `walk_forward_backtest(results, league, "basketball", params)`."""
    ref = walk_forward_backtest(results, league, FAMILY, params, warmup=warmup)
    mine_p = home_win_prob(df["mu_base"].to_numpy(), sigma)
    mine_y = df["y"].to_numpy()
    theirs_p = np.asarray(ref["binary_probs"], dtype=float)
    theirs_y = np.asarray(ref["binary_outcomes"], dtype=float)
    if len(mine_p) != len(theirs_p) or not np.allclose(mine_p, theirs_p, rtol=0, atol=atol):
        raise SystemExit(f"PARIDAD ROTA (base) en {league}: no se mide nada.")
    if not np.array_equal(mine_y, theirs_y):
        raise SystemExit(f"RESULTADOS DESALINEADOS (base) en {league}.")
    # Espeja tambien la formula escalar de produccion (sin duplicarla): el
    # vector de `home_win_prob` debe coincidir con `dist.normal_margin_probs`
    # llamado fila a fila, no solo con el motor.
    scalar = np.array([dist.normal_margin_probs(float(m), sigma, None)["home_win"]
                       for m in df["mu_base"].to_numpy()[:200]])
    if not np.allclose(mine_p[:200], scalar, rtol=0, atol=atol):
        raise SystemExit(f"PARIDAD ROTA (formula escalar) en {league}.")


def assert_parity_treatment(results: list[dict], league: str, params: dict,
                             df: pd.DataFrame, sigma: float, c: float,
                             warmup: int = WARMUP, atol: float = 1e-12) -> None:
    """Seccion 5, aserto 2: el brazo T con `c` coincide con el motor ejecutado
    con `params["rest_points_per_day"] = c`."""
    mine_p = home_win_prob(
        df["mu_base"].to_numpy() + c * df["delta_eff"].to_numpy(), sigma)
    ref = walk_forward_backtest(results, league, FAMILY,
                                {**params, "rest_points_per_day": c}, warmup=warmup)
    theirs_p = np.asarray(ref["binary_probs"], dtype=float)
    if len(mine_p) != len(theirs_p) or not np.allclose(mine_p, theirs_p, rtol=0, atol=atol):
        raise SystemExit(
            f"PARIDAD ROTA (tratamiento c={c}) en {league}: no se mide nada.")


def assert_parity_spreads(results: list[dict], league: str, params: dict,
                          df_all: pd.DataFrame, sigma: float, c: float,
                          lineas: list[float], warmup: int = WARMUP,
                          atol: float = 1e-12) -> None:
    """Informe secundario 6: el resumen por linea del motor
    (`walk_forward_backtest(..., spread_lines=lineas)` con `c` constante para
    TODO el historico) coincide, a 1e-12, con el calculo propio de
    `home_cover_prob` sobre TODO `df_all` (no solo una particion). Aborta si no
    coincide: la comprobacion de paridad de la seccion 5 exige tambien cubrir
    los mercados de spread, no solo el moneyline.

    `df_all` DEBE ser la vista de `build_rest_frame` que INCLUYE empates (3er
    valor de retorno), no la vista tie-excluded del moneyline: el motor
    alimenta `market_probs`/`market_outcomes` de spreads dentro del mismo
    `if i >= warmup:` que el moneyline pero SIN aplicarle la mascara binaria
    (engine.py:105-119), asi que solo excluye empujes, nunca empates. Pasar la
    vista tie-excluded desalinea todas las filas posteriores al primer
    empate y rompe esta paridad con longitudes distintas (causa raiz real de
    `PARIDAD ROTA (spreads probs)`, confirmada comparando longitudes: NBA
    tenia 34004 filas en `binary_probs` y 34005 en `markets['spreads@L']`)."""
    ref = walk_forward_backtest(results, league, FAMILY,
                                {**params, "rest_points_per_day": c},
                                warmup=warmup, spread_lines=tuple(lineas))
    mu = df_all["mu_base"].to_numpy()
    de = df_all["delta_eff"].to_numpy()
    # `margin` viene de la columna alineada por posicion (`mu_base_frame`), NO
    # de un diccionario indexado por `game_id`: ese indice colapsa filas legacy
    # con `game_id == ""` (ver comentario en mu_base_frame) y corrompia el
    # marcador de esas filas, desalineando `push`/`covered` frente al motor.
    margin = df_all["margin"].to_numpy(dtype=float)
    for line in lineas:
        key = f"spreads@{line}"
        mkt = ref["markets"].get(key)
        if mkt is None:
            raise SystemExit(
                f"PARIDAD ROTA (spreads) en {league}: el motor no devolvio '{key}'.")
        push = margin == -line
        covered = (margin > -line).astype(float)
        mine_p = home_cover_prob(mu + c * de, sigma, line)
        mine_p, mine_y = mine_p[~push], covered[~push]
        theirs_p = np.asarray(mkt["probs"], dtype=float)
        theirs_y = np.asarray(mkt["outcomes"], dtype=float)
        if len(mine_p) != len(theirs_p) or not np.allclose(mine_p, theirs_p, rtol=0, atol=atol):
            raise SystemExit(
                f"PARIDAD ROTA (spreads probs) en {league} linea {line}: no se mide nada.")
        if len(mine_y) != len(theirs_y) or not np.array_equal(mine_y, theirs_y):
            raise SystemExit(
                f"PARIDAD ROTA (spreads outcomes) en {league} linea {line}.")


# ------------------------------------------------------------------- --pre --
def _bucket_5_o_mas(series: pd.Series) -> dict[str, int]:
    """Recuento 1/2/3/4/5+ de una serie de dias de descanso SIN tope (seccion
    9: "5 o mas: 3.408")."""
    counts = series.value_counts()
    out = {str(k): int(counts.get(k, 0)) for k in (1, 2, 3, 4)}
    out["5+"] = int(counts[counts.index >= 5].sum())
    return out


def informe_pre(league: str) -> dict:
    results, params, procedencia = load_league(league)
    if not results:
        return {"liga": league, **procedencia, "aviso": "sin resultados historicos"}
    rc = rest_calendar(results, league, params, WARMUP)
    conocidos = rc[rc["known"]]
    afectados = conocidos[conocidos["delta_r"] != 0.0]

    # Distribucion SIN tope (seccion 9): segunda instancia de `RestModel` con
    # `max_rest=10**9`, alimentada igual dentro de `rest_calendar`, para poder
    # distinguir "exactamente 4" de "5 o mas" (la version con tope de arriba
    # los funde en un unico bucket "4").
    normalize = get_team_normalizer(league)
    probe_sin_tope = RestModel(points_per_day=0.0, max_rest=10**9, normalize=normalize)
    rc_sin_tope = rest_calendar(results, league, params, WARMUP, probe=probe_sin_tope)
    conocidos_sin_tope = rc_sin_tope[rc_sin_tope["known"]]

    out = {
        "liga": league, **procedencia,
        "partidos_totales": int(len(results)),
        "evaluados_tras_warmup": int(len(rc)),
        "con_ambos_descansos_conocidos": int(len(conocidos)),
        "afectados": int(len(afectados)),
        "fraccion_afectada_f": float(len(afectados) / len(conocidos)) if len(conocidos) else None,
        "delta_r_counts": {str(int(k)): int(v)
                           for k, v in conocidos["delta_r"].value_counts().sort_index().items()},
        "dias_descanso_por_equipo_partido": {
            str(int(k)): int(v) for k, v in
            pd.concat([conocidos["hr"], conocidos["ar"]]).value_counts().sort_index().items()},
        "dias_descanso_por_equipo_partido_sin_tope": _bucket_5_o_mas(
            pd.concat([conocidos_sin_tope["hr"], conocidos_sin_tope["ar"]])),
    }
    if league == "nba":
        out["particiones"] = {
            name: _potencia_fold(rc, fold) for name, fold in FOLDS_NBA.items()}
    elif league == "wnba":
        out["particiones"] = {
            name: _potencia_fold(rc, fold) for name, fold in FOLDS_WNBA.items()}
    return out


def _potencia_fold(rc: pd.DataFrame, fold: dict) -> dict:
    train = rc[rc["date"] <= fold["train_end"]]
    test = rc[(rc["date"] >= fold["test_start"]) & (rc["date"] <= fold["test_end"])]
    test_known = test[test["known"]]
    test_af = test_known[test_known["delta_r"] != 0.0]
    return {
        "n_train": int(len(train)), "n_test": int(len(test)),
        "n_test_afectados": int(len(test_af)),
        "abs_delta_r_1_2_3": [int((test_af["delta_r"].abs() == k).sum()) for k in (1, 2, 3)],
        "local_mas_descansado": int((test_af["delta_r"] > 0).sum()),
        "media_delta_r": float(test_af["delta_r"].mean()) if len(test_af) else None,
        "rms_delta_r": float(np.sqrt((test_af["delta_r"] ** 2).mean())) if len(test_af) else None,
    }


# -------------------------------------------------------------- captura odds --
def captured_lines(results: list[dict], league: str) -> dict:
    """Lineas de spread capturadas y procedencia de las cuotas leidas (mismo
    mecanismo que `measure_weather_mlb.captured_lines`:
    `_match_index`/`_match_result`/`_pick_main_lines` de produccion, sin
    reimplementar el emparejamiento).

    Devuelve:
      - "spreads": game_id -> linea principal de spread (home point) del
        ultimo snapshot pregame, solo para los partidos con esa linea.
      - "game_ids_emparejados": TODOS los game_id que `_match_result` empareja
        con un evento de cuotas, tengan o no linea de spread -- es el universo
        correcto para el informe secundario 7 (h2h), que no debe filtrarse por
        si el spread esta disponible.
      - "ficheros_sha256": SHA-256 de cada fichero `odds_<liga>_*.csv` leido
        (seccion 4: "cada fichero leido").
    """
    odds_dir = ROOT / "data" / "odds"
    ficheros_sha256 = {f.name: sha256_of(f)
                       for f in sorted(odds_dir.glob(f"odds_{league}_*.csv"))}
    odds = load_closing_odds(ROOT, league)
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


# ------------------------------------------------------------------ NBA -----
def run_nba(results: list[dict], params: dict) -> tuple[dict, float, pd.DataFrame, float]:
    df, sigma, df_all = build_rest_frame(results, "nba", params, WARMUP)
    assert_parity_base(results, "nba", params, df, sigma)
    assert_parity_treatment(results, "nba", params, df, sigma, PROBE_C)

    out: dict = {"n_total": int(len(df)), "folds": {}}
    pieces = []
    c_by_fold: dict[str, float] = {}
    grid_c = np.round(np.arange(-1.00, 3.0 + 1e-9, 0.25), 2)
    for name, fold in FOLDS_NBA.items():
        train = df[df["date"] <= fold["train_end"]]
        test = df[(df["date"] >= fold["test_start"]) & (df["date"] <= fold["test_end"])].copy()
        mu_tr, de_tr, y_tr = (train["mu_base"].to_numpy(), train["delta_eff"].to_numpy(),
                              train["y"].to_numpy())
        c = fit_c(mu_tr, de_tr, y_tr, sigma)
        a0 = fit_a(mu_tr, y_tr, sigma)
        a_joint, c_joint = fit_ac(mu_tr, de_tr, y_tr, sigma)
        c_by_fold[name] = c

        mu_te, de_te, y_te = (test["mu_base"].to_numpy(), test["delta_eff"].to_numpy(),
                              test["y"].to_numpy())
        p_base = home_win_prob(mu_te, sigma)
        p_treat = home_win_prob(mu_te + c * de_te, sigma)
        p_ctrl = home_win_prob(mu_te + a0, sigma)
        test["ll_base"] = ll_per_game(p_base, y_te)
        test["ll_treat"] = ll_per_game(p_treat, y_te)
        test["ll_ctrl"] = ll_per_game(p_ctrl, y_te)
        test["p_base"], test["p_treat"] = p_base, p_treat
        af = test[test["afectado"]]

        # Informe secundario 3: perfil de log loss de ENTRENAMIENTO en la rejilla.
        perfil = [{"c": float(cc),
                  "log_loss_train": float(np.mean(ll_per_game(
                      home_win_prob(mu_tr + cc * de_tr, sigma), y_tr)))}
                 for cc in grid_c]

        out["folds"][name] = {
            "train": fold["train_end"], "test": [fold["test_start"], fold["test_end"]],
            "n_train": int(len(train)), "n_test": int(len(test)), "n_test_afectados": int(len(af)),
            "c": c, "control_a": a0,
            "conjunto_a_c_controlando_ventaja_de_campo": {"a": a_joint, "c": c_joint},
            "bias_base_test": bias_of(p_base, y_te),
            "delta_ll_afectados": float((af["ll_treat"] - af["ll_base"]).mean()) if len(af) else None,
            "delta_ll_universo": float((test["ll_treat"] - test["ll_base"]).mean()),
            "ll_trat_menos_ctrl_universo": float((test["ll_treat"] - test["ll_ctrl"]).mean()),
            "perfil_log_loss_train_grid": perfil,
        }
        pieces.append(test)

    assert_parity_treatment(results, "nba", params, df, sigma, c_by_fold["C"])

    test_all = pd.concat(pieces).reset_index(drop=True)
    af_all = test_all[test_all["afectado"]]
    diff_af = (af_all["ll_treat"] - af_all["ll_base"]).to_numpy()
    diff_tc = (test_all["ll_treat"] - test_all["ll_ctrl"]).to_numpy()
    out["combinado"] = {
        "n_test": int(len(test_all)), "n_afectados": int(len(af_all)),
        "delta_ll_afectados": float(diff_af.mean()),
        "bootstrap_afectados": bootstrap_por_fecha(af_all["date"].to_numpy(), diff_af),
        "bootstrap_trat_vs_ctrl": bootstrap_por_fecha(test_all["date"].to_numpy(), diff_tc),
        "delta_ll_universo": float((test_all["ll_treat"] - test_all["ll_base"]).mean()),
        "ece_base": float(expected_calibration_error(test_all["p_base"].tolist(),
                                                      test_all["y"].tolist())),
        "ece_trat": float(expected_calibration_error(test_all["p_treat"].tolist(),
                                                      test_all["y"].tolist())),
        "ll_trat": float(test_all["ll_treat"].mean()),
        "ll_ctrl": float(test_all["ll_ctrl"].mean()),
        "bias_base": bias_of(test_all["p_base"].to_numpy(), test_all["y"].to_numpy()),
    }
    c_comb = out["combinado"]
    out["criterios"] = {
        # Seccion 14: resuelto por el operador el 2026-09-26, "Solo afectados".
        "1_delta_afectados_combinado_le_-0.002": c_comb["delta_ll_afectados"] <= -IMPROVEMENT_MARGIN,
        "2_delta_afectados_negativo_en_cada_particion":
            all(f["delta_ll_afectados"] is not None and f["delta_ll_afectados"] < 0
                for f in out["folds"].values()),
        "3_ece_universo_no_empeora": c_comb["ece_trat"] <= c_comb["ece_base"],
        "4_c_positivo_en_las_tres_particiones": all(v > 0 for v in c_by_fold.values()),
        "5_trat_bate_control_intercepto": c_comb["ll_trat"] < c_comb["ll_ctrl"],
    }
    out["veredicto"] = "ACEPTA" if all(out["criterios"].values()) else "RECHAZA"
    out["c_por_particion"] = c_by_fold

    # Informe secundario 1: bias por particion (ya en cada fold) + combinado (arriba).
    # Informe secundario 4: por |Delta_r| y signo; residuo medio por valor de Delta_r.
    out["secundario_por_delta_r"] = {
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
            for k, g in test_all[test_all["known"]].groupby("delta_r")},
    }

    # Informe secundario 5: por temporada (Oct-Jun ~ "YYYY-YY"), marcando 2019-20/2020-21.
    season = test_all["date"].apply(_nba_season_label)
    test_all = test_all.assign(season=season)
    por_temporada = {}
    for s, g in test_all.groupby("season"):
        por_temporada[s] = {
            "n": int(len(g)),
            "delta_ll_universo": float((g["ll_treat"] - g["ll_base"]).mean()),
            "regimen_atipico": s in ("2019-20", "2020-21"),
        }
    out["secundario_por_temporada"] = por_temporada

    # Informe secundario 8: sin exhibiciones (equipos con <=25 apariciones en
    # TODO el fichero de la liga, no solo en test). Cuenta y filtra por nombre
    # NORMALIZADO (`get_team_normalizer`): dos grafias del mismo equipo no
    # deben contarse como "pocas apariciones" por separado.
    normalize_nba = get_team_normalizer("nba")
    apariciones = Counter()
    for r in results:
        apariciones[normalize_nba(r["home"])] += 1
        apariciones[normalize_nba(r["away"])] += 1
    pocas = {t for t, n in apariciones.items() if n <= 25}
    home_norm = af_all["home"].map(normalize_nba)
    away_norm = af_all["away"].map(normalize_nba)
    sin_exh = af_all[~home_norm.isin(pocas) & ~away_norm.isin(pocas)]
    out["secundario_sin_exhibiciones"] = {
        "equipos_excluidos": len(pocas), "n_afectados": int(len(sin_exh)),
        "delta_ll_afectados": float((sin_exh["ll_treat"] - sin_exh["ll_base"]).mean())
        if len(sin_exh) else None,
    }

    # Informes secundarios 6 y 7: lineas fijas de spread y linea capturada de
    # mercado, con la `c` de la particion C. Reusa mu_base + delta_eff (misma
    # mu_base que el motor: el descanso no realimenta el Elo, seccion 5) y
    # `dist.normal_margin_probs`/`home_cover_prob` (produccion), no una formula
    # de spread propia.
    c_c = c_by_fold["C"]
    q = test_all["mu_base"].quantile([0.25, 0.5, 0.75])
    # Redondeo al medio punto (floor(-v) + 0.5): nunca cae en un entero, asi
    # que la linea nunca empuja (enmienda E2 de la revision independiente).
    lineas_fijas = [float(math.floor(-v) + 0.5) for v in q]
    out["secundario_spreads_lineas_fijas"] = {"lineas": lineas_fijas, "por_particion": {}}
    for name, fold in FOLDS_NBA.items():
        # `df_all` (incluye empates), NO `test_all` (tie-excluded, mascara del
        # moneyline): el motor no filtra empates al alimentar
        # `market_probs`/`market_outcomes` de spreads (ver build_rest_frame).
        te = df_all[(df_all["date"] >= fold["test_start"])
                   & (df_all["date"] <= fold["test_end"])]
        mu_te = te["mu_base"].to_numpy()
        de_te = te["delta_eff"].to_numpy()
        por_linea = {}
        for line in lineas_fijas:
            p_b = home_cover_prob(mu_te, sigma, line)
            p_t = home_cover_prob(mu_te + c_by_fold[name] * de_te, sigma, line)
            # outcome real (margin > -line): columna `margin` alineada por
            # posicion (ver mu_base_frame), no un dict por game_id (que
            # colapsa filas legacy con game_id == "").
            margin = te["margin"].to_numpy(dtype=float)
            covered = (margin > -line).astype(float)
            push = margin == -line
            ll_b = ll_per_game(p_b[~push], covered[~push])
            ll_t = ll_per_game(p_t[~push], covered[~push])
            por_linea[str(line)] = {"n": int((~push).sum()),
                                    "delta_ll": float((ll_t - ll_b).mean()) if (~push).any() else None}
        out["secundario_spreads_lineas_fijas"]["por_particion"][name] = por_linea

    # Paridad de spreads (seccion 5): motor ejecutado con `c_C` constante para
    # TODO el historico, comparado contra el calculo propio sobre TODO
    # `df_all` (no una particion, y SIN excluir empates -- ver
    # build_rest_frame). Aborta si no coincide a 1e-12.
    assert_parity_spreads(results, "nba", params, df_all, sigma, c_c, lineas_fijas)

    cap = captured_lines(results, "nba")
    matched_ids = cap["game_ids_emparejados"]
    if matched_ids:
        # `delta_ll_h2h` se mide SOLO sobre los partidos que `_match_result`
        # empareja con un evento de cuotas (matched_ids), no sobre todo el
        # test de la particion C: sin esta interseccion se mezclaban partidos
        # sin cuota capturada con los que si la tienen.
        cte = test_all[(test_all["date"] >= FOLDS_NBA["C"]["test_start"])
                       & (test_all["date"] <= FOLDS_NBA["C"]["test_end"])
                       & (test_all["game_id"].isin(matched_ids))].copy()
        cte["mkt_line"] = cte["game_id"].map(cap["spreads"])
        m = cte[cte["mkt_line"].notna()]
        out["secundario_linea_capturada_h2h_y_spread"] = {
            "n_h2h": int(len(cte)),
            "delta_ll_h2h": float((cte["ll_treat"] - cte["ll_base"]).mean()) if len(cte) else None,
            "n_spread_con_linea": int(len(m)),
            "ficheros_odds_sha256": cap["ficheros_sha256"],
        }
        if len(m):
            mu_m, de_m = m["mu_base"].to_numpy(), m["delta_eff"].to_numpy()
            lines = m["mkt_line"].to_numpy(dtype=float)
            # `margin` por posicion (ver mu_base_frame), no por game_id.
            margin = m["margin"].to_numpy(dtype=float)
            push = margin == -lines
            p_b = np.array([dist.normal_margin_probs(mu, sigma, ln)["home_cover"]
                            for mu, ln in zip(mu_m, lines)])
            p_t = np.array([dist.normal_margin_probs(mu + c_c * de, sigma, ln)["home_cover"]
                            for mu, de, ln in zip(mu_m, de_m, lines)])
            covered = (margin > -lines).astype(float)
            ll_b = ll_per_game(p_b[~push], covered[~push])
            ll_t = ll_per_game(p_t[~push], covered[~push])
            out["secundario_linea_capturada_h2h_y_spread"]["delta_ll_spread"] = (
                float((ll_t - ll_b).mean()) if (~push).any() else None)
            out["secundario_linea_capturada_h2h_y_spread"]["n_spread_evaluado"] = int((~push).sum())

    return out, c_by_fold["C"], df, sigma


def _nba_season_label(date_str: str) -> str:
    y, m = int(date_str[:4]), int(date_str[5:7])
    if y == 2020 and m == 10:
        # Burbuja de Orlando: las Finales de la temporada 2019-20 se jugaron
        # en octubre de 2020 (calendario desplazado por la pandemia), fuera
        # del ciclo Oct-Jun normal que asumiria la regla general de abajo.
        return "2019-20"
    start = y if m >= 10 else y - 1
    return f"{start}-{str((start + 1) % 100).zfill(2)}"


# ---------------------------------------------------------------- WNBA -----
def run_wnba(results: list[dict], params: dict, c_nba_c: float) -> dict:
    df, sigma, _df_all = build_rest_frame(results, "wnba", params, WARMUP)
    assert_parity_base(results, "wnba", params, df, sigma)

    out: dict = {"n_total": int(len(df)), "folds": {}}
    pieces = []
    for name, fold in FOLDS_WNBA.items():
        train = df[df["date"] <= fold["train_end"]]
        test = df[(df["date"] >= fold["test_start"]) & (df["date"] <= fold["test_end"])].copy()
        mu_tr, de_tr, y_tr = (train["mu_base"].to_numpy(), train["delta_eff"].to_numpy(),
                              train["y"].to_numpy())
        c = fit_c(mu_tr, de_tr, y_tr, sigma) if len(train) else float("nan")
        mu_te, de_te, y_te = (test["mu_base"].to_numpy(), test["delta_eff"].to_numpy(),
                              test["y"].to_numpy())
        p_base = home_win_prob(mu_te, sigma)
        p_treat = home_win_prob(mu_te + c * de_te, sigma) if not np.isnan(c) else p_base
        test["ll_base"] = ll_per_game(p_base, y_te)
        test["ll_treat"] = ll_per_game(p_treat, y_te)
        af = test[test["afectado"]]
        out["folds"][name] = {
            "n_train": int(len(train)), "n_test": int(len(test)), "n_test_afectados": int(len(af)),
            "c": c,
            "delta_ll_afectados": float((af["ll_treat"] - af["ll_base"]).mean()) if len(af) else None,
            "bootstrap_afectados": bootstrap_por_fecha(
                af["date"].to_numpy(), (af["ll_treat"] - af["ll_base"]).to_numpy()) if len(af) else None,
        }
        pieces.append(test)
    test_all = pd.concat(pieces).reset_index(drop=True) if pieces else df.iloc[0:0]

    # Informe secundario 10 (transferencia): el `c` de la particion C de la
    # NBA, SIN reajustar, sobre la union de los test WNBA 2025 + 2026 (las
    # dos particiones de la seccion 6: es la unica lectura de "WNBA 2025-26"
    # que el pre-registro define explicitamente; ver ambiguedades reportadas).
    if len(test_all):
        mu_a, de_a, y_a = (test_all["mu_base"].to_numpy(), test_all["delta_eff"].to_numpy(),
                          test_all["y"].to_numpy())
        p_base_a = home_win_prob(mu_a, sigma)
        p_trans = home_win_prob(mu_a + c_nba_c * de_a, sigma)
        ll_base_a = ll_per_game(p_base_a, y_a)
        ll_trans = ll_per_game(p_trans, y_a)
        af_a = test_all[test_all["afectado"]]
        out["transferencia_c_nba_particion_c"] = {
            "c_aplicado": c_nba_c, "n": int(len(test_all)), "n_afectados": int(len(af_a)),
            "delta_ll_afectados": float(
                (ll_trans[test_all["afectado"].to_numpy()]
                 - ll_base_a[test_all["afectado"].to_numpy()]).mean()) if len(af_a) else None,
        }
    return out


# -------------------------------------------------- NCAAB / WNCAAB (transfer) --
def run_transfer_only(league: str, results: list[dict], params: dict, c_nba_c: float) -> dict:
    """Seccion 10.10: sin particiones ni ajuste propio. Se evalua toda la
    temporada tras el warmup con la `c` de la particion C de la NBA."""
    df, sigma, _df_all = build_rest_frame(results, league, params, WARMUP)
    assert_parity_base(results, league, params, df, sigma)
    mu, de, y = df["mu_base"].to_numpy(), df["delta_eff"].to_numpy(), df["y"].to_numpy()
    p_base = home_win_prob(mu, sigma)
    p_trans = home_win_prob(mu + c_nba_c * de, sigma)
    ll_base = ll_per_game(p_base, y)
    ll_trans = ll_per_game(p_trans, y)
    af = df["afectado"].to_numpy()
    return {
        "n": int(len(df)), "n_afectados": int(af.sum()), "c_aplicado": c_nba_c,
        "delta_ll_afectados": float((ll_trans[af] - ll_base[af]).mean()) if af.any() else None,
        "delta_ll_universo": float((ll_trans - ll_base).mean()) if len(df) else None,
    }


# ------------------------------------------------------------------- main --
def _check_pre_hash(pre_data: dict | None, league: str, procedencia: dict) -> None:
    """Modo completo con `--pre-json`: aborta si el SHA-256 del fichero de
    resultados de `league` leido ahora difiere del registrado por `--pre`. Sin
    esto, un fichero de entrada distinto del medido en `--pre` (seccion 9) se
    mediria en silencio en el modo completo."""
    if pre_data is None:
        return
    previo = ((pre_data.get("ligas") or {}).get(league) or {})
    hash_previo = previo.get("sha256")
    hash_actual = procedencia.get("sha256")
    if hash_previo is None or hash_actual is None:
        return  # sin fichero que comparar en alguno de los dos lados
    if hash_previo != hash_actual:
        raise SystemExit(
            f"HASH DE ENTRADA CAMBIO en {league}: --pre-json registra "
            f"{hash_previo} y el fichero leido ahora es {hash_actual}. El modo "
            "completo aborta (seccion 12): los datos ya no son los que midio "
            "--pre.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pre", action="store_true")
    ap.add_argument("--parity-only", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--pre-json", type=Path, default=None,
                    help="Salida de --pre; el modo completo aborta si el SHA-256 de "
                         "algun fichero de resultados leido ahora difiere del alli "
                         "registrado (seccion 12).")
    args = ap.parse_args()

    if args.pre and args.parity_only:
        ap.error("--pre y --parity-only son mutuamente excluyentes.")
    if not args.parity_only and args.out is None:
        ap.error("--out es obligatorio salvo en --parity-only.")
    if args.pre_json and (args.pre or args.parity_only):
        ap.error("--pre-json solo aplica al modo completo.")

    if args.parity_only:
        # Seccion 5: solo construye el brazo base (c=0) y verifica paridad con
        # el motor canonico. Ningun Delta, ninguna estimacion de c, ningun
        # criterio. c=0,5 es unicamente una prueba de paridad del mecanismo.
        resumen = {}
        for league in LEAGUES:
            results, params, _ = load_league(league)
            if not results:
                resumen[league] = "SIN RESULTADOS HISTORICOS: paridad no evaluable."
                continue
            df, sigma, df_all = build_rest_frame(results, league, params, WARMUP)
            assert_parity_base(results, league, params, df, sigma)
            assert_parity_treatment(results, league, params, df, sigma, PROBE_C)
            # Paridad de spreads (seccion 5, informe 6) con `c` y lineas FIJAS
            # y arbitrarias, ajenas al test: detecta sin lanzar el modo
            # completo cualquier desalineacion entre la reconstruccion y
            # `walk_forward_backtest(..., spread_lines=...)` -- p.ej. el
            # desalineamiento por empates (motor no los excluye en spreads,
            # solo en moneyline) o el `margin` indexado por `game_id`,
            # corregidos en build_rest_frame/mu_base_frame. `df_all` incluye
            # empates a proposito: es la vista que espera assert_parity_spreads.
            assert_parity_spreads(results, league, params, df_all, sigma, PROBE_C,
                                  list(PARITY_SPREAD_LINES))
            resumen[league] = (f"PARIDAD OK (n={len(df)}, sigma={sigma}, "
                              f"c_prueba={PROBE_C}, lineas_spread_prueba="
                              f"{list(PARITY_SPREAD_LINES)})")
        out = {"modo": "parity-only", "resultado": resumen}
        print(json.dumps(out, indent=2, ensure_ascii=False))
        if args.out:
            args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    if args.pre:
        out = {"modo": "pre (sin marcadores)", "ligas": {L: informe_pre(L) for L in LEAGUES}}
        args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    # Modo completo. UNA SOLA EJECUCION (seccion 12).
    pre_data = (json.loads(args.pre_json.read_text(encoding="utf-8"))
               if args.pre_json else None)
    out: dict = {"ligas": {}}
    results_nba, params_nba, proc_nba = load_league("nba")
    _check_pre_hash(pre_data, "nba", proc_nba)
    out["procedencia"] = {"nba": proc_nba}
    nba_out, c_nba_c, _df_nba, _sigma_nba = run_nba(results_nba, params_nba)
    out["ligas"]["nba"] = nba_out

    results_wnba, params_wnba, proc_wnba = load_league("wnba")
    _check_pre_hash(pre_data, "wnba", proc_wnba)
    out["procedencia"]["wnba"] = proc_wnba
    out["ligas"]["wnba"] = run_wnba(results_wnba, params_wnba, c_nba_c)

    for league in ("ncaab", "wncaab"):
        results_l, params_l, proc_l = load_league(league)
        _check_pre_hash(pre_data, league, proc_l)
        out["procedencia"][league] = proc_l
        out["ligas"][league] = run_transfer_only(league, results_l, params_l, c_nba_c)

    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
