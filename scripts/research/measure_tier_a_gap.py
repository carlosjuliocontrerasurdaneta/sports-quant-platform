"""Medicion del pre-registro de la brecha del tier A del Tipster (2026-10-02).

Ver `docs/research/2026-10-02-preregistro-brecha-tier-a.md` (aprobado, seccion
10). Ese documento MANDA sobre este docstring: aqui solo se resumen decisiones
y se documentan las AMBIGUEDADES que el contrato no fijaba del todo, con la
decision tomada para resolverlas.

## Que mide

H0: el tier A acierta al menos lo que promete (D = E[y - p] >= 0).
H1: el tier A promete de mas (D < 0).

Universo PRIMARIO: stream servido (`data/calibration/served_*.csv`) + stream
graduado (`data/calibration/graded_*.csv`), seccion 2.2. Universo SECUNDARIO,
sin poder de decision: el ledger liquidado (`data/bets/settled_*.csv`).

El clasificador (tier A/B/C/NO BET) se congela en H: `classify`/`tipster_table`
de `src/sqp/evaluation/tipster.py` y `decision_prob` de
`src/sqp/evaluation/labels.py`, TAL COMO ESTAN en el commit H (tag anotado
`prereg-tier-a-t0`), con `max_plausible_ev = 0.075` como LITERAL, nunca leido
de configuracion (seccion 2.5). Si los blobs de esos dos ficheros en H
coinciden con los de HEAD (caso normal: hoy coinciden), se importan los
modulos normales de `sqp`. Si divergen, se cargan las fuentes de H via
`git show H:<ruta>` en un espacio de modulos AISLADO (nunca se sobreescribe
`sqp.evaluation.*` para el resto del proceso; el intercambio en
`sys.modules` es transitorio, solo mientras se ejecuta el `exec` de las dos
fuentes congeladas).

## Ambiguedades del contrato resueltas en este script (documentadas aqui
## porque el pre-registro no las fija con el detalle de una implementacion)

1. **`start_time` del ledger (seccion 2.2, 2.4, 3.1).** El esquema real de
   `data/bets/settled_*.csv` NO tiene columna `start_time` (si la tuviera en
   `data/calibration/served_*.csv`/`graded_*.csv`). El filtro "solo pregame"
   de la seccion 2.4 y el cluster de dia de la seccion 3.1 necesitan ese
   instante. Como el partido -- y por tanto su `start_time` -- es una
   propiedad del EVENTO y no de la fila que lo sirve o lo liquida, este
   script toma el `start_time` para la fila de decision del ledger de la
   PRIMERA servida de esa misma clave en `served_*.csv` (la que de todos
   modos hay que leer para decidir la ventana, seccion 2.2). Si la clave no
   aparece en absoluto en el stream servido, el `start_time` se trata como
   ILEGIBLE (excluido y contado por la seccion 2.4), exactamente igual que
   cualquier otra fila sin sello legible. Nunca se deriva de `game_date`
   (la seccion 3.1 prohibe ese fallback expresamente).
2. **Formato del addendum que fija T1 (seccion 4.3).** El documento dice que
   T1 se fija "en un addendum commiteado... con el hash del commit del
   registro que lo justifica", pero no fija el formato textual exacto (la
   seccion "Addenda" dice "Ninguno todavia"). Este script exige el formato
   literal (en cualquier parte del texto del pre-registro):

       T1 fijado = <ISO-8601>
       commit del registro = <sha-git>

   Si un addendum futuro usa otro formato, hay que actualizar
   `parse_t1_addendum`. Mientras no exista ese addendum (hoy, 2026-10-03),
   `--medir` SIEMPRE aborta por este motivo, que es ademas la salvaguarda que
   pide el encargo: no hay forma de ejecutar `--medir` sin ese addendum.
3. **Verificacion cruzada con `_unique_settled_picks` (seccion 2.3).** La
   clasificacion de diferencias en las tres clases documentadas (fila con
   stake, identidad incompleta por NaN, pertenencia a la ventana decidida por
   el stream servido) se implementa de forma best-effort: las dos primeras
   clases se detectan explicitamente; cualquier diferencia que no encaje en
   ellas --incluida la tercera clase, que exigiria recomputar la pertenencia
   a la ventana para cada fila de `_unique_settled_picks`-- cae en
   "discrepancia" para revision manual. Es informativo (S1 es secundario sin
   poder de decision), nunca decide el veredicto.
4. **Prioridad entre los motivos de exclusion de la seccion 2.4.** Una fila
   puede fallar varios filtros de validez a la vez. Para que los recuentos
   sean mutuamente excluyentes (y la suma coincida con el total excluido),
   este script cuenta cada fila UNA sola vez, en el orden en que la seccion
   2.4 los enumera: primero pregame (start_time ilegible, luego en vivo),
   despues p no finita, despues cuota invalida, despues sin novig. `pyp_mask`
   se aplica SOLO sobre las filas que ya pasaron `pregame_mask` (revision
   Fable, hallazgo L1): si se aplicara sobre toda la ventana, una fila que
   fallara los dos grupos se contaria dos veces.
5. **Blob de H vs. fichero EN DISCO, no solo HEAD (revision Fable, hallazgo
   M4).** Un import vivo de `sqp.evaluation.tipster`/`labels` lee el FICHERO
   del arbol de trabajo, no el commit HEAD. Comparar solo `hash(H)` contra
   `hash(HEAD)` no basta: si HEAD coincide con H pero el disco tiene cambios
   SIN COMMITEAR en esas dos rutas, el import vivo leeria esos cambios en
   silencio. Decision: se compara ademas `hash(H)` contra `git hash-object
   <fichero>` (el disco ahora mismo); si cualquiera de los dos difiere, se
   usa SIEMPRE la carga aislada desde H (nunca el import vivo), tanto en
   `--contar` como en `--medir`. No se opta por abortar `--contar`: la carga
   aislada ya es segura y correcta en cualquier caso, así que abortar solo
   anadiria friccion sin anadir seguridad. En `--medir`, `_check_git_clean`
   ya exige que `src/` (que incluye esas dos rutas) este limpio, asi que esta
   comparacion es ademas una defensa en profundidad.
6. **Zona de cluster y semilla/replicas del bootstrap en `--medir` (revision
   Fable, hallazgo M2 y L5).** El PRIMARIO de `--medir` (y los recuentos que
   disparan `--contar`) usan SIEMPRE `America/New_York`, sin importar lo que
   traiga `--tz-cluster`: es lo que exige la seccion 7 ("un valor distinto
   solo se admite como sensibilidad marcada, nunca para el primario"). Si
   `--tz-cluster` pide otra zona, `--medir` calcula una sensibilidad APARTE
   (`S5_sensibilidad_tz_cluster_alternativa`), claramente marcada, que nunca
   sustituye al primario. Del mismo modo, `--seed`/`--n-boot` distintos de
   los fijos (20261002 / 10000) NO abortan `--medir`: se marcan en la salida
   (`procedencia.seed_n_boot.difiere_de_lo_congelado`) para que cualquier
   lectura posterior vea que el bootstrap de esa ejecucion no uso los
   parametros congelados, en vez de abortar una ejecucion unica ya cara de
   repetir por un parametro que no es ninguno de los que decide el veredicto.
7. **AUD-003 (Addendum 2, 2026-10-17).** Tras pregame y antes de p/cuota/
   novig (recuentos mutuamente excluyentes, ambiguedad 4), la fila de
   decision de `nhl|h2h` con `generated_at` anterior a 2026-10-16T12:56:03Z
   (ffc5ad3) o ilegible se excluye y se cuenta (`mercado_invalido_aud003`),
   en el universo primario y en el ledger. No se salta a otra servida.

## Modos (seccion 7)

  --contar [--no-log]      Solo recuentos (n, G, fechas, T1 candidato,
                            picks sin graduar). NUNCA imprime y, p ni brecha.
                            Anade una linea a
                            `<preregistro>.contar.jsonl` (append-only),
                            salvo que se pase `--no-log` -- bandera de
                            DIAGNOSTICO, fuera del contrato original,
                            anadida para poder probar el modo sin escribir
                            en el registro oficial (encargo del coordinador).
  --medir --t1 <ISO>       Medicion UNICA. Exige un addendum commiteado que
                            fije T1 (ver ambiguedad 2) y que `n(T1) >= 2100`
                            con los datos del momento de medir. Aborta sin
                            calcular nada si alguna comprobacion falla.

PROHIBIDO ejecutar `--medir` contra datos de produccion antes de que exista
ese addendum (y el encargo de esta tarea lo prohibe explicitamente en
cualquier caso). `--contar` SI se puede ejecutar: no revela ningun resultado.

  python scripts/research/measure_tier_a_gap.py --contar --data-root <root>
  python scripts/research/measure_tier_a_gap.py --contar --no-log --data-root <root>
  python scripts/research/measure_tier_a_gap.py --medir --t1 2027-05-01T00:00:00Z --out out.json
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import re
import subprocess
import sys
import time
import types
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import numpy as np
import pandas as pd

from sqp.audit.report import _unique_settled_picks
from sqp.config import ROOT as DEFAULT_ROOT

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_DISCREPANTE = "__discrepante__"  # L5: distinto de None, para no sumar a "sin_graduar"

# Constantes congeladas por el pre-registro (secciones indicadas).
TAG_NAME = "prereg-tier-a-t0"                                     # seccion 2.1
MAX_PLAUSIBLE_EV = 0.075                                          # seccion 2.5, literal
DELTA = 0.03                                                      # seccion 4.2
N_REQUIRED = 2100                                                 # seccion 4.2
ALPHA_Z = 1.6449                                                  # seccion 3.1/4.2, z de 0.05 unilateral
SEED = 20261002                                                   # seccion 7
N_BOOT = 10_000                                                   # seccion 7
DEFAULT_TZ_CLUSTER = "America/New_York"                           # seccion 3.1
T1_CANDIDATO_MARGEN_DIAS = 14                                     # seccion 4.3
DEFAULT_PREREGISTRO = (DEFAULT_ROOT / "docs" / "research"
                       / "2026-10-02-preregistro-brecha-tier-a.md")

_LABELS_REL = "src/sqp/evaluation/labels.py"
_TIPSTER_REL = "src/sqp/evaluation/tipster.py"
_YAML_REL = "configs/default.yaml"
_GIT_STATUS_PATHS = ("src", "configs", "scripts/research")

_IDENTIDAD_PICK = ("event_id", "market", "selection")

# Addendum 2 (2026-10-17, AUD-003): `liga|mercado` cuyo `implied_probability_novig`
# es falso antes de un instante. Literal CONGELADO (no se importa del gate: una
# entrada nueva alli no puede cambiar esta poblacion sin su propio addendum).
# Un test fija que coincide con `sqp.risk.prediction_gate.INVALID_BEFORE`.
INVALID_BEFORE: dict[tuple[str, str], str] = {
    ("nhl", "h2h"): "2026-10-16T12:56:03+00:00",   # ffc5ad3
}


# ------------------------------------------------------------------- git --
def _git(args: list[str], cwd: Path) -> str | None:
    """Corre `git <args>` en `cwd`. `None` si git no esta disponible, el
    directorio no es un repositorio o el comando falla -- se deja constancia
    en la salida en vez de fallar en silencio (igual que `measure_tilt_nhl`)."""
    try:
        res = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                             text=True, encoding="utf-8", check=True, timeout=30)
        return res.stdout.strip()
    except Exception:  # noqa: BLE001 -- procedencia informativa, no decide nada
        return None


def git_rev_parse(ref: str, cwd: Path) -> str | None:
    return _git(["rev-parse", ref], cwd)


def git_committer_date_iso(ref: str, cwd: Path) -> str | None:
    return _git(["log", "-1", "--format=%cI", ref], cwd)


def git_log_added(relpath: str, cwd: Path) -> tuple[str, str] | None:
    """Fallback de la seccion 2.1: `git log --diff-filter=A` sobre la ruta
    del pre-registro. Si el fichero se anadio una sola vez (caso normal), hay
    una sola linea; si por lo que sea hay varias, se toma la MAS ANTIGUA
    (la ultima del texto, porque `git log` por defecto lista mas reciente
    primero): es la que de verdad lo "anadio"."""
    out = _git(["log", "--diff-filter=A", "--format=%H %cI", "--", relpath], cwd)
    if not out:
        return None
    lineas = [linea for linea in out.splitlines() if linea.strip()]
    if not lineas:
        return None
    partes = lineas[-1].split(" ", 1)
    if len(partes) != 2:
        return None
    return partes[0], partes[1]


def git_blob_hash(ref: str, relpath: str, cwd: Path) -> str | None:
    return _git(["rev-parse", f"{ref}:{relpath}"], cwd)


def git_hash_object(relpath: str, cwd: Path) -> str | None:
    """Hash del fichero EN DISCO ahora mismo (incluye cambios sin
    commitear) -- hallazgo M4: un import vivo de `sqp.evaluation.*` lee el
    FICHERO del arbol de trabajo, no el commit HEAD, asi que `hash(H) ==
    hash(HEAD)` no basta para confiar en el import vivo si el disco diverge
    de los dos (ambiguedad 5 del docstring del modulo)."""
    return _git(["hash-object", relpath], cwd)


def git_tag_message(tag: str, cwd: Path) -> str | None:
    """Mensaje completo del tag anotado (seccion 2.1/2.5): ahi queda escrito
    el `max_plausible_edge` efectivo de `Settings` en H, porque el propio
    pre-registro no puede contener un valor leido despues de su commit."""
    return _git(["tag", "-l", "--format=%(contents)", tag], cwd)


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
        raise SystemExit(
            "No se pudo obtener 'git status --porcelain' de src, configs, "
            "scripts/research y el pre-registro. El modo --medir aborta: no se "
            "puede verificar que el arbol este limpio en esas rutas.")
    if status.strip() != "":
        raise SystemExit(
            "git status --porcelain de src, configs, scripts/research y el "
            "pre-registro NO esta "
            f"vacio:\n{status}\nEl modo --medir aborta: no se mide con cambios "
            "sin commitear en esas rutas.")


def _relpath(path: Path, cwd: Path) -> str | None:
    try:
        return path.resolve().relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return None


def _preregistro_status_glob(rel_pre: str) -> str:
    """Patron de pathspec que cubre el pre-registro Y su registro hermano
    (`<preregistro>.contar.jsonl`) para `git status --porcelain` -- hallazgo
    M1: el arbol limpio de `--medir` debe cubrir tambien estas dos rutas, no
    solo src/configs/scripts-research."""
    p = Path(rel_pre)
    return (p.parent / f"{p.stem}*").as_posix()


def _parse_ts(value: object) -> pd.Timestamp | None:
    """Parsea a `pd.Timestamp` UTC para comparar POR INSTANTE, no por texto
    (hallazgo M1): dos representaciones ISO del mismo instante ('Z' frente a
    '+00:00', con o sin microsegundos) no deben contarse como distintas.
    `None` si no se puede parsear."""
    if value is None:
        return None
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(ts):
        return None
    return ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")


def resolve_h_t0(preregistro_path: Path, cwd: Path, tag: str = TAG_NAME) -> dict:
    """H y T0 (seccion 2.1): tag anotado con fallback a `git log
    --diff-filter=A`. Aborta si los dos mecanismos existen y dan commits
    distintos."""
    h_tag = git_rev_parse(f"{tag}^{{commit}}", cwd)
    t0_tag = git_committer_date_iso(tag, cwd) if h_tag else None
    rel = _relpath(preregistro_path, cwd)
    fallback = git_log_added(rel, cwd) if rel else None
    h_fb, t0_fb = fallback if fallback else (None, None)
    if h_tag and h_fb and h_tag != h_fb:
        raise SystemExit(
            f"H por el tag '{tag}' ({h_tag}) y H por el fallback "
            f"'git log --diff-filter=A' ({h_fb}) DIFIEREN. El script aborta: "
            "la resolucion de H/T0 no es unica (seccion 2.1).")
    h = h_tag or h_fb
    t0 = t0_tag or t0_fb
    via = "tag" if h_tag else "fallback"
    if h is None or t0 is None:
        raise SystemExit(
            f"No se pudo resolver H/T0 ni por el tag anotado '{tag}' ni por "
            f"el fallback sobre {rel!r}. El script aborta (seccion 2.1).")
    return {"h": h, "t0_iso": t0, "via": via}


# -------------------------------------------------------- clasificador en H --
@contextlib.contextmanager
def _swap_module(name: str, mod: types.ModuleType):
    """Sustituye `sys.modules[name]` temporalmente -- SOLO mientras se ejecuta
    el bloque, nunca para el resto del proceso. Sirve para que el `exec` de
    `tipster.py` congelado en H, que hace `from sqp.evaluation.labels import
    ...`, resuelva contra la version de `labels.py` congelada en H en vez de
    la version viva."""
    previo = sys.modules.get(name)
    sys.modules[name] = mod
    try:
        yield
    finally:
        if previo is not None:
            sys.modules[name] = previo
        else:
            sys.modules.pop(name, None)


def load_frozen_classifier(cwd: Path, h: str, head: str | None) -> tuple[object, object, dict]:
    """Devuelve (labels_mod, tipster_mod, hashes) -- seccion 2.5. Si los
    blobs de `labels.py`/`tipster.py` en H coinciden con los de HEAD Y con el
    fichero EN DISCO ahora mismo (`git hash-object`, hallazgo M4: un import
    vivo lee el disco, no HEAD), importa los modulos normales de `sqp` (ya
    son los de H). Si cualquiera de los dos diverge, carga las fuentes de H
    con `git show` en un espacio de modulos AISLADO."""
    hashes: dict[str, dict] = {}
    for key, rel in (("labels", _LABELS_REL), ("tipster", _TIPSTER_REL),
                     ("default_yaml", _YAML_REL)):
        h_hash = git_blob_hash(h, rel, cwd)
        head_hash = git_blob_hash(head, rel, cwd) if head else None
        disco_hash = git_hash_object(rel, cwd)
        hashes[key] = {"hash_h": h_hash, "hash_head": head_hash, "hash_disco": disco_hash,
                      "diverge": (h_hash != head_hash) or (h_hash != disco_hash)}
    if not (hashes["labels"]["diverge"] or hashes["tipster"]["diverge"]):
        from sqp.evaluation import labels as labels_mod
        from sqp.evaluation import tipster as tipster_mod
        return labels_mod, tipster_mod, hashes

    labels_src = git_show_text(h, _LABELS_REL, cwd)
    tipster_src = git_show_text(h, _TIPSTER_REL, cwd)
    labels_mod = types.ModuleType("_frozen_labels_at_h")
    labels_mod.__file__ = f"<git:{h}:{_LABELS_REL}>"
    tipster_mod = types.ModuleType("_frozen_tipster_at_h")
    tipster_mod.__file__ = f"<git:{h}:{_TIPSTER_REL}>"
    with _swap_module("sqp.evaluation.labels", labels_mod):
        exec(compile(labels_src, labels_mod.__file__, "exec"), labels_mod.__dict__)
        exec(compile(tipster_src, tipster_mod.__file__, "exec"), tipster_mod.__dict__)
    return labels_mod, tipster_mod, hashes


def settings_max_plausible_edge() -> float | None:
    """`Settings().risk.max_plausible_edge` efectivo AHORA (seccion 2.5): solo
    se registra, nunca se usa para clasificar."""
    try:
        from sqp.config import Settings
        return float(Settings.load().risk.max_plausible_edge)
    except Exception:  # noqa: BLE001 -- informativo, no decide
        return None


def yaml_max_plausible_edge(ref: str, cwd: Path) -> float | None:
    try:
        from sqp.config import load_yaml
        text = git_show_text(ref, _YAML_REL, cwd)
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(text)
            tmp = Path(fh.name)
        try:
            data = load_yaml(tmp)
        finally:
            tmp.unlink(missing_ok=True)
        return float(data.get("risk", {}).get("max_plausible_edge"))
    except Exception:  # noqa: BLE001 -- informativo, no decide
        return None


def parse_max_plausible_edge_from_tag_message(message: str | None) -> float | None:
    """`max_plausible_edge` efectivo que el tag anotado registra en su
    mensaje (seccion 2.1/2.5; hallazgo M6). `None` si no hay mensaje o no se
    encuentra el patron."""
    if not message:
        return None
    m = re.search(r"max_plausible_edge[^\n]*?:\s*([0-9]*\.?[0-9]+)", message)
    return float(m.group(1)) if m else None


# ------------------------------------------------------- utilidades genericas --
def sha256_and_rows(path: Path) -> tuple[str, int]:
    """Hash y filas (menos cabecera) sin materializar un DataFrame -- lectura
    por bloques, igual que `measure_rest_nhl.sha256_of`."""
    h = hashlib.sha256()
    saltos = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            saltos += chunk.count(b"\n")
    return h.hexdigest(), max(saltos - 1, 0)


def csv_provenance(paths: list[Path]) -> list[dict]:
    out = []
    for p in paths:
        if not p.exists():
            out.append({"fichero": str(p), "existe": False})
            continue
        sha, filas = sha256_and_rows(p)
        out.append({"fichero": str(p), "existe": True, "sha256": sha, "filas": filas})
    return out


def served_paths(data_root: Path) -> list[Path]:
    return sorted((data_root / "data" / "calibration").glob("served_*.csv"))


def graded_paths(data_root: Path) -> list[Path]:
    return sorted((data_root / "data" / "calibration").glob("graded_*.csv"))


def settled_paths(data_root: Path) -> list[Path]:
    return sorted((data_root / "data" / "bets").glob("settled_*.csv"))


def require_columns(df: pd.DataFrame, cols: list[str], context: str) -> None:
    faltan = [c for c in cols if c not in df.columns]
    if faltan:
        raise SystemExit(f"{context}: faltan columnas obligatorias {faltan}. "
                        "El script aborta (seccion 2.3/2.1).")


def _numeric_col(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce")
    return pd.Series(float("nan"), index=df.index, dtype=float)


def _cell_text(s: pd.Series) -> pd.Series:
    """Texto celda a celda, NaN -> "". Con una serie VACIA, `Series.map` no
    tiene nada con que inferir el dtype de salida y conserva el de entrada
    (p.ej. float64 de una columna `line` vacia); forzar `object` aqui evita
    que una concatenacion posterior mezcle texto con numeros (pandas 3 /
    pyarrow)."""
    if len(s) == 0:
        return pd.Series([], index=s.index, dtype=object)
    return s.map(lambda v: "" if pd.isna(v) else str(v))


def _is_blank(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "")


def pick_key(df: pd.DataFrame) -> pd.Series:
    """Clave del pick (seccion 2.3): `(event_id, market, selection, line)`,
    `line` redondeada a 4 decimales y `+0.0` (normaliza -0.0), vacia en h2h.
    Texto celda a celda, NaN -> "" (pandas 3: `astype(str)` deja NaN como NaN
    y la concatenacion entera sale NaN -- ver `_unique_settled_picks`)."""
    linea = _numeric_col(df, "line").round(4) + 0.0
    return (_cell_text(df["event_id"]) + "|" + _cell_text(df["market"]) + "|"
           + _cell_text(df["selection"]) + "|" + _cell_text(linea))


def filter_real(df: pd.DataFrame) -> pd.DataFrame:
    """`data_label == "real"` si la columna existe (seccion 2.1, paso 1)."""
    if df.empty or "data_label" not in df.columns:
        return df
    return df[df["data_label"].astype(str) == "real"].copy()


# ----------------------------------------------- carga de los tres ficheros --
def _read_csv_glob_safe(paths: list[Path]) -> tuple[pd.DataFrame, list[dict]]:
    """Lee una lista de CSV con `pd.read_csv`, SIN mutar nada en disco --
    hallazgo M5: `ServedStore._load` (`served_store.py:130-145`) RENOMBRA
    (cuarentena) un fichero ante un `ParserError`, y este script es de SOLO
    LECTURA: no puede mutar `data/` como efecto secundario de medir. Un
    fichero vacio o corrupto se omite y se informa, nunca crashea el
    proceso ni se toca en disco. Devuelve (concatenado, errores_por_fichero).
    """
    frames: list[pd.DataFrame] = []
    errores: list[dict] = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError) as exc:
            errores.append({"fichero": str(p), "error": str(exc)})
            continue
        if not df.empty:
            frames.append(df)
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return out, errores


def _ligas_provenance(paths: list[Path], df: pd.DataFrame, prefix: str,
                      errores: list[dict]) -> dict:
    """Hallazgo M5: ligas LISTADAS (un fichero `<prefix><liga>.csv` por liga)
    frente a REALMENTE cargadas (columna `league`, ya presente en los tres
    esquemas reales). Una liga listada que no aparece cargada -- vacia,
    corrupta, o con otra columna `league` -- se informa en `faltantes`;
    `--medir` aborta si hay alguna, `--contar` solo informa."""
    listadas = sorted(p.stem.replace(prefix, "", 1) for p in paths)
    cargadas = (sorted(str(v) for v in df["league"].astype(str).unique())
               if not df.empty and "league" in df.columns else [])
    # Un fichero que se lee SIN error pero solo trae cabecera no es una liga
    # perdida: no tiene filas que medir. Contarlo en `faltantes` haria abortar
    # `--medir` sin motivo (revision Fable 2026-10-03). Solo se re-lee la
    # cabecera de las ligas ausentes, que normalmente son ninguna.
    con_error = {Path(e["fichero"]).stem.replace(prefix, "", 1) for e in errores}
    vacias = []
    for p in paths:
        liga = p.stem.replace(prefix, "", 1)
        if liga in cargadas or liga in con_error:
            continue
        try:
            if pd.read_csv(p, nrows=1).empty:
                vacias.append(liga)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, OSError):
            continue
    faltantes = sorted(set(listadas) - set(cargadas) - set(vacias))
    return {"listadas": listadas, "cargadas": cargadas, "faltantes": faltantes,
           "vacias": sorted(vacias), "errores_lectura": errores}


def load_served_real(data_root: Path) -> tuple[pd.DataFrame, dict]:
    paths = served_paths(data_root)
    df, errores = _read_csv_glob_safe(paths)
    prov = _ligas_provenance(paths, df, "served_", errores)
    return filter_real(df), prov


def load_graded_real(data_root: Path) -> tuple[pd.DataFrame, dict]:
    """Misma semantica que `ServedStore.load_all_graded()` (concatena
    `graded_*.csv`, filtro `data_label == "real"`), pero SIN su cuarentena
    (hallazgo M5): no se llama a `ServedStore.load_all_graded`."""
    paths = graded_paths(data_root)
    df, errores = _read_csv_glob_safe(paths)
    prov = _ligas_provenance(paths, df, "graded_", errores)
    return filter_real(df), prov


def load_settled_all(data_root: Path) -> tuple[pd.DataFrame, dict]:
    """Misma semantica que `sqp.audit.report.load_all_settled`, con manejo de
    errores por fichero (ese loader no atrapa ninguno, asi que un CSV
    corrupto tumbaria todo el proceso en vez de informarse -- hallazgo M5)."""
    paths = settled_paths(data_root)
    df, errores = _read_csv_glob_safe(paths)
    prov = _ligas_provenance(paths, df, "settled_", errores)
    return df, prov


# -------------------------------------------- paso 1 de 2.1: primera servida --
def first_serve_rows(df: pd.DataFrame, ts_col: str = "generated_at") -> tuple[pd.DataFrame, dict]:
    """Seccion 2.3: excluye (y cuenta) la identidad incompleta, y se queda con
    UNA fila por clave -- la de `ts_col` MINIMO. Los sellos ilegibles van al
    final (nunca elegidos); una clave con TODOS los sellos ilegibles se
    excluye y se cuenta."""
    if df.empty:
        return df, {"identidad_incompleta": 0, "claves_todas_ilegibles": 0,
                   "duplicados_colapsados": 0}
    require_columns(df, [*_IDENTIDAD_PICK, ts_col], "first_serve_rows")
    incompleta = (_is_blank(df["event_id"]) | _is_blank(df["market"])
                 | _is_blank(df["selection"]))
    n_incompleta = int(incompleta.sum())
    valid = df[~incompleta].copy()
    if valid.empty:
        return valid, {"identidad_incompleta": n_incompleta, "claves_todas_ilegibles": 0,
                      "duplicados_colapsados": 0}
    valid["_clave"] = pick_key(valid)
    valid["_ts"] = pd.to_datetime(valid[ts_col], errors="coerce", utc=True, format="ISO8601")
    ilegibles_por_clave = valid.groupby("_clave")["_ts"].apply(lambda s: bool(s.isna().all()))
    claves_ilegibles = set(ilegibles_por_clave[ilegibles_por_clave].index)
    valid2 = valid[~valid["_clave"].isin(claves_ilegibles)].copy()
    ordenado = valid2.sort_values("_ts", kind="stable", na_position="last")
    primera_mask = ~ordenado["_clave"].duplicated(keep="first")
    primeras = ordenado[primera_mask].drop(columns=["_clave", "_ts"])
    # M6: filas de identidad completa, de clave legible, que NO eran la
    # primera servida de su clave -- la cuenta que faltaba en la salida.
    duplicados_colapsados = int(len(valid2) - len(primeras))
    return primeras, {"identidad_incompleta": n_incompleta,
                      "claves_todas_ilegibles": len(claves_ilegibles),
                      "duplicados_colapsados": duplicados_colapsados}


# ---------------------------------------------------- paso 2: ventana (T0,T1] --
def window_mask(ts: pd.Series, t0: pd.Timestamp, t1: pd.Timestamp) -> pd.Series:
    return (ts > t0) & (ts <= t1)


# --------------------------------------------- paso 3: filtros de validez 2.4 --
def pregame_mask(df: pd.DataFrame, labels_mod) -> tuple[pd.Series, dict]:
    gen = labels_mod.instantes_utc(df.get("generated_at"), index=df.index)
    start = labels_mod.instantes_utc(df.get("start_time"), index=df.index)
    ilegible = start.isna()
    en_vivo = (~ilegible) & (gen >= start)
    valido = ~ilegible & ~en_vivo
    return valido, {"start_time_ilegible": int(ilegible.sum()),
                    "generado_en_vivo_o_despues": int(en_vivo.sum())}


def invalid_market_mask(df: pd.DataFrame, labels_mod) -> tuple[pd.Series, dict]:
    """Addendum 2 (AUD-003): mascara de filas VALIDAS. Fuera la fila de
    decision de un `liga|mercado` de `INVALID_BEFORE` con `generated_at`
    anterior a su instante o ilegible (semantica de `_drop_invalid_market_rows`
    del gate). Se aplica tras `pregame_mask` y antes de `pyp_mask`; el pick no
    se sustituye por otra servida. No depende de `result`."""
    invalido = pd.Series(False, index=df.index)
    if not df.empty and {"league", "market"} <= set(df.columns):
        gen = labels_mod.instantes_utc(df.get("generated_at"), index=df.index)
        for (league, market), since in INVALID_BEFORE.items():
            seg = (df["league"].astype(str) == league) & (df["market"].astype(str) == market)
            valido = (gen >= pd.Timestamp(since)).fillna(False).astype(bool)
            invalido |= seg & ~valido
    return ~invalido, {"mercado_invalido_aud003": int(invalido.sum())}


def pyp_mask(df: pd.DataFrame, labels_mod) -> tuple[pd.Series, dict]:
    """p finita, cuota > 1.0, novig presente (seccion 2.4). Recuentos
    MUTUAMENTE EXCLUYENTES: orden p -> cuota -> novig (ambiguedad 4 del
    docstring del modulo)."""
    p = labels_mod.decision_prob(df)
    price = _numeric_col(df, "price_decimal")
    novig = _numeric_col(df, "implied_probability_novig")
    sin_p = ~np.isfinite(p.to_numpy(dtype=float))
    sin_cuota = ~(price.notna() & (price > 1.0)).to_numpy()
    sin_novig = ~novig.notna().to_numpy()
    cnt_sin_cuota = sin_cuota & ~sin_p
    cnt_sin_novig = sin_novig & ~sin_p & ~sin_cuota
    valido = pd.Series(~(sin_p | sin_cuota | sin_novig), index=df.index)
    return valido, {"sin_p_finita": int(sin_p.sum()),
                    "sin_cuota_valida": int(cnt_sin_cuota.sum()),
                    "sin_novig": int(cnt_sin_novig.sum())}


# -------------------------------------------- paso 5: clasificacion congelada --
def classify_rows(df: pd.DataFrame, labels_mod, tipster_mod,
                  max_plausible_ev: float) -> pd.DataFrame:
    """Clasifica cada fila con `classify` de `tipster_mod` (congelado en H) y
    el literal `max_plausible_ev`. Columnas `_p/_price/_novig/_casas/_ev/
    _edge_pp/_tier/_motivo`, alineadas al INDICE de `df` (nunca se reindexa,
    igual que `tipster_table`)."""
    out = df.copy()
    cols_float = ("_p", "_price", "_novig", "_casas", "_ev", "_edge_pp")
    if df.empty:
        for c in cols_float:
            out[c] = pd.Series(dtype=float)
        out["_tier"] = pd.Series(dtype=str)
        out["_motivo"] = pd.Series(dtype=str)
        return out
    p = labels_mod.decision_prob(df)
    price = _numeric_col(df, "price_decimal")
    novig = _numeric_col(df, "implied_probability_novig")
    casas = _numeric_col(df, "books_count")
    ev = tipster_mod.expected_value(p, price)
    edge_pp = p - novig
    tiers: list[str] = []
    motivos: list[str] = []
    for e, ed, c, pr in zip(ev.to_numpy(), edge_pp.to_numpy(), casas.to_numpy(), p.to_numpy()):
        t, m = tipster_mod.classify(float(e), float(ed), float(c), float(pr), max_plausible_ev)
        tiers.append(t)
        motivos.append(m)
    out["_p"] = p.to_numpy()
    out["_price"] = price.to_numpy()
    out["_novig"] = novig.to_numpy()
    out["_casas"] = casas.to_numpy()
    out["_ev"] = ev.to_numpy()
    out["_edge_pp"] = edge_pp.to_numpy()
    out["_tier"] = tiers
    out["_motivo"] = motivos
    return out


# ------------------------------------------------- paso 4: resultado graduado --
def join_result_by_key(claves: pd.Series, graded: pd.DataFrame) -> tuple[pd.Series, dict]:
    """Seccion 2.1 paso 4: una fila graduada de la clave sirve, sea cual sea;
    si discrepan en `result`, se excluye y se cuenta; si no hay ninguna, el
    pick cuenta como "sin graduar" (no entra en `n`, se informa).

    Hallazgo L5: una clave DISCREPANTE se marca con el sentinela
    `_DISCREPANTE`, NUNCA con `None` -- `None` significa "sin graduar" (no
    hay ninguna fila) y discrepante significa "hay varias, y no coinciden";
    conflarlas en el mismo valor hacia que `sin_graduar` contara tambien las
    discrepantes."""
    n = len(claves)
    if (graded.empty
            or not {*_IDENTIDAD_PICK, "result"}.issubset(graded.columns)):
        return pd.Series([None] * n, index=claves.index), {"resultados_discrepantes": 0}
    g_claves = pick_key(graded)
    por_clave = (graded.assign(_clave=g_claves)
                .groupby("_clave")["result"]
                .agg(lambda s: frozenset(str(v) for v in s.dropna())))
    discrepantes = 0
    resultados: list[str | None] = []
    for k in claves:
        vals = por_clave.get(k)
        if not vals:
            resultados.append(None)
        elif len(vals) == 1:
            resultados.append(next(iter(vals)))
        else:
            resultados.append(_DISCREPANTE)
            discrepantes += 1
    return pd.Series(resultados, index=claves.index), {"resultados_discrepantes": discrepantes}


# ------------------------------------------------------- cluster de dia 3.1 --
def day_cluster(start_time: pd.Series | None, tz_name: str, labels_mod,
                index: pd.Index) -> pd.Series:
    """Fecha del partido (`start_time`) en la zona IANA PASADA (nunca la de la
    maquina): seccion 3.1."""
    ts = labels_mod.instantes_utc(start_time, index=index)
    tz = ZoneInfo(tz_name)
    local = ts.dt.tz_convert(tz)
    return local.dt.strftime("%Y-%m-%d")


# ------------------------------------------------------------- estadistico --
def _phi(z: float) -> float:
    """Funcion de distribucion normal estandar, sin depender de scipy."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def cluster_mean_se(r: np.ndarray, cluster: np.ndarray,
                    weights: np.ndarray | None = None) -> dict:
    """D_hat y SE sandwich CR1 por `cluster` (seccion 3.1):

        SE^2 = G/(G-1) * sum_g (sum_{i en g} (r_i - D_hat))^2 / n^2

    Con pesos (seccion 2.6, S5c), D_hat es la media ponderada y `n` se
    sustituye por la suma de pesos (tamano efectivo); el residuo que se
    agrupa por dia es el residuo YA ponderado, consistente con ese D_hat."""
    n = len(r)
    if n == 0:
        return {"n": 0, "g": 0, "d_hat": None, "se": None, "z": None,
               "p_valor_unilateral": None}
    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    n_eff = float(np.sum(w))
    d_hat = float(np.sum(w * r) / n_eff) if n_eff else None
    if d_hat is None:
        return {"n": n, "g": 0, "d_hat": None, "se": None, "z": None,
               "p_valor_unilateral": None}
    resid = w * (r - d_hat)
    dias, inv = np.unique(cluster, return_inverse=True)
    g = len(dias)
    sums = np.bincount(inv, weights=resid, minlength=g)
    if g <= 1:
        return {"n": n, "g": g, "d_hat": d_hat, "se": None, "z": None,
               "p_valor_unilateral": None}
    se2 = (g / (g - 1)) * float(np.sum(sums ** 2)) / (n_eff ** 2)
    se = math.sqrt(se2)
    z = d_hat / se if se > 0 else None
    p_valor = _phi(z) if z is not None else None
    return {"n": n, "g": g, "d_hat": d_hat, "se": se, "z": z,
           "p_valor_unilateral": p_valor}


def cluster_diff_se(r_a: np.ndarray, day_a: np.ndarray,
                    r_b: np.ndarray, day_b: np.ndarray) -> dict:
    """SE de `D_A - D_B` con covarianza CR1 por dia COMPARTIDO (seccion 5,
    S2): generalizacion de `cluster_mean_se` a la diferencia de dos medias
    correlacionadas por el mismo cluster."""
    n_a, n_b = len(r_a), len(r_b)
    if n_a == 0 or n_b == 0:
        return {"d_hat_a": None, "d_hat_b": None, "diff": None, "se": None,
               "z": None, "g": 0}
    d_a = float(np.mean(r_a))
    d_b = float(np.mean(r_b))
    dias = np.union1d(np.unique(day_a), np.unique(day_b))
    g = len(dias)

    def _por_dia(r: np.ndarray, day: np.ndarray, d: float) -> np.ndarray:
        s = pd.Series(np.asarray(r) - d, index=pd.Index(day)).groupby(level=0).sum()
        return s.reindex(dias, fill_value=0.0).to_numpy()

    sa = _por_dia(r_a, day_a, d_a) / n_a
    sb = _por_dia(r_b, day_b, d_b) / n_b
    terms = sa - sb
    diff = d_a - d_b
    if g <= 1:
        return {"d_hat_a": d_a, "d_hat_b": d_b, "diff": diff, "se": None,
               "z": None, "g": g}
    se2 = (g / (g - 1)) * float(np.sum(terms ** 2))
    se = math.sqrt(se2)
    z = diff / se if se > 0 else None
    return {"d_hat_a": d_a, "d_hat_b": d_b, "diff": diff, "se": se, "z": z, "g": g}


def bootstrap_by_cluster(r: np.ndarray, cluster: np.ndarray, seed: int,
                         n_boot: int) -> dict:
    """Bootstrap por bloques de dia (seccion 5, S5b): `n_boot` replicas,
    `seed` fijo, cotas UNILATERALES al 95% por percentil (inferior p5,
    superior p95) sobre el MISMO conjunto de replicas."""
    n = len(r)
    if n == 0:
        return {"n_dias": 0, "p05": None, "p95": None, "n_replicas_validas": 0}
    dias, inv = np.unique(cluster, return_inverse=True)
    g = len(dias)
    sums = np.bincount(inv, weights=r, minlength=g)
    counts = np.bincount(inv, minlength=g)
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, g, size=(n_boot, g))
    rep_sum = sums[pick].sum(axis=1)
    rep_n = counts[pick].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        reps = rep_sum / rep_n
    reps = reps[np.isfinite(reps)]
    if len(reps) == 0:
        return {"n_dias": g, "p05": None, "p95": None, "n_replicas_validas": 0}
    return {"n_dias": g, "p05": float(np.quantile(reps, 0.05)),
           "p95": float(np.quantile(reps, 0.95)), "n_replicas_validas": int(len(reps))}


def decision_label(d_hat: float | None, se: float | None, z: float | None) -> str:
    """Seccion 6."""
    if d_hat is None or se is None or z is None:
        return "INCONCLUSO"
    if z <= -ALPHA_Z:
        return "CONFIRMA"
    if (d_hat - ALPHA_Z * se) > -DELTA:
        return "DESCARTA"
    return "INCONCLUSO"


def bootstrap_label(p05: float | None, p95: float | None) -> str:
    """Seccion 5, S5: clase de fragilidad del bootstrap (la cola opuesta
    cuenta como DESCARTA a estos efectos, tal como indica la seccion 5)."""
    if p05 is None or p95 is None:
        return "INCONCLUSO"
    if p95 < 0:
        return "CONFIRMA"
    if p05 > -DELTA:
        return "DESCARTA"
    return "INCONCLUSO"


# -------------------------------------------------- tuberia: universo primario --
def build_primary_from_primeras(primeras: pd.DataFrame, graded: pd.DataFrame,
                                labels_mod, tipster_mod,
                                t0: pd.Timestamp, t1: pd.Timestamp, tz_name: str,
                                max_plausible_ev: float) -> dict:
    """Pasos 2-5 de la seccion 2.1 sobre `primeras` (YA deduplicado por
    `first_serve_rows`). Devuelve el frame clasificado + recuentos +
    `ventana_fechas` (primera/ultima servida de la ventana, M6 -- solo
    fechas, ningun resultado)."""
    counts: dict = {}
    if primeras.empty:
        return {"frame": primeras, "counts": {"vacio": True}, "ventana_fechas": {}}
    gen_ts = labels_mod.instantes_utc(primeras.get("generated_at"), index=primeras.index)
    en_vent = window_mask(gen_ts, t0, t1)
    counts["fuera_de_ventana"] = int((~en_vent).sum())
    ventana = primeras[en_vent].copy()
    gen_ts_ventana = gen_ts.loc[ventana.index]
    ventana_fechas = ({"primera": gen_ts_ventana.min().strftime("%Y-%m-%d"),
                       "ultima": gen_ts_ventana.max().strftime("%Y-%m-%d")}
                      if len(ventana) else {})

    valido_pre, c_pre = pregame_mask(ventana, labels_mod)
    counts.update(c_pre)
    # L1: pyp_mask SOLO sobre lo que ya paso pregame, para que sus recuentos
    # sean mutuamente excluyentes con los de pregame (no solo entre si).
    ventana_pre_ok = ventana[valido_pre]
    valido_mkt, c_mkt = invalid_market_mask(ventana_pre_ok, labels_mod)   # Addendum 2
    counts.update(c_mkt)
    ventana_pre_ok = ventana_pre_ok[valido_mkt]
    valido_pyp, c_pyp = pyp_mask(ventana_pre_ok, labels_mod)
    counts.update(c_pyp)
    validas = ventana_pre_ok[valido_pyp].copy()

    clasif = classify_rows(validas, labels_mod, tipster_mod, max_plausible_ev)
    resultado, c_join = join_result_by_key(pick_key(clasif), graded)
    counts.update(c_join)
    clasif["_resultado"] = resultado.to_numpy()
    clasif["_dia"] = day_cluster(clasif.get("start_time"), tz_name, labels_mod, clasif.index)

    # L5: "sin_graduar" es SOLO None (ninguna fila graduada encontrada); una
    # clave discrepante (`_DISCREPANTE`) no es None y no se cuenta aqui --
    # ya la cuenta "resultados_discrepantes" (c_join), y antes se sumaba dos
    # veces.
    counts["sin_graduar"] = int(clasif["_resultado"].isna().sum())
    counts["void_o_push"] = int(clasif["_resultado"].isin(["void", "push"]).sum())
    counts["half_win_o_half_loss"] = int(
        clasif["_resultado"].isin(["half_win", "half_loss"]).sum())
    return {"frame": clasif, "counts": counts, "ventana_fechas": ventana_fechas}


# --------------------------------------------------- tuberia: ledger (2.2) --
def build_ledger_population(served_primeras: pd.DataFrame, settled: pd.DataFrame,
                            labels_mod, tipster_mod,
                            t0: pd.Timestamp, t1: pd.Timestamp, tz_name: str,
                            max_plausible_ev: float) -> dict:
    """Universo SECUNDARIO (seccion 2.2). Dos precisiones sobre el orden de
    2.1: (1) la fila de decision es la de `generated_at` MINIMO dentro del
    ledger; (2) la ventana se decide con la primera servida del stream
    SERVIDO de esa clave (`served_primeras`, sin filtrar por ventana). Ver
    tambien la ambiguedad 1 del docstring del modulo (`start_time` del
    ledger, tomado del stream servido por la misma clave). Devuelve ademas
    `ventana_keys` (claves del ledger en (T0,T1], ANTES de los filtros de
    validez de 2.4 -- hallazgo L2: es el conjunto que debe usar la
    verificacion cruzada de 2.3, no las claves del universo primario)."""
    if settled.empty:
        return {"frame": settled, "counts": {"vacio": True}, "ventana_keys": set()}
    primeras_ledger, c1 = first_serve_rows(settled)
    counts: dict = {f"dedupe_ledger_{k}": v for k, v in c1.items()}

    # L2 (segunda parte): entre las filas de IDENTIDAD INCOMPLETA del ledger
    # (excluidas por `first_serve_rows` antes de poder fecharlas por clave),
    # cuantas tienen un `generated_at` PROPIO que habria caido en la ventana
    # -- diagnostico aparte, nunca cambia ningun recuento anterior.
    incompleta = (_is_blank(settled["event_id"]) | _is_blank(settled["market"])
                 | _is_blank(settled["selection"]))
    gen_incompleta = labels_mod.instantes_utc(settled.get("generated_at"), index=settled.index)
    en_ventana_incompleta = incompleta & window_mask(gen_incompleta, t0, t1)
    counts["identidad_incompleta_con_generated_at_en_ventana"] = int(en_ventana_incompleta.sum())

    if primeras_ledger.empty:
        return {"frame": primeras_ledger, "counts": counts, "ventana_keys": set()}

    sp = served_primeras.copy()
    if not sp.empty:
        sp["_clave"] = pick_key(sp)
        sp = sp.drop_duplicates("_clave")
        start_by_key = sp.set_index("_clave")["start_time"] if "start_time" in sp.columns \
            else pd.Series(dtype=object)
        gen_by_key = sp.set_index("_clave")["generated_at"]
    else:
        start_by_key = pd.Series(dtype=object)
        gen_by_key = pd.Series(dtype=object)

    primeras_ledger = primeras_ledger.copy()
    primeras_ledger["_clave"] = pick_key(primeras_ledger)
    primeras_ledger["_start_time_evento"] = primeras_ledger["_clave"].map(start_by_key)

    gen_servido = primeras_ledger["_clave"].map(gen_by_key)
    sin_servido = gen_servido.isna()
    counts["claves_sin_served_fallback_a_ledger"] = int(sin_servido.sum())
    gen_para_ventana = gen_servido.where(~sin_servido, primeras_ledger["generated_at"])
    gen_ts = labels_mod.instantes_utc(gen_para_ventana, index=primeras_ledger.index)
    en_vent = window_mask(gen_ts, t0, t1)
    counts["fuera_de_ventana"] = int((~en_vent).sum())
    ventana = primeras_ledger[en_vent].copy()
    # L2 (primera parte): claves de la ventana del LEDGER, ANTES de 2.4.
    ventana_keys = set(ventana["_clave"])

    # start_time DEL EVENTO (ambiguedad 1); generated_at de la fila del ledger.
    ventana["start_time"] = ventana["_start_time_evento"]
    valido_pre, c_pre = pregame_mask(ventana, labels_mod)
    counts.update(c_pre)
    ventana_pre_ok = ventana[valido_pre]  # L1
    valido_mkt, c_mkt = invalid_market_mask(ventana_pre_ok, labels_mod)   # Addendum 2
    counts.update(c_mkt)
    ventana_pre_ok = ventana_pre_ok[valido_mkt]
    valido_pyp, c_pyp = pyp_mask(ventana_pre_ok, labels_mod)
    counts.update(c_pyp)
    validas = ventana_pre_ok[valido_pyp].copy()

    clasif = classify_rows(validas, labels_mod, tipster_mod, max_plausible_ev)
    clasif["_resultado"] = clasif["result"] if "result" in clasif.columns else None
    clasif["_dia"] = day_cluster(clasif.get("start_time"), tz_name, labels_mod, clasif.index)

    if "_resultado" in clasif.columns:
        counts["sin_graduar"] = int(pd.isna(clasif["_resultado"]).sum())
        res = clasif["_resultado"].astype(object)
        counts["void_o_push"] = int(res.isin(["void", "push"]).sum())
        counts["half_win_o_half_loss"] = int(res.isin(["half_win", "half_loss"]).sum())
    return {"frame": clasif, "counts": counts, "ventana_keys": ventana_keys}


def count_keys_with_multiple_stake_rows(settled: pd.DataFrame) -> int:
    """Seccion 2.3: "se informa cuantas claves tenian mas de una fila con
    stake (con shadow mode, previsiblemente 0)"."""
    if settled.empty or "stake" not in settled.columns:
        return 0
    s = settled.copy()
    s["_clave"] = pick_key(s)
    stake = pd.to_numeric(s["stake"], errors="coerce").fillna(0.0)
    con_stake = s[(stake > 0).to_numpy()]
    if con_stake.empty:
        return 0
    por_clave = con_stake.groupby("_clave").size()
    return int((por_clave > 1).sum())


def cross_check_unique_settled(settled: pd.DataFrame, window_keys: set[str]) -> dict:
    """Seccion 2.3: compara `_unique_settled_picks` (como el Historial) contra
    la regla textual (`first_serve_rows`), restringido a las claves de la
    ventana. Best-effort (ambiguedad 3 del docstring del modulo): detecta las
    clases 1 (fila con stake) y 2 (identidad incompleta NaN) explicitamente;
    el resto -- incluida la clase 3 -- se informa como "discrepancia"."""
    if settled.empty:
        return {"n_diferencias": 0, "clases": {}}
    ref = _unique_settled_picks(settled)
    textual, _ = first_serve_rows(settled)
    settled_c = settled.copy()
    settled_c["_clave"] = pick_key(settled_c)
    en_ventana_idx = set(settled_c[settled_c["_clave"].isin(window_keys)].index)
    ref_idx = set(ref.index) & en_ventana_idx
    textual_idx = set(textual.index) & en_ventana_idx
    solo_ref = ref_idx - textual_idx
    solo_textual = textual_idx - ref_idx
    diff_idx = solo_ref | solo_textual
    stake = pd.to_numeric(settled_c.get("stake"), errors="coerce").fillna(0.0)
    incompleta = (_is_blank(settled_c["event_id"]) | _is_blank(settled_c["market"])
                 | _is_blank(settled_c["selection"]))
    clases = {"fila_con_stake": 0, "identidad_incompleta_nan": 0, "discrepancia": 0}
    for idx in diff_idx:
        if idx in solo_ref and idx in stake.index and stake.loc[idx] > 0:
            clases["fila_con_stake"] += 1
        elif idx in solo_ref and idx in incompleta.index and incompleta.loc[idx]:
            clases["identidad_incompleta_nan"] += 1
        else:
            clases["discrepancia"] += 1
    return {"n_diferencias": len(diff_idx), "clases": clases,
           "aviso": "Comparacion best-effort, ver ambiguedad 3 del docstring del modulo."}


# ------------------------------------------------------------- informes S1-S6 --
def _vectors(sub: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if sub.empty:
        return np.array([]), np.array([]), np.array([]), np.array([])
    y = (sub["_resultado"] == "win").astype(float).to_numpy()
    p = sub["_p"].to_numpy(dtype=float)
    day = sub["_dia"].to_numpy()
    event = sub.get("event_id", pd.Series(dtype=str)).astype(str).to_numpy()
    return y, p, day, event


_SPORT_GROUP_DIRECT = {"mlb": "MLB", "nfl": "NFL", "ncaaf": "NCAAF", "nba": "NBA",
                       "wnba": "WNBA", "nhl": "NHL"}


def sport_group(league: object) -> str:
    """Agrupa una liga en uno de los 8 grupos de la seccion 5 S4 (MLB, NFL,
    NCAAF, NBA, WNBA, NHL, futbol, tenis) -- hallazgo M6. Usa la familia
    CANONICA del proyecto (`sqp.pipeline.daily._league_meta`) para todo lo
    que no sea uno de los seis codigos directos: nunca se inventa a mano una
    lista de ligas de futbol o torneos de tenis."""
    code = str(league).lower()
    if code in _SPORT_GROUP_DIRECT:
        return _SPORT_GROUP_DIRECT[code]
    try:
        from sqp.pipeline.daily import _league_meta
        family = _league_meta(code).get("family")
    except Exception:  # noqa: BLE001 -- agrupacion descriptiva, no decide
        family = None
    if family == "soccer":
        return "futbol"
    if family == "tennis":
        return "tenis"
    return f"otro:{code}"


def calibration_bands(a: pd.DataFrame) -> dict:
    """S4 (seccion 5): bandas de presentacion, con D_hat y SE por banda y por
    grupo de deporte (hallazgo M6) -- descriptivo, no decide nada."""
    if a.empty:
        return {}

    def _stat(sub: pd.DataFrame) -> dict:
        if sub.empty:
            return {"n": 0, "d_hat": None, "se": None}
        y = (sub["_resultado"] == "win").astype(float).to_numpy()
        p = sub["_p"].to_numpy(dtype=float)
        day = sub["_dia"].to_numpy()
        salida = cluster_mean_se(y - p, day)
        return {"n": salida["n"], "d_hat": salida["d_hat"], "se": salida["se"]}

    out_p = {etiqueta: _stat(a[(a["_p"] >= lo) & (a["_p"] < hi)])
            for lo, hi, etiqueta in ((0.50, 0.55, "[0.50,0.55)"), (0.55, 0.60, "[0.55,0.60)"),
                                     (0.60, float("inf"), "[0.60,inf)"))}
    out_edge = {etiqueta: _stat(a[(a["_edge_pp"] >= lo) & (a["_edge_pp"] < hi)])
               for lo, hi, etiqueta in ((0.03, 0.05, "[0.03,0.05)"),
                                        (0.05, float("inf"), "[0.05,inf)"))}
    por_grupo: dict[str, dict] = {}
    if "league" in a.columns:
        grupos = a["league"].map(sport_group)
        for grupo, sub in a.groupby(grupos):
            por_grupo[str(grupo)] = _stat(sub)
    return {"por_p": out_p, "por_edge_pp": out_edge, "por_grupo_deporte": por_grupo,
           "por_regimen": "ningun addendum de regimen registrado todavia (seccion 8, A2)"}


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


def betting_metrics(a: pd.DataFrame) -> dict:
    """S6 (seccion 5): metricas de apuesta SEPARADAS, ninguna es promesa."""
    if a.empty:
        return {}
    acierto = float((a["_resultado"] == "win").mean())
    out = {
        "n": int(len(a)),
        "acierto_observado": acierto,
        "prob_prometida_media": float(a["_p"].mean()),
        "prob_implicita_media": float((1.0 / a["_price"]).mean()),
        "edge_medio": float(a["_edge_pp"].mean()),
        "roi_esperado_medio": float(a["_ev"].mean()),
        "roi_realizado_stake_plano": float(
            np.mean(np.where(a["_resultado"] == "win", a["_price"] - 1.0, -1.0))),
    }
    if "execution_price" in a.columns:
        ex = pd.to_numeric(a["execution_price"], errors="coerce")
        con_ex = ex.notna()
        out["n_con_execution_price"] = int(con_ex.sum())
        if con_ex.any():
            sub = a[con_ex.to_numpy()]
            exp = ex[con_ex]
            out["roi_esperado_execution_price"] = float(
                (sub["_p"].to_numpy() * exp.to_numpy() - 1.0).mean())
            out["roi_realizado_execution_price"] = float(np.mean(
                np.where(sub["_resultado"] == "win", exp.to_numpy() - 1.0, -1.0)))
        reg = execution_regime(a["generated_at"] if "generated_at" in a.columns
                               else pd.Series(pd.NaT, index=a.index))
        por: dict = {}
        for lab in EXECUTION_REGIMES:
            m = con_ex.to_numpy() & (reg == lab)
            d: dict = {"n_con_execution_price": int(m.sum())}
            if m.any():
                sub_r, ex_r = a[m], ex[m].to_numpy()
                d["roi_esperado_execution_price"] = float(
                    (sub_r["_p"].to_numpy() * ex_r - 1.0).mean())
                d["roi_realizado_execution_price"] = float(np.mean(
                    np.where(sub_r["_resultado"] == "win", ex_r - 1.0, -1.0)))
            por[lab] = d
        out["execution_price_por_regimen"] = por
    return out


def count_live_classifier_disagreement(clasif: pd.DataFrame) -> int | None:
    """Seccion 2.5: "el informe dice cuantos picks de la muestra clasificaria
    distinto el vivo" (hallazgo M6). Compara el tier CONGELADO (columna
    `_tier`, ya calculado con el clasificador de H y el literal 0.075)
    contra el que asignaria el clasificador VIVO de `sqp`, con el
    `max_plausible_edge` EFECTIVO de `Settings` (no el literal). `None` si
    no se puede calcular (p.ej. `Settings` no carga)."""
    if clasif.empty or "_tier" not in clasif.columns:
        return 0
    live_max_ev = settings_max_plausible_edge()
    if live_max_ev is None:
        return None
    try:
        from sqp.evaluation import labels as live_labels
        from sqp.evaluation import tipster as live_tipster
        vivo = classify_rows(clasif, live_labels, live_tipster, live_max_ev)
    except Exception:  # noqa: BLE001 -- informativo, no decide
        return None
    return int((vivo["_tier"].to_numpy() != clasif["_tier"].to_numpy()).sum())


def assemble_stats(primary: dict, ledger: dict, seed: int, n_boot: int) -> dict:
    pf = primary["frame"]
    vacio_cols = "_tier" not in pf.columns or "_resultado" not in pf.columns
    a = (pf[(pf["_tier"] == "A") & pf["_resultado"].isin(["win", "loss"])]
        if not vacio_cols else pf.iloc[0:0])
    b = (pf[(pf["_tier"] == "B") & pf["_resultado"].isin(["win", "loss"])]
        if not vacio_cols else pf.iloc[0:0])
    c = (pf[(pf["_tier"] == "C") & pf["_resultado"].isin(["win", "loss"])]
        if not vacio_cols else pf.iloc[0:0])

    y_a, p_a, day_a, event_a = _vectors(a)
    r_a = y_a - p_a
    primario = cluster_mean_se(r_a, day_a)
    primario["etiqueta"] = decision_label(primario["d_hat"], primario["se"], primario["z"])
    primario["cola_opuesta"] = bool(primario["z"] is not None and primario["z"] >= ALPHA_Z)
    # M6: valor numerico D_hat - 1.6449*SE, no solo la etiqueta derivada de el.
    primario["cota_inferior_95"] = (
        primario["d_hat"] - ALPHA_Z * primario["se"]
        if primario["d_hat"] is not None and primario["se"] is not None else None)

    lf = ledger["frame"]
    la = (lf[(lf["_tier"] == "A") & lf["_resultado"].isin(["win", "loss"])]
         if "_tier" in lf.columns and "_resultado" in lf.columns else lf.iloc[0:0])
    y_la, p_la, day_la, _ = _vectors(la)
    s1 = cluster_mean_se(y_la - p_la, day_la)
    s1["etiqueta"] = decision_label(s1["d_hat"], s1["se"], s1["z"])

    y_b, p_b, day_b, _ = _vectors(b)
    r_b = y_b - p_b
    y_c, p_c, day_c, _ = _vectors(c)

    s4 = calibration_bands(a)

    s5_evento = cluster_mean_se(r_a, event_a)
    s5_boot = bootstrap_by_cluster(r_a, day_a, seed, n_boot)
    s5_boot["etiqueta"] = bootstrap_label(s5_boot.get("p05"), s5_boot.get("p95"))
    fragil = s5_boot["etiqueta"] != primario["etiqueta"]

    a_half = (pf[(pf["_tier"] == "A")
                & pf["_resultado"].isin(["win", "loss", "half_win", "half_loss"])]
             if not vacio_cols else pf.iloc[0:0])
    if a_half.empty:
        s5_half = cluster_mean_se(np.array([]), np.array([]))
    else:
        res = a_half["_resultado"]
        y_h = np.select([res == "win", res == "half_win", res == "half_loss"],
                        [1.0, 1.0, 0.0], default=0.0)
        w_h = np.where(res.isin(["half_win", "half_loss"]), 0.5, 1.0)
        p_h = a_half["_p"].to_numpy(dtype=float)
        day_h = a_half["_dia"].to_numpy()
        s5_half = cluster_mean_se(y_h - p_h, day_h, weights=w_h)

    return {
        "primario": primario,
        "S1_ledger": s1,
        "S2_tier_B": cluster_mean_se(r_b, day_b),
        "S2_diff_A_menos_B": cluster_diff_se(r_a, day_a, r_b, day_b),
        "S2_tier_C": cluster_mean_se(y_c - p_c, day_c),
        "S3_benchmark_mercado": (cluster_mean_se(y_a - a["_novig"].to_numpy(dtype=float), day_a)
                                 if not a.empty else cluster_mean_se(np.array([]), np.array([]))),
        "S4_bandas": s4,
        "S5_cluster_evento": s5_evento,
        "S5_bootstrap_dia": s5_boot,
        "S5_fragil": bool(fragil),
        "S5_half_win_half_loss": s5_half,
        "S6_metricas_apuesta": betting_metrics(a),
    }


# ----------------------------------------------------------- modo --contar --
def contar_log_path(preregistro: Path) -> Path:
    stem = preregistro.name
    if stem.endswith(".md"):
        stem = stem[:-3]
    return preregistro.parent / f"{stem}.contar.jsonl"


def run_contar(args: argparse.Namespace) -> dict:
    # L4: las consultas git corren SIEMPRE contra el arbol de trabajo del
    # script (_WORKTREE_ROOT), nunca contra --data-root -- en un worktree de
    # investigacion data_root puede ser la raiz de PRODUCCION, que no tiene
    # repositorio git propio (ver docstring de measure_tilt_nhl.py).
    git_cwd = _WORKTREE_ROOT
    data_root = args.data_root
    resuelto = resolve_h_t0(args.preregistro, git_cwd)
    h, t0_iso, via = resuelto["h"], resuelto["t0_iso"], resuelto["via"]
    head = git_rev_parse("HEAD", git_cwd)
    labels_mod, tipster_mod, hashes = load_frozen_classifier(git_cwd, h, head)

    t0 = _parse_ts(t0_iso)
    if t0 is None:
        raise SystemExit("T0 ilegible (seccion 2.1). El script aborta.")
    e = pd.Timestamp.now(tz="UTC")
    t1_candidato = e - pd.Timedelta(days=T1_CANDIDATO_MARGEN_DIAS)

    served, prov_served = load_served_real(data_root)
    graded, prov_graded = load_graded_real(data_root)
    settled, prov_settled = load_settled_all(data_root)

    primeras, c1 = first_serve_rows(served)
    # M2: el primario SIEMPRE en la zona congelada (seccion 3.1/7; ambiguedad
    # 6 del docstring): es la que dispara la medicion, y no puede variar con
    # --tz-cluster. Se informa la zona solicitada, nunca se usa aqui.
    primary = build_primary_from_primeras(primeras, graded, labels_mod, tipster_mod,
                                          t0, t1_candidato, DEFAULT_TZ_CLUSTER, MAX_PLAUSIBLE_EV)
    ledger = build_ledger_population(primeras, settled, labels_mod, tipster_mod,
                                     t0, t1_candidato, DEFAULT_TZ_CLUSTER, MAX_PLAUSIBLE_EV)

    pf = primary["frame"]
    if "_tier" in pf.columns:
        a_winloss = pf[(pf["_tier"] == "A") & pf["_resultado"].isin(["win", "loss"])]
        a_sin_graduar = pf[(pf["_tier"] == "A") & pf["_resultado"].isna()]
    else:
        a_winloss = pf.iloc[0:0]
        a_sin_graduar = pf.iloc[0:0]
    lf = ledger["frame"]
    n_ledger = (int(((lf["_tier"] == "A") & lf["_resultado"].isin(["win", "loss"])).sum())
               if "_tier" in lf.columns else 0)
    ventana_fechas = primary.get("ventana_fechas") or {}

    # Registro: SOLO escalares (seccion 7: "ni y, ni p, ni brechas"). La
    # procedencia pesada (hashes, sha256 de ficheros, ligas) vive aparte, en
    # `out["procedencia"]`, para que esta linea del .jsonl quede pequena.
    registro = {
        "instante_ejecucion_utc": e.isoformat(),
        "head": head, "h": h, "t0": t0.isoformat(), "t1_candidato": t1_candidato.isoformat(),
        "n_primario": int(len(a_winloss)),
        "g_primario": int(a_winloss["_dia"].nunique()) if len(a_winloss) else 0,
        "n_ledger_informativo": n_ledger,
        "picks_ventana_sin_graduar": int(len(a_sin_graduar)),
        "via_resolucion_h_t0": via,
        # M6: primera/ultima servida de la ventana, SOLO fechas.
        "primera_servida_ventana": ventana_fechas.get("primera"),
        "ultima_servida_ventana": ventana_fechas.get("ultima"),
        "tz_cluster_primario": DEFAULT_TZ_CLUSTER,
        "tz_cluster_solicitada": args.tz_cluster,
    }
    procedencia = {
        # M5: informativo en --contar (--medir aborta si falta alguna).
        "ligas": {"served": prov_served, "graded": prov_graded, "settled": prov_settled},
        "sha256_csv": {
            "served": csv_provenance(served_paths(data_root)),
            "graded": csv_provenance(graded_paths(data_root)),
            "settled": csv_provenance(settled_paths(data_root)),
        },
        "hashes_h_vs_head_vs_disco": hashes,
    }
    if not args.no_log:
        log_path = contar_log_path(args.preregistro)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
        aviso = f"Linea anadida a {log_path}."
    else:
        aviso = "--no-log: NO se escribio en el registro .contar.jsonl (diagnostico)."
    return {"modo": "contar", "registro": registro, "procedencia": procedencia, "aviso": aviso}


# ------------------------------------------------------------ modo --medir --
def parse_t1_addendum(doc_text: str) -> tuple[str, str] | None:
    """Formato propio de este script para el addendum de T1 (ambiguedad 2 del
    docstring del modulo):

        T1 fijado = <ISO-8601>
        commit del registro = <sha-git>
    """
    m_t1 = re.search(r"T1 fijado\s*=\s*(\S+)", doc_text)
    m_commit = re.search(r"commit del registro\s*=\s*([0-9a-fA-F]{7,40})", doc_text)
    if not m_t1 or not m_commit:
        return None
    return m_t1.group(1), m_commit.group(1)


def _parse_jsonl_text(text: str) -> list[dict]:
    out = []
    for linea in (text or "").splitlines():
        linea = linea.strip()
        if linea:
            out.append(json.loads(linea))
    return out


def read_contar_log(path: Path) -> list[dict]:
    """Lectura de disco del registro -- utilidad generica; `run_medir` NO la
    usa (lee siempre con `git show HEAD:<ruta>`, hallazgo M1)."""
    if not path.exists():
        return []
    return _parse_jsonl_text(path.read_text(encoding="utf-8"))


def find_first_n_over(log_lines: list[dict], threshold: int) -> dict | None:
    for fila in log_lines:
        if fila.get("n_primario", 0) >= threshold:
            return fila
    return None


def run_medir(args: argparse.Namespace) -> dict:
    git_cwd = _WORKTREE_ROOT
    data_root = args.data_root

    resuelto = resolve_h_t0(args.preregistro, git_cwd)
    h, t0_iso = resuelto["h"], resuelto["t0_iso"]
    head = git_rev_parse("HEAD", git_cwd)

    rel_pre = _relpath(args.preregistro, git_cwd)
    if rel_pre is None:
        raise SystemExit(
            f"El pre-registro ({args.preregistro}) no esta dentro del arbol "
            f"de trabajo del repositorio ({git_cwd}). El modo --medir aborta: "
            "no se puede verificar ni leer con git.")
    rel_jsonl = _relpath(contar_log_path(args.preregistro), git_cwd)
    if rel_jsonl is None:
        raise SystemExit(
            "El registro .contar.jsonl no esta dentro del arbol de trabajo "
            "del repositorio. El modo --medir aborta: no se puede verificar "
            "con git show.")

    # M1: arbol limpio TAMBIEN en el pre-registro y su registro hermano,
    # ademas de src/configs/scripts-research.
    status_paths = (*_GIT_STATUS_PATHS, _preregistro_status_glob(rel_pre))
    _check_git_clean(git_status_porcelain(git_cwd, status_paths))

    # M1: addendum y registro se leen SIEMPRE del commit HEAD con `git show`,
    # nunca del disco -- es la misma version que acaba de verificarse limpia.
    doc_text = git_show_text("HEAD", rel_pre, git_cwd)
    addendum = parse_t1_addendum(doc_text)
    if addendum is None:
        raise SystemExit(
            "No hay addendum que fije T1 en el pre-registro (seccion 4.3). "
            "El modo --medir aborta: no se puede medir sin T1 fijado por "
            "addendum commiteado.")
    t1_addendum_txt, commit_addendum = addendum
    t1_addendum = _parse_ts(t1_addendum_txt)
    t1_pedido = _parse_ts(args.t1)
    if t1_addendum is None or t1_pedido is None or t1_pedido != t1_addendum:
        raise SystemExit(
            f"--t1 {args.t1!r} no coincide (como instante) con el T1 del "
            f"addendum ({t1_addendum_txt!r}). El modo --medir aborta (seccion 4.3).")

    jsonl_head_text = git_show_text("HEAD", rel_jsonl, git_cwd)
    log_lines = _parse_jsonl_text(jsonl_head_text)
    primera_sobre_umbral = find_first_n_over(log_lines, N_REQUIRED)
    if primera_sobre_umbral is None:
        raise SystemExit(
            "El registro .contar.jsonl (leido en HEAD con git show) no "
            f"tiene ninguna linea con n_primario >= {N_REQUIRED}. El modo "
            "--medir aborta (seccion 4.3).")
    t1_primera = _parse_ts(primera_sobre_umbral.get("t1_candidato"))
    if t1_primera is None or t1_primera != t1_addendum:
        raise SystemExit(
            "El T1 del addendum no coincide (como instante) con el T1 "
            f"candidato de la PRIMERA linea del registro que cruzo "
            f"{N_REQUIRED} (seccion 4.3). El modo --medir aborta.")

    # M1: el COMMIT que el addendum cita como "registro que lo justifica"
    # debe contener, EN ESA version historica de .contar.jsonl, esa misma
    # primera linea con n >= 2100 -- no basta con que HEAD la tenga hoy.
    jsonl_commit_text = git_show_text(commit_addendum, rel_jsonl, git_cwd)
    log_lines_commit = _parse_jsonl_text(jsonl_commit_text)
    primera_en_commit = find_first_n_over(log_lines_commit, N_REQUIRED)
    t1_en_commit = (_parse_ts(primera_en_commit.get("t1_candidato"))
                    if primera_en_commit else None)
    if primera_en_commit is None or t1_en_commit is None or t1_en_commit != t1_addendum:
        raise SystemExit(
            f"El commit del registro citado en el addendum ({commit_addendum}) "
            "no contiene, en esa version de .contar.jsonl, una linea con "
            f"n_primario >= {N_REQUIRED} y el mismo T1 candidato. El modo "
            "--medir aborta (addendum sin respaldo verificable).")

    t0 = _parse_ts(t0_iso)
    if t0 is None:
        raise SystemExit("T0 ilegible (seccion 2.1). El modo --medir aborta.")
    t1 = t1_addendum

    labels_mod, tipster_mod, hashes = load_frozen_classifier(git_cwd, h, head)

    served, prov_served = load_served_real(data_root)
    graded, prov_graded = load_graded_real(data_root)
    settled, prov_settled = load_settled_all(data_root)
    # M5: --medir ABORTA si el conjunto de ligas cargadas no coincide con
    # los ficheros listados (corrupcion, fichero bloqueado, etc.): nunca se
    # mide sobre una lectura parcial sin saberlo.
    for nombre, prov in (("served", prov_served), ("graded", prov_graded),
                        ("settled", prov_settled)):
        if prov["faltantes"]:
            raise SystemExit(
                f"{nombre}: ligas listadas pero no cargadas correctamente: "
                f"{prov['faltantes']} (errores: {prov['errores_lectura']}). "
                "El modo --medir aborta (seccion 7, hallazgo M5).")

    primeras, c1 = first_serve_rows(served)
    # M2: primario SIEMPRE en America/New_York (ambiguedad 6).
    primary = build_primary_from_primeras(primeras, graded, labels_mod, tipster_mod,
                                          t0, t1, DEFAULT_TZ_CLUSTER, MAX_PLAUSIBLE_EV)
    ledger = build_ledger_population(primeras, settled, labels_mod, tipster_mod,
                                     t0, t1, DEFAULT_TZ_CLUSTER, MAX_PLAUSIBLE_EV)
    primary["counts"] = {**{f"servido_{k}": v for k, v in c1.items()}, **primary["counts"]}
    ledger["counts"] = {**ledger["counts"],
                       "claves_con_varias_filas_con_stake": count_keys_with_multiple_stake_rows(settled)}

    pf = primary["frame"]
    n_ahora = (int(((pf["_tier"] == "A") & pf["_resultado"].isin(["win", "loss"])).sum())
              if "_tier" in pf.columns else 0)
    if n_ahora < N_REQUIRED:
        raise SystemExit(
            f"n(T1) = {n_ahora} < {N_REQUIRED}. El modo --medir aborta "
            "(seccion 4.3): la condicion de disparo ya no se cumple con los "
            "datos actuales.")

    stats = assemble_stats(primary, ledger, args.seed, args.n_boot)

    # M2: sensibilidad de zona APARTE y marcada, nunca sustituye al primario.
    sensibilidad_tz = None
    if args.tz_cluster != DEFAULT_TZ_CLUSTER:
        primary_alt = build_primary_from_primeras(primeras, graded, labels_mod, tipster_mod,
                                                   t0, t1, args.tz_cluster, MAX_PLAUSIBLE_EV)
        pf_alt = primary_alt["frame"]
        a_alt = (pf_alt[(pf_alt["_tier"] == "A") & pf_alt["_resultado"].isin(["win", "loss"])]
                if "_tier" in pf_alt.columns else pf_alt.iloc[0:0])
        y_alt, p_alt, day_alt, _ = _vectors(a_alt)
        sensibilidad_tz = {
            "zona": args.tz_cluster,
            "aviso": ("SENSIBILIDAD MARCADA: nunca sustituye al primario, que "
                      f"siempre usa {DEFAULT_TZ_CLUSTER} (seccion 3.1/7, "
                      "ambiguedad 6 del docstring del modulo)."),
            **cluster_mean_se(y_alt - p_alt, day_alt),
        }

    # L2: la verificacion cruzada usa las claves de la VENTANA DEL LEDGER
    # (antes de 2.4), nunca las del universo primario.
    cross_check = cross_check_unique_settled(settled, ledger.get("ventana_keys", set()))
    n_disagree_vivo = count_live_classifier_disagreement(pf)

    procedencia = {
        "h": h, "t0": t0.isoformat(), "t1": t1.isoformat(), "head": head,
        "via_resolucion_h_t0": resuelto["via"],
        "tz_cluster_primario": DEFAULT_TZ_CLUSTER,
        "tz_cluster_solicitada": args.tz_cluster,
        "hashes_h_vs_head_vs_disco": hashes,
        "max_plausible_edge": {
            "literal_congelado": MAX_PLAUSIBLE_EV,
            # M6: el valor registrado en el MENSAJE DEL TAG (seccion 2.5).
            "registrado_en_tag": parse_max_plausible_edge_from_tag_message(
                git_tag_message(TAG_NAME, git_cwd)),
            "settings_efectivo_al_medir": settings_max_plausible_edge(),
            "yaml_en_h": yaml_max_plausible_edge(h, git_cwd),
            "yaml_en_head": yaml_max_plausible_edge(head, git_cwd) if head else None,
        },
        # M6: picks que el clasificador VIVO clasificaria distinto.
        "picks_que_el_clasificador_vivo_clasificaria_distinto": n_disagree_vivo,
        "seed_n_boot": {
            "seed_usado": args.seed, "seed_congelado": SEED,
            "n_boot_usado": args.n_boot, "n_boot_congelado": N_BOOT,
            "difiere_de_lo_congelado": bool(args.seed != SEED or args.n_boot != N_BOOT),
        },
        "git_status_porcelain": git_status_porcelain(git_cwd, status_paths),
        "ligas": {"served": prov_served, "graded": prov_graded, "settled": prov_settled},
        "sha256_csv": {
            "served": csv_provenance(served_paths(data_root)),
            "graded": csv_provenance(graded_paths(data_root)),
            "settled": csv_provenance(settled_paths(data_root)),
        },
    }
    out = {
        "modo": "medir", "procedencia": procedencia,
        "recuentos_servido_graduado": primary["counts"],
        "recuentos_ledger": ledger["counts"],
        "verificacion_cruzada_2_3": cross_check,
        **stats,
    }
    if sensibilidad_tz is not None:
        out["S5_sensibilidad_tz_cluster_alternativa"] = sensibilidad_tz
    return out


# --------------------------------------------------------------------- main --
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--preregistro", type=Path, default=DEFAULT_PREREGISTRO)
    ap.add_argument("--tz-cluster", default=DEFAULT_TZ_CLUSTER)
    ap.add_argument("--contar", action="store_true")
    ap.add_argument("--medir", action="store_true")
    ap.add_argument("--t1", default=None, help="ISO-8601, obligatorio con --medir.")
    ap.add_argument("--no-log", action="store_true",
                    help="Diagnostico, fuera del contrato original: con --contar, no "
                        "anade linea al registro .contar.jsonl. Nunca usar para la "
                        "ejecucion oficial del seguimiento de n.")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if args.contar and args.medir:
        ap.error("--contar y --medir son mutuamente excluyentes.")
    if not args.contar and not args.medir:
        ap.error("Hay que elegir --contar o --medir.")
    if args.no_log and not args.contar:
        ap.error("--no-log solo aplica a --contar.")
    if args.medir and not args.t1:
        ap.error("--medir exige --t1 <ISO-8601>.")
    if args.contar and args.t1:
        ap.error("--t1 solo aplica a --medir.")
    # Validar la zona ANTES de medir: fallar tras calcular gastaria la
    # ejecucion unica de --medir por un error tipografico.
    try:
        ZoneInfo(args.tz_cluster)
    except (ZoneInfoNotFoundError, ValueError):
        ap.error(f"--tz-cluster: zona IANA desconocida {args.tz_cluster!r}.")

    t_ini = time.perf_counter()
    out = run_contar(args) if args.contar else run_medir(args)
    out["segundos"] = time.perf_counter() - t_ini
    texto = json.dumps(out, indent=2, ensure_ascii=False, default=str)
    print(texto)
    if args.out:
        args.out.write_text(texto, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
