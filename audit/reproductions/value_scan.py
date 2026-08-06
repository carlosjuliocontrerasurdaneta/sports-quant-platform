"""Value scan: existe ALGUN lado de mercado donde el mejor precio supere el
valor justo sin vig del propio mercado?

Solo lectura. No usa el modelo: no hay Elo, ni Poisson, ni calibracion. La
pregunta es puramente de precios -- donde el mercado esta en desacuerdo consigo
mismo lo suficiente para que su dispersion supere su propio vig.

Para cada snapshot capturado, cada (mercado, punto):
  consenso mediano por outcome -> probabilidad justa sin vig (metodo power)
  EV_mejor = p_justa * mejor_precio_accesible - 1

Un EV > 0 significa que se paga por encima del valor justo que el propio mercado
declara. Es la definicion operativa de "value bet" y NO requiere predecir nada.

TRAMPA CONOCIDA, por eso se reporta la concentracion: un EV positivo suele venir
de una cotizacion rancia o erronea de una sola casa, que no estara disponible
cuando intentes tomarla. Si los positivos se concentran en pocas casas o tienen
magnitudes enormes, son errores, no oportunidades.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sqp.markets.vig import remove_vig_power   # noqa: E402

ODDS = ROOT / "data" / "odds"
COLS = ["event_id", "captured_at", "market", "outcome", "point",
        "bookmaker", "price_decimal", "home", "away"]

COMMISSION = {"matchbook": 0.015, "betfair_ex_uk": 0.03, "betfair_ex_au": 0.03,
              "betfair_ex_eu": 0.03, "smarkets": 0.02}
US_ONLY = {"fanduel", "draftkings", "betmgm", "betrivers", "williamhill_us",
           "fanatics", "espnbet", "hardrockbet", "ballybet", "windcreek",
           "betus", "superbook", "wynnbet", "unibet_us", "pointsbetus",
           "twinspires", "sugarhouse", "foxbet", "barstool", "lowvig_us"}

LEAGUES = sys.argv[1:] or ["mlb", "wnba", "mls"]

# Filtros de plausibilidad (ver comentario en scan_league).
MAX_PRICE = 51.0        # decimal; por encima es placeholder de exchange
MIN_BOOKS = 5           # mercados finos no dan un consenso utilizable
MAX_OVERROUND = 1.25    # suma de implicitas; mas alto = mercado mal formado
MAX_DEV = 1.5           # cuota maxima admisible como multiplo de su consenso

import logging  # noqa: E402
logging.getLogger("sqp.vig").setLevel(logging.ERROR)


def _eff(price: float, book: str) -> float:
    c = COMMISSION.get(book, 0.0)
    return 1.0 + (price - 1.0) * (1.0 - c) if c else price


def scan_league(league: str) -> tuple[list[float], Counter, int]:
    files = sorted(ODDS.glob(f"odds_{league}_*.csv"))
    evs: list[float] = []
    books = Counter()
    n_sides = 0
    for f in files:
        try:
            df = pd.read_csv(f, usecols=COLS)
        except (ValueError, pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        df["price_decimal"] = pd.to_numeric(df["price_decimal"], errors="coerce")
        df = df[df["price_decimal"].notna() & (df["price_decimal"] > 1.0)]
        df = df[~df["bookmaker"].isin(US_ONLY)]
        if df.empty:
            continue
        df["pt"] = pd.to_numeric(df["point"], errors="coerce").fillna(-9999.0)
        # Un "mercado" a de-vigar = (evento, snapshot, mercado, punto)
        for _key, grp in df.groupby(["event_id", "captured_at", "market", "pt"],
                                    sort=False):
            # --- FILTROS DE PLAUSIBILIDAD -------------------------------------
            # Sin ellos el scan mide basura: los exchanges publican ordenes sin
            # emparejar a 1000.0 decimal (implied 0.001), que producen EV
            # falsos de miles por ciento. Verificado en la primera corrida.
            grp = grp[grp["price_decimal"] <= MAX_PRICE]
            if grp.empty:
                continue
            med = grp.groupby("outcome")["price_decimal"].median()
            if len(med) < 2:
                continue                      # mercado incompleto: sin ancla no-vig
            if grp["bookmaker"].nunique() < MIN_BOOKS:
                continue
            implied = [1.0 / p for p in med.values]
            if any((not np.isfinite(x)) or x <= 0 or x >= 1 for x in implied):
                continue
            overround = float(sum(implied))
            if not (1.0 <= overround <= MAX_OVERROUND):
                continue                      # mercado degenerado o mal formado
            try:
                fair = remove_vig_power(implied)
            except Exception:
                continue
            fair_by = dict(zip(med.index, fair))
            for outcome, sub in grp.groupby("outcome"):
                p = fair_by.get(outcome)
                if p is None or not np.isfinite(p):
                    continue
                m = float(med[outcome])
                # Una cuota a mas de MAX_DEV veces el consenso no es una opinion
                # de mercado: es un error o una orden sin emparejar.
                sub = sub[sub["price_decimal"] <= m * MAX_DEV]
                if sub.empty:
                    continue
                eff = [(str(b), _eff(float(pr), str(b)))
                       for b, pr in zip(sub["bookmaker"], sub["price_decimal"])]
                book, d = max(eff, key=lambda x: x[1])
                ev = p * d - 1.0
                n_sides += 1
                evs.append(ev)
                if ev > 0:
                    books[book] += 1
    return evs, books, n_sides


def main() -> int:
    print("=" * 76)
    print("VALUE SCAN  -- mejor precio accesible vs valor justo sin vig del mercado")
    print("=" * 76)
    print("Sin modelo. Casas solo-EEUU excluidas; comision de exchange descontada.\n")
    all_ev: list[float] = []
    all_books = Counter()
    for lg in LEAGUES:
        evs, books, n = scan_league(lg)
        if not evs:
            print(f"{lg:12s}  sin datos utilizables")
            continue
        a = np.array(evs)
        pos = a[a > 0]
        print(f"{lg:12s}  lados={len(a):7d}  EV>0: {len(pos)/len(a)*100:5.2f}%  "
              f"EV mediano={np.median(a)*100:+6.2f}%  "
              f"EV medio de los positivos={pos.mean()*100 if len(pos) else 0:+6.2f}%")
        all_ev.extend(evs)
        all_books.update(books)

    if not all_ev:
        return 0
    a = np.array(all_ev)
    pos = a[a > 0]
    print("\n" + "-" * 76)
    print(f"TOTAL  lados evaluados={len(a):,}   con EV>0: {len(pos):,} "
          f"({len(pos)/len(a)*100:.2f}%)")
    print(f"EV mediano de TODOS los lados : {np.median(a)*100:+.2f}%")
    if len(pos):
        print(f"EV de los positivos  mediana={np.median(pos)*100:+.2f}%  "
              f"media={pos.mean()*100:+.2f}%  p95={np.percentile(pos,95)*100:+.2f}%  "
              f"max={pos.max()*100:+.1f}%")
        print("\nMagnitud de los EV>0 (los enormes son errores de cotizacion, no valor):")
        for lo, hi in [(0, 0.01), (0.01, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 9e9)]:
            k = ((pos >= lo) & (pos < hi)).sum()
            etiqueta = f"  {lo*100:5.1f}% - {hi*100:6.1f}%" if hi < 9e8 else "  > 10.0%       "
            print(f"{etiqueta}: {k:7d}  ({k/len(pos)*100:5.1f}% de los positivos)")
        print("\nQuien ofrece los EV>0 (concentracion = senal de cotizacion rancia):")
        tot = sum(all_books.values())
        acc = 0
        for i, (b, c) in enumerate(all_books.most_common(10), 1):
            acc += c
            print(f"  {i:2d}. {b:26s} {c:7d}  ({c/tot*100:5.1f}%)  acum {acc/tot*100:5.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
