"""EL TEST QUE DECIDE: los lados con EV>0 ganan a la tasa que implica su precio?

Solo lectura. Sin modelo, sin cuota de API.

`value_scan.py` midio PRECIOS: el 15% de los lados de mercado se pagan por
encima del valor justo sin vig. Eso es necesario pero NO suficiente: si el
consenso sin vig esta sesgado, un EV>0 puede ser sistematicamente falso.

Aqui se gradua contra el resultado real. Procedimiento:

  1. Barrido de snapshots -> primer instante en que cada lado
     (evento, mercado, seleccion, punto) alcanza EV>0 al mejor precio accesible.
     Se toma UNA sola observacion por lado: es lo que haria un scanner real
     (apuesta al detectar), y evita contar la misma apuesta en 50 snapshots.
  2. Emparejamiento del evento con su resultado final (nombres normalizados,
     fecha +-1 dia).
  3. Graduacion con la misma funcion de produccion (`settle._grade`).
  4. ROI realizado a stake plano al precio detectado, con IC bootstrap 95%.

CONTROL obligatorio: los lados con EV<0 deben salir claramente peores. Si ambos
grupos rinden igual, el EV no discrimina y la medicion de precios era ruido.

Limitaciones que NO se modelan: disponibilidad de la cuota en el instante de la
apuesta, limites, cierre de cuenta, y correlacion entre lados del mismo partido.
Las cuatro empujan el resultado real a la baja.
"""
from __future__ import annotations

import logging
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sqp.markets.vig import remove_vig_power        # noqa: E402
from sqp.settlement.settle import _grade            # noqa: E402
from sqp.sports.team_names import normalize_key     # noqa: E402
from sqp.storage.results_store import ResultsStore  # noqa: E402

logging.getLogger("sqp.vig").setLevel(logging.ERROR)

ODDS = ROOT / "data" / "odds"
COLS = ["event_id", "captured_at", "market", "outcome", "point",
        "bookmaker", "price_decimal", "home", "away", "commence_time"]

COMMISSION = {"matchbook": 0.015, "betfair_ex_uk": 0.03, "betfair_ex_au": 0.03,
              "betfair_ex_eu": 0.03, "smarkets": 0.02}
US_ONLY = {"fanduel", "draftkings", "betmgm", "betrivers", "williamhill_us",
           "fanatics", "espnbet", "hardrockbet", "ballybet", "windcreek",
           "betus", "superbook", "wynnbet", "unibet_us", "pointsbetus",
           "twinspires", "sugarhouse", "foxbet", "barstool", "lowvig_us"}

MAX_PRICE, MIN_BOOKS, MAX_OVERROUND, MAX_DEV = 51.0, 5, 1.25, 1.5
LEAGUES = sys.argv[1:] or ["mlb", "wnba", "mls"]


def _eff(price: float, book: str) -> float:
    c = COMMISSION.get(book, 0.0)
    return 1.0 + (price - 1.0) * (1.0 - c) if c else price


def _results_map(league: str) -> dict:
    """(home_norm, away_norm, fecha) -> (hs, as_, home_original)."""
    try:
        rows = ResultsStore(ROOT).load(league)
    except Exception:
        return {}
    out = {}
    for r in rows:
        try:
            hs, as_ = int(r["home_score"]), int(r["away_score"])
        except (KeyError, TypeError, ValueError):
            continue
        day = str(r.get("date", ""))[:10]
        out[(normalize_key(str(r["home"])), normalize_key(str(r["away"])), day)] = (
            hs, as_, str(r["home"]))
    return out


def _lookup(res: dict, home: str, away: str, day: str):
    h, a = normalize_key(home), normalize_key(away)
    base = pd.to_datetime(day, errors="coerce")
    if pd.isna(base):
        return None
    for delta in (0, -1, 1):
        d = (base + pd.Timedelta(days=delta)).strftime("%Y-%m-%d")
        hit = res.get((h, a, d))
        if hit:
            return hit
    return None


def scan(league: str) -> list[dict]:
    res = _results_map(league)
    if not res:
        return []
    seen: set[tuple] = set()
    recs: list[dict] = []
    for f in sorted(ODDS.glob(f"odds_{league}_*.csv")):
        try:
            df = pd.read_csv(f, usecols=COLS)
        except (ValueError, pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        df["price_decimal"] = pd.to_numeric(df["price_decimal"], errors="coerce")
        df = df[df["price_decimal"].notna()
                & (df["price_decimal"] > 1.0) & (df["price_decimal"] <= MAX_PRICE)]
        df = df[~df["bookmaker"].isin(US_ONLY)]
        if df.empty:
            continue
        df["pt"] = pd.to_numeric(df["point"], errors="coerce").fillna(-9999.0)
        # CRITICO (KI-019, 2026-08-05): sin este filtro entran snapshots EN VIVO.
        # Un precio tomado con el partido en curso grada como acierto a cuota
        # alta y fabrica un ROI enorme y falso. El proveedor ademas CORRIGE
        # commence_time sobre la marcha, asi que vale el ultimo reportado.
        cap = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
        com = df.groupby("event_id")["commence_time"].transform("max")
        com_ts = pd.to_datetime(com, utc=True, errors="coerce")
        pre = cap.notna() & com_ts.notna() & (cap < com_ts)
        df = df[pre]
        if df.empty:
            continue
        df = df.sort_values("captured_at")          # primer instante primero
        for _k, grp in df.groupby(["event_id", "captured_at", "market", "pt"],
                                  sort=False):
            med = grp.groupby("outcome")["price_decimal"].median()
            if len(med) < 2 or grp["bookmaker"].nunique() < MIN_BOOKS:
                continue
            implied = [1.0 / p for p in med.values]
            if any((not np.isfinite(x)) or x <= 0 or x >= 1 for x in implied):
                continue
            if not (1.0 <= float(sum(implied)) <= MAX_OVERROUND):
                continue
            try:
                fair = remove_vig_power(implied)
            except Exception:
                continue
            fair_by = dict(zip(med.index, fair))
            eid = str(grp["event_id"].iloc[0])
            home, away = str(grp["home"].iloc[0]), str(grp["away"].iloc[0])
            day = str(grp["commence_time"].iloc[0])[:10]
            for outcome, sub in grp.groupby("outcome"):
                key = (eid, str(grp["market"].iloc[0]), str(outcome),
                       float(grp["pt"].iloc[0]))
                if key in seen:
                    continue
                p = fair_by.get(outcome)
                if p is None or not np.isfinite(p):
                    continue
                m = float(med[outcome])
                sub = sub[sub["price_decimal"] <= m * MAX_DEV]
                if sub.empty:
                    continue
                book, d = max(((str(b), _eff(float(pr), str(b)))
                               for b, pr in zip(sub["bookmaker"], sub["price_decimal"])),
                              key=lambda x: x[1])
                ev = p * d - 1.0
                if ev <= 0:
                    continue                      # aun no es oportunidad: seguir mirando
                seen.add(key)                     # primer instante con EV>0: se "apuesta"
                hit = _lookup(res, home, away, day)
                if hit is None:
                    continue
                hs, as_, home_real = hit
                mk = str(grp["market"].iloc[0])
                pt = None if key[3] == -9999.0 else key[3]
                row = pd.Series({"market": mk, "selection": str(outcome),
                                 "line": pt if pt is not None else float("nan")})
                result = _grade(row, hs, as_, home_real)
                recs.append({"league": league, "market": mk, "ev": ev, "price": d,
                             "fair": p, "book": book, "result": result})
    return recs


def _boot(pnl: np.ndarray, n_boot: int = 5000, seed: int = 42):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pnl), size=(n_boot, len(pnl)))
    m = pnl[idx].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def report(recs: list[dict], etiqueta: str) -> None:
    df = pd.DataFrame(recs)
    df = df[df.result.isin(["win", "loss"])]
    if df.empty:
        print(f"{etiqueta}: sin muestra graduable")
        return
    pnl = np.where(df.result == "win", df.price - 1.0, -1.0)
    roi = pnl.mean()
    lo, hi = _boot(pnl)
    hit = (df.result == "win").mean()
    breakeven = (1.0 / df.price).mean()
    print(f"\n{etiqueta}")
    print(f"  n = {len(df)}   EV medio prometido por el precio: {df.ev.mean()*100:+.2f}%")
    print(f"  hit rate observado : {hit*100:5.2f}%")
    print(f"  hit rate de equilibrio (1/cuota): {breakeven*100:5.2f}%")
    print(f"  margen sobre equilibrio: {(hit-breakeven)*100:+.2f} puntos")
    print(f"  ROI realizado a stake plano: {roi*100:+.2f}%   "
          f"IC95% [{lo*100:+.2f}%, {hi*100:+.2f}%]")


def main() -> int:
    print("=" * 78)
    print("TEST DECISIVO: los lados con EV>0 ganan a la tasa que implica su precio?")
    print("=" * 78)
    allr: list[dict] = []
    for lg in LEAGUES:
        r = scan(lg)
        print(f"  {lg:10s} lados EV>0 graduables: {len(r)}")
        allr.extend(r)
    if not allr:
        print("Sin muestra.")
        return 0
    report(allr, "TODOS LOS LADOS CON EV>0 (al mejor precio accesible)")

    df = pd.DataFrame(allr)
    for lo_, hi_, name in [(0, 0.02, "EV pequeno  (0-2%)"),
                           (0.02, 0.05, "EV medio    (2-5%)"),
                           (0.05, 9e9, "EV grande   (>5%)")]:
        sub = df[(df.ev >= lo_) & (df.ev < hi_)]
        if len(sub) >= 30:
            report(sub.to_dict("records"), name)

    sin_1xbet = df[~df.book.isin({"onexbet", "matchbook", "smarkets",
                                  "betfair_ex_uk", "betfair_ex_eu", "betfair_ex_au"})]
    if len(sin_1xbet) >= 30:
        report(sin_1xbet.to_dict("records"),
               "SIN 1xBet NI EXCHANGES (solo casas que no limitan tan agresivo)")

    print("\n--- casas que originaron los lados apostados ---")
    for b, c in Counter(df.book).most_common(8):
        print(f"  {b:26s} {c:6d}  ({c/len(df)*100:5.1f}%)")
    print("\nLectura: si el ROI realizado no es positivo y el margen sobre el punto")
    print("de equilibrio no es > 0, el EV medido sobre precios NO se traduce en")
    print("dinero y el value scanning tampoco es un camino con estos datos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
