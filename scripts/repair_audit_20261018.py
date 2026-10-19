"""Reparacion de datos de la ronda audit-2026-10-18 (autorizada por el operador
el 2026-10-19, «Te autorizo»). UNA sola ejecucion con `--apply`; sin el flag
solo informa (dry-run).

Dos reparaciones, cada una con la logica de PRODUCCION, sin reimplementarla.

AUD-003 NO se repara en disco (revision Fable 2026-10-19): quitar las filas de
`results_*.csv` romperia la Enmienda 3(c) de la bateria (exige exactamente 15
descartes MLB) y la Enmienda 2 de recencia (lee las filas crudas de la fase H),
y contradice "los datos crudos no se mutan". `ResultsStore.load` ya los
descarta al leer: AUD-003 queda resuelto en la lectura.

1. KI-071 -- `data/bets/settled_{epl,mls,ncaaf}.csv`: 9 identidades
   (`runner._pick_identity`) liquidadas dos veces en la restauracion del
   13-14/09; se conserva la fila de la generacion mas reciente. Esperado:
   9 identidades, 18 filas (epl 5, mls 1, ncaaf 3).
2. AUD-008 -- `data/calibration/graded_*.csv` y `data/bets/settled_*.csv`:
   re-gradua las filas de linea de cuarto anteriores al arreglo
   (`quarter_line_fix.pre_fix_quarter_line_mask`) contra el historico con
   `runner.exact_history_scores_map` y `settle._grade`; solo cambia `result`
   y `pnl` donde el grado actual difiere, y anade el flag `regrade_aud008`.
   Las filas siguen EXCLUIDAS del gate y de la calibracion (literal congelado
   y addenda del 2026-10-18): esto corrige el registro, no la decision.
   Esperado (dry-run de Fable, 2026-10-19): 124 filas del stream, todas
   win->half_win o loss->half_loss; en el ledger 27 filas de cuarto, 0
   emparejables (sin `start_time`), stake 0, sin cambios.

Concurrencia: el SHA-256 de cada fichero se toma AL PLANIFICAR; bajo el lock se
aborta si el fichero cambio desde entonces (una liquidacion que anadiera filas
entre la lectura y la escritura las perderia), y la copia de seguridad debe
reproducir ese mismo SHA. Ejecutar fuera de las ventanas de SETTLE y DIARIO.

Antes de escribir copia cada fichero tocado a
`data/backups/repair-audit-20261018/` con un manifiesto SHA-256 antes/despues.
Escritura atomica bajo el lock del fichero. Aborta, sin escribir nada, si
algun recuento no coincide con lo esperado.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqp.settlement.quarter_line_fix import pre_fix_quarter_line_mask  # noqa: E402
from sqp.settlement.runner import _pick_identity, exact_history_scores_map  # noqa: E402
from sqp.settlement.settle import _grade  # noqa: E402
from sqp.storage.atomic import atomic_write_csv  # noqa: E402
from sqp.storage.lock import locked  # noqa: E402
from sqp.storage.results_store import ResultsStore  # noqa: E402

BACKUP = ROOT / "data" / "backups" / "repair-audit-20261018"
ESPERADO_KI071 = {"epl": 5, "mls": 1, "ncaaf": 3}       # identidades duplicadas
# AUD-008: filas re-graduadas por fichero (dry-run de Fable, 2026-10-19). El
# ledger (`settled_*`) no tiene `start_time` y no empareja: 0 cambios. Un
# historico ausente o distinto da otro recuento y aborta ANTES de escribir nada
# (revision cruzada de Codex, 2026-10-19: antes se aplicaba KI-071 y AUD-008 se
# quedaba a medias sin poder reintentarse).
ESPERADO_AUD008 = {"graded_brasileirao": 12, "graded_chile": 52, "graded_epl": 2,
                   "graded_laliga": 28, "graded_ligamx": 12, "graded_mls": 8,
                   "graded_seriea": 10}
FLAG = "regrade_aud008"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# SHA-256 de cada fichero en el instante en que se LEYO para planificar.
SHA_PLAN: dict[Path, str] = {}


def _leer(p: Path) -> pd.DataFrame:
    SHA_PLAN[p] = _sha(p)
    return pd.read_csv(p)


def plan_ki071() -> dict[Path, pd.DataFrame]:
    out: dict[Path, pd.DataFrame] = {}
    vistos: dict[str, int] = {}
    for league in ESPERADO_KI071:
        p = ROOT / "data" / "bets" / f"settled_{league}.csv"
        df = _leer(p)
        ident = _pick_identity(df)
        dup = ident.duplicated(keep=False)
        if not dup.any():
            continue
        vistos[league] = int(ident[dup].nunique())
        gen = pd.to_datetime(df["generated_at"], utc=True, errors="coerce", format="mixed")
        orden = df.assign(_i=ident, _g=gen).sort_values(["_i", "_g"], kind="stable")
        fuera = orden.index[orden["_i"].duplicated(keep="last") & orden["_i"].isin(ident[dup])]
        if len(fuera) != vistos[league]:
            raise SystemExit(f"KI-071 {league}: identidades con mas de 2 filas. Aborta.")
        out[p] = df.drop(index=fuera)
    if vistos != ESPERADO_KI071:
        raise SystemExit(f"KI-071: recuento {vistos} != esperado {ESPERADO_KI071}. Aborta.")
    return out


def _regrade(df: pd.DataFrame, league: str) -> tuple[pd.DataFrame, dict]:
    cand = pre_fix_quarter_line_mask(df) & df["result"].isin(
        ["win", "loss", "half_win", "half_loss"])
    info = {"filas_cuarto_pre": int(cand.sum()), "emparejadas": 0, "cambiadas": 0}
    if not cand.any():
        return df, info
    rows = df[cand]
    scores = exact_history_scores_map(rows, ResultsStore(ROOT).load(league), league,
                                      known_events=df)
    out = df.copy()
    flags = (out["flags"].fillna("").astype(str) if "flags" in out.columns
             else pd.Series("", index=out.index))
    for idx, row in rows.iterrows():
        sc = scores.get(row["event_id"])
        if sc is None:
            continue
        info["emparejadas"] += 1
        hs, as_, home = sc
        nuevo = _grade(row, hs, as_, home)
        if nuevo == row["result"]:
            continue
        stake = float(pd.to_numeric(row.get("stake", 0.0), errors="coerce") or 0.0)
        price = float(row["price_decimal"])
        pnl = {"win": stake * (price - 1), "loss": -stake, "push": 0.0, "void": 0.0,
               "half_win": 0.5 * stake * (price - 1), "half_loss": -0.5 * stake}[nuevo]
        out.at[idx, "result"] = nuevo
        out.at[idx, "pnl"] = round(pnl, 2)
        flags.at[idx] = (flags.at[idx] + ";" + FLAG).lstrip(";")
        info["cambiadas"] += 1
        info.setdefault("transiciones", {}).setdefault(f"{row['result']}->{nuevo}", 0)
        info["transiciones"][f"{row['result']}->{nuevo}"] += 1
        if stake > 0:
            info["con_stake"] = info.get("con_stake", 0) + 1
    out["flags"] = flags
    return out, info


def plan_aud008(base: dict[Path, pd.DataFrame]) -> tuple[dict[Path, pd.DataFrame], dict]:
    out: dict[Path, pd.DataFrame] = {}
    resumen: dict = {}
    for carpeta, prefijo in (("calibration", "graded_"), ("bets", "settled_")):
        for p in sorted((ROOT / "data" / carpeta).glob(f"{prefijo}*.csv")):
            league = p.stem[len(prefijo):]
            df = base[p] if p in base else _leer(p)
            if not {"market", "line", "generated_at", "result", "event_id"} <= set(df.columns):
                continue
            nuevo, info = _regrade(df, league)
            if info["filas_cuarto_pre"]:
                if carpeta == "bets" and not info["emparejadas"]:
                    info["nota"] = ("ledger sin `start_time`: 0 emparejables; las filas siguen "
                                    "excluidas por la mascara y no se tocan")
                resumen[str(p.relative_to(ROOT))] = info
            if info["cambiadas"]:
                out[p] = nuevo
    vistos = {p.stem: resumen[str(p.relative_to(ROOT))]["cambiadas"] for p in out}
    if vistos != ESPERADO_AUD008:
        raise SystemExit(f"AUD-008: re-graduadas {vistos} != esperado {ESPERADO_AUD008}. "
                         "Aborta sin escribir nada.")
    return out, resumen


def aplicar(cambios: dict[Path, pd.DataFrame], destino: Path, informe: dict) -> dict:
    """Todo o nada frente a cambios concurrentes (revision cruzada de Codex,
    2026-10-19): toma el lock de TODOS los ficheros, comprueba TODOS los SHA
    planificados y hace TODAS las copias antes de la primera escritura. Antes
    se comprobaba fichero a fichero, y un cambio en el segundo dejaba el
    primero ya reparado, sin manifiesto y sin poder reintentar. El manifiesto
    se escribe antes de reemplazar nada, para que las copias sean localizables
    aunque una escritura falle."""
    manifiesto: dict = {"creado": destino.name, "estado": "en_curso", "informe": informe,
                        "ficheros": {}}
    with ExitStack() as pila:
        for p in cambios:
            pila.enter_context(locked(p))
        for p in cambios:
            if _sha(p) != SHA_PLAN[p]:
                raise SystemExit(f"{p.relative_to(ROOT)} cambio desde que se planifico la "
                                 "reparacion (liquidacion en curso?). Aborta sin escribir nada.")
        for p in cambios:
            rel = p.relative_to(ROOT)
            copia = destino / rel
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, copia)
            if _sha(copia) != SHA_PLAN[p]:
                raise SystemExit(f"La copia de {rel} no reproduce el SHA planificado. "
                                 "Aborta sin escribir nada.")
            manifiesto["ficheros"][str(rel)] = {"sha256_antes": SHA_PLAN[p],
                                                "copia": str(copia.relative_to(ROOT))}
        (destino / "MANIFEST.json").write_text(
            json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
        for p, df in cambios.items():
            atomic_write_csv(df, p)
            manifiesto["ficheros"][str(p.relative_to(ROOT))]["sha256_despues"] = _sha(p)
    manifiesto["estado"] = "aplicado"
    (destino / "MANIFEST.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifiesto


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="escribir (sin el flag: dry-run)")
    args = ap.parse_args()
    k071 = plan_ki071()
    a008, resumen = plan_aud008(k071)
    cambios = {**k071, **a008}
    informe = {
        "aud003": "resuelto en la lectura (ResultsStore.load); el CSV crudo no se toca",
        "ki071_filas_quitadas": {p.stem: int(len(pd.read_csv(p, usecols=[0])) - len(d))
                                 for p, d in k071.items()},
        "aud008": resumen,
        "ficheros": sorted(str(p.relative_to(ROOT)) for p in cambios),
    }
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    if not args.apply:
        print("dry-run: nada escrito.")
        return 0
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = BACKUP / marca
    aplicar(cambios, destino, informe)
    print(f"Aplicado. Copias y manifiesto en {destino.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
