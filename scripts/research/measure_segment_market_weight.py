"""Medicion del pre-registro «peso del mercado por segmento» (2026-10-13).

Ver `docs/research/2026-10-13-preregistro-peso-mercado-por-segmento.md`
(aprobado, seccion 11 = contrato de este script). Ese documento MANDA sobre
este docstring: aqui solo se resumen los modos y se documentan las
AMBIGUEDADES del contrato con la decision tomada.

## Que mide

La probabilidad servida es `p = (1 - s)*cal(p_adj) + s*fair` con `s = 0,5`
global. H1: un peso `s_k` por segmento, ajustado en `start_time <= T0` y
aplicado en `(T0, T1]`, tiene menor Brier que `s = 0,5`. NO es un test de
rentabilidad.

## Modos (seccion 11)

  --contar [--no-log]   Solo recuentos. NUNCA emite y, p, s_k ni Brier.
                         Anade una linea a `<preregistro>.contar.jsonl`
                         (append-only) salvo `--no-log` (diagnostico; no
                         cuenta para fijar T1). Sin T0 imprime n = 0.
  --ajustar             Una vez, con E >= T0 + 14 d. Escribe `.sk.json`.
  --medir --t1 <ISO>    Una vez. Exige addendum de T1, `.sk.json` commiteado
                         y n(T1) >= 3.300.

## Ambiguedades resueltas

1. **Addendum de T1 (7.4/11).** Dos lineas literales al INICIO de linea,
   `T1 fijado = <ISO>` y `commit del registro = <sha>`; las citas en prosa o
   entre comillas inversas (7.4) y los ISO ilegibles no cuentan; varios T1
   distintos abortan.
2. **Tabla de regimen de `s` (Addendum 2026-10-13 (1), manda).** Fuente de
   `s_t` por fila: columna `market_shrink` si existe y es finita > tabla >
   desconocido (se excluye y se cuenta). Tabla: entrada implicita
   `0.5 global desde 2026-06-21T00:00:00+00:00` + lineas de la seccion
   «Addenda» con el formato literal; gana `desde` mas reciente respecto del
   `generated_at` y, a igual `desde`, el alcance `liga|mercado`. Una linea que
   empiece por `s servido` y no parsee aborta `--ajustar` y `--medir` (en
   `--contar` se informa). Discrepancia columna/tabla: se cuenta e informa.
3. **Fila con `generated_at` ilegible (4.1).** La seccion solo nombra
   `start_time` ilegible; un `generated_at` ilegible tampoco permite probar
   «pregame», asi que se excluye y se cuenta junto a esa causa
   (`pregame_ilegible`).
4. **Conteos de exclusion mutuamente excluyentes.** Orden: identidad,
   resultado (void/push/half/otro), colapso, pregame, mercado invalido
   (AUD-003, ambiguedad 13), probabilidades presentes, `s_t` (=1 o
   desconocido), `p_cal` fuera de [0,1].
5. **«Picks sin graduar» (11).** Picks SERVIDOS (primera servida de
   `served_*.csv`, `start_time` en (T0, T1]) sin ninguna fila en el stream
   graduado. No depende de `result`.
6. **`_league_meta` y familias (4.3, 11).** `--ajustar` guarda en el
   `.sk.json` la correspondencia liga->familia usada y `--medir` la aplica;
   las ligas sin entrada usan el `_league_meta` vivo y se listan en
   `ligas_sin_entrada_en_mapa`. La procedencia registra ademas los hashes de
   blob de `daily.py` en H, HEAD y disco.
7. **`s~_F` fuera de [0,1] (5.2).** Solo `s~_G` y `s_k` se recortan segun la
   formula. Cuando una familia se usa como peso (segmento nuevo, 5.3) se
   recorta a [0,1] al aplicarla.
8. **`--ajustar` no sobreescribe.** Aborta si el `.sk.json` ya existe en disco
   o en HEAD (el documento solo dice «si esta commiteado»).
9. **IC de las sensibilidades.** H1, log loss, ROI, H2 y segmentos usan el
   bootstrap por evento del contrato (10.000, seed 42). S1-S7 son descriptivas
   y usan el IC de la media con error estandar CR1 por evento (para no
   repetir decenas de bootstraps de 10.000 replicas).
10. **S3 (10).** Reajuste sin las filas de MLB anteriores al 2026-09-26 y de
    NHL anteriores al 2026-09-30 (fechas de la seccion 10), por `generated_at`.
11. **Lectura de CSV.** `--ajustar`/`--medir` abortan ante cualquier
    `graded_*.csv` ilegible (parseo, E/S, codificacion); `--contar` informa.
    `league` sale del nombre del fichero y nunca se renombra ni toca nada.
12. **`--seed`/`--n-boot` distintos de 42/10.000** no abortan: se marcan en la
    procedencia (`difiere_de_lo_congelado`).
13. **AUD-003 (Addendum 2026-10-17).** La fila de decision (primera servida)
    de `nhl|h2h` con `generated_at` anterior a 2026-10-16T12:56:03Z
    (ffc5ad3) se excluye y se cuenta (`mercado_invalido_aud003`) en ajuste y
    evaluacion, igual en todos los modos; el pick no se sustituye por una
    servida posterior. En S1 (sin colapsar) el filtro actua por fila.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import pandas as pd

from sqp.config import ROOT as DEFAULT_ROOT
from sqp.evaluation.bootstrap import cluster_bootstrap_ci
from sqp.evaluation.edge_information import one_row_per_pick
from sqp.evaluation.labels import instantes_utc
from sqp.evaluation.model_vs_market import _EPS, flattened_segments, log_loss_safe
from sqp.markets.settlement_math import is_quarter_line

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]

# Constantes congeladas por el pre-registro (seccion indicada).
TAG_NAME = "prereg-peso-mercado-h"                 # 11
T0_PATHSPEC = "docs/research/*resultado-el-modelo-manda*.md"   # 3.1
TAU = 0.25                                          # 5.2
MIN_EVENTS_NODE = 30                                # 5.2
MARGIN_DAYS = 14                                    # 5.4 / 7.4
N_REQUIRED = 3300                                   # 7.3
MIN_SEGMENT_EVENTS_EVAL = 200                       # 6.2
ALPHA = 0.05
SEED = 42                                           # 11
N_BOOT = 10_000                                     # 11
BASE_SHRINK = 0.5
ROI_MIN_EDGE = 0.02                                 # 8
ROI_MAX_EDGE = 0.075                                # 8
DEFAULT_PREREGISTRO = (DEFAULT_ROOT / "docs" / "research"
                       / "2026-10-13-preregistro-peso-mercado-por-segmento.md")
_GIT_STATUS_PATHS = ("src", "configs", "scripts/research")
_BLOBS = ("src/sqp/pipeline/probabilities.py", "src/sqp/evaluation/edge_information.py",
          "src/sqp/evaluation/bootstrap.py", "configs/default.yaml",
          "src/sqp/pipeline/daily.py")
_REGIME_CHANGES_PRE_T0 = {"mlb": "2026-09-26", "nhl": "2026-09-30"}   # 10, S3
_IDENTIDAD = ("event_id", "market", "selection")

# Addendum 2026-10-17 (AUD-003): `liga|mercado` cuyo `implied_probability_novig`
# es falso antes de un instante. Literal CONGELADO (no se importa del gate: una
# entrada nueva alli no puede cambiar esta poblacion sin su propio addendum).
# Un test fija que coincide con `sqp.risk.prediction_gate.INVALID_BEFORE`.
INVALID_BEFORE: dict[tuple[str, str], str] = {
    ("nhl", "h2h"): "2026-10-16T12:56:03+00:00",   # ffc5ad3
}

# Addendum 2026-10-18 (AUD-008, ronda audit-2026-10-18): las filas totals/spreads
# de linea de cuarto generadas antes de este instante (c578f52) se graduaron
# win/loss sin medias. Literal CONGELADO, como INVALID_BEFORE; un test fija que
# coincide con `sqp.settlement.quarter_line_fix.QUARTER_LINE_GRADING_FIXED_AT`.
QUARTER_LINE_INVALID_BEFORE = "2026-09-13T12:36:34+00:00"
_QUARTER_LINE_MARKETS = ("totals", "spreads")

# Addendum 2026-10-20 (`execution.books: [pinnacle]`): desde este instante (commit
# f92e8e1) `execution_price` es el precio de Pinnacle cuando cotiza la linea;
# antes repetia la mediana. Las metricas DESCRIPTIVAS de `execution_price` se
# informan tambien partidas por este corte (por `generated_at`). Literal
# CONGELADO. No toca seleccion, decision ni ningun criterio.
EXECUTION_REGIME_FROM = "2026-10-20T13:31:09+00:00"
EXECUTION_REGIMES = ("mediana_hasta_2026-10-20", "pinnacle_desde_2026-10-20", "sin_fecha")


def execution_regime(gen: pd.Series) -> np.ndarray:
    """Etiqueta de regimen de `execution_price` por fila (Addendum 2026-10-20)."""
    ts = pd.to_datetime(gen, errors="coerce", utc=True, format="mixed")
    corte = pd.Timestamp(EXECUTION_REGIME_FROM)
    return np.where(ts.isna(), EXECUTION_REGIMES[2],
                    np.where(ts >= corte, EXECUTION_REGIMES[1], EXECUTION_REGIMES[0]))
# Campos permitidos en la linea de `--contar` (11): nada que dependa de y/p/s_k.
CONTAR_CAMPOS = frozenset({
    "instante_ejecucion_utc", "head", "h", "t0", "t1_candidato",
    "n_eventos_evaluacion", "n_picks_evaluacion", "picks_sin_graduar_ventana",
    "market_shrink_efectivo", "market_shrink_tabla", "market_shrink_difiere",
    "sha256_csv", "via_resolucion_h", "errores_lectura_csv",
    "error_tabla_regimen"})


# ------------------------------------------------------------------- git --
def _git(args: list[str], cwd: Path) -> str | None:
    try:
        res = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                             text=True, encoding="utf-8", check=True, timeout=30)
        return res.stdout.strip()
    except Exception:  # noqa: BLE001 -- procedencia, no decide nada
        return None


# Auditoria audit-2026-10-18, AUD-017. `resolve_t0`/`resolve_h` SI deciden (si
# `--medir` puede correr), pero usaban `_git`, que convierte un timeout o un git
# que no arranca en `None`: con la maquina cargada, `git log` pasaba de 30 s y el
# script abortaba con "--medir exige T0 y no existe", un motivo FALSO (el test
# `test_medir_aborts_with_different_t1` fallo asi 1 de 3 veces). Aqui un fallo
# del ENTORNO se reintenta una vez con mas margen y, si persiste, aborta diciendo
# que fue git; solo un `returncode != 0` (ref inexistente) vale `None`.
_GIT_DECIDE_TIMEOUTS = (60, 180)


def _git_decide(args: list[str], cwd: Path) -> str | None:
    ultimo: Exception | None = None
    for limite in _GIT_DECIDE_TIMEOUTS:
        try:
            res = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                                 text=True, encoding="utf-8", check=True, timeout=limite)
            return res.stdout.strip()
        except subprocess.CalledProcessError:
            return None
        except (subprocess.TimeoutExpired, OSError) as exc:
            ultimo = exc
    raise SystemExit(f"git {args[0]} no respondio ({ultimo!r}); no se puede resolver "
                     "la procedencia. Es un fallo del entorno, no de T0/H. Aborta.")


def git_show_or_none(ref: str, relpath: str, cwd: Path) -> str | None:
    try:
        res = subprocess.run(["git", "show", f"{ref}:{relpath}"], cwd=str(cwd),
                             capture_output=True, text=True, encoding="utf-8",
                             check=True, timeout=30)
        return res.stdout
    except Exception:  # noqa: BLE001
        return None


def git_show_text(ref: str, relpath: str, cwd: Path) -> str:
    out = git_show_or_none(ref, relpath, cwd)
    if out is None:
        raise SystemExit(f"No se pudo leer {relpath!r} en {ref!r} con git show.")
    return out


def git_status_porcelain(cwd: Path, paths: tuple[str, ...]) -> str | None:
    try:
        res = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=str(cwd),
                             capture_output=True, text=True, encoding="utf-8",
                             check=True, timeout=30)
        return res.stdout
    except Exception:  # noqa: BLE001
        return None


def _relpath(path: Path, cwd: Path) -> str | None:
    try:
        return path.resolve().relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return None


def _parse_ts(value: object) -> pd.Timestamp | None:
    """Timestamp UTC (comparacion por instante, no por texto)."""
    if value is None:
        return None
    try:
        ts = pd.Timestamp(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    return ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")


def resolve_h(preregistro: Path, cwd: Path, tag: str = TAG_NAME) -> dict | None:
    """H (11): tag anotado, si no `git log --diff-filter=A` sobre el fichero.
    Aborta si los dos existen y difieren; `None` si ninguno resuelve."""
    h_tag = _git_decide(["rev-parse", f"{tag}^{{commit}}"], cwd)
    rel = _relpath(preregistro, cwd)
    h_fb = None
    if rel:
        out = _git_decide(["log", "--diff-filter=A", "--format=%H", "--", rel], cwd)
        lineas = [x for x in (out or "").splitlines() if x.strip()]
        h_fb = lineas[-1] if lineas else None   # la mas antigua
    if h_tag and h_fb and h_tag != h_fb:
        raise SystemExit(f"H por el tag {tag!r} ({h_tag}) y por el fallback "
                         f"({h_fb}) DIFIEREN. El script aborta (seccion 11).")
    h = h_tag or h_fb
    if h is None:
        return None
    return {"h": h, "via": "tag" if h_tag else "fallback"}


def resolve_t0(cwd: Path) -> dict | None:
    """T0 (3.1): committer date UTC del commit que AÑADE el unico fichero
    `docs/research/*resultado-el-modelo-manda*.md`. `None` si hay cero;
    aborta si hay mas de uno."""
    out = _git_decide(["log", "--diff-filter=A", "--name-only", "--format=@@%H %cI",
                "--", T0_PATHSPEC], cwd)
    if not out:
        return None
    ficheros: dict[str, tuple[str, str]] = {}
    actual: tuple[str, str] | None = None
    for linea in out.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if linea.startswith("@@"):
            sha, iso = linea[2:].split(" ", 1)
            actual = (sha, iso)
        elif actual is not None:
            ficheros[linea] = actual   # git log va de reciente a antiguo: gana el mas antiguo
    if not ficheros:
        return None
    if len(ficheros) > 1:
        raise SystemExit(f"Hay {len(ficheros)} ficheros de resultado de MM "
                         f"({sorted(ficheros)}); T0 no es unico. Aborta (seccion 3.1).")
    (fichero, (sha, iso)), = ficheros.items()
    t0 = _parse_ts(iso)
    if t0 is None:
        raise SystemExit(f"T0 ilegible ({iso!r}). Aborta.")
    return {"commit": sha, "t0": t0, "fichero": fichero}


def blob_hashes(h: str | None, head: str | None, cwd: Path) -> dict:
    out = {}
    for rel in _BLOBS:
        out[rel] = {"h": _git(["rev-parse", f"{h}:{rel}"], cwd) if h else None,
                    "head": _git(["rev-parse", f"{head}:{rel}"], cwd) if head else None,
                    "disco": _git(["hash-object", rel], cwd)}
    return out


# ------------------------------------------------------------ regimen de s --
_REGIMEN_LINEA = re.compile(
    r"s servido = (desconocido|[0-9]+(?:\.[0-9]+)?) \| desde = (\S+) \| "
    r"alcance = (global|[a-z0-9_]+\|[a-z0-9_]+)[ \t]*$")
BASE_DESDE = pd.Timestamp("2026-06-21T00:00:00+00:00")   # Addendum (1)


def parse_regime_table(doc_text: str | None) -> list[dict]:
    """Tabla de regimen de `s` (Addendum 2026-10-13 (1)): entrada implicita
    `0.5 global desde 2026-06-21` + las lineas de la seccion «Addenda», con el
    formato literal al INICIO de linea. Cualquier linea de esa seccion que
    empiece por `s servido` y no cumpla el formato aborta (nunca se ignora).
    `s = NaN` si el valor es `desconocido`."""
    tabla: list[dict] = [{"s": BASE_SHRINK, "desde": BASE_DESDE, "alcance": "global"}]
    texto = doc_text or ""
    m_sec = re.search(r"(?m)^## Addenda[ \t]*$", texto)
    if m_sec is None:
        return tabla
    for linea in texto[m_sec.end():].splitlines():
        if not linea.startswith("s servido"):
            continue
        m = _REGIMEN_LINEA.match(linea)
        desde = (_parse_ts(m.group(2))
                 if m and re.search(r"(Z|[+-]\d\d:\d\d)$", m.group(2)) else None)
        if m is None or desde is None:
            raise SystemExit(f"Tabla de regimen de s: linea con formato invalido: {linea!r}. "
                             "Aborta (Addendum 2026-10-13 (1)).")
        if m.group(1) == "desconocido":
            s = float("nan")
        else:
            s = float(m.group(1))
            if not 0.0 <= s <= 1.0:
                raise SystemExit(f"Tabla de regimen de s: valor fuera de [0,1]: {linea!r}.")
        alcance = m.group(3)
        if alcance != "global":
            liga = alcance.split("|", 1)[0]
            circuito = tennis_circuit(liga)
            if circuito is not None and circuito != liga:
                raise SystemExit(f"Tabla de regimen de s: el alcance de tenis debe ser el "
                                 f"circuito ({circuito}|<mercado>), no {alcance!r}. Aborta "
                                 "(Addendum 2026-10-13 (2)).")
        tabla.append({"s": s, "desde": desde, "alcance": alcance})
    return tabla


def load_regime_table(preregistro: Path, cwd: Path) -> list[dict]:
    rel = _relpath(preregistro, cwd)
    texto = git_show_or_none("HEAD", rel, cwd) if rel else None
    if texto is None:
        raise SystemExit(f"No se pudo leer el pre-registro {preregistro} en HEAD (fuera del "
                         "repositorio o no commiteado): la tabla de regimen de s no es "
                         "legible (Addendum 2026-10-13 (2)).")
    return parse_regime_table(texto)


def _desde_key(e: dict) -> tuple[pd.Timestamp, bool]:
    return e["desde"], e["alcance"] != "global"


def regime_s(gen: pd.Series, seg: pd.Series, table: list[dict]) -> np.ndarray:
    """`s_t` por la TABLA (4.4). Gana la entrada aplicable con `desde` mas
    reciente; a igual `desde`, la de alcance `liga|mercado`. NaN = ninguna
    aplica (desconocido)."""
    s = np.full(len(gen), np.nan, dtype=float)
    seg_a = seg.to_numpy()
    for e in sorted(table, key=_desde_key):
        aplica = (np.ones(len(gen), dtype=bool) if e["alcance"] == "global"
                  else (seg_a == e["alcance"]))
        aplica = aplica & (gen >= e["desde"]).to_numpy(dtype=bool)
        s[aplica] = e["s"]
    return s


def last_global_s(table: list[dict], at: pd.Timestamp) -> float:
    """Ultimo valor GLOBAL de la tabla vigente en `at`."""
    vig = [e for e in table if e["alcance"] == "global" and e["desde"] <= at]
    vig.sort(key=_desde_key)
    return float(vig[-1]["s"])


# ----------------------------------------------------------- segmento/familia --
def tennis_circuit(league: str) -> str | None:
    lg = league.lower()
    if lg == "atp" or lg.startswith("tennis_atp"):
        return "tennis_atp"
    if lg == "wta" or lg.startswith("tennis_wta"):
        return "tennis_wta"
    return None


def segment_id(league: object, market: object) -> str:
    """`liga|mercado`; torneos de tenis agrupados por circuito (4.3)."""
    lg = str(league).lower()
    return f"{tennis_circuit(lg) or lg}|{market}"


@functools.lru_cache(maxsize=None)
def _family_of_league(league: str) -> str | None:
    try:
        from sqp.pipeline.daily import _league_meta
        fam = _league_meta(league).get("family")
    except Exception:  # noqa: BLE001 -- liga sin familia legible -> global
        return None
    return str(fam) if fam else None


def family_id(league: object, market: object) -> str | None:
    """`familia|mercado` (4.3); `None` si la liga no tiene familia legible."""
    fam = _family_of_league(str(league).lower())
    return f"{fam}|{market}" if fam else None


# ---------------------------------------------------------------- lectura --
def _paths(data_root: Path, prefix: str) -> list[Path]:
    return sorted((data_root / "data" / "calibration").glob(f"{prefix}_*.csv"))


def graded_paths(data_root: Path) -> list[Path]:
    return _paths(data_root, "graded")


def load_real_csvs(data_root: Path, prefix: str, strict: bool) -> tuple[pd.DataFrame, list[dict]]:
    """`<prefix>_<liga>.csv` con `data_label == "real"`, SIN la cuarentena de
    `ServedStore._load` (no renombra ni toca nada en `data/`). `league` sale del
    nombre del fichero, como `load_all_graded`. Un fichero ilegible (parseo,
    E/S o codificacion) ABORTA con `strict` (--ajustar/--medir); sin `strict`
    (--contar) se informa y se sigue. Un fichero vacio se trata como vacio."""
    frames, errores = [], []
    for p in _paths(data_root, prefix):
        try:
            df = pd.read_csv(p)
        except pd.errors.EmptyDataError:
            continue
        except (pd.errors.ParserError, OSError, UnicodeDecodeError, ValueError) as exc:
            errores.append({"fichero": str(p), "error": str(exc)})
            continue
        if df.empty:
            continue
        df["league"] = p.stem.replace(f"{prefix}_", "", 1)
        frames.append(df)
    if errores and strict:
        raise SystemExit(f"Ficheros {prefix}_*.csv ilegibles: {errores}. El modo aborta "
                         "(no se mide sobre una lectura parcial; no se toca ningun fichero).")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not df.empty and "data_label" in df.columns:
        df = df[df["data_label"].astype(str) == "real"].copy()
    return df, errores


def load_graded_real(data_root: Path, strict: bool = False) -> tuple[pd.DataFrame, list[dict]]:
    return load_real_csvs(data_root, "graded", strict)


def load_served_real(data_root: Path, strict: bool = False) -> tuple[pd.DataFrame, list[dict]]:
    return load_real_csvs(data_root, "served", strict)


def csv_provenance(data_root: Path) -> list[dict]:
    out: list[dict] = []
    for p in [*_paths(data_root, "graded"), *_paths(data_root, "served")]:
        h = hashlib.sha256()
        saltos = 0
        try:
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
                    saltos += chunk.count(b"\n")
        except OSError as exc:
            out.append({"fichero": str(p), "error": str(exc)})
            continue
        out.append({"fichero": str(p), "sha256": h.hexdigest(), "filas": max(saltos - 1, 0)})
    return out


def _is_blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "")


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(float("nan"), index=df.index, dtype=float)


# --------------------------------------------------------------- poblacion --
def _key_strings(df: pd.DataFrame) -> pd.Series:
    linea = _num(df, "line").round(4) + 0.0
    return (df["event_id"].astype(str) + "|" + df["market"].astype(str) + "|"
            + df["selection"].astype(str) + "|"
            + linea.map(lambda v: "" if pd.isna(v) else str(v)))


def count_sin_graduar(served: pd.DataFrame, graded_all: pd.DataFrame,
                      t0: pd.Timestamp, t1: pd.Timestamp) -> int:
    """Picks servidos (primera servida, `start_time` en (T0, T1]) sin ninguna
    fila en el stream graduado. No depende de `result`."""
    if served.empty or not {*_IDENTIDAD, "start_time"}.issubset(served.columns):
        return 0
    inc = _is_blank(served["event_id"]) | _is_blank(served["market"]) \
        | _is_blank(served["selection"])
    primeras = one_row_per_pick(served[~inc])
    st = instantes_utc(primeras["start_time"], index=primeras.index)
    sel = primeras[((st > t0) & (st <= t1)).to_numpy()]
    if sel.empty:
        return 0
    if graded_all.empty or not set(_IDENTIDAD).issubset(graded_all.columns):
        return int(len(sel))
    return int((~_key_strings(sel).isin(set(_key_strings(graded_all)))).sum())


def _fam_lookup(league: object, market: object, mapa: dict[str, str | None] | None,
                nuevas: set[str]) -> str | None:
    lg = str(league).lower()
    if mapa is not None and lg in mapa:
        fam = mapa[lg]
    else:
        fam = _family_of_league(lg)
        if mapa is not None:
            nuevas.add(lg)
    return f"{fam}|{market}" if fam else None


def reconstruct_p_cal(cal: np.ndarray, fair: np.ndarray, s_t: np.ndarray) -> np.ndarray:
    """`p_cal = (cal - s_t*fair)/(1 - s_t)` (4.4). NaN si `s_t` es NaN o >= 1."""
    with np.errstate(divide="ignore", invalid="ignore"):
        p = (cal - s_t * fair) / (1.0 - s_t)
    return np.where(np.isfinite(s_t) & (s_t < 1.0), p, np.nan)


def invalid_market_mask(df: pd.DataFrame) -> pd.Series:
    """True en las filas de `INVALID_BEFORE` con `_gen` anterior a su instante
    o ilegible (Addendum 2026-10-17; semantica de `_drop_invalid_market_rows`
    del gate). `league` es la del nombre del fichero. No depende de `result`."""
    out = pd.Series(False, index=df.index)
    if df.empty or not {"league", "market", "_gen"} <= set(df.columns):
        return out
    for (league, market), since in INVALID_BEFORE.items():
        seg = (df["league"].astype(str) == league) & (df["market"].astype(str) == market)
        valido = (df["_gen"] >= pd.Timestamp(since)).fillna(False).astype(bool)
        out |= seg & ~valido
    return out


def quarter_line_mask(df: pd.DataFrame) -> pd.Series:
    """True en las filas totals/spreads de linea de cuarto con instante de
    generacion anterior a `QUARTER_LINE_INVALID_BEFORE` o ilegible (Addendum
    2026-10-18, AUD-008; misma semantica que `sqp.settlement.quarter_line_fix`).
    No depende de `result`."""
    out = pd.Series(False, index=df.index)
    if df.empty or not {"market", "line", "_gen"} <= set(df.columns):
        return out
    linea = _num(df, "line")
    cuarto = df["market"].astype(str).isin(_QUARTER_LINE_MARKETS) & linea.map(
        lambda x: bool(np.isfinite(x) and is_quarter_line(float(x))))
    antes = ~(df["_gen"] >= pd.Timestamp(QUARTER_LINE_INVALID_BEFORE)).fillna(False).astype(bool)
    return (cuarto & antes).astype(bool)


def prepare_picks(graded: pd.DataFrame, table: list[dict], collapse: bool = True,
                  liga_familia: dict[str, str | None] | None = None,
                  ) -> tuple[pd.DataFrame, dict]:
    """Seccion 4.1/4.2. Devuelve (picks validos, recuentos). Con
    `collapse=False` (S1) no se colapsa a una fila por pick. Con
    `liga_familia` (la guardada en el `.sk.json`) la familia sale de ese mapa;
    las ligas sin entrada usan `_league_meta` vivo y se listan en
    `ligas_sin_entrada_en_mapa`."""
    cnt: dict[str, Any] = {"filas_reales": int(len(graded))}
    if graded.empty:
        return pd.DataFrame(columns=["event_id", "_start", "_gen"]), cnt
    faltan = [c for c in (*_IDENTIDAD, "result", "generated_at", "start_time") if c not in graded.columns]
    if faltan:
        raise SystemExit(f"graded: faltan columnas obligatorias {faltan}. Aborta.")
    incompleta = _is_blank(graded["event_id"]) | _is_blank(graded["market"]) \
        | _is_blank(graded["selection"])
    cnt["identidad_incompleta"] = int(incompleta.sum())
    df = graded[~incompleta]
    res = df["result"].astype("object").where(df["result"].notna(), "").astype(str).str.strip()
    ok = res.isin(["win", "loss"])
    blanco = res == ""
    cnt["resultado_no_win_loss"] = int((~ok & ~blanco).sum())
    df = df[ok].copy()
    df["_y"] = (res[ok] == "win").astype(float)
    n0 = len(df)
    if collapse:
        df = one_row_per_pick(df)
    cnt["duplicados_colapsados"] = int(n0 - len(df))
    df = df.copy()
    df["_start"] = instantes_utc(df["start_time"], index=df.index)
    df["_gen"] = instantes_utc(df["generated_at"], index=df.index)

    ilegible = df["_start"].isna() | df["_gen"].isna()
    en_vivo = ~ilegible & (df["_gen"] >= df["_start"])
    cnt["pregame_ilegible"] = int(ilegible.sum())
    cnt["generado_en_vivo_o_despues"] = int(en_vivo.sum())
    df = df[~ilegible & ~en_vivo].copy()

    # Addendum 2026-10-17 (AUD-003): fila de decision de un `liga|mercado` con
    # no-vig falso en su instante -> fuera (el pick entero con `collapse`; no
    # se busca otra servida). `_gen` ya es legible aqui.
    invalido = invalid_market_mask(df)
    cnt["mercado_invalido_aud003"] = int(invalido.sum())
    df = df[~invalido].copy()
    # Addendum 2026-10-18 (AUD-008): linea de cuarto graduada sin medias.
    cuarto = quarter_line_mask(df)
    cnt["linea_cuarto_aud008"] = int(cuarto.sum())
    df = df[~cuarto].copy()

    cal = _num(df, "calibrated_probability")
    fair = _num(df, "implied_probability_novig")
    sin_prob = ~(np.isfinite(cal) & np.isfinite(fair))
    cnt["sin_probabilidad"] = int(sin_prob.sum())
    df = df[~sin_prob].copy()

    df["_seg"] = [segment_id(lg, m) for lg, m in zip(df["league"], df["market"], strict=True)] \
        if len(df) and "league" in df.columns else "|"
    nuevas: set[str] = set()
    df["_fam"] = [_fam_lookup(lg, m, liga_familia, nuevas)
                  for lg, m in zip(df["league"], df["market"], strict=True)] \
        if len(df) and "league" in df.columns else None
    if liga_familia is not None:
        cnt["ligas_sin_entrada_en_mapa"] = sorted(nuevas)
    df["_cal"] = _num(df, "calibrated_probability")
    df["_fair"] = _num(df, "implied_probability_novig")
    # Fuente de s_t (Addendum (1)): columna `market_shrink` si es finita > tabla.
    s_tab = regime_s(df["_gen"], df["_seg"], table)
    col = _num(df, "market_shrink").to_numpy(dtype=float)
    usa_col = np.isfinite(col)
    df["_s_t"] = np.where(usa_col, col, s_tab)
    col_fuera = usa_col & ~((col >= 0.0) & (col <= 1.0))
    cnt["s_desde_columna"] = int(usa_col.sum())
    cnt["s_columna_fuera_de_rango"] = int(col_fuera.sum())
    s_malo = ~(np.isfinite(df["_s_t"]) & (df["_s_t"] >= 0.0) & (df["_s_t"] < 1.0))
    cnt["s_t_igual_1_o_desconocido"] = int((s_malo & ~col_fuera).sum())
    # Discrepancia columna/tabla: solo filas que llegan a la reconstruccion (Add. (2)).
    cnt["s_columna_vs_tabla_discrepancias"] = int(
        (~s_malo.to_numpy() & usa_col & np.isfinite(s_tab)
         & (np.abs(col - s_tab) > 1e-9)).sum())
    df = df[~s_malo].copy()
    df["_p_cal"] = reconstruct_p_cal(df["_cal"].to_numpy(), df["_fair"].to_numpy(),
                                     df["_s_t"].to_numpy())
    fuera = ~((df["_p_cal"] >= 0.0) & (df["_p_cal"] <= 1.0))
    cnt["p_cal_fuera_de_rango"] = int(fuera.sum())
    df = df[~fuera].copy()
    cnt["picks_validos"] = int(len(df))
    return df, cnt


def split_windows(picks: pd.DataFrame, t0: pd.Timestamp,
                  t1: pd.Timestamp | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(ajuste: start <= T0, evaluacion: T0 < start <= T1) -- 3.2/3.3."""
    if picks.empty:
        return picks, picks
    ajuste = picks[picks["_start"] <= t0]
    ev = picks[picks["_start"] > t0]
    if t1 is not None:
        ev = ev[ev["_start"] <= t1]
    return ajuste, ev


# ---------------------------------------------------------------- estimador --
def node_stats(d: np.ndarray, p_cal: np.ndarray, y: np.ndarray,
               events: np.ndarray) -> dict:
    """`ŝ_X` y `v_X` (5.1). `n` = eventos distintos."""
    if len(d) == 0:
        return {"n": 0, "sum_D": 0.0, "s_hat": None, "v": None}
    _, inv = np.unique(events, return_inverse=True)
    g_e = np.bincount(inv, weights=d * (p_cal - y))
    d_e = np.bincount(inv, weights=d * d)
    sum_d = float(d_e.sum())
    n = int(len(g_e))
    if sum_d <= 0.0:
        return {"n": n, "sum_D": sum_d, "s_hat": None, "v": None}
    s_hat = float(g_e.sum() / sum_d)
    v = float(np.sum((g_e - s_hat * d_e) ** 2) / sum_d ** 2)
    return {"n": n, "sum_D": sum_d, "s_hat": s_hat, "v": v}


def shrink_node(stats: dict, parent: float, tau: float = TAU,
                min_n: int = MIN_EVENTS_NODE) -> float:
    """`s~ = (tau^2 ŝ + v parent)/(tau^2 + v)` si n >= min_n y hay datos; si no,
    hereda `parent` (5.2)."""
    if stats["n"] < min_n or stats["s_hat"] is None or stats["v"] is None:
        return float(parent)
    t2 = tau * tau
    return float((t2 * stats["s_hat"] + stats["v"] * parent) / (t2 + stats["v"]))


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _node(sub: pd.DataFrame) -> dict:
    d = (sub["_p_cal"] - sub["_fair"]).to_numpy(dtype=float)
    return node_stats(d, sub["_p_cal"].to_numpy(dtype=float),
                      sub["_y"].to_numpy(dtype=float), sub["event_id"].astype(str).to_numpy())


def fit_weights(picks: pd.DataFrame, tau: float = TAU,
                min_n: int = MIN_EVENTS_NODE) -> dict:
    """Jerarquia global -> familia -> segmento (5.2)."""
    g = _node(picks) if len(picks) else node_stats(np.array([]), np.array([]),
                                                    np.array([]), np.array([]))
    g_sin_datos = g["s_hat"] is None
    s_g = 0.5 if g_sin_datos else _clip01(g["s_hat"])
    g["s_tilde"] = s_g
    g["sin_datos"] = g_sin_datos
    familias: dict[str, dict] = {}
    segmentos: dict[str, dict] = {}
    if len(picks):
        for fam, sub in picks[picks["_fam"].notna()].groupby("_fam"):
            st = _node(sub)
            st["s_tilde"] = shrink_node(st, s_g, tau, min_n)
            familias[str(fam)] = st
        for seg, sub in picks.groupby("_seg"):
            st = _node(sub)
            fam = sub["_fam"].iloc[0]
            fam = None if pd.isna(fam) else str(fam)
            padre = familias[fam]["s_tilde"] if fam in familias else s_g
            st["familia"] = fam
            st["s_tilde"] = shrink_node(st, padre, tau, min_n)
            st["s_k"] = _clip01(st["s_tilde"])
            segmentos[str(seg)] = st
    return {"tau": tau, "min_eventos": min_n, "global": g, "familias": familias,
            "segmentos": segmentos}


def weights_for(fit: dict, seg: pd.Series, fam: pd.Series) -> np.ndarray:
    """`s_k` del segmento si tiene ajuste; si no, `s~_F` (recortado) de su
    familia; si no, `s~_G` (5.3)."""
    s_g = _clip01(fit["global"]["s_tilde"])
    out = []
    for sg, fm in zip(seg, fam, strict=True):
        if sg in fit["segmentos"]:
            out.append(fit["segmentos"][sg]["s_k"])
        elif fm is not None and not pd.isna(fm) and fm in fit["familias"]:
            out.append(_clip01(fit["familias"][fm]["s_tilde"]))
        else:
            out.append(s_g)
    return np.asarray(out, dtype=float)


def picks_sha256(picks: pd.DataFrame) -> str:
    lineas = sorted(f"{e}|{m}|{s}|{lin}|{y}|{c}|{f}" for e, m, s, lin, y, c, f in zip(
        picks["event_id"], picks["market"], picks["selection"],
        picks["line"] if "line" in picks.columns else [""] * len(picks),
        picks["_y"], picks["_cal"], picks["_fair"], strict=True))
    return hashlib.sha256("\n".join(lineas).encode("utf-8")).hexdigest()


# ------------------------------------------------------------- estadisticos --
def phi_two_sided(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def cluster_mean_cr1(v: np.ndarray, clusters: np.ndarray) -> dict:
    """Media y SE sandwich CR1 por cluster (como tier A 3.1), p bilateral."""
    n = len(v)
    if n == 0:
        return {"n": 0, "g": 0, "media": None, "se": None, "z": None, "p_bilateral": None,
                "ic95_cr1": None}
    mean = float(np.mean(v))
    _, inv = np.unique(clusters, return_inverse=True)
    g = int(inv.max()) + 1
    if g <= 1:
        return {"n": n, "g": g, "media": mean, "se": None, "z": None, "p_bilateral": None,
                "ic95_cr1": None}
    sums = np.bincount(inv, weights=v - mean)
    se = math.sqrt((g / (g - 1)) * float(np.sum(sums ** 2)) / n ** 2)
    z = mean / se if se > 0 else None
    return {"n": n, "g": g, "media": mean, "se": se, "z": z,
            "p_bilateral": phi_two_sided(z) if z is not None else None,
            "ic95_cr1": [mean - 1.96 * se, mean + 1.96 * se]}


def holm(pvalues: dict[str, float | None], alpha: float = ALPHA) -> dict[str, dict]:
    """Holm step-down. Un p-valor ausente (None) no puede rechazar, pero SI
    cuenta en m, para no inflar la potencia de los demas."""
    m = len(pvalues)
    orden = sorted(pvalues.items(), key=lambda kv: (kv[1] is None, kv[1] or 0.0))
    out: dict[str, dict] = {}
    maximo = 0.0
    rechaza = True
    for i, (k, p) in enumerate(orden):
        if p is None:
            out[k] = {"p": None, "p_holm": None, "rechaza": False}
            rechaza = False
            continue
        ajustado = min(1.0, max(maximo, (m - i) * p))
        maximo = ajustado
        rechaza = rechaza and p <= alpha / (m - i)
        out[k] = {"p": p, "p_holm": ajustado, "rechaza": bool(rechaza)}
    return out


def label_contraste(rechaza: bool, media: float | None) -> str:
    """H2 y segmentos (6.2): `pasa = rechaza (Holm) y media < 0`; si rechaza con
    media > 0 la etiqueta es PEOR."""
    if not rechaza or media is None:
        return "NO_RECHAZA"
    return "PASA" if media < 0 else "PEOR"


def boot_ci(values: np.ndarray, clusters: np.ndarray, n_boot: int, seed: int) -> list[float]:
    lo, hi = cluster_bootstrap_ci(values, clusters, n_boot=n_boot, seed=seed)
    return [lo, hi]


def label_h1(lo: float, hi: float) -> str:
    """6.1: PASA si hi < 0; PEOR si lo > 0; FALLA en otro caso."""
    if hi < 0:
        return "PASA"
    if lo > 0:
        return "PEOR"
    return "FALLA"


def _ll_pick(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    q = np.clip(p, _EPS, 1 - _EPS)
    return -(y * np.log(q) + (1 - y) * np.log(1 - q))


def eval_columns(ev: pd.DataFrame, fit: dict) -> pd.DataFrame:
    """`p_k`, `p_G`, `p_0,5`, `diff` por pick (6)."""
    ev = ev.copy()
    s_k = weights_for(fit, ev["_seg"], ev["_fam"])
    s_g = _clip01(fit["global"]["s_tilde"])
    ev["_s_k"] = s_k
    ev["_p_k"] = (1 - s_k) * ev["_p_cal"] + s_k * ev["_fair"]
    ev["_p_g"] = (1 - s_g) * ev["_p_cal"] + s_g * ev["_fair"]
    ev["_p_05"] = 0.5 * ev["_p_cal"] + 0.5 * ev["_fair"]
    y = ev["_y"]
    ev["_diff"] = (ev["_p_k"] - y) ** 2 - (ev["_p_05"] - y) ** 2
    ev["_diff_g"] = (ev["_p_k"] - y) ** 2 - (ev["_p_g"] - y) ** 2
    return ev


def _stat_block(ev: pd.DataFrame, col: str = "_diff") -> dict:
    if ev.empty:
        return {"n_picks": 0, "n_eventos": 0, "media": None, "ic95_cr1": None}
    ids = ev["event_id"].astype(str).to_numpy()
    out = cluster_mean_cr1(ev[col].to_numpy(dtype=float), ids)
    return {"n_picks": int(len(ev)), "n_eventos": int(len(np.unique(ids))),
            "media": out["media"], "ic95_cr1": out["ic95_cr1"]}


def policy_stats(ev: pd.DataFrame, p: np.ndarray) -> dict:
    """Politica de la seccion 8: stake 1 si 0,02 <= p*cuota - 1 <= 0,075."""
    price = _num(ev, "price_decimal").to_numpy()
    evx = p * price - 1.0
    bet = np.isfinite(evx) & (evx >= ROI_MIN_EDGE) & (evx <= ROI_MAX_EDGE)
    win = ev["_y"].to_numpy() == 1.0
    pnl = np.where(bet, np.where(win, price - 1.0, -1.0), 0.0)
    n = int(bet.sum())
    out: dict[str, Any] = {"n_apuestas": n}
    if n:
        out.update({
            "acierto_observado": float(win[bet].mean()),
            "prob_prometida_media": float(p[bet].mean()),
            "prob_implicita_media": float((1.0 / price[bet]).mean()),
            "edge_medio": float((p[bet] - ev["_fair"].to_numpy()[bet]).mean()),
            "roi_esperado_medio": float(evx[bet].mean()),
            "roi_realizado": float(pnl[bet].mean()),
        })
        if "execution_price" in ev.columns:
            ex = _num(ev, "execution_price").to_numpy()
            con = bet & np.isfinite(ex) & (ex > 1.0)
            out["n_con_execution_price"] = int(con.sum())
            if con.any():
                out["roi_esperado_execution_price"] = float((p[con] * ex[con] - 1.0).mean())
                out["roi_realizado_execution_price"] = float(
                    np.where(win[con], ex[con] - 1.0, -1.0).mean())
            reg = execution_regime(ev["_gen"] if "_gen" in ev.columns
                                   else ev.get("generated_at", pd.Series(pd.NaT, index=ev.index)))
            por: dict[str, Any] = {}
            for lab in EXECUTION_REGIMES:
                m = con & (reg == lab)
                d: dict[str, Any] = {"n_con_execution_price": int(m.sum())}
                if m.any():
                    d["roi_esperado_execution_price"] = float((p[m] * ex[m] - 1.0).mean())
                    d["roi_realizado_execution_price"] = float(
                        np.where(win[m], ex[m] - 1.0, -1.0).mean())
                por[lab] = d
            out["execution_price_por_regimen"] = por
    return out


def roi_gate(ev: pd.DataFrame, n_boot: int, seed: int) -> dict:
    """Puerta de ROI (8): ΔPnL por evento, IC bootstrap por evento."""
    price = _num(ev, "price_decimal").to_numpy()
    win = ev["_y"].to_numpy() == 1.0

    def pnl(p: np.ndarray) -> np.ndarray:
        evx = p * price - 1.0
        bet = np.isfinite(evx) & (evx >= ROI_MIN_EDGE) & (evx <= ROI_MAX_EDGE)
        return np.where(bet, np.where(win, price - 1.0, -1.0), 0.0)

    delta = pnl(ev["_p_k"].to_numpy()) - pnl(ev["_p_05"].to_numpy())
    por_evento = pd.Series(delta).groupby(ev["event_id"].astype(str).to_numpy()).sum()
    vals = por_evento.to_numpy(dtype=float)
    ids = por_evento.index.to_numpy()
    media = float(vals.mean()) if len(vals) else None
    lo, hi = boot_ci(vals, ids, n_boot, seed) if len(vals) else [float("nan")] * 2
    return {"delta_pnl_por_evento": media, "ic95_bootstrap": [lo, hi],
            "pasa": bool(lo > 0), "n_eventos": int(len(vals)),
            "politica_p_k": policy_stats(ev, ev["_p_k"].to_numpy()),
            "politica_p_05": policy_stats(ev, ev["_p_05"].to_numpy()),
            "aviso": "Pasar NO significa rentabilidad (seccion 8)."}


# ------------------------------------------------------------ tuberia comun --
def _counts_eval(picks: pd.DataFrame, t0: pd.Timestamp,
                 t1: pd.Timestamp) -> tuple[int, int]:
    _, ev = split_windows(picks, t0, t1)
    return (int(ev["event_id"].astype(str).nunique()) if len(ev) else 0, int(len(ev)))


# ------------------------------------------------------------------ --contar --
def contar_log_path(preregistro: Path) -> Path:
    nombre = preregistro.name[:-3] if preregistro.name.endswith(".md") else preregistro.name
    return preregistro.parent / f"{nombre}.contar.jsonl"


def sk_json_path(preregistro: Path) -> Path:
    nombre = preregistro.name[:-3] if preregistro.name.endswith(".md") else preregistro.name
    return preregistro.parent / f"{nombre}.sk.json"


def _now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def settings_market_shrink() -> float | None:
    try:
        from sqp.config import Settings
        return float(Settings.load().risk.market_shrink)
    except Exception:  # noqa: BLE001 -- informativo
        return None


def run_contar(args: argparse.Namespace) -> dict:
    cwd = _WORKTREE_ROOT
    rh = resolve_h(args.preregistro, cwd)
    rt = resolve_t0(cwd)
    head = _git(["rev-parse", "HEAD"], cwd)
    e = _now()
    t1c = e - pd.Timedelta(days=MARGIN_DAYS)
    try:
        table = load_regime_table(args.preregistro, cwd)
        error_tabla = None
    except SystemExit as exc:      # --contar informa y sigue (Addendum (1))
        table = parse_regime_table(None)
        error_tabla = str(exc)
    prov = csv_provenance(args.data_root)
    efectivo = settings_market_shrink()
    tabla_s = last_global_s(table, e)
    n_ev = n_pk = n_pend = 0
    graded, err_g = load_graded_real(args.data_root)
    served, err_s = load_served_real(args.data_root)
    if rt is not None:
        picks, _ = prepare_picks(graded, table)
        n_ev, n_pk = _counts_eval(picks, rt["t0"], t1c)
        n_pend = count_sin_graduar(served, graded, rt["t0"], t1c)
    registro = {
        "instante_ejecucion_utc": e.isoformat(), "head": head,
        "h": rh["h"] if rh else None,
        "t0": rt["t0"].isoformat() if rt else None,
        "t1_candidato": t1c.isoformat(),
        "n_eventos_evaluacion": n_ev, "n_picks_evaluacion": n_pk,
        "picks_sin_graduar_ventana": n_pend,
        "market_shrink_efectivo": efectivo, "market_shrink_tabla": tabla_s,
        "market_shrink_difiere": (None if efectivo is None
                                  else bool(abs(efectivo - tabla_s) > 1e-12)),
        "sha256_csv": [x for x in prov if "error" not in x],
        "via_resolucion_h": rh["via"] if rh else None,
        "errores_lectura_csv": [*err_g, *err_s,
                                *[x for x in prov if "error" in x]],
        "error_tabla_regimen": error_tabla,
    }
    assert set(registro) == CONTAR_CAMPOS
    if not args.no_log:
        log_path = contar_log_path(args.preregistro)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
        aviso = f"Linea anadida a {log_path}."
    else:
        aviso = "--no-log: NO se escribio en el registro .contar.jsonl (diagnostico)."
    if rt is None:
        aviso += " T0 no existe todavia (no hay resultado de MM): n = 0."
    return {"modo": "contar", "registro": registro, "aviso": aviso}


# ----------------------------------------------------------------- --ajustar --
def run_ajustar(args: argparse.Namespace) -> dict:
    cwd = _WORKTREE_ROOT
    rt = resolve_t0(cwd)
    if rt is None:
        raise SystemExit("--ajustar exige T0 (resultado de MM commiteado) y no existe. Aborta.")
    rh = resolve_h(args.preregistro, cwd)
    if rh is None:
        raise SystemExit("--ajustar: H no se pudo resolver. Aborta.")
    e = _now()
    t0 = rt["t0"]
    if e < t0 + pd.Timedelta(days=MARGIN_DAYS):
        raise SystemExit(f"--ajustar exige E >= T0 + {MARGIN_DAYS} d "
                         f"({(t0 + pd.Timedelta(days=MARGIN_DAYS)).isoformat()}); "
                         f"E = {e.isoformat()}. Aborta (seccion 5.4).")
    sk_path = sk_json_path(args.preregistro)
    rel_sk = _relpath(sk_path, cwd)
    if sk_path.exists() or (rel_sk and git_show_or_none("HEAD", rel_sk, cwd) is not None):
        raise SystemExit(f"{sk_path} ya existe (en disco o commiteado). --ajustar se "
                         "ejecuta una sola vez (ambiguedad 8). Aborta.")
    table = load_regime_table(args.preregistro, cwd)
    graded, errores = load_graded_real(args.data_root, strict=True)
    picks, cnt = prepare_picks(graded, table)
    ajuste, _ = split_windows(picks, t0, None)
    fit = fit_weights(ajuste)
    ligas = sorted({str(x).lower() for x in ajuste["league"]}) if len(ajuste) else []
    liga_familia = {lg: _family_of_league(lg) for lg in ligas}
    sk = {"h": rh["h"], "t0": t0.isoformat(), "instante_ajuste_utc": e.isoformat(),
          "head": _git(["rev-parse", "HEAD"], cwd),
          "sha256_picks_ajuste": picks_sha256(ajuste) if len(ajuste) else None,
          "n_picks_ajuste": int(len(ajuste)), "exclusiones": cnt,
          "errores_lectura": errores, "liga_familia": liga_familia, "ajuste": fit}
    texto = json.dumps(sk, indent=2, ensure_ascii=False, sort_keys=True)
    sk_path.write_text(texto + "\n", encoding="utf-8")
    return {"modo": "ajustar", "fichero": str(sk_path), "n_segmentos": len(fit["segmentos"]),
            "n_picks_ajuste": int(len(ajuste))}


# ------------------------------------------------------------------- --medir --
def parse_t1_addendum(doc_text: str) -> tuple[str, str] | None:
    """Dos LINEAS literales al inicio de linea: `T1 fijado = <ISO>` y
    `commit del registro = <sha>`. Las citas en prosa o entre comillas
    inversas (p. ej. en 7.4) NO cuentan, ni los valores ISO ilegibles. `None`
    si faltan; aborta si hay varios T1 validos distintos."""
    t1s = [m for m in re.findall(r"(?m)^[ \t]*T1 fijado[ \t]*=[ \t]*(\S+)[ \t]*$", doc_text)
           if _parse_ts(m) is not None]
    cms = re.findall(r"(?m)^[ \t]*commit del registro[ \t]*=[ \t]*([0-9a-fA-F]{7,40})[ \t]*$",
                     doc_text)
    if not t1s or not cms:
        return None
    if len({_parse_ts(x) for x in t1s}) > 1 or len(set(cms)) > 1:
        raise SystemExit("Hay varios addenda de T1 distintos en el pre-registro. --medir aborta.")
    return t1s[-1], cms[-1]


def _parse_jsonl_text(text: str | None) -> list[dict]:
    return [json.loads(x) for x in (text or "").splitlines() if x.strip()]


def first_over(lines: list[dict], threshold: int) -> dict | None:
    for fila in lines:
        if fila.get("n_eventos_evaluacion", 0) >= threshold:
            return fila
    return None


def _refit(picks_ajuste: pd.DataFrame, picks_eval: pd.DataFrame, tau: float) -> dict:
    ev = eval_columns(picks_eval, fit_weights(picks_ajuste, tau=tau))
    return _stat_block(ev)


def run_medir(args: argparse.Namespace) -> dict:
    cwd = _WORKTREE_ROOT
    rt = resolve_t0(cwd)
    if rt is None:
        raise SystemExit("--medir exige T0 y no existe. Aborta.")
    rh = resolve_h(args.preregistro, cwd)
    if rh is None:
        raise SystemExit("--medir: H no se pudo resolver. Aborta.")
    t0 = rt["t0"]
    head = _git(["rev-parse", "HEAD"], cwd)
    rel_pre = _relpath(args.preregistro, cwd)
    rel_jsonl = _relpath(contar_log_path(args.preregistro), cwd)
    rel_sk = _relpath(sk_json_path(args.preregistro), cwd)
    if rel_pre is None or rel_jsonl is None or rel_sk is None:
        raise SystemExit("El pre-registro y sus ficheros hermanos deben estar dentro del "
                         "repositorio. --medir aborta.")
    status_paths = (*_GIT_STATUS_PATHS,
                    (Path(rel_pre).parent / f"{Path(rel_pre).stem}*").as_posix())
    status = git_status_porcelain(cwd, status_paths)
    if status is None or status.strip():
        raise SystemExit(f"git status --porcelain no esta vacio o no se pudo leer:\n{status}\n"
                         "--medir aborta: arbol con cambios sin commitear.")

    addendum = parse_t1_addendum(git_show_text("HEAD", rel_pre, cwd))
    if addendum is None:
        raise SystemExit("No hay addendum que fije T1 (7.4). --medir aborta.")
    t1 = _parse_ts(addendum[0])
    pedido = _parse_ts(args.t1)
    if t1 is None or pedido is None or pedido != t1:
        raise SystemExit(f"--t1 {args.t1!r} no coincide con el T1 del addendum "
                         f"({addendum[0]!r}). --medir aborta.")
    primera = first_over(_parse_jsonl_text(git_show_or_none("HEAD", rel_jsonl, cwd)),
                         N_REQUIRED)
    t1_primera = _parse_ts(primera.get("t1_candidato")) if primera else None
    if t1_primera is None or t1_primera != t1:
        raise SystemExit("El T1 del addendum no coincide con el T1 candidato de la PRIMERA "
                         f"linea del registro con n >= {N_REQUIRED} (o no hay ninguna). "
                         "--medir aborta.")
    en_commit = first_over(_parse_jsonl_text(git_show_or_none(addendum[1], rel_jsonl, cwd)),
                           N_REQUIRED)
    t1_commit = _parse_ts(en_commit.get("t1_candidato")) if en_commit else None
    if t1_commit is None or t1_commit != t1:
        raise SystemExit(f"El commit citado ({addendum[1]}) no contiene esa primera linea "
                         "del registro. --medir aborta.")
    sk_text = git_show_or_none("HEAD", rel_sk, cwd)
    if sk_text is None:
        raise SystemExit("El .sk.json no esta commiteado en HEAD. --medir aborta (5.4).")
    sk = json.loads(sk_text)
    if _parse_ts(sk.get("t0")) != t0:
        raise SystemExit("El T0 del .sk.json no coincide con el T0 resuelto. --medir aborta.")
    committed_fit = sk["ajuste"]
    liga_familia = sk.get("liga_familia")

    table = load_regime_table(args.preregistro, cwd)
    graded, errores = load_graded_real(args.data_root, strict=True)
    picks, cnt = prepare_picks(graded, table, liga_familia=liga_familia)
    n_ev, _ = _counts_eval(picks, t0, t1)
    if n_ev < N_REQUIRED:
        raise SystemExit(f"n(T1) = {n_ev} < {N_REQUIRED}. --medir aborta (7.4).")

    ajuste, ev0 = split_windows(picks, t0, t1)
    # Defensa: ninguna fila de una ventana en la otra (3.2/3.3).
    assert (ajuste["_start"] <= t0).all() and (ev0["_start"] > t0).all()
    ev = eval_columns(ev0, committed_fit)
    ids = ev["event_id"].astype(str).to_numpy()
    y = ev["_y"].to_numpy(dtype=float)

    # Discrepancia con el recalculo (5.4): se informa; manda el commiteado.
    refit = fit_weights(ajuste)
    difs = [abs(refit["segmentos"][k]["s_k"] - v["s_k"]) for k, v in committed_fit["segmentos"].items()
            if k in refit["segmentos"]]
    discrepancia = {"max_abs_s_k": max(difs) if difs else None,
                    "segmentos_solo_en_commit": sorted(set(committed_fit["segmentos"])
                                                       - set(refit["segmentos"])),
                    "segmentos_solo_en_recalculo": sorted(set(refit["segmentos"])
                                                          - set(committed_fit["segmentos"])),
                    "sha256_picks_ajuste_commit": sk.get("sha256_picks_ajuste"),
                    "sha256_picks_ajuste_recalculo": picks_sha256(ajuste) if len(ajuste) else None}

    # H1 + control de log loss (6.1)
    diff = ev["_diff"].to_numpy(dtype=float)
    lo, hi = boot_ci(diff, ids, args.n_boot, args.seed)
    etiqueta = label_h1(lo, hi)
    ll_diff = _ll_pick(ev["_p_k"].to_numpy(dtype=float), y) - _ll_pick(
        ev["_p_05"].to_numpy(dtype=float), y)
    ll_lo, ll_hi = boot_ci(ll_diff, ids, args.n_boot, args.seed)
    ll_peor = bool(ll_lo > 0)
    h1 = {"n_picks": int(len(ev)), "n_eventos": n_ev, "media_diff": float(diff.mean()),
          "ic95_bootstrap": [lo, hi], "etiqueta": etiqueta,
          "brier_p_k": float(np.mean((ev["_p_k"] - y) ** 2)),
          "brier_p_05": float(np.mean((ev["_p_05"] - y) ** 2)),
          "log_loss": {"p_k": log_loss_safe(ev["_p_k"].to_numpy(), y),
                       "p_05": log_loss_safe(ev["_p_05"].to_numpy(), y),
                       "media_diff": float(ll_diff.mean()), "ic95_bootstrap": [ll_lo, ll_hi],
                       "peor_con_ic": ll_peor},
          "fragil": bool(etiqueta == "PASA" and ll_peor)}

    # H2 y segmentos con Holm (6.2): solo si H1 PASA
    h2_seg: dict[str, Any]
    if etiqueta == "PASA":
        pruebas: dict[str, float | None] = {}
        detalle: dict[str, dict] = {}
        r = cluster_mean_cr1(ev["_diff_g"].to_numpy(dtype=float), ids)
        pruebas["H2"] = r["p_bilateral"]
        detalle["H2"] = {**r, "ic95_bootstrap": boot_ci(
            ev["_diff_g"].to_numpy(dtype=float), ids, args.n_boot, args.seed)}
        for seg, sub in ev.groupby("_seg"):
            n_seg = sub["event_id"].astype(str).nunique()
            if n_seg < MIN_SEGMENT_EVENTS_EVAL:
                continue
            sid = sub["event_id"].astype(str).to_numpy()
            sv = sub["_diff"].to_numpy(dtype=float)
            r = cluster_mean_cr1(sv, sid)
            pruebas[f"seg:{seg}"] = r["p_bilateral"]
            detalle[f"seg:{seg}"] = {**r, "n_eventos": int(n_seg), "ic95_bootstrap":
                                     boot_ci(sv, sid, args.n_boot, args.seed)}
        h = holm(pruebas)
        h2_seg = {}
        for k in pruebas:
            etq = label_contraste(h[k]["rechaza"], detalle[k]["media"])
            h2_seg[k] = {**detalle[k], **h[k], "pasa": etq == "PASA", "etiqueta": etq}
    else:
        h2_seg = {"aviso": "H1 no PASA: H2 y segmentos no se abren (6.2)."}

    # S1..S7 (9.2, descriptivas)
    s1_picks, s1_cnt = prepare_picks(graded, table, collapse=False, liga_familia=liga_familia)
    _, s1_ev = split_windows(s1_picks, t0, t1)
    s1 = _stat_block(eval_columns(s1_ev, committed_fit)) if len(s1_ev) else {}
    s2 = {f"tau_{t:.2f}": _refit(ajuste, ev0, t) for t in (0.10, 0.50)}
    excl = pd.Series(False, index=ajuste.index)
    if len(ajuste) and "league" in ajuste.columns:
        for liga, fecha in _REGIME_CHANGES_PRE_T0.items():
            corte = _parse_ts(fecha)
            excl |= (ajuste["league"].astype(str).str.lower() == liga) & (ajuste["_gen"] < corte)
    s3 = {"filas_excluidas_del_ajuste": int(excl.sum()),
          "fechas": _REGIME_CHANGES_PRE_T0, **_refit(ajuste[~excl], ev0, TAU)}
    s4 = {}
    for e_ in sorted((x for x in table if x["desde"] is not None and x["desde"] > t0),
                     key=lambda x: x["desde"]):
        antes = ev[ev["_start"] < e_["desde"]]
        despues = ev[ev["_start"] >= e_["desde"]]
        s4[e_["desde"].isoformat()] = {"antes": _stat_block(antes), "despues": _stat_block(despues)}
    dist = ev[(ev["_s_t"] - 0.5).abs() > 1e-12]
    s5 = {"n_picks_con_s_distinto_de_0_5": int(len(dist))}
    if len(dist):
        d5 = (dist["_p_k"] - dist["_y"]) ** 2 - (dist["_cal"] - dist["_y"]) ** 2
        s5.update(cluster_mean_cr1(d5.to_numpy(dtype=float),
                                   dist["event_id"].astype(str).to_numpy()))
    s6 = {str(f): _stat_block(sub) for f, sub in ev.groupby(ev["_fam"].fillna("sin_familia"))}
    raw_ev = graded[(instantes_utc(graded["start_time"], index=graded.index) > t0)
                    & (instantes_utc(graded["start_time"], index=graded.index) <= t1)] \
        if len(graded) and "start_time" in graded.columns else graded
    plan = flattened_segments(raw_ev)
    s7 = plan.to_dict(orient="records") if len(plan) else []

    procedencia = {
        "h": rh["h"], "t0": t0.isoformat(), "t1": t1.isoformat(), "head": head,
        "via_resolucion_h": rh["via"], "hashes_blob": blob_hashes(rh["h"], head, cwd),
        "git_status_porcelain": status,
        "seed_n_boot": {"seed": args.seed, "n_boot": args.n_boot,
                        "difiere_de_lo_congelado":
                            bool(args.seed != SEED or args.n_boot != N_BOOT)},
        "sha256_csv": csv_provenance(args.data_root), "errores_lectura": errores}
    return {
        "modo": "medir", "procedencia": procedencia, "recuentos": cnt,
        "recuentos_S1": s1_cnt, "s_k_commiteado_vs_recalculo": discrepancia,
        "H1": h1, "H2_y_segmentos_holm": h2_seg, "ROI": roi_gate(ev, args.n_boot, args.seed),
        "S1_sin_colapsar": s1, "S2_tau": s2, "S3_sin_filas_pre_regimen": s3,
        "S4_particion_por_regimen": s4, "S5_vs_s_vigente": s5, "S6_por_familia": s6,
        "S7_calibrador_aplanado": s7}


# --------------------------------------------------------------------- main --
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--preregistro", type=Path, default=DEFAULT_PREREGISTRO)
    ap.add_argument("--contar", action="store_true")
    ap.add_argument("--ajustar", action="store_true")
    ap.add_argument("--medir", action="store_true")
    ap.add_argument("--t1", default=None, help="ISO-8601, obligatorio con --medir.")
    ap.add_argument("--no-log", action="store_true",
                    help="Diagnostico: con --contar no anade linea al registro.")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--out", type=Path, default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    modos = [m for m in ("contar", "ajustar", "medir") if getattr(args, m)]
    if len(modos) != 1:
        ap.error("Hay que elegir exactamente uno de --contar, --ajustar, --medir.")
    if args.no_log and not args.contar:
        ap.error("--no-log solo aplica a --contar.")
    if args.medir and not args.t1:
        ap.error("--medir exige --t1 <ISO-8601>.")
    if args.t1 and not args.medir:
        ap.error("--t1 solo aplica a --medir.")
    t_ini = time.perf_counter()
    out = {"contar": run_contar, "ajustar": run_ajustar, "medir": run_medir}[modos[0]](args)
    out["segundos"] = time.perf_counter() - t_ini
    texto = json.dumps(out, indent=2, ensure_ascii=False, default=str)
    print(texto)
    if args.out:
        args.out.write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
