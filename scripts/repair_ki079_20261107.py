"""Reparacion de KI-079 (autorizada por el operador el 2026-11-07, «Elige la mejor
opcion y ejecutala»). UNA sola ejecucion con `--apply`; sin el flag solo informa
(dry-run).

Contexto: partido NCAAF Buffalo Bulls (local) vs UMass Minutemen, game_date
2026-10-17, event_id `7d7f757d2bf4cb7b6d8bbfe9589d25a2`. El resultado real es
25-18 (prorroga incluida; verificado con tres fuentes y coincide con
ResultsStore). La liquidacion uso un marcador distinto (total 42, margen 6).

Se re-gradua SOLO ese event_id con la logica de PRODUCCION
(`settle._grade`, marcador de `runner.exact_history_scores_map` sobre
`ResultsStore`), en:
- `data/calibration/graded_ncaaf.csv` (30 filas del evento);
- `data/bets/settled_ncaaf.csv` (2 filas; no tiene `start_time`, asi que usa el
  marcador que el store dio para el mismo event_id en el graded, tras comprobar
  que local y visitante coinciden).

Solo cambian `result`, `pnl` (recalculado como en repair_audit_20261018; aqui
stake=0, y si alguna fila cambiada tuviera stake>0 se aborta: no esta previsto)
y `flags` (se anade `regrade_ki079` con `;`). Ninguna otra columna ni fila; mismo
orden de columnas y filas.

Es una correccion del REGISTRO: las filas re-graduadas vuelven a ser etiquetas
validas para el gate y la calibracion porque ahora reflejan el marcador real.
No es una afirmacion de rentabilidad.

Guardas: aborta, sin escribir, si el marcador del store no es exactamente
(Buffalo Bulls 25, UMass Minutemen 18) o si los recuentos de cambios por fichero
y transicion no son los congelados (ESPERADO_*). Idempotente: si las filas ya
llevan el flag `regrade_ki079`, informa «ya aplicado» y sale con 0 sin escribir.

Concurrencia: el SHA-256 de cada fichero se toma AL PLANIFICAR; bajo el lock de
TODOS los ficheros se comprueba que no cambiaron y que la copia reproduce ese
SHA antes de la primera escritura. Ejecutar FUERA de las ventanas de SETTLE
(madrugada/12:00) y DIARIO.

Copias en `data/backups/repair-ki079-20261107/<UTC>/` con MANIFEST.json (SHA-256
antes/despues). Escritura atomica. Todo o nada.
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

from sqp.settlement.runner import exact_history_scores_map  # noqa: E402
from sqp.settlement.settle import _grade  # noqa: E402
from sqp.storage.atomic import atomic_write_csv  # noqa: E402
from sqp.storage.lock import locked  # noqa: E402
from sqp.storage.results_store import ResultsStore  # noqa: E402

LEAGUE = "ncaaf"
EVENT_ID = "7d7f757d2bf4cb7b6d8bbfe9589d25a2"
MARCADOR = (25, 18)
LOCAL, VISITANTE = "Buffalo Bulls", "UMass Minutemen"
FLAG = "regrade_ki079"
BACKUP = ROOT / "data" / "backups" / "repair-ki079-20261107"
GRADED_REL = Path("data") / "calibration" / "graded_ncaaf.csv"
SETTLED_REL = Path("data") / "bets" / "settled_ncaaf.csv"

# Recuentos congelados (dry-run 2026-11-07): clave "mercado:antes->despues".
ESPERADO_TRANSICIONES: dict[str, dict[str, int]] = {
    "graded_ncaaf": {"spreads:loss->push": 1, "spreads:loss->win": 3,
                     "spreads:win->loss": 3, "spreads:win->push": 1,
                     "totals:loss->win": 2, "totals:win->loss": 2},
    "settled_ncaaf": {"totals:loss->win": 1},
}
ESPERADO_CAMBIOS = {"graded_ncaaf": 12, "settled_ncaaf": 1}

SHA_PLAN: dict[Path, str] = {}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _leer(p: Path) -> pd.DataFrame:
    SHA_PLAN[p] = _sha(p)
    return pd.read_csv(p)


def _cargar_resultados() -> list[dict]:
    return ResultsStore(ROOT).load(LEAGUE)


def _marcador(graded: pd.DataFrame) -> tuple[int, int, str]:
    """Marcador del store para el evento, por la ruta canonica de produccion."""
    filas = graded[graded["event_id"].astype(str) == EVENT_ID]
    if filas.empty:
        raise SystemExit(f"KI-079: sin filas del evento {EVENT_ID} en graded. Aborta.")
    scores = exact_history_scores_map(filas, _cargar_resultados(), LEAGUE, known_events=graded)
    sc = scores.get(EVENT_ID)
    if sc is None:
        raise SystemExit("KI-079: el store no empareja el evento. Aborta.")
    hs, as_, home = sc
    if (hs, as_) != MARCADOR or home != LOCAL or set(filas["away"].astype(str)) != {VISITANTE}:
        raise SystemExit(f"KI-079: marcador del store {sc} / visitante "
                         f"{sorted(set(filas['away'].astype(str)))} != esperado "
                         f"({LOCAL} {MARCADOR[0]}, {VISITANTE} {MARCADOR[1]}). Aborta.")
    return sc


def _regrade(df: pd.DataFrame, sc: tuple[int, int, str]) -> tuple[pd.DataFrame, dict]:
    hs, as_, home = sc
    idx = df.index[df["event_id"].astype(str) == EVENT_ID]
    info: dict = {"filas_evento": len(idx), "cambiadas": 0, "transiciones": {}}
    if "home" in df.columns and "away" in df.columns:
        if (set(df.loc[idx, "home"].astype(str)) - {LOCAL}
                or set(df.loc[idx, "away"].astype(str)) - {VISITANTE}):
            raise SystemExit("KI-079: local/visitante de las filas no coinciden. Aborta.")
    out = df.copy()
    flags = (out["flags"].fillna("").astype(str) if "flags" in out.columns
             else pd.Series("", index=out.index))
    for i in idx:
        row = df.loc[i]
        nuevo = _grade(row, hs, as_, home)
        if nuevo == row["result"]:
            continue
        stake = float(pd.to_numeric(row.get("stake", 0.0), errors="coerce") or 0.0)
        if stake > 0:
            raise SystemExit("KI-079: fila cambiada con stake>0, no previsto. Aborta.")
        price = float(row["price_decimal"])
        pnl = {"win": stake * (price - 1), "loss": -stake, "push": 0.0, "void": 0.0,
               "half_win": 0.5 * stake * (price - 1), "half_loss": -0.5 * stake}[nuevo]
        out.at[i, "result"] = nuevo
        out.at[i, "pnl"] = round(pnl, 2)
        flags.at[i] = (flags.at[i] + ";" + FLAG).lstrip(";")
        info["cambiadas"] += 1
        k = f"{row['market']}:{row['result']}->{nuevo}"
        info["transiciones"][k] = info["transiciones"].get(k, 0) + 1
    out["flags"] = flags
    return out, info


def _ya_aplicado(df: pd.DataFrame) -> bool:
    if "flags" not in df.columns:
        return False
    f = df.loc[df["event_id"].astype(str) == EVENT_ID, "flags"].fillna("").astype(str)
    return bool(f.str.contains(FLAG, regex=False).any())


def planificar() -> tuple[dict[Path, pd.DataFrame], dict] | None:
    """None si ya esta aplicado. Aborta (SystemExit) ante cualquier recuento distinto."""
    graded_p, settled_p = ROOT / GRADED_REL, ROOT / SETTLED_REL
    graded, settled = _leer(graded_p), _leer(settled_p)
    if _ya_aplicado(graded) or _ya_aplicado(settled):
        return None
    sc = _marcador(graded)
    cambios: dict[Path, pd.DataFrame] = {}
    informe: dict = {"evento": EVENT_ID, "marcador_store": list(sc), "ficheros": {}}
    for p, df in ((graded_p, graded), (settled_p, settled)):
        nuevo, info = _regrade(df, sc)
        informe["ficheros"][p.stem] = info
        if info["cambiadas"] != ESPERADO_CAMBIOS[p.stem]:
            raise SystemExit(f"KI-079 {p.stem}: {info['cambiadas']} cambios != esperado "
                             f"{ESPERADO_CAMBIOS[p.stem]}. Aborta sin escribir nada.")
        esperado_t = ESPERADO_TRANSICIONES[p.stem]
        if info["transiciones"] != esperado_t:
            raise SystemExit(f"KI-079 {p.stem}: transiciones {info['transiciones']} != "
                             f"esperado {esperado_t}. Aborta sin escribir nada.")
        cambios[p] = nuevo
    return cambios, informe


def aplicar(cambios: dict[Path, pd.DataFrame], destino: Path, informe: dict) -> dict:
    """Todo o nada: lock de TODOS los ficheros, todos los SHA y todas las copias
    antes de la primera escritura; manifiesto antes de reemplazar nada."""
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
    plan = planificar()
    if plan is None:
        print("KI-079: ya aplicado (flag regrade_ki079 presente). Nada escrito.")
        return 0
    cambios, informe = plan
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    if not args.apply:
        print("dry-run: nada escrito.")
        return 0
    destino = BACKUP / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    aplicar(cambios, destino, informe)
    print(f"Aplicado. Copias y manifiesto en {destino.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
