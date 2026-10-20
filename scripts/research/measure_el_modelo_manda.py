"""Medicion del pre-registro «el modelo manda» (2026-08-26).

Ver `docs/research/2026-08-26-preregistro-el-modelo-manda.md`, en especial el
"Addendum 2026-10-13 (2) -- especificacion de ejecucion" (secciones E1-E9).
Ese documento MANDA sobre este docstring; aqui solo se resumen decisiones y se
documentan las AMBIGUEDADES que la especificacion dejaba abiertas, con la
decision tomada (todas coinciden con la lectura mas literal del addendum).

## Que mide

Diferencia pareada de Brier `diff = Brier(p_cal) - Brier(fair)` por pick,
con `p_cal = 2*calibrated_probability - implied_probability_novig` (lo que se
serviria con `market_shrink = 0`), sobre `data/calibration/graded_*.csv`.
Negativo = el modelo gana. Test primario global, secundarios por
`league|market` con Holm, y segunda puerta de ROI.

## Modos (E4)

  --contar [--no-log]   (por defecto) Solo recuentos. Anade UNA linea JSON a
                        `<preregistro>.contar.jsonl` (append-only). NUNCA
                        calcula ni imprime Brier, diff, aciertos, ROI, z ni p.
                        `--no-log` es diagnostico: no escribe el registro.
  --medir --t1 <ISO>    Medicion UNICA. Aborta sin calcular nada que dependa
                        de `result` si falla cualquier comprobacion previa.

PROHIBIDO ejecutar `--medir` contra datos reales antes de que exista el
addendum que fija T1 (y antes de la revision de Fable). `--contar` si se puede.

  python scripts/research/measure_el_modelo_manda.py --contar --no-log
  python scripts/research/measure_el_modelo_manda.py --medir --t1 2026-12-01T00:00:00Z --out r.json

## Ambiguedades resueltas en este script

1. **Formato del addendum de T1 (E4).** Se exigen dos LINEAS literales
   (ancladuras de linea, no texto suelto) `T1 fijado = <ISO-8601>` y
   `commit del registro = <sha>`. El propio addendum E4 cita esas frases entre
   comillas inversas dentro de un parrafo; el anclaje de linea y la exigencia
   de que el valor sea un instante legible evitan leer esas citas como si
   fueran el addendum. Si hay varios addenda validos con T1 distinto, aborta.
2. **Arbol limpio en `--medir`.** E8 pide REGISTRAR `git status --porcelain --
   src configs scripts/research`; el precedente de tier A ademas ABORTA si no
   esta vacio (el hash de blob registrado no probaria nada con cambios sin
   commitear). Se sigue el precedente, y tambien para el pre-registro y su
   registro hermano.
3. **`generated_at` ilegible en la primera servida (E3 paso 5).** No se puede
   comparar con T1, asi que el pick queda fuera del corte y se cuenta
   (`primera_servida_generated_at_ilegible`). Sin T1 (recuento "sin corte") no
   se excluye.
4. **Decision del primario.** `score_model_vs_market` redondea los limites a
   5 decimales; la decision usa esos limites redondeados (es lo que fija E5:
   «PASA si `brier_diff_hi < 0`»). `decision` es PASA o FALLA y `modelo_peor`
   (`brier_diff_lo > 0`) se informa aparte, como pide E5.
5. **Sensibilidad «todas las servidas sin colapsar» (addendum de unidad).**
   Filas posteriores a E3 paso 2, sin las de picks excluidos por `p_cal` fuera
   de rango en su primera servida y solo las con `generated_at <= T1`; Brier
   pareado y bootstrap por evento calculados a mano (el colapso interno de
   `score_model_vs_market` no permite medir sin colapsar).
6. **`books_count` ausente en la regla de E6** se trata como 0 (convencion del
   stream servido: `int(cons_n.get(key) or 0)`), de modo que aplica la
   penalizacion de mercado fino.
7. **Comparaciones de umbral de E6** son las del literal sin tolerancia
   (`e_adj >= 0.02`, `e <= 0.075`), en coma flotante, como el pipeline.
8. **E7 sin filas con |a - fair| >= 0.02** (no se puede verificar `s`): se
   considera NO verificado y `--medir` aborta.
9. **Politica ROI sin apuestas en una replica**: la replica se descarta y se
   cuenta (E6). `ROI_s = sum(PnL)/n apuestas` recalculado por replica.
10. **AUD-003 (Addendum 2026-10-17).** Paso 4b de E3: un pick cuya primera
    servida es de `nhl|h2h` con `generated_at` anterior a
    2026-10-16T12:56:03Z (ffc5ad3), ilegible o ausente queda fuera entero
    (`picks_mercado_invalido_aud003`), tambien en `--contar` y en las
    sensibilidades. No se sustituye por una servida posterior.
"""
from __future__ import annotations

import argparse
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
from sqp.evaluation.edge_information import PICK_KEY, one_row_per_pick
from sqp.evaluation.model_vs_market import score_model_vs_market
from sqp.markets.settlement_math import is_quarter_line

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]

# Constantes congeladas por el pre-registro (seccion indicada).
DELTA = 0.0025                      # texto original: efecto minimo de interes
N_REQUIRED = 3402                   # texto original: eventos del primario
SEG_MIN_EVENTS = 800                # texto original: segmentos secundarios
SEED = 42                           # texto original
N_BOOT = 10_000                     # texto original
MARGEN_DIAS = 14                    # E4
HOLM_ALPHA = 0.05                   # E5
S_ESPERADO = 0.5                    # E7
S_TOL_MEDIANA = 0.01                # E7
S_TOL_FILA = 0.05                   # E7
S_TOL_FRAC = 0.01                   # E7
MIN_GAP_S = 0.02                    # E7
MAX_REPLICAS_INDEFINIDAS = 0.01     # E6

# E6, literales congelados (== configs/default.yaml en el commit del addendum).
E6_MIN_EDGE = 0.02
E6_MAX_PLAUSIBLE = 0.075
E6_UNCERTAINTY = 0.35
E6_ANOMALY_GAP = 0.06
E6_ANOMALY_EXTRA = 0.02
E6_LOW_BOOK = 0.015
E6_MIN_BOOKS = 2

DEFAULT_PREREGISTRO = (DEFAULT_ROOT / "docs" / "research"
                       / "2026-08-26-preregistro-el-modelo-manda.md")

_GIT_STATUS_PATHS = ("src", "configs", "scripts/research")
_BLOB_FILES = ("src/sqp/evaluation/edge_information.py",
               "src/sqp/evaluation/model_vs_market.py",
               "src/sqp/evaluation/bootstrap.py",
               "src/sqp/pipeline/probabilities.py",
               "scripts/research/measure_el_modelo_manda.py")
_ADDENDUM_E_MARCA = "## Addendum 2026-10-13 (2)"

# Addendum 2026-10-17 (AUD-003): `liga|mercado` cuyo `implied_probability_novig`
# es falso antes de un instante. Literal CONGELADO aqui (no se importa de
# `sqp.risk.prediction_gate.INVALID_BEFORE`: una entrada nueva en el gate no
# puede cambiar la poblacion de este test sin su propio addendum). Un test fija
# que coincide con el del gate, para que cualquier divergencia obligue a decidir.
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
_SEGMENT_COLS = ["league", "market"]
_REQUIRED_COLS = ("result", "calibrated_probability", "implied_probability_novig",
                  "event_id", "selection", "market", "generated_at", "league")


# ------------------------------------------------------------------- git --
def _git(args: list[str], cwd: Path) -> str | None:
    """`git <args>`; `None` si falla (procedencia informativa, no decide)."""
    try:
        res = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                             text=True, encoding="utf-8", check=True, timeout=30)
        return res.stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def git_rev_parse(ref: str, cwd: Path) -> str | None:
    return _git(["rev-parse", ref], cwd)


def git_blob_hash(ref: str, relpath: str, cwd: Path) -> str | None:
    return _git(["rev-parse", f"{ref}:{relpath}"], cwd)


def git_hash_object(relpath: str, cwd: Path) -> str | None:
    return _git(["hash-object", relpath], cwd)


def git_log_added(relpath: str, cwd: Path) -> str | None:
    """Commit que ANADIO el fichero (H_MM): el mas antiguo de `--diff-filter=A`."""
    out = _git(["log", "--diff-filter=A", "--format=%H %cI", "--", relpath], cwd)
    lineas = [x for x in (out or "").splitlines() if x.strip()]
    return lineas[-1].split(" ", 1)[0] if lineas else None


def git_commit_introducing(text: str, relpath: str, cwd: Path) -> str | None:
    """Commit mas antiguo que introdujo `text` en `relpath` (pickaxe `-S`)."""
    out = _git(["log", "--format=%H", f"-S{text}", "--", relpath], cwd)
    lineas = [x for x in (out or "").splitlines() if x.strip()]
    return lineas[-1] if lineas else None


def git_show_text(ref: str, relpath: str, cwd: Path) -> str:
    try:
        res = subprocess.run(["git", "show", f"{ref}:{relpath}"], cwd=str(cwd),
                             capture_output=True, text=True, encoding="utf-8",
                             check=True, timeout=30)
        return res.stdout
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"No se pudo leer {relpath!r} en {ref!r} con git show: {exc}") from exc


def git_status_porcelain(cwd: Path, paths: tuple[str, ...] = _GIT_STATUS_PATHS) -> str | None:
    try:
        res = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=str(cwd),
                             capture_output=True, text=True, encoding="utf-8",
                             check=True, timeout=30)
        return res.stdout
    except Exception:  # noqa: BLE001
        return None


def _check_git_clean(status: str | None) -> None:
    if status is None:
        raise SystemExit("No se pudo obtener 'git status --porcelain'. --medir aborta: "
                         "no se puede verificar que el arbol este limpio.")
    if status.strip() != "":
        raise SystemExit("git status --porcelain de src, configs, scripts/research y el "
                         f"pre-registro NO esta vacio:\n{status}\n--medir aborta.")


def _relpath(path: Path, cwd: Path) -> str | None:
    try:
        return path.resolve().relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return None


def _parse_ts(value: object) -> pd.Timestamp | None:
    """Instante UTC comparable POR INSTANTE ('Z' == '+00:00'); `None` si ilegible."""
    if value is None:
        return None
    try:
        ts = pd.Timestamp(str(value))
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    return ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")


# ----------------------------------------------------------- lectura (E2) --
def sha256_and_rows(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    saltos = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            saltos += chunk.count(b"\n")
    return h.hexdigest(), max(saltos - 1, 0)


def read_stream(data_root: Path, prefix: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Lector propio SIN efectos secundarios (E2). Misma semantica que
    `ServedStore.load_all_graded` (orden alfabetico, no `demo/`, `league` del
    nombre del fichero) pero NUNCA renombra ni toca un fichero: uno ilegible o
    corrupto se omite y se informa (`errores_lectura`), y `--medir` aborta si
    hay alguno. Un fichero que solo trae cabecera es una liga `vacia`."""
    paths = sorted((data_root / "data" / "calibration").glob(f"{prefix}_*.csv"))
    frames: list[pd.DataFrame] = []
    errores: list[dict[str, str]] = []
    listadas: list[str] = []
    cargadas: list[str] = []
    vacias: list[str] = []
    ficheros: list[dict[str, Any]] = []
    for p in paths:
        liga = p.stem[len(prefix) + 1:]
        listadas.append(liga)
        sha, filas = sha256_and_rows(p)
        ficheros.append({"fichero": p.name, "sha256": sha, "filas": filas})
        try:
            df = pd.read_csv(p)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError,
                UnicodeDecodeError) as exc:
            errores.append({"fichero": str(p), "error": f"{type(exc).__name__}: {exc}"})
            continue
        if df.empty:
            vacias.append(liga)
            continue
        df["league"] = liga          # sobrescribe la columna del CSV (E2)
        frames.append(df)
        cargadas.append(liga)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    prov = {"listadas": listadas, "cargadas": cargadas, "vacias": vacias,
            "faltantes": sorted({Path(e["fichero"]).stem[len(prefix) + 1:] for e in errores}),
            "errores_lectura": errores, "ficheros": ficheros}
    return out, prov


def filter_real(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """`data_label == "real"` si la columna existe; devuelve tambien las excluidas."""
    if df.empty or "data_label" not in df.columns:
        return df, 0
    mask = df["data_label"].astype(str) == "real"
    return df[mask].copy(), int((~mask).sum())


# ------------------------------------------------- poblacion medida (E3) --
def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(float("nan"), index=df.index, dtype=float)


def _ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", utc=True, format="ISO8601")


def invalid_market_mask(df: pd.DataFrame) -> pd.Series:
    """True en las filas de `INVALID_BEFORE` con `generated_at` anterior a su
    instante, ilegible o ausente (Addendum 2026-10-17, misma semantica que
    `_drop_invalid_market_rows` del gate). No depende de `result`."""
    out = pd.Series(False, index=df.index)
    if df.empty or not {"league", "market"} <= set(df.columns):
        return out
    gen = (_ts(df["generated_at"]) if "generated_at" in df.columns
           else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]"))
    for (league, market), since in INVALID_BEFORE.items():
        seg = (df["league"].astype(str) == league) & (df["market"].astype(str) == market)
        valido = (gen >= pd.Timestamp(since)).fillna(False).astype(bool)
        out |= seg & ~valido
    return out


def quarter_line_mask(df: pd.DataFrame) -> pd.Series:
    """True en las filas totals/spreads de linea de cuarto con instante de
    generacion anterior a `QUARTER_LINE_INVALID_BEFORE` o ilegible (Addendum
    2026-10-18, AUD-008; misma semantica que `sqp.settlement.quarter_line_fix`).
    No depende de `result`."""
    out = pd.Series(False, index=df.index)
    if df.empty or not {"market", "line"} <= set(df.columns):
        return out
    gen = (_ts(df["generated_at"]) if "generated_at" in df.columns
           else pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]"))
    linea = _num(df, "line")
    cuarto = df["market"].astype(str).isin(_QUARTER_LINE_MARKETS) & linea.map(
        lambda x: bool(np.isfinite(x) and is_quarter_line(float(x))))
    antes = ~(gen >= pd.Timestamp(QUARTER_LINE_INVALID_BEFORE)).fillna(False).astype(bool)
    return (cuarto & antes).astype(bool)


def build_population(graded: pd.DataFrame, t1: pd.Timestamp | None) -> dict[str, Any]:
    """Pasos 1-6 de E3, en el orden vinculante. `t1=None` omite el corte (5).

    Devuelve `frame` (poblacion medida: una fila por pick, la primera
    servida), `counts` (recuento de cada paso), `filtradas` (filas tras el
    paso 2, con `p_cal`, para la sensibilidad sin colapsar) y `gid`."""
    counts: dict[str, Any] = {"filas_entrada": int(len(graded))}
    if graded.empty:
        counts["vacio"] = True
        return {"frame": graded, "counts": counts, "filtradas": graded,
                "malos_gid": set(), "gid": pd.Series(dtype=int)}
    faltan = [c for c in _REQUIRED_COLS if c not in graded.columns]
    if faltan:
        raise SystemExit(f"graded: faltan columnas obligatorias {faltan}.")
    # 1. resultado binario
    res = graded["result"].astype(object).where(graded["result"].notna(), "<vacio>")
    binario = res.isin(["win", "loss"])
    counts["resultado_excluido_por_valor"] = {
        str(k): int(v) for k, v in res[~binario].value_counts().items()}
    d = graded[binario.to_numpy()].copy()
    # 2. probabilidades presentes y finitas
    cal = _num(d, "calibrated_probability")
    fair = _num(d, "implied_probability_novig")
    fin = np.isfinite(cal.to_numpy(float)) & np.isfinite(fair.to_numpy(float))
    counts["sin_probabilidades"] = int((~fin).sum())
    d = d[fin].copy()
    d["calibrated_probability"] = cal[fin].to_numpy(float)
    d["implied_probability_novig"] = fair[fin].to_numpy(float)
    d["p_cal"] = 2.0 * d["calibrated_probability"] - d["implied_probability_novig"]
    counts["filas_tras_filtros"] = int(len(d))
    if d.empty:
        return {"frame": d, "counts": counts, "filtradas": d, "malos_gid": set(),
                "gid": pd.Series(dtype=int)}
    # 3. colapso a la primera servida (importado, no copiado)
    primeras = one_row_per_pick(d)
    counts["picks_tras_colapso"] = int(len(primeras))
    keys = [c for c in PICK_KEY if c in d.columns]
    gid = d.groupby(keys, dropna=False).ngroup()
    # 4. p_cal en [0,1] sobre la primera servida; el pick entero fuera si no
    p_cal = primeras["p_cal"].to_numpy(float)
    fuera = ~((p_cal >= 0.0) & (p_cal <= 1.0))
    counts["picks_p_cal_fuera_de_rango"] = int(fuera.sum())
    # 4b. Addendum 2026-10-17 (AUD-003): si la primera servida es de un
    # `liga|mercado` con no-vig falso en su instante, el pick entero fuera; no
    # se sustituye por una servida posterior (misma regla que el paso 4).
    invalido = invalid_market_mask(primeras).to_numpy() & ~fuera
    counts["picks_mercado_invalido_aud003"] = int(invalido.sum())
    # 4c. Addendum 2026-10-18 (AUD-008): primera servida de linea de cuarto
    # anterior al arreglo de su liquidacion -> el pick entero fuera.
    cuarto = quarter_line_mask(primeras).to_numpy() & ~fuera & ~invalido
    counts["picks_linea_cuarto_aud008"] = int(cuarto.sum())
    invalido = invalido | cuarto
    malos_gid = {int(g) for g in gid.loc[primeras.index[fuera | invalido]]}
    p4 = primeras[~(fuera | invalido)].copy()
    counts["eventos_sin_corte"] = int(p4["event_id"].nunique())
    counts["picks_sin_corte"] = int(len(p4))
    # 5. corte temporal sobre el generated_at de ESA primera servida
    gen = _ts(p4["generated_at"])
    ilegible = gen.isna()
    if t1 is not None:
        posterior = (~ilegible) & (gen > t1)
        counts["primera_servida_generated_at_ilegible"] = int(ilegible.sum())
        counts["primera_servida_posterior_a_t1"] = int(posterior.sum())
        p5 = p4[((~ilegible) & (gen <= t1)).to_numpy()].copy()
    else:
        counts["primera_servida_generated_at_ilegible"] = int(ilegible.sum())
        counts["primera_servida_posterior_a_t1"] = 0
        p5 = p4
    # Informativo (no excluye): primera servida no pregame
    if "start_time" in p5.columns and len(p5):
        st = _ts(p5["start_time"])
        g5 = _ts(p5["generated_at"])
        counts["primera_servida_start_time_ilegible"] = int(st.isna().sum())
        counts["primera_servida_no_pregame"] = int(((~st.isna()) & (g5 >= st)).sum())
    else:
        counts["primera_servida_start_time_ilegible"] = 0
        counts["primera_servida_no_pregame"] = 0
    # 6. poblacion medida
    counts["n_eventos"] = int(p5["event_id"].nunique())
    counts["n_picks"] = int(len(p5))
    return {"frame": p5, "counts": counts, "filtradas": d, "malos_gid": malos_gid, "gid": gid}


def events_by_segment(pop: pd.DataFrame) -> dict[str, int]:
    if pop.empty:
        return {}
    g = pop.groupby(_SEGMENT_COLS)["event_id"].nunique()
    return {f"{k[0]}|{k[1]}": int(v) for k, v in g.items()}


def eligible_segments(pop: pd.DataFrame) -> list[str]:
    return sorted(k for k, v in events_by_segment(pop).items() if v >= SEG_MIN_EVENTS)


def _key_strings(df: pd.DataFrame) -> pd.Series:
    """Clave de pick como texto (solo para pertenencia en el recuento 'sin graduar')."""
    def txt(s: pd.Series) -> pd.Series:
        return s.map(lambda v: "" if pd.isna(v) else str(v)).astype(object)
    linea = (_num(df, "line").round(4) + 0.0) if "line" in df.columns else pd.Series(
        float("nan"), index=df.index)
    return (txt(df["event_id"]) + "|" + txt(df["market"]) + "|" + txt(linea) + "|"
            + txt(df["selection"]))


def count_sin_graduar(served: pd.DataFrame, graded_all: pd.DataFrame,
                      t1: pd.Timestamp) -> int | None:
    """Picks servidos (primera servida <= T1, start_time <= T1) ausentes del graduado."""
    need = {"event_id", "market", "selection", "generated_at", "start_time"}
    if served.empty:
        return 0
    if not need.issubset(served.columns):
        return None
    primeras = one_row_per_pick(served)
    gen = _ts(primeras["generated_at"])
    st = _ts(primeras["start_time"])
    sel = primeras[((gen <= t1) & (st <= t1)).to_numpy()]
    if sel.empty:
        return 0
    if graded_all.empty or not {"event_id", "market", "selection"}.issubset(graded_all.columns):
        return int(len(sel))
    en_grad = set(_key_strings(graded_all))
    return int((~_key_strings(sel).isin(en_grad)).sum())


# -------------------------------------------------------- E7 y consistencia --
def s_check(pop: pd.DataFrame) -> dict[str, Any]:
    """E7: `s_hat = (a - estimated_probability)/(a - fair)` sobre primeras
    servidas con |a - fair| >= 0.02; `a = adjusted_probability` con fallback
    por fila a `model_probability`. No depende de `result`."""
    if pop.empty:
        return {"verificable": False, "ok": False, "razon": "poblacion vacia"}
    a = _num(pop, "adjusted_probability").fillna(_num(pop, "model_probability"))
    fair = _num(pop, "implied_probability_novig")
    est = _num(pop, "estimated_probability")
    m = ((a - fair).abs() >= MIN_GAP_S) & np.isfinite(est) & np.isfinite(a)
    n = int(m.sum())
    out: dict[str, Any] = {"n_filas": n}
    cal = _num(pop, "calibrated_probability")
    price = _num(pop, "price_decimal")
    edge = _num(pop, "estimated_edge")
    me = np.isfinite(cal) & np.isfinite(price) & np.isfinite(edge)
    if int(me.sum()):
        incons = ((cal[me] * price[me] - 1.0 - edge[me]).abs() > 0.001 + 0.0001 * price[me])
        out["fraccion_edge_inconsistente"] = float(incons.mean())
    # Descriptivo, sin poder de decision: solo filas que SI traen
    # adjusted_probability (las de esquema antiguo usan fallback y p_adj no guardado).
    a_raw = _num(pop, "adjusted_probability")
    m2 = ((a_raw - fair).abs() >= MIN_GAP_S) & np.isfinite(est) & np.isfinite(a_raw)
    n2 = int(m2.sum())
    desc: dict[str, Any] = {"n_filas": n2}
    if n2:
        sh2 = (a_raw[m2] - est[m2]) / (a_raw[m2] - fair[m2])
        desc.update(mediana_s_hat=float(sh2.median()),
                    fraccion_fuera_de_0_05=float(((sh2 - S_ESPERADO).abs() > S_TOL_FILA).mean()))
    out["descriptivo_solo_con_adjusted_probability"] = desc
    if n == 0:
        out.update(verificable=False, ok=False, razon="sin filas con |a - fair| >= 0.02")
        return out
    s_hat = (a[m] - est[m]) / (a[m] - fair[m])
    med = float(s_hat.median())
    frac = float(((s_hat - S_ESPERADO).abs() > S_TOL_FILA).mean())
    ok = (abs(med - S_ESPERADO) <= S_TOL_MEDIANA) and (frac <= S_TOL_FRAC)
    out.update(verificable=True, ok=bool(ok), mediana_s_hat=med,
               fraccion_fuera_de_0_05=frac)
    return out


def market_shrink_counts(df: pd.DataFrame) -> dict[str, Any]:
    """Procedencia: filas del graduado con `market_shrink` no nulo y con valor
    distinto de 0,5 (columna nueva del stream; vacia en filas historicas). No
    se usa en la medicion."""
    if df.empty or "market_shrink" not in df.columns:
        return {"columna_presente": "market_shrink" in df.columns, "no_nulas": 0, "distintas_de_0_5": 0}
    v = _num(df, "market_shrink")
    nn = v.notna()
    return {"columna_presente": True, "no_nulas": int(nn.sum()),
            "distintas_de_0_5": int((nn & ((v - S_ESPERADO).abs() > 1e-9)).sum())}


def config_check(root: Path) -> dict[str, Any]:
    """E7: `market_shrink` efectivo y literales de E6 frente a `configs/default.yaml`.
    Solo se REGISTRA, no decide."""
    out: dict[str, Any] = {}
    literales = {"min_edge": E6_MIN_EDGE, "max_plausible_edge": E6_MAX_PLAUSIBLE,
                 "uncertainty_penalty": E6_UNCERTAINTY, "anomaly_edge_gap": E6_ANOMALY_GAP,
                 "anomaly_extra_penalty": E6_ANOMALY_EXTRA, "low_book_penalty": E6_LOW_BOOK,
                 "min_books_for_consensus": E6_MIN_BOOKS, "market_shrink": S_ESPERADO,
                 "line_movement_penalty": 0.0, "line_velocity_penalty": 0.0,
                 "books_spread_penalty": 0.0}
    try:
        from sqp.config import Settings, load_yaml
        risk = load_yaml(root / "configs" / "default.yaml").get("risk", {})
        out["yaml_vs_literales"] = {
            k: {"literal": v, "yaml": risk.get(k), "coincide": risk.get(k) == v}
            for k, v in literales.items()}
        out["settings_market_shrink_efectivo"] = float(Settings.load().risk.market_shrink)
    except Exception as exc:  # noqa: BLE001 -- informativo
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


# --------------------------------------------------------- estadistica (E5) --
def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def cr1_by_event(d: np.ndarray, clusters: np.ndarray) -> dict[str, Any]:
    """z bilateral con SE robusto CR1 por evento (E5):

        D = mean(d)   SE^2 = G/(G-1) * sum_g (sum_{i in g}(d_i - D))^2 / n^2
        z = D/SE      p = 2*Phi(-|z|)
    """
    d = np.asarray(d, dtype=float)
    n = len(d)
    if n == 0:
        return {"n": 0, "g": 0, "d_hat": None, "se": None, "z": None, "p": None}
    d_hat = float(d.mean())
    _, inv = np.unique(clusters, return_inverse=True)
    g = int(inv.max()) + 1
    if g <= 1:
        return {"n": n, "g": g, "d_hat": d_hat, "se": None, "z": None, "p": None}
    sums = np.bincount(inv, weights=d - d_hat, minlength=g)
    se = math.sqrt((g / (g - 1)) * float(np.sum(sums ** 2)) / (n ** 2))
    if se <= 0.0:
        return {"n": n, "g": g, "d_hat": d_hat, "se": se, "z": None, "p": None}
    z = d_hat / se
    return {"n": n, "g": g, "d_hat": d_hat, "se": se, "z": z, "p": 2.0 * _phi(-abs(z))}


def holm(pvals: dict[str, float | None], alpha: float = HOLM_ALPHA) -> dict[str, dict[str, Any]]:
    """Holm a nivel `alpha` de familia sobre las `m` hipotesis dadas (E5): se
    ordenan los p ascendentes (p ausente = 1) y se rechaza el j-esimo mientras
    `p_(j) <= alpha/(m-j+1)`; al primer no-rechazo se para."""
    m = len(pvals)
    orden = sorted(pvals, key=lambda k: (1.0 if pvals[k] is None else float(pvals[k] or 0.0), k))
    out: dict[str, dict[str, Any]] = {}
    parar = False
    for j, k in enumerate(orden, start=1):
        umbral = alpha / (m - j + 1)
        p = 1.0 if pvals[k] is None else float(pvals[k] or 0.0)
        rechaza = (not parar) and p <= umbral
        if not rechaza:
            parar = True
        out[k] = {"umbral_holm": umbral, "rechaza": bool(rechaza), "orden": j}
    return out


def _ic_class(lo: float, hi: float) -> str:
    if hi < 0:
        return "modelo_mejor"
    if lo > 0:
        return "modelo_peor"
    return "cruza_0"


def primary_test(pop: pd.DataFrame, seed: int, n_boot: int) -> dict[str, Any]:
    """E5 primario: `score_model_vs_market(by=['_global'], model_col='p_cal')`."""
    d = pop.assign(_global="global")
    res = score_model_vs_market(d, by=["_global"], n_boot=n_boot, seed=seed,
                                model_col="p_cal",
                                market_col="implied_probability_novig")
    if res.empty:
        return {"decision": "FALLA", "modelo_peor": False, "vacio": True}
    r = res.iloc[0]
    lo, hi = float(r["brier_diff_lo"]), float(r["brier_diff_hi"])
    return {"decision": "PASA" if hi < 0 else "FALLA", "modelo_peor": bool(lo > 0),
            "n_picks": int(r["n_rows"]), "n_eventos": int(r["n_events"]),
            "brier_model": float(r["brier_model"]), "brier_market": float(r["brier_market"]),
            "brier_diff": float(r["brier_diff"]), "brier_diff_lo": lo, "brier_diff_hi": hi,
            "veredicto_score": str(r["veredicto"])}


def secondary_tests(pop: pd.DataFrame, seed: int, n_boot: int) -> dict[str, Any]:
    """E5 secundarios: segmentos `league|market` con >= SEG_MIN_EVENTS eventos,
    p-valor CR1 por evento y Holm. Se deciden SIEMPRE, pase o no el primario."""
    elig = eligible_segments(pop)
    if not elig:
        return {"m": 0, "segmentos": {}, "nota": "m = 0: no hay secundarios."}
    seg = pop["league"].astype(str) + "|" + pop["market"].astype(str)
    y = (pop["result"] == "win").astype(float)
    d_all = ((pop["p_cal"] - y) ** 2 - (pop["implied_probability_novig"] - y) ** 2)
    stats: dict[str, dict[str, Any]] = {}
    for s in elig:
        mask = (seg == s).to_numpy()
        stats[s] = cr1_by_event(d_all[mask].to_numpy(float),
                                pop.loc[mask, "event_id"].to_numpy())
    h = holm({s: stats[s]["p"] for s in elig})
    sub = pop[seg.isin(elig).to_numpy()]
    ic = score_model_vs_market(sub, by=_SEGMENT_COLS, n_boot=n_boot, seed=seed,
                               model_col="p_cal", market_col="implied_probability_novig")
    ic_by = {f"{r['league']}|{r['market']}": (float(r["brier_diff_lo"]), float(r["brier_diff_hi"]))
             for _, r in ic.iterrows()}
    out: dict[str, Any] = {}
    for s in elig:
        st, hh = stats[s], h[s]
        d_hat = st["d_hat"]
        if hh["rechaza"] and d_hat is not None and d_hat < 0:
            dec = "PASA_PRIMERA_PUERTA"
        elif hh["rechaza"] and d_hat is not None and d_hat > 0:
            dec = "MODELO_PEOR"
        else:
            dec = "NO_RECHAZA"
        lo, hi = ic_by.get(s, (float("nan"), float("nan")))
        clase_ic = _ic_class(lo, hi) if not math.isnan(lo) else None
        clase_h = {"PASA_PRIMERA_PUERTA": "modelo_mejor", "MODELO_PEOR": "modelo_peor"}.get(
            dec, "cruza_0")
        out[s] = {**st, **hh, "decision": dec,
                  "ic_bootstrap": {"lo": lo, "hi": hi, "clase": clase_ic},
                  "fragil": bool(clase_ic is not None and clase_ic != clase_h)}
    return {"m": len(elig), "segmentos": out}


# ----------------------------------------------------------- ROI (E6) --
def bet_mask(p: np.ndarray, price: np.ndarray, fair: np.ndarray, books: np.ndarray,
             rule: str = "full") -> tuple[np.ndarray, np.ndarray]:
    """(apuesta?, e) con la regla del modo `edge` congelada en E6 (literales
    propios; no se lee ninguna configuracion). `rule='simple'` es la regla
    descriptiva `0.02 <= e <= 0.075` sin penalizacion."""
    p = np.asarray(p, float)
    price = np.asarray(price, float)
    fair = np.asarray(fair, float)
    books = np.nan_to_num(np.asarray(books, float), nan=0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        e = p * price - 1.0
        base = np.isfinite(p) & np.isfinite(price) & np.isfinite(fair) & (price > 1.0)
        if rule == "simple":
            bet = base & (p > 0.0) & (p < 1.0) & (e >= E6_MIN_EDGE) & (e <= E6_MAX_PLAUSIBLE)
            return bet, e
        gap = np.abs(p - fair)
        pen = (E6_UNCERTAINTY * gap + np.where(gap > E6_ANOMALY_GAP, E6_ANOMALY_EXTRA, 0.0)
               + np.where(books < E6_MIN_BOOKS, E6_LOW_BOOK, 0.0))
        e_adj = e - np.maximum(0.0, pen)
        p_eff = (e_adj + 1.0) / price
        bet = (base & (p_eff > 0.0) & (p_eff < 1.0) & (e_adj >= E6_MIN_EDGE)
               & (e <= E6_MAX_PLAUSIBLE))
    return bet, e


def roi_comparison(unit: pd.DataFrame, seed: int, n_boot: int,
                   rule: str = "full") -> dict[str, Any]:
    """E6: `Delta = ROI_0 - ROI_0.5`, stake plano de 1, IC95 bootstrap por evento
    (`default_rng(seed)`, percentiles 2.5 y 97.5)."""
    price = _num(unit, "price_decimal").to_numpy(float)
    fair = unit["implied_probability_novig"].to_numpy(float)
    books = _num(unit, "books_count").to_numpy(float)
    win = (unit["result"] == "win").to_numpy()
    pnl_all = np.where(win, price - 1.0, -1.0)
    pols = {"s_0_5": unit["calibrated_probability"].to_numpy(float),
            "s_0": unit["p_cal"].to_numpy(float)}
    _, inv = np.unique(unit["event_id"].to_numpy(), return_inverse=True)
    g = int(inv.max()) + 1 if len(inv) else 0
    sums: dict[str, np.ndarray] = {}
    cnts: dict[str, np.ndarray] = {}
    desc: dict[str, Any] = {}
    for name, p in pols.items():
        bet, e = bet_mask(p, price, fair, books, rule)
        sums[name] = np.bincount(inv, weights=np.where(bet, pnl_all, 0.0), minlength=g)
        cnts[name] = np.bincount(inv, weights=bet.astype(float), minlength=g)
        nb = int(bet.sum())
        d_pol: dict[str, Any] = {"n_apuestas": nb}
        if nb:
            d_pol.update(roi_realizado=float(pnl_all[bet].mean()),
                         roi_esperado=float(e[bet].mean()),
                         acierto_observado=float(win[bet].mean()),
                         prob_prometida_media=float(p[bet].mean()))
            if "execution_price" in unit.columns:
                ex = _num(unit, "execution_price").to_numpy(float)
                ok = bet & np.isfinite(ex)
                d_pol["execution_price_informativo"] = {
                    "n_con_execution_price": int(ok.sum()),
                    "roi_realizado": (float(np.where(win[ok], ex[ok] - 1.0, -1.0).mean())
                                      if ok.any() else None)}
                reg = execution_regime(unit["generated_at"] if "generated_at" in unit.columns
                                       else pd.Series(pd.NaT, index=unit.index))
                d_pol["execution_price_informativo"]["por_regimen"] = {
                    lab: {"n_con_execution_price": int((ok & (reg == lab)).sum()),
                          "roi_realizado": (float(np.where(win[ok & (reg == lab)],
                                                           ex[ok & (reg == lab)] - 1.0,
                                                           -1.0).mean())
                                            if (ok & (reg == lab)).any() else None)}
                    for lab in EXECUTION_REGIMES}
        desc[name] = d_pol
    out: dict[str, Any] = {"regla": rule, "politicas": desc}
    n0, n5 = float(cnts["s_0"].sum()), float(cnts["s_0_5"].sum())
    if n0 == 0 or n5 == 0 or g < 2:
        out.update(decision="FALLA", razon="alguna politica no apuesta nada en la muestra "
                   "observada (o hay menos de 2 eventos)")
        return out
    roi0 = float(sums["s_0"].sum() / n0)
    roi5 = float(sums["s_0_5"].sum() / n5)
    rng = np.random.default_rng(seed)
    deltas: list[np.ndarray] = []
    indef = 0
    lote = 500
    hecho = 0
    while hecho < n_boot:
        k = min(lote, n_boot - hecho)
        idx = rng.integers(0, g, size=(k, g))
        s0, c0 = sums["s_0"][idx].sum(axis=1), cnts["s_0"][idx].sum(axis=1)
        s5, c5 = sums["s_0_5"][idx].sum(axis=1), cnts["s_0_5"][idx].sum(axis=1)
        ok = (c0 > 0) & (c5 > 0)
        indef += int((~ok).sum())
        deltas.append(s0[ok] / c0[ok] - s5[ok] / c5[ok])
        hecho += k
    dd = np.concatenate(deltas) if deltas else np.array([])
    frac_indef = indef / n_boot
    lo, hi = (float(np.quantile(dd, 0.025)), float(np.quantile(dd, 0.975))) if len(dd) else (
        float("nan"), float("nan"))
    pasa = bool(len(dd) and lo > 0 and frac_indef <= MAX_REPLICAS_INDEFINIDAS)
    out.update(roi_s_0=roi0, roi_s_0_5=roi5, delta=roi0 - roi5, ic95_lo=lo, ic95_hi=hi,
               replicas_indefinidas=indef, fraccion_indefinidas=frac_indef,
               decision="PASA" if pasa else "FALLA")
    return out


def second_gate(pop: pd.DataFrame, primario: dict[str, Any], secundarios: dict[str, Any],
                seed: int, n_boot: int) -> dict[str, Any]:
    """E6: solo a las unidades que pasaron la primera puerta."""
    unidades: dict[str, pd.DataFrame] = {}
    if primario.get("decision") == "PASA":
        unidades["global"] = pop
    seg = pop["league"].astype(str) + "|" + pop["market"].astype(str)
    for s, v in secundarios.get("segmentos", {}).items():
        if v["decision"] == "PASA_PRIMERA_PUERTA":
            unidades[s] = pop[(seg == s).to_numpy()]
    if not unidades:
        return {"nota": "ninguna unidad paso la primera puerta: no se calcula."}
    return {u: {"principal": roi_comparison(f, seed, n_boot, "full"),
                "sensibilidad_regla_simple": roi_comparison(f, seed, n_boot, "simple")}
            for u, f in unidades.items()}


def uncollapsed_sensitivity(res: dict[str, Any], t1: pd.Timestamp | None,
                            seed: int, n_boot: int) -> dict[str, Any]:
    """Sensibilidad (sin poder de decision): todas las servidas, sin colapsar."""
    d = res["filtradas"]
    if d.empty:
        return {"vacio": True}
    rows = d[~res["gid"].isin(res["malos_gid"])]
    p_in = (rows["p_cal"] >= 0.0) & (rows["p_cal"] <= 1.0)
    rows = rows[p_in.to_numpy()]
    if t1 is not None:
        gen = _ts(rows["generated_at"])
        rows = rows[((~gen.isna()) & (gen <= t1)).to_numpy()]
    y = (rows["result"] == "win").to_numpy(float)
    diff = ((rows["p_cal"].to_numpy(float) - y) ** 2
            - (rows["implied_probability_novig"].to_numpy(float) - y) ** 2)
    lo, hi = cluster_bootstrap_ci(diff, rows["event_id"].to_numpy(), n_boot=n_boot, seed=seed)
    return {"n_filas": int(len(rows)), "n_eventos": int(rows["event_id"].nunique()),
            "brier_diff": float(diff.mean()) if len(diff) else None,
            "ic95_lo": lo, "ic95_hi": hi, "pasa": bool(hi < 0)}


def sensitivity_primary(pop: pd.DataFrame, seed: int, n_boot: int) -> dict[str, Any]:
    if pop.empty:
        return {"vacio": True}
    r = primary_test(pop, seed, n_boot)
    return {k: r.get(k) for k in ("decision", "n_picks", "n_eventos", "brier_diff",
                                  "brier_diff_lo", "brier_diff_hi")}


# ------------------------------------------------------ procedencia (E8) --
def provenance(git_cwd: Path) -> dict[str, Any]:
    head = git_rev_parse("HEAD", git_cwd)
    blobs = {rel: {"hash_head": git_blob_hash("HEAD", rel, git_cwd),
                   "hash_disco": git_hash_object(rel, git_cwd)} for rel in _BLOB_FILES}
    return {"head": head, "blobs": blobs,
            "git_status_porcelain": git_status_porcelain(git_cwd),
            "python": sys.version.split()[0], "pandas": pd.__version__,
            "numpy": np.__version__}


def contar_log_path(preregistro: Path) -> Path:
    stem = preregistro.name[:-3] if preregistro.name.endswith(".md") else preregistro.name
    return preregistro.parent / f"{stem}.contar.jsonl"


def _hash_commit_info(preregistro: Path, git_cwd: Path) -> dict[str, Any]:
    rel = _relpath(preregistro, git_cwd)
    return {"h_mm": git_log_added(rel, git_cwd) if rel else None,
            "commit_addendum_e": (git_commit_introducing(_ADDENDUM_E_MARCA, rel, git_cwd)
                                  if rel else None)}


# ----------------------------------------------------------- modo --contar --
def run_contar(args: argparse.Namespace) -> dict[str, Any]:
    git_cwd = _WORKTREE_ROOT
    e = pd.Timestamp.now(tz="UTC")
    t1c = e - pd.Timedelta(days=MARGEN_DIAS)
    graded_raw, prov_g = read_stream(args.data_root, "graded")
    served_raw, prov_s = read_stream(args.data_root, "served")
    graded, n_no_real = filter_real(graded_raw)
    served, _ = filter_real(served_raw)
    res = build_population(graded, t1c)
    pop = res["frame"]
    seg_events = events_by_segment(pop)
    counts = res["counts"]
    registro: dict[str, Any] = {
        "instante_ejecucion_utc": e.isoformat(),
        "head": git_rev_parse("HEAD", git_cwd),
        **{k: v for k, v in _hash_commit_info(args.preregistro, git_cwd).items()
           if k == "h_mm"},
        "t1_candidato": t1c.isoformat(),
        "n_eventos": int(counts.get("n_eventos", 0)),
        "n_picks": int(counts.get("n_picks", 0)),
        "n_eventos_sin_corte": int(counts.get("eventos_sin_corte", 0)),
        "eventos_por_segmento": seg_events,
        "segmentos_con_800_o_mas": sorted(k for k, v in seg_events.items()
                                          if v >= SEG_MIN_EVENTS),
        "exclusiones": {**{k: v for k, v in counts.items()
                           if k not in ("n_eventos", "n_picks", "eventos_sin_corte")},
                        "filas_data_label_no_real": n_no_real},
        "picks_sin_graduar": count_sin_graduar(served, graded_raw, t1c),
        "chequeo_s": s_check(pop),
        "csv_leidos": {"graded": prov_g["ficheros"], "served": prov_s["ficheros"]},
        "ligas": {"graded": {k: prov_g[k] for k in ("listadas", "cargadas", "vacias", "faltantes")},
                  "served": {k: prov_s[k] for k in ("listadas", "cargadas", "vacias", "faltantes")}},
    }
    if not args.no_log:
        log_path = contar_log_path(args.preregistro)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
        aviso = f"Linea anadida a {log_path}."
    else:
        aviso = "--no-log: NO se escribio en el registro .contar.jsonl (diagnostico)."
    return {"modo": "contar", "registro": registro, "aviso": aviso,
            "errores_lectura": {"graded": prov_g["errores_lectura"],
                                "served": prov_s["errores_lectura"]}}


# ------------------------------------------------------------ modo --medir --
def parse_t1_addendum(doc_text: str) -> tuple[str, str] | None:
    """Dos LINEAS literales (ver ambiguedad 1 del docstring). `None` si faltan;
    aborta si hay varios T1 validos distintos."""
    t1s = [m for m in re.findall(r"(?m)^[ \t]*T1 fijado[ \t]*=[ \t]*(\S+)[ \t]*$", doc_text)
           if _parse_ts(m) is not None]
    cms = re.findall(r"(?m)^[ \t]*commit del registro[ \t]*=[ \t]*([0-9a-fA-F]{7,40})[ \t]*$",
                     doc_text)
    if not t1s or not cms:
        return None
    if len({_parse_ts(x) for x in t1s}) > 1 or len(set(cms)) > 1:
        raise SystemExit("Hay varios addenda de T1 distintos en el pre-registro. --medir aborta.")
    return t1s[-1], cms[-1]


def _parse_jsonl_text(text: str) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (text or "").splitlines() if x.strip()]


def find_first_n_over(lines: list[dict[str, Any]], threshold: int) -> dict[str, Any] | None:
    for fila in lines:
        if fila.get("n_eventos", 0) >= threshold:
            return fila
    return None


def _verify_registry(args: argparse.Namespace, git_cwd: Path) -> tuple[pd.Timestamp, str, dict[str, Any]]:
    rel_pre = _relpath(args.preregistro, git_cwd)
    rel_jsonl = _relpath(contar_log_path(args.preregistro), git_cwd)
    if rel_pre is None or rel_jsonl is None:
        raise SystemExit("El pre-registro o su registro no estan dentro del arbol de trabajo. "
                         "--medir aborta: no se pueden leer con git.")
    stem_glob = (Path(rel_pre).parent / f"{Path(rel_pre).stem}*").as_posix()
    _check_git_clean(git_status_porcelain(git_cwd, (*_GIT_STATUS_PATHS, stem_glob)))
    doc_text = git_show_text("HEAD", rel_pre, git_cwd)
    add = parse_t1_addendum(doc_text)
    if add is None:
        raise SystemExit("No hay addendum que fije T1 en el pre-registro (E4). --medir aborta.")
    t1_txt, commit = add
    t1_add = _parse_ts(t1_txt)
    t1_ped = _parse_ts(args.t1)
    if t1_add is None or t1_ped is None or t1_ped != t1_add:
        raise SystemExit(f"--t1 {args.t1!r} no coincide (como instante) con el T1 del "
                         f"addendum ({t1_txt!r}). --medir aborta (E4).")
    lines = _parse_jsonl_text(git_show_text("HEAD", rel_jsonl, git_cwd))
    primera = find_first_n_over(lines, N_REQUIRED)
    t1_prim = _parse_ts(primera.get("t1_candidato")) if primera else None
    if primera is None or t1_prim is None or t1_prim != t1_add:
        raise SystemExit("El registro (HEAD) no tiene una primera linea con "
                         f"n_eventos >= {N_REQUIRED} cuyo T1 candidato coincida con el del "
                         "addendum. --medir aborta (E4).")
    lines_c = _parse_jsonl_text(git_show_text(commit, rel_jsonl, git_cwd))
    prim_c = find_first_n_over(lines_c, N_REQUIRED)
    t1_c = _parse_ts(prim_c.get("t1_candidato")) if prim_c else None
    if prim_c is None or t1_c is None or t1_c != t1_add:
        raise SystemExit(f"El commit del registro citado ({commit}) no contiene esa primera "
                         f"linea con n_eventos >= {N_REQUIRED}. --medir aborta.")
    return t1_add, commit, {"t1_addendum": t1_txt, "commit_registro": commit,
                            "primera_linea_registro": primera}


def run_medir(args: argparse.Namespace) -> dict[str, Any]:
    git_cwd = _WORKTREE_ROOT
    t1, commit, reg_info = _verify_registry(args, git_cwd)

    graded_raw, prov_g = read_stream(args.data_root, "graded")
    if prov_g["faltantes"] or prov_g["errores_lectura"]:
        raise SystemExit(f"graded: ligas listadas no cargadas: {prov_g['faltantes']} "
                         f"(errores: {prov_g['errores_lectura']}). --medir aborta (E2).")
    graded, n_no_real = filter_real(graded_raw)
    res = build_population(graded, t1)
    pop = res["frame"]
    n = int(res["counts"].get("n_eventos", 0))
    if n < N_REQUIRED:
        raise SystemExit(f"n(T1) = {n} < {N_REQUIRED}. --medir aborta (E4).")
    chk = s_check(pop)
    if not chk.get("ok"):
        raise SystemExit(f"E7: `s` no verificada en tolerancia ({chk}). --medir aborta; "
                         "el pre-registro debe reescribirse (amenaza 2). No se midio nada.")

    # ---- a partir de aqui se calculan cosas que dependen de `result` ----
    primario = primary_test(pop, args.seed, args.n_boot)
    secundarios = secondary_tests(pop, args.seed, args.n_boot)
    puerta2 = second_gate(pop, primario, secundarios, args.seed, args.n_boot)

    sens: dict[str, Any] = {
        "todas_las_servidas_sin_colapsar": uncollapsed_sensitivity(res, t1, args.seed,
                                                                   args.n_boot),
        "sin_corte_t1": sensitivity_primary(build_population(graded, None)["frame"],
                                            args.seed, args.n_boot),
    }
    if n_no_real > 0:
        sens["sin_filtro_data_label"] = sensitivity_primary(
            build_population(graded_raw, t1)["frame"], args.seed, args.n_boot)

    prov = provenance(git_cwd)
    prov.update({
        **_hash_commit_info(args.preregistro, git_cwd),
        "commit_registro": commit,
        # Pickaxe con el valor de T1: "T1 fijado =" a secas casaria con la cita
        # del propio addendum E4 y devolveria ese commit.
        "commit_addendum_t1": git_commit_introducing(
            f"T1 fijado = {reg_info['t1_addendum']}",
            _relpath(args.preregistro, git_cwd) or "", git_cwd),
        "market_shrink_en_graduado": market_shrink_counts(graded_raw),
        "t1": t1.isoformat(), "seed": args.seed, "n_boot": args.n_boot,
        "difiere_de_lo_congelado": bool(args.seed != SEED or args.n_boot != N_BOOT),
        "csv_graded": prov_g["ficheros"],
        "ligas_graded": {k: prov_g[k] for k in ("listadas", "cargadas", "vacias", "faltantes")},
        "filas_data_label_no_real": n_no_real,
        "registro": reg_info,
        "configuracion": config_check(git_cwd),
    })
    return {"modo": "medir", "procedencia": prov, "recuentos_e3": res["counts"],
            "chequeo_s": chk, "primario": primario, "secundarios": secundarios,
            "segunda_puerta": puerta2, "sensibilidades_sin_poder_de_decision": sens}


# --------------------------------------------------------------------- main --
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--preregistro", type=Path, default=DEFAULT_PREREGISTRO)
    ap.add_argument("--contar", action="store_true")
    ap.add_argument("--medir", action="store_true")
    ap.add_argument("--t1", default=None, help="ISO-8601, obligatorio con --medir.")
    ap.add_argument("--no-log", action="store_true",
                    help="Diagnostico: con --contar, no anade linea al registro.")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.contar and args.medir:
        ap.error("--contar y --medir son mutuamente excluyentes.")
    if args.medir and not args.t1:
        ap.error("--medir exige --t1 <ISO-8601>.")
    if not args.medir:
        args.contar = True
        if args.t1:
            ap.error("--t1 solo aplica a --medir.")
    if args.no_log and not args.contar:
        ap.error("--no-log solo aplica a --contar.")
    t_ini = time.perf_counter()
    out = run_medir(args) if args.medir else run_contar(args)
    out["segundos"] = time.perf_counter() - t_ini
    texto = json.dumps(out, indent=2, ensure_ascii=False, default=str)
    print(texto)
    if args.out:
        args.out.write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
