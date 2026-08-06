"""Techo de ejecucion: cuanto CLV se recupera tomando el MEJOR precio en vez de
la mediana del consenso.

Solo lectura. No escribe artefactos del sistema ni consume cuota de API.

Pregunta que responde: los picks se registran a `consensus_median`
(pipeline/daily.py:656). Si en el momento del pick se hubiera tomado la mejor
cuota disponible entre las casas que cotizaban, cuanto habria cambiado el CLV?
Y sobre todo: QUE casas habria hecho falta tener para capturarlo?

CLV = precio_entrada / precio_cierre - 1. El cierre se mantiene identico al que
usa la auditoria vigente (consenso mediano del ultimo snapshot fresco previo al
comienzo), asi que la unica variable que cambia es la entrada.

Advertencia de lectura: esto mide un TECHO, no una ganancia. Supone ejecucion
al mejor precio observado, sin limites de apuesta, sin cierre de cuenta y con
la linea disponible en el instante del pick. Ninguna de esas tres cosas esta
garantizada en la practica.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sqp.audit.clv import _point, CLOSE_MAX_AGE_MIN          # noqa: E402
from sqp.backtesting.roi_engine import load_closing_odds      # noqa: E402
from sqp.pipeline.probabilities import _consensus_lines       # noqa: E402

BETS = ROOT / "data" / "bets"
ODDS = ROOT / "data" / "odds"


def _load_settled() -> pd.DataFrame:
    frames = []
    for f in sorted(BETS.glob("settled_*.csv")):
        try:
            df = pd.read_csv(f)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df[df["result"].isin(["win", "loss"])].copy()


def _odds_for(league: str) -> pd.DataFrame:
    files = sorted(ODDS.glob(f"odds_{league}_*.csv"))
    if not files:
        return pd.DataFrame()
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["captured_ts"] = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
    return df


def main() -> int:
    settled = _load_settled()
    if settled.empty:
        print("Sin apuestas liquidadas.")
        return 0

    rows = []
    best_book = Counter()
    books_per_key = []
    # cuantas casas distintas harian falta para capturar el X% de los mejores precios
    per_league_books: dict[str, set] = defaultdict(set)

    for league in sorted(settled["league"].unique()):
        odds = _odds_for(str(league))
        if odds.empty:
            continue
        closes = load_closing_odds(ROOT, str(league), max_age_min=CLOSE_MAX_AGE_MIN)
        cons_close = {eid: _consensus_lines(eo) for eid, eo in closes.items()}
        sub = settled[settled["league"] == league]
        by_event = {str(k): g for k, g in odds.groupby("event_id")}

        for r in sub.itertuples():
            eid = str(r.event_id)
            cons = cons_close.get(eid)
            if not cons:
                continue
            pt = _point(str(r.market), r.line)
            close = cons.get((str(r.market), str(r.selection), pt))
            if close is None or not pd.notna(close) or close <= 1.0:
                continue
            # CONTROL: mejor precio tambien en el CIERRE. Si al comprar en ambos
            # extremos el CLV vuelve a ~0, el +X% no es informacion: es la prima
            # de dispersion del mercado, que se cobra igual pero no predice.
            eo_close = closes.get(eid)
            close_best = None
            if eo_close is not None:
                cands = [ln.price_decimal for ln in eo_close.lines
                         if str(ln.market) == str(r.market)
                         and str(ln.outcome) == str(r.selection)
                         and (pt is None if ln.point is None else ln.point == pt)
                         and ln.price_decimal is not None
                         and pd.notna(ln.price_decimal) and ln.price_decimal > 1.0]
                if cands:
                    close_best = float(max(cands))

            g = by_event.get(eid)
            if g is None:
                continue
            gen = pd.to_datetime(str(r.generated_at), utc=True, errors="coerce")
            if pd.isna(gen):
                continue
            # snapshot vigente en el momento del pick: el ultimo capturado <= generated_at
            prev = g[g["captured_ts"] <= gen]
            if prev.empty:
                continue
            snap_ts = prev["captured_ts"].max()
            snap = prev[prev["captured_ts"] == snap_ts]

            same = snap[(snap["market"].astype(str) == str(r.market))
                        & (snap["outcome"].astype(str) == str(r.selection))]
            if pt is not None:
                same = same[pd.to_numeric(same["point"], errors="coerce") == pt]
            else:
                same = same[pd.to_numeric(same["point"], errors="coerce").isna()]
            prices = pd.to_numeric(same["price_decimal"], errors="coerce")
            prices = prices[prices.notna() & (prices > 1.0)]
            if prices.empty:
                continue

            entry_median = float(r.price_decimal)
            entry_best = float(prices.max())
            idx_best = prices.idxmax()
            book = str(same.loc[idx_best, "bookmaker"])
            best_book[book] += 1
            per_league_books[str(league)].add(book)
            books_per_key.append(int(prices.size))

            rows.append({
                "league": str(league), "market": str(r.market),
                "n_books": int(prices.size),
                "entry_median": entry_median, "entry_best": entry_best,
                "close": float(close),
                "clv_median_entry": entry_median / float(close) - 1.0,
                "clv_best_entry": entry_best / float(close) - 1.0,
                "clv_best_both": (entry_best / close_best - 1.0
                                  if close_best else float("nan")),
                "improvement": entry_best / entry_median - 1.0 if entry_median > 0 else float("nan"),
            })

    if not rows:
        print("Ninguna apuesta pudo emparejarse a un snapshot de entrada y un cierre.")
        return 0

    df = pd.DataFrame(rows)
    n = len(df)
    print("=" * 72)
    print(f"TECHO DE EJECUCION  ({n} apuestas liquidadas emparejadas a entrada y cierre)")
    print("=" * 72)
    print(f"Casas cotizando por seleccion: mediana {df.n_books.median():.0f}, "
          f"media {df.n_books.mean():.1f}, max {df.n_books.max()}")
    print()
    print("CLV mediano  |  entrada = mediana del consenso : "
          f"{df.clv_median_entry.median() * 100:+.4f}%")
    print("CLV mediano  |  entrada = MEJOR precio         : "
          f"{df.clv_best_entry.median() * 100:+.4f}%")
    print("CLV medio    |  entrada = mediana del consenso : "
          f"{df.clv_median_entry.mean() * 100:+.4f}%")
    print("CLV medio    |  entrada = MEJOR precio         : "
          f"{df.clv_best_entry.mean() * 100:+.4f}%")
    ctrl = df[df.clv_best_both.notna()]
    print("CONTROL      |  mejor en entrada Y en cierre    : "
          f"{ctrl.clv_best_both.median() * 100:+.4f}%  (n={len(ctrl)})")
    print("   -> si este control vuelve a ~0, el +X% de arriba es PRIMA DE")
    print("      DISPERSION (dinero real, pero no capacidad predictiva).")
    print()
    mlb = df[df.league == "mlb"]
    if len(mlb) >= 30:
        print(f"Solo MLB (muestra mas limpia, n={len(mlb)}): "
              f"mediana {mlb.clv_median_entry.median()*100:+.4f}% -> "
              f"mejor {mlb.clv_best_entry.median()*100:+.4f}%")
        print()
    print(f"Mejora de precio mediana: {df.improvement.median() * 100:+.3f}%")
    print(f"Mejora de precio media  : {df.improvement.mean() * 100:+.3f}%")
    print(f"% de picks donde el mejor precio supera a la mediana: "
          f"{(df.improvement > 1e-9).mean() * 100:.1f}%")
    print()
    print("--- por (liga, mercado), n >= 20 ---")
    seg = (df.groupby(["league", "market"])
             .agg(n=("clv_best_entry", "size"),
                  clv_mediana=("clv_median_entry", "median"),
                  clv_mejor=("clv_best_entry", "median"),
                  mejora=("improvement", "median"))
             .reset_index())
    seg = seg[seg.n >= 20].sort_values("clv_mejor", ascending=False)
    if seg.empty:
        print("  (ningun segmento alcanza n=20)")
    else:
        for s in seg.itertuples():
            print(f"  {s.league:28s} {s.market:8s} n={s.n:4d}  "
                  f"mediana {s.clv_mediana*100:+7.3f}%  ->  mejor {s.clv_mejor*100:+7.3f}%  "
                  f"(mejora {s.mejora*100:+.2f}%)")
    print()
    print("--- QUE casas dan el mejor precio (top 15) ---")
    total = sum(best_book.values())
    acc = 0
    for i, (b, c) in enumerate(best_book.most_common(15), 1):
        acc += c
        print(f"  {i:2d}. {b:28s} {c:5d} veces  ({c/total*100:5.1f}%)  acumulado {acc/total*100:5.1f}%")
    print(f"\n  Casas distintas que aparecen como mejor precio: {len(best_book)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
