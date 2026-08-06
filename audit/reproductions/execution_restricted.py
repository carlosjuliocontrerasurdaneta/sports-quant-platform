"""Techo de ejecucion REALISTA: por universo de casas accesible, neto de comision.

Solo lectura. No consume cuota de API ni escribe artefactos del sistema.

Convierte el techo teorico (mejor precio entre 31-67 casas) en la cifra que un
operador en Chile podria cobrar de verdad. Tres metricas por escenario:

  1. Mejora de precio frente a la mediana del consenso (lo que gana la entrada).
  2. EV frente a la probabilidad justa SIN VIG del propio mercado en el momento
     del pick (columna implied_probability_novig). Es la prueba directa de valor
     positivo y NO depende del modelo: si p_novig * d > 1, estas pagando por
     encima del valor justo que el propio mercado declara.
  3. ROI realizado a STAKE PLANO (1 unidad por apuesta) sobre la muestra
     liquidada, con IC bootstrap del 95%.

SUPUESTOS DECLARADOS (cambiar si el operador aporta su lista real de cuentas):
  - Casas solo-EEUU excluidas: no accesibles desde Chile.
  - Comision de exchange aplicada sobre la ganancia neta:
    d_efectiva = 1 + (d - 1) * (1 - c).
  - No se modelan limites de apuesta, cierres de cuenta ni disponibilidad de la
    linea en el instante del pick. Los tres empujan el resultado a la baja.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sqp.audit.clv import CLOSE_MAX_AGE_MIN, _point       # noqa: E402
from sqp.backtesting.roi_engine import load_closing_odds  # noqa: E402
from sqp.pipeline.probabilities import _consensus_lines   # noqa: E402

BETS = ROOT / "data" / "bets"
ODDS = ROOT / "data" / "odds"

# Comision sobre ganancia neta (aproximaciones publicas; ajustar si procede).
COMMISSION = {
    "matchbook": 0.015,
    "betfair_ex_uk": 0.03,
    "betfair_ex_au": 0.03,
    "betfair_ex_eu": 0.03,
    "smarkets": 0.02,
}

# Solo-EEUU: no accesibles desde Chile.
US_ONLY = {
    "fanduel", "draftkings", "betmgm", "betrivers", "williamhill_us",
    "fanatics", "espnbet", "hardrockbet", "ballybet", "windcreek",
    "betus", "superbook", "wynnbet", "unibet_us", "pointsbetus", "twinspires",
    "sugarhouse", "foxbet", "barstool", "lowvig_us",
}

SHARP = {"pinnacle"}
EXCHANGES = set(COMMISSION)
# Offshore de acceso internacional plausible, con riesgo real de limitacion.
OFFSHORE = {"onexbet", "lowvig", "mybookieag", "gtbets", "betonlineag",
            "bovada", "betanysports", "everygame", "marathonbet", "coolbet"}

SCENARIOS = [
    ("A. Solo Pinnacle", SHARP),
    ("B. Pinnacle + exchanges (neto comision)", SHARP | EXCHANGES),
    ("C. B + offshore (riesgo de limitacion)", SHARP | EXCHANGES | OFFSHORE),
    ("D. Todas menos solo-EEUU", None),          # None = todas las accesibles
    ("E. TECHO TEORICO: todas las casas", "all"),
]


def _effective(price: float, book: str) -> float:
    c = COMMISSION.get(book, 0.0)
    return 1.0 + (price - 1.0) * (1.0 - c) if c else price


def _load_settled() -> pd.DataFrame:
    frames = []
    for f in sorted(BETS.glob("settled_*.csv")):
        try:
            df = pd.read_csv(f)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
        if not df.empty:
            frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    return df[df["result"].isin(["win", "loss"])].copy()


def _boot_ci(pnl: np.ndarray, n_boot: int = 5000, seed: int = 42) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(pnl), size=(n_boot, len(pnl)))
    means = pnl[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main() -> int:
    settled = _load_settled()
    recs: list[dict] = []

    for league in sorted(settled["league"].unique()):
        files = sorted(ODDS.glob(f"odds_{league}_*.csv"))
        if not files:
            continue
        odds = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
        odds["captured_ts"] = pd.to_datetime(odds["captured_at"], utc=True, errors="coerce")
        closes = load_closing_odds(ROOT, str(league), max_age_min=CLOSE_MAX_AGE_MIN)
        cons_close = {eid: _consensus_lines(eo) for eid, eo in closes.items()}
        by_event = {str(k): g for k, g in odds.groupby("event_id")}

        for r in settled[settled["league"] == league].itertuples():
            eid = str(r.event_id)
            cons = cons_close.get(eid)
            if not cons:
                continue
            pt = _point(str(r.market), r.line)
            close = cons.get((str(r.market), str(r.selection), pt))
            if close is None or not pd.notna(close) or close <= 1.0:
                continue
            g = by_event.get(eid)
            gen = pd.to_datetime(str(r.generated_at), utc=True, errors="coerce")
            if g is None or pd.isna(gen):
                continue
            prev = g[g["captured_ts"] <= gen]
            if prev.empty:
                continue
            snap = prev[prev["captured_ts"] == prev["captured_ts"].max()]
            same = snap[(snap["market"].astype(str) == str(r.market))
                        & (snap["outcome"].astype(str) == str(r.selection))]
            pts = pd.to_numeric(same["point"], errors="coerce")
            same = same[pts.isna()] if pt is None else same[pts == pt]
            if same.empty:
                continue
            quotes = [(str(b), float(p)) for b, p in
                      zip(same["bookmaker"], pd.to_numeric(same["price_decimal"], errors="coerce"))
                      if pd.notna(p) and p > 1.0]
            if not quotes:
                continue
            recs.append({
                "league": str(league), "market": str(r.market),
                "result": str(r.result),
                "entry_median": float(r.price_decimal),
                "novig": float(r.implied_probability_novig)
                if pd.notna(r.implied_probability_novig) else np.nan,
                "close": float(close),
                "quotes": quotes,
            })

    if not recs:
        print("Sin muestra emparejable.")
        return 0

    print("=" * 78)
    print(f"TECHO DE EJECUCION POR UNIVERSO DE CASAS   (n base = {len(recs)} apuestas liquidadas)")
    print("=" * 78)
    print("Supuestos: solo-EEUU excluidas; comision de exchange sobre ganancia neta;")
    print("sin modelar limites, cierres de cuenta ni disponibilidad instantanea.\n")
    print(f"{'Escenario':42s} {'n':>4s} {'mejora':>8s} {'EV vs justo':>12s} {'ROI plano':>10s} {'IC95%':>18s}")
    print("-" * 78)

    baseline_pnl = None
    for name, allowed in SCENARIOS:
        pnls, evs, imps = [], [], []
        for rec in recs:
            qs = rec["quotes"]
            if allowed == "all":
                pool = qs
                net = [(b, p) for b, p in pool]
            else:
                pool = [(b, p) for b, p in qs if b not in US_ONLY]
                if allowed is not None:
                    pool = [(b, p) for b, p in pool if b in allowed]
                net = [(b, _effective(p, b)) for b, p in pool]
            if not net:
                continue
            book, d = max(net, key=lambda x: x[1])
            imps.append(d / rec["entry_median"] - 1.0)
            if not np.isnan(rec["novig"]):
                evs.append(rec["novig"] * d - 1.0)
            pnls.append((d - 1.0) if rec["result"] == "win" else -1.0)

        if not pnls:
            print(f"{name:42s}    0        --            --         --")
            continue
        arr = np.array(pnls, dtype=float)
        roi = arr.mean()
        lo, hi = _boot_ci(arr)
        ev = np.mean(evs) if evs else float("nan")
        print(f"{name:42s} {len(arr):4d} {np.median(imps)*100:+7.2f}% "
              f"{ev*100:+11.2f}% {roi*100:+9.2f}% "
              f"[{lo*100:+6.2f}%, {hi*100:+6.2f}%]")
        if name.startswith("A."):
            baseline_pnl = arr

    # Referencia: lo que realmente ocurrio, a la mediana del consenso.
    ref = np.array([(rec["entry_median"] - 1.0) if rec["result"] == "win" else -1.0
                    for rec in recs], dtype=float)
    lo, hi = _boot_ci(ref)
    print("-" * 78)
    print(f"{'REFERENCIA: mediana del consenso (lo real)':42s} {len(ref):4d} "
          f"{0.0:+7.2f}% {'':>11s} {ref.mean()*100:+9.2f}% "
          f"[{lo*100:+6.2f}%, {hi*100:+6.2f}%]")
    print()
    print("Lectura: 'EV vs justo' usa la probabilidad sin vig del propio mercado en el")
    print("momento del pick. Positivo = se paga por encima del valor justo declarado por")
    print("el mercado, con independencia del modelo. 'ROI plano' es 1 unidad por apuesta")
    print("sobre la muestra liquidada; el IC95% es bootstrap sobre las mismas apuestas y")
    print("NO cubre riesgo de limitacion, disponibilidad ni cambio de regimen.")
    if baseline_pnl is not None:
        print(f"\nn con Pinnacle disponible: {len(baseline_pnl)} de {len(recs)} "
              f"({len(baseline_pnl)/len(recs)*100:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
