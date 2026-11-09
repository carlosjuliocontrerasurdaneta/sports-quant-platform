"""Medicion del pre-registro del portero titular y su calidad en la NHL.

Ver `docs/research/2026-09-26-preregistro-portero-nhl.md` y sus Enmiendas 1-4
(2026-09-26 a 2026-10-18) con las decisiones del operador, en especial la del
2026-10-01 (instantanea congelada de entradas, `--data-root`). Ese documento
MANDA sobre este docstring; aqui solo se resumen decisiones y se documentan las
AMBIGUEDADES que dejaba abiertas, con la lectura mas literal.

## Modos (seccion 14)

  --pre            Recuentos de la seccion 10 con y sin E, cobertura, sanidad
                   de `starter`, tasa titular real != proxy, fraccion de
                   partidos afectados, k por entrenamiento, RMS de la
                   diferencia de q, correlacion con `diff` Elo (Enmienda 3 d),
                   dispersion/sensibilidad/escenarios de potencia y
                   procedencia (SHA-256, HEAD, estado de git, lista E). NO lee
                   `goals_against`, `goalie_name` ni `toi` (el cargador pide las
                   columnas por nombre) y no construye `y`/`margin`/`total`: la
                   unica lectura de marcadores es la de `adapter.observe` para
                   Elo/tasas, igual que en produccion.
  --parity-only    Comprueba las paridades de la seccion 6 con valores
                   arbitrarios de beta y k (sin estimar nada, sin perdidas, sin
                   criterios): base contra el motor, y brazo T de M1 y de M2
                   contra el motor con `goalie_beta`/`goalie_prior_shots`.
  (sin flags)      Medicion completa, UNA SOLA EJECUCION: M1 y M2 juntos. Exige
                   `--pre-json` y aborta si cambia cualquier hash, el HEAD, los
                   parametros o la lista E, o si el arbol git no esta limpio.

  python scripts/research/measure_goalie_nhl.py --parity-only --data-root <root>
  python scripts/research/measure_goalie_nhl.py --pre --out <pre.json> --data-root <root>
  python scripts/research/measure_goalie_nhl.py --out <res.json> --pre-json <pre.json> --data-root <root>

`--data-root` es OBLIGATORIO en `--pre` y en el modo completo y no puede ser la
raiz viva del repositorio (`sqp.config.ROOT`) ni ningun checkout git (`<root>/.git`); el modo completo rechaza ademas un
`--out` que ya exista. Solo `--parity-only` conserva `sqp.config.ROOT` por
defecto. Es la raiz con la estructura
`<root>/data/historical/{results_nhl.csv,goalies_nhl.csv,
.goalies_nhl_backfill_failed_dates.json,.goalies_nhl_backfill_checkpoint.json}`
y `<root>/data/odds/odds_nhl_*.csv`: la INSTANTANEA CONGELADA de la decision
del 2026-10-01. El codigo y `configs/leagues/ratings.yaml` salen del arbol.

## Pricing

La base es el pricing VIGENTE del motor (Enmienda 4: AUD-001, el empate
reglamentario suma un gol y las tasas se reescalan), no el anterior a AUD-001
de la medicion del tilt. Las funciones vectorizadas de `measure_rest_nhl.py`
NO sirven para eso (asumen `TIE_ADDS_GOAL=False`), asi que aqui se reimplementa
`distributions.poisson_match_probs(..., tie_adds_goal=True)` vectorizada
(biseccion de 50 pasos identica) y su paridad con el motor es la aserto 1.

## Ambiguedades resueltas (lectura mas literal)

1. **Partidos sin datos de portero.** Un solo camino de codigo (seccion 5):
   la identidad es `event.home_goalie` si viene informado y, si no, el ultimo
   titular observado del equipo. Un partido SIN apariciones (pretemporada,
   exhibicion, fecha fallida, sin emparejar) no recibe f=1 por fuerza: cada
   lado usa su proxy si el equipo lo tiene. Lo que NO tiene proxy (f=1) es un
   equipo cuyo ultimo partido observado no tiene un titular inequivoco (sin
   datos, o 0 / 2 o mas titulares marcados), por la regla de la seccion 13.3
   («sin adivinar»). Cuanta pretemporada hay en `goalies_nhl.csv` NO se afirma
   aqui: `--pre` la MIDE (`cobertura.pretemporada_medida`: apariciones por
   `game_type`, nulos incluidos, y filas del historico de septiembre con
   apariciones) y cuenta los lados sin identidad. PENDIENTE DE DECISION DEL
   OPERADOR: que un partido sin apariciones (exhibiciones contra clubes no NHL,
   sin emparejar) use el proxy de cada lado es la lectura IMPLEMENTADA, no una
   decision tomada.
2. **M1 sin titular real identificable** (sin datos, 0 o 2+ titulares): cae al
   proxy por el mismo camino unico.
3. **Referencia de liga L en el primer dia de temporada.** «El primer dia de
   cada temporada se usa la temporada anterior completa» se lee como: si la
   temporada (1 ago - 31 jul) no tiene ninguna aparicion con fecha anterior, se
   usa la temporada anterior entera; si tampoco la hay (2005-10-05), la
   aparicion no aporta exceso ni tiros a ningun portero (sigue entrando en la
   referencia de liga) y f=1.
4. **Apariciones.** Cuenta toda aparicion con tiros y paradas informados
   (titular o relevo). Una fila sin `shots_against`/`saves` es un suplente que
   no jugo: no cuenta. Solo cuentan las apariciones unidas a una fila del
   historico de resultados (lo que el adaptador puede observar); las no unidas
   se listan en `--pre`. Las apariciones SIN `goalie_player_id` (vacio / NaN) se
   excluyen por igual de L, de k y de los excesos, en el script y en el motor;
   `--pre` las cuenta (`cobertura.apariciones_con_tiros_y_paradas_sin_goalie_player_id`).
5. **Titular inequivoco** = exactamente un portero con `starter=True` por
   equipo y partido. Con 0 o 2+ el proxy/identidad M1 es desconocido.
6. **k por entrenamiento.** Unidad = (portero, temporada) con las apariciones
   del entrenamiento (fecha <= train_end); `L_j` = % de paradas de la liga de
   esa temporada con esas mismas apariciones; `L` global = ponderado por tiros
   de todo el entrenamiento. k es identico para M1 y M2 (solo depende de las
   apariciones). Si tau^2 <= 0 en cualquier particion: RECHAZA sin estimar.
7. **Partido afectado** (seccion 7): q_lado != 0 en algun lado, por brazo (M1
   y M2 tienen identidades distintas) y con el k de la particion. Es
   equivalente a f != 1 con beta != 0 y no depende de beta ni de resultados.
8. **a (control) y E.** a no depende de la identidad, asi que se estima una
   vez por particion. E se retira de la perdida de entrenamiento y test, de los
   criterios, del ECE, de «afectado», del bootstrap y de los informes; sigue en
   el motor (Enmienda 2 c).
9. **Criterio 6 «medio de las dos lineas»** = media por partido sobre la
   concatenacion de ambas lineas (precedente del criterio 6 del descanso NHL);
   la media de cada linea se informa aparte. Los spreads usan la vista CON
   empates, el moneyline la vista sin empates.
10. **Suelo de lambda.** El tratamiento aplica `max(0.1, lambda*f)` tras el
    suelo que ya aplica `PoissonAdapter._rates` (igual que `BaseballAdapter`);
    solo difiere de «antes del suelo» si un lambda base bajara de 0,1, cosa que
    no ocurre en la NHL. El control C no lleva suelo.
11. **Pretemporada (informe 8).** El historico de resultados no trae
    `gameType`; se estima por el mes (septiembre) como
    `goalie_backfill._guess_season_phase` y se declara asi. Donde la aparicion
    unida trae `game_type` (1 = pretemporada), el informe anade cuantas filas
    coinciden o difieren con la estimacion por mes (sin cambiar el criterio).
12. **Desempate de enfrentamientos duplicados en fecha UTC** (Enmienda 1 a):
    solo si el numero de partidos de la NHL sin emparejar de un (fecha, local,
    visitante) iguala al de filas candidatas libres del historico; se ordenan
    por `start_time_utc` y por `game_id` de ESPN (numerico). Los demas se listan.
13. **Pruebas de paridad con k y beta arbitrarios.** PROBE_BETA=1.3 y
    PROBE_K=1500.0 (sin origen en el proyecto: solo ejercitan el camino).
14. **Escenarios de potencia de `--pre`** (Enmienda 3 d): receta del tilt
    (`escenarios_9_2`) con q ~ N(0, sigma) independientes, beta=1,
    1 - L = 0,0925, semilla 42, sobre el pricing vigente; sus cifras difieren
    algo de la tabla de la Enmienda 3 por AUD-001 (Enmienda 4). El «RMS de
    log-lambda necesario» usa la sensibilidad media de los dos lados.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # modulos hermanos

import numpy as np
import pandas as pd
from scipy.special import gammaln
from sklearn.metrics import roc_auc_score

import measure_rest_nhl as rmnhl  # reutiliza codigo validado, no lo copia
import measure_tilt_nhl as tilt
from sqp.backtesting.engine import walk_forward_backtest
from sqp.backtesting.roi_engine import _match_index, _match_result, load_closing_odds
from sqp.backtesting.tuning import IMPROVEMENT_MARGIN
from sqp.calibration.metrics import expected_calibration_error
from sqp.config import ROOT as DEFAULT_ROOT
from sqp.models import distributions as dist
from sqp.models.goalies import season_of
from sqp.pipeline.daily import _league_meta
from sqp.pipeline.probabilities import _pick_main_lines
from sqp.sports.nhl_goalie_matching import _short_is_suffix
from sqp.sports.registry import get_adapter
from sqp.sports.team_names import get_team_normalizer
from sqp.storage.results_store import ResultsStore

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]

LEAGUE = "nhl"
FAMILY = "hockey"
WARMUP = rmnhl.WARMUP
FOLDS = rmnhl.FOLDS
N_BOOT, SEED = rmnhl.N_BOOT, rmnhl.SEED          # 10_000, 42 (seccion 9)
SPREAD_LINES = rmnhl.SPREAD_LINES                # (-1.5, 1.5)
TOTAL_LINES = rmnhl.TOTAL_LINES                  # (5.5, 6.5)
BOUND = 0.35                                     # tope de f (seccion 5)
PROBE_BETA, PROBE_K = 1.3, 1500.0                # solo paridad (ambiguedad 13)
GRID_BETA = tuple(float(x) for x in np.arange(-1.0, 3.0 + 1e-9, 0.5))  # informe 3
ONE_MINUS_L_SCENARIO = 0.0925                    # Enmienda 3 d
SIGMAS_Q = (0.002, 0.003, 0.004, 0.005, 0.006)   # Enmienda 3 d
ARMS = ("M1", "M2")
ARM_TAG = {"M1": "1", "M2": "2"}

# Parametros resueltos que deben coincidir exactamente (Enmienda 3 b).
EXPECTED_PARAMS = {"avg_total": 6.1, "tilt_scale": 0.439, "max_score": 15,
                   "home_scoring_bonus": 0.10, "elo_k": 10, "elo_home_adv": 15.0}
ABSENT_OR_ZERO = ("rest_elo_per_day", "goalie_beta", "elo_season_regression",
                  "dc_rho", "score_rho")
ABSENT = ("dispersion_k",)

# Columnas de goalies_nhl.csv que se leen: NUNCA goals_against, goalie_name ni toi.
APP_USECOLS = ["nhl_game_id", "espn_game_id", "date", "game_type", "start_time_utc",
               "team_side", "team_nhl", "matched", "goalie_player_id", "starter",
               "shots_against", "saves"]
FORBIDDEN_COLS = ("goals_against", "goalie_name", "toi", "decision")

# Recuentos de la seccion 10 del pre-registro (2026-09-26) para contrastar.
SEC10 = {
    "A": {"n_test": 5780, "dias": 957, "alguno_b2b": 1889, "local_b2b": 882,
          "visitante_b2b": 1506, "neutral": 74, "n_train": 15827},
    "B": {"n_test": 5192, "dias": 872, "alguno_b2b": 1629, "local_b2b": 892,
          "visitante_b2b": 1309, "neutral": 118, "n_train": 21607},
    "C": {"n_test": 5978, "dias": 952, "alguno_b2b": 1882, "local_b2b": 953,
          "visitante_b2b": 1486, "neutral": 65, "n_train": 26799},
    "combinado": {"n_test": 16950, "dias": 2781, "alguno_b2b": 5400},
}

# Reutilizado por referencia.
sha256_of = rmnhl.sha256_of
ll_per_game = rmnhl.ll_per_game
fit = rmnhl.fit
bootstrap_por_fecha = rmnhl.bootstrap_por_fecha
bias_of = rmnhl.bias_of
_lambda_split = rmnhl._lambda_split
_pendiente_calibracion = tilt._pendiente_calibracion
_safe_informe = rmnhl._safe_informe   # solo `Exception`: SystemExit (fit no converge) ABORTA (pre-registro 7)

K = 16                               # max_score 15 + 1
_KS = np.arange(K, dtype=float)
_LGAM = gammaln(_KS + 1.0)


# =============================================================== procedencia ==
def git_head(cwd: Path) -> str | None:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(cwd),
                             capture_output=True, text=True, check=True, timeout=30)
        return res.stdout.strip()
    except Exception:  # noqa: BLE001 -- procedencia informativa
        return None


def git_status_full(cwd: Path) -> str | None:
    """`git status --porcelain` de TODO el repositorio (Enmienda 3 f: arbol
    limpio, no solo src/configs/scripts)."""
    try:
        res = subprocess.run(["git", "status", "--porcelain"], cwd=str(cwd),
                             capture_output=True, text=True, check=True, timeout=60)
        return res.stdout
    except Exception:  # noqa: BLE001
        return None


def _check_git_clean(status: str | None) -> None:
    if status is None:
        raise SystemExit("No se pudo obtener 'git status --porcelain'. El modo completo "
                         "aborta: no se puede verificar que el arbol este limpio.")
    if status.strip() != "":
        raise SystemExit(f"git status --porcelain NO esta vacio:\n{status}\nEl modo "
                         "completo aborta: no se mide con el arbol sucio (Enmienda 3 f).")


def input_paths(data_root: Path) -> dict[str, Path]:
    h = data_root / "data" / "historical"
    return {
        "results_nhl.csv": ResultsStore(data_root).path(LEAGUE),
        "goalies_nhl.csv": h / "goalies_nhl.csv",
        "failed_dates": h / ".goalies_nhl_backfill_failed_dates.json",
        "checkpoint": h / ".goalies_nhl_backfill_checkpoint.json",
    }


def ratings_path() -> Path:
    from sqp.config import CONFIG_DIR
    return CONFIG_DIR / "leagues" / "ratings.yaml"


def odds_files(data_root: Path) -> list[Path]:
    return sorted((data_root / "data" / "odds").glob(f"odds_{LEAGUE}_*.csv"))


def procedencia_hashes(data_root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"data_root": str(data_root)}
    for name, p in input_paths(data_root).items():
        out[name] = {"ruta": str(p), "sha256": sha256_of(p) if p.exists() else None}
    rp = ratings_path()
    out["ratings.yaml"] = {"ruta": str(rp), "sha256": sha256_of(rp) if rp.exists() else None}
    out["odds_cierre_nhl"] = {f.name: sha256_of(f) for f in odds_files(data_root)}
    return out


def check_base_params(league_params: dict) -> dict:
    """Enmienda 3 b: los parametros resueltos deben coincidir EXACTAMENTE; un
    tilt_scale 0.9 (checkout anterior a c390c2f o adaptador sin league_params)
    aborta. Devuelve los parametros resueltos."""
    rparams = get_adapter(LEAGUE, FAMILY, league_params).params
    for key, want in EXPECTED_PARAMS.items():
        if rparams.get(key) != want:
            raise ValueError(f"nhl: parametro resuelto {key}={rparams.get(key)!r} != {want!r} "
                             "(Enmienda 3 b). No decido reinterpretar la base: abortando.")
    for key in ABSENT_OR_ZERO:
        if rparams.get(key, 0.0) not in (0, 0.0, None):
            raise ValueError(f"nhl: {key}={rparams.get(key)!r} debe valer 0 o no existir "
                             "(Enmienda 3 b). Abortando.")
    for key in ABSENT:
        if rparams.get(key) is not None:
            raise ValueError(f"nhl: {key}={rparams.get(key)!r} debe no existir. Abortando.")
    return rparams


def load_league(data_root: Path) -> tuple[list[dict], dict, dict]:
    """Resultados, `league_params` y parametros resueltos, con la raiz de datos
    parametrizada. Aborta si la base no es la de la Enmienda 3 b."""
    results = ResultsStore(data_root).load(LEAGUE)
    params = dict(_league_meta(LEAGUE).get("league_params") or {})
    rparams = check_base_params(params)
    return results, params, rparams


# =========================================================== datos de porteros ==
def read_appearances(path: Path) -> pd.DataFrame:
    """`goalies_nhl.csv` con SOLO las columnas de `APP_USECOLS` (nunca
    goals_against / goalie_name / toi). `starter` y `matched` a booleano."""
    assert not set(APP_USECOLS) & set(FORBIDDEN_COLS)
    df = pd.read_csv(path, usecols=APP_USECOLS, dtype={
        "nhl_game_id": str, "espn_game_id": str, "date": str, "start_time_utc": str,
        "team_side": str, "team_nhl": str, "goalie_player_id": str,
        "starter": str, "matched": str, "game_type": str})
    true_set = {"True", "true", "1", "1.0"}
    df["starter"] = df["starter"].astype(str).str.strip().isin(true_set)
    df["matched"] = df["matched"].astype(str).str.strip().isin(true_set)
    df["shots_against"] = pd.to_numeric(df["shots_against"], errors="coerce")
    df["saves"] = pd.to_numeric(df["saves"], errors="coerce")
    df["espn_game_id"] = df["espn_game_id"].fillna("")
    return df


def _clean_id(x: Any) -> str | None:
    """Id de portero o None: vacio / NaN / NA = sin id (NaN es truthy)."""
    if x is None or (not isinstance(x, str) and pd.isna(x)):
        return None
    sx = str(x).strip()
    return sx or None


def _game_type_label(x: Any) -> str:
    """`game_type` como entero en texto ("1.0" -> "1"; el CSV puede traerlo float);
    "<nulo>" si falta; el texto crudo si no es numerico."""
    if x is None or (not isinstance(x, str) and pd.isna(x)):
        return "<nulo>"
    try:
        v = float(str(x).strip())
    except ValueError:
        return str(x).strip() or "<nulo>"
    if math.isnan(v):
        return "<nulo>"
    return str(int(v)) if v.is_integer() else str(v)


def read_failed_dates(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return sorted(data.get("failed", []) or [], key=lambda e: str(e.get("date")))


def _gid_key(gid: str) -> tuple[int, Any]:
    return (0, int(gid)) if gid.isdigit() else (1, gid)


_INFO_LISTAS = ("sin_emparejar", "matched_sin_fila_unica_lista", "desempatados_grupos_lista")


def assign_appearances(ordered: list[dict], app: pd.DataFrame) -> tuple[dict[str, int], dict]:
    """nhl_game_id -> posicion en `ordered` (fila del historico).

    1. Los `matched=True` por `espn_game_id` == `game_id` (si es unico).
    2. Los demas, por desempate de orden (Enmienda 1 a, ambiguedad 12), sin
       leer marcadores. Devuelve tambien el informe de los no emparejados
       (fecha, equipos de la NHL, tipo: sin nombres de jugadores)."""
    norm = get_team_normalizer(LEAGUE)
    gid_to_pos: dict[str, list[int]] = defaultdict(list)
    by_date: dict[str, list[int]] = defaultdict(list)
    for pos, r in enumerate(ordered):
        gid = str(r.get("game_id") or "")
        if gid:
            gid_to_pos[gid].append(pos)
        by_date[str(r.get("date", ""))[:10]].append(pos)
    games = app.drop_duplicates("nhl_game_id")
    names: dict[str, dict[str, str]] = defaultdict(dict)
    for t in app[["nhl_game_id", "team_side", "team_nhl"]].drop_duplicates().itertuples(index=False):
        names[t.nhl_game_id][t.team_side] = t.team_nhl
    assigned: dict[str, int] = {}
    claimed: set[int] = set()
    pend: list[Any] = []
    sin_fila = 0
    sin_fila_lista: list[dict] = []
    for g in games.itertuples(index=False):
        if g.matched and g.espn_game_id:
            ps = gid_to_pos.get(g.espn_game_id, [])
            if len(ps) == 1 and ps[0] not in claimed:
                assigned[g.nhl_game_id] = ps[0]
                claimed.add(ps[0])
            else:
                sin_fila += 1
                nm = names.get(g.nhl_game_id, {})
                sin_fila_lista.append({"date": str(g.date)[:10], "home_nhl": nm.get("home"),
                                       "away_nhl": nm.get("away"), "game_type": str(g.game_type),
                                       "filas_con_ese_game_id": len(ps)})
        else:
            pend.append(g)
    groups: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    for g in pend:
        nm = names.get(g.nhl_game_id, {})
        groups[(str(g.date)[:10], norm(nm.get("home", "")), norm(nm.get("away", "")))].append(g)
    desempatados = 0
    en_grupos = 0                       # partidos asignados dentro de grupos de >= 2
    grupos_lista: list[dict] = []
    sin_emparejar: list[dict] = []
    for (date, hk, ak), gs in sorted(groups.items()):
        cand = [p for p in by_date.get(date, []) if p not in claimed
                and _short_is_suffix(hk, norm(str(ordered[p].get("home", ""))))
                and _short_is_suffix(ak, norm(str(ordered[p].get("away", ""))))]
        if cand and len(cand) == len(gs):
            gs_sorted = sorted(gs, key=lambda g: (str(g.start_time_utc), str(g.nhl_game_id)))
            cand_sorted = sorted(cand, key=lambda p: _gid_key(str(ordered[p].get("game_id") or "")))
            for g, p in zip(gs_sorted, cand_sorted):
                assigned[g.nhl_game_id] = p
                claimed.add(p)
                desempatados += 1
            if len(gs) >= 2:
                en_grupos += len(gs)
                nm0 = names.get(gs[0].nhl_game_id, {})
                grupos_lista.append({"date": date, "home_nhl": nm0.get("home"),
                                     "away_nhl": nm0.get("away"), "partidos": len(gs)})
        else:
            for g in gs:
                nm = names.get(g.nhl_game_id, {})
                sin_emparejar.append({"date": date, "home_nhl": nm.get("home"),
                                      "away_nhl": nm.get("away"),
                                      "game_type": str(g.game_type),
                                      "candidatas_en_historico": len(cand)})
    return assigned, {"partidos_nhl": int(len(games)), "asignados": len(assigned),
                      "desempatados_por_orden": desempatados,
                      "desempatados_en_grupos_de_2_o_mas": en_grupos,
                      "rescatados_individuales": desempatados - en_grupos,
                      "desempatados_grupos_lista": grupos_lista,
                      "matched_sin_fila_unica_en_historico": sin_fila,
                      "matched_sin_fila_unica_lista": sin_fila_lista,
                      "sin_emparejar": sin_emparejar}


def _starter_of(apps: list[dict]) -> str | None:
    s = [a["id"] for a in apps if a["starter"] and a["id"]]
    return s[0] if len(s) == 1 else None


def attach_goalies(results: list[dict], app: pd.DataFrame
                   ) -> tuple[list[dict], list[dict], dict]:
    """(rows_m2, rows_m1, info), en el orden del motor (estable por fecha).

    Cada fila lleva `home_goalie_appearances` / `away_goalie_appearances`
    (mapas id/shots_against/saves/starter). `rows_m1` anade
    `home_goalie_announced` / `away_goalie_announced` = titular real."""
    ordered = sorted((dict(r) for r in results), key=lambda row: str(row.get("date", "")))
    assigned, info = assign_appearances(ordered, app)
    side_apps: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for t in app.itertuples(index=False):
        pos = assigned.get(t.nhl_game_id)
        if pos is None:
            continue
        sa = None if pd.isna(t.shots_against) else float(t.shots_against)
        sv = None if pd.isna(t.saves) else float(t.saves)
        side_apps[(pos, t.team_side)].append(
            {"id": _clean_id(t.goalie_player_id), "shots_against": sa, "saves": sv,
             "starter": bool(t.starter)})
    gt_by_pos: dict[int, str | None] = {}
    for g in app.drop_duplicates("nhl_game_id").itertuples(index=False):
        if g.nhl_game_id in assigned:
            lab = _game_type_label(g.game_type)
            gt_by_pos[assigned[g.nhl_game_id]] = None if lab == "<nulo>" else lab
    rows2: list[dict] = []
    rows1: list[dict] = []
    for pos, r in enumerate(ordered):
        h, a = side_apps.get((pos, "home"), []), side_apps.get((pos, "away"), [])
        r2 = dict(r)
        r2["home_goalie_appearances"], r2["away_goalie_appearances"] = h, a
        r2["nhl_game_type"] = gt_by_pos.get(pos)       # solo informativo (informe 8)
        r1 = dict(r2)
        r1["home_goalie_announced"], r1["away_goalie_announced"] = _starter_of(h), _starter_of(a)
        rows2.append(r2)
        rows1.append(r1)
    return rows2, rows1, info


# ===================================================== estado de los porteros ==
class _PlayerPrefix:
    """Sumas acumuladas por portero, EXCLUSIVAS de la fecha consultada."""

    def __init__(self, ids: np.ndarray, dates: np.ndarray, e: np.ndarray, sa: np.ndarray):
        self.by_id: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        order = np.lexsort((dates, ids))
        ids, dates, e, sa = ids[order], dates[order], e[order], sa[order]
        if len(ids):
            cuts = np.flatnonzero(ids[1:] != ids[:-1]) + 1
            for lo, hi in zip(np.r_[0, cuts], np.r_[cuts, len(ids)]):
                self.by_id[str(ids[lo])] = (
                    dates[lo:hi], np.r_[0.0, np.cumsum(e[lo:hi])], np.r_[0.0, np.cumsum(sa[lo:hi])])

    def before(self, gid: str | None, date: str) -> tuple[float, float] | None:
        if gid is None:
            return None
        rec = self.by_id.get(gid)
        if rec is None:
            return (0.0, 0.0)
        pos = int(np.searchsorted(rec[0], date, side="left"))
        return (float(rec[1][pos]), float(rec[2][pos]))


def appearance_table(rows: list[dict]) -> pd.DataFrame:
    """Una fila por aparicion con tiros y paradas informados, unida a una fila
    del historico: pos, date, season, side, id, sa, sv."""
    recs = []
    for pos, r in enumerate(rows):
        date = str(r.get("date", ""))[:10]
        for side in ("home", "away"):
            for a in r.get(f"{side}_goalie_appearances") or []:
                if a.get("shots_against") is None or a.get("saves") is None or not a.get("id"):
                    continue
                recs.append((pos, date, season_of(date), side, a["id"],
                             float(a["shots_against"]), float(a["saves"])))
    return pd.DataFrame(recs, columns=["pos", "date", "season", "side", "id", "sa", "sv"])


def league_ref_at(apps: pd.DataFrame, dates: list[str]) -> dict[str, float]:
    """L por fecha (ambiguedad 3): % de paradas ponderado por tiros de las
    apariciones de la MISMA temporada con fecha estrictamente anterior; si no
    hay ninguna, la temporada anterior completa; si tampoco, ausente."""
    per_season: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for s, g in apps.groupby("season"):
        d = g.groupby("date")[["sa", "sv"]].sum().sort_index()
        per_season[int(s)] = (d.index.to_numpy(dtype=str),
                              np.r_[0.0, np.cumsum(d["sa"].to_numpy())],
                              np.r_[0.0, np.cumsum(d["sv"].to_numpy())])
    out: dict[str, float] = {}
    for date in dates:
        s = season_of(date)
        rec = per_season.get(s)
        if rec is not None:
            pos = int(np.searchsorted(rec[0], date, side="left"))
            if rec[1][pos] > 0:
                out[date] = float(rec[2][pos] / rec[1][pos])
                continue
        prev = per_season.get(s - 1)
        if prev is not None and prev[1][-1] > 0:
            out[date] = float(prev[2][-1] / prev[1][-1])
    return out


def goalie_state(rows: list[dict]) -> pd.DataFrame:
    """Estado de porteros ANTES de cada fila (todas las posiciones del motor),
    reconstruido SIN `GoalieRatings` (la paridad con el motor demuestra que es
    el mismo): `ref` (L del dia) y, por brazo y lado, `id`, `num`, `den`
    (suma de excesos y de tiros con fecha estrictamente anterior). M2 = proxy
    (ultimo titular inequivoco del equipo, dia a dia); M1 = titular real del
    partido o, si no se identifica, el proxy."""
    n = len(rows)
    norm = get_team_normalizer(LEAGUE)
    dates = [str(r.get("date", ""))[:10] for r in rows]
    apps = appearance_table(rows)
    refs = league_ref_at(apps, sorted(set(dates))) if len(apps) else {}
    if len(apps):
        apps["ref"] = apps["date"].map(refs)
        ok = apps["ref"].notna()
        e = np.where(ok, apps["sv"] - apps["sa"] * apps["ref"].fillna(0.0), 0.0)
        sa_eff = np.where(ok, apps["sa"], 0.0)
        prefix = _PlayerPrefix(apps["id"].to_numpy(dtype=str), apps["date"].to_numpy(dtype=str),
                               e.astype(float), sa_eff.astype(float))
    else:
        prefix = _PlayerPrefix(np.array([], dtype=str), np.array([], dtype=str),
                               np.array([]), np.array([]))
    last: dict[str, str | None] = {}
    pend: list[tuple[str, str, str | None, str | None]] = []
    pend_date: str | None = None
    proxy_h: list[str | None] = []
    proxy_a: list[str | None] = []
    real_h: list[str | None] = []
    real_a: list[str | None] = []
    for i, r in enumerate(rows):
        if pend and dates[i] != pend_date:
            for th, ta, sh, sa_ in pend:
                last[th], last[ta] = sh, sa_
            pend.clear()
        th, ta = norm(r["home"]), norm(r["away"])
        proxy_h.append(last.get(th))
        proxy_a.append(last.get(ta))
        sh = _starter_of(r.get("home_goalie_appearances") or [])
        sa_ = _starter_of(r.get("away_goalie_appearances") or [])
        real_h.append(sh)
        real_a.append(sa_)
        pend.append((th, ta, sh, sa_))
        pend_date = dates[i]
    cols: dict[str, list[Any]] = {"idx": list(range(n)), "ref": [refs.get(d, np.nan) for d in dates],
                                  "game_type": [r.get("nhl_game_type") for r in rows],
                                  "real_h": real_h, "real_a": real_a,
                                  "proxy_h": proxy_h, "proxy_a": proxy_a}
    ids = {"h1": [x if x is not None else p for x, p in zip(real_h, proxy_h)],
           "a1": [x if x is not None else p for x, p in zip(real_a, proxy_a)],
           "h2": proxy_h, "a2": proxy_a}
    for tag, idl in ids.items():
        nums, dens = [], []
        for gid, d in zip(idl, dates):
            b = prefix.before(gid, d)
            nums.append(np.nan if b is None else b[0])
            dens.append(np.nan if b is None else b[1])
        cols[f"{tag}_id"], cols[f"{tag}_num"], cols[f"{tag}_den"] = idl, nums, dens
    return pd.DataFrame(cols)


def q_of(num: np.ndarray, den: np.ndarray, k: float) -> np.ndarray:
    """q = num / (den + k); 0 si no hay identidad (NaN) o el denominador <= 0."""
    den_k = den + k
    valid = np.isfinite(num) & np.isfinite(den) & (den_k > 0.0)
    out = np.zeros_like(num, dtype=float)
    np.divide(num, den_k, out=out, where=valid)
    return out


def f_of(q: np.ndarray, beta: float, ref: np.ndarray) -> np.ndarray:
    """f = clip(1 - beta*q/(1 - L), 1-0,35, 1+0,35); 1 sin referencia de liga."""
    good = np.isfinite(ref) & (ref < 1.0)
    denom = np.where(good, 1.0 - ref, 1.0)
    raw = 1.0 - beta * q / denom
    return np.where(good, np.clip(raw, 1.0 - BOUND, 1.0 + BOUND), 1.0)


def k_moments(apps: pd.DataFrame, train_end: str) -> dict:
    """k por el metodo de momentos beta-binomial (seccion 4), solo con las
    apariciones con fecha <= train_end (ambiguedad 6)."""
    a = apps[apps["date"] <= train_end]
    if a.empty:
        return {"k": None, "tau2": None, "motivo": "sin apariciones"}
    league = a.groupby("season")[["sa", "sv"]].sum()
    lj = (league["sv"] / league["sa"]).to_dict()
    u = a.groupby(["id", "season"])[["sa", "sv"]].sum()
    u = u[u["sa"] > 0]
    sa = u["sa"].to_numpy()
    r = (u["sv"] / u["sa"]).to_numpy()
    lseason = np.array([lj[s] for s in u.index.get_level_values("season")])
    tot = float(sa.sum())
    v = float(np.sum(sa * (r - lseason) ** 2) / tot)
    b = float(np.sum(lseason * (1.0 - lseason)) / tot)
    lbar = float(a["sv"].sum() / a["sa"].sum())
    tau2 = v - b
    out = {"V": v, "B": b, "tau2": tau2, "L_global": lbar, "n_unidades": int(len(u)),
           "tiros_totales": tot, "k": None}
    if tau2 > 0:
        out["k"] = lbar * (1.0 - lbar) / tau2
    return out


# ================================================================ exclusion E ==
def exclusion_set(dates: list[str], home: list[str], away: list[str],
                  failed_dates: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """(E1, E2) como mascaras por posicion (Enmienda 2 c). E1: la fecha esta en
    `failed`. E2: el SIGUIENTE partido de un equipo con un partido en E1 (fecha
    estrictamente posterior) si su partido inmediatamente anterior (ultima
    fecha anterior del equipo) es el de E1. Posiciones en el orden del motor."""
    norm = get_team_normalizer(LEAGUE)
    n = len(dates)
    bad = set(failed_dates)
    e1 = np.array([d in bad for d in dates], dtype=bool)
    e2 = np.zeros(n, dtype=bool)
    team_games: dict[str, list[int]] = defaultdict(list)
    for i in range(n):
        team_games[norm(home[i])].append(i)
        team_games[norm(away[i])].append(i)
    for games in team_games.values():
        by_date: dict[str, list[int]] = defaultdict(list)
        for i in games:
            by_date[dates[i]].append(i)
        days = sorted(by_date)
        for prev, nxt in zip(days, days[1:]):
            if prev in bad:                       # todas las filas del dia previo estan en E1
                for i in by_date[nxt]:
                    if not e1[i]:
                        e2[i] = True
    return e1, e2


def exclusion_sides(dates: list[str], home: list[str], away: list[str],
                    failed_dates: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """(E2_local, E2_visitante): como `exclusion_set`, pero separa por LADO del
    equipo afectado (Enmienda 2 c). Una fila puede estar en ambas. La union es
    exactamente E2 de `exclusion_set`. Solo informa; no entra en ninguna perdida."""
    norm = get_team_normalizer(LEAGUE)
    n = len(dates)
    bad = set(failed_dates)
    e1 = np.array([d in bad for d in dates], dtype=bool)
    e2h = np.zeros(n, dtype=bool)
    e2a = np.zeros(n, dtype=bool)
    team_games: dict[str, list[int]] = defaultdict(list)
    for i in range(n):
        team_games[norm(home[i])].append(i)
        team_games[norm(away[i])].append(i)
    for team, games in team_games.items():
        by_date: dict[str, list[int]] = defaultdict(list)
        for i in games:
            by_date[dates[i]].append(i)
        days = sorted(by_date)
        for prev, nxt in zip(days, days[1:]):
            if prev in bad:
                for i in by_date[nxt]:
                    if not e1[i]:
                        if norm(home[i]) == team:
                            e2h[i] = True
                        if norm(away[i]) == team:
                            e2a[i] = True
    return e2h, e2a


# ==================================================== pricing vectorizado ==
def _pmf(lam: np.ndarray) -> np.ndarray:
    lam = lam[:, None]
    return np.exp(-lam + _KS * np.log(lam) - _LGAM)


def _tie_mean(mh: np.ndarray, ma: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(P(empate), E[total]) de la rejilla reglamentaria normalizada
    (`distributions._tie_mass_and_mean` con dc_rho = score_rho = 0)."""
    ph, pa = _pmf(mh), _pmf(ma)
    sh, sa = ph.sum(axis=1), pa.sum(axis=1)
    tie = (ph * pa).sum(axis=1) / (sh * sa)
    mean = (ph * _KS).sum(axis=1) / sh + (pa * _KS).sum(axis=1) / sa
    return tie, mean


def regulation_rates_vec(lam_h: np.ndarray, lam_a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """`distributions._regulation_rates` por filas: biseccion de 50 pasos de c
    en (1e-6, 1] hasta que la media FINAL (media + P(empate)) iguale la suma de
    tasas; si c satura, tasas sin reescalar."""
    target = lam_h + lam_a
    lo = np.full(lam_h.shape, 1e-6)
    hi = np.ones(lam_h.shape)
    for _ in range(50):
        mid = (lo + hi) / 2.0
        tie, mean = _tie_mean(mid * lam_h, mid * lam_a)
        below = (mean + tie) < target
        lo = np.where(below, mid, lo)
        hi = np.where(below, hi, mid)
    c = (lo + hi) / 2.0
    sat = (c - 1e-6 < 1e-9) | (1.0 - c < 1e-9)
    return np.where(sat, lam_h, c * lam_h), np.where(sat, lam_a, c * lam_a)


def score_dists(lam_h: np.ndarray, lam_a: np.ndarray, tie_adds_goal: bool = True
                ) -> tuple[np.ndarray, np.ndarray]:
    """Distribuciones FINALES normalizadas: margen (indice m + K-1, 2K-1
    columnas) y total (indice t, 2K columnas), con el reparto del empate de
    AUD-001 (los empates (k,k) pasan a (k+1,k) y (k,k+1) con la mitad)."""
    if tie_adds_goal:
        lam_h, lam_a = regulation_rates_vec(lam_h, lam_a)
    ph, pa = _pmf(lam_h), _pmf(lam_a)
    mass = ph.sum(axis=1) * pa.sum(axis=1)
    n = len(lam_h)
    margin = np.zeros((n, 2 * K - 1))
    total = np.zeros((n, 2 * K))
    for i in range(K):
        margin[:, i:i + K] += ph[:, i:i + 1] * pa[:, ::-1]
        total[:, i:i + K] += ph[:, i:i + 1] * pa
    if tie_adds_goal:
        tie = ph * pa
        d = tie.sum(axis=1)
        margin[:, K - 1] -= d
        margin[:, K] += d / 2.0
        margin[:, K - 2] += d / 2.0
        for k in range(K):
            total[:, 2 * k] -= tie[:, k]
            total[:, 2 * k + 1] += tie[:, k]
    return margin / mass[:, None], total / mass[:, None]


def p_home_from(margin: np.ndarray) -> np.ndarray:
    return margin[:, K:].sum(axis=1) + 0.5 * margin[:, K - 1]


def p_cover_from(margin: np.ndarray, line: float) -> np.ndarray:
    """P(margen > -line), linea de medio punto (sin push)."""
    m0 = int(math.floor(-line)) + 1
    return margin[:, max(0, m0 + K - 1):].sum(axis=1)


def p_over_from(total: np.ndarray, line: float) -> np.ndarray:
    t0 = int(math.floor(line)) + 1
    return total[:, t0:].sum(axis=1)


def p_home_fast(lam_h: np.ndarray, lam_a: np.ndarray) -> np.ndarray:
    """Moneyline sin construir la rejilla completa (objetivo de los ajustes)."""
    lh, la = regulation_rates_vec(lam_h, lam_a)
    ph, pa = _pmf(lh), _pmf(la)
    mass = ph.sum(axis=1) * pa.sum(axis=1)
    cum_a = np.cumsum(pa, axis=1)
    less_a = np.zeros_like(pa)
    less_a[:, 1:] = cum_a[:, :-1]
    win = (ph * less_a).sum(axis=1)
    draw = (ph * pa).sum(axis=1)
    return (win + 0.5 * draw) / mass


# ================================================================== marcos ==
def _calendar(rows: list[dict], params: dict) -> pd.DataFrame:
    return rmnhl.rest_calendar(rows, params, WARMUP)


def _attach_state(frame: pd.DataFrame, gs: pd.DataFrame, e1: np.ndarray, e2: np.ndarray
                  ) -> pd.DataFrame:
    out = frame.merge(gs, on="idx", how="left", validate="one_to_one")
    out["e1"] = e1[out["idx"].to_numpy()]
    out["e2"] = e2[out["idx"].to_numpy()]
    out["excl"] = out["e1"] | out["e2"]
    return out


def build_frame(rows: list[dict], params: dict, rparams: dict, failed_dates: list[str],
                with_outcomes: bool) -> pd.DataFrame:
    """Una fila por partido tras el warmup, en el orden del motor: `diff_base`,
    `avg`, lambdas base, calendario (descanso), estado de porteros y E. Con
    `with_outcomes=False` (--pre) NO existen `y`, `margin` ni `total`."""
    if with_outcomes:
        mb = rmnhl.diff_base_frame(rows, params, WARMUP)
    else:
        mb = tilt.diff_avg_for_pre(rows, params, WARMUP).drop(columns=["date"])
    cal = _calendar(rows, params)
    fr = mb.merge(cal, on="idx", how="inner", validate="one_to_one")
    fr = fr.sort_values("idx", kind="stable").reset_index(drop=True)
    tilt_scale = float(rparams["tilt_scale"])
    bonus = float(rparams.get("home_scoring_bonus", 0.0))
    lam_h, lam_a = _lambda_split(fr["diff_base"].to_numpy(), fr["avg"].to_numpy(),
                                 tilt_scale, bonus)
    fr["lam_h"], fr["lam_a"] = lam_h, lam_a
    gs = goalie_state(rows)
    dates = [str(r.get("date", ""))[:10] for r in rows]
    e1, e2 = exclusion_set(dates, [r["home"] for r in rows], [r["away"] for r in rows],
                           failed_dates)
    fr = _attach_state(fr, gs, e1, e2)
    fr["b2b_h"] = fr["hr"] == 1
    fr["b2b_a"] = fr["ar"] == 1
    return fr


def fold_masks(fr: pd.DataFrame, fold: dict) -> tuple[np.ndarray, np.ndarray]:
    d = fr["date"].to_numpy(dtype=str)
    train = d <= fold["train_end"]
    test = (d >= fold["test_start"]) & (d <= fold["test_end"])
    return train, test


# ================================================================== brazos ==
def arm_qf(fr: pd.DataFrame, arm: str, k: float, beta: float
           ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(q_home, q_away, f_home, f_away) de un brazo para un k y un beta."""
    tag = ARM_TAG[arm]
    ref = fr["ref"].to_numpy(dtype=float)
    qh = q_of(fr[f"h{tag}_num"].to_numpy(dtype=float), fr[f"h{tag}_den"].to_numpy(dtype=float), k)
    qa = q_of(fr[f"a{tag}_num"].to_numpy(dtype=float), fr[f"a{tag}_den"].to_numpy(dtype=float), k)
    return qh, qa, f_of(qh, beta, ref), f_of(qa, beta, ref)


def treat_lambdas(fr: pd.DataFrame, arm: str, k: float, beta: float
                  ) -> tuple[np.ndarray, np.ndarray]:
    """Brazo T: lambda_h * f(portero visitante), lambda_a * f(portero local),
    con el suelo de 0,1 (ambiguedad 10)."""
    _, _, f_h, f_a = arm_qf(fr, arm, k, beta)
    return (np.maximum(0.1, fr["lam_h"].to_numpy() * f_a),
            np.maximum(0.1, fr["lam_a"].to_numpy() * f_h))


def control_lambdas(fr: pd.DataFrame, a: float) -> tuple[np.ndarray, np.ndarray]:
    return fr["lam_h"].to_numpy() * math.exp(a), fr["lam_a"].to_numpy() * math.exp(-a)


def base_lambdas(fr: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    return fr["lam_h"].to_numpy(), fr["lam_a"].to_numpy()


def affected_mask(fr: pd.DataFrame, arm: str, k: float) -> np.ndarray:
    """Seccion 7 / ambiguedad 7: q != 0 en algun lado (con referencia de liga)."""
    qh, qa, _, _ = arm_qf(fr, arm, k, 1.0)
    ref = fr["ref"].to_numpy(dtype=float)
    return np.isfinite(ref) & ((qh != 0.0) | (qa != 0.0))


def fit_beta(tr: pd.DataFrame, arm: str, k: float) -> float:
    y = tr["y"].to_numpy()

    def obj(x: np.ndarray) -> float:
        lh, la = treat_lambdas(tr, arm, k, float(x[0]))
        return float(np.mean(ll_per_game(p_home_fast(lh, la), y)))
    return float(fit(obj, [0.0], f"beta {arm}")[0])


def fit_a(tr: pd.DataFrame) -> float:
    y = tr["y"].to_numpy()

    def obj(x: np.ndarray) -> float:
        lh, la = control_lambdas(tr, float(x[0]))
        return float(np.mean(ll_per_game(p_home_fast(lh, la), y)))
    return float(fit(obj, [0.0], "a")[0])


def fit_a_beta(tr: pd.DataFrame, arm: str, k: float) -> tuple[float, float]:
    y = tr["y"].to_numpy()

    def obj(x: np.ndarray) -> float:
        lh, la = treat_lambdas(tr, arm, k, float(x[1]))
        p = p_home_fast(lh * math.exp(float(x[0])), la * math.exp(-float(x[0])))
        return float(np.mean(ll_per_game(p, y)))
    x = fit(obj, [0.0, 0.0], f"a,beta conjunto {arm}")
    return float(x[0]), float(x[1])


def _totals_nll(tr_all: pd.DataFrame, lh: np.ndarray, la: np.ndarray) -> float:
    _, tot = score_dists(lh, la)
    total = tr_all["total"].to_numpy()
    vals = []
    for line in TOTAL_LINES:
        vals.append(ll_per_game(p_over_from(tot, line), (total > line).astype(float)))
    return float(np.mean(np.concatenate(vals)))


def fit_beta_totals(tr_all: pd.DataFrame, arm: str, k: float) -> float:
    def obj(x: np.ndarray) -> float:
        lh, la = treat_lambdas(tr_all, arm, k, float(x[0]))
        return _totals_nll(tr_all, lh, la)
    return float(fit(obj, [0.0], f"beta totales {arm}")[0])


def market_probs(lh: np.ndarray, la: np.ndarray) -> dict[str, np.ndarray]:
    mg, tt = score_dists(lh, la)
    out = {"ml": p_home_from(mg)}
    for line in SPREAD_LINES:
        out[f"spreads@{line}"] = p_cover_from(mg, line)
    for line in TOTAL_LINES:
        out[f"totals@{line}"] = p_over_from(tt, line)
    return out


def outcomes_of(fr: pd.DataFrame) -> dict[str, np.ndarray]:
    margin, total = fr["margin"].to_numpy(), fr["total"].to_numpy()
    out = {"ml": fr["y"].to_numpy()}
    for line in SPREAD_LINES:
        out[f"spreads@{line}"] = (margin > -line).astype(float)
    for line in TOTAL_LINES:
        out[f"totals@{line}"] = (total > line).astype(float)
    return out


# ================================================================== paridad ==
def assert_parity(rows_m2: list[dict], rows_m1: list[dict], params: dict, rparams: dict,
                  fr: pd.DataFrame, beta: float, k: float, atol: float = 1e-12,
                  label: str = "", base_only: bool = False,
                  arms: tuple[str, ...] = ARMS) -> None:
    """Seccion 6 (aserto 1 y 2): las probabilidades de la reconstruccion
    coinciden con las del motor a `atol`. Base: contra `binary_probs` y los
    cuatro `markets`. Brazo T de M1 y de M2: contra el motor ejecutado con
    `goalie_beta=beta` y `goalie_prior_shots=k` (comprueba que q y el proxy
    reconstruidos son los del adaptador y no una copia). Aborta con SystemExit."""
    runs: list[tuple[str, list[dict], dict, str | None]] = [
        ("base", rows_m2, params, None)]
    if not base_only:
        tp = {**params, "goalie_beta": beta, "goalie_prior_shots": k}
        if "M1" in arms:
            runs.append(("T-M1", rows_m1, tp, "M1"))
        if "M2" in arms:
            runs.append(("T-M2", rows_m2, tp, "M2"))
    for name, rows, p, arm in runs:
        ref = walk_forward_backtest(rows, LEAGUE, FAMILY, p, warmup=WARMUP,
                                    spread_lines=SPREAD_LINES, total_lines=TOTAL_LINES)
        lh, la = (base_lambdas(fr) if arm is None else treat_lambdas(fr, arm, k, beta))
        mine = market_probs(lh, la)
        outc = outcomes_of(fr)
        ml_mask = np.isin(outc["ml"], (0.0, 1.0))
        theirs_p = np.asarray(ref["binary_probs"], dtype=float)
        theirs_y = np.asarray(ref["binary_outcomes"], dtype=float)
        if len(theirs_p) != int(ml_mask.sum()) or not np.allclose(
                mine["ml"][ml_mask], theirs_p, rtol=0, atol=atol):
            raise SystemExit(f"PARIDAD ROTA (moneyline, {name}, k={k}) {label}: "
                             "no se mide nada.")
        if not np.array_equal(outc["ml"][ml_mask], theirs_y):
            raise SystemExit(f"RESULTADOS DESALINEADOS (moneyline, {name}) {label}.")
        for key in [f"spreads@{ln}" for ln in SPREAD_LINES] + [f"totals@{ln}" for ln in TOTAL_LINES]:
            mkt = ref["markets"].get(key)
            if mkt is None:
                raise SystemExit(f"PARIDAD ROTA ({key}, {name}) {label}: el motor no lo devolvio.")
            tp = np.asarray(mkt["probs"], dtype=float)
            ty = np.asarray(mkt["outcomes"], dtype=float)
            if len(tp) != len(mine[key]) or not np.allclose(mine[key], tp, rtol=0, atol=atol):
                raise SystemExit(f"PARIDAD ROTA ({key} probs, {name}, k={k}) {label}.")
            if not np.array_equal(outc[key], ty):
                raise SystemExit(f"PARIDAD ROTA ({key} outcomes, {name}) {label}.")
    # Cruce con la formula escalar de produccion en una muestra.
    sample = fr.head(100)
    lh, la = base_lambdas(sample)
    for i in range(len(sample)):
        sc = dist.poisson_match_probs(float(lh[i]), float(la[i]), -1.5, 5.5,
                                      max_goals=int(rparams.get("max_score", 15)),
                                      tie_adds_goal=True)
        vec = market_probs(lh[i:i + 1], la[i:i + 1])
        if not (abs(sc["home_win"] - vec["ml"][0]) <= atol
                and abs(sc["home_cover"] - vec["spreads@-1.5"][0]) <= atol
                and abs(sc["over"] - vec["totals@5.5"][0]) <= atol):
            raise SystemExit(f"PARIDAD ROTA (formula escalar) {label}.")


# ===================================================== ayudas de informes ==
def _json_default(o: Any) -> Any:
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=_json_default)


def _partition_of(date: str) -> str:
    for name, f in FOLDS.items():
        if f["test_start"] <= date <= f["test_end"]:
            return f"test {name}"
    if date <= FOLDS["A"]["train_end"]:
        return "entrenamiento previo a A"
    return "fuera de todas las particiones"


def recuentos_seccion_10(fr: pd.DataFrame) -> dict:
    out: dict[str, Any] = {}
    parts = []
    for name, fold in FOLDS.items():
        train, test = fold_masks(fr, fold)
        te = fr[test]
        alguno = int((te["b2b_h"] | te["b2b_a"]).sum())
        out[name] = {"n_test": int(len(te)), "dias": int(te["date"].nunique()),
                     "alguno_b2b": alguno, "local_b2b": int(te["b2b_h"].sum()),
                     "visitante_b2b": int(te["b2b_a"].sum()),
                     "neutral": int(te["neutral"].sum()), "n_train": int(train.sum())}
        parts.append(te)
    comb = pd.concat(parts)
    out["combinado"] = {"n_test": int(len(comb)), "dias": int(comb["date"].nunique()),
                        "alguno_b2b": int((comb["b2b_h"] | comb["b2b_a"]).sum())}
    return out


def contraste_seccion_10(cnt: dict) -> dict:
    return {name: {k: {"obtenido": cnt[name].get(k), "documento": v,
                       "coincide": cnt[name].get(k) == v} for k, v in want.items()}
            for name, want in SEC10.items()}


def _rms(x: np.ndarray) -> float | None:
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else None


def _auc_boot(dates: np.ndarray, y: np.ndarray, scores: dict[str, np.ndarray],
              pairs: list[tuple[str, str]]) -> dict:
    """AUC de cada modelo y IC95 percentil (bootstrap por dias, 10.000
    replicas, semilla 42) de las diferencias `pairs`, con AUC ponderado por la
    multiplicidad de cada dia (equivale a re-muestrear dias completos)."""
    u, inv = np.unique(dates, return_inverse=True)
    prep = {}
    for name, s in scores.items():
        _, grp = np.unique(s, return_inverse=True)
        prep[name] = grp
    out: dict[str, Any] = {"auc": {n: float(roc_auc_score(y, s)) for n, s in scores.items()}}
    rng = np.random.default_rng(SEED)
    reps = {pair: np.empty(N_BOOT) for pair in pairs}
    chunk = 250
    for lo in range(0, N_BOOT, chunk):
        hi = min(N_BOOT, lo + chunk)
        pick = rng.integers(0, len(u), size=(hi - lo, len(u)))
        for r in range(hi - lo):
            mult = np.bincount(pick[r], minlength=len(u)).astype(float)
            w = mult[inv]
            aucs = {}
            for name, grp in prep.items():
                pos = np.bincount(grp, weights=w * (y == 1.0))
                neg = np.bincount(grp, weights=w * (y == 0.0))
                below = np.cumsum(neg) - neg
                den = pos.sum() * neg.sum()
                aucs[name] = float(np.sum(pos * (below + 0.5 * neg)) / den) if den > 0 else np.nan
            for pair in pairs:
                reps[pair][lo + r] = aucs[pair[0]] - aucs[pair[1]]
    for pair, v in reps.items():
        v = v[np.isfinite(v)]
        out[f"dif_{pair[0]}_menos_{pair[1]}"] = {
            "ic95": [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))] if len(v) else [None, None],
            "se": float(np.std(v, ddof=1)) if len(v) > 1 else None}
    return out


# =============================================================== captura odds ==
def captured_lines_root(rows: list[dict], data_root: Path) -> dict:
    """Linea del mercado (puck line y total) del consenso, desde las cuotas de
    cierre de `data_root` (como `measure_rest_nhl.captured_lines`, pero con la
    raiz parametrizada y con total)."""
    files = odds_files(data_root)
    sha = {f.name: sha256_of(f) for f in files}
    odds = load_closing_odds(data_root, LEAGUE)
    out: dict[str, Any] = {"spreads": {}, "totals": {}, "ids": set(), "sha": sha}
    if not odds:
        return out
    idx, used = _match_index(odds), set()
    for r in sorted(rows, key=lambda x: str(x.get("date", ""))):
        eo = _match_result(r, idx, used)
        if eo is None:
            continue
        used.add(eo.event.event_id)
        gid = str(r.get("game_id"))
        out["ids"].add(gid)
        spread, total = _pick_main_lines(eo)
        if spread is not None:
            out["spreads"][gid] = spread
        if total is not None:
            out["totals"][gid] = total
    return out


def informe_linea_capturada(rows: list[dict], test_c: pd.DataFrame, lam_t: tuple[np.ndarray, np.ndarray],
                            data_root: Path, rparams: dict) -> dict | None:
    """Informe 9: Delta log loss (T de M2 con beta_C frente a base) en la
    submuestra de la particion C con cuotas, h2h / spread / total del consenso.
    Mide log loss frente al resultado, NO ventaja sobre el mercado. Se restringe
    al test de la particion C (precedente `measure_rest_nhl.py`); no se informa
    sobre A ni B y el JSON lo declara en `alcance`."""
    cap = captured_lines_root(rows, data_root)
    sel = test_c["game_id"].astype(str).isin(cap["ids"]).to_numpy()
    if not sel.any():
        return None
    sub = test_c[sel]
    mg = int(rparams.get("max_score", 15))
    lh_b, la_b = sub["lam_h"].to_numpy(), sub["lam_a"].to_numpy()
    lh_t, la_t = lam_t[0][sel], lam_t[1][sel]
    out: dict[str, Any] = {"alcance": ("solo el test de la particion C (test C), precedente "
                                       "measure_rest_nhl.py; no se informa sobre A ni B"),
                           "n_h2h": int(len(sub)), "ficheros_odds_sha256": cap["sha"]}
    y = sub["y"].to_numpy()
    ok = np.isin(y, (0.0, 1.0))
    pb, pt = p_home_fast(lh_b, la_b), p_home_fast(lh_t, la_t)
    out["delta_ll_h2h"] = float(np.mean(ll_per_game(pt[ok], y[ok]) - ll_per_game(pb[ok], y[ok]))) if ok.any() else None
    for name, mp, key in (("spread", cap["spreads"], "home_cover"), ("total", cap["totals"], "over")):
        lines = sub["game_id"].astype(str).map(mp)
        has = lines.notna().to_numpy()
        res = {"n": int(has.sum()), "delta_ll": None}
        if has.any():
            diffs = []
            for i in np.flatnonzero(has):
                ln = float(lines.iloc[i])
                kw = {"spread_line": ln, "total_line": None} if name == "spread" else {"spread_line": None, "total_line": ln}
                b = dist.poisson_match_probs(float(lh_b[i]), float(la_b[i]), kw["spread_line"],
                                             kw["total_line"], max_goals=mg, tie_adds_goal=True)[key]
                t = dist.poisson_match_probs(float(lh_t[i]), float(la_t[i]), kw["spread_line"],
                                             kw["total_line"], max_goals=mg, tie_adds_goal=True)[key]
                if name == "spread":
                    covered = float(sub["margin"].iloc[i] > -ln)
                    push = bool(sub["margin"].iloc[i] == -ln)
                else:
                    covered = float(sub["total"].iloc[i] > ln)
                    push = bool(sub["total"].iloc[i] == ln)
                if push:
                    continue
                diffs.append(float(ll_per_game(np.array([t]), np.array([covered]))[0]
                                   - ll_per_game(np.array([b]), np.array([covered]))[0]))
            res = {"n": len(diffs), "delta_ll": float(np.mean(diffs)) if diffs else None}
        out[name] = res
    return out


# ======================================================================= --pre ==
def informe_pre(data_root: Path) -> dict:
    results, params, rparams = load_league(data_root)
    paths = input_paths(data_root)
    app = read_appearances(paths["goalies_nhl.csv"])
    failed = read_failed_dates(paths["failed_dates"])
    failed_dates = [str(e["date"]) for e in failed]
    rows2, _rows1, info = attach_goalies(results, app)
    fr = build_frame(rows2, params, rparams, failed_dates, with_outcomes=False)
    assert not {"y", "margin", "total"} & set(fr.columns)
    apps = appearance_table(rows2)

    cnt_sin_e = recuentos_seccion_10(fr)
    cnt_con_e = recuentos_seccion_10(fr[~fr["excl"]])
    out: dict[str, Any] = {
        "liga": LEAGUE, "git_head": git_head(_WORKTREE_ROOT),
        "git_status_porcelain": git_status_full(_WORKTREE_ROOT),
        "parametros_resueltos": {k: rparams.get(k) for k in
                                 (*EXPECTED_PARAMS, *ABSENT_OR_ZERO, *ABSENT)},
        "hashes": procedencia_hashes(data_root),
        "partidos_totales": int(len(results)), "evaluados_tras_warmup": int(len(fr)),
        "emparejamiento": {k: v for k, v in info.items() if k not in _INFO_LISTAS},
        "sin_emparejar_nhl_lista": info["sin_emparejar"],
        "matched_sin_fila_unica_lista": info["matched_sin_fila_unica_lista"],
        "desempatados_grupos_lista": info["desempatados_grupos_lista"],
        "recuentos_seccion_10_sin_E": cnt_sin_e,
        "contraste_con_seccion_10_sin_E": contraste_seccion_10(cnt_sin_e),
        "recuentos_seccion_10_con_E": cnt_con_e,
    }
    # --- E (Enmienda 2 c): las fechas por nombre, particion y filas.
    lista_e = []
    for e in failed:
        d = str(e["date"])
        sel = fr["date"] == d
        lista_e.append({
            "date": d, "kind": e.get("kind"), "http_status": e.get("http_status"),
            "season_phase": e.get("season_phase"), "particion": _partition_of(d),
            "filas_en_historico": int(sel.sum()),
            "game_type_api": "desconocido (sin datos del backfill en esa fecha)"})
    e1 = fr[fr["e1"]]
    e2 = fr[fr["e2"] & ~fr["e1"]]
    out["E"] = {
        "fechas_fallidas": lista_e, "n_fechas": len(failed),
        "E1_filas": int(len(e1)), "E2_filas": int(len(e2)),
        "E_por_particion": {
            name: {"E1": int(fold_masks(e1, f)[1].sum()), "E2": int(fold_masks(e2, f)[1].sum())}
            for name, f in FOLDS.items()},
        "E_por_fase_estimada": {
            "E1": e1["date"].str[5:7].map(lambda m: "septiembre (pretemporada)" if m == "09" else "otro mes")
            .value_counts().to_dict(),
            "E2": e2["date"].str[5:7].map(lambda m: "septiembre (pretemporada)" if m == "09" else "otro mes")
            .value_counts().to_dict()},
        "E2_por_game_type": _e2_por_game_type(e2),
        "E1_game_type": "desconocido (sin datos del backfill en esas fechas)",
        "E2_por_lado_del_equipo_afectado": _e2_por_lado(rows2, e2, failed_dates),
        "E1_por_lado": "E1 es la fecha entera: ambos lados de cada fila",
        "lista_E_posiciones": [int(i) for i in fr.loc[fr["excl"], "idx"]],
    }
    # --- cobertura y sanidad de `starter`.
    out["cobertura"] = _cobertura(rows2, fr, app)
    # --- por particion: k, afectados, tasa titular != proxy, RMS de dq, correlacion.
    folds: dict[str, Any] = {}
    for name, fold in FOLDS.items():
        km = k_moments(apps, fold["train_end"])
        train, test = fold_masks(fr, fold)
        te = fr[test & ~fr["excl"].to_numpy()]
        entry: dict[str, Any] = {"k_momentos": km, "n_test_sin_E": int(len(te))}
        k = km["k"]
        if k is not None:
            for arm in ARMS:
                qh, qa, _, _ = arm_qf(te, arm, k, 1.0)
                ref = te["ref"].to_numpy(dtype=float)
                dq = (qh - qa) / np.where(np.isfinite(ref), 1.0 - ref, np.nan)
                aff = affected_mask(te, arm, k)
                diff = te["diff_base"].to_numpy()
                ok = np.isfinite(dq)
                corr = float(np.corrcoef(dq[ok], diff[ok])[0, 1]) if ok.sum() > 2 else None
                entry[arm] = {
                    "fraccion_afectada_f": float(aff.mean()) if len(te) else None,
                    "rms_dq_sobre_1_menos_L": _rms(dq),
                    "correlacion_dq_con_diff_elo": corr,
                    "rms_q_lado": _rms(np.r_[qh, qa]),
                }
        entry["titular_real_distinto_del_proxy"] = _tasa_titular_vs_proxy(te)
        folds[name] = entry
    out["particiones"] = folds
    out["potencia"] = _safe_informe("potencia", lambda: _potencia_pre(fr, rparams))
    return out


def _filas_sin_titular(rows: list[dict], te: pd.DataFrame) -> list[dict]:
    """Enmienda 2(e)1: POR NOMBRE (fecha, local, visitante) las filas de test sin
    titular inequivoco en algun lado (las del recuento por mes), con el numero de
    apariciones de cada lado (0 = sin apariciones; >0 = titular no inequivoco) y
    si estan en E."""
    sel = te[te["real_h"].isna() | te["real_a"].isna()]
    out = []
    for idx, excl in zip(sel["idx"], sel["excl"]):
        r = rows[int(idx)]
        out.append({"date": str(r["date"])[:10], "home": r["home"], "away": r["away"],
                    "n_apariciones_local": len(r.get("home_goalie_appearances") or []),
                    "n_apariciones_visitante": len(r.get("away_goalie_appearances") or []),
                    "en_E": bool(excl)})
    return out


def _e2_por_game_type(e2: pd.DataFrame) -> dict:
    """Filas de E2 por `game_type` de la aparicion unida (numerico), ademas del mes."""
    return e2["game_type"].map(_game_type_label).value_counts().sort_index().to_dict()


def _e2_por_lado(rows: list[dict], e2: pd.DataFrame, failed_dates: list[str]) -> dict:
    """Filas de E2 (tras el warmup, sin E1) segun el lado del equipo afectado, en
    total y por particion de test (Enmienda 2 c)."""
    dates = [str(r.get("date", ""))[:10] for r in rows]
    e2h, e2a = exclusion_sides(dates, [r["home"] for r in rows], [r["away"] for r in rows],
                               failed_dates)
    idx = e2["idx"].to_numpy(dtype=int)
    h, a = e2h[idx], e2a[idx]

    def cuenta(m: np.ndarray) -> dict:
        return {"solo_local": int((h & ~a)[m].sum()), "solo_visitante": int((a & ~h)[m].sum()),
                "ambos": int((h & a)[m].sum()), "total": int(m.sum())}
    out: dict[str, Any] = {"total": cuenta(np.ones(len(e2), dtype=bool))}
    for name, f in FOLDS.items():
        out[f"test {name}"] = cuenta(fold_masks(e2, f)[1])
    return out


def _cobertura(rows: list[dict], fr: pd.DataFrame, app: pd.DataFrame) -> dict:
    n_rows = len(rows)
    sin_datos = [i for i, r in enumerate(rows) if not (r.get("home_goalie_appearances")
                                                       and r.get("away_goalie_appearances"))]
    titulares = {"home": defaultdict(int), "away": defaultdict(int)}
    for r in rows:
        for side in ("home", "away"):
            apps = r.get(f"{side}_goalie_appearances") or []
            if apps:
                titulares[side][sum(1 for a in apps if a["starter"] and a["id"])] += 1
    porteros = {a["id"] for r in rows for side in ("home", "away")
                for a in (r.get(f"{side}_goalie_appearances") or []) if a["id"]}
    sin_datos_mes = defaultdict(int)
    for i in sin_datos:
        sin_datos_mes[str(rows[i]["date"])[5:7]] += 1
    sin_proxy = {"M2_local": int(fr["h2_id"].isna().sum()), "M2_visitante": int(fr["a2_id"].isna().sum())}
    sin_real = {"local": int(fr["real_h"].isna().sum()), "visitante": int(fr["real_a"].isna().sum())}
    sept = sum(1 for r in rows if str(r["date"])[5:7] == "09")
    sept_con = sum(1 for r in rows if str(r["date"])[5:7] == "09"
                   and (r.get("home_goalie_appearances") or r.get("away_goalie_appearances")))
    por_particion = {}
    for name, fold in FOLDS.items():
        _, test = fold_masks(fr, fold)
        te = fr[test]
        por_particion[name] = {
            "n_test": int(len(te)),
            "lados_con_titular_real": {"local": int(te["real_h"].notna().sum()),
                                       "visitante": int(te["real_a"].notna().sum())},
            "lados_con_proxy": {"local": int(te["h2_id"].notna().sum()),
                                "visitante": int(te["a2_id"].notna().sum())},
            "filas_sin_apariciones_por_mes": te.loc[te["real_h"].isna() | te["real_a"].isna(), "date"]
            .str[5:7].value_counts().sort_index().to_dict(),
            "filas_sin_apariciones_lista": _filas_sin_titular(rows, te)}
    return {
        "filas_historico": n_rows, "filas_sin_apariciones_en_algun_lado": len(sin_datos),
        "sin_apariciones_por_mes": dict(sorted(sin_datos_mes.items())),
        "apariciones_por_game_type": app["game_type"].map(_game_type_label).value_counts().to_dict(),
        "apariciones_con_tiros_y_paradas_sin_goalie_player_id": int((
            app["shots_against"].notna() & app["saves"].notna()
            & app["goalie_player_id"].map(_clean_id).isna()).sum()),
        "filas_historico_septiembre": sept,
        "filas_historico_septiembre_con_apariciones": sept_con,
        "pretemporada_medida": ("recuento medido de goalies_nhl.csv (apariciones por game_type, "
                                "nulos incluidos) y de filas del historico de septiembre; no se "
                                "afirma que la API liste o no la pretemporada (ambiguedad 1)"),
        "titulares_marcados_por_equipo_y_partido": {s: dict(sorted(v.items())) for s, v in titulares.items()},
        "porteros_distintos": len(porteros),
        "apariciones_filas_no_unidas_al_historico": int(len(app) - sum(
            len(r.get("home_goalie_appearances") or []) + len(r.get("away_goalie_appearances") or [])
            for r in rows)),
        "lados_sin_proxy_tras_warmup": sin_proxy, "lados_sin_titular_real_tras_warmup": sin_real,
        "por_particion": por_particion}


def _tasa_titular_vs_proxy(te: pd.DataFrame) -> dict:
    out: dict[str, Any] = {}
    for side, real, prox, b2b in (("local", "real_h", "proxy_h", "b2b_h"),
                                  ("visitante", "real_a", "proxy_a", "b2b_a")):
        both = te[real].notna() & te[prox].notna()
        diff = (te[real] != te[prox]) & both
        res = {"lados_comparables": int(both.sum()),
               "distinto": int(diff.sum()),
               "fraccion": float(diff.sum() / both.sum()) if both.sum() else None}
        for lab, m in (("b2b", te[b2b]), ("no_b2b", ~te[b2b])):
            bb = both & m
            res[f"fraccion_{lab}"] = float(((te[real] != te[prox]) & bb).sum() / bb.sum()) if bb.sum() else None
        out[side] = res
    return out


def _potencia_pre(fr: pd.DataFrame, rparams: dict) -> dict:
    """Enmienda 3 d: dispersion de p, sensibilidades, efecto necesario del
    criterio 1 y escenarios, sobre el pricing VIGENTE y el test combinado sin E.
    No lee `y`."""
    parts = []
    disp: dict[str, Any] = {}
    for name, fold in FOLDS.items():
        _, test = fold_masks(fr, fold)
        te = fr[test & ~fr["excl"].to_numpy()]
        parts.append(te)
        p = p_home_fast(*base_lambdas(te))
        disp[name] = _disp(p)
    comb = pd.concat(parts)
    lh, la = base_lambdas(comb)
    p0 = p_home_fast(lh, la)
    disp["combinado"] = _disp(p0)
    h = 1e-3
    dp_home_g = (p_home_fast(lh, la * math.exp(-h)) - p_home_fast(lh, la * math.exp(h))) / (2 * h)   # d/d(-log lam_a)
    dp_away_g = (p_home_fast(lh * math.exp(h), la) - p_home_fast(lh * math.exp(-h), la)) / (2 * h)   # d/d log lam_h
    mg0, tt0 = score_dists(lh, la)
    mgm, ttm = score_dists(lh * math.exp(-h), la * math.exp(-h))
    mgp, ttp = score_dists(lh * math.exp(h), la * math.exp(h))
    sens_total = (p_over_from(ttp, 6.5) - p_over_from(ttm, 6.5)) / (2 * h)
    sens_puck = ((p_cover_from(score_dists(lh * math.exp(h), la)[0], -1.5)
                  - p_cover_from(score_dists(lh * math.exp(-h), la)[0], -1.5)) / (2 * h))
    s = 0.5 * (dp_home_g + dp_away_g)
    gain_per_r2 = np.mean(s ** 2 / (2.0 * p0 * (1.0 - p0)))
    r_needed = math.sqrt(IMPROVEMENT_MARGIN / gain_per_r2)
    rng = np.random.default_rng(SEED)
    esc: dict[str, Any] = {}
    for sigma in SIGMAS_Q:
        qh = rng.normal(0.0, sigma, len(comb))
        qa = rng.normal(0.0, sigma, len(comb))
        f_h = np.clip(1.0 - qh / ONE_MINUS_L_SCENARIO, 1 - BOUND, 1 + BOUND)
        f_a = np.clip(1.0 - qa / ONE_MINUS_L_SCENARIO, 1 - BOUND, 1 + BOUND)
        pt = p_home_fast(np.maximum(0.1, lh * f_a), np.maximum(0.1, la * f_h))
        kl = tilt._kl_bernoulli(pt, p0)
        var = tilt._var_delta_bernoulli(pt, p0)
        esc[str(sigma)] = {"rms_dq": float(np.sqrt(np.mean((qh - qa) ** 2))),
                           "delta_rms_p": float(np.sqrt(np.mean((pt - p0) ** 2))),
                           "ganancia_esperada": float(np.mean(kl)),
                           "ee_sin_agrupar": float(np.sqrt(np.mean(var) / len(comb)))}
    return {
        "dispersion_p_moneyline": disp,
        "lambda_medias_local_visitante": [float(np.mean(lh)), float(np.mean(la))],
        "sensibilidad_media": {
            "dP_portero_local_por_log_lambda": float(np.mean(dp_home_g)),
            "dP_portero_visitante_por_log_lambda": float(np.mean(dp_away_g)),
            "dP_menos5pct_lambda_visitante_pp": float(np.mean(
                p_home_fast(lh, la * 0.95) - p0) * 100.0),
            "dP_over6.5_por_log_lambda_comun": float(np.mean(sens_total)),
            "dP_cover_-1.5_por_log_lambda_local": float(np.mean(sens_puck))},
        "rms_log_lambda_necesario_criterio_1": r_needed,
        "rms_dq_necesario_con_beta_1": r_needed * ONE_MINUS_L_SCENARIO,
        "escenarios": esc,
        "aviso": "pricing vigente (AUD-001); difiere algo de la tabla de la Enmienda 3 (Enmienda 4)"}


def _disp(p: np.ndarray) -> dict:
    return {"media": float(np.mean(p)), "dt": float(np.std(p)),
            "p5": float(np.quantile(p, 0.05)), "p95": float(np.quantile(p, 0.95))} if len(p) else {}


# =========================================================== modo completo ==
def _veredicto(m2_ok: bool, m1_ok: bool) -> str:
    if m2_ok:
        return "ACEPTA"
    if m1_ok:
        return "RECHAZA, con senal en la cota superior"
    return "RECHAZA"


def run_nhl(results: list[dict], params: dict, rparams: dict, app: pd.DataFrame,
            failed_dates: list[str], data_root: Path) -> dict:
    rows2, rows1, info = attach_goalies(results, app)
    fr = build_frame(rows2, params, rparams, failed_dates, with_outcomes=True)
    apps = appearance_table(rows2)
    kms = {n: k_moments(apps, f["train_end"]) for n, f in FOLDS.items()}
    out: dict[str, Any] = {"emparejamiento": {k: v for k, v in info.items() if k not in _INFO_LISTAS},
                           "k_momentos": kms}
    if any(km["k"] is None for km in kms.values()):
        out["veredicto"] = "RECHAZA"
        out["motivo"] = ("tau^2 <= 0 en alguna particion: sin varianza de talento medible "
                         "(seccion 4); no hay calificacion q")
        return out
    k_by = {n: float(km["k"]) for n, km in kms.items()}
    ok_rows = ~fr["excl"].to_numpy()
    ml_ok = fr["y"].isin([0.0, 1.0]).to_numpy()

    # Paridad con el motor: base y T (M1 y M2) con beta_C, k_C. Se ejecuta tras
    # estimar beta_C (mas abajo); la base ya se comprueba aqui.
    assert_parity(rows2, rows1, params, rparams, fr, PROBE_BETA, k_by["C"], label="base",
                  base_only=True)

    res: dict[str, Any] = {a: {"folds": {}} for a in ARMS}
    a_by: dict[str, float] = {}
    pieces: dict[str, list[pd.DataFrame]] = {a: [] for a in ARMS}
    beta_by: dict[str, dict[str, float]] = {a: {} for a in ARMS}
    for name, fold in FOLDS.items():
        train_m, test_m = fold_masks(fr, fold)
        tr = fr[train_m & ok_rows & ml_ok].reset_index(drop=True)
        te = fr[test_m & ok_rows].reset_index(drop=True)
        k = k_by[name]
        a0 = fit_a(tr)
        a_by[name] = a0
        pb = market_probs(*base_lambdas(te))
        pc = market_probs(*control_lambdas(te, a0))
        outc = outcomes_of(te)
        for arm in ARMS:
            beta = fit_beta(tr, arm, k)
            beta_by[arm][name] = beta
            pt = market_probs(*treat_lambdas(te, arm, k, beta))
            aff = affected_mask(te, arm, k)
            ml = np.isin(outc["ml"], (0.0, 1.0))
            ll = {tag: ll_per_game(p["ml"][ml], outc["ml"][ml]) for tag, p in
                  (("base", pb), ("T", pt), ("C", pc))}
            d_aff = (ll["T"] - ll["base"])[aff[ml]]
            res[arm]["folds"][name] = {
                "k": k, "beta": beta, "a_control": a0,
                "n_train": int(len(tr)), "n_test": int(ml.sum()),
                "n_afectados": int(aff[ml].sum()),
                "delta_ll_afectados": float(d_aff.mean()) if len(d_aff) else None,
                "delta_ll_universo": float((ll["T"] - ll["base"]).mean()),
                "ll_T": float(ll["T"].mean()), "ll_C": float(ll["C"].mean()),
                "ll_base": float(ll["base"].mean()),
                "bias_base": bias_of(pb["ml"][ml], outc["ml"][ml]),
                "bias_T": bias_of(pt["ml"][ml], outc["ml"][ml]),
                "bias_C": bias_of(pc["ml"][ml], outc["ml"][ml])}
            piece = te.copy()
            piece["aff"] = aff
            piece["fold"] = name
            for key in pb:
                piece[f"b_{key}"], piece[f"t_{key}"], piece[f"c_{key}"] = pb[key], pt[key], pc[key]
            pieces[arm].append(piece)

    # Paridad del brazo T con beta_C y k_C, M1 y M2 (aserto 2), cada uno con su beta.
    for arm in ARMS:
        assert_parity(rows2, rows1, params, rparams, fr, beta_by[arm]["C"], k_by["C"],
                      label=f"T con beta_C de {arm}", arms=(arm,))

    for arm in ARMS:
        out_arm = _criterios(pieces[arm], res[arm], beta_by[arm])
        res[arm].update(out_arm)
        res[arm]["secundarios"] = _secundarios(arm, fr, ok_rows, ml_ok, pieces[arm], k_by,
                                               beta_by[arm], rows2, data_root, rparams)
    out.update(res)
    out["veredicto"] = _veredicto(res["M2"]["acepta"], res["M1"]["acepta"])
    out["a_control_por_particion"] = a_by
    out["beta_por_particion"] = beta_by
    return out


def _criterios(parts: list[pd.DataFrame], arm_out: dict, betas: dict[str, float]) -> dict:
    te = pd.concat(parts).reset_index(drop=True)
    ml = te["y"].isin([0.0, 1.0]).to_numpy()
    y = te["y"].to_numpy()
    ll_b = ll_per_game(te["b_ml"].to_numpy()[ml], y[ml])
    ll_t = ll_per_game(te["t_ml"].to_numpy()[ml], y[ml])
    ll_c = ll_per_game(te["c_ml"].to_numpy()[ml], y[ml])
    dates = te["date"].to_numpy()[ml]
    aff = te["aff"].to_numpy()[ml]
    d1 = (ll_t - ll_b)[aff]
    boot1 = bootstrap_por_fecha(dates[aff], d1, margen=IMPROVEMENT_MARGIN)
    d5 = ll_t - ll_c
    boot5 = bootstrap_por_fecha(dates, d5, margen=0.0)
    # Criterio 6 (ambiguedad 9): vista con empates, media por partido sobre la
    # concatenacion de las dos lineas de cada mercado.
    c6: dict[str, Any] = {}
    for fam, lines in (("totals", TOTAL_LINES), ("spreads", SPREAD_LINES)):
        diffs, ds, per_line = [], [], {}
        for line in lines:
            key = f"{fam}@{line}"
            yy = (te["total"].to_numpy() > line) if fam == "totals" else (te["margin"].to_numpy() > -line)
            d = ll_per_game(te[f"t_{key}"].to_numpy(), yy.astype(float)) - ll_per_game(
                te[f"b_{key}"].to_numpy(), yy.astype(float))
            diffs.append(d)
            ds.append(te["date"].to_numpy())
            per_line[str(line)] = float(d.mean())
        cat, dcat = np.concatenate(diffs), np.concatenate(ds)
        c6[fam] = {"delta_ll_media": float(cat.mean()), "por_linea": per_line,
                   "bootstrap": bootstrap_por_fecha(dcat, cat, margen=0.0)}
    ece_b = float(expected_calibration_error(te["b_ml"].to_numpy()[ml].tolist(), y[ml].tolist()))
    ece_t = float(expected_calibration_error(te["t_ml"].to_numpy()[ml].tolist(), y[ml].tolist()))
    folds = arm_out["folds"]
    crit = {
        "1_delta_afectados_combinado_le_-0.002": bool(len(d1) and d1.mean() <= -IMPROVEMENT_MARGIN),
        "2_delta_afectados_negativo_en_cada_particion": all(
            f["delta_ll_afectados"] is not None and f["delta_ll_afectados"] < 0 for f in folds.values()),
        "3_ece_T_no_empeora": ece_t <= ece_b,
        "4_beta_positivo_en_las_tres_particiones": all(b > 0 for b in betas.values()),
        "5_T_bate_control": bool(ll_t.mean() < ll_c.mean()),
        "6a_totales_no_empeora": c6["totals"]["delta_ll_media"] <= 0,
        "6b_spreads_no_empeora": c6["spreads"]["delta_ll_media"] <= 0}
    return {"criterios": crit, "acepta": all(crit.values()),
            "combinado": {
                "n_test": int(ml.sum()), "n_afectados": int(aff.sum()),
                "delta_ll_afectados": float(d1.mean()) if len(d1) else None,
                "bootstrap_delta_afectados": boot1,
                "delta_ll_universo": float((ll_t - ll_b).mean()),
                "T_menos_C": float(d5.mean()), "bootstrap_T_menos_C": boot5,
                "criterio_6": c6, "ece_base": ece_b, "ece_T": ece_t,
                "ll_base": float(ll_b.mean()), "ll_T": float(ll_t.mean()), "ll_C": float(ll_c.mean())}}


def _informe_sin_pretemporada(t: pd.DataFrame, y: np.ndarray) -> dict:
    """Informe 8: la estimacion por mes (septiembre) NO cambia; se anade la
    concordancia con `game_type` (1 = pretemporada) donde la aparicion unida lo
    trae. No elige entre mes y `game_type` como criterio."""
    aff = t["aff"].to_numpy()
    est_pre = (t["date"].str[5:7] == "09").to_numpy()
    d = ll_per_game(t["t_ml"].to_numpy(), y) - ll_per_game(t["b_ml"].to_numpy(), y)
    sel = aff & ~est_pre
    gt = t["game_type"] if "game_type" in t.columns else pd.Series([None] * len(t), index=t.index)
    has = gt.notna().to_numpy()
    real_pre = (pd.to_numeric(gt, errors="coerce") == 1).to_numpy()
    diff = has & (est_pre != real_pre)
    conc = {"n_con_game_type": int(has.sum()), "sin_game_type": int((~has).sum()),
            "coinciden": int((has & ~diff).sum()), "difieren": int(diff.sum()),
            "estimadas_pretemporada_por_mes_pero_game_type_no_1": int((has & est_pre & ~real_pre).sum()),
            "game_type_1_pero_no_septiembre": int((has & ~est_pre & real_pre).sum()),
            "afectados_difieren": int((diff & aff).sum())}
    return {"nota": "pretemporada estimada por el mes (septiembre); ambiguedad 11",
            "n": int(sel.sum()), "delta_ll_afectados": float(d[sel].mean()) if sel.any() else None,
            "concordancia_con_game_type": conc}


def _secundarios(arm: str, fr: pd.DataFrame, ok_rows: np.ndarray, ml_ok: np.ndarray,
                 parts: list[pd.DataFrame], k_by: dict[str, float], betas: dict[str, float],
                 rows: list[dict], data_root: Path, rparams: dict) -> dict:
    """Informes de la seccion 11 y 11.11-11.13. No deciden: cada uno va
    protegido por `_safe_informe`."""
    te = pd.concat(parts).reset_index(drop=True)
    ml = te["y"].isin([0.0, 1.0]).to_numpy()
    y = te["y"].to_numpy()[ml]
    t = te[ml].reset_index(drop=True)
    sec: dict[str, Any] = {}

    def i1_bias() -> dict:
        return {n: bias_of(g["b_ml"].to_numpy(), g["y"].to_numpy()) for n, g in t.groupby("fold")}

    def i2_joint() -> dict:
        res = {}
        for name, fold in FOLDS.items():
            train_m, _ = fold_masks(fr, fold)
            tr = fr[train_m & ok_rows & ml_ok].reset_index(drop=True)
            a, b = fit_a_beta(tr, arm, k_by[name])
            res[name] = {"a": a, "beta": b}
        return res

    def i3_profile() -> dict:
        res = {}
        for name, fold in FOLDS.items():
            train_m, _ = fold_masks(fr, fold)
            tr = fr[train_m & ok_rows & ml_ok].reset_index(drop=True)
            yy = tr["y"].to_numpy()
            res[name] = [{"beta": b, "log_loss_train": float(np.mean(ll_per_game(
                p_home_fast(*treat_lambdas(tr, arm, k_by[name], b)), yy)))} for b in GRID_BETA]
        return res

    def i4_b2b() -> dict:
        ll_t = ll_per_game(t["t_ml"].to_numpy(), y)
        ll_b = ll_per_game(t["b_ml"].to_numpy(), y)
        alg = (t["b2b_h"] | t["b2b_a"]).to_numpy()
        return {"ningun_equipo_b2b": {"n": int((~alg).sum()), "delta_ll": float((ll_t - ll_b)[~alg].mean())},
                "algun_equipo_b2b": {"n": int(alg.sum()), "delta_ll": float((ll_t - ll_b)[alg].mean())},
                "nota": "si la ganancia vive en los b2b, parte puede ser fatiga de jugadores de campo"}

    def i5_real_vs_proxy() -> dict | None:
        if arm != "M1":
            return None
        both = (t["real_h"].notna() & t["proxy_h"].notna()) | (t["real_a"].notna() & t["proxy_a"].notna())
        dif = ((t["real_h"] != t["proxy_h"]) & t["real_h"].notna() & t["proxy_h"].notna()) | (
            (t["real_a"] != t["proxy_a"]) & t["real_a"].notna() & t["proxy_a"].notna())
        sel = (both & dif).to_numpy()
        d = ll_per_game(t["t_ml"].to_numpy(), y) - ll_per_game(t["b_ml"].to_numpy(), y)
        por_fold = {n: _tasa_titular_vs_proxy(g) for n, g in t.groupby("fold")}
        return {"n_partidos_con_diferencia": int(sel.sum()),
                "delta_ll": float(d[sel].mean()) if sel.any() else None,
                "tasa_por_particion": por_fold}

    def i6_season() -> dict:
        d = ll_per_game(t["t_ml"].to_numpy(), y) - ll_per_game(t["b_ml"].to_numpy(), y)
        season = t["date"].apply(rmnhl._nhl_season_label)
        return {s: {"n": int(len(g)), "delta_ll": float(d[g.index].mean()),
                    "regimen_atipico": s in ("2019-20", "2020-21")} for s, g in t.groupby(season)}

    def i7_totals_beta() -> dict:
        res = {}
        for name, fold in FOLDS.items():
            train_m, _ = fold_masks(fr, fold)
            tr_all = fr[train_m & ok_rows].reset_index(drop=True)
            res[name] = {"beta_totales": fit_beta_totals(tr_all, arm, k_by[name]),
                         "beta_moneyline": betas[name]}
        return res

    def i8_sin_pretemporada() -> dict:
        return _informe_sin_pretemporada(t, y)

    def i9_linea() -> dict | None:
        if arm != "M2":
            return None
        fold_c = FOLDS["C"]
        train_m, test_m = fold_masks(fr, fold_c)
        tec = fr[test_m & ok_rows].reset_index(drop=True)
        lam_t = treat_lambdas(tec, "M2", k_by["C"], betas["C"])
        return informe_linea_capturada(rows, tec, lam_t, data_root, rparams)

    def i10_cobertura() -> dict:
        return {"k_por_particion": k_by,
                "q_resumen_test": {a: {"rms": _rms(np.r_[arm_qf(t, a, k_by["C"], 1.0)[0],
                                                          arm_qf(t, a, k_by["C"], 1.0)[1]])}
                                   for a in ARMS}}

    def i11_auc() -> dict:
        sc = {"base": t["b_ml"].to_numpy(), "T": t["t_ml"].to_numpy(), "C": t["c_ml"].to_numpy()}
        comb = _auc_boot(t["date"].to_numpy(), y, sc, [("T", "base")])
        por = {n: {k: float(roc_auc_score(y[g.index], g[c].to_numpy()))
                   for k, c in (("base", "b_ml"), ("T", "t_ml"), ("C", "c_ml"))}
               for n, g in t.groupby("fold")}
        return {"combinado": comb, "por_particion": por}

    def i12_slope() -> dict:
        res = {}
        for n, g in list(t.groupby("fold")) + [("combinado", t)]:
            yy = g["y"].to_numpy()
            res[n] = {m: {"bias": bias_of(g[c].to_numpy(), yy),
                          "pendiente": _pendiente_calibracion(g[c].to_numpy(), yy)}
                      for m, c in (("base", "b_ml"), ("T", "t_ml"), ("C", "c_ml"))}
        return res

    for nombre, fn in (("1_bias", i1_bias), ("2_estimacion_conjunta", i2_joint),
                       ("3_perfil_beta", i3_profile), ("4_b2b", i4_b2b),
                       ("5_titular_real_vs_proxy", i5_real_vs_proxy), ("6_por_temporada", i6_season),
                       ("7_beta_totales", i7_totals_beta), ("8_sin_pretemporada", i8_sin_pretemporada),
                       ("9_linea_capturada", i9_linea), ("10_cobertura", i10_cobertura),
                       ("11_auc", i11_auc), ("12_sesgo_y_pendiente", i12_slope)):
        sec[nombre] = _safe_informe(nombre, fn)
    return sec


# ====================================================================== main ==
def _check_pre_provenance(pre: dict, now: dict, head_now: str | None, params_now: dict,
                          e_now: list[int]) -> None:
    for key in ("results_nhl.csv", "goalies_nhl.csv", "failed_dates", "checkpoint", "ratings.yaml"):
        a = (pre.get("hashes", {}).get(key) or {}).get("sha256")
        b = (now.get(key) or {}).get("sha256")
        if a is None or b is None or a != b:
            raise SystemExit(f"HASH DE ENTRADA CAMBIO ({key}): --pre-json {a} vs ahora {b}. "
                             "El modo completo aborta: no se ha medido nada.")
    if pre.get("hashes", {}).get("odds_cierre_nhl") != now.get("odds_cierre_nhl"):
        raise SystemExit("HASH DE ENTRADA CAMBIO (cuotas de cierre NHL). El modo completo aborta.")
    if pre.get("git_head") is None or head_now is None or pre["git_head"] != head_now:
        raise SystemExit(f"HEAD DE GIT CAMBIO: --pre-json {pre.get('git_head')} vs {head_now}. Aborta.")
    if (pre.get("git_status_porcelain") or "").strip() != "":
        raise SystemExit("--pre-json registra un arbol git sucio. El modo completo aborta.")
    if pre.get("parametros_resueltos") != params_now:
        raise SystemExit("PARAMETROS RESUELTOS DISTINTOS de los de --pre-json. Aborta.")
    if pre.get("E", {}).get("lista_E_posiciones") != e_now:
        raise SystemExit("LISTA E DISTINTA de la de --pre-json. El modo completo aborta.")


def _data_root_error(args: argparse.Namespace) -> str | None:
    """Reglas de `--data-root` (instantanea congelada, decision 2026-10-01): en
    `--pre` y en el modo completo debe pasarse explicitamente y no ser la raiz
    viva del repositorio ni ningun checkout git (existe `<root>/.git`); el modo
    completo rechaza un `--out` ya existente. `--parity-only` conserva el default."""
    if args.parity_only:
        return None
    if args.data_root is None:
        return "--data-root es obligatorio en --pre y en el modo completo (instantanea congelada)."
    if Path(args.data_root).resolve() == Path(DEFAULT_ROOT).resolve():
        return ("--data-root no puede ser la raiz viva del repositorio (sqp.config.ROOT): "
                "usa la instantanea congelada.")
    if (Path(args.data_root) / ".git").exists():
        return ("--data-root es un checkout git (existe .git): puede ser la raiz viva de "
                "produccion u otro arbol; usa una instantanea de datos.")
    if not args.pre and args.out is not None and Path(args.out).exists():
        return f"--out ya existe ({args.out}): el modo completo es UNA SOLA EJECUCION; no se sobrescribe."
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pre", action="store_true")
    ap.add_argument("--parity-only", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--pre-json", type=Path, default=None)
    ap.add_argument("--data-root", type=Path, default=None)
    args = ap.parse_args()
    if args.pre and args.parity_only:
        ap.error("--pre y --parity-only son mutuamente excluyentes.")
    if not args.parity_only and args.out is None:
        ap.error("--out es obligatorio salvo en --parity-only.")
    if args.pre_json and (args.pre or args.parity_only):
        ap.error("--pre-json solo aplica al modo completo.")
    if not args.pre and not args.parity_only and args.pre_json is None:
        ap.error("--pre-json es obligatorio en el modo completo.")
    err = _data_root_error(args)
    if err:
        ap.error(err)
    if args.data_root is None:
        args.data_root = DEFAULT_ROOT                     # solo --parity-only

    t0 = time.perf_counter()
    out: dict[str, Any]
    if args.pre:
        out = {"modo": "pre (sin marcadores ni goals_against)", **informe_pre(args.data_root)}
    elif args.parity_only:
        results, params, rparams = load_league(args.data_root)
        paths = input_paths(args.data_root)
        app = read_appearances(paths["goalies_nhl.csv"])
        failed = [str(e["date"]) for e in read_failed_dates(paths["failed_dates"])]
        rows2, rows1, _ = attach_goalies(results, app)
        fr = build_frame(rows2, params, rparams, failed, with_outcomes=True)
        assert_parity(rows2, rows1, params, rparams, fr, PROBE_BETA, PROBE_K, label="parity-only")
        out = {"modo": "parity-only",
               "resultado": (f"PARIDAD OK (n={len(fr)}, beta={PROBE_BETA}, k={PROBE_K}, "
                             "base + T de M1 + T de M2; moneyline, puck line y totales a 1e-12)")}
    else:
        _check_git_clean(git_status_full(_WORKTREE_ROOT))
        pre = json.loads(args.pre_json.read_text(encoding="utf-8"))
        results, params, rparams = load_league(args.data_root)
        paths = input_paths(args.data_root)
        app = read_appearances(paths["goalies_nhl.csv"])
        failed = read_failed_dates(paths["failed_dates"])
        failed_dates = [str(e["date"]) for e in failed]
        rows2, _, _ = attach_goalies(results, app)
        dates = [str(r.get("date", ""))[:10] for r in rows2]
        e1, e2 = exclusion_set(dates, [r["home"] for r in rows2], [r["away"] for r in rows2],
                               failed_dates)
        e_now = [int(i) for i in np.flatnonzero((e1 | e2)) if i >= WARMUP]
        _check_pre_provenance(
            pre, procedencia_hashes(args.data_root), git_head(_WORKTREE_ROOT),
            {k: rparams.get(k) for k in (*EXPECTED_PARAMS, *ABSENT_OR_ZERO, *ABSENT)}, e_now)
        out = {"procedencia": procedencia_hashes(args.data_root),
               LEAGUE: run_nhl(results, params, rparams, app, failed_dates, args.data_root)}
    out["segundos"] = time.perf_counter() - t0
    text = _dump(out)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
