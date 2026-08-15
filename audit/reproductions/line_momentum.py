"""Test terminal: el movimiento pasado de la linea predice el futuro?

Criterio PRE-REGISTRADO en docs/research/2026-08-15-preregistro-momentum-de-linea.md
(commit 331df74, anterior a la primera ejecucion de este script).

No usa el modelo: ni Elo, ni Poisson, ni calibracion. Solo precios y tiempo.

Para cada (evento, mercado, punto, outcome) se toman tres anclajes prepartido:
  t1 = snapshot mas antiguo
  t2 = ultimo snapshot a >= 6h del comienzo   (instante de decision)
  t3 = ultimo snapshot a <= 90min del comienzo (cierre, criterio del gate)

  move_A = p_novig(t2) - p_novig(t1)   el movimiento observable al decidir
  move_B = p_novig(t3) - p_novig(t2)   el movimiento que habria que predecir
  clv    = precio_consenso(t2) / precio_consenso(t3) - 1

La regla evaluada compra en t2 el lado con move_A > 0 (el mercado viene hacia
el) al precio de CONSENSO -- no al mejor precio: ya esta medido que el mejor
precio de 67 casas es anchura de mercado, no informacion.

TRAMPA KI-019, cerrada explicitamente: commence_time vale el ULTIMO reportado
por el proveedor, no uno arbitrario. Con el valor obsoleto entran precios EN
VIVO que fabrican resultados espectaculares y falsos. Ya se colo dos veces en
analisis de este proyecto.

CLV es diagnostico de proceso, no promesa de ganancia. Todas las cifras son
probabilidades estimadas.

  python audit/reproductions/line_momentum.py [liga ...]
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from scipy.stats import binomtest             # noqa: E402
from sqp.markets.vig import remove_vig_power   # noqa: E402

logging.getLogger("sqp.vig").setLevel(logging.ERROR)

ODDS = ROOT / "data" / "odds"
COLS = ["event_id", "captured_at", "commence_time", "market", "outcome",
        "point", "bookmaker", "price_decimal"]

US_ONLY = {"fanduel", "draftkings", "betmgm", "betrivers", "williamhill_us",
           "fanatics", "espnbet", "hardrockbet", "ballybet", "windcreek",
           "betus", "superbook", "wynnbet", "unibet_us", "pointsbetus",
           "twinspires", "sugarhouse", "foxbet", "barstool", "lowvig_us"}

# Filtros de plausibilidad, identicos a value_scan.py (sin ellos el scan mide
# ordenes sin emparejar de exchanges a 1000.0 decimal).
MAX_PRICE = 51.0
MIN_BOOKS = 5
MAX_OVERROUND = 1.25

# Anclajes temporales, en horas hasta el comienzo.
T2_MIN_H = 6.0      # decision: al menos 6h antes
T3_MAX_H = 1.5      # cierre: como CLOSE_MAX_AGE_MIN (90 min) del gate vigente

MIN_N = 200         # criterio 1 del pre-registro


def _leagues() -> list[str]:
    if len(sys.argv) > 1:
        return sys.argv[1:]
    seen = []
    for f in sorted(ODDS.glob("odds_*.csv")):
        lg = f.stem[len("odds_"):].rsplit("_", 1)[0]
        if lg not in seen:
            seen.append(lg)
    return seen


def snapshots(league: str) -> pd.DataFrame:
    """Consenso no-vig por (evento, mercado, punto, outcome, snapshot)."""
    files = sorted(ODDS.glob(f"odds_{league}_*.csv"))
    if not files:
        return pd.DataFrame()
    parts = []
    for f in files:
        try:
            parts.append(pd.read_csv(f, usecols=COLS))
        except (ValueError, pd.errors.EmptyDataError, pd.errors.ParserError):
            continue
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)

    df["price_decimal"] = pd.to_numeric(df["price_decimal"], errors="coerce")
    df = df[df["price_decimal"].notna()]
    df = df[(df["price_decimal"] > 1.0) & (df["price_decimal"] <= MAX_PRICE)]
    df = df[~df["bookmaker"].isin(US_ONLY)]
    if df.empty:
        return pd.DataFrame()

    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
    df["commence_time"] = pd.to_datetime(df["commence_time"], utc=True, errors="coerce")
    df = df[df["captured_at"].notna() & df["commence_time"].notna()]
    if df.empty:
        return pd.DataFrame()

    # --- KI-019: el commence vale el ULTIMO reportado, no uno arbitrario -----
    last = (df.sort_values("captured_at")
              .groupby("event_id")["commence_time"].last())
    df["commence"] = df["event_id"].map(last)
    df = df[df["captured_at"] < df["commence"]]          # nada EN VIVO
    if df.empty:
        return pd.DataFrame()

    df["pt"] = pd.to_numeric(df["point"], errors="coerce").fillna(-9999.0)

    rows = []
    keys = ["event_id", "captured_at", "market", "pt"]
    for (ev, cap, mkt, pt), grp in df.groupby(keys, sort=False):
        if grp["bookmaker"].nunique() < MIN_BOOKS:
            continue
        med = grp.groupby("outcome")["price_decimal"].median()
        if len(med) < 2:
            continue                       # mercado incompleto: sin ancla no-vig
        implied = [1.0 / p for p in med.values]
        if any((not np.isfinite(x)) or x <= 0 or x >= 1 for x in implied):
            continue
        overround = float(sum(implied))
        if not (1.0 <= overround <= MAX_OVERROUND):
            continue
        try:
            fair = remove_vig_power(implied)
        except Exception:
            continue
        ttc = (grp["commence"].iloc[0] - cap).total_seconds() / 3600.0
        for outcome, p_fair, price in zip(med.index, fair, med.values):
            if not np.isfinite(p_fair):
                continue
            rows.append((ev, mkt, pt, str(outcome), cap, ttc,
                         float(price), float(p_fair)))

    return pd.DataFrame(rows, columns=["event_id", "market", "pt", "outcome",
                                       "captured_at", "ttc", "price", "p_fair"])


def anchors(snaps: pd.DataFrame, league: str) -> pd.DataFrame:
    """Una fila por lado con los tres anclajes validos."""
    out = []
    keys = ["event_id", "market", "pt", "outcome"]
    for (ev, mkt, pt, outcome), g in snaps.groupby(keys, sort=False):
        g = g.sort_values("captured_at")
        early = g[g["ttc"] >= T2_MIN_H]
        close = g[g["ttc"] <= T3_MAX_H]
        if early.empty or close.empty:
            continue
        t1, t2, t3 = g.iloc[0], early.iloc[-1], close.iloc[-1]
        # t1 < t2 < t3 estrictamente: sin separacion real move_A es 0 por
        # construccion y la fila no aporta informacion.
        if not (t1["captured_at"] < t2["captured_at"] < t3["captured_at"]):
            continue
        out.append({
            "league": league, "event_id": ev, "market": mkt, "outcome": outcome,
            "move_A": t2["p_fair"] - t1["p_fair"],
            "move_B": t3["p_fair"] - t2["p_fair"],
            "clv": t2["price"] / t3["price"] - 1.0,
        })
    return pd.DataFrame(out)


def _sign_test(clv: np.ndarray) -> tuple[int, int, float]:
    """n no empatadas, positivas, p unilateral. Empates EXCLUIDOS (KI-020)."""
    nz = clv[clv != 0.0]
    if len(nz) == 0:
        return 0, 0, 1.0
    pos = int((nz > 0).sum())
    p = float(binomtest(pos, len(nz), 0.5, alternative="greater").pvalue)
    return len(nz), pos, p


def _report(tag: str, df: pd.DataFrame) -> tuple[int, float]:
    if df.empty:
        print(f"{tag:34s}  sin filas")
        return 0, 1.0
    clv = df["clv"].to_numpy()
    n_nz, pos, p = _sign_test(clv)
    rate = pos / n_nz * 100 if n_nz else 0.0
    print(f"{tag:34s}  n={len(df):5d}  no_emp={n_nz:5d}  "
          f"pos={rate:5.1f}%  CLV med={np.median(clv)*100:+6.3f}%  "
          f"medio={clv.mean()*100:+6.3f}%  p={p:.4f}")
    return n_nz, p


def main() -> int:
    print("=" * 100)
    print("TEST TERMINAL DE MOMENTUM DE LINEA -- el movimiento pasado predice el futuro?")
    print("=" * 100)
    print("Sin modelo. Precio de consenso. Casas solo-EEUU excluidas.")
    print(f"Anclajes: t1=mas antiguo | t2=ultimo a >={T2_MIN_H}h | "
          f"t3=ultimo a <={T3_MAX_H}h del comienzo\n")

    frames = []
    for lg in _leagues():
        snaps = snapshots(lg)
        if snaps.empty:
            continue
        a = anchors(snaps, lg)
        if a.empty:
            print(f"  {lg:34s} 0 lados con los tres anclajes")
            continue
        print(f"  {lg:34s} {len(a):6d} lados")
        frames.append(a)

    if not frames:
        print("\nSin datos utilizables. FAIL por criterio 1.")
        return 0

    df = pd.concat(frames, ignore_index=True)
    rule = df[df["move_A"] > 0].copy()

    print("\n" + "-" * 100)
    print(f"Lados con los tres anclajes: {len(df):,}   "
          f"con move_A > 0 (la regla): {len(rule):,}")

    corr = df[["move_A", "move_B"]].corr().iloc[0, 1]
    print(f"Correlacion move_A <-> move_B (todos los lados): {corr:+.4f}   "
          "(H0: 0; negativa = reversion, positiva = momentum)")

    print("\n--- CRITERIO 1 y 2: la regla completa " + "-" * 60)
    n_nz, p = _report("REGLA (move_A > 0)", rule)
    _report("  control: move_A < 0", df[df["move_A"] < 0])

    print("\n--- CRITERIO 3: sobrevive excluyendo tenis? " + "-" * 53)
    no_tennis = rule[~rule["league"].str.startswith("tennis")]
    n_nz_nt, p_nt = _report("REGLA sin tenis", no_tennis)
    _report("  solo tenis", rule[rule["league"].str.startswith("tennis")])

    print("\n--- Monotonia: el CLV crece con la magnitud de move_A? " + "-" * 42)
    print("    (si no crece, se esta midiendo otra cosa -- fue lo que delato KI-019)")
    for lo, hi in [(0.0, 0.01), (0.01, 0.02), (0.02, 0.05), (0.05, 9.0)]:
        b = rule[(rule["move_A"] >= lo) & (rule["move_A"] < hi)]
        etiqueta = (f"  move_A {lo*100:4.1f}-{hi*100:4.1f}pp" if hi < 9
                    else "  move_A > 5.0pp      ")
        _report(etiqueta, b)

    print("\n--- Desglose por liga (concentracion = senal de artefacto) " + "-" * 38)
    for lg, g in rule.groupby("league"):
        if len(g) >= 30:
            _report(f"  {lg}", g)

    print("\n--- Desglose por mercado " + "-" * 72)
    for mkt, g in rule.groupby("market"):
        if len(g) >= 30:
            _report(f"  {mkt}", g)

    print("\n" + "=" * 100)
    c1 = n_nz >= MIN_N
    c2 = p < 0.05
    c3 = (n_nz_nt >= 30) and (p_nt < 0.05)
    print(f"  Criterio 1  n >= {MIN_N} no empatadas         : "
          f"{'PASS' if c1 else 'FAIL'}  (n={n_nz})")
    print(f"  Criterio 2  test de signo p < 0.05        : "
          f"{'PASS' if c2 else 'FAIL'}  (p={p:.4f})")
    print(f"  Criterio 3  sobrevive excluyendo tenis    : "
          f"{'PASS' if c3 else 'FAIL'}  (n={n_nz_nt}, p={p_nt:.4f})")
    veredicto = "PASS" if (c1 and c2 and c3) else "FAIL"
    print(f"\n  VEREDICTO: {veredicto}")
    if veredicto == "FAIL":
        print("  Por el pre-registro: se cierra el proyecto. No se abre una variante,")
        print("  no se ajusta el umbral, no se prueba otra ventana.")
    else:
        print("  Un PASS NO autoriza apostar dinero: autoriza construir la fase de")
        print("  ejecucion y volver a medirla en shadow, con el gate de CLV intacto.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
